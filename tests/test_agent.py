from app.agent import answer


def test_followup_keeps_category(store_fx):
    a1 = answer("가동 약국 접근성", store_fx)
    a2 = answer("어르신 걸음으로 하면?", store_fx, prev=a1.query)
    assert a2.query.category == "pharmacy" and a2.query.persona == "senior" and a2.query.emds == ["가동"]


def test_unsupported_has_message(store_fx):
    a = answer("오늘 날씨 어때", store_fx)
    assert a.table is None and a.message


def test_trace_reports_geocode_fail(store_fx):
    a = answer("가동 약국 접근성", store_fx)
    assert any("좌표" in t for t in a.trace) and a.summary


def test_zero_facility_message(store_fx):
    a = answer("섬면 소아과", store_fx)
    assert any("없습니다" in s for s in a.summary)


def test_rank_and_compare(store_fx):
    assert len(answer("약국 가장 불편한 2곳", store_fx).table) == 2
    a = answer("2019년이랑 비교하면 가동 약국 2분", store_fx)
    assert a.query.intent == "compare_year" and "2019" in a.summary[0]


def test_followup_last_year(store_fx):
    a1 = answer("가동 약국 접근성", store_fx)
    a2 = answer("작년엔?", store_fx, prev=a1.query)
    assert a2.query.intent == "compare_year" and a2.query.year_from == 2024


def test_direct_overrides(store_fx):
    a = answer("", store_fx, overrides={"category": "pharmacy", "persona": "senior", "minutes": 10, "emds": ["가동"]})
    assert a.parsed_by == "direct" and a.table is not None


def test_simulate(store_fx):
    a = answer("가동에 약국이 새로 생기면 5분", store_fx)
    assert a.query.intent == "simulate" and a.map_spec["type"] == "simulate"


def test_new_category_resets_followup(store_fx):
    a1 = answer("가동 어르신 약국 접근성", store_fx)
    a2 = answer("소아과 못 가는 동네 2곳", store_fx, prev=a1.query)
    assert a2.query.emds == [] and a2.query.persona == "adult" and a2.query.intent == "rank"


def test_multi_category_summary(store_fx):
    a = answer("가동 약국이랑 소아과 접근성", store_fx)
    assert any("[소아청소년과]" in s for s in a.summary)


def test_hours_message(store_fx):
    a = answer("가동 약국 지금 문 연 곳 알려주세요", store_fx)
    assert "시간" in a.message


def test_cards_reach_single_emd(store_fx):
    a = answer("가동 약국", store_fx)
    assert a.cards and a.cards[0]["value"].endswith("분") and "가동약국" in a.cards[0]["sub"]
    assert not any("%" in c["value"] for c in a.cards)


def test_cards_nearest(store_fx):
    a = answer("가동에서 가장 가까운 약국", store_fx)
    assert a.cards[0]["value"].endswith("분") and "가동약국" in a.cards[0]["sub"]


def test_compare_only_for_history(store_fx):
    a = answer("가동 도서관 예전보다 멀어졌어?", store_fx)
    assert "과거 기록" in a.message and a.query.intent == "reach"


def test_no_compare_followup(store_fx):
    assert not any("2019" in f for f in answer("가동 약국", store_fx).followups)


def test_followups_run_clean(store_fx):
    a = answer("가동 약국 10분", store_fx)
    assert 2 <= len(a.followups) <= 4
    for f in a.followups:
        b = answer(f, store_fx, prev=a.query)
        assert b.query.category == "pharmacy" and not b.query.clarify, f


def test_no_followups_for_unsupported(store_fx):
    assert answer("노래방 어디야", store_fx).followups == []


def test_followup_keeps_new_intent(store_fx):
    a = answer("가동에서 가장 가까운 약국", store_fx)
    assert answer("가장 불편한 동네는?", store_fx, prev=a.query).query.intent == "rank"
    b = answer("2019년이랑 비교하면?", store_fx, prev=a.query)
    assert b.query.intent == "compare_year" and b.query.year_from == 2019
    assert answer("10분이면?", store_fx, prev=a.query).query.intent == "nearest"
