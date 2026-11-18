import math
import pickle
from pathlib import Path

import networkx as nx

BBOX = (33.05, 126.05, 34.05, 127.0)
WALK = {
    "footway", "pedestrian", "path", "steps", "living_street", "residential", "service", "track",
    "unclassified", "tertiary", "tertiary_link", "secondary", "secondary_link", "primary", "primary_link",
    "trunk", "trunk_link", "road", "corridor", "crossing", "bridleway", "cycleway",
}
NO_FOOT = {"no", "private"}


def haversine(lat1, lon1, lat2, lon2):
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def walkable(tags: dict) -> bool:
    if tags.get("highway") not in WALK:
        return False
    if tags.get("foot") in NO_FOOT or tags.get("access") in NO_FOOT and tags.get("foot") not in {"yes", "designated"}:
        return False
    return tags.get("area") != "yes"


def build_graph(ways, bbox=BBOX) -> nx.Graph:
    s, w, n, e = bbox
    G = nx.Graph()
    for tags, nodes in ways:
        if not walkable(tags):
            continue
        pts = [(nid, lat, lon) for nid, lat, lon in nodes if s <= lat <= n and w <= lon <= e]
        for (a, la, lo), (b, lb, lob) in zip(pts, pts[1:]):
            if a == b:
                continue
            G.add_node(a, y=la, x=lo)
            G.add_node(b, y=lb, x=lob)
            d = haversine(la, lo, lb, lob)
            if not G.has_edge(a, b) or G[a][b]["length"] > d:
                G.add_edge(a, b, length=d)
    return G


def read_pbf(path: Path, bbox=BBOX):
    import osmium

    s, w, n, e = bbox
    fp = osmium.FileProcessor(str(path)).with_locations().with_filter(osmium.filter.KeyFilter("highway"))
    for obj in fp:
        if not obj.is_way():
            continue
        try:
            nodes = [(nd.ref, nd.location.lat, nd.location.lon) for nd in obj.nodes]
        except Exception:
            continue
        if not any(s <= la <= n and w <= lo <= e for _, la, lo in nodes):
            continue
        yield dict(obj.tags), nodes


def main():
    root = Path(__file__).resolve().parent.parent
    pbf = sorted((root / "data_ext").glob("south-korea*.osm.pbf"))[-1]
    G = build_graph(read_pbf(pbf))
    out = root / "data_ext" / "jeju_walk.pkl"
    with open(out, "wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
    comps = sorted((len(c) for c in nx.connected_components(G)), reverse=True)
    print(f"노드 {G.number_of_nodes()}, 엣지 {G.number_of_edges()}, 연결요소 상위 {comps[:5]}")
    print(f"저장: {out}")


def load_walk_graph(path: Path) -> nx.Graph:
    with open(path, "rb") as f:
        return pickle.load(f)


if __name__ == "__main__":
    main()
