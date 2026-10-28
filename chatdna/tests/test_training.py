from types import SimpleNamespace
import torch
from chatdna.finetune import tensor_batch,evaluate

def test_padding_masks_padding_but_keeps_real_eos_target():
    a={'input_ids':[1,8,2],'attention_mask':[1,1,1],'labels':[-100,8,2],'target_tokens':2}
    b={'input_ids':[1,9],'attention_mask':[1,1],'labels':[-100,9],'target_tokens':1}
    batch=tensor_batch([a,b],'cpu',pad_id=2)
    assert batch['input_ids'].tolist()==[[1,8,2],[1,9,2]]
    assert batch['labels'].tolist()==[[-100,8,2],[-100,9,-100]]
    assert batch['attention_mask'].tolist()==[[1,1,1],[1,1,0]]

def test_validation_weights_tokens_instead_of_examples():
    class Dummy:
        def eval(self): return self
        def __call__(self,**kwargs):
            n=(kwargs['labels'][:,1:]!=-100).sum().float()
            return SimpleNamespace(loss=n)
    samples=[{'input_ids':[1,2],'labels':[-100,2],'attention_mask':[1,1]}, {'input_ids':[1,3,4,2],'labels':[-100,3,4,2],'attention_mask':[1,1,1,1]}]
    result=evaluate(Dummy(),samples,'cpu')
    assert result['evaluated_target_tokens']==4
    assert result['loss']==2.5
