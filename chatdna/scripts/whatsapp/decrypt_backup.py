"""Decrypt a local crypt15 copy, authenticating before publishing SQLite output."""
import argparse
import hashlib
import logging
from pathlib import Path
import sqlite3
import zlib

from Cryptodome.Cipher import AES
from wa_crypt_tools.lib.db.dbfactory import DatabaseFactory
from wa_crypt_tools.lib.db.db15 import Database15
from wa_crypt_tools.lib.key.keyfactory import KeyFactory


class RejectLibraryErrors(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            raise RuntimeError('Backup parser rejected the file: ' + record.getMessage())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('key_path', type=Path)
    parser.add_argument('backup', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    logging.getLogger('wa_crypt_tools').addHandler(RejectLibraryErrors())
    partial = args.output.with_suffix('.db.partial')
    if args.output.exists() or partial.exists():
        raise FileExistsError('Output or partial output already exists; preserving it.')
    key = KeyFactory.from_hex(args.key_path.read_text(encoding='ascii').strip())
    chunk_size = 1024 * 1024
    size = args.backup.stat().st_size
    with args.backup.open('rb') as source:
        database = DatabaseFactory.from_file(source)
        if not isinstance(database, Database15):
            raise ValueError('Expected crypt15; refusing to apply this key to another format.')
        payload_offset = source.tell()
        source.seek(0)
        digest = hashlib.md5()
        remaining = size - 16
        while remaining:
            chunk = source.read(min(chunk_size, remaining))
            if not chunk:
                raise ValueError('Unexpected end of encrypted backup.')
            digest.update(chunk)
            remaining -= len(chunk)
        has_checksum = digest.digest() == source.read(16)
        ciphertext_end = size - (32 if has_checksum else 16)
        source.seek(ciphertext_end)
        tag = source.read(16)
        source.seek(payload_offset)
        cipher = AES.new(key.get(), AES.MODE_GCM, nonce=database.get_iv())
        decompressor = zlib.decompressobj()
        remaining = ciphertext_end - payload_offset
        with partial.open('xb') as target:
            while remaining:
                chunk = source.read(min(chunk_size, remaining))
                if not chunk:
                    raise ValueError('Unexpected end of ciphertext.')
                remaining -= len(chunk)
                pending = cipher.decrypt(chunk)
                while pending:
                    target.write(decompressor.decompress(pending, 8 * chunk_size))
                    pending = decompressor.unconsumed_tail
            cipher.verify(tag)
            target.write(decompressor.flush())
            if not decompressor.eof or decompressor.unused_data:
                raise ValueError('Incomplete or unexpected compressed payload.')
    print('AES-GCM authentication passed.', flush=True)
    with partial.open('rb') as source:
        if source.read(16) != b'SQLite format 3\x00':
            raise ValueError('Decrypted payload is not a SQLite database.')
    connection = sqlite3.connect(partial.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        checks = connection.execute('PRAGMA quick_check').fetchall()
        if checks != [('ok',)]:
            raise ValueError('SQLite quick_check failed.')
    finally:
        connection.close()
    partial.rename(args.output)
    print(f'SQLite quick_check passed. Database saved ({args.output.stat().st_size} bytes).')


if __name__ == '__main__':
    main()
