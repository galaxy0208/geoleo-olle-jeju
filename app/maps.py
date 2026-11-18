import json
from pathlib import Path

import folium

TEAL = ["#DDF3EA", "#7DCCAF", "#1A8F6B", "#0A5240"]
GAP = ["#FBE3D6", "#F2A07C", "#D85A30", "#8A3418"]
DIVERGE = {-2: "#C4532A", -1: "#EE9C78", 0: "#ECEAE3", 1: "#6FC6A5", 2: "#0F6E56"}
NO_DATA = "#E8E6DF"
INK = "#2C2C2A"
PAPER = "#FAFAF7"
FONT = "Pretendard, 'Noto Sans KR', 'Malgun Gothic', sans-serif"
CENTER = (33.38, 126.55)


def _bin(v, edges):
    for i, e in enumerate(edges):
        if v <= e:
            return i
    return len(edges)


MIN_COLORS = ["#0A5240", "#1A8F6B", "#7DCCAF", "#DDF3EA", "#F2A07C"]


def minutes_color(v) -> str:
    if v is None or v != v or v == float("inf"):
        return MIN_COLORS[4]
    return MIN_COLORS[_bin(v, [5, 10, 15, 30])]


def color_for(value_kind: str, v) -> str:
    if value_kind == "minutes":
        return minutes_color(v)
    if v is None or v != v:
        return NO_DATA
    if value_kind == "reach_pct":
        return TEAL[_bin(v, [25, 50, 75])]
    if value_kind == "gap_index":
        return GAP[_bin(v, [25, 50, 75])]
    if value_kind == "diff":
        return DIVERGE[-2 if v <= -5 else -1 if v < -0.05 else 0 if v <= 0.05 else 1 if v < 5 else 2]
    return NO_DATA


LEGENDS = {
    "minutes": [("5분 안", MIN_COLORS[0]), ("10분 안", MIN_COLORS[1]), ("15분 안", MIN_COLORS[2]), ("30분 안", MIN_COLORS[3]), ("30분 넘음", MIN_COLORS[4])],
    "reach_pct": [("0~25%", TEAL[0]), ("25~50%", TEAL[1]), ("50~75%", TEAL[2]), ("75~100%", TEAL[3])],
    "gap_index": [("0~25", GAP[0]), ("25~50", GAP[1]), ("50~75", GAP[2]), ("75~100", GAP[3])],
    "diff": [("5%p 이상 감소", DIVERGE[-2]), ("감소", DIVERGE[-1]), ("변화 없음", DIVERGE[0]), ("증가", DIVERGE[1]), ("5%p 이상 증가", DIVERGE[2])],
}
TITLES = {"minutes": "걸어서 걸리는 시간", "reach_pct": "걸어서 닿는 비율", "gap_index": "취약 지수 (높을수록 불편)", "diff": "과거 대비 변화"}


BASE_CSS = (f"<style>.leaflet-interactive:focus,path:focus{{outline:none}}.leaflet-tile-pane{{filter:grayscale(1) brightness(1.06) contrast(.92);opacity:.5}}"
            f".leaflet-container{{background:{PAPER};font-family:{FONT}}}"
            f".leaflet-tooltip{{font-family:{FONT};font-size:13px;border-radius:8px;border:1px solid #E3E1DA;box-shadow:none}}"
            f".leaflet-bar a{{border-radius:8px!important}}.leaflet-bar{{border:1px solid #D3D1C7!important;box-shadow:none!important;border-radius:10px}}</style>")


def _legend_html(kind: str) -> str:
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0">'
        f'<span style="width:12px;height:12px;border-radius:3px;background:{c};display:inline-block"></span>{l}</div>'
        for l, c in LEGENDS[kind])
    return (f'<div style="position:fixed;top:12px;right:12px;z-index:9999;background:#FFFFFF;padding:12px 14px;'
            f'border-radius:14px;font:13px {FONT};color:{INK};border:1px solid #E3E1DA">'
            f'<div style="font-weight:600;margin-bottom:6px">{TITLES[kind]}</div>{rows}</div>')


def load_geojson(root: Path) -> dict:
    return json.loads((Path(root) / "data_ext" / "jeju_emd.geojson").read_text(encoding="utf-8"))


def make_map(geojson: dict, answer, facilities=None) -> folium.Map:
    spec = answer.map_spec or {}
    kind = spec.get("value")
    m = folium.Map(location=CENTER, zoom_start=10, tiles="OpenStreetMap", control_scale=True)
    values = dict(spec.get("values") or {})
    if not values and answer.table is not None and kind and kind in answer.table:
        values = dict(zip(answer.table.emd, answer.table[kind]))
    focus = set(spec.get("emds") or [])
    bg = 0.06 if spec.get("type") == "homes" else 0.35
    for f in geojson["features"]:
        emd = f["properties"]["emd"]
        v = values.get(emd)
        fill = color_for(kind, v) if kind else NO_DATA
        if kind == "minutes":
            tip = emd if v is None else (f"{emd}: {int(v)}분" if v == v and v != float("inf") else f"{emd}: 걸어서 가기 어려움")
        else:
            tip = emd if v is None else f"{emd}: {v}"
        folium.GeoJson(
            f, tooltip=tip,
            style_function=lambda _, fill=fill, hot=emd in focus: {
                "fillColor": fill, "fillOpacity": 0.85 if fill != NO_DATA else bg,
                "color": INK if hot else "#FFFFFF", "weight": 2.5 if hot else 1,
            },
        ).add_to(m)
    t = spec.get("type")
    if t == "homes":
        pts = spec.get("points") or []
        for lat, lon, mins in pts:
            folium.CircleMarker((lat, lon), radius=3, stroke=False, fill=True, fill_color=minutes_color(mins), fill_opacity=0.9,
                                tooltip=f"{int(mins)}분" if mins == mins and mins != float("inf") else "30분 넘음").add_to(m)
        for name, lat, lon in spec.get("facilities") or []:
            folium.CircleMarker((lat, lon), radius=7, color="#FFFFFF", weight=2, fill=True, fill_color=INK, fill_opacity=1,
                                tooltip=name).add_to(m)
        if spec.get("anchor"):
            lat, lon, name = spec["anchor"]
            folium.Marker((lat, lon), tooltip=name, icon=folium.DivIcon(html='<div style="width:14px;height:14px;border-radius:7px;background:#FFFFFF;border:3px solid #2C2C2A"></div>')).add_to(m)
        if pts:
            la, lo = [p[0] for p in pts], [p[1] for p in pts]
            m.fit_bounds([[min(la), min(lo)], [max(la), max(lo)]])
        kind = "minutes"
    if t == "nearest" and spec.get("anchor"):
        lat, lon = spec["anchor"]
        folium.CircleMarker((lat, lon), radius=8, color="#FFFFFF", weight=2, fill=True, fill_color=INK,
                            fill_opacity=1, tooltip="기준 지점").add_to(m)
        if facilities is not None and answer.table is not None and len(answer.table):
            names = answer.table["시설명"] if "시설명" in answer.table else answer.table.get("name", [])
            fs = facilities[facilities.name.isin(list(names)) & (facilities.category == answer.query.category)]
            for r in (fs.drop_duplicates("name").itertuples() if "lat" in fs else []):
                folium.CircleMarker((r.lat, r.lon), radius=7, color="#FFFFFF", weight=2, fill=True,
                                    fill_color="#1A8F6B", fill_opacity=1, tooltip=r.name).add_to(m)
        m.location = [lat, lon]
        m.options["zoom"] = 13
    if t == "simulate":
        for i, (lat, lon) in enumerate(spec.get("picks", [])):
            folium.Marker((lat, lon), tooltip=f"후보 {i + 1}",
                          icon=folium.DivIcon(html=f'<div style="width:24px;height:24px;border-radius:12px;background:#2C2C2A;'
                                                   f'color:#FFFFFF;font:600 12px sans-serif;display:flex;align-items:center;'
                                                   f'justify-content:center;border:2px solid #FFFFFF">{i + 1}</div>')).add_to(m)
        if spec.get("picks"):
            m.location = list(spec["picks"][0])
            m.options["zoom"] = 12
    m.get_root().header.add_child(folium.Element(BASE_CSS))
    if kind in LEGENDS:
        m.get_root().html.add_child(folium.Element(_legend_html(kind)))
    return m
