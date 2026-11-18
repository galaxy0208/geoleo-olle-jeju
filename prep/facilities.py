import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

HOSPITAL_RULES = {
    "clinic": {"의원"},
    "hospital": {"병원", "종합병원", "요양병원(일반요양병원)"},
    "dental": {"치과의원", "치과병원"},
    "public_health": {"보건소", "보건지소", "보건진료소"},
}
PEDIATRIC_TYPES = {"의원", "병원", "종합병원"}
COLUMNS = ["fac_id", "category", "name", "address", "address_alt", "lat", "lon", "open_date", "close_date", "is_open"]


def _load(raw_dir: Path, name: str) -> list:
    p = raw_dir / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _date(s):
    s = (s or "").strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def _addr(s):
    parts = (s or "").split()
    parts = [w for i, w in enumerate(parts) if i == 0 or w != parts[i - 1]]
    s = " ".join(parts)
    if not s:
        return ""
    return s if s.startswith("제주특별자치도") else f"제주특별자치도 {s}"


def _row(cat, name, doro, jibun, open_date=None, close_date=None, is_open=True, lat=None, lon=None):
    a, b = _addr(doro), _addr(jibun)
    return {
        "category": cat, "name": name, "address": a or b, "address_alt": b if a else "",
        "lat": lat, "lon": lon, "open_date": open_date, "close_date": close_date, "is_open": is_open,
    }


def build_facilities(raw_dir: Path) -> pd.DataFrame:
    raw_dir = Path(raw_dir)
    rows = []
    for x in _load(raw_dir, "pharmacy"):
        rows.append(_row("pharmacy", x["companyName"], x.get("addressDoro"), x.get("addressJibun"),
                         _date(x.get("licensingDate")), _date(x.get("closeDate")), x.get("openStatus") == "영업/정상"))
    for x in _load(raw_dir, "hospital"):
        t = x.get("bizSmallType") or ""
        subj = {s.strip() for s in (x.get("medicalSubject") or "").split(",")}
        cats = [c for c, types in HOSPITAL_RULES.items() if t in types]
        if "소아청소년과" in subj and t in PEDIATRIC_TYPES:
            cats.append("pediatric")
        for c in cats:
            rows.append(_row(c, x["companyName"], x.get("addressDoro"), x.get("addressJibun"),
                             _date(x.get("licensingDate")), _date(x.get("closeDate")), x.get("openStatus") == "영업/정상"))
    for x in _load(raw_dir, "library"):
        rows.append(_row("library", x["libraryName"], x.get("address"), "", _date(x.get("openDate"))))
    for x in _load(raw_dir, "small_library"):
        rows.append(_row("library", x["libraryName"], x.get("address"), ""))
    for x in _load(raw_dir, "museum"):
        rows.append(_row("museum", x["placeName"], x.get("addressDoro"), x.get("addressJibun"),
                         lat=float(x["latitude"]), lon=float(x["longitude"])))
    for x in _load(raw_dir, "dementia_center"):
        rows.append(_row("dementia", x["centerName"], x.get("address"), ""))
    for x in _load(raw_dir, "bus_station"):
        lat, lon = float(x["latitude"]), float(x["longitude"])
        if lat > lon:
            lat, lon = lon, lat
        r = _row("bus_stop", x["stationName"], "", x.get("stationAddress"), lat=lat, lon=lon)
        r["fac_key"] = x["stationId"]
        rows.append(r)
    df = pd.DataFrame(rows)
    df["fac_id"] = [f"{c}_{i}" for i, c in enumerate(df.category)]
    return df[COLUMNS]


def main():
    root = Path(__file__).resolve().parent.parent
    df = build_facilities(root / "data_raw")
    out = root / "data" / "facilities_raw.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(df.groupby(["category", "is_open"]).size().to_string())
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
