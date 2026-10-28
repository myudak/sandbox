"""Response-only LoRA training on a local pretrained model, with verified labels."""
import json
import math
from pathlib import Path
import random
import time
import torch
from .runtime import private_runtime,seed_all,save_json,hardware
from .tokenization import records

MODEL_ID='Qwen/Qwen3-0.6B'
MODEL_REVISION='c1899de289a04d12100db370d81485cdf75e47ca'

from .responses import encode_response,load_samples

def tensor_sample(sample,device):
    return {key:torch.tensor([sample[key]],dtype=torch.long,device=device) for key in ('input_ids','attention_mask','labels')}

def tensor_batch(samples,device,pad_id):
    longest=max(len(sample['input_ids']) for sample in samples)
    batch={key:[] for key in ('input_ids','attention_mask','labels')}
    for sample in samples:
        padding=longest-len(sample['input_ids'])
        batch['input_ids'].append(sample['input_ids']+[pad_id]*padding)
        batch['attention_mask'].append(sample['attention_mask']+[0]*padding)
        batch['labels'].append(sample['labels']+[-100]*padding)
    return {key:torch.tensor(value,dtype=torch.long,device=device) for key,value in batch.items()}

@torch.no_grad()
def evaluate(model,samples,device,limit=64):
    model.eval()
    total=tokens=0
    for sample in samples[:limit]:
        batch=tensor_sample(sample,device)
        count=int((batch['labels'][:,1:]!=-100).sum())
        total+=float(model(**batch,use_cache=False).loss)*count
        tokens+=count
    return {'loss':total/tokens,'perplexity':math.exp(min(total/tokens,50)),'evaluated_target_tokens':tokens,'evaluated_examples':min(limit,len(samples))}

def train(model_path,dataset,output,steps=100,accumulation=4,max_length=128,lr=2e-4,seed=42,resume=None,micro_batch=1,rank=8):
    private_runtime()
    seed_all(seed)
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import LoraConfig,get_peft_model,PeftModel
    dataset,output=Path(dataset),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    dtype=torch.bfloat16 if device=='cuda' and torch.cuda.is_bf16_supported() else (torch.float16 if device=='cuda' else torch.float32)
    tokenizer=AutoTokenizer.from_pretrained(model_path,local_files_only=True,trust_remote_code=False)
    samples,training_stats=load_samples(dataset/'sft_train.jsonl',tokenizer,max_length,5000,seed)
    validation,validation_stats=load_samples(dataset/'sft_validation.jsonl',tokenizer,max_length,256,seed)
    test,test_stats=load_samples(dataset/'sft_test.jsonl',tokenizer,max_length,256,seed)
    model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,trust_remote_code=False,dtype=dtype,attn_implementation='sdpa').to(device)
    model.config.use_cache=False
    baseline_validation=evaluate(model,validation,device)
    baseline_test=evaluate(model,test,device)
    base_parameters=sum(p.numel() for p in model.parameters())
    if resume:
        model=PeftModel.from_pretrained(model,resume,is_trainable=True,local_files_only=True)
    else:
        model=get_peft_model(model,LoraConfig(r=rank,lora_alpha=2*rank,lora_dropout=.05,target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM',bias='none'))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model.enable_input_require_grads()
    parameters=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(parameters,lr=lr,weight_decay=.01)
    scaler=torch.amp.GradScaler('cuda',enabled=device=='cuda' and dtype==torch.float16)
    rng=random.Random(seed)
    start=0
    if resume:
        state=torch.load(Path(resume)/'training_state.pt',map_location=device,weights_only=True)
        optimizer.load_state_dict(state['optimizer'])
        rng.setstate(state['python_rng'])
        torch.set_rng_state(state['torch_rng'].cpu())
        if device=='cuda' and state['cuda_rng']:
            torch.cuda.set_rng_state_all([r.cpu() for r in state['cuda_rng']])
        scaler.load_state_dict(state['scaler'])
        start=state['step']
    history=[]
    trained_tokens=0
    started=time.perf_counter()
    if device=='cuda':
        torch.cuda.reset_peak_memory_stats()
    for step in range(start,steps):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        rate=lr*min(1,(step+1)/5)*(.1+.9*.5*(1+math.cos(math.pi*step/max(1,steps))))
        for group in optimizer.param_groups:
            group['lr']=rate
        chosen=[[rng.choice(samples) for _ in range(micro_batch)] for _ in range(accumulation)]
        target_count=sum(s['target_tokens'] for group in chosen for s in group)
        loss_value=0
        for group in chosen:
            batch=tensor_batch(group,device,tokenizer.pad_token_id or tokenizer.eos_token_id)
            group_count=sum(s['target_tokens'] for s in group)
            with torch.autocast(device_type=device,dtype=dtype,enabled=device=='cuda'):
                loss=model(**batch,use_cache=False).loss*(group_count/target_count)
            scaler.scale(loss).backward()
            loss_value+=float(loss.detach())
        scaler.unscale_(optimizer)
        norm=float(torch.nn.utils.clip_grad_norm_(parameters,1.0))
        scaler.step(optimizer)
        scaler.update()
        trained_tokens+=target_count
        if (step+1)%20==0 or step+1==steps:
            valid=evaluate(model,validation,device,limit=16)
            point={'step':step+1,'train_loss':loss_value,'validation_loss':valid['loss'],'trained_target_tokens':trained_tokens,'gradient_norm':norm,'learning_rate':rate,'elapsed_seconds':time.perf_counter()-started}
            history.append(point)
            print(json.dumps(point),flush=True)
            model.save_pretrained(output/'adapter',safe_serialization=True)
            tokenizer.save_pretrained(output/'adapter')
            torch.save({'optimizer':optimizer.state_dict(),'step':step+1,'python_rng':rng.getstate(),'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all() if device=='cuda' else [],'scaler':scaler.state_dict()},output/'adapter'/'training_state.pt')
    elapsed=time.perf_counter()-started
    result={'track':'lora','base_model_id':MODEL_ID,'base_revision':MODEL_REVISION,'license':'Apache-2.0','base_parameters':base_parameters,'trainable_parameters':sum(p.numel() for p in parameters),'rank':rank,'modules':['q_proj','v_proj'],'dtype':str(dtype),'quantization':False,'seed':seed,'steps':steps,'start_step':start,'max_length':max_length,'micro_batch':micro_batch,'gradient_accumulation':accumulation,'initial_learning_rate':lr,'trained_target_tokens_this_run':trained_tokens,'seconds':elapsed,'target_tokens_per_second':trained_tokens/elapsed,'baseline_validation':baseline_validation,'baseline_test':baseline_test,'final_validation':evaluate(model,validation,device),'test':evaluate(model,test,device),'peak_gpu_bytes':torch.cuda.max_memory_allocated() if device=='cuda' else 0,'dataset':{'train':training_stats,'validation':validation_stats,'test':test_stats},'hardware':hardware(),'history':history,'loss_scope':'Only final owner response plus EOS, context labels -100; token-weighted accumulation and evaluation.'}
    save_json(output/'metrics.json',result)
    return result
