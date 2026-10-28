# Monorepo publication

ChatDNA is published as `chatdna/` in [myudak/sandbox](https://github.com/myudak/sandbox). It is an independent Python project inside the monorepo; run its commands from that folder. Existing sibling projects remain independent.

The initial import is a snapshot of standalone source commit `55d3f80`, followed by monorepo path/hook adjustments. The original eleven local development commits remain in the standalone checkout; they are not imported as unrelated history or as a nested Git repository. New monorepo commits record subsequent public changes under the owner's configured Git identity.

Included: implementation, tests, dependency locks, configurations, local acquisition helpers, synthetic examples embedded in tests, aggregate experiment reports, and screenshots of empty local UI sessions. The source records real pilot experiments and their quality limitations. The public repository does not contain a ready-trained personal model.

Excluded: WhatsApp exports/message bodies, databases/backups, encryption keys/screenshots, contacts, media, private identity mappings/salt, private tokenizer vocabulary, memorization-guard hashes, registries with local artifact paths, model weights/adapters, optimizer/checkpoint files and environment credentials. Only reviewed tracked source files were copied. Private artifacts remain local; no private training strings or weights are published.

The experiment reports describe the original local run layout and chronology. Private artifact locations in that report are historical relative paths, not files distributed by this monorepo. Set external private paths for a new installation. The staged-file guard and optional hook support this project as a monorepo subfolder. The hook is not automatically installed into other clones.

Reproduction still requires appropriately authorized data and local training. Redaction is risk reduction rather than proof of anonymity, and weights trained on private data require their own review before any future publication.

Validation after import: all 25 tests passed, including the actual local Qwen tokenizer and an additional test of synthetic fixture staging under the monorepo prefix. Staged-file privacy checks passed before publication.
