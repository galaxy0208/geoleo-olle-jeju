from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from prep.grid import TO_M
from prep.osm_pbf import BBOX


def read_buildings(path: Path, bbox=BBOX):
    import osmium

    s, w, n, e = bbox
    fp = osmium.FileProcessor(str(path)).with_locations().with_filter(osmium.filter.KeyFilter("building"))
    for obj in fp:
        if obj.is_node():
            la, lo = obj.location.lat, obj.location.lon
        elif obj.is_way():
            try:
                pts = [(nd.location.lat, nd.location.lon) for nd in obj.nodes]
            except Exception:
                continue
            la, lo = np.mean([p[0] for p in pts]), np.mean([p[1] for p in pts])
        else:
            continue
        if s <= la <= n and w <= lo <= e:
            yield la, lo


RES = {"residential", "living_street", "service"}


def read_res_nodes(path: Path, bbox=BBOX):
    from prep.osm_pbf import read_pbf

    seen = set()
    for tags, nodes in read_pbf(path, bbox):
        if tags.get("highway") in RES:
            for nid, la, lo in nodes:
                if nid not in seen:
                    seen.add(nid)
                    yield la, lo


def grid_weights(grid: pd.DataFrame, bld_latlon: np.ndarray) -> np.ndarray:
    gx, gy = TO_M.transform(grid.lon.values, grid.lat.values)
    bx, by = TO_M.transform(bld_latlon[:, 1], bld_latlon[:, 0])
    tree = cKDTree(np.column_stack([gx, gy]))
    _, idx = tree.query(np.column_stack([bx, by]))
    return np.bincount(idx, minlength=len(grid)).astype(float)


def main():
    root = Path(__file__).resolve().parent.parent
    pbf = sorted((root / "data_ext").glob("south-korea*.osm.pbf"))[-1]
    b = np.array(list(read_buildings(pbf)))
    grid = pd.read_csv(root / "data" / "grid.csv", encoding="utf-8-sig")
    grid["bld"] = grid_weights(grid, b)
    r = np.array(list(read_res_nodes(pbf)))
    grid["res"] = grid_weights(grid, r)
    pop = pd.read_csv(root / "data" / "emd_pop.csv", encoding="utf-8-sig").groupby("emd").resd_pop.sum()
    agg = grid.groupby("emd")[["bld", "res"]].sum().join(pop)
    print("인구와 상관", agg.corr(method="spearman").resd_pop.round(3).to_dict())
    grid.to_csv(root / "data" / "grid.csv", index=False, encoding="utf-8-sig")
    print(f"건물 {len(b)}개, 건물 있는 격자점 {(grid.bld > 0).mean():.0%}")
    print(grid.groupby("emd").bld.sum().sort_values().head(5).to_string())


if __name__ == "__main__":
    main()
