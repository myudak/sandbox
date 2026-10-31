import json
import pytest
from src.dataset_variants import digest
from src.journal_data import apply_review


def test_review_is_bound_to_source_and_peer_and_preserves_holdout():
    records={'train':[dict(name='a.jpg',image_sha256='a')], 'val':[], 'test':[dict(name='b.jpg',image_sha256='b')]}
    review=dict(schema='journal-reviewed-exclusions-v1',raw_source_fingerprint='raw',base_fingerprint='base',
        exclusions=[dict(split='train',name='a.jpg',image_sha256='a',peer_split='test',peer_name='b.jpg',peer_sha256='b')])
    changed,excluded=apply_review(records,'raw','base',review)
    assert changed['train']==[] and len(excluded)==1
    assert changed['test']==records['test'] and len(records['train'])==1
    with pytest.raises(ValueError,match='identity'):apply_review(records,'wrong','base',review)
    review['exclusions'][0]['peer_sha256']='wrong'
    with pytest.raises(ValueError,match='changed'):apply_review(records,'raw','base',review)


def test_twenty_class_fingerprint_survives_json_roundtrip():
    names={i:f'class-{i}' for i in range(20)}
    assert digest(names)==digest(json.loads(json.dumps(names)))
    with pytest.raises(ValueError,match='Ambiguous'):digest({1:'a','1':'b'})
