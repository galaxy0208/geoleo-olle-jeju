import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


def build_stops(stations: list, users: list, grid: pd.DataFrame) -> pd.DataFrame:
    s = pd.DataFrame(stations)
    s["lat"] = s.latitude.astype(float)
    s["lon"] = s.longitude.astype(float)
    sw = s.lat > s.lon
    s.loc[sw, ["lat", "lon"]] = s.loc[sw, ["lon", "lat"]].values
    u = pd.DataFrame(users)
    if len(u):
        u = u.groupby("stationName").userCount.sum()
        s["users"] = s.stationName.map(u).fillna(0)
    else:
        s["users"] = 0.0
    tree = cKDTree(np.column_stack([grid.lat.values, grid.lon.values]))
    _, i = tree.query(np.column_stack([s.lat.values, s.lon.values]))
    s["emd"] = grid.emd.values[i]
    s["node"] = grid.node.values[i]
    s["ri"] = s.stationAddress.fillna("").str.split().str[-1].where(lambda x: x.str.endswith(("리", "동")), "")
    return s[["stationId", "stationName", "stationAddress", "ri", "emd", "lat", "lon", "users"]]


def main():
    root = Path(__file__).resolve().parent.parent
    rd = lambda n: json.loads((root / "data_raw" / f"{n}.json").read_text(encoding="utf-8"))
    grid = pd.read_csv(root / "data" / "grid.csv", encoding="utf-8-sig")
    s = build_stops(rd("bus_station"), rd("bus_station_users"), grid)
    s.to_csv(root / "data" / "stops.csv", index=False, encoding="utf-8-sig")
    top = s.sort_values("users", ascending=False).groupby("emd").head(1)
    print(top[["emd", "stationName", "users"]].head(12).to_string())
    print("리 이름 수", s.ri.replace("", np.nan).nunique())


if __name__ == "__main__":
    main()
