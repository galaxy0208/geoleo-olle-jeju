from app.agent import answer
from app.maps import color_for, make_map


def _geo():
    from shapely.geometry import box, mapping
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"emd": "가동"}, "geometry": mapping(box(126.5, 33.49, 126.51, 33.51))},
        {"type": "Feature", "properties": {"emd": "섬면"}, "geometry": mapping(box(126.29, 33.89, 126.31, 33.91))},
    ]}


def test_map_has_all_emd(store_fx):
    html = make_map(_geo(), answer("약국 접근성", store_fx))._repr_html_()
    import html as h
    raw = h.unescape(h.unescape(html))
    assert "가동" in raw and "섬면" in raw and "걸어서 걸리는 시간" in raw


def test_colors():
    assert color_for("reach_pct", 10) == "#DDF3EA" and color_for("reach_pct", 90) == "#0A5240"
    assert color_for("diff", 0) == "#ECEAE3" and color_for("diff", -10) == "#C4532A"
    assert color_for("reach_pct", None) == "#E8E6DF"


def test_minutes_colors():
    from app.maps import minutes_color
    assert minutes_color(3) == "#0A5240" and minutes_color(12) == "#7DCCAF"
    assert minutes_color(25) == "#DDF3EA" and minutes_color(float("inf")) == "#F2A07C" and minutes_color(45) == "#F2A07C"


def test_homes_map(store_fx):
    a = answer("가동 약국", store_fx)
    html = make_map(_geo(), a, store_fx.facilities).get_root().render()
    assert a.map_spec["type"] == "homes" and "걸어서 걸리는 시간" in html


def test_nearest_map(store_fx):
    a = answer("가동에서 가장 가까운 약국", store_fx)
    html = make_map(_geo(), a, store_fx.facilities).get_root().render()
    assert "기준 지점" in html
