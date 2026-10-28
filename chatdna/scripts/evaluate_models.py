"""Run local, aggregate-only generation comparisons."""
import argparse
from pathlib import Path
from chatdna.evaluation import compare, scratch_continuations
from chatdna.runtime import private_runtime


def main():
    private_runtime()
    parser = argparse.ArgumentParser()
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--split', choices=['validation', 'test'], default='validation')
    parser.add_argument('--temperature', type=float, default=.7)
    parser.add_argument('--samples', type=int, default=12)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--scratch-continuations', action='store_true')
    args = parser.parse_args()
    if args.samples < 1 or args.temperature < 0:
        raise ValueError('Invalid evaluation configuration')
    if args.scratch_continuations:
        scratch_continuations(args.registry, args.dataset, args.output, args.samples, args.seed)
    else:
        compare(args.registry, args.dataset, args.output, args.samples, args.seed, args.split, args.temperature)
    print('Aggregate evaluation saved; private strings withheld.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('Evaluation stopped: '+type(error).__name__+' (private values withheld)') from None
