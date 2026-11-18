from prep.osm_pbf import build_graph, haversine


def test_haversine_100m():
    assert abs(haversine(33.5, 126.5, 33.5009, 126.5) - 100) < 1


def test_build_graph_filters():
    ways = [
        ({"highway": "footway"}, [(1, 33.5, 126.5), (2, 33.5009, 126.5)]),
        ({"highway": "motorway"}, [(3, 33.5, 126.6), (4, 33.51, 126.6)]),
        ({"highway": "residential", "foot": "no"}, [(5, 33.5, 126.7), (6, 33.51, 126.7)]),
        ({"highway": "residential"}, [(7, 35.0, 129.0), (8, 35.1, 129.0)]),
    ]
    G = build_graph(ways)
    assert set(G.nodes) == {1, 2}
    assert abs(G[1][2]["length"] - 100) < 1
