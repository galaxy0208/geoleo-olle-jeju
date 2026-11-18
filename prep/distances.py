import json
from datetime import date
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

CATEGORIES = ["pharmacy", "clinic", "hospital", "pediatric", "dental", "public_health", "dementia", "library", "bus_stop", "museum"]
YEARS = [0, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
CUTOFF_M = 2000.0
MAX_FAC_SNAP_M = 300.0


def nearest_dist(G, source_nodes, cutoff=CUTOFF_M) -> dict:
    src = [n for n in set(source_nodes) if n in G]
    if not src:
        return {}
    return nx.multi_source_dijkstra_path_length(G, src, cutoff=cutoff, weight="length")


def _d(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def active_in_year(df: pd.DataFrame, year: int) -> pd.DataFrame:
    if year == 0:
        return df[df.is_open.astype(bool)]
    end = date(year, 12, 31)
    od = df.open_date.map(_d)
    cd = df.close_date.map(_d)
    ok = [(o is None or o <= end) and (c is None or c > end) for o, c in zip(od, cd)]
    return df[pd.Series(ok, index=df.index, dtype=bool)]


def compute_nearest(grid: pd.DataFrame, facs: pd.DataFrame, G, categories=CATEGORIES, years=YEARS) -> pd.DataFrame:
    out = []
    for cat in categories:
        fc = facs[facs.category == cat]
        for y in years:
            act = active_in_year(fc, y)
            dist = nearest_dist(G, act.node.tolist())
            out.append(pd.DataFrame({
                "grid_id": grid.grid_id.values, "category": cat, "year": y,
                "dist_m": [dist.get(n, np.inf) for n in grid.node.values],
            }))
    return pd.concat(out, ignore_index=True)


def main():
    from prep.grid import node_index, snap
    from prep.osm_pbf import load_walk_graph

    root = Path(__file__).resolve().parent.parent
    G = load_walk_graph(root / "data_ext" / "jeju_walk.pkl")
    grid = pd.read_csv(root / "data" / "grid.csv", encoding="utf-8-sig")
    facs = pd.read_csv(root / "data" / "facilities.csv", encoding="utf-8-sig")
    facs = facs[facs.lat.notna()].copy()
    ids, tree = node_index(G)
    facs["node"], facs["snap_m"] = snap(facs.lat.values, facs.lon.values, ids, tree)
    far = facs[facs.snap_m > MAX_FAC_SNAP_M]
    facs = facs[facs.snap_m <= MAX_FAC_SNAP_M]
    facs.to_csv(root / "data" / "facilities_snapped.csv", index=False, encoding="utf-8-sig")
    res = compute_nearest(grid, facs, G)
    res.to_csv(root / "data" / "nearest.csv.gz", index=False)
    rep = {"far_from_network": int(len(far)), "far_names": far.name.tolist(), "used": int(len(facs)), "cutoff_m": CUTOFF_M}
    (root / "data" / "distance_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: v for k, v in rep.items() if k != "far_names"}, len(res))


if __name__ == "__main__":
    main()
