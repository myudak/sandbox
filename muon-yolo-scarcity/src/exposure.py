"""Deterministic exposure blocks and lazy CUDA trainer integration."""
from __future__ import annotations

import hashlib
import math


class CyclicOrder:
    """One shuffled stream, independent of how it is divided into exposure blocks."""

    def __init__(self, size: int, seed: int):
        if size < 1:
            raise ValueError("Empty sampling population")
        self.size, self.seed, self.cycle, self.position = size, seed, 0, 0
        self.order = self._order()

    def _order(self):
        return sorted(range(self.size), key=lambda i: hashlib.sha256(
            f"exposure-v1:{self.seed}:{self.cycle}:{i}".encode()).digest())

    def take(self, count: int):
        if count < 1:
            raise ValueError("Positive exposure block required")
        result = []
        while len(result) < count:
            available = min(count - len(result), self.size - self.position)
            result.extend(self.order[self.position:self.position + available])
            self.position += available
            if self.position == self.size:
                self.cycle += 1
                self.position = 0
                self.order = self._order()
        return result


def effective_samples(population: int, batch: int, fixed_samples: int | None):
    samples = fixed_samples if fixed_samples is not None else math.ceil(population / batch) * batch
    if batch < 1 or samples < batch or samples % batch:
        raise ValueError("Exposure block must contain complete fixed-size batches")
    return samples


def image_identity(path: str):
    normalized = str(path).replace("\\", "/")
    if "/images/train/" not in normalized:
        raise ValueError(f"Unexpected training image path: {path}")
    return normalized.rsplit("/images/train/", 1)[1]


def make_exposure_trainer(sampling: dict):
    """Torch is imported only inside the remote CUDA training process."""
    import torch
    from ultralytics.data.build import InfiniteDataLoader, seed_worker
    from ultralytics.models.yolo.detect import DetectionTrainer

    class ExposureSampler(torch.utils.data.Sampler):
        def __init__(self, population, samples, seed):
            self.stream = CyclicOrder(population, seed)
            self.samples = samples

        def __len__(self):
            return self.samples

        def __iter__(self):
            return iter(self.stream.take(self.samples))

    class ExposureTrainer(DetectionTrainer):
        def __init__(self, *args, **kwargs):
            self.exposure_images = 0
            self.exposure_batches = 0
            self.exposure_hash = hashlib.sha256()
            super().__init__(*args, **kwargs)

        def get_dataloader(self, dataset_path, batch_size=16, rank=0, mode="train"):
            if mode != "train":
                return super().get_dataloader(dataset_path, batch_size, rank, mode)
            if self.world_size > 1 or self.args.nbs != self.args.batch or self.args.warmup_epochs:
                raise ValueError("Exposure control requires one device, no accumulation and zero warmup")
            dataset = self.build_dataset(dataset_path, mode, batch_size)
            samples = effective_samples(len(dataset), batch_size, sampling.get("samples_per_epoch"))
            self.exposure_samples_per_epoch = samples
            sampler = ExposureSampler(len(dataset), samples, self.args.seed + 30000)
            generator = torch.Generator().manual_seed(self.args.seed + 40000)
            workers = min(self.args.workers, 2)
            return InfiniteDataLoader(dataset=dataset, batch_size=batch_size, sampler=sampler,
                shuffle=False, num_workers=workers, collate_fn=dataset.collate_fn,
                worker_init_fn=seed_worker, generator=generator, pin_memory=True,
                drop_last=False, prefetch_factor=2 if workers else None)

        def preprocess_batch(self, batch):
            self.exposure_images += int(batch["img"].shape[0])
            self.exposure_batches += 1
            for path in batch["im_file"]:
                self.exposure_hash.update(image_identity(path).encode() + b"\0")
            return super().preprocess_batch(batch)

        def build_optimizer(self, model, name="auto", lr=0.001, momentum=0.9, decay=1e-5, iterations=1e5):
            optimizer = super().build_optimizer(model, name, lr, momentum, decay, iterations)
            multiplier = sampling.get("musgd_head_lr_multiplier", 3.0)
            if name == "MuSGD" and multiplier != 3.0:
                for group in optimizer.param_groups:
                    if math.isclose(group["lr"], lr * 3, rel_tol=1e-8):
                        group["lr"] = lr * multiplier
            return optimizer

    return ExposureTrainer
