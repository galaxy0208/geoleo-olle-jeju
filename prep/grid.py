import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import Point, shape
from shapely.ops import transform
from shapely.prepared import prep

TO_M = Transformer.from_crs(4326, 5179, always_xy=True)
TO_LL = Transformer.from_crs(5179, 4326, always_xy=True)


def node_index(G):
    nodes = list(G.nodes)
    ids = np.empty(len(nodes), dtype=object)
    ids[:] = nodes
    xs = np.array([G.nodes[n]["x"] for n in ids])
    ys = np.array([G.nodes[n]["y"] for n in ids])
    mx, my = TO_M.transform(xs, ys)
    return ids, cKDTree(np.column_stack([mx, my]))


def snap(lats, lons, ids, tree):
    mx, my = TO_M.transform(np.asarray(lons), np.asarray(lats))
    d, i = tree.query(np.column_stack([mx, my]))
    return ids[i], d


def _points(pm, spacing_m):
    pp = prep(pm)
    x0, y0, x1, y1 = pm.bounds
    xs = np.arange(x0 + spacing_m / 2, x1, spacing_m)
    ys = np.arange(y0 + spacing_m / 2, y1, spacing_m)
    return [(x, y) for x in xs for y in ys if pp.contains(Point(x, y))]


def make_grid(emd_shapes: dict, G, spacing_m=250, max_snap_m=100, min_points=30) -> pd.DataFrame:
    ids, tree = node_index(G)
    rows = []
    for emd, geom in emd_shapes.items():
        pm = transform(TO_M.transform, geom)
        sp = spacing_m
        pts = _points(pm, sp)
        while len(pts) < min_points and sp > spacing_m / 4:
            sp /= 2
            pts = _points(pm, sp)
        if not pts:
            c = pm.representative_point()
            pts = [(c.x, c.y)]
        arr = np.array(pts)
        lon, lat = TO_LL.transform(arr[:, 0], arr[:, 1])
        node, d = snap(lat, lon, ids, tree)
        for k in range(len(arr)):
            rows.append({"emd": emd, "lat": lat[k], "lon": lon[k], "node": node[k], "snap_m": float(d[k]), "spacing_m": sp})
    g = pd.DataFrame(rows)
    g = g[g.snap_m <= max_snap_m].reset_index(drop=True)
    g.insert(0, "grid_id", [f"g{i}" for i in range(len(g))])
    return g


def load_emd_shapes(path: Path) -> dict:
    gj = json.loads(Path(path).read_text(encoding="utf-8"))
    return {f["properties"]["emd"]: shape(f["geometry"]) for f in gj["features"]}


def main():
    from prep.osm_pbf import load_walk_graph

    root = Path(__file__).resolve().parent.parent
    G = load_walk_graph(root / "data_ext" / "jeju_walk.pkl")
    g = make_grid(load_emd_shapes(root / "data_ext" / "jeju_emd.geojson"), G)
    g.to_csv(root / "data" / "grid.csv", index=False, encoding="utf-8-sig")
    print(g.groupby("emd").size().sort_values().to_string())
    print(f"격자점 {len(g)}개")


if __name__ == "__main__":
    main()
