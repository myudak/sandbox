from chatdna.runtime import save_json, load_json

def test_json_round_trip(tmp_path):
    path=tmp_path/"result.json"
    save_json(path,{"seed":42,"note":"synthetic"})
    assert load_json(path)["seed"]==42
