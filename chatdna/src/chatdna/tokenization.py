"""Train a private BPE from the training split only; keep documents separate."""
from pathlib import Path
import json
import numpy as np
from tokenizers import Tokenizer,models,pre_tokenizers,decoders,trainers
from .runtime import save_json,records

def train_tokenizer(dataset,output,vocab_size=4096,block_size=128):
    dataset,output=Path(dataset),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    tokenizer=Tokenizer(models.BPE(unk_token='[UNK]'))
    tokenizer.pre_tokenizer=pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder=decoders.ByteLevel()
    trainer=trainers.BpeTrainer(vocab_size=vocab_size,min_frequency=2,special_tokens=['[PAD]','[BOS]','[EOS]','[UNK]'],initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),show_progress=False)
    tokenizer.train_from_iterator((r['text'] for r in records(dataset/'lm_train.jsonl')),trainer)
    tokenizer.save(str(output/'tokenizer.json'))
    report={'vocab_size':tokenizer.get_vocab_size(),'block_size':block_size,'trained_on':'lm_train only','splits':{}}
    for split in ('train','validation','test'):
        blocks=[]
        lengths=[]
        for record in records(dataset/f'lm_{split}.jsonl'):
            tokens=[1]+tokenizer.encode(record['text']).ids+[2]
            lengths.append(len(tokens)-2)
            for offset in range(0,len(tokens)-1,block_size):
                window=tokens[offset:offset+block_size+1]
                if len(window)>=2:
                    blocks.append(window+[0]*(block_size+1-len(window)))
        array=np.asarray(blocks,dtype=np.int32)
        if not len(array):
            raise ValueError('Empty tokenized split')
        np.save(output/f'{split}.npy',array)
        report['splits'][split]={'documents':len(lengths),'blocks':len(blocks),'body_tokens':sum(lengths),'predicted_tokens_including_eos':int((array[:,1:]!=0).sum()),'length_percentiles':{str(p):float(np.percentile(lengths,p)) for p in (50,90,95,99)},'mean_tokens':float(np.mean(lengths))}
    save_json(output/'report.json',report)
    return report
