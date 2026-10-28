from dataclasses import asdict
import json
import math
from pathlib import Path
import time
import numpy as np
import torch
from torch.nn import functional as F
from .runtime import seed_all,save_json,hardware
from .scratch import GPT,GPTConfig

def tensors(blocks,indices,device):
    data=torch.tensor(np.asarray(blocks[indices]),dtype=torch.long,device=device)
    x,y=data[:,:-1],data[:,1:].clone()
    y[y==0]=-100
    return x,y

@torch.no_grad()
def evaluate(model,blocks,device,batch_size=8,max_batches=32):
    model.eval()
    total=tokens=0
    for offset in range(0,min(len(blocks),batch_size*max_batches),batch_size):
        x,y=tensors(blocks,np.arange(offset,min(offset+batch_size,len(blocks))),device)
        logits,_=model(x)
        total+=F.cross_entropy(logits.reshape(-1,logits.size(-1)),y.reshape(-1),ignore_index=-100,reduction='sum').item()
        tokens+=int((y!=-100).sum())
    return {'loss':total/tokens,'perplexity':math.exp(min(total/tokens,50)),'evaluated_tokens':tokens}

def train(tokenized,output,steps=200,batch_size=4,accumulation=2,lr=3e-4,seed=42,resume=None,config=None,log_every=25):
    seed_all(seed)
    tokenized,output=Path(tokenized),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    tokenizer_report=json.loads((tokenized/'report.json').read_text(encoding='utf-8'))
    config=config or GPTConfig(vocab_size=tokenizer_report['vocab_size'],block_size=tokenizer_report['block_size'])
    model=GPT(config).to(device)
    optimizer=torch.optim.AdamW([{'params':[p for p in model.parameters() if p.ndim>=2],'weight_decay':.1},{'params':[p for p in model.parameters() if p.ndim<2],'weight_decay':0}],lr=lr)
    rng=torch.Generator().manual_seed(seed)
    start_step=0
    train_blocks=np.load(tokenized/'train.npy',mmap_mode='r')
    valid_blocks=np.load(tokenized/'validation.npy',mmap_mode='r')
    if resume:
        checkpoint=torch.load(resume,map_location=device,weights_only=True)
        model.load_state_dict(checkpoint['model'])
        optimizer.load_state_dict(checkpoint['optimizer'])
        rng.set_state(checkpoint['sampler_rng'].cpu())
        torch.set_rng_state(checkpoint['torch_rng'].cpu())
        if device=='cuda' and checkpoint.get('cuda_rng'):
            torch.cuda.set_rng_state_all([r.cpu() for r in checkpoint['cuda_rng']])
        start_step=checkpoint['step']
    baseline=evaluate(model,valid_blocks,device,batch_size)
    history=[]
    trained_tokens=0
    started=time.perf_counter()
    if device=='cuda':
        torch.cuda.reset_peak_memory_stats()
    for step in range(start_step,steps):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        warmup=max(1,min(20,steps//10))
        rate=lr*min(1,(step+1)/warmup)*(.1+.9*.5*(1+math.cos(math.pi*max(0,step-warmup)/max(1,steps-warmup))))
        for group in optimizer.param_groups:
            group['lr']=rate
        batches=[tensors(train_blocks,torch.randint(len(train_blocks),(batch_size,),generator=rng).numpy(),device) for _ in range(accumulation)]
        count=sum(int((y!=-100).sum()) for _,y in batches)
        total_loss=0
        for x,y in batches:
            logits,_=model(x)
            loss=F.cross_entropy(logits.reshape(-1,logits.size(-1)),y.reshape(-1),ignore_index=-100,reduction='sum')/count
            loss.backward()
            total_loss+=loss.item()
        gradient_norm=float(torch.nn.utils.clip_grad_norm_(model.parameters(),1.0))
        optimizer.step()
        trained_tokens+=count
        if (step+1)%log_every==0 or step+1==steps:
            validation=evaluate(model,valid_blocks,device,batch_size)
            point={'step':step+1,'train_loss':total_loss,'validation_loss':validation['loss'],'trained_tokens':trained_tokens,'learning_rate':rate,'gradient_norm':gradient_norm,'elapsed_seconds':time.perf_counter()-started}
            history.append(point)
            print(json.dumps(point),flush=True)
            torch.save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),'config':asdict(config),'step':step+1,'sampler_rng':rng.get_state(),'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all() if device=='cuda' else [],'origin':'random_initialization'},output/'checkpoint.pt')
    elapsed=time.perf_counter()-started
    final=evaluate(model,valid_blocks,device,batch_size)
    test=evaluate(model,np.load(tokenized/'test.npy',mmap_mode='r'),device,batch_size)
    result={'track':'scratch','initialization':'random; no pretrained weights','parameters':sum(p.numel() for p in model.parameters()),'config':asdict(config),'seed':seed,'steps':steps,'start_step':start_step,'trained_tokens_this_run':trained_tokens,'seconds':elapsed,'tokens_per_second':trained_tokens/elapsed,'baseline_validation':baseline,'final_validation':final,'test':test,'peak_gpu_bytes':torch.cuda.max_memory_allocated() if device=='cuda' else 0,'hardware':hardware(),'history':history}
    save_json(output/'metrics.json',result)
    return result
