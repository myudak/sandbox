"""Write private absolute checkpoint paths outside the repository."""
import argparse
import json
from pathlib import Path
from chatdna.inference import MemorizationGuard
from chatdna.runtime import save_json

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--private-root',type=Path,required=True); args=parser.parse_args()
    root=args.private_root.resolve()
    selection=json.loads((root/'selection.json').read_text(encoding='utf-8')) if (root/'selection.json').exists() else {}
    lora_run=selection.get('lora_run','a1')
    scratch_run=selection.get('scratch_run','b1')
    guard=root/'memorization-guard.json'
    MemorizationGuard.build(root/'dataset-v3',guard)
    base=str(root/'models/qwen3-0.6b')
    registry={'guard':str(guard),'models':{
      'baseline':{'kind':'baseline','base':base,'label':'Qwen3 · baseline','checkpoint_label':'c1899de · pretrained','details':'596M pretrained parameters. Native chat template; no personal adaptation.'},
      'lora':{'kind':'lora','base':base,'adapter':str(root/f'runs/{lora_run}/adapter'),'label':'Qwen3 · experimental LoRA','checkpoint_label':lora_run,'details':'1.15M trainable adapter parameters. General instruction probes regressed; baseline remains recommended.'},
      'scratch':{'kind':'scratch','checkpoint':str(root/f'runs/{scratch_run}/checkpoint.pt'),'tokenizer':str(root/'bpe-v1/tokenizer.json'),'label':'GPT · from scratch','checkpoint_label':scratch_run,'details':'2.59M parameters, trained from random weights. Weak own-text continuation; not instruction tuning.'}}}
    save_json(root/'registry.json',registry)
    print('Three-model local registry created; private paths withheld.')

if __name__=='__main__':
    main()
