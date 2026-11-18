import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_43_emd():
    gj = json.loads((ROOT / "data_ext" / "jeju_emd.geojson").read_text(encoding="utf-8"))
    names = [f["properties"]["emd"] for f in gj["features"]]
    assert len(names) == 43 and len(set(names)) == 43
    assert {"추자면", "우도면"} <= set(names)


def test_emd_matches_population():
    gj = json.loads((ROOT / "data_ext" / "jeju_emd.geojson").read_text(encoding="utf-8"))
    pop = json.loads((ROOT / "data_raw" / "floating_pop.json").read_text(encoding="utf-8"))
    assert {f["properties"]["emd"] for f in gj["features"]} == {x["emd"] for x in pop}
