"""Private streaming preparation, session reconstruction and chronological splits."""
from collections import Counter, deque
from dataclasses import dataclass,asdict
from datetime import datetime, timezone,timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import unicodedata

from .runtime import save_json

RULES = [
    ('credential',re.compile(r'(?i)\b(?:password|passwd|api[_ -]?key|secret|otp|pin)\s*[:=]\s*\S+'), '[CREDENTIAL]'),
    ('credential',re.compile(r'\b(?:sk-proj-|hf_)[A-Za-z0-9_-]{16,}\b|\b[a-fA-F0-9]{40,}\b'), '[CREDENTIAL]'),
    ('email',re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), '[EMAIL]'),
    ('url',re.compile(r'(?i)https?://\S+|\bwww\.\S+'), '[URL]'),
    ('jid',re.compile(r'\b\d{5,}@(s\.whatsapp\.net|lid|g\.us)\b'), '[ID]'),
    ('phone',re.compile(r'(?<!\w)(?:\+\d[\d ().-]{7,}\d|0[\s.-]*8[\d ().-]{7,}\d)(?!\w)'), '[PHONE]'),
    ('long_number',re.compile(r'(?<!\w)\d{8,19}(?!\w)'), '[NUMBER]'),
]
PLACEHOLDER = re.compile(r'(?i)^(?:<media omitted>|this message was deleted|pesan ini dihapus|\[media\])$')
PERSON = re.compile(r'^([0-9]+)(?::[0-9]+)?@(s\.whatsapp\.net|lid)$')

@dataclass
class DataPolicy:
    max_message_chars:int=2000
    max_turn_messages:int=8
    session_gap_minutes:int=30
    repeat_burst_limit:int=6
    repeat_window_seconds:int=60
    train_fraction:float=.8
    validation_fraction:float=.1
    drop_forwarded:bool=True
    reference_date:str='2026-10-28'
    def __post_init__(self):
        if min(self.max_message_chars,self.max_turn_messages,self.session_gap_minutes,self.repeat_burst_limit,self.repeat_window_seconds)<=0:
            raise ValueError('Data limits must be positive')
        if not 0<self.train_fraction<1 or not 0<self.validation_fraction<1 or self.train_fraction+self.validation_fraction>=1:
            raise ValueError('Invalid chronological fractions')
        datetime.fromisoformat(self.reference_date)

def clean_text(text, max_chars=2000):
    counts=Counter()
    if not isinstance(text,str):
        return None, {'empty':1}
    text=unicodedata.normalize('NFC',text).replace('\r\n','\n').replace('\r','\n').strip()
    if not text:
        return None, {'empty':1}
    if len(text)>max_chars:
        return None, {'too_long':1}
    if PLACEHOLDER.fullmatch(text):
        return None, {'media_placeholder':1}
    for name,pattern,replacement in RULES:
        text,n=pattern.subn(replacement,text)
        counts[name]+=n
    if counts['credential']:
        return None, dict(counts|Counter(credential_message_dropped=1))
    return text, dict(counts)

def normalize(text):
    return ' '.join(unicodedata.normalize('NFC',text).casefold().split())

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def split_for(start,end,train_end,val_end):
    if end<=train_end:
        return 'train'
    if start>train_end and end<=val_end:
        return 'validation'
    if start>val_end:
        return 'test'
    return None

class LeakageGuard:
    """Keep training repetition; purge exact/near-duplicate held-out documents."""
    def __init__(self):
        self.exact={}
        self.buckets={}
    @staticmethod
    def simhash(text):
        words=normalize(text).split()
        if len(words)<12:
            return None
        scores=[0]*64
        for gram in set(' '.join(words[i:i+3]) for i in range(len(words)-2)):
            bits=int.from_bytes(hashlib.blake2b(gram.encode(),digest_size=8).digest(),'big')
            for j in range(64):
                scores[j]+=1 if bits>>j&1 else -1
        return sum(1<<j for j,n in enumerate(scores) if n>0)
    def accept(self,text,split):
        key=digest(normalize(text))
        old=self.exact.get(key)
        if old is not None and old!=split:
            return False,'exact_cross_split'
        value=self.simhash(text)
        if value is not None:
            for band in range(4):
                bucket=(band,(value>>(band*16))&65535)
                for previous,previous_split in self.buckets.get(bucket,[]):
                    if previous_split!=split and (value^previous).bit_count()<=3:
                        return False,'near_cross_split'
        self.exact.setdefault(key,split)
        if value is not None:
            for band in range(4):
                bucket=(band,(value>>(band*16))&65535)
                if (value,split) not in self.buckets.get(bucket,[]):
                    self.buckets.setdefault(bucket,[]).append((value,split))
        return True,None

def build(export,source_db,output,participant_context=False,include_group_quoted=False,policy=None):
    policy=DataPolicy(**(policy or {}))
    export,source_db,output=Path(export),Path(source_db),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    db_path=output/'prepared.sqlite'
    if db_path.exists():
        raise FileExistsError('Prepared dataset exists; use a fresh output directory.')
    salt_path=output.parent/'identity-salt.bin'
    if not salt_path.exists():
        salt_path.write_bytes(os.urandom(32))
    salt=salt_path.read_bytes()
    def pseudo(value):
        return hmac.digest(salt,str(value).encode(),'sha256').hex()[:32]
    def personal(value):
        match=PERSON.fullmatch(value or '')
        return match[1]+'@'+match[2] if match and int(match[1]) else None
    source=sqlite3.connect(source_db.resolve().as_uri()+'?mode=ro',uri=True)
    source.execute('PRAGMA cache_size=-16384')
    forwarded={r[0] for r in source.execute('SELECT message_row_id FROM message_forwarded')}
    system={r[0] for r in source.execute('SELECT message_row_id FROM message_system')}
    aliases={personal(a):personal(b) for a,b in source.execute('SELECT a.raw_string,b.raw_string FROM jid_map m JOIN jid a ON a._id=m.lid_row_id JOIN jid b ON b._id=m.jid_row_id') if personal(a) and personal(b)}
    quotes={r[0]:pseudo(r[1]) for r in source.execute('SELECT q.message_row_id,q.key_id FROM message_quoted q JOIN message m ON m._id=q.message_row_id WHERE m.from_me=1 AND m.message_type=0 AND q.key_id IS NOT NULL')}
    expected=source.execute('SELECT count(*) FROM message').fetchone()[0]
    db=sqlite3.connect(db_path)
    db.execute('PRAGMA journal_mode=OFF')
    db.execute('PRAGMA synchronous=OFF')
    db.execute('PRAGMA cache_size=-16384')
    db.execute('CREATE TABLE events(mid INTEGER PRIMARY KEY,chat TEXT,ts INTEGER,sender TEXT,me INTEGER,text TEXT,key TEXT,quote TEXT,kind TEXT)')
    counts=Counter()
    by_year={}
    message_lengths=Counter()
    source_hash=hashlib.sha256()
    rows=[]
    last_ts={}
    cutoff=int((datetime.fromisoformat(policy.reference_date).replace(tzinfo=timezone.utc)+timedelta(days=2)).timestamp()*1000)
    with (export/'messages.jsonl').open('rb') as stream:
        for line in stream:
            source_hash.update(line)
            record=json.loads(line)
            counts['input_rows']+=1
            mid,stamp=record['_id'],record.get('timestamp')
            chat=pseudo('chat:'+str(record['chat_row_id']))
            kind='group' if record.get('is_group') is True else ('direct' if personal(record.get('chat_jid')) else 'unknown')
            valid_ts=isinstance(stamp,int) and 1230768000000<=stamp<=cutoff
            if valid_ts:
                if stamp<last_ts.get(chat,stamp):
                    counts['timestamp_regressions']+=1
                last_ts[chat]=stamp
            else:
                counts['invalid_timestamp']+=1
                stamp=None
            is_text=record.get('message_type')==0 and mid not in system
            text=None
            if is_text:
                counts['plain_text_candidates']+=1
                if mid in forwarded and policy.drop_forwarded:
                    counts['forwarded_dropped']+=1
                elif participant_context or record['from_me']:
                    text,redactions=clean_text(record.get('text_data'),policy.max_message_chars)
                    counts.update(redactions)
                else:
                    counts['unauthorized_context_excluded']+=1
            else:
                category='system' if mid in system or record.get('message_type')==7 else ('revoked' if record.get('message_type') in {15,64} else 'nontext_or_unknown')
                counts['excluded_'+category]+=1
            raw_sender=personal(record.get('sender_jid')) if record.get('sender_jid_row_id') else None
            raw_sender=raw_sender or personal(record.get('chat_jid'))
            sender='self' if record['from_me'] else pseudo(aliases.get(raw_sender,raw_sender)) if raw_sender else None
            if not sender or stamp is None:
                text=None
                counts['unresolved_or_invalid_boundary']+=1
            if text:
                counts['clean_self_messages' if record['from_me'] else 'clean_other_messages']+=1
                year=datetime.fromtimestamp(stamp/1000,timezone.utc).year
                by_year.setdefault(str(year),Counter())['self' if record['from_me'] else 'others']+=1
                message_lengths[len(text)]+=1
            rows.append((mid,chat,stamp,sender,int(record['from_me']),text,pseudo(record.get('key_id')),quotes.get(mid),kind))
            if len(rows)>=10000:
                db.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)',rows)
                rows.clear()
            if counts['input_rows']%500000==0:
                db.commit()
                print('Prepared',counts['input_rows'],'source rows; content withheld.',flush=True)
    if rows:
        db.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)',rows)
    if counts['input_rows']!=expected:
        raise ValueError('Source/export counts differ.')
    db.execute('CREATE INDEX event_order ON events(chat,ts,mid)')
    db.execute('CREATE TABLE sessions(id INTEGER PRIMARY KEY,start INTEGER,end INTEGER)')
    db.execute('CREATE TABLE candidates(id INTEGER PRIMARY KEY,session INTEGER,kind TEXT,payload TEXT,first INTEGER,last INTEGER)')
    db.commit()
    source.close()
    return reconstruct(db,output,counts,by_year,source_hash.hexdigest(),participant_context,include_group_quoted,policy)

def rebuild_cached(stage,output):
    stage,output=Path(stage),Path(output)
    previous=json.loads((stage/'report.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True,exist_ok=True)
    if (output/'prepared.sqlite').exists():
        raise FileExistsError('Destination stage exists')
    original=sqlite3.connect((stage/'prepared.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    db=sqlite3.connect(output/'prepared.sqlite')
    original.backup(db)
    original.close()
    db.executescript('DROP TABLE sessions; DROP TABLE candidates; CREATE TABLE sessions(id INTEGER PRIMARY KEY,start INTEGER,end INTEGER); CREATE TABLE candidates(id INTEGER PRIMARY KEY,session INTEGER,kind TEXT,payload TEXT,first INTEGER,last INTEGER);')
    counts=Counter(previous['filters'])
    for name in ('pair_ambiguity_dropped','burst_repetition_dropped','sessions','boundary_sessions_purged'):
        counts.pop(name,None)
    return reconstruct(db,output,counts,previous['messages_by_year'],previous['input_sha256'],previous['permission']['participant_context_authorized'],False,DataPolicy(**previous.get('policy',{})))

def reconstruct(db,output,counts,by_year,input_sha256,participant_context,include_group_quoted,policy=None):
    policy=policy or DataPolicy()
    session=0
    session_start=session_end=None
    history=deque(maxlen=4)
    turn=None
    previous_chat=None
    previous_stamp=None
    repeat_text=None
    repeat_sender=None
    repeat_count=0
    def flush_turn():
        nonlocal turn
        if not turn:
            return
        body,merged_rules=clean_text('\n'.join(turn['texts']),policy.max_message_chars)
        counts.update({'merged_'+key:value for key,value in merged_rules.items() if value})
        if body is None:
            counts['merged_turn_dropped']+=1
            turn=None
            history.clear()
            return
        turn['texts']=[body]
        if turn['me']:
            lm={'text':body,'chat_id':turn['chat'],'session_id':session,'source_ids':turn['ids'],'start':turn['first'],'end':turn['last']}
            db.execute('INSERT INTO candidates(session,kind,payload,first,last) VALUES(?,?,?,?,?)',(session,'lm',json.dumps(lm,ensure_ascii=False),turn['first'],turn['last']))
            if participant_context and history and not history[-1]['me']:
                quote=turn['quote']
                quote_matches=bool(quote and quote in history[-1]['keys'])
                eligible=turn['kind']=='direct' and (not quote or quote_matches)
                eligible=eligible or (include_group_quoted and turn['kind']=='group' and quote_matches)
                if eligible:
                    messages=[{'role':'assistant' if h['me'] else 'user','content':'\n'.join(h['texts'])} for h in history]
                    while messages and messages[0]['role']!='user':
                        messages.pop(0)
                    sft={'messages':messages+[{'role':'assistant','content':body}], 'chat_id':turn['chat'],'session_id':session,'start':history[0]['first'],'end':turn['last'],'source_ids':[i for h in history for i in h['ids']]+turn['ids'],'evidence':'quoted' if quote_matches else 'direct_adjacency','chat_type':turn['kind']}
                    db.execute('INSERT INTO candidates(session,kind,payload,first,last) VALUES(?,?,?,?,?)',(session,'sft',json.dumps(sft,ensure_ascii=False),sft['start'],sft['end']))
                else:
                    counts['pair_ambiguity_dropped']+=1
        history.append(turn)
        turn=None
    def finish_session():
        if session_start is not None:
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(session,session_start,session_end))
    for mid,chat,stamp,sender,me,text,key,quote,kind in db.execute('SELECT * FROM events ORDER BY chat,ts,mid'):
        boundary=chat!=previous_chat or stamp is None or previous_stamp is None or stamp-previous_stamp>policy.session_gap_minutes*60000 or not text
        if boundary:
            flush_turn()
            finish_session()
            session+=1
            session_start=session_end=None
            history.clear()
            repeat_text=None
            repeat_sender=None
            repeat_count=0
        if text:
            if session_start is None:
                session_start=stamp
            session_end=stamp
            repeated=sender==repeat_sender and normalize(text)==repeat_text and stamp-previous_stamp<policy.repeat_window_seconds*1000 if previous_stamp is not None else False
            repeat_count=repeat_count+1 if repeated else 1
            repeat_text=normalize(text)
            repeat_sender=sender
            if repeat_count>policy.repeat_burst_limit:
                counts['burst_repetition_dropped']+=1
                flush_turn()
                history.clear()
            else:
                if turn and (turn['sender']!=sender or len(turn['texts'])>=policy.max_turn_messages or sum(map(len,turn['texts']))+len(turn['texts'])+len(text)>policy.max_message_chars):
                    flush_turn()
                if turn is None:
                    turn={'sender':sender,'me':bool(me),'texts':[],'keys':[],'ids':[],'first':stamp,'last':stamp,'quote':quote,'chat':chat,'kind':kind}
                turn['texts'].append(text)
                turn['keys'].append(key)
                turn['ids'].append(mid)
                turn['last']=stamp
        previous_chat,previous_stamp=chat,stamp
    flush_turn()
    finish_session()
    db.commit()
    sessions=list(db.execute('SELECT id,start,end FROM sessions ORDER BY end,id'))
    train_end=sessions[max(0,int(len(sessions)*policy.train_fraction)-1)][2]
    val_end=sessions[max(0,int(len(sessions)*(policy.train_fraction+policy.validation_fraction))-1)][2]
    split_map={sid:split_for(start,end,train_end,val_end) for sid,start,end in sessions}
    counts['sessions']=len(sessions)
    counts['boundary_sessions_purged']=sum(v is None for v in split_map.values())
    report={'source_rows':counts['input_rows'],'input_sha256':input_sha256,'permission':{'participant_context_authorized':participant_context,'owner_confirmation_date':'2026-10-28'},'filters':dict(counts),'messages_by_year':{k:dict(v) for k,v in by_year.items()},'split_cutoffs_utc_ms':{'train_end':train_end,'validation_end':val_end},'datasets':{},'split_rule':'Whole sessions ordered chronologically. Boundary-straddling sessions purged. Exact/SimHash-near duplicate held-out documents purged; repeated training phrases retained.','group_policy':'Quoted-only opt-in; excluded by default.','limitations':['Redaction is incomplete; names and sensitive facts may remain. All outputs remain private.','Language/code-switching proportions are not claimed without a validated language classifier.','Direct adjacency and quoted linkage are evidence, not proof of semantic relevance.']}
    report['policy']=asdict(policy)
    for dataset in ('lm','sft'):
        guard=LeakageGuard()
        report['datasets'][dataset]={}
        for split in ('train','validation','test'):
            count=chars=0
            sha=hashlib.sha256()
            rejected=Counter()
            with (output/f'{dataset}_{split}.jsonl').open('w',encoding='utf-8',newline='\n') as stream:
                for sid,payload in db.execute('SELECT session,payload FROM candidates WHERE kind=? ORDER BY last,id',(dataset,)):
                    if split_map[sid]!=split:
                        continue
                    record=json.loads(payload)
                    comparison=record['text'] if dataset=='lm' else '\n'.join(m['role']+':'+m['content'] for m in record['messages'])
                    accepted,reason=guard.accept(comparison,split)
                    if not accepted:
                        rejected[reason]+=1
                        continue
                    record['split']=split
                    line=json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n'
                    stream.write(line)
                    sha.update(line.encode())
                    count+=1
                    chars+=len(record['text'] if dataset=='lm' else record['messages'][-1]['content'])
            report['datasets'][dataset][split]={'examples':count,'target_characters':chars,'sha256':sha.hexdigest(),'leakage_rejections':dict(rejected)}
    db.commit()
    db.close()
    save_json(output/'report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report
