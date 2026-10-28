from chatdna.responses import encode_response
import os
import pytest

class SyntheticTokenizer:
    eos_token_id=2
    def encode(self,text,add_special_tokens=False):
        return [10+ord(c)%20 for c in text]
    def apply_chat_template(self,messages,**kwargs):
        return [1]+[4 for _ in messages]+[5]

def test_response_only_labels():
    tokenizer=SyntheticTokenizer()
    sample=encode_response(tokenizer,[{'role':'user','content':'synthetic question'},{'role':'assistant','content':'yes'}],32)
    assert sample['labels'][:3]==[-100]*3
    assert sample['labels'][3:]==tokenizer.encode('yes')+[2]
    assert sample['target_tokens']==4
    assert all(x==1 for x in sample['attention_mask'])

def test_long_target_not_silently_truncated():
    assert encode_response(SyntheticTokenizer(),[{'role':'user','content':'hi'},{'role':'assistant','content':'a'*50}],32) is None

def test_actual_qwen_template_target_boundaries():
    path=os.environ.get('CHATDNA_TOKENIZER_PATH')
    if not path:
        pytest.skip('Set CHATDNA_TOKENIZER_PATH for public local Qwen tokenizer validation')
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
    reply='belajar pytorch wkwk'
    sample=encode_response(tokenizer,[{'role':'user','content':'lagi apa?'},{'role':'assistant','content':reply}],128)
    active=[(i,label) for i,label in enumerate(sample['labels']) if label!=-100]
    first=active[0][0]
    assert all(label==-100 for label in sample['labels'][:first])
    assert sample['labels'][first:]==sample['input_ids'][first:]
    assert tokenizer.decode(sample['input_ids'][first:-1])==reply
    assert sample['labels'][-1]==tokenizer.eos_token_id
    assert sample['target_tokens']==len(active)
