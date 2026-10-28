import json
import sqlite3
from chatdna.data import build
from chatdna.validation import validate_dataset

def test_full_builder_preserves_split_boundaries_and_owner_targets(tmp_path):
    export=tmp_path/'export'; export.mkdir()
    source=tmp_path/'source.sqlite'
    db=sqlite3.connect(source)
    db.executescript('CREATE TABLE message(_id INTEGER,from_me INTEGER,message_type INTEGER); CREATE TABLE message_forwarded(message_row_id INTEGER); CREATE TABLE message_system(message_row_id INTEGER); CREATE TABLE jid(_id INTEGER,raw_string TEXT); CREATE TABLE jid_map(lid_row_id INTEGER,jid_row_id INTEGER); CREATE TABLE message_quoted(message_row_id INTEGER,key_id TEXT);')
    rows=[]
    for session in range(30):
        for own in (False,True):
            mid=len(rows)+1
            rows.append({'_id':mid,'chat_row_id':1,'timestamp':1600000000000+session*1900000+int(own)*1000,'message_type':0,'from_me':own,'sender_jid_row_id':0,'sender_jid':None,'chat_jid':'1'+'@s.whatsapp.net','is_group':False,'key_id':f'synthetic-{mid}','text_data':f'synthetic {"reply" if own else "question"} {session} wkwk'})
            db.execute('INSERT INTO message VALUES(?,?,0)',(mid,int(own)))
    db.commit(); db.close()
    (export/'messages.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    output=tmp_path/'private'
    result=build(export,source,output,participant_context=True,policy={'max_message_chars':500,'max_turn_messages':4})
    assert result['policy']['max_message_chars']==500
    previous_ids=set()
    previous_max=None
    for split in ('train','validation','test'):
        samples=[json.loads(line) for line in (output/f'sft_{split}.jsonl').read_text().splitlines()]
        assert samples
        ids={i for sample in samples for i in sample['source_ids']}
        assert not previous_ids.intersection(ids)
        previous_ids.update(ids)
        if previous_max is not None:
            assert min(s['start'] for s in samples)>previous_max
        previous_max=max(s['end'] for s in samples)
        for sample in samples:
            assert sample['messages'][-1]['role']=='assistant'
            assert sample['messages'][-1]['content'].startswith('synthetic reply')
    assert result['datasets']['lm']['train']['examples']>0
    assert validate_dataset(output)['validation']['source_ids_disjoint_across_splits']
