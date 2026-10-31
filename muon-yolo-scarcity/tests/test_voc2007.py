import pytest
from src.voc2007 import convert_annotation


def xml(box="1 1 100 50", difficult=1):
    x1,y1,x2,y2=box.split()
    return f'<annotation><size><width>100</width><height>50</height></size><object><name>person</name><difficult>{difficult}</difficult><bndbox><xmin>{x1}</xmin><ymin>{y1}</ymin><xmax>{x2}</xmax><ymax>{y2}</ymax></bndbox></object></annotation>'


def test_inclusive_full_image_and_difficult_are_preserved():
    text, report = convert_annotation(xml())
    assert list(map(float,text.split())) == [14,0.5,0.5,1,1]
    assert report['difficult_included']==1 and report['objects']==1


def test_single_pixel_box_and_recorded_clipping():
    text,_=convert_annotation(xml('10 20 10 20'))
    values=list(map(float,text.split()))
    assert values[3:]==[0.01,0.02]
    _,report=convert_annotation(xml('0 0 101 51'))
    assert report['boxes_clipped_to_image']==1


def test_invalid_voc_boxes_and_dtd_rejected():
    with pytest.raises(ValueError):convert_annotation(xml('50 40 10 20'))
    with pytest.raises(ValueError):convert_annotation('<!DOCTYPE annotation>'+xml())
