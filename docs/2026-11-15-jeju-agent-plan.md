# 우리 동네 생활권 진단 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 도민이 보행자 유형을 고르고 질문하면, 제주 43개 읍면동의 시설 보행 접근성을 계산해 지도, 표, 요약, 분석 과정으로 답하는 로컬 실행 Agent를 만든다.

**Architecture:** 무거운 계산(주소 좌표 변환, OSM 보행망, 격자점→시설 보행거리)은 `prep/`에서 한 번 수행해 `data/`에 저장한다. 실행 중에는 `app/`이 저장된 거리표를 조회하고, 유형별 속도로 시간을 환산한다. LLM은 질문을 조건(JSON)으로 바꾸고 결과를 요약하는 일만 하며, LLM 없이 조건을 직접 고르는 모드가 항상 동작한다.

**Tech Stack:** Python 3.10+, pandas, numpy, networkx, osmnx(전처리만), shapely, geopandas(전처리만), folium, streamlit, requests, pytest. LLM: Ollama `qwen3.5:4b`, 예비 Gemini Flash REST.

**Spec:** `docs/2026-11-15-jeju-agent-design.md`

## Global Constraints

- 프로젝트 루트: 사용자 PC `C:\Users\uSER\OneDrive\Dokumen\Dakon\제주공공데이터` (작업 VM에서는 `$HOME/mnt/제주공공데이터`).
- 네트워크가 필요한 단계(좌표 변환, OSM 다운로드, API 재수집)는 사용자 Windows에서 실행한다. 작업 VM과 클라우드 컨테이너는 jejudatahub, Kakao, Overpass에 접속할 수 없다.
- 코드에 주석을 달지 않는다. 화면 문구와 문서는 짧은 한국어 문장으로 쓴다.
- 숫자는 항상 도구 함수 결과에서만 화면에 나온다. LLM 출력에 숫자가 있으면 버린다.
- 폐업·취소·휴업 시설은 현재 기준 계산에서 제외한다 (`openStatus == "영업/정상"`만 사용).
- 보행자 유형과 속도(m/s): 일반 성인 1.00, 어르신 0.85, 보조기구 사용 어르신 0.73, 아이 동반 보호자 0.80.
- 유형별 인구 가중 연령대: 일반 성인 20대~60대, 어르신·보조기구 어르신 70대이상, 아이 동반 10세미만.
- 기준 시간 선택지: 5, 10, 15, 20분. 기본 15분.
- 격자 간격 250m. 보행망에서 100m 넘게 떨어진 격자점은 제외한다.
- API 키(데이터허브, Kakao, Gemini)는 `.env`에서만 읽고 제출 zip에 넣지 않는다. `.env.example`만 둔다.
- 데이터허브 데이터 목록 xlsx는 제출물과 저장소에 넣지 않는다.
- 센터 PC: i7-8700, GTX 1060, RAM 32GB, VRAM 3GB, Windows 가정. `run.bat` 하나로 설치와 실행.
- git 사용 안 함 (연결 폴더에서 삭제 권한이 없어 git 잠금 파일이 깨진다). 각 Task 끝의 "Commit" 대신 테스트 통과를 확인하고 다음으로 넘어간다.

## Review Focus

1. 읍면동 이름 불일치: 유동인구 `emd`(예: "삼도1동")와 경계 파일 `adm_nm` 끝 단어가 다르면 인구 가중이 0이 된다. Task 4 테스트가 43개 모두 매칭되는지 확인한다.
2. 좌표 변환 실패 시설: 좌표 없는 시설이 조용히 사라지면 접근성이 과소평가된다. Task 2가 실패 목록과 비율을 저장하고, 화면 "분석 과정"에 실패 건수를 보여준다 (Task 8 테스트).
3. 섬 지역(우도면, 추자면): 본섬 보행망과 끊겨 있다. 시설이 없으면 도달 불가로 나와야 하고 에러가 나면 안 된다 (Task 5 테스트).
4. LLM이 없거나 이상한 JSON을 줄 때: 규칙 기반 파서로 넘어가고 화면이 멈추지 않아야 한다 (Task 7 테스트).
5. 조건에 맞는 시설이 0개 (예: 추자면 소아청소년과): "해당 조건의 시설이 없습니다"를 보여주고 0으로 나누지 않아야 한다 (Task 6 테스트).

---

## File Structure

```
제주공공데이터/
  collect.py, apis.json            기존. 데이터허브 재수집
  data_raw/                        기존. API 원본 JSON 10개
  data_ext/                        외부 데이터 (경계, 보행망)
  data/                            전처리 결과
  prep/
    facilities.py                  원본 → 시설 표 (카테고리, 연도 이력)
    geocode.py                     [Windows] Kakao 주소→좌표
    boundary.py                    읍면동 경계 내려받기 정리
    osm.py                         [Windows] 제주 보행망 다운로드
    grid.py                        격자점 생성, 보행망 노드 매칭
    distances.py                   격자→카테고리별 최근접 보행거리 (연도별)
    population.py                  읍면동×연령대 인구 가중치
  app/
    personas.py                    유형, 속도, 기본 시설, 연령대
    store.py                       data/ 로딩 캐시
    analysis.py                    reach_by_emd, rank_gaps, nearest, simulate_new_facility, trace
    query.py                       Query 데이터클래스, 규칙 파서
    llm.py                         Ollama/Gemini 클라이언트, parse/explain
    agent.py                       질문 → 도구 호출 → 결과 묶음
    maps.py                        folium 지도
    related.py                     관련 데이터 추천 (수작업 목록)
    ui.py                          Streamlit 화면
  tests/                           pytest, 작은 합성 그래프 픽스처
  requirements.txt, run.bat, prep.bat, .env.example, README.md
```

카테고리 키 (전 Task 공통):

| key | 이름 | 출처와 조건 |
|---|---|---|
| pharmacy | 약국 | pharmacy |
| clinic | 의원 | hospital, bizSmallType == "의원" |
| hospital | 병원급 | hospital, bizSmallType in 병원, 종합병원, 요양병원(일반요양병원) |
| pediatric | 소아청소년과 | hospital, medicalSubject에 "소아청소년과" 포함, bizSmallType in 의원, 병원, 종합병원 |
| dental | 치과 | hospital, bizSmallType in 치과의원, 치과병원 |
| public_health | 보건기관 | hospital, bizSmallType in 보건소, 보건지소, 보건진료소 |
| dementia | 치매안심센터 | dementia_center |
| library | 공공도서관 | library |
| bus_stop | 버스정류소 | bus_station (좌표 있음) |

---

### Task 1: 시설 표 만들기

**Files:**
- Create: `prep/facilities.py`, `tests/test_facilities.py`, `tests/conftest.py`

**Interfaces:**
- Produces: `build_facilities(raw_dir: Path) -> pd.DataFrame` 컬럼 `fac_id, category, name, address, address_alt, lat, lon, open_date, close_date, is_open`. 한 시설이 여러 카테고리에 해당하면 행을 나눈다 (예: 소아청소년과가 있는 의원은 clinic 행과 pediatric 행). `open_date`, `close_date`는 `datetime.date | None`. bus_stop은 lat/lon이 채워져 있고, 나머지는 None.
- 실행: `python -m prep.facilities` → `data/facilities_raw.csv`

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_pediatric_split(raw_dir_fixture):
    df = build_facilities(raw_dir_fixture)
    rows = df[df.name == "튼튼소아과의원"]
    assert set(rows.category) == {"clinic", "pediatric"}

def test_closed_kept_with_dates(raw_dir_fixture):
    df = build_facilities(raw_dir_fixture)
    r = df[(df.name == "안성약국")].iloc[0]
    assert r.is_open is False and r.close_date == date(2020, 1, 23)

def test_bus_stop_has_coords(raw_dir_fixture):
    df = build_facilities(raw_dir_fixture)
    assert df[df.category == "bus_stop"].lat.notna().all()
```

`conftest.py`의 `raw_dir_fixture`는 tmp_path에 data_raw 형식 JSON 몇 건을 쓴다 (약국 2건: 영업 1, 폐업 1 / 병의원 3건: 의원+소아청소년과, 치과의원, 보건진료소 / 정류소 2건 / 도서관 1 / 치매센터 1).

- [ ] **Step 2: `pytest tests/test_facilities.py -v` → FAIL (모듈 없음)**
- [ ] **Step 3: `build_facilities` 구현.** `address`는 도로명 우선, 없으면 지번. `address_alt`는 나머지 하나. 도서관 주소("제주시 연오로 140")처럼 시도명이 없으면 앞에 "제주특별자치도 "를 붙인다. `is_open`은 `openStatus == "영업/정상"`, 도서관·치매센터·정류소는 True.
- [ ] **Step 4: 테스트 PASS 확인, 실제 data_raw로 실행해 카테고리별 건수를 출력**

Expected: pharmacy 영업 318, clinic 영업 507, bus_stop 4352.

---

### Task 2: 주소 좌표 변환 [Windows]

**Files:**
- Create: `prep/geocode.py`, `tests/test_geocode.py`, `.env.example`

**Interfaces:**
- Consumes: `data/facilities_raw.csv` (Task 1)
- Produces: `data/facilities.csv` (lat/lon 채움, `geocode_status` in ok, alt, fail), `data/geocode_report.json` `{"total": int, "ok": int, "alt": int, "fail": int, "fail_names": [str]}`. 캐시 `data/geocode_cache.json` (주소 → [lat, lon] 또는 null).
- `geocode_one(address: str, session, key: str) -> tuple[float, float] | None` Kakao `GET https://dapi.kakao.com/v2/local/search/address.json?query=...`, 헤더 `Authorization: KakaoAK {key}`, 응답 `documents[0].y/x`.

- [ ] **Step 1: 실패 테스트** (네트워크 없이 `session`을 가짜 객체로)

```python
def test_fallback_to_alt_address(fake_session):
    df = run_geocode(sample_df, fake_session, key="x")
    assert df.loc[0, "geocode_status"] == "alt"

def test_cache_prevents_second_call(fake_session, tmp_path):
    run_geocode(sample_df, fake_session, key="x", cache_path=tmp_path/"c.json")
    run_geocode(sample_df, fake_session, key="x", cache_path=tmp_path/"c.json")
    assert fake_session.calls == 2
```

- [ ] **Step 2: FAIL 확인**
- [ ] **Step 3: 구현.** bus_stop은 건너뛴다. 폐업 시설도 변환한다 (연도별 분석용). 요청 사이 0.05초 대기. `.env`의 `KAKAO_REST_KEY`를 읽는다.
- [ ] **Step 4: 테스트 PASS**
- [ ] **Step 5: 사용자 작업.** Kakao Developers에서 앱 생성 → REST API 키를 `.env`에 `KAKAO_REST_KEY=...`로 저장 → Windows에서 `python -m prep.geocode` 실행.

Expected: `geocode_report.json`의 fail 비율 5% 미만. 넘으면 실패 주소 패턴을 보고 Task 2를 보완한다.

---

### Task 3: 읍면동 경계와 보행망

**Files:**
- Create: `prep/boundary.py`, `prep/osm.py`, `tests/test_boundary.py`

**Interfaces:**
- Produces: `data_ext/jeju_emd.geojson` 43개 폴리곤, 속성 `emd`(adm_nm 마지막 단어), `sgg`(제주시/서귀포시), `adm_cd2`. 출처 vuski/admdongkor `ver20250101/HangJeongDong_ver20250101.geojson`, `sidonm == "제주특별자치도"`.
- Produces: `data_ext/jeju_walk.graphml` (osmnx `network_type="walk"`, 경계 합집합 폴리곤 + 200m 버퍼). 엣지 속성 `length`(m).
- `load_walk_graph(path) -> nx.MultiDiGraph`

- [ ] **Step 1: 실패 테스트** `test_43_emd`: 파일을 읽어 행 43개, `emd` 고유 43개, "추자면"과 "우도면" 포함.
- [ ] **Step 2: FAIL 확인**
- [ ] **Step 3: `boundary.py` 구현** (클라우드 컨테이너에서 GitHub raw로 받아 사용자 폴더에 넣는다).
- [ ] **Step 4: 테스트 PASS**
- [ ] **Step 5: `osm.py` 작성 후 사용자 작업.** Windows에서 `pip install osmnx` → `python -m prep.osm`.

Expected: graphml 생성, 노드 수 출력. 섬 지역은 별도 연결 요소로 들어온다.

---

### Task 4: 격자점과 인구 가중치

**Files:**
- Create: `prep/grid.py`, `prep/population.py`, `tests/test_grid.py`, `tests/test_population.py`

**Interfaces:**
- Consumes: `jeju_emd.geojson`, `jeju_walk.graphml`, `data_raw/floating_pop.json`
- Produces: `data/grid.csv` 컬럼 `grid_id, emd, lat, lon, node, snap_m`. `snap_m > 100` 행은 제외.
- Produces: `data/emd_pop.csv` 컬럼 `emd, age_group, resd_pop`. `resd_pop`은 7일 평균, 성별 합. 연령대 값은 원본 그대로(`10세미만`, `10대` … `70대이상`).
- `persona_pop(emd_pop: pd.DataFrame, age_groups: list[str]) -> pd.Series` (index emd)

- [ ] **Step 1: 실패 테스트**

```python
def test_grid_spacing_and_snap(small_polygon, small_graph):
    g = make_grid(small_polygon, small_graph, spacing_m=250, max_snap_m=100)
    assert (g.snap_m <= 100).all() and g.grid_id.is_unique

def test_all_emd_match():
    pop = pd.read_csv("data/emd_pop.csv"); emd = gpd.read_file("data_ext/jeju_emd.geojson")
    assert set(pop.emd) == set(emd.emd)
```

- [ ] **Step 2: FAIL 확인**
- [ ] **Step 3: 구현.** 격자는 EPSG:5179로 투영해 250m 간격으로 만들고 WGS84로 되돌린다. 노드 매칭은 `osmnx.distance.nearest_nodes`. 이름이 안 맞으면 매핑 사전을 `population.py`에 둔다.
- [ ] **Step 4: 테스트 PASS, 읍면동별 격자 수 출력** (모든 읍면동이 1개 이상).

---

### Task 5: 격자→시설 보행거리 사전 계산

**Files:**
- Create: `prep/distances.py`, `tests/test_distances.py`

**Interfaces:**
- Consumes: grid.csv, facilities.csv, walk graph
- Produces: `data/nearest.parquet` 컬럼 `grid_id, category, year, dist_m`. year는 2019~2025와 `0`(현재 영업 기준). 도달 불가는 `inf`. 탐색 상한 2,000m (20분 × 1.0 m/s = 1,200m보다 여유).
- `nearest_dist(G, source_nodes: list, cutoff: float) -> dict[node, float]` 다중 출발 Dijkstra (`nx.multi_source_dijkstra_path_length`, weight="length"). 그래프는 무방향으로 바꿔 쓴다.
- `active_in_year(df, year) -> pd.DataFrame` : `open_date <= year-12-31` 이고 (`close_date` 없음 또는 `> year-12-31`).

- [ ] **Step 1: 실패 테스트**

```python
def test_line_graph_distance(line_graph):
    d = nearest_dist(line_graph, [0], cutoff=2000)
    assert d[3] == 300

def test_unreachable_is_inf(two_component_graph, grid_small):
    out = compute_nearest(grid_small, facs_only_in_comp_a, two_component_graph)
    assert np.isinf(out.loc[out.grid_id == "island_1", "dist_m"]).all()

def test_active_in_year():
    assert list(active_in_year(df_hist, 2019).name) == ["2018개업약국"]
```

- [ ] **Step 2: FAIL 확인**
- [ ] **Step 3: 구현.** 시설 좌표도 노드에 매칭한다 (좌표 실패 시설은 제외하고 개수를 `data/distance_report.json`에 기록). 카테고리 9개 × 연도 8개 = 72회 Dijkstra.
- [ ] **Step 4: 테스트 PASS, 실제 데이터로 실행 시간과 행 수 출력**

---

### Task 6: 분석 도구

**Files:**
- Create: `app/personas.py`, `app/store.py`, `app/analysis.py`, `tests/test_analysis.py`

**Interfaces:**
- `Persona(key: str, label: str, speed: float, age_groups: list[str], default_categories: list[str])`, `PERSONAS: dict[str, Persona]` 키 `adult, senior, senior_aid, child_guardian`. 값은 Global Constraints 그대로.
- `Store.load(data_dir: Path) -> Store` 속성 `grid, nearest, facilities, emd_pop, geocode_report, emd_shapes`.
- `reach_by_emd(store, category: str, persona: str, minutes: int, year: int = 0, emds: list[str] | None = None) -> pd.DataFrame` 컬럼 `emd, grid_n, reach_n, reach_pct, persona_pop, est_unreached`. `est_unreached = persona_pop * (1 - reach_pct/100)` 반올림 정수.
- `rank_gaps(store, category, persona, minutes, top: int = 5, year: int = 0) -> pd.DataFrame` `est_unreached` 내림차순.
- `nearest(store, emd: str, category: str, persona: str, n: int = 3) -> pd.DataFrame` 읍면동 중심 격자점에서 가까운 시설 n개 `name, address, dist_m, minutes`. 런타임 Dijkstra.
- `simulate_new_facility(store, lat: float, lon: float, category: str, persona: str, minutes: int) -> dict` `{"new_reach_grid": int, "by_emd": DataFrame, "est_people": int}`.
- `trace(store, category, persona, minutes, year) -> list[str]` 분석 과정 문장들 (원본 건수, 폐업 제외, 좌표 실패, 유형 속도, 거리 상한).

- [ ] **Step 1: 실패 테스트** (합성 store 픽스처)

```python
def test_speed_changes_reach(store_fx):
    a = reach_by_emd(store_fx, "pharmacy", "adult", 15)
    s = reach_by_emd(store_fx, "pharmacy", "senior_aid", 15)
    assert (s.reach_pct <= a.reach_pct).all()

def test_threshold_math(store_fx):
    r = reach_by_emd(store_fx, "pharmacy", "adult", 10, emds=["가동"])
    assert r.iloc[0].reach_pct == 50.0

def test_no_facility_zero_not_error(store_fx):
    r = reach_by_emd(store_fx, "pediatric", "child_guardian", 15, emds=["섬면"])
    assert r.iloc[0].reach_pct == 0.0

def test_trace_mentions_closed(store_fx):
    assert any("폐업" in s for s in trace(store_fx, "pharmacy", "adult", 15, 0))
```

- [ ] **Step 2: FAIL 확인**
- [ ] **Step 3: 구현.** 도달 판정: `dist_m <= speed * minutes * 60`.
- [ ] **Step 4: 테스트 PASS**

---

### Task 7: 질문 해석과 LLM

**Files:**
- Create: `app/query.py`, `app/llm.py`, `tests/test_query.py`, `tests/test_llm.py`

**Interfaces:**
- `Query(intent: str, category: str | None, persona: str, minutes: int, emds: list[str], year: int, lat: float | None, lon: float | None, clarify: str | None)`. intent ∈ `reach, rank, nearest, simulate, compare_year, unsupported`. 기본값 persona="adult", minutes=15, year=0.
- `rule_parse(text: str, emd_names: list[str]) -> Query` 키워드 사전 기반.
- `LLMClient.from_env() -> LLMClient | None` 순서: Ollama(`OLLAMA_HOST` 기본 `http://localhost:11434`, 모델 `OLLAMA_MODEL` 기본 `qwen3.5:4b`) 응답 확인 → Gemini(`GEMINI_API_KEY`) → None.
- `LLMClient.parse(text, emd_names) -> Query | None` JSON 스키마를 프롬프트로 주고, 파싱 실패나 허용값 밖이면 None.
- `LLMClient.explain(result_summary: dict) -> str | None` 세 문장. 출력에 숫자가 있으면 None (숫자 요약은 템플릿이 담당).
- `parse(text, emd_names, llm) -> Query` : llm.parse → 실패 시 rule_parse.

- [ ] **Step 1: 실패 테스트**

```python
@pytest.mark.parametrize("text,cat,persona,mins,intent", [
    ("한림읍 어르신 걸어서 약국 몇 퍼센트", "pharmacy", "senior", 15, "reach"),
    ("아이랑 10분 안에 소아과 갈 수 있는 동네", "pediatric", "child_guardian", 10, "reach"),
    ("의원 접근 제일 나쁜 동네 5곳", "clinic", "adult", 15, "rank"),
    ("휠체어 타는 어르신 기준 버스정류소", "bus_stop", "senior_aid", 15, "reach"),
    ("2019년이랑 비교하면 약국", "pharmacy", "adult", 15, "compare_year"),
    ("오늘 날씨 어때", None, "adult", 15, "unsupported"),
])
def test_rule_parse(text, cat, persona, mins, intent): ...

def test_병원_asks_clarify():
    assert rule_parse("병원 가까운 동네", EMDS).clarify is not None

def test_bad_llm_json_falls_back(fake_llm_returning_garbage):
    q = parse("한림읍 약국", EMDS, fake_llm_returning_garbage)
    assert q.category == "pharmacy"

def test_explain_rejects_numbers(fake_llm_with_numbers):
    assert fake_llm_with_numbers.explain({"x": 1}) is None
```

- [ ] **Step 2: FAIL 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 테스트 PASS**
- [ ] **Step 5: 평가 세트 30문항** `tests/eval_questions.csv` (text, 기대 category, persona, minutes, intent). `python -m app.query --eval`이 규칙 파서와 LLM 각각의 정확도를 출력.

---

### Task 8: Agent 흐름

**Files:**
- Create: `app/agent.py`, `app/related.py`, `tests/test_agent.py`

**Interfaces:**
- `answer(text: str, store: Store, llm, prev: Query | None = None, overrides: dict | None = None) -> Answer`
- `Answer(query: Query, table: pd.DataFrame | None, summary: list[str], explanation: str | None, trace: list[str], sources: list[str], limits: list[str], related: list[dict], map_spec: dict | None, message: str | None)`
- 후속 질문: `prev`가 있고 새 질문에 빠진 항목은 `prev`에서 채운다 ("어르신 걸음으로 하면?" → category, emds 유지, persona만 변경).
- `summary`는 템플릿 문장 3개 (숫자 포함, LLM 미사용).
- `related.py`: 카테고리별 데이터허브 관련 데이터 2~3개 수작업 목록 `{"title", "why"}` (예: senior → 경로당현황, 노인복지시설현황).
- `limits` 고정 문장: 경사 미반영, 아이 동반 속도는 가정, 유동인구 기반 인구는 추정, 좌표 실패 N건 제외.

- [ ] **Step 1: 실패 테스트**

```python
def test_followup_keeps_category(store_fx, no_llm):
    a1 = answer("가동 약국 접근성", store_fx, no_llm)
    a2 = answer("어르신 걸음으로 하면?", store_fx, no_llm, prev=a1.query)
    assert a2.query.category == "pharmacy" and a2.query.persona == "senior"

def test_unsupported_has_message(store_fx, no_llm):
    a = answer("오늘 날씨 어때", store_fx, no_llm)
    assert a.table is None and a.message

def test_trace_reports_geocode_fail(store_fx, no_llm):
    a = answer("가동 약국 접근성", store_fx, no_llm)
    assert any("좌표" in t for t in a.trace)

def test_zero_facility_message(store_fx, no_llm):
    a = answer("섬면 소아과", store_fx, no_llm)
    assert "없습니다" in a.message
```

- [ ] **Step 2: FAIL 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 테스트 PASS**

---

### Task 9: 지도와 화면

**Files:**
- Create: `app/maps.py`, `app/ui.py`, `tests/test_maps.py`

**Interfaces:**
- `make_map(store, answer: Answer) -> folium.Map` 읍면동 단계 색칠(reach_pct 0~100, 4구간), 시설 점, simulate일 때 후보 위치 표시.
- `ui.py` 구성 (설계 8절): 유형 선택 라디오(첫 화면 상단), 질문 입력, 예시 버튼 3개, 지도(`st.components.v1.html`), 요약, 표, "분석 과정" 펼치기, 출처·한계, 관련 데이터, 조건 직접 고르기(시설/시간/지역/유형/연도), CSV 내려받기. 대화 기록은 `st.session_state["prev"]`.
- LLM 상태를 사이드바에 표시: "Qwen 로컬 / Gemini / LLM 없음(직접 고르기 모드)".

- [ ] **Step 1: 실패 테스트** `test_map_has_all_emd`: 지도 HTML에 43개 읍면동 이름이 모두 들어 있음 (합성 store면 픽스처 수).
- [ ] **Step 2: FAIL 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 테스트 PASS, `streamlit run app/ui.py`로 화면 확인** (작업 VM에서 띄우고 사용자 브라우저로 확인).

---

### Task 10: 패키징과 검증

**Files:**
- Create: `requirements.txt`, `run.bat`, `prep.bat`, `README.md`, `docs/validation.md`

**Interfaces:**
- `run.bat`: venv 없으면 생성 → `pip install -r requirements.txt` → Ollama 설치 여부 확인 후 없으면 안내 문구 → `streamlit run app/ui.py`.
- `prep.bat`: collect → facilities → geocode → osm → grid → population → distances 순서.
- README: 설치, 실행, 키 발급(데이터허브 프로젝트키, Kakao, Gemini 선택), 사용법, 오류와 제약, 외부 데이터·오픈소스·AI 사용 내역 (대회 제출 요구 항목).

- [ ] **Step 1: 보행 시간 검증.** 표본 20쌍(격자점→시설)의 계산 거리를 사용자가 네이버 지도 도보 거리와 비교해 `docs/validation.md`에 표로 기록. 평균 절대 오차 % 계산.
- [ ] **Step 2: 평가 세트 실행** `python -m app.query --eval` 결과를 validation.md에 기록.
- [ ] **Step 3: 새 venv에서 `run.bat`이 처음부터 실행되는지 확인** (사용자 Windows).
- [ ] **Step 4: 전체 `pytest` PASS**

---

## 일정 매핑

| 날짜 | Task |
|---|---|
| 11/15(일) | 1, 2(코드), 3 |
| 11/16(월) | 2(실행), 4, 5 |
| 11/17(화) | 6, 7 |
| 11/18(수) | 8, 9 |
| 11/19(목) | 10, 기획서, zip 정리, 저녁 제출 |

기획서 작성은 이 계획 밖이다. Task 10 이후 별도로 진행한다.
