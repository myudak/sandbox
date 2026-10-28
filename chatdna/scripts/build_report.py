"""Build figures and tables from known aggregate metrics, never message files."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-root', type=Path, required=True)
    args = parser.parse_args()
    docs = Path(__file__).resolve().parents[1] / 'docs'
    root = args.private_root
    copies = {
        'generation-comparison.json': 'GENERATION_PILOT_TEST.json',
        'validation-sampling.json': 'GENERATION_PILOT_VALIDATION.json',
        'candidate-validation.json': 'GENERATION_CANDIDATE_VALIDATION.json',
        'candidate-continuations.json': 'SCRATCH_CONTINUATIONS.json',
        'selection.json': 'SELECTION.json',
        'runs/a1-resume/metrics.json': 'A1_RESUME_RESULTS.json',
        'runs/b1-resume/metrics.json': 'B1_RESUME_RESULTS.json',
    }
    # These producers emit aggregates/configuration only. No registry or vocabulary is copied.
    for source, target in copies.items():
        value = read(root / source)
        (docs / target).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    runs = {name: read(docs / file) for name, file in {
        'A1': 'A1_RESULTS.json', 'A1 conservative': 'A1_CONSERVATIVE_RESULTS.json',
        'B1': 'B1_RESULTS.json', 'B1 longer': 'B1_LONGER_RESULTS.json'}.items()}
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': '#f4f3eb', 'axes.facecolor': '#f4f3eb'})
    figures = docs / 'figures'
    figures.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7))
    colors = ['#1c4a3a', '#b75227']
    for ax, names, label in zip(axes, [('A1', 'A1 conservative'), ('B1', 'B1 longer')],
                               ['Qwen response-token NLL', 'Scratch BPE-token NLL']):
        for name, color in zip(names, colors):
            h = runs[name]['history']
            ax.plot([r['step'] for r in h], [r['validation_loss'] for r in h],
                    label=name+' validation', color=color)
            ax.plot([r['step'] for r in h], [r['train_loss'] for r in h],
                    label=name+' last update', color=color, alpha=.5, linestyle=':')
        ax.set(xlabel='Optimizer steps', ylabel=label)
        ax.legend(fontsize=8)
    fig.suptitle('Measured learning curves: separate objectives and tokenizers')
    fig.text(.04, .015, 'Qwen monitoring: 16 validation examples; final table uses 64. Scratch: first 128 validation blocks. Train curves are noisy last-update losses.', fontsize=8)
    fig.tight_layout(rect=(0, .055, 1, .95))
    fig.savefig(figures / 'loss-curves.png', dpi=160)
    plt.close(fig)
    analysis = read(docs / 'DATASET_ANALYSIS.json')
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, key, title, token_key in zip(axes, ['lm_turns', 'sft_sequences'],
        ['Owner LM body tokens (private BPE)', 'Owner SFT target tokens (Qwen)'], ['body_tokens', 'target_tokens']):
        years = sorted({year for split in analysis[key].values() for year in split['by_year']})
        for split, color in zip(['train', 'validation', 'test'], ['#1c4a3a', '#91a777', '#b75227']):
            ax.plot(years, [analysis[key][split]['by_year'].get(year, {}).get(token_key, 0) for year in years],
                    marker='o', label=split, color=color)
        ax.set(title=title, xlabel='UTC document/response end year', ylabel='Tokens')
        ax.legend(fontsize=8)
        ax.ticklabel_format(axis='y', style='plain')
    fig.suptitle('Actual tokenizer distribution; overlapping datasets must not be added')
    fig.tight_layout()
    fig.savefig(figures / 'token-distribution.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    labels = ['A1 GPU', 'A1 lower LR GPU', 'B1 CPU', 'B1 longer GPU']
    values = list(runs.values())
    rates = [v.get('target_tokens_per_second', v.get('tokens_per_second')) for v in values]
    memory = [v['peak_gpu_bytes'] / 2**30 for v in values]
    axes[0].bar(labels, rates, color=['#1c4a3a', '#91a777', '#b75227', '#cf916d'])
    axes[0].set(yscale='log', ylabel='Predicted non-padding tokens / second (log scale)', title='Measured training-loop throughput')
    axes[1].bar(labels, memory, color=['#1c4a3a', '#91a777', '#b75227', '#cf916d'])
    axes[1].set(ylabel='GiB of peak torch allocated memory', title='Training allocation; CPU entry has no GPU allocation')
    for ax in axes:
        ax.tick_params(axis='x', labelrotation=15)
    fig.text(.04, .015, 'Different tokenizers/hardware/budgets: descriptive, not equivalent work. Includes periodic validation/checkpointing; excludes download/load/final evaluation.', fontsize=8)
    fig.tight_layout(rect=(0, .07, 1, 1))
    fig.savefig(figures / 'compute.png', dpi=160)
    plt.close(fig)
    rows = ['| Run | Device | Steps | Predicted tokens | Seconds | Tokens/s | Final val NLL | Test NLL | Peak allocated GiB |',
            '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, v in runs.items():
        rows.append(f"| {name} | {'GPU' if v['hardware']['cuda_available'] else 'CPU'} | {v['steps']:,} | {v.get('trained_target_tokens_this_run', v.get('trained_tokens_this_run')):,} | {v['seconds']:.2f} | {v.get('target_tokens_per_second', v.get('tokens_per_second')):.2f} | {v['final_validation']['loss']:.4f} | {v['test']['loss']:.4f} | {v['peak_gpu_bytes']/2**30:.3f} |")
    (docs / 'RESULTS_TABLE.md').write_text('\n'.join(rows)+'\n', encoding='utf-8')
    build = read(docs / 'DATASET_BUILD.json')
    cutoffs = {k: datetime.fromtimestamp(v/1000, timezone.utc).isoformat() for k,v in build['split_cutoffs_utc_ms'].items()}
    (docs / 'SPLIT_DATES.json').write_text(json.dumps(cutoffs, indent=2)+'\n', encoding='utf-8')
    print('Aggregate tables, evaluation reports and three figures created.')


if __name__ == '__main__':
    main()
