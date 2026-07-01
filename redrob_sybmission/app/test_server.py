import sys
from pathlib import Path


APP = Path(__file__).resolve().parent
sys.path.insert(0, str(APP))

import server


def test_default_dataset_exists():
    assert server.DEFAULT_DATASET.is_file()


def test_model_assets_exist():
    assert server.MODEL_PATH.is_file()
    assert server.LABELS_PATH.is_file()


def test_engine_loads_sample():
    sample = (
        server.ROOT.parent
        / "[PUB] India_runs_data_and_ai_challenge"
        / "India_runs_data_and_ai_challenge"
        / "sample_candidates.json"
    )
    data = __import__("json").loads(sample.read_text(encoding="utf-8"))
    temp = server.ROOT / "data" / "imports" / "_test_sample.jsonl"
    temp.parent.mkdir(parents=True, exist_ok=True)
    with temp.open("w", encoding="utf-8") as handle:
        for item in data:
            handle.write(__import__("json").dumps(item) + "\n")
    state = server.ENGINE.load(temp, "test sample", imported=True)
    assert len(state.candidates) == len(data)
    assert state.candidates[0]["rank"] == 1
    temp.unlink(missing_ok=True)

