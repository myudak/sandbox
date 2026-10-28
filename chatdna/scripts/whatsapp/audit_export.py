"""Local aggregate-only audit. Never prints or writes message text to audit outputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import importlib.metadata
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import time

MEDIA_TYPES = {1, 2, 3, 9, 13, 20, 42, 43, 81, 82}
PERSON_JID = re.compile(r'^([0-9]+)(?::[0-9]+)?@(s\.whatsapp\.net|lid)$')
SELF = b'SELF'
TEXT, MEDIA_ONLY, SYSTEM, OTHER, CAPTIONED_MEDIA = range(5)


def person_jid(value):
    match = PERSON_JID.fullmatch(value or '')
    if not match or int(match[1]) == 0:
        return None
    return match[1] + '@' + match[2]


def classification(kind, has_text, has_media, has_caption, is_system):
    if is_system or kind == 7:
        return SYSTEM
    if kind == 0 and has_text:
        return TEXT
    if has_media or kind in MEDIA_TYPES:
        return CAPTIONED_MEDIA if has_text or has_caption else MEDIA_ONLY
    return OTHER


def count_turns(rows, gap_ms=1800000):
    previous = None
    counts = Counter()
    for chat, stamp, mid, seq, sender, me, category, tokens, group_kind in rows:
        if category != TEXT or sender is None or stamp is None or group_kind == 2:
            previous = None
            continue
        if previous is not None:
            pchat, ptime, psender, pme = previous
            if chat == pchat and stamp >= ptime and stamp - ptime <= gap_ms:
                if sender != psender:
                    counts['all_speaker_change_pairs'] += 1
                    if not pme and me:
                        counts['incoming_to_me_turn_pairs'] += 1
                        counts['incoming_to_me_' + {0:'direct',1:'group',2:'unknown_chat_type'}[group_kind]] += 1
        previous = (chat, stamp, sender, bool(me))
    return counts


def median_from_histogram(histogram):
    size = sum(histogram.values())
    if not size:
        return None
    positions = {(size - 1) // 2, size // 2}
    values = []
    seen = 0
    for tokens, count in sorted(histogram.items()):
        for position in sorted(positions):
            if seen <= position < seen + count:
                values.append(tokens)
        seen += count
    return sum(values) / len(values)


def self_test():
    assert person_jid('0@s.whatsapp.net') is None
    assert person_jid('123:4@s.whatsapp.net') == '123@s.whatsapp.net'
    assert person_jid('123@g.us') is None
    assert classification(7, True, False, False, True) == SYSTEM
    assert classification(0, True, False, False, False) == TEXT
    assert classification(1, False, True, True, False) == CAPTIONED_MEDIA
    assert classification(20, False, False, False, False) == MEDIA_ONLY
    assert median_from_histogram(Counter({2:2, 5:2})) == 3.5
    assert median_from_histogram(Counter({2:3, 5:2})) == 2
    rows = [(1, 1000, 1, 1, b'A', 0, TEXT, 1, 0),
            (1, 2000, 2, 2, b'A', 0, TEXT, 1, 0),
            (1, 3000, 3, 3, SELF, 1, TEXT, 1, 0),
            (1, 4000, 4, 4, None, 0, MEDIA_ONLY, 0, 0),
            (1, 5000, 5, 5, b'A', 0, TEXT, 1, 0),
            (1, 1900000, 6, 6, SELF, 1, TEXT, 1, 0),
            (2, 1900001, 7, 7, b'A', 0, TEXT, 1, 0),
            (2, 1900002, 8, 8, SELF, 1, TEXT, 1, 0)]
    result = count_turns(rows)
    assert result['incoming_to_me_turn_pairs'] == 2
    assert result['all_speaker_change_pairs'] == 2
    assert count_turns([(1, 1, 1, 1, b'A', 0, TEXT, 1, 1), (1, 2, 2, 2, SELF, 1, TEXT, 1, 1)])['incoming_to_me_group'] == 1
    assert count_turns([(1, 1, 1, 1, b'A', 0, TEXT, 1, 2), (1, 2, 2, 2, SELF, 1, TEXT, 1, 2)])['incoming_to_me_turn_pairs'] == 0
    print('Synthetic classification, identity, median, and chronology tests passed.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', type=Path)
    parser.add_argument('--source-db', type=Path)
    parser.add_argument('--scratch', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    import tiktoken
    encoding = tiktoken.get_encoding('o200k_base')
    # Vocabulary may be loaded from its public cache before this point. All data
    # processing below is explicitly prevented from opening network connections.
    def deny_network(*unused, **kwargs):
        raise RuntimeError('Network access is disabled during the audit.')
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    args.scratch.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    scratch_db = args.scratch / 'audit-index.sqlite'
    if scratch_db.exists() or (args.output / 'audit.json').exists():
        raise FileExistsError('Audit destination exists; preserving it.')
    source = sqlite3.connect(args.source_db.resolve().as_uri() + '?mode=ro', uri=True)
    source.execute('PRAGMA cache_size=-16384')
    system_ids = {row[0] for row in source.execute('SELECT message_row_id FROM message_system')}
    alias_map = {}
    ambiguous_aliases = set()
    for alias, target in source.execute('SELECT a.raw_string,b.raw_string FROM jid_map m JOIN jid a ON a._id=m.lid_row_id JOIN jid b ON b._id=m.jid_row_id'):
        alias, target = person_jid(alias), person_jid(target)
        if alias and target and alias != target:
            if alias in alias_map and alias_map[alias] != target:
                ambiguous_aliases.add(alias)
            alias_map[alias] = target
    expected_count = source.execute('SELECT count(*) FROM message').fetchone()[0]
    source_plain_text_count = source.execute("SELECT count(*) FROM message WHERE message_type=0 AND text_data IS NOT NULL AND length(trim(text_data))>0").fetchone()[0]
    own_text_sender_rows = source.execute('SELECT count(DISTINCT sender_jid_row_id), min(sender_jid_row_id), max(sender_jid_row_id) FROM message WHERE from_me=1 AND message_type=0').fetchone()
    raw_direction_counts = dict(source.execute('SELECT from_me,count(*) FROM message GROUP BY from_me'))
    salt = os.urandom(32)
    (args.scratch / 'audit-hmac-salt.bin').write_bytes(salt)
    def fingerprint(value):
        return hmac.digest(salt, value.encode('utf-8', errors='surrogatepass'), 'sha256')
    sender_cache = {}
    def resolved_sender(record):
        if record['from_me']:
            return SELF
        jid = person_jid(record.get('sender_jid')) if record.get('sender_jid_row_id', 0) else None
        if jid is None:
            jid = person_jid(record.get('chat_jid'))
        if jid is None or jid in ambiguous_aliases:
            return None
        seen = set()
        while jid in alias_map:
            if jid in seen or jid in ambiguous_aliases:
                return None
            seen.add(jid)
            jid = alias_map[jid]
        if jid not in sender_cache:
            sender_cache[jid] = fingerprint(jid)
        return sender_cache[jid]
    media_info = {}
    for line in (args.export / 'media_references.jsonl').open('rb'):
        record = json.loads(line)
        media_info[record['message_row_id']] = bool(isinstance(record.get('media_caption'), str) and record['media_caption'].strip())
    index = sqlite3.connect(scratch_db)
    index.execute('PRAGMA journal_mode=OFF')
    index.execute('PRAGMA synchronous=OFF')
    index.execute('PRAGMA temp_store=FILE')
    index.execute('PRAGMA cache_size=-32768')
    index.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,mid INTEGER,chat INTEGER,ts INTEGER,sender BLOB,me INTEGER,category INTEGER,tokens INTEGER,group_kind INTEGER,logical_key BLOB,record_hash BLOB,text_hash BLOB)')
    counters = Counter()
    token_histogram = Counter()
    kind_counts = Counter()
    type_categories = Counter()
    unique_senders = set()
    unique_text_senders = set()
    last_chat_timestamp = {}
    min_timestamp, max_timestamp = None, None
    input_hash = hashlib.sha256()
    batch = []
    source_projection_hash = hashlib.sha256()
    export_projection_hash = hashlib.sha256()
    oldest_valid = int(datetime(2009,1,1,tzinfo=timezone.utc).timestamp()*1000)
    newest_valid = int((datetime(2026,10,28,23,59,59,tzinfo=timezone(timedelta(hours=7)))+timedelta(days=1)).timestamp()*1000)
    started = time.monotonic()
    with (args.export / 'messages.jsonl').open('rb') as stream:
        for seq, line in enumerate(stream, 1):
            input_hash.update(line)
            record = json.loads(line)
            if not isinstance(record.get('from_me'), bool):
                raise ValueError('Non-boolean direction field.')
            mid, chat, stamp = record['_id'], record['chat_row_id'], record.get('timestamp')
            kind = record.get('message_type')
            kind_counts[str(kind)] += 1
            text = record.get('text_data')
            has_text = isinstance(text, str) and bool(text.strip())
            category = classification(kind, has_text, mid in media_info, media_info.get(mid, False), mid in system_ids)
            counters[{TEXT:'text_messages',MEDIA_ONLY:'media_only_messages',SYSTEM:'system_messages',OTHER:'other_messages',CAPTIONED_MEDIA:'captioned_media_messages'}[category]] += 1
            type_categories[(str(kind),category)] += 1
            sender = resolved_sender(record)
            if category != SYSTEM:
                if sender is not None:
                    unique_senders.add(sender)
                else:
                    counters['unresolved_sender_non_system_rows'] += 1
            tokens, text_hash = 0, None
            if category == TEXT:
                tokens = len(encoding.encode_ordinary(text))
                counters['total_text_tokens'] += tokens
                counters['my_text_messages' if record['from_me'] else 'others_text_messages'] += 1
                if record['from_me']:
                    counters['my_text_tokens'] += tokens
                token_histogram[tokens] += 1
                if sender is not None:
                    unique_text_senders.add(sender)
                else:
                    counters['unresolved_sender_text_rows'] += 1
                text_hash = fingerprint(json.dumps([chat,sender.hex() if sender else ['unknown',record.get('sender_jid_row_id')],text],ensure_ascii=False,separators=(',',':')))
            if category not in (TEXT,SYSTEM) and has_text:
                counters['non_plain_text_rows_with_text_data'] += 1
            if record['from_me']:
                counters['all_outgoing_rows'] += 1
            if not isinstance(stamp,int) or isinstance(stamp,bool) or stamp < oldest_valid or stamp > newest_valid:
                counters['invalid_or_out_of_range_timestamps'] += 1
                valid_stamp = None
            else:
                valid_stamp = stamp
                if chat in last_chat_timestamp and stamp < last_chat_timestamp[chat]:
                    counters['timestamp_regressions_in_export_order'] += 1
                last_chat_timestamp[chat] = stamp
                min_timestamp = stamp if min_timestamp is None else min(min_timestamp,stamp)
                max_timestamp = stamp if max_timestamp is None else max(max_timestamp,stamp)
            if record.get('chat_jid') is None:
                counters['rows_missing_chat_jid'] += 1
            raw_key = record.get('key_id')
            logical_key = None
            if isinstance(raw_key,str) and raw_key:
                counters['logical_duplicate_eligible_rows'] += 1
                logical_key = fingerprint(json.dumps([chat,record['from_me'],raw_key,record.get('sender_jid_row_id')],separators=(',',':')))
            group_kind = 1 if record.get('is_group') is True else (0 if person_jid(record.get('chat_jid')) else 2)
            batch.append((seq,mid,chat,valid_stamp,sender,int(record['from_me']),category,tokens,group_kind,logical_key,hashlib.sha256(line).digest(),text_hash))
            # Validate a content-bearing projection against SQLite without storing
            # any plaintext or displaying differences.
            export_projection_hash.update(json.dumps([mid,chat,int(record['from_me']),record.get('sender_jid_row_id'),kind,stamp,raw_key,text],ensure_ascii=True,separators=(',',':')).encode('ascii'))
            if len(batch) >= 10000:
                index.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',batch)
                batch.clear()
            if seq % 250000 == 0:
                index.commit()
                print(f'Audited {seq:,} rows; aggregate processing only.',flush=True)
    if batch:
        index.executemany('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',batch)
    index.commit()
    counters['total_messages'] = seq
    if seq != expected_count:
        raise ValueError('JSONL/source row count mismatch.')
    print('Validating JSONL projection against source database.',flush=True)
    for row in source.execute('SELECT _id,chat_row_id,from_me,sender_jid_row_id,message_type,timestamp,key_id,text_data FROM message ORDER BY _id'):
        values = list(row)
        values[2] = int(bool(values[2]))
        source_projection_hash.update(json.dumps(values,ensure_ascii=True,separators=(',',':')).encode('ascii'))
    projection_matches = source_projection_hash.digest() == export_projection_hash.digest()
    if not projection_matches:
        raise ValueError('JSONL/source projection mismatch.')
    print('Checking duplicates and reconstructing per-chat chronology.',flush=True)
    duplicate_counts = {}
    for label,column in (('logical','logical_key'),('exact_record','record_hash'),('repeated_text','text_hash'),('row_id','mid')):
        duplicate_counts[label] = index.execute('SELECT coalesce(sum(n-1),0) FROM (SELECT count(*) n FROM events WHERE '+column+' IS NOT NULL GROUP BY '+column+' HAVING count(*)>1)').fetchone()[0]
    index.execute('CREATE INDEX chronological_order ON events(chat,ts,mid,seq)')
    # Logical duplicate keys, if present, are excluded from pairing rather than
    # arbitrarily selecting a version of an edited/conflicting message.
    index.execute('CREATE TABLE ambiguous_keys AS SELECT logical_key FROM events WHERE logical_key IS NOT NULL GROUP BY logical_key HAVING count(*)>1')
    index.execute('CREATE UNIQUE INDEX ambiguous_keys_index ON ambiguous_keys(logical_key)')
    rows = index.execute('SELECT e.chat,e.ts,e.mid,e.seq,e.sender,e.me,CASE WHEN a.logical_key IS NOT NULL THEN 3 ELSE e.category END,e.tokens,e.group_kind FROM events e LEFT JOIN ambiguous_keys a ON a.logical_key=e.logical_key ORDER BY e.chat,e.ts,e.mid,e.seq')
    turns = count_turns(rows)
    index.commit()
    index.close()
    source.close()
    def date_value(value):
        return datetime.fromtimestamp(value/1000,timezone(timedelta(hours=7))).isoformat() if value is not None else None
    eligible = counters['logical_duplicate_eligible_rows']
    metrics = {key:counters[key] for key in ('total_messages','text_messages','media_only_messages','system_messages','my_text_messages','others_text_messages','total_text_tokens','my_text_tokens')}
    metrics.update({'unique_senders':len(unique_senders),'conversation_turn_pairs':turns['incoming_to_me_turn_pairs'],'median_message_tokens':median_from_histogram(token_histogram),'date_range':{'start':date_value(min_timestamp),'end':date_value(max_timestamp),'timezone':'Asia/Jakarta'},'duplicate_rate':duplicate_counts['logical']/eligible if eligible else None})
    privacy = [
      {'fields':['sender_jid','chat_jid','jid','jid_row_id','sender_jid_row_id','chat_row_id','_id','key_id'],'risk':'Phone numbers or persistent identifiers and relationship links; use consistent salted pseudonyms and keep any mapping private.'},
      {'fields':['text_data','quoted_messages.text_data','media_caption','raw_transcription_text','translated_text'],'risk':'Unredacted personal content; may include names, contact details, addresses, financial information or credentials. Not printed by this audit.'},
      {'fields':['chat_subject','subject','media_name','file_path'],'risk':'Names, group affiliations, document titles and local storage paths.'},
      {'fields':['timestamp','timestamp_utc','received_timestamp','receipt_server_timestamp','created_timestamp','server_sts'],'risk':'Precise activity times; retain ordering while coarsening dates if preparing a shared training set.'},
      {'fields':['participant_hash','from_me','is_group','archived','hidden','chat_lock','starred','status','recipient_count','view_mode','origination_flags','message_add_on_flags','lookup_tables'],'risk':'Relationship, behavior and private chat-state metadata; remove fields unnecessary for training.'},
      {'fields':['decrypted SQLite database','backup key','key screenshot'],'risk':'Underlying database contains richer private records and may include cryptographic material. Never bundle these with a shared training dataset.'},
    ]
    report = {'metrics':metrics,'tokenizer':{'name':encoding.name,'package_version':importlib.metadata.version('tiktoken'),'scope':'Sum of independently tokenized nonblank type-0 text_data values; original whitespace retained; no JSON, role, chat-template or training-epoch overhead. Captions, quotes, transcripts and system text excluded.'},
      'definitions':{'text_messages':'Nonblank text_data on message_type=0, excluding source message_system links. Plain text only; captioned media reported separately.','media_only_messages':'Non-system media row or known media type with neither nonblank text_data nor nonblank media_caption.','system_messages':'message_type=7 or linked from source message_system; calls, revoked records and unknown structured types remain other_messages.','unique_senders':'Distinct resolved personal JIDs plus canonical self across non-system rows. Incoming direct chats fall back to peer chat JID; LID aliases are resolved using source jid_map. Unknown senders are excluded and counted separately. This is observed account identifiers, not a guaranteed count of distinct humans.','conversation_turn_pairs':'Adjacent incoming-person text turn -> self text turn within one known personal/group chat, chronological timestamp then _id then input sequence; consecutive same-sender text rows form one turn, maximum intermessage gap 30 minutes. Non-text/system/unresolved events and duplicate logical identities break turns. Unknown chat types, status/broadcast/channel contexts are excluded. Chats are never concatenated or merged.','duplicate_rate':'Excess rows sharing (chat_row_id,from_me,key_id,sender_jid_row_id), divided by rows with nonempty key_id. Repeated text is a separate diagnostic, not automatic duplication.','median_message_tokens':'Median o200k_base token count over text_messages, not all records.'},
      'identity':{'canonical_self_sender_id':'self','authoritative_rule':'from_me is true; never infer self from chat_jid or sender popularity.','all_type0_outgoing_sender_row_ids_are_zero':own_text_sender_rows == (1,0,0),'raw_zero_sender_row_id_meaning':'Placeholder/omitted sender on outgoing text, not a globally unique personal sender ID.','actual_self_phone_or_lid':'Not established from authoritative account metadata in the available export; no phone number guessed.','ambiguous_lid_aliases':len(ambiguous_aliases),'source_direction_values':{str(k):v for k,v in raw_direction_counts.items()}},
      'additional_counts':dict(counters),'turn_pair_details':dict(turns),'duplicate_details':{**duplicate_counts,'eligible_rows':eligible,'missing_key_rows':seq-eligible,'exact_record_duplicate_rate':duplicate_counts['exact_record']/seq,'repeated_text_rate_within_chat_and_sender':duplicate_counts['repeated_text']/counters['text_messages']},
      'message_type_counts':dict(kind_counts),'message_type_category_counts':[{'message_type':k,'category':{TEXT:'text',MEDIA_ONLY:'media_only',SYSTEM:'system',OTHER:'other',CAPTIONED_MEDIA:'captioned_media'}[cat],'count':n} for (k,cat),n in sorted(type_categories.items())],
      'chronology':{'original_file_modified':False,'original_order':'SQLite _id; not reliably chronological within chats.','audit_order':['chat_row_id','timestamp','_id','input_sequence'],'session_gap_minutes':30,'timestamp_regressions_in_original_order':counters['timestamp_regressions_in_export_order'],'invalid_or_out_of_range_timestamps':counters['invalid_or_out_of_range_timestamps'],'tie_breaker_warning':'_id resolves equal timestamps deterministically; true causal order of equal-timestamp messages is not recoverable.'},
      'privacy_sensitive_fields':privacy,'validation':{'jsonl_rows_match_source':seq==expected_count,'jsonl_projection_sha256_matches_source':projection_matches,'projection_fields':['_id','chat_row_id','from_me','sender_jid_row_id','message_type','timestamp','key_id','text_data'],'plain_text_count_sql_vs_python':{'sql_trim_nonempty':source_plain_text_count,'python_unicode_strip_nonempty':counters['text_messages']},'text_partition_matches':counters['text_messages']==counters['my_text_messages']+counters['others_text_messages'],'category_partition_matches':seq==sum(counters[k] for k in ('text_messages','media_only_messages','system_messages','other_messages','captioned_media_messages')),'source_message_ids_unique':duplicate_counts['row_id']==0,'network_disabled_during_data_processing':True},
      'input':{'name':'messages.jsonl','bytes':(args.export/'messages.jsonl').stat().st_size,'sha256':input_hash.hexdigest()},'elapsed_seconds':round(time.monotonic()-started,1),'scope_limitations':['Sender counts are observed resolved identifiers; unknown participants and unmapped account aliases prevent a claim about exact distinct people.','Missing chat metadata is not reconstructed from content.','The report contains aggregate metrics and field names, no raw messages, phone numbers, chat names or example excerpts.','Raw export and original database remain unchanged.']}
    if not all(report['validation'][k] for k in ('jsonl_rows_match_source','jsonl_projection_sha256_matches_source','text_partition_matches','category_partition_matches','source_message_ids_unique')):
        raise ValueError('Audit consistency check failed.')
    (args.output/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines = ['# WhatsApp export audit','', 'Aggregate-only local audit; no personal message content is included.','', '| Metric | Value |','|---|---:|']
    for key,value in metrics.items():
        display = (f"{value['start']} to {value['end']}" if key=='date_range' else (f'{value:.8%}' if key=='duplicate_rate' and value is not None else f'{value:,}' if isinstance(value,(int,float)) else str(value)))
        lines.append(f'| {key} | {display} |')
    lines += ['', '## Definitions', ''] + [f'- **{key}**: {value}' for key,value in report['definitions'].items()]
    lines += ['', '## Identity and chronology', '', '- Your canonical sender ID is **self**, using the explicit from_me flag. All outgoing type-0 messages use raw sender_jid_row_id=0; this is a placeholder. Your actual phone-number/LID is not established and has not been guessed.', '- Calculations sort within each chat by timestamp, message ID and input sequence. The original export is unchanged.', f"- Original-order timestamp regressions: {counters['timestamp_regressions_in_export_order']:,}; invalid timestamps: {counters['invalid_or_out_of_range_timestamps']:,}.", '', '## Additional findings', '', f"- Captioned media: {counters['captioned_media_messages']:,}; other records (calls, revocations, structured/unknown types, empty text placeholders): {counters['other_messages']:,}.", f"- Unresolved sender rows outside system events: {counters['unresolved_sender_non_system_rows']:,}; unresolved sender text rows: {counters['unresolved_sender_text_rows']:,}.", f"- Exact record duplicates: {duplicate_counts['exact_record']:,}; repeated text within the same chat/sender: {duplicate_counts['repeated_text']:,} (often legitimate repetitions; not deduplicated).", '', '## Privacy-sensitive fields', '']
    lines += ['- '+', '.join('`'+f+'`' for f in item['fields'])+': '+item['risk'] for item in privacy]
    lines += ['', '## Reproducibility', '', 'Tokenizer: o200k_base, tiktoken '+report['tokenizer']['package_version']+'. Counts are text-only, not model-specific training billing estimates. See audit.json for full definitions, validation, source fingerprint and category counts.']
    (args.output/'audit.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'metrics':metrics,'additional_counts':dict(counters),'identity':report['identity'],'turn_pair_details':dict(turns),'duplicate_details':report['duplicate_details'],'validation':report['validation']},ensure_ascii=False,indent=2),flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Exception strings/tracebacks can contain offending data. Emit only type.
        print('Audit stopped safely: '+type(error).__name__+'; no personal record printed.',file=sys.stderr,flush=True)
        sys.exit(1)
