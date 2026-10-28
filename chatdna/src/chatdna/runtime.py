import json
import os
from pathlib import Path
import random

def private_runtime():
    for key, value in {"HF_HUB_DISABLE_TELEMETRY":"1", "HF_HUB_OFFLINE":"1", "DO_NOT_TRACK":"1", "WANDB_DISABLED":"true", "WANDB_MODE":"disabled", "TOKENIZERS_PARALLELISM":"false"}.items():
        os.environ[key] = value

def seed_all(seed=42):
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4)

def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def records(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)

def hardware():
    import platform
    import torch
    result = {"python":platform.python_version(), "torch":torch.__version__, "cuda_available":torch.cuda.is_available(), "torch_cuda":torch.version.cuda, "cpu_threads":os.cpu_count()}
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        free, total = torch.cuda.mem_get_info()
        result.update(gpu=props.name, gpu_total_bytes=total, gpu_free_bytes=free)
    return result
