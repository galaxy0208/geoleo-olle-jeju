import networkx as nx
import numpy as np
import pandas as pd

from app.personas import CATEGORY_LABELS, PERSONAS, reach_m


def _weights(g: pd.DataFrame) -> pd.Series:
    w = g["res"].astype(float) if "res" in g else pd.Series(1.0, index=g.index)
    tot = w.groupby(g.emd).transform("sum")
    return w.where(tot > 0, 1.0)


def _persona_pop(store, persona: str) -> pd.Series:
    p = store.emd_pop
    return p[p.age_group.isin(PERSONAS[persona].age_groups)].groupby("emd").resd_pop.sum()


def _reach_table(store, category, persona, minutes, year):
    thr = reach_m(persona, minutes)
    n = store.nearest
    n = n[(n.category == category) & (n.year == year)][["grid_id", "dist_m"]]
    g = store.grid.merge(n, on="grid_id", how="left")
    g["dist_m"] = g.dist_m.fillna(np.inf)
    g["w"] = _weights(g)
    g["hit"] = g.dist_m <= thr
    agg = g.assign(hw=g.hit * g.w).groupby("emd").agg(grid_n=("grid_id", "size"), reach_n=("hit", "sum"), hw=("hw", "sum"), w=("w", "sum"))
    agg["reach_pct"] = (agg.hw / agg.w * 100).fillna(0).round(1)
    pop = _persona_pop(store, persona)
    agg["persona_pop"] = pop.reindex(agg.index).fillna(0)
    raw_gap = (1 - agg.reach_pct / 100) * agg.persona_pop
    agg["gap_index"] = (raw_gap / raw_gap.max() * 100).round(1) if raw_gap.max() > 0 else 0.0
    return agg.reset_index()[["emd", "grid_n", "reach_n", "reach_pct", "persona_pop", "gap_index"]]


def reach_by_emd(store, category, persona, minutes, year=0, emds=None) -> pd.DataFrame:
    t = _reach_table(store, category, persona, minutes, year)
    if emds:
        t = t[t.emd.isin(emds)]
    return t.sort_values("reach_pct").reset_index(drop=True)


def rank_gaps(store, category, persona, minutes, top=5, year=0) -> pd.DataFrame:
    t = _reach_table(store, category, persona, minutes, year)
    return t.sort_values("gap_index", ascending=False).head(top).reset_index(drop=True)


def compare_year(store, category, persona, minutes, year_from, year_to=0, emds=None) -> pd.DataFrame:
    a = _reach_table(store, category, persona, minutes, year_from)[["emd", "reach_pct"]]
    b = _reach_table(store, category, persona, minutes, year_to)[["emd", "reach_pct"]]
    t = a.merge(b, on="emd", suffixes=("_from", "_to"))
    t["diff"] = (t.reach_pct_to - t.reach_pct_from).round(1)
    if emds:
        t = t[t.emd.isin(emds)]
    return t.sort_values("diff").reset_index(drop=True)


def anchor(store, emd, place=None):
    from prep.grid import node_index, snap

    st = store.stops
    if st is not None and len(st):
        if place:
            pool = st[st.emd == emd] if emd and (st.emd == emd).any() else st
            m = pool[pool.ri.fillna("") == place]
            if m.empty:
                m = pool[pool.stationName.fillna("").str.replace(" ", "").str.contains(place.replace(" ", ""), regex=False)]
            if m.empty and pool is not st:
                m = st[st.stationName.fillna("").str.replace(" ", "").str.contains(place.replace(" ", ""), regex=False)]
            if not m.empty:
                r = m.sort_values("users", ascending=False).iloc[0]
                label = f"{r.stationName} 정류소" if place.replace(" ", "") in r.stationName.replace(" ", "") else f"{place} {r.stationName} 정류소"
                return r.lat, r.lon, label
    of = getattr(store, "offices", None)
    if of is not None and (of.emd == emd).any():
        r = of[of.emd == emd].iloc[0]
        return r.lat, r.lon, r.office
    if st is not None and len(st):
        m = st[st.emd == emd]
        if not m.empty:
            r = m.sort_values("users", ascending=False).iloc[0]
            return r.lat, r.lon, f"{emd}에서 이용객이 가장 많은 {r.stationName} 정류소"
    g = store.grid[store.grid.emd == emd]
    r = g.loc[_weights(g).idxmax()]
    return r.lat, r.lon, f"{emd} 주거 밀집 지점"


def _node_at(store, lat, lon):
    G = store.G
    best = min(G.nodes, key=lambda n: (G.nodes[n]["y"] - lat) ** 2 + (G.nodes[n]["x"] - lon) ** 2) if G.number_of_nodes() < 5000 else None
    if best is not None:
        return best
    from prep.grid import node_index, snap
    if not hasattr(store, "_nidx"):
        store._nidx = node_index(G)
    return snap([lat], [lon], *store._nidx)[0][0]


def nearest(store, emd, category, persona, n=3, cutoff=5000, place=None) -> pd.DataFrame:
    lat, lon, label = anchor(store, emd, place)
    src = _node_at(store, lat, lon)
    dist = nx.single_source_dijkstra_path_length(store.G, src, cutoff=cutoff, weight="length")
    f = store.facilities
    f = f[(f.category == category) & f.is_open.astype(bool)].copy()
    f["dist_m"] = f.node.map(dist)
    f = f[f.dist_m.notna()].sort_values("dist_m").drop_duplicates("name").head(n)
    f["minutes"] = (f.dist_m / PERSONAS[persona].speed / 60).round(1)
    out = f[["name", "address", "dist_m", "minutes"]].reset_index(drop=True)
    out.attrs["anchor"] = label
    return out


def simulate_new_facility(store, node, category, persona, minutes, emds=None) -> dict:
    thr = reach_m(persona, minutes)
    reached = nx.single_source_dijkstra_path_length(store.G, node, cutoff=thr, weight="length")
    n = store.nearest
    cur = n[(n.category == category) & (n.year == 0)].set_index("grid_id").dist_m
    g = store.grid.copy()
    g["cur"] = g.grid_id.map(cur).fillna(np.inf)
    g["w"] = _weights(g)
    g["before"] = g.cur <= thr
    g["after"] = g.before | g.node.isin(reached.keys())
    by = g.assign(bw=g.before * g.w, aw=g.after * g.w).groupby("emd")[["bw", "aw", "w"]].sum()
    by["before_pct"] = (by.bw / by.w * 100).round(1)
    by["after_pct"] = (by.aw / by.w * 100).round(1)
    by = by[by.after_pct > by.before_pct].reset_index()[["emd", "before_pct", "after_pct"]]
    if emds:
        by = by[by.emd.isin(emds)]
    return {"new_reach_grid": int((g.after & ~g.before).sum()), "by_emd": by.reset_index(drop=True)}


def suggest_sites(store, emd, category, persona, minutes, k=3, candidates=60) -> pd.DataFrame:
    thr = reach_m(persona, minutes)
    n = store.nearest
    cur = n[(n.category == category) & (n.year == 0)].set_index("grid_id").dist_m
    g = store.grid[store.grid.emd == emd].copy()
    g["cur"] = g.grid_id.map(cur).fillna(np.inf)
    g["w"] = _weights(g)
    miss = g[g.cur > thr]
    if miss.empty:
        return pd.DataFrame(columns=["lat", "lon", "node", "gain_pct"])
    total = g.w.sum()
    cands = miss.sort_values("w", ascending=False).head(candidates)
    covered, picks = set(), []
    reach = {r.node: set(nx.single_source_dijkstra_path_length(store.G, r.node, cutoff=thr, weight="length")) for r in cands.itertuples()}
    for _ in range(k):
        best, gain = None, 0.0
        for r in cands.itertuples():
            m = miss[miss.node.isin(reach[r.node]) & ~miss.grid_id.isin(covered)]
            gw = m.w.sum()
            if gw > gain:
                best, gain = r, gw
        if best is None:
            break
        covered |= set(miss[miss.node.isin(reach[best.node])].grid_id)
        picks.append({"lat": best.lat, "lon": best.lon, "node": best.node, "gain_pct": round(gain / total * 100, 1)})
    return pd.DataFrame(picks)


def trace(store, category, persona, minutes, year=0) -> list:
    fa = store.facilities_all[store.facilities_all.category == category]
    fs = store.facilities[store.facilities.category == category]
    p = PERSONAS[persona]
    lab = CATEGORY_LABELS[category]
    lines = [f"{lab} 원본 {len(fa)}건을 불러왔습니다."]
    if "is_open" in fa and (~fa.is_open.astype(bool)).any():
        lines.append(f"폐업·휴업 {int((~fa.is_open.astype(bool)).sum())}건을 현재 기준 계산에서 뺐습니다.")
    if "geocode_status" in fa:
        nf = int((fa.geocode_status == "fail").sum())
        if nf:
            lines.append(f"주소를 좌표로 바꾸지 못한 {nf}건은 제외했습니다.")
    far = len(fa) - len(fs) - (int((fa.geocode_status == "fail").sum()) if "geocode_status" in fa else 0)
    if far > 0:
        lines.append(f"도로망에서 300m 넘게 떨어진 {far}건은 제외했습니다.")
    if year:
        lines.append(f"{year}년 말에 영업 중이던 시설만 썼습니다 (인허가일, 폐업일 기준).")
    lines.append(f"{p.label} 보행속도 {p.speed}m/s로 걷는 시간을 계산했습니다.")
    lines.append("OpenStreetMap 보행 도로망을 따라 가장 짧은 길로 쟀습니다.")
    lines.append("동네 중심은 읍면동 사무소(주민센터)입니다. 지도의 점은 250m 간격 격자입니다.")
    return lines


def place_label(store, lat, lon) -> str:
    st = store.stops
    if st is None or st.empty:
        return f"{lat:.4f}, {lon:.4f}"
    d = (st.lat - lat) ** 2 + ((st.lon - lon) * 0.84) ** 2
    r = st.loc[d.idxmin()]
    m = (d.min() ** 0.5) * 111000
    ri = f"{r.ri}, " if isinstance(r.ri, str) and r.ri else ""
    return f"{ri}{r.stationName} 정류소 근처 ({m:.0f}m)"


CUTOFF_M = 8000
TIME_CATEGORIES_WITH_HISTORY = ("pharmacy", "clinic", "hospital", "pediatric", "dental", "public_health")


def _cache(store, name):
    c = store.__dict__.setdefault("_cache_" + name, {})
    return c


def dist_field(store, category, year=0) -> dict:
    c = _cache(store, "field")
    key = (category, year)
    if key not in c:
        from prep.distances import active_in_year
        f = store.facilities[store.facilities.category == category]
        f = active_in_year(f, year)
        src = [n for n in f.node.dropna().unique() if n in store.G]
        c[key] = nx.multi_source_dijkstra_path_length(store.G, src, cutoff=CUTOFF_M, weight="length") if src else {}
    return c[key]


def near_stop(store, lat, lon, emd=None) -> str:
    st = store.stops
    if st is not None and emd is not None:
        st = st[st.emd == emd]
    if st is None or st.empty:
        return f"{emd} 외곽" if emd else f"{lat:.3f}, {lon:.3f} 근처"
    d = (st.lat - lat) ** 2 + ((st.lon - lon) * 0.84) ** 2
    r = st.loc[d.idxmin()]
    name = str(r.stationName).split("(")[0].strip() or str(r.stationName)
    ri = f"{r.ri} " if isinstance(r.ri, str) and r.ri and r.ri not in name else ""
    return f"{ri}{name} 정류소 근처"


def _homes(store, emd) -> pd.DataFrame:
    g = store.grid[store.grid.emd == emd]
    if "res" in g and (g.res > 0).any():
        g = g[g.res > 0]
    return g


def _density(store) -> pd.Series:
    c = _cache(store, "density")
    if "d" not in c:
        from scipy.spatial import cKDTree
        from prep.grid import TO_M
        g, st = store.grid, store.stops
        x, y = TO_M.transform(g.lon.values, g.lat.values)
        tie = (g["bld"] if "bld" in g else g["res"] if "res" in g else pd.Series(0.0, index=g.index)).fillna(0).values * 1e-3
        if st is None or st.empty:
            c["d"] = pd.Series(tie, index=g.index)
        else:
            sx, sy = TO_M.transform(st.lon.values, st.lat.values)
            cnt = [len(v) for v in cKDTree(np.c_[sx, sy]).query_ball_point(np.c_[x, y], r=500)]
            c["d"] = pd.Series(np.asarray(cnt, dtype=float) + tie, index=g.index)
    return c["d"]


def emd_centers(store) -> pd.DataFrame:
    c = _cache(store, "centers")
    if "emd" not in c:
        dens = _density(store)
        of = getattr(store, "offices", None)
        rows = []
        for emd, g in store.grid.groupby("emd"):
            if of is not None and (of.emd == emd).any():
                o = of[of.emd == emd].iloc[0]
                rows.append({"emd": emd, "center": o.office, "lat": o.lat, "lon": o.lon, "node": _node_at(store, o.lat, o.lon)})
                continue
            r = g.loc[dens.loc[g.index].idxmax()]
            rows.append({"emd": emd, "center": near_stop(store, r.lat, r.lon, emd), "lat": r.lat, "lon": r.lon, "node": r.node})
        c["emd"] = pd.DataFrame(rows)
    return c["emd"]


def home_times(store, emd, category, persona, year=0, extra: dict | None = None) -> pd.DataFrame:
    field = dist_field(store, category, year)
    g = _homes(store, emd).copy()
    ex = extra or {}
    g["dist_m"] = g.node.map(lambda n: min(field.get(n, np.inf), ex.get(n, np.inf))).astype(float)
    g["minutes"] = (g.dist_m / PERSONAS[persona].speed / 60).round(0)
    return g[["grid_id", "lat", "lon", "node", "dist_m", "minutes"]].reset_index(drop=True)


def places_by_time(store, homes: pd.DataFrame, far=True, k=5, emd=None) -> pd.DataFrame:
    g = homes.sort_values("dist_m", ascending=not far).head(k * 8).copy()
    g["place"] = [near_stop(store, r.lat, r.lon, emd) for r in g.itertuples()]
    return g.drop_duplicates("place").head(k).reset_index(drop=True)[["place", "lat", "lon", "dist_m", "minutes"]]


def nearest_from(store, node, category, persona, year=0, n=3) -> pd.DataFrame:
    from prep.distances import active_in_year
    dist = nx.single_source_dijkstra_path_length(store.G, node, cutoff=CUTOFF_M, weight="length")
    f = active_in_year(store.facilities[store.facilities.category == category], year).copy()
    f["dist_m"] = f.node.map(dist)
    f = f[f.dist_m.notna()].sort_values("dist_m").drop_duplicates("name").head(n)
    f["minutes"] = (f.dist_m / PERSONAS[persona].speed / 60).round(0)
    return f[["name", "address", "lat", "lon", "dist_m", "minutes"]].reset_index(drop=True) if "lat" in f else f[["name", "address", "dist_m", "minutes"]].reset_index(drop=True)


def _timed(df, field, persona):
    out = df.copy()
    out["dist_m"] = out.node.map(lambda n: field.get(n, np.inf)).astype(float)
    out["minutes"] = (out.dist_m / PERSONAS[persona].speed / 60).round(0)
    return out


def center_times(store, category, persona, year=0) -> pd.DataFrame:
    t = _timed(emd_centers(store), dist_field(store, category, year), persona)
    return t.sort_values("dist_m", ascending=False).reset_index(drop=True)[["emd", "center", "dist_m", "minutes"]]


def new_facility_field(store, node) -> dict:
    return nx.single_source_dijkstra_path_length(store.G, node, cutoff=CUTOFF_M, weight="length")


def fmt_time(dist_m, persona) -> tuple:
    if dist_m is None or not np.isfinite(dist_m):
        return "걸어서 가기 어려움", f"{CUTOFF_M // 1000}km 안에 없음"
    m = max(1, int(round(dist_m / PERSONAS[persona].speed / 60)))
    d = f"{dist_m / 1000:.1f}km" if dist_m >= 1000 else f"{dist_m:.0f}m"
    return f"{m}분", d
