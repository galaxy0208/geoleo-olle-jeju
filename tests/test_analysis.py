from app.analysis import compare_year, nearest, rank_gaps, reach_by_emd, simulate_new_facility, suggest_sites, trace


def test_threshold_math(store_fx):
    r = reach_by_emd(store_fx, "pharmacy", "adult", 5, emds=["가동"])
    assert r.iloc[0].reach_pct == 50.0


def test_speed_changes_reach(store_fx):
    a = reach_by_emd(store_fx, "pharmacy", "adult", 10).set_index("emd")
    s = reach_by_emd(store_fx, "pharmacy", "senior_aid", 5).set_index("emd")
    assert (s.reach_pct <= a.reach_pct).all()


def test_no_facility_zero_not_error(store_fx):
    r = reach_by_emd(store_fx, "pediatric", "child_guardian", 15, emds=["섬면"])
    assert r.iloc[0].reach_pct == 0.0


def test_rank_gaps_island_first(store_fx):
    assert rank_gaps(store_fx, "pharmacy", "senior", 15).iloc[0].emd == "섬면"


def test_compare_year_closed_pharmacy(store_fx):
    t = compare_year(store_fx, "pharmacy", "adult", 2, 2019, 0).set_index("emd")
    assert t.loc["가동", "reach_pct_from"] > t.loc["가동", "reach_pct_to"]


def test_nearest_minutes(store_fx):
    t = nearest(store_fx, "가동", "pharmacy", "adult")
    assert t.iloc[0]["name"] == "가동약국" and len(t) == 1


def test_simulate_and_suggest(store_fx):
    out = simulate_new_facility(store_fx, 4, "pharmacy", "adult", 5)
    assert out["new_reach_grid"] == 1
    assert suggest_sites(store_fx, "가동", "pharmacy", "adult", 5).iloc[0].gain_pct == 50.0


def test_trace_mentions_closed_and_geocode(store_fx):
    t = " ".join(trace(store_fx, "pharmacy", "adult", 15, 0))
    assert "폐업" in t and "좌표" in t and "1.0m/s" in t


def test_anchor_prefers_busy_stop_and_place(store_fx):
    from app.analysis import anchor
    assert "가동입구" in anchor(store_fx, "가동")[2]
    assert anchor(store_fx, "가동", "가리")[2].startswith("가리")
