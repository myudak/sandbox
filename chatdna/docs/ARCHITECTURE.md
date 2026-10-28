# Two independent models

## A: pretrained adaptation

Qwen3-0.6B is the pretrained multilingual conversational model, pinned to the revision in configs/finetune/small.json under Apache-2.0. Its native chat template is used with thinking disabled. There is no external inference API. The base weights are downloaded once; private examples are processed locally with local-files-only loading and telemetry disabled.

LoRA freezes W and learns a low-rank update: effective W = W + (alpha/r) B A. With rank r=8, A is [8,input_width] and B is [output_width,8], instead of training the entire [output_width,input_width] matrix. Only attention q_proj and v_proj are adapted initially. AdamW keeps states for trainable parameters, reducing memory. No quantization is required for the first small configuration; actual fitting is measured rather than inferred from parameter size alone.

Each sample is chat-template(context) + owner response + EOS. Prefix labels are -100; target labels are the owner's response token IDs. The model shifts internally so the last prefix position predicts the first response token. Context remains visible to attention. Masking the loss does **not** mean context has no effect on target gradients. Tests check actual token boundaries, not only a trainer setting. Whole old context turns may be removed for length; a response is never silently cut into a different target.

## B: random-initialized GPT

src/chatdna/scratch.py implements the architecture directly with PyTorch operations. It does not instantiate a pretrained GPT class or load pretrained weights. A private byte-level BPE is trained solely on the training split; learned tokenizer files are also private artifacts.

For B=4, T=128, D=192, H=6 and head width=32:

1. Token IDs [4,128] index token embeddings [vocabulary,192]. Learned position embeddings [128,192] are added, producing x [4,128,192].
2. A linear projection produces Q/K/V, each reshaped to [4,6,128,32]. Q K-transpose / sqrt(32) gives scores [4,6,128,128].
3. A lower-triangular mask fills future scores with negative infinity. Softmax makes future probabilities zero. Weighted V is concatenated back to [4,128,192] and projected.
4. Pre-LayerNorm residual blocks apply x + attention(norm(x)), then x + MLP(norm(x)). The MLP expands D to 4D, applies GELU, then projects back.
5. Final LayerNorm and a vocabulary projection produce logits [4,128,vocabulary]. The projection shares token-embedding weights; all weights begin random.

The next-token dataset gives input=sequence[:-1] and target=sequence[1:]. Unlike the pretrained HF model's loss, this forward function expects targets already shifted. Right padding is masked with -100. Causal attention prevents padded future positions influencing valid earlier tokens. Documents stay separate and splits are assigned before token windows exist.

Training: zero_grad -> forward -> cross-entropy -> backward -> clip_grad_norm -> optimizer.step. Autograd propagates prediction error through logits, MLPs, attention, positions and token embeddings. AdamW applies adaptive moments and decoupled weight decay; norm/bias vectors are excluded from scratch weight decay. Warmup/cosine scheduling changes the learning rate rather than the objective.

Gradient accumulation uses token-weighted summed losses, not an unweighted average of short and long micro-batches. Validation also sums token losses before dividing by valid target-token count. Checkpoints store model/optimizer state, step and sampler/torch RNG states. Resumption restores optimization and sampling state; kernels may still vary numerically across hardware.

## Evaluation interpretation

Perplexity is exp(mean next-token loss) in that model's token units. Do not rank the scratch BPE and Qwen by raw perplexity as though token units were identical. Compare each model with its own baseline, then use common held-out prompts and explicit style/relevance/memorization measurements. A lower training loss does not establish better conversation or privacy.

A 128-token model, short informal texts and a limited personal corpus will not recreate the pretrained model's general language knowledge. B0 overfitting proves the learning machinery works; B1 held-out prediction asks whether it generalizes at all. Neither proves human-like conversation.
