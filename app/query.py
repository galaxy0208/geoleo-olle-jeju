import re
from dataclasses import asdict, dataclass, field

from app.personas import CATEGORY_LABELS, MINUTES, PERSONAS

BLOCK_PLACES = {"약국", "의원", "병원", "치과", "도서관", "보건소", "정류소", "정류장", "버스", "동네", "입구", "사거리", "삼거리"}

INTENTS = ["reach", "rank", "nearest", "simulate", "compare_year", "unsupported"]
DATA_YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
CURRENT_YEAR = 2026
LAST_FULL_YEAR = 2024

CAT_RULES = [
    ("pediatric", ["소아청소년과", "소아과", "소아"]),
    ("dental", ["치과"]),
    ("dementia", ["치매"]),
    ("public_health", ["보건소", "보건지소", "보건진료소", "보건기관"]),
    ("hospital", ["종합병원", "병원급", "큰 병원", "큰병원", "요양병원"]),
    ("clinic", ["의원", "동네병원", "동네 병원", "내과", "병의원"]),
    ("pharmacy", ["약국", "약방"]),
    ("library", ["도서관", "새마을문고", "작은도서관", "문고", "책 빌", "책을 빌", "책 읽", "도서 대출"]),
    ("bus_stop", ["버스", "정류장", "정류소"]),
    ("museum", ["박물관", "미술관", "전시관", "갤러리", "전시"]),
]
PERSONA_RULES = [
    ("senior_aid", ["휠체어", "지팡이", "보행보조", "보조기구", "보행기", "거동", "몸이 불편", "걷기 힘드", "걸음이 불편"]),
    ("child_guardian", ["아이", "아기", "유아", "어린이", "유모차", "애기", "자녀"]),
    ("senior", ["어르신", "노인", "할머니", "할아버지", "고령", "70대", "부모님"]),
    ("adult", ["성인", "일반", "젊은"]),
]


@dataclass
class Query:
    intent: str = "reach"
    category: str | None = None
    persona: str = "adult"
    minutes: int = 15
    emds: list = field(default_factory=list)
    year: int = 0
    year_from: int | None = None
    place: str | None = None
    top: int = 5
    clarify: str | None = None
    categories: list = field(default_factory=list)
    sgg: str | None = None
    hours_asked: bool = False
    explicit: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def _all(text, rules):
    hits = []
    for key, words in rules:
        pos = [text.find(w) for w in words if w in text]
        if pos:
            hits.append((min(pos), key))
    return [k for _, k in sorted(hits)]


def _first(text, rules):
    for key, words in rules:
        if any(w in text for w in words):
            return key
    return None


def _snap_minutes(m):
    return min(MINUTES, key=lambda x: abs(x - m))


def find_emds(text, emd_names):
    found = [e for e in emd_names if e in text]
    for e in emd_names:
        if e.endswith(("읍", "면")) and e[:-1] in text and e not in found and len(e[:-1]) >= 2:
            found.append(e)
    return found


def rule_parse(text: str, emd_names: list, place_names: list | None = None) -> Query:
    t = text.strip()
    q = Query()
    ex = {}
    cats = _all(re.sub(r"(소아청소년과|소아과|치과|한)의원", r"\1", t), CAT_RULES)
    cat = cats[0] if cats else None
    q.categories = cats
    if cat is None and "병원" in t:
        q.clarify = "병원은 동네 의원까지 볼까요, 병원급(병원·종합병원)만 볼까요?"
    q.category = cat
    if cat:
        ex["category"] = True
    p = _first(t, PERSONA_RULES)
    if p:
        q.persona = p
        ex["persona"] = True
    m = re.search(r"(\d+)\s*분", t)
    if m:
        q.minutes = _snap_minutes(int(m.group(1)))
        ex["minutes"] = True
    q.emds = find_emds(t, emd_names)
    if q.emds:
        ex["emds"] = True
    if place_names:
        tn = t.replace(" ", "")
        hits = [(tn.rfind(r.replace(" ", "")), len(r), r) for r in place_names
                if r and len(r) >= 2 and r.replace(" ", "") in tn and r not in q.emds and r not in BLOCK_PLACES]
        if hits:
            q.place = max(hits)[2]
            ex["place"] = True
    tm = re.search(r"(\d+)\s*(곳|개|군데|위)", t)
    if tm:
        q.top = max(1, min(20, int(tm.group(1))))
    y = re.search(r"(20\d\d)\s*년", t)
    year = int(y.group(1)) if y else (LAST_FULL_YEAR if "작년" in t else None)
    if year is not None:
        year = min(max(year, DATA_YEARS[0]), DATA_YEARS[-1])
    if "서귀포" in t:
        q.sgg = "서귀포시"
    elif "제주시" in t:
        q.sgg = "제주시"
    q.hours_asked = any(w in t for w in ["문 연", "문연", "문 여는", "영업 중", "영업중", "지금 열", "오늘 열", "진료 시간", "진료시간", "야간", "휴일", "주말"])
    old = any(w in t for w in ["예전", "옛날", "전보다", "나아졌", "좋아졌", "나빠졌", "달라졌", "변했", "줄었", "늘었"])
    if year is None and old:
        year = DATA_YEARS[0]
    if any(w in t for w in ["생기면", "새로 ", "새로생", "들어서면", "만들면", "세우면", "어디에 만들", "어디에 생", "입지", "위치 추천"]):
        q.intent = "simulate"
    elif year is not None and (old or any(w in t for w in ["비교", "대비", "변화", "보다", "달라", "줄었", "늘었", "전보다", "때랑", "이랑"])):
        q.intent, q.year_from = "compare_year", year
    elif any(w in t for w in ["가까운", "가깝", "몇 분", "얼마나 걸", "어디가 있", "어디 있", "어디야", "어디예요", "어딘지", "알려주세요", "문 연 곳"]) and not any(w in t for w in ["동네가", "동네 중", "사각지대", "순위"]):
        q.intent = "nearest"
    elif any(w in t for w in ["순위", "제일", "가장", "나쁜", "취약", "부족", "불편", "멀리", "열악", "못 가", "못가", "어려운", "힘든"]):
        q.intent = "rank"
    else:
        q.intent = "reach"
        if year is not None:
            q.year = year
    if q.intent != "reach":
        ex["intent"] = q.intent
    if cat is None and q.clarify is None:
        q.intent = "unsupported"
    if q.place and q.intent in ("reach", "rank") and not q.emds and any(w in t for w in ["거기", "에서", "근처", "주변"]):
        q.intent = "nearest"
    if q.intent in ("nearest",) and not q.emds and not q.place:
        q.clarify = q.clarify or "어느 동네를 기준으로 볼까요? 읍면동이나 리 이름을 알려주세요."
    if q.intent == "simulate" and not q.emds:
        q.clarify = q.clarify or "어느 읍면동에 생긴다고 가정할까요?"
    q.explicit = ex
    return q


def describe(q: Query) -> str:
    cat = " + ".join(CATEGORY_LABELS[c] for c in (q.categories or [q.category]) if c) or "시설"
    where = q.place if q.place and q.intent == "nearest" else (", ".join(q.emds) if q.emds else (q.sgg or "제주 전체"))
    return f"{where} · {cat} · {PERSONAS[q.persona].label} · {q.minutes}분"


def josa(word: str, pair: str) -> str:
    a, b = pair.split("/")
    if not word:
        return word + b
    c = ord(word[-1]) - 0xAC00
    has = 0 <= c <= 11171 and c % 28 != 0
    if pair == "으로/로" and has and c % 28 == 8:
        has = False
    return word + (a if has else b)
