import pytest

from app.query import rule_parse

EMDS = ["한림읍", "애월읍", "연동", "노형동", "표선면", "가동", "섬면"]


@pytest.mark.parametrize("text,cat,persona,mins,intent", [
    ("한림읍 어르신 걸어서 약국 몇 퍼센트", "pharmacy", "senior", 15, "reach"),
    ("아이랑 10분 안에 소아과 갈 수 있는 동네", "pediatric", "child_guardian", 10, "reach"),
    ("의원 접근 제일 나쁜 동네 5곳", "clinic", "adult", 15, "rank"),
    ("휠체어 타는 어르신 기준 버스정류소", "bus_stop", "senior_aid", 15, "reach"),
    ("2019년이랑 비교하면 약국", "pharmacy", "adult", 15, "compare_year"),
    ("오늘 날씨 어때", None, "adult", 15, "unsupported"),
    ("한림 가까운 치과 어디야", "dental", "adult", 15, "nearest"),
    ("애월읍에 약국이 새로 생기면 어디가 좋아", "pharmacy", "adult", 15, "simulate"),
    ("치과의원 12분", "dental", "adult", 10, "reach"),
])
def test_rule_parse(text, cat, persona, mins, intent):
    q = rule_parse(text, EMDS)
    assert (q.category, q.persona, q.minutes, q.intent) == (cat, persona, mins, intent)


def test_emd_stem():
    assert rule_parse("한림 약국", EMDS).emds == ["한림읍"]


def test_hospital_asks_clarify():
    q = rule_parse("병원 가까운 동네", EMDS)
    assert q.clarify is not None and q.category is None


def test_top_n_and_year_clip():
    q = rule_parse("약국 가장 불편한 3곳", EMDS)
    assert q.top == 3
    assert rule_parse("2015년이랑 비교 약국", EMDS).year_from == 2019


def test_place_from_ri():
    q = rule_parse("표선면 세화리 약국 가까운 곳", EMDS, place_names=["세화리", "동명리"])
    assert q.place == "세화리" and q.emds == ["표선면"]


def test_josa():
    from app.query import josa
    assert josa("한림읍", "은/는") == "한림읍은" and josa("연동", "은/는") == "연동은"
    assert josa("약국", "이/가") == "약국이" and josa("치과", "이/가") == "치과가"


def test_mot_ganeun_is_rank():
    assert rule_parse("소아과 못 가는 동네 3곳", EMDS).intent == "rank"


def test_multi_category_and_scope():
    q = rule_parse("서귀포 동네 중 거동 불편하신 분 치과나 의원 가기 제일 사각지대", EMDS)
    assert q.categories == ["dental", "clinic"] and q.sgg == "서귀포시" and q.persona == "senior_aid" and q.intent == "rank"


def test_pediatric_clinic_word_not_clinic():
    assert rule_parse("소아청소년과의원 접근성", EMDS).categories == ["pediatric"]


def test_old_means_compare_and_book_means_library():
    assert rule_parse("한림읍은 예전이랑 비교했을 때 약국 나아졌나요", EMDS).intent == "compare_year"
    q = rule_parse("연동에서 책 빌려볼 수 있는 데가 제일 가깝나요", EMDS)
    assert q.category == "library" and q.intent == "nearest"


def test_hours_flag():
    assert rule_parse("애월읍 소아과 오늘 문 연 곳 알려주세요", EMDS).hours_asked


def test_landmark_place_last_mentioned():
    places = ["이스트소프트", "제주시청", "세화리"]
    q = rule_parse("이스트 소프트에서 제주시청까지 갈 일이 있는데, 거기서 가장 가까운 약국을 찾아줘", EMDS, places)
    assert q.place == "제주시청" and q.intent == "nearest" and q.clarify is None


def test_museum_and_small_library():
    assert rule_parse("한림읍 박물관 걸어서", EMDS).category == "museum"
    assert rule_parse("연동 새마을문고 가까운 곳", EMDS).category == "library"
