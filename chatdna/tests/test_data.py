from chatdna.data import clean_text,LeakageGuard,split_for,DataPolicy
import pytest

def test_style_preserved_and_sensitive_removed():
    text='WKWK anjirrr 🤣 belajar PyTorch seruu!!'
    assert clean_text(text)[0]==text
    address='fake'+'@'+'example.org'
    cleaned,counts=clean_text('email '+address+' https://example.org/private')
    assert address not in cleaned
    assert '[EMAIL]' in cleaned and '[URL]' in cleaned
    assert counts['email']==1

def test_credentials_dropped_and_empty_excluded():
    assert clean_text('password: synthetic-only')[0] is None
    assert clean_text('\u2003 \n')[0] is None
    assert clean_text('<Media omitted>')[0] is None
    assert clean_text('password:\nsynthetic-only')[0] is None

def test_phone_redaction():
    phone='08'+'1234567890'
    assert phone not in clean_text('hubungi '+phone)[0]

def test_chronological_boundary_purge():
    assert split_for(1,9,10,20)=='train'
    assert split_for(9,11,10,20) is None
    assert split_for(11,19,10,20)=='validation'
    assert split_for(21,22,10,20)=='test'

def test_leakage_repeats_retained_only_within_split():
    guard=LeakageGuard()
    assert guard.accept('WKWK  yes','train')[0]
    assert guard.accept('wkwk yes','train')[0]
    assert not guard.accept('WKWK YES','test')[0]
    assert guard.accept('different held out response','test')[0]

def test_near_duplicate_heldout_document_rejected():
    original=' '.join('syntheticword'+str(i) for i in range(1000))
    revised=original+' extra'
    guard=LeakageGuard()
    assert (guard.simhash(original)^guard.simhash(revised)).bit_count()<=3
    assert guard.accept(original,'train')[0]
    assert not guard.accept(revised,'test')[0]

def test_invalid_policy_rejected():
    with pytest.raises(ValueError):
        DataPolicy(train_fraction=.95,validation_fraction=.1)
    with pytest.raises(ValueError):
        DataPolicy(session_gap_minutes=0)
