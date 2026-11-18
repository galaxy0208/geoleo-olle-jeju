import json
import pytest


def _w(d, name, rows):
    (d / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def raw_dir_fixture(tmp_path):
    d = tmp_path / "data_raw"
    d.mkdir()
    _w(d, "pharmacy", [
        {"companyName": "안성약국", "openStatus": "폐업", "licensingDate": "20190128", "closeDate": "20200123",
         "addressJibun": "제주특별자치도 제주시 건입동 940번지", "addressDoro": "제주특별자치도 제주시 연무정길 28 (건입동)"},
        {"companyName": "새별약국", "openStatus": "영업/정상", "licensingDate": "20190213", "closeDate": "",
         "addressJibun": "제주특별자치도 제주시 한림읍 동명리 1601번지", "addressDoro": ""},
    ])
    _w(d, "hospital", [
        {"companyName": "튼튼소아과의원", "openStatus": "영업/정상", "bizSmallType": "의원", "licensingDate": "20150101",
         "closeDate": "", "medicalSubject": "소아청소년과, 내과", "addressDoro": "제주특별자치도 제주시 노형로 1", "addressJibun": ""},
        {"companyName": "미소치과의원", "openStatus": "영업/정상", "bizSmallType": "치과의원", "licensingDate": "20100101",
         "closeDate": "", "medicalSubject": "치과", "addressDoro": "제주특별자치도 제주시 연동 1", "addressJibun": ""},
        {"companyName": "고산보건진료소", "openStatus": "영업/정상", "bizSmallType": "보건진료소", "licensingDate": "20000101",
         "closeDate": "", "medicalSubject": "", "addressDoro": "제주특별자치도 제주시 한경면 고산로 1", "addressJibun": ""},
    ])
    _w(d, "bus_station", [
        {"stationId": "1", "stationName": "한국병원", "latitude": "33.500054", "longitude": "126.518076", "stationAddress": "제주시 삼도1동"},
        {"stationId": "2", "stationName": "구판장", "latitude": "33.329732", "longitude": "126.797879", "stationAddress": "서귀포시 표선면"},
    ])
    _w(d, "library", [{"libraryName": "제주꿈바당어린이도서관", "address": "제주시 연오로 140", "openDate": "20171014"}])
    _w(d, "dementia_center", [{"centerName": "제주시치매안심센터", "address": "제주특별자치도 제주시 도남동 연삼로 264"}])
    return d


@pytest.fixture
def store_fx():
    import networkx as nx
    import pandas as pd

    from app.store import Store
    from prep.distances import compute_nearest

    G = nx.Graph()
    for i in range(5):
        G.add_node(i, y=33.5, x=126.5 + i * 0.001)
    for i in range(4):
        G.add_edge(i, i + 1, length=100)
    G.add_node("i0", y=33.9, x=126.3)
    G.add_node("i1", y=33.9, x=126.301)
    G.add_edge("i0", "i1", length=50)
    grid = pd.DataFrame({
        "grid_id": ["g0", "g1", "g2"], "emd": ["가동", "가동", "섬면"],
        "lat": [33.5, 33.5, 33.9], "lon": [126.5, 126.504, 126.3], "node": [0, 4, "i0"], "res": [1.0, 1.0, 1.0],
    })
    fac = pd.DataFrame([
        {"fac_id": "p0", "category": "pharmacy", "name": "가동약국", "address": "가동 1", "node": 0, "is_open": True,
         "open_date": "2010-01-01", "close_date": None, "geocode_status": "ok"},
        {"fac_id": "p1", "category": "pharmacy", "name": "폐업약국", "address": "가동 3", "node": 3, "is_open": False,
         "open_date": "2015-01-01", "close_date": "2020-06-01", "geocode_status": "ok"},
    ])
    fac_all = pd.concat([fac, pd.DataFrame([{"fac_id": "p2", "category": "pharmacy", "name": "좌표실패약국", "is_open": True,
                                              "geocode_status": "fail"}])], ignore_index=True)
    near = compute_nearest(grid, fac, G, categories=["pharmacy", "pediatric"], years=[0, 2019])
    pop = pd.DataFrame({"emd": ["가동", "가동", "섬면", "섬면"], "age_group": ["20대", "70대이상", "70대이상", "10세미만"],
                        "resd_pop": [10.0, 10.0, 10.0, 5.0]})
    s = Store(grid=grid, nearest=near, facilities=fac, facilities_all=fac_all, emd_pop=pop,
              geocode_report={"fail": 1}, distance_report={"far_from_network": 0},
              stops=pd.DataFrame({"stationName": ["가동입구", "가동끝"], "ri": ["가리", ""], "emd": ["가동", "가동"],
                                  "lat": [33.5, 33.5], "lon": [126.5, 126.504], "users": [10.0, 1.0]}))
    s._G = G
    return s
