from datetime import date

import networkx as nx
import numpy as np
import pandas as pd

from prep.distances import active_in_year, compute_nearest, nearest_dist


def line_graph():
    G = nx.Graph()
    for i in range(5):
        G.add_edge(i, i + 1, length=100)
    G.add_edge("island_a", "island_b", length=50)
    return G


def test_line_graph_distance():
    assert nearest_dist(line_graph(), [0])[3] == 300


def test_unreachable_is_inf():
    grid = pd.DataFrame({"grid_id": ["g0", "island_1"], "node": [2, "island_a"]})
    facs = pd.DataFrame({"category": ["pharmacy"], "node": [0], "is_open": [True], "open_date": [None], "close_date": [None]})
    out = compute_nearest(grid, facs, line_graph(), categories=["pharmacy"], years=[0])
    assert out.set_index("grid_id").dist_m["g0"] == 200
    assert np.isinf(out.set_index("grid_id").dist_m["island_1"])


def test_active_in_year():
    df = pd.DataFrame({
        "name": ["2018개업약국", "2020개업약국", "2018폐업약국"],
        "is_open": [True, True, False],
        "open_date": ["2018-01-01", "2020-03-01", "2010-01-01"],
        "close_date": [None, None, "2018-06-01"],
    })
    assert list(active_in_year(df, 2019).name) == ["2018개업약국"]
    assert list(active_in_year(df, 0).name) == ["2018개업약국", "2020개업약국"]
