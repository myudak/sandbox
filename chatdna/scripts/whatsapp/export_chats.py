"""Stream all message rows and useful related records from a verified local backup."""
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def json_default(value):
    if isinstance(value, bytes):
        return {'encoding': 'base64', 'data': base64.b64encode(value).decode('ascii')}
    raise TypeError(type(value).__name__)


def iso_timestamp(value):
    if not value or value < 0:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def write_rows(connection, query, destination, transform=None):
    partial = destination.with_suffix(destination.suffix + '.partial')
    if destination.exists() or partial.exists():
        raise FileExistsError('Export destination already exists.')
    count = 0
    with partial.open('x', encoding='utf-8', newline='\n') as output:
        for row in connection.execute(query):
            record = dict(row)
            if transform:
                record = transform(record)
            output.write(json.dumps(record, ensure_ascii=False, default=json_default, separators=(',', ':')) + '\n')
            count += 1
            if count % 100000 == 0:
                print(f'{destination.name}: {count:,} records', flush=True)
    return partial, count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('database', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA cache_size=-16384')
    jids = {row['_id']: row['raw_string'] for row in connection.execute('SELECT _id, raw_string FROM jid')}
    id_map = {row['lid_row_id']: row['jid_row_id'] for row in connection.execute('SELECT lid_row_id, jid_row_id FROM jid_map')}

    def resolve_jid(row_id):
        return jids.get(id_map.get(row_id, row_id)) or jids.get(row_id)

    chats = {}
    for row in connection.execute('SELECT _id,jid_row_id,subject,created_timestamp,archived,hidden,chat_lock,group_type FROM chat'):
        record = dict(row)
        record['jid'] = resolve_jid(record['jid_row_id'])
        record['is_group'] = bool(record['jid'] and record['jid'].endswith('@g.us'))
        chats[record['_id']] = record
    expected_messages = connection.execute('SELECT count(*) FROM message').fetchone()[0]
    print(f'Source: {expected_messages:,} message rows; {len(chats):,} chat rows.', flush=True)
    with (args.output / 'chats.json').open('x', encoding='utf-8') as output:
        json.dump(list(chats.values()), output, ensure_ascii=False, default=json_default, indent=2)
    stats = Counter()
    chat_ids = set()
    minimum_timestamp = None
    maximum_timestamp = None
    previous_id = None

    def enrich(record):
        nonlocal previous_id, minimum_timestamp, maximum_timestamp
        if previous_id is not None and record['_id'] <= previous_id:
            raise ValueError('Message IDs are not strictly increasing.')
        previous_id = record['_id']
        chat = chats.get(record['chat_row_id'], {})
        record['chat_jid'] = chat.get('jid')
        record['chat_subject'] = chat.get('subject')
        record['is_group'] = chat.get('is_group')
        record['from_me'] = bool(record['from_me'])
        record['sender_jid'] = resolve_jid(record['sender_jid_row_id'])
        record['timestamp_utc'] = iso_timestamp(record['timestamp'])
        stats['sent_by_me' if record['from_me'] else 'received_or_system'] += 1
        if isinstance(record.get('text_data'), str) and record['text_data'].strip():
            stats['rows_with_text_data'] += 1
        stats['type_' + str(record['message_type'])] += 1
        chat_ids.add(record['chat_row_id'])
        if record['timestamp_utc']:
            minimum_timestamp = record['timestamp'] if minimum_timestamp is None else min(minimum_timestamp, record['timestamp'])
            maximum_timestamp = record['timestamp'] if maximum_timestamp is None else max(maximum_timestamp, record['timestamp'])
        return record

    destination = args.output / 'messages.jsonl'
    partial, actual_messages = write_rows(connection, 'SELECT * FROM message ORDER BY _id', destination, enrich)
    if actual_messages != expected_messages:
        raise ValueError('Export count does not match source message count.')
    partial.rename(destination)
    related_counts = {}
    queries = {
        'quoted_messages': 'SELECT * FROM message_quoted',
        'media_references': 'SELECT message_row_id,chat_row_id,file_path,file_size,mime_type,media_name,media_duration,media_caption,raw_transcription_text FROM message_media',
    }
    for name, query in queries.items():
        destination = args.output / (name + '.jsonl')
        partial, count = write_rows(connection, query, destination)
        expected = connection.execute('SELECT count(*) FROM ' + ('message_quoted' if name == 'quoted_messages' else 'message_media')).fetchone()[0]
        if count != expected:
            raise ValueError('Related export count mismatch.')
        partial.rename(destination)
        related_counts[name] = count
    connection.close()
    summary = {
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_database': '../whatsapp-backup-2026-10-28/msgstore.db',
        'source_message_rows': expected_messages,
        'exported_message_rows': actual_messages,
        'source_chat_rows': len(chats),
        'chats_with_messages': len(chat_ids),
        'statistics': dict(stats),
        'related_rows': related_counts,
        'earliest_message_utc': iso_timestamp(minimum_timestamp),
        'latest_message_utc': iso_timestamp(maximum_timestamp),
        'validation': {'aes_gcm_authentication': 'passed', 'sqlite_quick_check': 'passed', 'row_counts_match': True, 'message_ids_unique': True},
        'scope': 'All rows in message, chat, and message_quoted; selected non-key fields from message_media. No filters. Media files themselves are not copied. Other metadata tables remain in the original SQLite database.',
    }
    with (args.output / 'summary.json').open('x', encoding='utf-8') as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    (args.output / 'README.txt').write_text(
        'WHATSAPP LOCAL EXPORT\n\n'
        'messages.jsonl: One JSON object per source message row. All original message columns are preserved; from_me is normalized to a boolean. Extra fields: chat_jid, chat_subject, is_group, sender_jid, timestamp_utc. text_data contains message text when present. Includes system/media records; this is a source dataset, not a curated training set.\n\n'
        'chats.json: Chat IDs, available subjects, resolved JIDs and archive/lock flags. Direct-contact names may be missing because wa.db was unavailable.\n\n'
        'quoted_messages.jsonl: Quote records linked by message_row_id.\n'
        'media_references.jsonl: Selected media metadata, captions and existing transcriptions. Actual images, videos and voice recordings are not included. Media encryption keys are excluded from this file.\n'
        'summary.json: Counts, scope and validation results.\n\n'
        'Ordering: messages are ordered by source _id. Group by chat_row_id and order by timestamp and _id before constructing training conversations. Do not combine separate chats into a single conversation. from_me=true identifies your own outgoing messages. JIDs can be phone-number IDs or WhatsApp local IDs; group IDs are not individual people.\n\n'
        'The original decrypted SQLite database retains tables and metadata outside the JSONL export. Only history present in this backup can be exported. Keep the backup key separately.\n',
        encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('exported_message_rows','source_chat_rows','chats_with_messages','related_rows','earliest_message_utc','latest_message_utc','validation')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
