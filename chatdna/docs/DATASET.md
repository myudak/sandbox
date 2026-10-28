# Dataset protocol

The source audit contains 3,493,665 records, not 3.49 million trainable responses. Plain-text eligibility uses type 0, nonblank Unicode text and the absence of a source system-message link. Self is always from_me=true. Calls, revocations, captions and unknown types are not silently converted into prose.

The owner confirmed participant permission. Direct-chat context may therefore include other participants; labels supervise only the final owner response. A self-only fallback excludes all participant text and still builds the scratch corpus. Group SFT is disabled unless quoted-only pairing is explicitly enabled.

Preparation streams the JSONL, reconciles its row count to the original database, uses source forwarding/quote/alias metadata and stages redacted events outside the repository. Chat and participant metadata are salted pseudonyms; the salt is never committed. Text is still private.

Cleaning applies Unicode NFC, drops whitespace-only/unsupported placeholders and messages longer than 2,000 characters, drops known forwarded records and credential-bearing messages, and redacts phone-like strings, emails, URLs, persistent JIDs and long digit strings. Names, addresses and sensitive facts may remain. Slang, capitalization, repeated letters, laughter and emoji are preserved. Only bursts exceeding six identical consecutive messages in one minute are curtailed; normal repetition remains.

Chronology is per original chat, timestamp, then source message ID. Non-text/invalid/unresolved events are context barriers. Same-sender turns merge up to eight messages and 2,000 characters; a 30-minute gap begins a new session. Direct incoming-to-owner adjacency is a candidate, not proof of a reply. An explicit quote must match the prior incoming turn; otherwise the pair is dropped. No future text is used.

Whole sessions receive chronological 80/10/10 boundaries; sessions straddling either cutoff are purged. Training repetitions are retained, while exact normalized and near-duplicate held-out documents/examples are removed across splits. Near detection uses 64-bit three-word-shingle SimHash, four bands and Hamming distance at most three for documents at least twelve words long. This is a conservative heuristic, not proof against all paraphrases. Overlapping windows remain inside their assigned document/split.

Dataset A: messages with role/content, final assistant target, pseudonymous chat/session, source IDs, times and evidence. Dataset B: owner-only turn documents with explicit document boundaries. Everything except aggregates remains private. Model-specific token counts are calculated later using each training tokenizer; audit o200k counts must not be substituted.

Language/code-switching proportions are intentionally not asserted from an unvalidated heuristic. Actual reports record filtering, year counts, split dates/fingerprints and leakage rejections.
