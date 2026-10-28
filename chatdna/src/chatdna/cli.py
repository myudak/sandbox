import argparse
import json
from pathlib import Path
from .runtime import private_runtime

def main():
    private_runtime()
    parser=argparse.ArgumentParser(prog='chatdna')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    p.add_argument('--export',required=True); p.add_argument('--source-db',required=True); p.add_argument('--output',required=True)
    p.add_argument('--participant-context-authorized',action='store_true')
    p.add_argument('--config')
    p=sub.add_parser('validate'); p.add_argument('--dataset',required=True)
    p=sub.add_parser('tokenize'); p.add_argument('--dataset',required=True); p.add_argument('--output',required=True); p.add_argument('--vocab-size',type=int,default=4096); p.add_argument('--block-size',type=int,default=128)
    for command in ('train-scratch','train-lora'):
        p=sub.add_parser(command); p.add_argument('--data',required=True); p.add_argument('--output',required=True); p.add_argument('--steps',type=int); p.add_argument('--seed',type=int); p.add_argument('--resume'); p.add_argument('--config'); p.add_argument('--learning-rate',type=float); p.add_argument('--micro-batch',type=int); p.add_argument('--accumulation',type=int)
        if command=='train-lora':
            p.add_argument('--model',required=True)
    sub.add_parser('hardware')
    p=sub.add_parser('serve'); p.add_argument('--registry',required=True); p.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if args.command in {'prepare','tokenize','train-scratch','train-lora'}:
        repo=Path(__file__).resolve().parents[2]
        if Path(args.output).resolve().is_relative_to(repo):
            raise ValueError('Private outputs must be outside the source repository')
    config=json.loads(Path(args.config).read_text(encoding='utf-8')) if getattr(args,'config',None) else {}
    if args.command=='prepare':
        from .data import build
        result=build(args.export,args.source_db,args.output,args.participant_context_authorized,policy=config or None)
    elif args.command=='validate':
        from .validation import validate_dataset
        result=validate_dataset(args.dataset)
    elif args.command=='tokenize':
        from .tokenization import train_tokenizer
        result=train_tokenizer(args.dataset,args.output,args.vocab_size,args.block_size)
    elif args.command=='train-scratch':
        from .train_scratch import train
        from .scratch import GPTConfig
        architecture=GPTConfig(**{k:config[k] for k in ('vocab_size','block_size','n_layers','n_heads','d_model','dropout') if k in config}) if config else None
        result=train(args.data,args.output,args.steps or config.get('steps',200),seed=args.seed if args.seed is not None else config.get('seed',42),resume=args.resume,batch_size=args.micro_batch or config.get('micro_batch',4),accumulation=args.accumulation or config.get('gradient_accumulation',2),lr=args.learning_rate or config.get('learning_rate',.0003),config=architecture,log_every=config.get('log_every',25))
    elif args.command=='train-lora':
        from .finetune import train
        result=train(args.model,args.data,args.output,args.steps or config.get('steps',100),seed=args.seed if args.seed is not None else config.get('seed',42),resume=args.resume,micro_batch=args.micro_batch or config.get('micro_batch',1),accumulation=args.accumulation or config.get('gradient_accumulation',4),lr=args.learning_rate or config.get('learning_rate',.0002),max_length=config.get('max_length',128),rank=config.get('rank',8))
    elif args.command=='hardware':
        from .runtime import hardware
        result=hardware()
    else:
        from .playground import serve
        serve(args.registry,args.port)
        return
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Do not leak offending dataset rows through exception text/tracebacks.
        raise SystemExit('Operation stopped: '+type(error).__name__+' (private values withheld)') from None
