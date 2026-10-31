"""Bounded journal campaign: validation tuning, paired replication and frozen tests.

All GPU work runs inside Kaggle. Images stay in scratch; checkpoints and compact
evidence stay in the notebook's output directory. No result is fabricated when
the time budget is insufficient to complete a stage.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

from .dataset_variants import digest, file_hash, save_json
from .experiment import ROOT, _train_one, code_fingerprint, load_config, utc_now
from .journal_data import link, prepare_context, variant
from .metrics import write_results
from .exposure import effective_samples

CHECKPOINT_SHA = "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef"


def candidate(optimizer, lr, decay=0.0005):
    return {"optimizer":optimizer,"lr0":lr,"momentum":0.9,"weight_decay":decay}


def choose_candidates(rows):
    choices, diagnostics = {}, {}
    for optimizer in ("AdamW","MuSGD","SGD"):
        groups = {}
        for row in rows:
            if row["optimizer"] == optimizer:
                groups.setdefault(row["candidate_id"],[]).append(row)
        ranked=[]
        for identity, trials in groups.items():
            cells={(r["data_fraction"],r["noise_probability"]) for r in trials}
            if len(trials)!=2 or cells!={(1.0,0.0),(0.2,0.2)} or any(r["status"]!="completed" for r in trials):continue
            hp=trials[0]["hyperparameters"]
            ranked.append({"candidate_id":identity,"hyperparameters":hp,
                           "mean_anchor_val_map":statistics.mean(r["val_map50_95"] for r in trials)})
        if not ranked:raise RuntimeError(f"No valid tuning candidate for {optimizer}")
        ranked.sort(key=lambda r:(-r["mean_anchor_val_map"],r["hyperparameters"]["lr0"],r["hyperparameters"]["weight_decay"]))
        choices[optimizer]=ranked[0]["hyperparameters"]
        diagnostics[optimizer]={"ranked":ranked,"selection_margin_ap_points":100*(ranked[0]["mean_anchor_val_map"]-ranked[1]["mean_anchor_val_map"]) if len(ranked)>1 else None,
            "tried_candidates":len(groups),"valid_candidates":len(ranked)}
    return choices,diagnostics


def select_confirmatory_rows(rows):
    """Only complete prespecified seed blocks; failures remain in the full ledger."""
    selected=[];incomplete=[]
    for dataset,optimizers in (("wildlife",{"AdamW","MuSGD","SGD"}),("voc2007",{"AdamW","MuSGD"})):
        for block in (101,102,103,104,105):
            phase=f"{dataset}_confirmation_{block}"
            group=[r for r in rows if phase in r.get("roles",[])]
            if not group:continue
            expected={(o,f,n) for o in optimizers for f in (0.2,1.0) for n in (0.0,0.2)}
            found={(r["optimizer"],r["data_fraction"],r["noise_probability"]) for r in group if r["status"]=="completed"}
            if found==expected and len(group)==len(expected):selected.extend(group)
            else:incomplete.append({"phase":phase,"completed_cells":len(found),"expected_cells":len(expected)})
    return selected,incomplete


class Campaign:
    def __init__(self, output: Path, plan: dict, max_seconds: int, preflight=False):
        self.start=time.monotonic();self.deadline=self.start+max_seconds
        self.training_deadline=self.deadline-(90 if preflight else 1800)
        self.output=output.resolve();self.output.mkdir(parents=True,exist_ok=True)
        if (self.output/"manifest.json").exists():raise FileExistsError("Use a new output directory; never mix campaign attempts")
        self.scratch=Path('/tmp/muon_yolo_journal')/digest([str(output),utc_now()])[:12]
        self.scratch.mkdir(parents=True)
        self.plan=plan;self.preflight=preflight;self.rows=[];self.contexts={};self.cache={};self.skipped=[]
        self.base=load_config(ROOT/'configs/pilot.yaml')
        self.manifest={"status":"preflight","started_utc":utc_now(),"max_notebook_seconds":max_seconds,
            "identity":{"plan":plan,"plan_sha256":digest(plan),"code_sha256":code_fingerprint()},
            "test_evaluated":False,"purpose":"Fixed-exposure recipe comparison for journal development"}
        save_json(self.output/'manifest.json',self.manifest)
        save_json(self.output/'frozen_plan_before_training.json',plan)
        os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
        os.environ.setdefault('WANDB_MODE','disabled');os.environ.setdefault('YOLO_AUTOINSTALL','false')
        os.environ.setdefault('YOLO_VERBOSE','false')
        import torch,ultralytics
        from ultralytics import YOLO,settings
        self.torch,self.YOLO=torch,YOLO
        if not torch.cuda.is_available() or ultralytics.__version__!='8.4.187':raise RuntimeError("Pinned Ultralytics and CUDA required")
        settings.update({k:False for k in ('wandb','mlflow','comet','tensorboard','clearml','neptune','hub','sync') if k in settings})
        self.hardware={"gpu":torch.cuda.get_device_name(0),"device_used":0,"gpu_count_visible":torch.cuda.device_count(),
            "python":sys.version,"torch":str(torch.__version__),"cuda":torch.version.cuda,"ultralytics":ultralytics.__version__}
        self.manifest['environment']=self.hardware
        self.weights=self.output/'initial_weights/yolo26n.pt';self.weights.parent.mkdir(exist_ok=True)
        model=YOLO(str(self.weights))
        if file_hash(self.weights)!=CHECKPOINT_SHA:raise RuntimeError("Pretrained checkpoint hash changed")
        save_json(self.output/'checkpoint_lineage.json',{"sha256":CHECKPOINT_SHA,"pretraining_train_args":model.ckpt.get('train_args',{}),
            "note":"Official checkpoint; exact bytes pinned. Pretraining-image overlap is not excluded."})
        del model
        freeze=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True,check=True)
        (self.output/'environment-lock.txt').write_text(freeze.stdout,encoding='utf-8')
        for name in ('wildlife','voc2007'):
            print('PREPARE_DATASET',name,flush=True)
            context=prepare_context(name,self.scratch,self.output/'datasets'/name,ROOT,val_limit=512 if name=='voc2007' else None)
            expected=plan.get('expected_dataset_fingerprints',{}).get(name)
            if expected and context['source']['fingerprint']!=expected:raise RuntimeError(f"Frozen {name} source/split changed")
            self.contexts[name]=context
            print('DATASET_READY',name,context['source']['counts'],flush=True)
        self.manifest.update(status='running',dataset_fingerprints={k:v['source']['fingerprint'] for k,v in self.contexts.items()})
        self.flush()

    def remaining(self):return self.training_deadline-time.monotonic()

    def flush(self):
        write_results(self.output,self.rows)
        self.manifest.update(updated_utc=utc_now(),elapsed_notebook_seconds=time.monotonic()-self.start,
            completed_runs=sum(r['status']=='completed' for r in self.rows),attempted_runs=len(self.rows),skipped=self.skipped)
        save_json(self.output/'manifest.json',self.manifest)

    def estimate(self,epochs=20):
        rates=[r['run_call_seconds']/r['epochs_budget'] for r in self.rows if r['status']=='completed' and r.get('samples_per_epoch')==1024]
        return epochs*max(18,statistics.median(rates) if rates else 20)+60

    def has_block_budget(self,count,epochs=20):return self.remaining()>1.15*count*self.estimate(epochs)+120

    def trial(self,dataset,fraction,noise,block,hp,phase,epochs=20,fixed_samples=1024,head_multiplier=3.0):
        context=self.contexts[dataset]
        path,data=variant(context,fraction,noise,block['subset_seed'],block['corruption_seed'])
        cfg=copy.deepcopy(self.base)
        cfg.update(study='journal',dataset=dataset,fractions=[fraction],noise_levels=[noise],
            subset_seed=block['subset_seed'],corruption_seed=block['corruption_seed'],training_seeds=[block['training_seed']],
            optimizers={hp['optimizer']:{k:v for k,v in hp.items() if k!='optimizer'}},
            sampling={"mode":"shuffled_cyclic_stream_v1","samples_per_epoch":effective_samples(data['train_images'],self.base['train']['batch'],fixed_samples),
                      "musgd_head_lr_multiplier":head_multiplier})
        cfg['train']['epochs']=epochs
        if self.preflight:cfg['train']['imgsz']=320
        spec={"study":cfg,"code_sha256":code_fingerprint(),"environment":self.hardware,"checkpoint_sha256":CHECKPOINT_SHA,
              "source_fingerprint":context['source']['fingerprint'],"variant_fingerprint":data['fingerprint'],
              "optimizer":hp['optimizer'],"seed":block['training_seed']}
        run_id=f"journal-{dataset}-{hp['optimizer']}-s{block['training_seed']}-{digest(spec)[:12]}"
        if run_id in self.cache:
            row=self.cache[run_id]
            if phase not in row['roles']:row['roles'].append(phase)
            save_json(self.output/'runs'/run_id/f"attempt-{row['attempt']:03d}"/'result.json',row)
            self.flush();return row
        if self.remaining()<self.estimate(epochs)+60:
            raise TimeoutError("Insufficient reserved time for another complete training run")
        row=_train_one(self.YOLO,self.torch,cfg,self.output,path,data,block['training_seed'],hp['optimizer'],run_id,spec,self.rows,deadline=self.training_deadline-30)
        row.update(dataset=dataset,subset_seed=block['subset_seed'],corruption_seed=block['corruption_seed'],
            hyperparameters=hp,candidate_id=digest(hp)[:12],roles=[phase],checkpoint_sha256=CHECKPOINT_SHA,
            source_fingerprint=context['source']['fingerprint'])
        save_json(self.output/'runs'/run_id/f"attempt-{row['attempt']:03d}"/'result.json',row)
        if row['status']=='completed':
            for other in self.rows:
                if other['status']=='completed' and other['seed']==row['seed'] and other['variant_fingerprint']==row['variant_fingerprint'] and other.get('sampling')==row.get('sampling') and other['epochs_budget']==epochs:
                    if other['exposure_order_sha256']!=row['exposure_order_sha256']:raise RuntimeError("Paired image order differs")
        self.rows.append(row);self.cache[run_id]=row;self.flush()
        print('CAMPAIGN_RESULT',json.dumps({k:row.get(k) for k in ('run_id','dataset','roles','status','val_map50_95','images_seen','optimizer_steps','training_seconds')}),flush=True)
        return row

    def grid(self,dataset,block,choices,phase,epochs=20,fixed_samples=1024,noises=(0.0,0.2)):
        for i,(fraction,noise) in enumerate((f,n) for f in (0.2,1.0) for n in noises):
            optimizers=list(choices)
            if (i+block['training_seed'])%2:optimizers.reverse()
            for optimizer in optimizers:self.trial(dataset,fraction,noise,block,choices[optimizer],phase,epochs,fixed_samples)

    def run_preflight(self):
        block={"training_seed":42,"subset_seed":2026,"corruption_seed":2027}
        for dataset in self.contexts:
            for hp in self.defaults().values():self.trial(dataset,0.2,0.2,block,hp,'gpu_preflight',epochs=2,fixed_samples=64)
        if len(self.rows)!=6 or any(r['status']!='completed' for r in self.rows):raise RuntimeError("GPU preflight failed")
        for name in self.contexts:
            group=[r for r in self.rows if r['dataset']==name]
            if len({r['exposure_order_sha256'] for r in group})!=1:raise RuntimeError("GPU preflight sampling not paired")
        self.manifest['status']='completed';self.flush()

    @staticmethod
    def defaults():return {o:candidate(o,0.001 if o=='AdamW' else 0.01) for o in ('AdamW','MuSGD','SGD')}

    def run_main(self):
        control={"training_seed":42,"subset_seed":2026,"corruption_seed":2027}
        self.grid('wildlife',control,{k:v for k,v in self.defaults().items() if k!='SGD'},'variable_exposure_control',fixed_samples=None)
        self.grid('wildlife',control,self.defaults(),'fixed_exposure_defaults')
        development={"training_seed":11,"subset_seed":2026,"corruption_seed":2027}
        rates={'AdamW':[0.0003,0.001,0.003],'MuSGD':[0.003,0.01,0.03],'SGD':[0.003,0.01,0.03]}
        for i in range(6):
            for optimizer in ('AdamW','MuSGD','SGD'):
                hp=candidate(optimizer,rates[optimizer][i//2],[0.0,0.0005][i%2])
                for f,n in ((1.0,0.0),(0.2,0.2)):self.trial('wildlife',f,n,development,hp,'tuning',epochs=10)
        tuning=[r for r in self.rows if 'tuning' in r['roles']]
        choices,diagnostics=choose_candidates(tuning)
        boundary=any(choices[o]['lr0'] in (rates[o][0],rates[o][-1]) for o in choices)
        # Keep time for all 60 mandatory confirmation/transfer runs before extension.
        if boundary and self.remaining()>1.15*(12*self.estimate(10)+60*self.estimate(20))+120:
            for optimizer in ('AdamW','MuSGD','SGD'):
                lr=choices[optimizer]['lr0']
                new_lr=rates[optimizer][-1]*3 if lr==rates[optimizer][-1] else rates[optimizer][0]/3
                for decay in (0.0,0.0005):
                    for f,n in ((1.0,0.0),(0.2,0.2)):
                        self.trial('wildlife',f,n,development,candidate(optimizer,new_lr,decay),'tuning',epochs=10)
            choices,diagnostics=choose_candidates([r for r in self.rows if 'tuning' in r['roles']])
        elif boundary:self.skipped.append('Equal-budget boundary extension: insufficient time')
        save_json(self.output/'selected_hyperparameters.json',{"selected":choices,"diagnostics":diagnostics,
            "selection_split":"wildlife validation anchors only","frozen_utc":utc_now(),"boundary_extension_triggered":boundary})
        for block_id in (101,102,103):
            block={"training_seed":block_id,"subset_seed":3000+block_id,"corruption_seed":4000+block_id}
            self.grid('wildlife',block,choices,f'wildlife_confirmation_{block_id}')
        external={o:choices[o] for o in ('AdamW','MuSGD')}
        for block_id in (101,102,103):
            block={"training_seed":block_id,"subset_seed":3000+block_id,"corruption_seed":4000+block_id}
            self.grid('voc2007',block,external,f'voc2007_confirmation_{block_id}')
        long_block={"training_seed":101,"subset_seed":3101,"corruption_seed":4101}
        if self.has_block_budget(4,60):self.grid('wildlife',long_block,external,'long_schedule_transfer',epochs=60,noises=(0.2,))
        else:self.skipped.append('Long-schedule transfer block: insufficient reserved time')
        if self.has_block_budget(4):
            for f in (0.2,1.0):
                for n in (0.0,0.2):self.trial('wildlife',f,n,long_block,choices['MuSGD'],'head_lr_1x_ablation',head_multiplier=1.0)
        else:self.skipped.append('Matched-head-LR ablation: insufficient reserved time')
        for block_id in (104,105):
            if self.has_block_budget(12):
                self.grid('wildlife',{"training_seed":block_id,"subset_seed":3000+block_id,"corruption_seed":4000+block_id},choices,f'wildlife_confirmation_{block_id}')
            else:self.skipped.append(f'Optional primary block {block_id}: insufficient reserved time')

    def final_test(self):
        selected,incomplete=select_confirmatory_rows(self.rows)
        required={(d,s) for d in ('wildlife','voc2007') for s in (101,102,103)}
        found={(r['dataset'],r['seed']) for r in selected}
        if incomplete or not required.issubset(found):
            self.manifest['final_test_status']='not_opened_incomplete_confirmation';return
        frozen={"frozen_utc":utc_now(),"plan_sha256":digest(self.plan),"code_sha256":code_fingerprint(),
                "selection":"best checkpoints by validation; no changes after opening test",
                "checkpoints":[{k:r[k] for k in ('run_id','dataset','seed','data_fraction','noise_probability','best_weights','best_weights_sha256','variant_fingerprint','hyperparameters')} for r in selected]}
        save_json(self.output/'frozen_final_test_plan.json',frozen)
        freeze_hash=digest(frozen);test_rows=[]
        for row in selected:
            if self.deadline-time.monotonic()<90:
                self.manifest['final_test_status']='partial_budget_exhausted';break
            context=self.contexts[row['dataset']]
            data_yaml,_=variant(context,row['data_fraction'],row['noise_probability'],row['subset_seed'],row['corruption_seed'])
            if file_hash(Path(row['best_weights']))!=row['best_weights_sha256']:raise RuntimeError("Frozen checkpoint changed")
            model=self.YOLO(row['best_weights'])
            def stop_validation(validator):
                if time.monotonic()>self.deadline-30:raise TimeoutError("Final-test evaluation budget exhausted")
            model.add_callback('on_val_batch_end',stop_validation)
            started=time.perf_counter()
            try:
                metrics=model.val(data=str(data_yaml),split='test',imgsz=512,batch=16,device=0,workers=2,
                    plots=False,verbose=False,save_json=True,conf=0.001,iou=0.7,max_det=300,
                    project=str(self.output/'final_test'),name=row['run_id'],exist_ok=False)
                result={"run_id":row['run_id'],"dataset":row['dataset'],"seed":row['seed'],"optimizer":row['optimizer'],
                    "data_fraction":row['data_fraction'],"noise_probability":row['noise_probability'],
                    "test_map50_95":float(metrics.box.map),"test_map50":float(metrics.box.map50),
                    "test_precision":float(metrics.box.mp),"test_recall":float(metrics.box.mr),
                    "test_per_class_map50_95":[float(v) for v in metrics.box.maps],"status":"completed",
                    "freeze_sha256":freeze_hash,"evaluation_seconds":time.perf_counter()-started}
                if not all(math.isfinite(result[k]) and 0<=result[k]<=1 for k in ('test_map50_95','test_map50','test_precision','test_recall')):raise ValueError("Invalid frozen test metrics")
            except Exception as error:
                result={"run_id":row['run_id'],"dataset":row['dataset'],"status":"failed","error":f"{type(error).__name__}: {error}","freeze_sha256":freeze_hash}
            test_rows.append(result)
            save_json(self.output/'final_test_results.json',test_rows)
            self.manifest['test_evaluated']=True;self.flush()
            del model;self.torch.cuda.empty_cache()
        else:self.manifest['final_test_status']='completed' if all(r['status']=='completed' for r in test_rows) else 'completed_with_failures'

    def run(self):
        try:
            if self.preflight:self.run_preflight()
            else:
                try:self.run_main()
                except TimeoutError as error:self.skipped.append(str(error))
                self.final_test()
                self.manifest['status']='completed' if self.manifest.get('final_test_status')=='completed' else 'partial'
        except Exception as error:
            self.manifest.update(status='failed',error=f"{type(error).__name__}: {error}")
            raise
        finally:
            self.flush()
            from .journal_statistics import summarize_campaign
            summarize_campaign(self.output)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-seconds',type=int,required=True)
    parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args()
    Campaign(args.output,json.loads(args.plan.read_text()),args.max_seconds,args.preflight).run()


if __name__=='__main__':main()
