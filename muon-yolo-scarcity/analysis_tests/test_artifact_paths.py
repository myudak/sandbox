from pathlib import PureWindowsPath
import pytest
from scripts.artifact_paths import comparable_path


def test_extended_drive_and_unc_paths_preserve_containment():
    assert comparable_path('\\\\?\\D:\\work\\result.json')=='D:\\work\\result.json'
    assert comparable_path('\\\\?\\UNC\\server\\share\\result.json')=='\\\\server\\share\\result.json'
    root=PureWindowsPath('D:/work')
    assert PureWindowsPath(comparable_path('\\\\?\\D:\\work\\nested\\result.json')).is_relative_to(root)
    assert not PureWindowsPath(comparable_path('\\\\?\\D:\\outside\\result.json')).is_relative_to(root)
    with pytest.raises(ValueError):comparable_path('\\\\?\\GLOBALROOT\\Device\\HarddiskVolume1')
