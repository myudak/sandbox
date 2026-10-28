# Learning log

## Milestone 1 — Environment and provenance

**What:** initialized a clean project, local Git identity, ignored artifact paths and staged-file privacy checks. Selected Python 3.12 to keep the training-library combination conservative.

**Why:** the available 4 GiB GPU requires small initial experiments. Source code and shareable aggregate results must remain separate from private data and model artifacts.

**Evidence:** existing local WhatsApp audit reconciles 3,493,665 records to the SQLite backup; 2,940,539 are nonblank plain-text rows, of which 256,887 are outgoing. These are audit-tokenizer counts, not final training examples or model-token counts.

**Identity:** use `from_me`, not the sender JID placeholder. System messages may also carry this flag; text/category checks still matter.

**Permission:** owner explicitly confirmed permission for all participant content on 28 October 2026. SFT targets remain outgoing responses only. Group adjacency is not automatically a reply.

**What to learn:** an audit is evidence about the source, not proof that the model-ready corpus is clean. Cleaning, pairing, splitting and tokenization each change the usable data and require their own counts.

## Milestone 2 — Real data preparation and held-out boundaries

**Implemented:** streaming JSONL staging; source-backed forwarded/system/quote/alias metadata; salted IDs; configurable permission handling; credential drops and contact/URL/number redaction; same-speaker turns; direct-chat SFT; owner-only LM documents; chronological session splits and cross-split duplicate guards.

**Actual results:** 254,864 owner messages pass message-level cleaning. Final train/validation/test sizes are 27,769 / 14,959 / 8,309 SFT examples and 128,853 / 22,000 / 18,474 owner-only LM documents. One session straddling a split cutoff was removed. See aggregate JSON reports for all removals and cutoffs.

**Tested:** seven model-independent tests passed, including synthetic end-to-end reconstruction. An independent pass over the actual prepared files found no source-message overlap across splits, no exact cross-split examples, strict chronological separation and zero residual matches for the recognized redaction patterns. This does not establish complete anonymization or eliminate all paraphrases.

**Failure and correction:** the first repetition counter did not include speaker identity. The corrected rule retained more legitimate repetitions. A second review identified merged-message boundaries as a privacy risk; merged turns are rescanned. Rebuilding from cached cleaned events preserved the original source and avoided repeating raw-data acquisition.

**Learn:** source-message identity, repeated language and near-duplicate examples are different notions. Short acknowledgements should remain in training. Held-out duplicate documents can be purged without pretending that ordinary repeated words are data corruption. Splitting whole sessions before windows prevents a single response leaking into two splits.

## Milestone 3 — Model implementation and numerical verification

**Implemented:** explicit Q/K/V attention and a triangular causal mask, pre-norm residual blocks, GELU MLP, tied embedding/output weights, learned positions, next-token loss and sampling. Pretrained adaptation uses a separate model loader, native template and response-only labels with rank-8 LoRA.

**Why separate implementations:** the scratch track must reveal the architecture and gradient flow; the pretrained track tests adaptation of existing language knowledge. Shared data/evaluation utilities do not turn random initialization into pretraining.

**Completed numerical evidence:** future-token invariance, tensor shapes, shifted targets, nonzero attention/embedding gradients, optimizer updates, tiny synthetic overfit, checkpoint round trips and generation all passed. The final full suite passed 24 tests using the actual local Qwen tokenizer as well as synthetic examples.

**Resource observation:** the public CUDA download took about 39m22s. A separate CPU environment allowed numerical checks and the first scratch run during setup. The pretrained model transfer required a resumable HTTP fallback; pinned revision and LFS checksum protect reproducibility. GPU training later completed successfully; the CPU and CUDA environments have separate lock files.

## Milestone 4 — Tokenization and objectives

**What/why:** private byte-level BPE is fitted only on `lm_train`; a test changes held-out text and verifies learned vocabulary is unchanged. Its 4,096 tokens keep scratch's embedding/output cost small. Qwen uses its existing tokenizer and native template, with thinking disabled. Private BPE vocabulary can contain personal substrings, so it stays outside Git.

**How:** a synthetic document `[BOS,a,b,EOS,PAD]` becomes inputs `[BOS,a,b,EOS]`, labels `[a,b,EOS,-100]`. Scratch explicitly shifts once; Qwen's model shifts internally. Double-shifting would teach the wrong token. Padding IDs are ignored, while a genuine EOS remains a target even when EOS is also Qwen's padding ID.

For synthetic conversation `user: lagi apa?` → `assistant: belajar pytorch`, all prefix/template labels are -100; only final response plus EOS contribute loss. Context is visible to attention and still affects gradients at target positions. The actual Qwen tokenizer test verifies boundaries rather than trusting an option name. Long contexts lose whole old turns, while overlong responses are excluded rather than truncated.

**Results:** scratch train has 1,251,457 body tokens/1,380,310 predicted targets including EOS, not the audit's 2.65M owner o200k tokens. Median LM turn lengths are 5/7/7 across splits. Qwen train median sequence 46 tokens, p90=77, p99=111; median target 8. Byte BPE preserves slang/emoji but can need multiple tokens for rare words. See DATASET_ANALYSIS.json and SCRATCH_TOKENIZATION.json.

**Learn:** a window is a compute container, not a count of real tokens. Short texts waste padding, and EOS is a large fraction of meaningful targets. Count actual non-padding labels. Do not compare perplexities across the two tokenizations.

## Milestone 5 — Transformer, autograd and optimization

**How:** at B=4,T=128,D=192,H=6, embeddings are [4,128,192]; Q/K/V are [4,6,128,32]; attention scores [4,6,128,128]; logits [4,128,4096]. QK-transpose/sqrt(32) scores similarity; the lower-triangular mask excludes future positions before softmax. Concatenated weighted values are projected back to width 192. The tests perturb future tokens and require unchanged earlier logits.

The MLP expands 192→768, applies GELU and projects back. Pre-LayerNorm stabilizes sublayer inputs; residual additions preserve a direct gradient route. Learned positions encode order. Tied token/output weights save parameters. Larger width increases projection/MLP parameters roughly quadratically; longer context increases explicit attention scores quadratically. More layers increase depth/cost approximately linearly. No pretrained architecture class or weights are used in scratch.py.

**Training step:** `zero_grad` clears previous updates; forward builds a graph; token-summed cross entropy divided by the accumulated valid-token count defines the objective; `backward` computes gradients; clipping limits norm; AdamW updates weights and moment estimates. Warmup/cosine changes LR. Bias/norm vectors have no scratch weight decay. For micro-batches with 2 and 8 targets, average the 10 token losses, not two equally weighted batch means.

**Evidence:** B0's7,656 random parameters memorize the synthetic sequence in 100 steps, loss 2.638861→.000252. Gradient tests cover attention and embeddings, optimizer tests observe weight changes, and checkpoint tests reproduce logits. Resumed actual B1 step 200→201 and A1 step 100→101 restore optimization/RNG state. Changing total planned steps changes the LR schedule; these tests do not claim bit-identical uninterrupted training.

## Milestone 6 — LoRA and real learning dynamics

**What/why:** freeze 596,049,920 Qwen parameters and train 1,146,880 adapter parameters. For each chosen projection W, LoRA learns W+(alpha/r)BA. Rank 8 limits update capacity and optimizer memory. BF 16 plus gradient checkpointing fit this short-context run within the available GPU; quantization was unnecessary. Saving an adapter does not save an independent full model: inference also needs the same base revision.

**Results:**100-step A1 consumes 3,899 target tokens, val NLL 7.6456→5.2094. Lower LR 5e-5 consumes the same tokens, reaches 5.7206 and reduces repetition. These are tiny fractions of the available data. Scratch B1 consumes 15,781 targets in 200 CPU steps; longer scratch consumes 166,249 in 2,000 GPU steps, val 8.3498→6.3260. Both are real, independent training paths. Exact costs/units are in EXPERIMENTS.md.

**What failed:** lower response loss did not preserve elementary instruction behavior. On three validation-time synthetic probes baseline scores 3/3, A1 scores 1/3 and conservative LoRA 0/3. This small set suggests regression; it is not a broad benchmark. Overlap scores cannot prove relevance or personal style. Domain-only tiny updates can change output behavior quickly, even with frozen base weights.

Scratch predicts EOS too often. Body-only validation NLL still improves 8.3443→6.7515, so some non-EOS statistics were learned; EOS is nevertheless argmax on 53.9% of body positions in the longer run. Greedy can choose that token immediately. Sampling reveals some output but does not solve weak language modeling. The model saw only about 12% of the train corpus's target-token count, sampled with replacement; useful generation is not expected from this budget.

## Milestone 7 — Evaluation, privacy and local interface

**What/why:** separate teacher-forced prediction, generated-response proxies and synthetic instruction probes. Use only genuinely held-out source IDs; report aggregates without storing private outputs. The original tiny greedy test probe informed development, so it is explicitly exploratory. Validation drives later checkpoint selection. A fresh locked benchmark and blinded preference study remain future work.

The local playground exposes baseline, conservative LoRA and longer scratch. Baseline remains default. It loads one model at a time, shows timing/token count and uses each current input independently. No messages are sent through WhatsApp. Loopback binding, session token and origin checks limit browser access; request bodies are not logged. Hashed exact/fragment guards can suppress recognized training overlap but miss paraphrases and can suppress legitimate shared phrases. Privacy is not certified.

**Tests/results:**24 unit/integration tests; actual baseline/LoRA/scratch HTTP generation; invalid token/foreign origin rejected; desktop and mobile browser QA completed with zero page errors and no horizontal overflow. Screenshots contain an empty session only. A metadata-label encoding bug was fixed with explicit UTF-8; it did not affect the UTF-8 training data. Browser assertions were adapted to the existing CSP without weakening it.

**What to learn next:** inspect the actual masked labels and tensor shapes, reproduce B0, compare random versus trained body/EOS loss, then test a single controlled data/budget change. A convincing personal chatbot needs relevance and capability evaluation in addition to lower loss. Acquisition, data cleaning, numerical correctness, generalization and privacy are separate claims requiring separate evidence.

## Follow-up — Scratch as a sentence finisher

The scratch interface now matches its owner-text next-token objective: supply an unfinished sentence, display the original prefix and highlighted model suffix together, and optionally reuse the result as the next prefix. This is a presentation/input workflow change; weights, EOS stopping and privacy checks are unchanged. Prefix whitespace is preserved and model text is inserted with text nodes rather than interpreted as HTML. Empty output is explicitly represented as no continuation. Browser QA exercises actual scratch inference plus a synthetic deterministic suffix to verify Keep writing and safe text rendering even when the real checkpoint stops early. This improves experimentation without claiming better model quality.
