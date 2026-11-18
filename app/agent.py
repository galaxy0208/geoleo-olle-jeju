from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app import analysis as A
from app.llm import parse
from app.personas import CATEGORY_LABELS, PERSONAS
from app.query import Query, describe, josa
from app.related import related

SOURCES = {
    "pharmacy": "제주데이터허브 약국 정보 (LOCALDATA, 2025-09-18 기준)",
    "clinic": "제주데이터허브 병·의원 정보 (LOCALDATA, 2025-09 기준)",
    "hospital": "제주데이터허브 병·의원 정보 (LOCALDATA, 2025-09 기준)",
    "pediatric": "제주데이터허브 병·의원 정보 진료과목 (LOCALDATA, 2025-09 기준)",
    "dental": "제주데이터허브 병·의원 정보 (LOCALDATA, 2025-09 기준)",
    "public_health": "제주데이터허브 병·의원 정보 (LOCALDATA, 2025-09 기준)",
    "dementia": "제주데이터허브 제주 치매 안심 센터 위치 정보 (2021-11-23 기준)",
    "library": "제주데이터허브 제주 공공 도서관 정보, 제주 새마을문고 정보 (2021-11-23 기준)",
    "museum": "제주데이터허브 박물관 및 미술관 위치 정보 (카카오위치서비스, 2025-09-21 기준)",
    "bus_stop": "제주데이터허브 버스 정류소 기본 정보 (자동갱신)",
}
COMMON_SOURCES = [
    "제주데이터허브 읍면동 단위 내국인 유동인구 (2025-10-01~07 평균, 연령대별 거주인구)",
    "OpenStreetMap 보행 도로망 (Geofabrik 2026-11-14 추출, ODbL)",
    "읍면동 경계: vuski/admdongkor ver20250101",
    "주소 좌표 변환: 카카오 로컬 API",
]
LIMITS = [
    "경사와 계단은 반영하지 않았습니다. 언덕이 많은 곳은 실제로 더 걸립니다.",
    "아이 동반 보호자 속도(0.80m/s)는 측정 연구가 없어 보호구역 신호 기준을 가정했습니다.",
    "동네 중심은 읍면동 사무소(주민센터) 위치로 잡았습니다(OpenStreetMap). 추자면은 위치가 없어 버스 정류소가 가장 촘촘한 곳을 썼습니다.",
    "지도의 점에는 사람이 살지 않는 산간 도로도 들어 있습니다.",
    "8km 넘게 걸어야 하는 곳은 '걸어서 가기 어려움'으로 표시합니다.",
    "진료 시간, 휴무일은 데이터에 없어 반영하지 않았습니다.",
]


@dataclass
class Answer:
    query: Query
    table: pd.DataFrame | None = None
    summary: list = field(default_factory=list)
    explanation: str | None = None
    trace: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    limits: list = field(default_factory=list)
    related: list = field(default_factory=list)
    map_spec: dict | None = None
    message: str | None = None
    parsed_by: str = "rule"
    cards: list = field(default_factory=list)
    side: dict | None = None
    followups: list = field(default_factory=list)


def merge_followup(q: Query, prev: Query | None) -> Query:
    if prev is None or q.clarify:
        return q
    ex = q.explicit
    if ex.get("category"):
        return q
    if prev.category:
        q.category = prev.category
        q.categories = list(prev.categories or [prev.category])
        q.sgg = q.sgg or prev.sgg
        if q.intent == "unsupported" and ex.get("intent"):
            q.intent = ex["intent"]
        elif q.intent == "unsupported":
            q.intent = prev.intent if prev.intent != "compare_year" else "reach"
            q.year_from = prev.year_from
            q.top = prev.top
    if not ex.get("emds"):
        q.emds = prev.emds
        q.place = q.place or prev.place
    if not ex.get("persona"):
        q.persona = prev.persona
    if not ex.get("minutes"):
        q.minutes = prev.minutes
    if q.year and q.intent == "reach" and not ex.get("category"):
        q.intent, q.year_from, q.year = "compare_year", q.year, 0
    return q


def _apply_overrides(q: Query, ov: dict | None) -> Query:
    for k, v in (ov or {}).items():
        if v is not None and hasattr(q, k):
            setattr(q, k, v)
    if ov:
        q.clarify = None
        if q.category and q.intent == "unsupported":
            q.intent = "reach"
    return q


def _no_facility(store, q, emds):
    n = store.nearest
    n = n[(n.category == q.category) & (n.year == 0)]
    g = store.grid[store.grid.emd.isin(emds)]
    d = n[n.grid_id.isin(g.grid_id)].dist_m
    return len(d) == 0 or np.isinf(d).all()


def _rank_of(t: pd.DataFrame, emd: str) -> int:
    s = t.sort_values("reach_pct").reset_index(drop=True)
    return int(s.index[s.emd == emd][0]) + 1


def _scope(store, q: Query, t: pd.DataFrame) -> pd.DataFrame:
    if q.sgg and store.emd_sgg and not q.emds:
        return t[t.emd.map(store.emd_sgg) == q.sgg].reset_index(drop=True)
    return t


def run(store, q: Query) -> Answer:
    a = _run_one(store, q)
    extra = [c for c in (q.categories or []) if c != q.category]
    if extra and a.summary:
        for c in extra:
            q2 = Query(**{**q.to_dict(), "category": c, "categories": [c]})
            b = _run_one(store, q2)
            a.summary.append(f"[{CATEGORY_LABELS[c]}]")
            a.summary += b.summary if b.summary else [b.message or ""]
            a.sources = list(dict.fromkeys(a.sources + b.sources))
        a.trace.append("여러 시설을 물어서 시설마다 따로 계산했습니다. 지도와 표는 첫 번째 시설 기준입니다.")
    if q.sgg and not q.emds and q.intent in ("rank", "reach", "compare_year"):
        a.trace.append(f"{q.sgg} 읍면동만 대상으로 했습니다.")
    if q.hours_asked:
        note = "진료·영업 시간은 데이터에 없어 지금 문을 연 곳인지는 알 수 없습니다. 걸어서 닿는 곳만 보여드립니다."
        a.message = f"{a.message} {note}" if a.message else note
    return a


def _tm(d, persona):
    return A.fmt_time(d, persona)


def _sent(d, persona):
    t, m = A.fmt_time(d, persona)
    return "8km 안에 없어 걸어서 가기 어렵습니다." if t.startswith("걸어서") else f"걸어서 {t}, {m}입니다."


def _alt(persona):
    return "senior" if persona == "adult" else "adult"


def _table(rows, cols):
    return pd.DataFrame(rows, columns=cols)


def _emd_list(ct, persona, k=10):
    return [{"label": r.emd, "value": _tm(r.dist_m, persona)[0], "minutes": r.minutes} for r in ct.head(k).itertuples()]


def _scope_ct(store, q, ct):
    if q.sgg and store.emd_sgg and not q.emds:
        return ct[ct.emd.map(store.emd_sgg) == q.sgg].reset_index(drop=True)
    return ct


def _run_one(store, q: Query) -> Answer:
    a = Answer(query=q)
    if q.clarify:
        a.message = q.clarify
        return a
    if q.intent == "unsupported" or q.category is None:
        cats = ", ".join(CATEGORY_LABELS.values())
        where = q.place or (", ".join(q.emds) if q.emds else None)
        if where:
            a.message = f"{josa(where, '은/는')} 찾았지만, 물어보신 시설은 제주데이터허브 데이터에 없습니다. {where} 기준으로 볼 수 있는 시설: {cats}."
        else:
            a.message = f"이 도구는 제주데이터허브 데이터로 걸어서 생활 시설에 닿는 정도를 봅니다. 볼 수 있는 시설: {cats}."
        return a
    p, lab = PERSONAS[q.persona], CATEGORY_LABELS[q.category]
    alt = _alt(q.persona)
    a.trace = A.trace(store, q.category, q.persona, q.minutes, q.year_from or q.year)
    a.sources = [SOURCES[q.category]] + COMMON_SOURCES
    a.limits = LIMITS + [f"주소를 좌표로 바꾸지 못한 시설 {store.geocode_report.get('fail', 0)}건은 빠져 있습니다."]
    a.related = related(q.category, q.persona)

    if q.intent == "compare_year" and q.category not in A.TIME_CATEGORIES_WITH_HISTORY:
        a.message = f"{josa(lab, '은/는')} 과거 기록이 없어 예전과 비교할 수 없습니다. 지금 기준으로 보여 드립니다."
        q.intent, q.year_from = "reach", None

    if q.intent == "reach" and q.emds:
        ct = A.center_times(store, q.category, q.persona).set_index("emd")
        cen = A.emd_centers(store).set_index("emd")
        e = q.emds[0]
        c = ct.loc[e]
        fac = A.nearest_from(store, cen.loc[e].node, q.category, q.persona, n=5)
        homes = A.home_times(store, e, q.category, q.persona)
        f = store.facilities
        n_in = int(((f.category == q.category) & f.is_open.astype(bool) & f.address.fillna("").str.contains(e)).sum())
        t_c, d_c = _tm(c.dist_m, q.persona)
        a.cards = [
            {"label": f"{c.center}에서 가장 가까운 {lab}", "value": t_c,
             "sub": f"{fac.iloc[0]['name']} · {d_c}" if len(fac) else "8km 안에 없음"},
        ]
        if len(fac) > 1:
            a.cards.append({"label": "다음으로 가까운 곳", "value": _tm(fac.iloc[1].dist_m, q.persona)[0],
                            "sub": f"{fac.iloc[1]['name']} · {_tm(fac.iloc[1].dist_m, q.persona)[1]}"})
        a.cards.append({"label": f"{PERSONAS[alt].label} 걸음이면", "value": _tm(c.dist_m, alt)[0], "sub": f"{c.center}에서"})
        a.cards.append({"label": f"{e} 안 {lab}", "value": f"{n_in}곳", "sub": "주소 기준"})
        if len(fac):
            a.summary.append(f"{c.center}에서 가장 가까운 {josa(lab, '은/는')} {fac.iloc[0]['name']}입니다. {p.label} 걸음으로 {t_c}, {d_c}입니다.")
        else:
            a.summary.append(f"{c.center}에서 8km 안에 {josa(lab, '이/가')} 없습니다. 걸어서 가기 어렵습니다.")
        a.summary.append(f"지도의 점은 {e} 곳곳에서 가장 가까운 {lab}까지 걷는 시간입니다. 색이 옅을수록 멉니다.")
        for e2 in q.emds[1:]:
            a.summary.append(f"{ct.loc[e2].center}에서는 {_tm(ct.loc[e2].dist_m, q.persona)[0]}입니다.")
        a.side = {"title": f"{c.center}에서 가까운 {lab}", "rows": [{"label": r["name"], "value": _tm(r.dist_m, q.persona)[0], "minutes": r.minutes} for _, r in fac.iterrows()]}
        a.table = _table([[r["name"], r.address, *_tm(r.dist_m, q.persona)] for _, r in fac.iterrows()], ["시설명", "주소", "걸리는 시간", "걷는 거리"])
        a.map_spec = {"type": "homes", "emds": q.emds, "points": homes[["lat", "lon", "minutes"]].values.tolist(),
                      "facilities": fac[["name", "lat", "lon"]].values.tolist() if "lat" in fac else [],
                      "anchor": [cen.loc[e].lat, cen.loc[e].lon, c.center]}
    elif q.intent in ("reach", "rank"):
        ct = _scope_ct(store, q, A.center_times(store, q.category, q.persona))
        far1, near1 = ct.iloc[0], ct.iloc[-1]
        n30 = int((ct.minutes > 30).sum() + ct.minutes.isna().sum())
        a.cards = [
            {"label": f"{lab}까지 가장 먼 동네", "value": far1.emd, "sub": f"중심에서 {_tm(far1.dist_m, q.persona)[0]}"},
            {"label": f"{lab}까지 가장 가까운 동네", "value": near1.emd, "sub": f"중심에서 {_tm(near1.dist_m, q.persona)[0]}"},
            {"label": "중심에서 30분 넘게 걸리는 동네", "value": f"{n30}곳", "sub": f"{q.sgg or '제주'} {len(ct)}개 읍면동 중"},
        ]
        top = ct.head(q.top if q.intent == "rank" else 5)
        a.summary.append(f"{p.label} 걸음으로 {lab}까지 가장 오래 걸리는 동네는 " + ", ".join(f"{r.emd} {_tm(r.dist_m, q.persona)[0]}" if np.isfinite(r.dist_m) else f"{r.emd}(걸어서 가기 어려움)" for r in top.itertuples()) + "입니다.")
        a.summary.append("각 동네 읍면동 사무소(주민센터)에서 잰 시간입니다.")
        a.side = {"title": f"동네 중심에서 {lab}까지", "rows": _emd_list(ct, q.persona)}
        rows = top if q.intent == "rank" else ct
        a.table = _table([[r.emd, r.center, *_tm(r.dist_m, q.persona)] for r in rows.itertuples()], ["읍면동", "동네 중심", "걸리는 시간", "걷는 거리"])
        a.map_spec = {"type": "choropleth", "value": "minutes", "emds": top.emd.tolist() if q.intent == "rank" else [],
                      "values": dict(zip(ct.emd, ct.minutes))}
    elif q.intent == "nearest":
        if q.emds:
            emd = q.emds[0]
        else:
            st = store.stops
            cand = st[(st.ri == q.place) | st.stationName.fillna("").str.replace(" ", "").str.contains(q.place.replace(" ", ""), regex=False)]
            emd = cand.sort_values("users", ascending=False).emd.iloc[0]
        t = A.nearest(store, emd, q.category, q.persona, n=q.top if q.top <= 5 else 3, place=q.place)
        anc = t.attrs.get("anchor", emd)
        if t.empty:
            a.message = f"{anc}에서 5km 안에 {josa(lab, '이/가')} 없습니다."
        else:
            f0 = t.iloc[0]
            a.cards = [
                {"label": f"{anc}에서", "value": _tm(f0.dist_m, q.persona)[0], "sub": f"{f0['name']} · {_tm(f0.dist_m, q.persona)[1]}"},
                {"label": f"{PERSONAS[alt].label} 걸음이면", "value": _tm(f0.dist_m, alt)[0], "sub": f0["name"]},
            ]
            if len(t) > 1:
                f1 = t.iloc[1]
                a.cards.append({"label": "다음으로 가까운 곳", "value": _tm(f1.dist_m, q.persona)[0], "sub": f1["name"]})
            a.summary.append(f"{anc}에서 가장 가까운 {josa(lab, '은/는')} {f0['name']}입니다. {p.label} 걸음으로 {_tm(f0.dist_m, q.persona)[0]}, {_tm(f0.dist_m, q.persona)[1]}입니다.")
            a.side = {"title": f"가까운 {lab}", "rows": [{"label": r.name, "value": _tm(r.dist_m, q.persona)[0], "minutes": r.minutes} for r in t.itertuples()]}
            a.table = _table([[r.name, r.address, *_tm(r.dist_m, q.persona)] for r in t.itertuples()], ["시설명", "주소", "걸리는 시간", "걷는 거리"])
        a.map_spec = {"type": "nearest", "anchor": A.anchor(store, emd, q.place)[:2], "emds": [emd]}
    elif q.intent == "simulate":
        emd = q.emds[0]
        picks = A.suggest_sites(store, emd, q.category, q.persona, q.minutes)
        if picks.empty:
            a.message = f"{josa(emd, '은/는')} 이미 대부분의 집에서 {q.minutes}분 안에 {josa(lab, '이/가')} 있습니다."
            return a
        best = picks.iloc[0]
        extra = A.new_facility_field(store, best.node)
        field = A.dist_field(store, q.category)
        before = A.home_times(store, emd, q.category, q.persona)
        after = A.home_times(store, emd, q.category, q.persona, extra=extra)
        near_site = ((before.lat - best.lat) ** 2 + ((before.lon - best.lon) * 0.84) ** 2) ** 0.5 * 111000 <= 1000
        nb, na = before[near_site].dist_m.max(), after[near_site].dist_m.max()
        cen = A.emd_centers(store).set_index("emd").loc[emd]
        cb = field.get(cen.node, np.inf)
        ca = min(cb, extra.get(cen.node, np.inf))
        site = A.near_stop(store, best.lat, best.lon, emd)
        a.cards = [
            {"label": "새로 생길 후보 위치", "value": site.replace(" 근처", ""), "sub": "1순위"},
            {"label": "후보 위치 1km 안에서 가장 먼 곳", "value": f"{_tm(nb, q.persona)[0]} → {_tm(na, q.persona)[0]}", "sub": "지금 → 생기면"},
            {"label": f"동네 중심({cen.center})에서", "value": f"{_tm(cb, q.persona)[0]} → {_tm(ca, q.persona)[0]}", "sub": "지금 → 생기면"},
        ]
        a.summary.append(f"{emd}에 {josa(lab, '이/가')} 하나 생긴다면 {site}가 가장 많은 집을 가깝게 만듭니다.")
        a.summary.append(f"후보 위치 1km 안에서 가장 먼 곳이 지금 {_tm(nb, q.persona)[0]}인데, 생기면 {josa(_tm(na, q.persona)[0], '으로/로')} 줄어듭니다.")
        a.side = {"title": "후보 위치", "rows": [{"label": A.near_stop(store, r.lat, r.lon, emd), "value": f"{i + 1}순위", "minutes": None} for i, r in enumerate(picks.itertuples())]}
        a.table = _table([[i + 1, A.near_stop(store, r.lat, r.lon, emd)] for i, r in enumerate(picks.itertuples())], ["순위", "후보 위치"])
        a.map_spec = {"type": "simulate", "picks": picks[["lat", "lon"]].values.tolist(), "emds": [emd]}
    elif q.intent == "compare_year":
        if q.year_from >= 2025:
            q.year_from = 2024
            a.trace.append("시설 데이터가 2025년 9월 기준이라 2024년 말과 비교했습니다.")
        old = A.center_times(store, q.category, q.persona, year=q.year_from).set_index("emd")
        now = A.center_times(store, q.category, q.persona).set_index("emd")
        t = old[["center", "dist_m"]].join(now[["dist_m"]], lsuffix="_old", rsuffix="_now").reset_index()
        t = _scope_ct(store, q, t)
        t["diff"] = t.dist_m_now - t.dist_m_old
        if q.emds:
            r = t.set_index("emd").loc[q.emds[0]]
            to, tn = _tm(r.dist_m_old, q.persona)[0], _tm(r.dist_m_now, q.persona)[0]
            a.cards = [
                {"label": f"{q.year_from}년 말", "value": to, "sub": f"{q.emds[0]} 중심({r.center})에서"},
                {"label": "지금", "value": tn, "sub": f"가장 가까운 {lab}까지"},
            ]
            a.summary.append(f"{q.emds[0]} 중심에서 가장 가까운 {lab}까지 {q.year_from}년 말에는 {to}, 지금은 {tn}입니다.")
            show = t[t.emd.isin(q.emds)]
        else:
            worse = t[t["diff"] > 1].sort_values("diff", ascending=False)
            better = t[t["diff"] < -1]
            a.cards = [
                {"label": f"{q.year_from}년 말보다 멀어진 동네", "value": f"{len(worse)}곳", "sub": f"동네 중심에서 {lab}까지"},
                {"label": "가까워진 동네", "value": f"{len(better)}곳", "sub": f"동네 중심에서 {lab}까지"},
            ]
            if len(worse):
                a.summary.append("가장 많이 멀어진 곳: " + ", ".join(f"{r.emd} {_tm(r.dist_m_old, q.persona)[0]} → {_tm(r.dist_m_now, q.persona)[0]}" for r in worse.head(3).itertuples()))
            else:
                a.summary.append(f"{q.year_from}년 말보다 멀어진 동네는 없습니다.")
            show = worse if len(worse) else t
        a.table = _table([[r.emd, r.center, _tm(r.dist_m_old, q.persona)[0], _tm(r.dist_m_now, q.persona)[0]] for r in show.itertuples()],
                         ["읍면동", "동네 중심", f"{q.year_from}년 말", "지금"])
        a.map_spec = {"type": "choropleth", "value": "minutes", "emds": q.emds, "values": dict(zip(t.emd, (t.dist_m_now / p.speed / 60).round(0)))}
    return a


def followups(q: Query) -> list:
    if q.clarify or not q.category or q.intent == "unsupported":
        return []
    lab = CATEGORY_LABELS[q.category]
    out = ["일반 성인 걸음으로 하면?" if q.persona != "adult" else "어르신 걸음으로 하면?"]
    if q.intent != "rank":
        out.append("가장 불편한 동네는?")
    if q.emds and q.intent == "reach":
        out.append(f"{q.emds[0]}에 {josa(lab, '이/가')} 새로 생기면?")
    return out[:4]


def answer(text: str, store, llm=None, prev: Query | None = None, overrides: dict | None = None,
           default_persona: str | None = None) -> Answer:
    places = store.place_names
    if overrides and not text:
        q, src = Query(), "direct"
    else:
        q, src = parse(text, store.emds, llm, places)
        q = merge_followup(q, prev)
        if default_persona and not q.explicit.get("persona"):
            q.persona = default_persona
    q = _apply_overrides(q, overrides)
    a = run(store, q)
    a.parsed_by = src
    head = {"rule": "질문을 규칙 사전으로 해석했습니다", "llm": "질문을 로컬 LLM(Qwen)으로 해석했습니다", "direct": "조건을 직접 골랐습니다"}[src]
    a.trace = [f"{head}: {describe(q)}"] + a.trace
    if not a.message or a.table is not None:
        a.followups = followups(q)
    return a
