import pytest
from src.journal_statistics import interval, paired_summary
from src.journal import candidate, choose_candidates, select_confirmatory_rows


def fixture_rows(seeds=(101,),dataset='wildlife'):
    return [dict(seed=s,optimizer=o,data_fraction=f,noise_probability=q,status='completed',
        dataset=dataset,roles=[f'{dataset}_confirmation_{s}'],variant_fingerprint=f'{s}-{f}-{q}',
        val_map50_95=.5+(.02 if o=='MuSGD' else 0))
        for s in seeds for o in ('AdamW','MuSGD','SGD') for f in (.2,1.) for q in (0.,.2)]


def test_interval_uses_block_standard_error():
    result=interval([1,2,3],critical=4.3026527299)
    assert result['ci95']==pytest.approx([2-4.3026527299/3**.5,2+4.3026527299/3**.5])
    assert interval([2])['ci95'] is None


def test_paired_math_and_unpaired_rejection():
    rows=fixture_rows()
    result=paired_summary(rows,'val_map50_95',('AdamW','MuSGD','SGD'))
    assert result['paired_optimizer_contrasts'][0]['mean']==pytest.approx(2.)
    assert result['three_way_interactions'][0]['mean']==pytest.approx(0.)
    with pytest.raises(ValueError,match='Duplicate'):paired_summary(rows+[rows[0]],'val_map50_95',('AdamW','MuSGD','SGD'))
    with pytest.raises(ValueError,match='Incomplete'):paired_summary(rows[:-1],'val_map50_95',('AdamW','MuSGD','SGD'))
    rows[0]['variant_fingerprint']='wrong'
    with pytest.raises(ValueError,match='Unpaired'):paired_summary(rows,'val_map50_95',('AdamW','MuSGD','SGD'))


def test_incomplete_block_not_selected():
    rows=fixture_rows((101,102))
    rows[-1]['status']='failed'
    selected,incomplete=select_confirmatory_rows(rows)
    assert len(selected)==12 and len(incomplete)==1
    assert {r['seed'] for r in selected}=={101}


def test_tuning_requires_two_successful_anchors():
    rows=[]
    for optimizer in ('AdamW','MuSGD','SGD'):
        for i,score in enumerate((.5,.6)):
            hp=candidate(optimizer,.001*(i+1))
            for f,q in ((1.,0.),(.2,.2)):
                rows.append(dict(optimizer=optimizer,candidate_id=f'{optimizer}-{i}',hyperparameters=hp,
                    data_fraction=f,noise_probability=q,status='completed',val_map50_95=score))
    rows[-1]['status']='failed'
    selected,diagnostics=choose_candidates(rows)
    assert selected['AdamW']['lr0']==.002
    assert selected['SGD']['lr0']==.001
    assert diagnostics['SGD']['valid_candidates']==1
