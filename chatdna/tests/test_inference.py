from chatdna.inference import MemorizationGuard,text_hash
from chatdna.playground import origin_allowed
from chatdna.inference import LocalModels
from types import SimpleNamespace
import torch

def test_memorized_fragment_withheld():
    fragment='one two three four five six seven eight'
    guard=MemorizationGuard(ngrams=[text_hash(fragment)])
    assert guard.matches('prefix '+fragment+' suffix')
    assert not guard.matches('ordinary synthetic response')

def test_local_origin_only():
    assert origin_allowed('http://127.0.0.1:8765',8765)
    assert origin_allowed('http://localhost:8765',8765)
    assert not origin_allowed('https://example.org',8765)
    assert not origin_allowed('http://127.0.0.1:8766',8765)

def test_empty_generation_is_not_reported_as_memorization():
    models=LocalModels.__new__(LocalModels)
    models.device='cpu'
    models.registry={'models':{'synthetic':{'kind':'scratch'}}}
    models.guard=MemorizationGuard()
    models.load=lambda name:None
    models.tokenizer=SimpleNamespace(encode=lambda text:SimpleNamespace(ids=[9]),decode=lambda tokens,**kwargs:'')
    models.model=SimpleNamespace(config=SimpleNamespace(block_size=8),generate=lambda ids,*args,**kwargs:torch.cat([ids,torch.tensor([[2]])],dim=1))
    result=models.generate('synthetic','synthetic input',temperature=0,max_new_tokens=1)
    assert result['empty_output']
    assert not result['suppressed']
