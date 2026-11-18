import json
import time
from pathlib import Path

ENDPOINTS = [
    "https://overpass-api.de/api",
    "https://overpass.kumi.systems/api",
    "https://maps.mail.ru/osm/tools/overpass/api",
    "https://overpass.private.coffee/api",
]


def main():
    import osmnx as ox
    from shapely.geometry import shape
    from shapely.ops import unary_union

    root = Path(__file__).resolve().parent.parent
    gj = json.loads((root / "data_ext" / "jeju_emd.geojson").read_text(encoding="utf-8"))
    poly = unary_union([shape(f["geometry"]) for f in gj["features"]]).buffer(0.002)
    ox.settings.use_cache = True
    ox.settings.requests_timeout = 300
    ox.settings.max_query_area_size = 100_000_000
    out = root / "data_ext" / "jeju_walk.graphml"
    print("제주 보행망 다운로드 중. 10~20분 걸릴 수 있습니다.", flush=True)
    wait = 30
    for attempt in range(8):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        ox.settings.overpass_url = url
        print(f"[{attempt + 1}/8] {url}", flush=True)
        try:
            G = ox.graph_from_polygon(poly, network_type="walk", simplify=True, retain_all=True)
            ox.save_graphml(G, out)
            print(f"노드 {G.number_of_nodes()}, 엣지 {G.number_of_edges()}")
            print(f"저장: {out}")
            return
        except Exception as e:
            print(f"  실패: {str(e).splitlines()[0][:150]}", flush=True)
            if attempt % len(ENDPOINTS) == len(ENDPOINTS) - 1:
                print(f"  {wait}초 대기", flush=True)
                time.sleep(wait)
                wait *= 2
    raise SystemExit("모든 서버가 응답하지 않았습니다. 잠시 뒤 다시 실행해 주세요.")


if __name__ == "__main__":
    main()
