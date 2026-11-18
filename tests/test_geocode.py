import pandas as pd

from prep.geocode import run_geocode


class FakeResp:
    def __init__(self, docs):
        self._docs = docs

    def raise_for_status(self):
        pass

    def json(self):
        return {"documents": self._docs}


class FakeSession:
    def __init__(self, known):
        self.known = known
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        q = params["query"]
        return FakeResp([{"y": str(self.known[q][0]), "x": str(self.known[q][1])}] if q in self.known else [])


def sample_df():
    return pd.DataFrame([
        {"fac_id": "pharmacy_0", "category": "pharmacy", "name": "a", "address": "없는주소", "address_alt": "지번주소", "lat": None, "lon": None},
        {"fac_id": "bus_stop_1", "category": "bus_stop", "name": "b", "address": "", "address_alt": "", "lat": 33.5, "lon": 126.5},
    ])


def test_fallback_to_alt_address(tmp_path):
    s = FakeSession({"지번주소": (33.4, 126.4)})
    df = run_geocode(sample_df(), s, key="x", cache_path=tmp_path / "c.json", delay=0)
    assert df.loc[0, "geocode_status"] == "alt" and df.loc[0, "lat"] == 33.4


def test_bus_stop_skipped(tmp_path):
    s = FakeSession({})
    df = run_geocode(sample_df(), s, key="x", cache_path=tmp_path / "c.json", delay=0)
    assert df.loc[1, "geocode_status"] == "given"


def test_cache_prevents_second_call(tmp_path):
    s = FakeSession({"지번주소": (33.4, 126.4)})
    run_geocode(sample_df(), s, key="x", cache_path=tmp_path / "c.json", delay=0)
    run_geocode(sample_df(), s, key="x", cache_path=tmp_path / "c.json", delay=0)
    assert s.calls == 2


def test_fail_status(tmp_path):
    s = FakeSession({})
    df = run_geocode(sample_df(), s, key="x", cache_path=tmp_path / "c.json", delay=0)
    assert df.loc[0, "geocode_status"] == "fail"


from prep.geocode import clean_address


def test_clean_address():
    assert clean_address("제주특별자치도 제주시 중앙로 310, 1,2층 (이도이동)") == "제주특별자치도 제주시 중앙로 310"
    assert clean_address("제주특별자치도 제주시 신형로 2, 1~4층 (노형동)") == "제주특별자치도 제주시 신형로 2"


def test_keyword_fallback(tmp_path):
    class S(FakeSession):
        def get(self, url, params=None, headers=None, timeout=None):
            self.calls += 1
            if "keyword" in url:
                return FakeResp([{"y": "33.3", "x": "126.3", "address_name": "제주특별자치도 제주시", "place_name": "a"}])
            return FakeResp([])
    df = run_geocode(sample_df(), S({}), key="x", cache_path=tmp_path / "c.json", delay=0)
    assert df.loc[0, "geocode_status"] == "keyword"
