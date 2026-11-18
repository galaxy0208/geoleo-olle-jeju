import networkx as nx
import pandas as pd
from shapely.geometry import box

from prep.grid import make_grid
from prep.population import build_emd_pop, persona_pop


def small_graph():
    G = nx.Graph()
    for i in range(11):
        for j in range(11):
            G.add_node((i, j), y=33.5 + i * 0.001, x=126.5 + j * 0.0012)
    return G


def test_grid_spacing_and_snap():
    shapes = {"가동": box(126.5, 33.5, 126.512, 33.51), "먼동": box(126.6, 33.6, 126.601, 33.601)}
    g = make_grid(shapes, small_graph(), spacing_m=250, max_snap_m=100)
    assert (g.snap_m <= 100).all() and g.grid_id.is_unique
    assert set(g.emd) == {"가동"} and len(g) >= 9


def test_population_average_and_persona():
    rows = [
        {"baseDate": "1", "emd": "가동", "gender": "남", "ageGroup": "70대이상", "resdPop": 10},
        {"baseDate": "1", "emd": "가동", "gender": "여", "ageGroup": "70대이상", "resdPop": 20},
        {"baseDate": "2", "emd": "가동", "gender": "남", "ageGroup": "70대이상", "resdPop": 20},
        {"baseDate": "2", "emd": "가동", "gender": "여", "ageGroup": "70대이상", "resdPop": 20},
        {"baseDate": "1", "emd": "가동", "gender": "남", "ageGroup": "20대", "resdPop": 5},
        {"baseDate": "2", "emd": "가동", "gender": "남", "ageGroup": "20대", "resdPop": 5},
    ]
    pop = build_emd_pop(rows)
    assert persona_pop(pop, ["70대이상"])["가동"] == 35
