# Getting the WhatsApp data: the procedure that actually worked

This documents the Android/Windows acquisition completed on 28 October 2026. It is a procedure for an account and device you are authorized to access. Keep the private working directory outside the repository. No message export, screenshot of a key or decrypted database belongs in Git.

## What worked and what did not

- The phone ran Android 16. ADB was already installed on Windows.
- ADB could read the shared-storage backup folder. It could not read `/data/data/com.whatsapp/files/key` or `encrypted_backup.key`: permission denied on the unrooted device.
- The initial current backup was crypt14. A new end-to-end backup using the app's **64-digit hexadecimal key** produced a crypt15 file. A newly generated key does not unlock the old crypt14 backup.
- Copying and decrypting the crypt15 backup locally succeeded. AES-GCM authentication and SQLite quick_check passed. The database was 4,036,431,872 bytes.
- The old downgrade/legacy-APK guide was not used. Its extractor is marked unmaintained and the old viewer warns about current database incompatibility.

ADB transports files; it does not bypass backup encryption. Do not uninstall, clear application data, unlock the bootloader, root the phone or downgrade WhatsApp for this procedure.

## 1. Enable and authorize ADB

On the phone enable Developer options and USB debugging, connect a data-capable USB cable, unlock the screen and accept the USB debugging fingerprint prompt.

```powershell
adb devices -l
adb shell ls -lah /sdcard/Android/media/com.whatsapp/WhatsApp/Databases/
```

If multiple devices are connected, use `adb -s <DEVICE_SERIAL>` consistently. Treat the serial as private metadata; it is intentionally omitted here. An unauthorized device needs confirmation on the phone; an empty list may indicate the cable, USB mode or driver.

## 2. Preserve existing backups

Before changing backup settings, copy the existing current backup to a private directory. The helper refuses to overwrite and checks source hashes before and after the transfer against the local hash:

```powershell
python scripts/whatsapp/copy_backup.py --filename msgstore.db.crypt14 --output <PRIVATE_BACKUPS>
```

The initial crypt14 copy was retained even though its inaccessible key prevented decryption. It provides a preserved source rather than relying on a risky app replacement.

## 3. Create the matching crypt15 backup

On the phone go to WhatsApp Settings > Chats > Chat backup > End-to-end encrypted backup > Turn on. Under More options choose the **64-digit encryption key**, save it privately, press Continue and finish setup. Then press Back up and wait for the backup to finish.

This is a 64-character hexadecimal key, not a 64-bit key. In password mode WhatsApp retrieves the actual encryption key through its protected key vault; the local decryptor does not obtain that key merely from your password. The manually saved root key is supported by the local crypt15 tools. Password/passkey modes are valid for WhatsApp restore, but are not interchangeable inputs to this offline method.

A screenshot of the key screen alone does not mean setup or backup is complete. In this acquisition the old current crypt14 file disappeared while the new backup was being created; archived copies remained. Wait for the new crypt15 file rather than decrypting an incomplete file.

```powershell
adb shell ls -lah /sdcard/Android/media/com.whatsapp/WhatsApp/Databases/
python scripts/whatsapp/copy_backup.py --filename msgstore.db.crypt15 --output <PRIVATE_BACKUPS>
```

Shared-storage availability and formats vary by app/OS version. If the file is absent or access is denied, report that fact rather than assuming this path guarantees access on every device.

## 4. Decrypt locally and verify

Install the acquisition extra in a separate environment if desired:

```powershell
python -m pip install -e ".[acquisition]"
python scripts/whatsapp/decrypt_backup.py <PRIVATE_KEY_HEX_FILE> <PRIVATE_BACKUPS>/msgstore.db.crypt15 <PRIVATE_BACKUPS>/msgstore.db
```

The key file is ASCII containing exactly the saved 64 hexadecimal characters, without spaces. Enter it into a local editor; do not paste it into shell history, logs, examples or a commit. The helper reads the key from that file, not a command-line key value.

The implementation uses wa-crypt-tools for crypt15 header parsing and key derivation, then streams AES-GCM decryption and zlib decompression. It checks the authentication tag before publishing the SQLite output, confirms the SQLite header and runs PRAGMA quick_check. Output is initially `.partial`; an authentication/decompression failure is not a successful result. The helper intentionally rejects unsupported payload formats rather than forcing a result.

**Observed failure:** OCR read the screenshot's key blocks in the wrong order. Decompression failed on the resulting incorrect key. The key was checked against the visual row order; the corrected transcription then passed authentication. Never accept readable-looking output as a substitute for an authenticating tag check. Do not reproduce the key in a failure report.

The installed historical command-line decryptor had a problematic streaming implementation on inspection. This project's checked streaming wrapper avoids loading gigabytes into scarce RAM and validates both cryptographic authentication and database integrity. Do not treat a zero process exit code or a file named `.db` alone as proof.

## 5. Export all available message records

```powershell
python scripts/whatsapp/export_chats.py <PRIVATE_BACKUPS>/msgstore.db <PRIVATE_EXPORT>
```

Outputs are messages.jsonl, chats.json, quoted_messages.jsonl, media_references.jsonl, summary.json and format notes. The first JSONL retains every source message row, including system and non-text rows; it is not yet a training set. Media references/captions are metadata, not the actual photo/video/audio files. Those files were not copied in this acquisition. Contact names may be absent because the separate contacts database was unavailable.

The observed export contained **3,493,665 message rows**, **778,731 quote rows** and **352,003 media-reference rows**. Source reconciliation, persisted line counts and unique message IDs passed. There were **13,703 messages across 2,934 chat IDs** whose chat-table metadata was absent. These messages were retained, and explicit unknown metadata entries were added to the original chat index; no names were fabricated.

## 6. Audit before preparing model inputs

```powershell
python scripts/whatsapp/audit_export.py --export <PRIVATE_EXPORT> --source-db <PRIVATE_BACKUPS>/msgstore.db --scratch <PRIVATE_AUDIT_WORK> --output <PRIVATE_AUDIT_REPORT>
```

Only aggregates are emitted. The audit treats `from_me=true` as Self, not sender JID zero or the most popular participant. It compares an important content-bearing projection back to SQLite, checks duplicate logical IDs and builds a metadata-only chronological index. The source export is ID-ordered, so conversation processing must sort within each chat by timestamp then message ID.

The verified audit found 2,940,539 nonblank plain-text messages, 256,887 outgoing plain-text messages, 22,021 backward timestamp steps in original ID order and one invalid timestamp. The o200k token totals were 30,657,752 overall and 2,654,182 outgoing; the eventual training tokenizers produce different counts.

## Sources and version limits

- [WhatsApp: encrypted backup options](https://faq.whatsapp.com/490592613091019/)
- [Meta: password vault versus saved encryption key](https://engineering.fb.com/2021/09/10/security/whatsapp-e2ee-backups/)
- [wa-crypt-tools](https://github.com/ElDavoo/wa-crypt-tools)
- [WhatsApp Chat Exporter](https://github.com/KnugiHK/WhatsApp-Chat-Exporter)
- [Android ADB backup restrictions](https://developer.android.com/about/versions/12/behavior-changes-12#adb-backup-restrictions)

This is a recorded successful procedure, not a promise that future WhatsApp versions, backup formats or OS access rules will remain identical. The project does not upload data to external services.
