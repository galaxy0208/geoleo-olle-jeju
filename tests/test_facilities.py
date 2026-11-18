from datetime import date

from prep.facilities import build_facilities


def test_pediatric_split(raw_dir_fixture):
    df = build_facilities(raw_dir_fixture)
    rows = df[df.name == "튼튼소아과의원"]
    assert set(rows.category) == {"clinic", "pediatric"}


def test_closed_kept_with_dates(raw_dir_fixture):
    df = build_facilities(raw_dir_fixture)
    r = df[df.name == "안성약국"].iloc[0]
    assert r.is_open == False and r.close_date == date(2020, 1, 23)


def test_bus_stop_has_coords(raw_dir_fixture):
    df = build_facilities(raw_dir_fixture)
    assert df[df.category == "bus_stop"].lat.notna().all()


def test_address_fallback_and_prefix(raw_dir_fixture):
    df = build_facilities(raw_dir_fixture)
    assert df[df.name == "새별약국"].iloc[0].address.startswith("제주특별자치도 제주시 한림읍")
    assert df[df.category == "library"].iloc[0].address == "제주특별자치도 제주시 연오로 140"


def test_categories(raw_dir_fixture):
    df = build_facilities(raw_dir_fixture)
    assert {"pharmacy", "clinic", "pediatric", "dental", "public_health", "bus_stop", "library", "dementia"} <= set(df.category)
    assert df.fac_id.is_unique


def test_swapped_bus_coords(raw_dir_fixture):
    import json
    p = raw_dir_fixture / "bus_station.json"
    rows = json.loads(p.read_text(encoding="utf-8"))
    rows.append({"stationId": "3", "stationName": "뒤바뀜", "latitude": "126.5", "longitude": "33.4", "stationAddress": ""})
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    r = build_facilities(raw_dir_fixture).query("name == '뒤바뀜'").iloc[0]
    assert r.lat == 33.4 and r.lon == 126.5
