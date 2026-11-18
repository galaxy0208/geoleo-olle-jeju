import pandas as pd

from prep.hero_dots import build_svg, level


def test_level_edges():
    assert [level(m) for m in (3, 5, 9, 15, 20, 21, float("inf"))] == [0, 0, 1, 2, 3, 4, 4]


def test_build_svg_one_dot_per_cell():
    grid = pd.DataFrame({"grid_id": ["a", "b", "c", "d"], "emd": ["가동", "가동", "가동", "추자면"],
                         "lat": [33.5, 33.5001, 33.45, 33.9], "lon": [126.5, 126.5001, 126.6, 126.3]})
    near = pd.DataFrame({"grid_id": ["a", "b", "c"], "category": "pharmacy", "year": 0, "dist_m": [100, 1500, float("inf")]})
    svg = build_svg(grid, near)
    assert svg.startswith("<svg") and svg.count("<circle") == 2
    assert 'fill-opacity="0.62"' in svg and 'fill-opacity="0.1"' in svg
