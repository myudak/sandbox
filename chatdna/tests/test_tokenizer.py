import json
from pathlib import Path
from tokenizers import Tokenizer
from chatdna.tokenization import train_tokenizer

def test_training_tokenizer_never_fits_heldout_text(tmp_path):
    source=tmp_path/'source'; source.mkdir()
    for split,text in [('train','synthetic belajar python wkwk 😃'),('validation','heldout alpha'),('test','heldout beta')]:
        (source/f'lm_{split}.jsonl').write_text(json.dumps({'text':text})+'\n',encoding='utf-8')
    first=tmp_path/'first'; second=tmp_path/'second'
    report=train_tokenizer(source,first,vocab_size=300,block_size=8)
    (source/'lm_validation.jsonl').write_text(json.dumps({'text':'completely changed heldout language'})+'\n')
    train_tokenizer(source,second,vocab_size=300,block_size=8)
    assert (first/'tokenizer.json').read_bytes()==(second/'tokenizer.json').read_bytes()
    tokenizer=Tokenizer.from_file(str(first/'tokenizer.json'))
    phrase='synthetic belajar python wkwk 😃'
    assert tokenizer.decode(tokenizer.encode(phrase).ids)==phrase
    assert report['splits']['train']['predicted_tokens_including_eos']>0
