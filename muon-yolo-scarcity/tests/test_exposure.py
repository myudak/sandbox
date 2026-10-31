from collections import Counter
import pytest
from src.exposure import CyclicOrder, effective_samples, image_identity
from src.dataset_variants import digest


def test_stream_is_independent_of_block_boundaries():
    a, b = CyclicOrder(23, 101), CyclicOrder(23, 101)
    assert a.take(23) + a.take(23) + a.take(23) == b.take(69)
    assert CyclicOrder(23, 102).take(69) != CyclicOrder(23, 101).take(69)


def test_cyclic_sampling_balances_exposure_and_covers_every_image():
    values = CyclicOrder(205, 30042).take(1024)
    counts = Counter(values)
    assert len(values) == 1024 and len(counts) == 205
    assert max(counts.values()) - min(counts.values()) == 1


def test_complete_batches_and_normalized_image_ids():
    assert effective_samples(205, 16, None) == 208
    assert effective_samples(1021, 16, None) == 1024
    assert effective_samples(205, 16, 1024) == 1024
    with pytest.raises(ValueError): effective_samples(205, 16, 1023)
    assert image_identity('/tmp/v/images/train/nested/a.jpg') == 'nested/a.jpg'
    assert image_identity(r'D:\v\images\train\a.jpg') == 'a.jpg'


def test_twenty_class_json_hash_survives_serialization():
    import json
    names = dict(enumerate(str(i) for i in range(20)))
    assert digest(names) == digest(json.loads(json.dumps(names)))
