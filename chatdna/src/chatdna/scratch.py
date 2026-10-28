"""Decoder-only Transformer implemented directly in PyTorch; no pretrained weights."""
from dataclasses import dataclass
import math
import torch
from torch import nn
from torch.nn import functional as F

@dataclass
class GPTConfig:
    vocab_size:int=4096
    block_size:int=128
    n_layers:int=4
    n_heads:int=6
    d_model:int=192
    dropout:float=0.1

class CausalAttention(nn.Module):
    def __init__(self,config):
        super().__init__()
        if config.d_model%config.n_heads:
            raise ValueError('d_model must divide evenly into heads')
        self.heads=config.n_heads
        self.qkv=nn.Linear(config.d_model,3*config.d_model,bias=False)
        self.output=nn.Linear(config.d_model,config.d_model,bias=False)
        self.dropout=nn.Dropout(config.dropout)
        self.register_buffer('causal',torch.tril(torch.ones(config.block_size,config.block_size,dtype=torch.bool)),persistent=False)
    def forward(self,x):
        batch,length,width=x.shape
        q,k,v=self.qkv(x).chunk(3,dim=-1)
        q,k,v=(a.view(batch,length,self.heads,width//self.heads).transpose(1,2) for a in (q,k,v))
        scores=(q@k.transpose(-2,-1))/math.sqrt(width//self.heads)
        scores=scores.masked_fill(~self.causal[:length,:length],float('-inf'))
        probabilities=self.dropout(F.softmax(scores,dim=-1))
        attended=(probabilities@v).transpose(1,2).contiguous().view(batch,length,width)
        return self.dropout(self.output(attended))

class Block(nn.Module):
    def __init__(self,config):
        super().__init__()
        self.norm1=nn.LayerNorm(config.d_model)
        self.attention=CausalAttention(config)
        self.norm2=nn.LayerNorm(config.d_model)
        self.mlp=nn.Sequential(nn.Linear(config.d_model,4*config.d_model),nn.GELU(),nn.Linear(4*config.d_model,config.d_model),nn.Dropout(config.dropout))
    def forward(self,x):
        x=x+self.attention(self.norm1(x))
        return x+self.mlp(self.norm2(x))

class GPT(nn.Module):
    def __init__(self,config):
        super().__init__()
        self.config=config
        self.token_embedding=nn.Embedding(config.vocab_size,config.d_model)
        self.position_embedding=nn.Embedding(config.block_size,config.d_model)
        self.dropout=nn.Dropout(config.dropout)
        self.blocks=nn.ModuleList([Block(config) for _ in range(config.n_layers)])
        self.final_norm=nn.LayerNorm(config.d_model)
        self.lm_head=nn.Linear(config.d_model,config.vocab_size,bias=False)
        self.lm_head.weight=self.token_embedding.weight
        self.apply(self._initialize)
    @staticmethod
    def _initialize(module):
        if isinstance(module,(nn.Linear,nn.Embedding)):
            nn.init.normal_(module.weight,mean=0,std=.02)
            if isinstance(module,nn.Linear) and module.bias is not None:
                nn.init.zeros_(module.bias)
    def forward(self,ids,targets=None):
        if ids.ndim!=2 or ids.shape[1]>self.config.block_size:
            raise ValueError('Expected [batch,time] inside block_size')
        positions=torch.arange(ids.shape[1],device=ids.device)
        x=self.dropout(self.token_embedding(ids)+self.position_embedding(positions))
        for block in self.blocks:
            x=block(x)
        logits=self.lm_head(self.final_norm(x))
        loss=None if targets is None else F.cross_entropy(logits.reshape(-1,logits.size(-1)),targets.reshape(-1),ignore_index=-100)
        return logits,loss
    @torch.no_grad()
    def generate(self,ids,max_new_tokens=64,temperature=.8,top_k=40,eos_id=None):
        self.eval()
        for _ in range(max_new_tokens):
            logits,_=self(ids[:,-self.config.block_size:])
            logits=logits[:,-1,:]
            if temperature<=0:
                following=logits.argmax(-1,keepdim=True)
            else:
                logits=logits/temperature
                if top_k:
                    boundary=logits.topk(min(top_k,logits.size(-1))).values[:,-1:]
                    logits=logits.masked_fill(logits<boundary,float('-inf'))
                following=torch.multinomial(F.softmax(logits,-1),1)
            ids=torch.cat([ids,following],dim=1)
            if eos_id is not None and bool((following==eos_id).all()):
                break
        return ids
