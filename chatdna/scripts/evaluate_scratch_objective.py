"""Uniform validation subset, distinguishing body-token prediction from EOS."""
import argparse
from dataclasses import asdict
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from chatdna.scratch import GPT,GPTConfig
from chatdna.train_scratch import tensors
from chatdna.runtime import seed_all,save_json

@torch.no_grad()
def score(model,blocks,device):
    model.eval()
    counts={'all_tokens':0,'body_tokens':0,'eos_tokens':0,'predicted_eos_on_body':0,'correct_eos':0}
    all_loss=body_loss=0
    for offset in range(0,len(blocks),8):
        x,y=tensors(blocks,np.arange(offset,min(offset+8,len(blocks))),device)
        logits,_=model(x)
        losses=F.cross_entropy(logits.transpose(1,2),y,ignore_index=-100,reduction='none')
        valid=y!=-100; body=y>2; eos=y==2
        all_loss+=float(losses[valid].sum()); body_loss+=float(losses[body].sum())
        predicted=logits.argmax(-1)
        counts['all_tokens']+=int(valid.sum()); counts['body_tokens']+=int(body.sum()); counts['eos_tokens']+=int(eos.sum())
        counts['predicted_eos_on_body']+=int(((predicted==2)&body).sum()); counts['correct_eos']+=int(((predicted==2)&eos).sum())
    return {'all_token_nll':all_loss/counts['all_tokens'],'body_token_nll':body_loss/counts['body_tokens'],'eos_prediction_rate_on_body':counts['predicted_eos_on_body']/counts['body_tokens'],'eos_accuracy':counts['correct_eos']/counts['eos_tokens'],'counts':counts}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--private-root',type=Path,required=True); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    root=args.private_root; seed_all(42)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    full=np.load(root/'bpe-v1/validation.npy',mmap_mode='r')
    indices=np.linspace(0,len(full)-1,min(512,len(full)),dtype=int)
    blocks=np.asarray(full[indices])
    result={'protocol':'512 uniformly spaced validation blocks, token-weighted; same private BPE. EOS body diagnostic. No test metrics used for selection. Random baseline recreated with seed42 on this runtime.','models':{}}
    model=GPT(GPTConfig()).to(device)
    result['models']['random_seed42']=score(model,blocks,device)
    del model
    for name in ('b1','b1-longer'):
        checkpoint=torch.load(root/f'runs/{name}/checkpoint.pt',map_location='cpu',weights_only=True)
        model=GPT(GPTConfig(**checkpoint['config'])).to(device)
        model.load_state_dict(checkpoint['model'])
        result['models'][name]=score(model,blocks,device)
        del model
        if device=='cuda':torch.cuda.empty_cache()
    save_json(args.output,result)
    print('Native-objective validation diagnostics saved; private strings withheld.')

if __name__=='__main__':main()
