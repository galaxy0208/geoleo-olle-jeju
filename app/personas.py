from dataclasses import dataclass, field


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    speed: float
    age_groups: list = field(default_factory=list)
    default_categories: list = field(default_factory=list)


ADULT_AGES = ["20대", "30대", "40대", "50대", "60대"]
SENIOR_CATS = ["clinic", "public_health", "pharmacy", "dementia", "bus_stop"]

PERSONAS = {
    "adult": Persona("adult", "일반 성인", 1.00, ADULT_AGES, ["pharmacy", "clinic", "bus_stop"]),
    "senior": Persona("senior", "어르신", 0.85, ["70대이상"], SENIOR_CATS),
    "senior_aid": Persona("senior_aid", "보조기구 사용 어르신", 0.73, ["70대이상"], SENIOR_CATS),
    "child_guardian": Persona("child_guardian", "아이 동반 보호자", 0.80, ["10세미만"], ["pediatric", "pharmacy", "library"]),
}

CATEGORY_LABELS = {
    "pharmacy": "약국",
    "clinic": "의원",
    "hospital": "병원급",
    "pediatric": "소아청소년과",
    "dental": "치과",
    "public_health": "보건기관",
    "dementia": "치매안심센터",
    "library": "도서관",
    "bus_stop": "버스정류소",
    "museum": "박물관·미술관",
}

MINUTES = [5, 10, 15, 20]


def reach_m(persona: str, minutes: int) -> float:
    return PERSONAS[persona].speed * minutes * 60
