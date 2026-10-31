import csv
import json
from pathlib import Path

import pytest

from src.experiment import load_config, planned_runs, run_study
from src.metrics import write_results

ROOT = Path(__file__).resolve().parents[1]


def test_bounded_plans_and_control_inheritance():
    smoke = load_config(ROOT / "configs/smoke.yaml")
    pilot = load_config(ROOT / "configs/pilot.yaml")
    assert planned_runs(smoke) == 2
    assert planned_runs(pilot) == 8
    assert pilot["train"]["imgsz"] == 512
    assert pilot["train"]["amp"] is False
    assert pilot["evaluation"]["split"] == "val"


def test_run_cap_fails_before_gpu_import(tmp_path):
    with pytest.raises(ValueError, match="max_runs"):
        run_study(ROOT / "configs/pilot.yaml", tmp_path / "runs", max_runs=2)


def test_test_access_and_auto_optimizer_rejected(tmp_path):
    import yaml
    config = load_config(ROOT / "configs/smoke.yaml")
    path = tmp_path / "config.yaml"
    config["evaluation"]["split"] = "test"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="only evaluates validation"):
        load_config(path)
    config["evaluation"]["split"] = "val"
    config["optimizers"] = {"auto": {"lr0": 0.01}}
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="auto is prohibited"):
        load_config(path)


def test_failures_remain_in_machine_readable_outputs(tmp_path):
    rows = [{"run_id": "a", "status": "completed", "val_map50_95": 0.2},
            {"run_id": "b", "status": "oom", "error": "out of memory"}]
    write_results(tmp_path, rows)
    assert json.loads((tmp_path / "results.json").read_text()) == rows
    with (tmp_path / "results.csv").open(newline="") as stream:
        result = list(csv.DictReader(stream))
    assert len(result) == 2 and result[1]["status"] == "oom"
    assert result[1]["val_map50_95"] == ""
