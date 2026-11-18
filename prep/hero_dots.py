import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OPACITY = [0.62, 0.46, 0.33, 0.22, 0.1]
COLOR = "#1A8F6B"


def level(minutes: float) -> int:
    for i, edge in enumerate([5, 10, 15, 20]):
        if minutes <= edge:
            return i
    return 4


def build_svg(grid: pd.DataFrame, nearest: pd.DataFrame, category="pharmacy", step_m=500, width=1100,
              skip_emds=("추자면",)) -> str:
    g = grid[~grid.emd.isin(skip_emds)]
    n = nearest[(nearest.category == category) & (nearest.year == 0)][["grid_id", "dist_m"]]
    d = g.merge(n, on="grid_id", how="left")
    d["minutes"] = d.dist_m.fillna(np.inf) / 60
    lat0 = d.lat.mean()
    mx, my = 111320 * np.cos(np.radians(lat0)), 110540
    d["x"] = (d.lon - d.lon.min()) * mx
    d["y"] = (d.lat.max() - d.lat) * my
    d["cx"], d["cy"] = (d.x // step_m).astype(int), (d.y // step_m).astype(int)
    cells = d.groupby(["cx", "cy"]).minutes.min().reset_index()
    scale = width / ((cells.cx.max() + 1) * step_m)
    s = step_m * scale
    height = int((cells.cy.max() + 1) * s) + 1
    r = s * 0.28
    dots = "".join(
        f'<circle cx="{(c.cx + .5) * s:.1f}" cy="{(c.cy + .5) * s:.1f}" r="{r:.2f}" fill-opacity="{OPACITY[level(c.minutes)]}"/>'
        for c in cells.itertuples())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
            f'<g fill="{COLOR}">{dots}</g></svg>')


def main(root=ROOT):
    d = Path(root) / "data"
    grid = pd.read_csv(d / "grid.csv", encoding="utf-8-sig")
    nearest = pd.read_csv(d / "nearest.csv.gz")
    out = Path(root) / "app" / "static" / "jeju_dots.svg"
    out.write_text(build_svg(grid, nearest), encoding="utf-8")
    print(out, out.stat().st_size)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT)
