import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
KEYS = ("주민센터", "읍사무소", "면사무소", "행정복지센터")
ALIAS = {"한림읍": ["한립읍사무소"]}


def scan_pbf(path) -> list:
    import osmium
    from osmium.geom import WKBFactory
    import shapely.wkb as wkb

    out, fab = [], WKBFactory()

    def keep(t):
        nm = t.get("name", "")
        return t.get("amenity") == "townhall" or any(k in nm for k in KEYS)

    class H(osmium.SimpleHandler):
        def node(self, n):
            if n.tags and keep(n.tags):
                out.append({"name": n.tags.get("name", ""), "lat": n.location.lat, "lon": n.location.lon})

        def area(self, a):
            if keep(a.tags):
                try:
                    c = wkb.loads(fab.create_multipolygon(a), hex=True).centroid
                    out.append({"name": a.tags.get("name", ""), "lat": c.y, "lon": c.x})
                except Exception:
                    pass

    H().apply_file(str(path), locations=True)
    return [o for o in out if 33.0 < o["lat"] < 33.7 and 126.1 < o["lon"] < 127.0]


def match(emds, halls: pd.DataFrame) -> pd.DataFrame:
    h = halls.assign(key=halls.name.str.replace(" ", ""))
    h = h[~h.key.str.contains(r"\(|앞|옆|사거리|주차장", regex=True)]
    rows = []
    for emd in emds:
        names = ALIAS.get(emd, []) + [emd + k for k in ("사무소", "주민센터", "행정복지센터")]
        m = h[h.key.isin(names)]
        if len(m):
            r = m.iloc[0]
            rows.append({"emd": emd, "office": names[-3] if emd in ALIAS else r["name"], "lat": r.lat, "lon": r.lon})
    return pd.DataFrame(rows, columns=["emd", "office", "lat", "lon"])


def main(root=ROOT):
    root = Path(root)
    halls = pd.DataFrame(scan_pbf(next((root / "data_ext").glob("*.osm.pbf"))))
    emds = [f["properties"]["emd"] for f in json.loads((root / "data_ext" / "jeju_emd.geojson").read_text(encoding="utf-8"))["features"]]
    out = match(emds, halls)
    out.to_csv(root / "data" / "emd_office.csv", index=False, encoding="utf-8-sig")
    print(f"{len(out)}/{len(emds)}", sorted(set(emds) - set(out.emd)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT)
