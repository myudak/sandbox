from dataclasses import asdict
import torch
from torch.nn import functional as F
from chatdna.scratch import GPT,GPTConfig

def tiny():
    torch.manual_seed(7)
    torch.set_num_threads(2)
    return GPT(GPTConfig(vocab_size=12,block_size=8,n_layers=1,n_heads=2,d_model=24,dropout=0))

def test_shapes_and_next_token_loss():
    model=tiny()
    ids=torch.tensor([[1,2,3,4,5]])
    logits,loss=model(ids[:,:-1],ids[:,1:])
    assert logits.shape==(1,4,12)
    assert torch.allclose(loss,F.cross_entropy(logits.reshape(-1,12),ids[:,1:].reshape(-1)))

def test_future_cannot_change_past():
    model=tiny().eval()
    a=torch.tensor([[1,2,3,4,5]])
    b=a.clone(); b[:,3:]=9
    assert torch.allclose(model(a)[0][:,:3],model(b)[0][:,:3],atol=1e-6)

def test_gradients_and_optimizer_update():
    model=tiny()
    optimizer=torch.optim.AdamW(model.parameters(),lr=.01)
    before=model.token_embedding.weight.detach().clone()
    _,loss=model(torch.tensor([[1,2,3]]),torch.tensor([[2,3,4]]))
    loss.backward()
    assert model.blocks[0].attention.qkv.weight.grad.abs().sum()>0
    assert model.token_embedding.weight.grad.abs().sum()>0
    optimizer.step()
    assert not torch.equal(before,model.token_embedding.weight)

def test_tiny_overfit_and_checkpoint(tmp_path):
    model=tiny()
    optimizer=torch.optim.AdamW(model.parameters(),lr=.02)
    x=torch.tensor([[1,2,3,4]])
    y=torch.tensor([[2,3,4,5]])
    initial=model(x,y)[1].item()
    for _ in range(100):
        optimizer.zero_grad(); loss=model(x,y)[1]; loss.backward(); optimizer.step()
    assert model(x,y)[1].item()<min(.1,initial*.1)
    path=tmp_path/'checkpoint.pt'
    torch.save({'state':model.state_dict(),'config':asdict(model.config)},path)
    saved=torch.load(path,weights_only=True)
    restored=GPT(GPTConfig(**saved['config']))
    restored.load_state_dict(saved['state'])
    assert torch.equal(model(x)[0],restored(x)[0])
    assert restored.generate(torch.tensor([[1]]),max_new_tokens=4,temperature=0).tolist()==[[1,2,3,4,5]]
