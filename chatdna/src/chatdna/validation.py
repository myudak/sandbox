from collections import Counter
from pathlib import Path
import json
from .data import clean_text,digest,normalize
from .runtime import save_json,records

def validate_dataset(dataset):
    dataset=Path(dataset)
    metadata=json.loads((dataset/'report.json').read_text(encoding='utf-8'))
    max_chars=metadata.get('policy',{}).get('max_message_chars',2000)
    global_ids={split:set() for split in ('train','validation','test')}
    report={}
    for kind in ('lm','sft'):
        hashes={}
        previous_end=None
        report[kind]={}
        for split in global_ids:
            count=0
            earliest=latest=None
            for record in records(dataset/f'{kind}_{split}.jsonl'):
                assert record['split']==split
                assert record['start']<=record['end']
                if kind=='sft':
                    assert record['messages'][0]['role']=='user'
                    assert record['messages'][-1]['role']=='assistant'
                    assert record['chat_type']=='direct' or record['evidence']=='quoted'
                    texts=[m['content'] for m in record['messages']]
                    combined='\n'.join(m['role']+':'+m['content'] for m in record['messages'])
                else:
                    texts=[record['text']]
                    combined=record['text']
                for text in texts:
                    cleaned,rules=clean_text(text,max_chars=max_chars)
                    assert cleaned==text and not any(rules.values()),'Unresolved privacy/cleaning pattern; content withheld'
                key=digest(normalize(combined))
                assert key not in hashes or hashes[key]==split,'Exact example leakage'
                hashes[key]=split
                global_ids[split].update(record['source_ids'])
                earliest=record['start'] if earliest is None else min(earliest,record['start'])
                latest=record['end'] if latest is None else max(latest,record['end'])
                count+=1
            assert count>0 or (kind=='sft' and not metadata['permission']['participant_context_authorized'])
            if previous_end is not None and earliest is not None:
                assert earliest>previous_end,'Chronological split overlap'
            previous_end=latest
            report[kind][split]={'examples':count,'earliest_utc_ms':earliest,'latest_utc_ms':latest}
    for a,b in (('train','validation'),('train','test'),('validation','test')):
        assert not global_ids[a].intersection(global_ids[b]),'Source-message leakage across datasets/splits'
    report['validation']={'source_ids_disjoint_across_splits':True,'chronology_disjoint':True,'exact_examples_disjoint':True,'residual_known_redaction_patterns':0,'owner_target_role':True,'note':'Pattern scanning is not proof of anonymity; semantic PII and paraphrase leakage remain possible.'}
    save_json(dataset/'validation.json',report)
    return report
