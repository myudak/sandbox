"""One local model at a time, with best-effort output memorization suppression."""
import gc
import hashlib
import json
from pathlib import Path
import re
import time
import torch
from .runtime import private_runtime,save_json,records
from .data import clean_text,normalize

def words(text):
    return normalize(text).split()

def text_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()

class MemorizationGuard:
    def __init__(self,document_hashes=(),ngrams=()):
        self.document_hashes=set(document_hashes)
        self.ngrams=set(ngrams)
    @classmethod
    def build(cls,dataset,output):
        documents=set(); grams=set()
        for record in records(Path(dataset)/'lm_train.jsonl'):
            text=normalize(record['text'])
            if len(text)>=20:
                documents.add(text_hash(text))
            tokens=words(text)
            grams.update(text_hash(' '.join(tokens[i:i+8])) for i in range(len(tokens)-7))
        save_json(output,{'documents':sorted(documents),'ngrams':sorted(grams)})
        return cls(documents,grams)
    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(data['documents'],data['ngrams'])
    def matches(self,text):
        text=normalize(text)
        if len(text)>=20 and text_hash(text) in self.document_hashes:
            return True
        tokens=words(text)
        return any(text_hash(' '.join(tokens[i:i+8])) in self.ngrams for i in range(len(tokens)-7))

class LocalModels:
    def __init__(self,registry_path):
        private_runtime()
        self.registry=json.loads(Path(registry_path).read_text(encoding='utf-8'))
        self.guard=MemorizationGuard.load(self.registry['guard'])
        self.model=None; self.tokenizer=None; self.current=None
        self.device='cuda' if torch.cuda.is_available() else 'cpu'
    def listing(self):
        items=[]
        for name,spec in self.registry['models'].items():
            required=[spec['checkpoint'],spec['tokenizer']] if spec['kind']=='scratch' else [str(Path(spec['base'])/'model.safetensors'),str(Path(spec['base'])/'config.json'),str(Path(spec['base'])/'tokenizer.json')]
            if spec['kind']=='lora':
                required.extend([str(Path(spec['adapter'])/'adapter_model.safetensors'),str(Path(spec['adapter'])/'adapter_config.json')])
            available=all(Path(path).exists() for path in required)
            items.append({'id':name,'label':spec.get('label',name),'kind':spec['kind'],'available':available,'details':spec.get('details',''),'checkpoint':spec.get('checkpoint_label',Path(required[-1]).name),'reason':None if available else 'Required local checkpoint is unavailable'})
        return items
    def unload(self):
        self.model=None; self.tokenizer=None; self.current=None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    def load(self,name):
        if name==self.current:
            return
        if name not in self.registry['models']:
            raise ValueError('Unknown local model')
        if not next(x for x in self.listing() if x['id']==name)['available']:
            raise FileNotFoundError('Local checkpoint is unavailable')
        self.unload()
        spec=self.registry['models'][name]
        if spec['kind']=='scratch':
            from tokenizers import Tokenizer
            from .scratch import GPT,GPTConfig
            checkpoint=torch.load(spec['checkpoint'],map_location='cpu',weights_only=True)
            if checkpoint.get('origin')!='random_initialization':
                raise ValueError('Scratch checkpoint origin is not verified')
            self.model=GPT(GPTConfig(**checkpoint['config']))
            self.model.load_state_dict(checkpoint['model'])
            self.model.to(self.device).eval()
            self.tokenizer=Tokenizer.from_file(spec['tokenizer'])
        else:
            from transformers import AutoModelForCausalLM,AutoTokenizer
            dtype=torch.bfloat16 if self.device=='cuda' and torch.cuda.is_bf16_supported() else (torch.float16 if self.device=='cuda' else torch.float32)
            self.tokenizer=AutoTokenizer.from_pretrained(spec['base'],local_files_only=True,trust_remote_code=False)
            self.model=AutoModelForCausalLM.from_pretrained(spec['base'],local_files_only=True,trust_remote_code=False,dtype=dtype,attn_implementation='sdpa').to(self.device)
            if spec['kind']=='lora':
                from peft import PeftModel
                self.model=PeftModel.from_pretrained(self.model,spec['adapter'],local_files_only=True)
            self.model.eval()
        self.current=name
    @torch.inference_mode()
    def generate(self,name,prompt,temperature=.7,max_new_tokens=64):
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>4000:
            raise ValueError('Prompt must contain 1–4000 characters')
        max_new_tokens=max(1,min(int(max_new_tokens),128))
        temperature=max(0,min(float(temperature),1.5))
        self.load(name)
        spec=self.registry['models'][name]
        started=time.perf_counter()
        if self.device=='cuda':
            torch.cuda.synchronize()
        if spec['kind']=='scratch':
            encoded=[1]+self.tokenizer.encode(prompt).ids
            ids=torch.tensor([encoded[-self.model.config.block_size:]],device=self.device)
            result=self.model.generate(ids,max_new_tokens,temperature,top_k=40,eos_id=2)
            generated=result[0,ids.shape[1]:].tolist()
            text=self.tokenizer.decode(generated,skip_special_tokens=True)
        else:
            ids=self.tokenizer.apply_chat_template([{'role':'user','content':prompt}],tokenize=True,add_generation_prompt=True,enable_thinking=False,return_tensors='pt')
            if hasattr(ids,'keys'):
                ids=ids['input_ids']
            ids=ids[:,-256:].to(self.device)
            generation={'max_new_tokens':max_new_tokens,'do_sample':temperature>0,'pad_token_id':self.tokenizer.eos_token_id,'use_cache':True}
            if temperature>0:
                generation.update(temperature=temperature,top_k=20,top_p=.8)
            result=self.model.generate(ids,attention_mask=torch.ones_like(ids),**generation)
            generated=result[0,ids.shape[1]:].tolist()
            text=self.tokenizer.decode(generated,skip_special_tokens=True)
        if self.device=='cuda':
            torch.cuda.synchronize()
        elapsed=time.perf_counter()-started
        memorized=self.guard.matches(text)
        cleaned,flags=clean_text(text,max_chars=8000)
        empty=not text.strip()
        suppressed=memorized or (cleaned is None and not empty)
        reason='training_overlap' if memorized else 'filtered_sensitive_or_invalid_text' if suppressed else None
        displayed='Output withheld by the local privacy check.' if suppressed else ('Model ended without text.' if empty else cleaned)
        return {'text':displayed,'output_tokens':len(generated),'input_tokens':int(ids.shape[1]),'seconds':elapsed,'model':name,'kind':spec['kind'],'suppressed':suppressed,'suppression_reason':reason,'empty_output':empty,'redactions':sum(flags.get(k,0) for k in ('email','url','jid','phone','long_number')),'notice':'Generated model output, not the account owner. Privacy checks are incomplete.'}
