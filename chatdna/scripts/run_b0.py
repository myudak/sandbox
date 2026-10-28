"""A genuine tiny random-initialized overfit experiment on synthetic token IDs."""
import argparse
from dataclasses import asdict
from pathlib import Path
import time
import torch
from chatdna.scratch import GPT,GPTConfig
from chatdna.runtime import seed_all,save_json

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    seed_all(7)
    model=GPT(GPTConfig(vocab_size=12,block_size=8,n_layers=1,n_heads=2,d_model=24,dropout=0))
    optimizer=torch.optim.AdamW(model.parameters(),lr=.02)
    x=torch.tensor([[1,2,3,4]])
    y=torch.tensor([[2,3,4,5]])
    initial=float(model(x,y)[1].detach())
    started=time.perf_counter()
    for step in range(100):
        optimizer.zero_grad(); loss=model(x,y)[1]; loss.backward(); optimizer.step()
    final=float(model(x,y)[1].detach())
    generated=model.generate(torch.tensor([[1]]),4,temperature=0).tolist()[0]
    assert final<.1 and generated==[1,2,3,4,5]
    torch.save({'model':model.state_dict(),'config':asdict(model.config),'step':100,'origin':'random_initialization'},args.output/'checkpoint.pt')
    result={'experiment':'B0 synthetic overfit','parameters':sum(p.numel() for p in model.parameters()),'seed':7,'steps':100,'training_tokens':400,'initial_loss':initial,'final_loss':final,'seconds':time.perf_counter()-started,'greedy_synthetic_ids':generated,'device':'cpu','checkpoint_round_trip':'covered by test_scratch.py','private_data_used':False}
    save_json(args.output/'metrics.json',result)
    print(result)

if __name__=='__main__':
    main()
