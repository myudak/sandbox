"""Aggregate actual-tokenizer lengths and year counts without exporting strings."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import sqlite3
import numpy as np
from tokenizers import Tokenizer
from transformers import AutoTokenizer
from chatdna.runtime import private_runtime,records,save_json
from chatdna.data import digest,normalize
from chatdna.responses import encode_response

def summary(values):
    return {'count':len(values),'mean':float(np.mean(values)),'percentiles':{str(p):float(np.percentile(values,p)) for p in (50,90,95,99)}}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--private-root',type=Path,required=True); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    private_runtime()
    root=args.private_root
    tokenizer=Tokenizer.from_file(str(root/'bpe-v1/tokenizer.json'))
    source=sqlite3.connect((root/'dataset-v3/prepared.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    lengths=[]; repeated=Counter()
    for text, in source.execute('SELECT text FROM events WHERE me=1 AND text IS NOT NULL'):
        lengths.append(len(tokenizer.encode(text).ids))
        repeated[digest(normalize(text))]+=1
    source.close()
    report={'owner_clean_message_lengths_bpe_pre_burst':summary(lengths),'owner_repeated_text_concentration':{'messages':sum(repeated.values()),'unique_exact_normalized_texts':len(repeated),'top_10_share':sum(sorted(repeated.values(),reverse=True)[:10])/sum(repeated.values()),'note':'Only frequency concentration is published, not the repeated words.'},'lm_turns':{},'sft_sequences':{},'year_basis':'UTC document/response end timestamp; dataset units are different and must not be summed as unique content.','language_distribution':'Not measured: no validated language/code-switching classifier was used.'}
    qwen=AutoTokenizer.from_pretrained(root/'models/qwen3-0.6b',local_files_only=True,trust_remote_code=False)
    for split in ('train','validation','test'):
        years={}; turn_lengths=[]; reserved=0
        for record in records(root/f'dataset-v3/lm_{split}.jsonl'):
            ids=tokenizer.encode(record['text']).ids
            turn_lengths.append(len(ids))
            reserved+=int(any(i<4 for i in ids))
            year=str(datetime.fromtimestamp(record['end']/1000,timezone.utc).year)
            years.setdefault(year,Counter()).update(documents=1,body_tokens=len(ids))
        report['lm_turns'][split]={'lengths':summary(turn_lengths),'by_year':{k:dict(v) for k,v in years.items()},'reserved_body_token_collisions':reserved}
        years={}; sequence_lengths=[]; targets=[]; rejected=0
        for record in records(root/f'dataset-v3/sft_{split}.jsonl'):
            encoded=encode_response(qwen,record['messages'],128)
            if encoded is None:
                rejected+=1; continue
            year=str(datetime.fromtimestamp(record['end']/1000,timezone.utc).year)
            sequence_lengths.append(len(encoded['input_ids'])); targets.append(encoded['target_tokens'])
            years.setdefault(year,Counter()).update(examples=1,target_tokens=encoded['target_tokens'],context_tokens=len(encoded['input_ids'])-encoded['target_tokens'])
        report['sft_sequences'][split]={'sequence_lengths':summary(sequence_lengths),'target_lengths':summary(targets),'total_target_tokens':sum(targets),'length_rejections':rejected,'by_year':{k:dict(v) for k,v in years.items()}}
    save_json(args.output,report)
    print('Actual-tokenizer dataset summary saved; no text or identifiers emitted.')

if __name__=='__main__':
    main()
