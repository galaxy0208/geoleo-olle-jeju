import json
import os
import re
from pathlib import Path

from app.personas import CATEGORY_LABELS, PERSONAS
from app.query import DATA_YEARS, INTENTS, Query, _snap_minutes, rule_parse

PARSE_PROMPT = """너는 제주 생활권 분석 도구의 질문 해석기다. 사용자 질문을 아래 JSON 하나로만 바꿔라. 설명은 쓰지 마라.
{{"intent": one of {intents},
 "category": one of {cats} or null,
 "persona": one of {personas},
 "minutes": 5|10|15|20,
 "emds": 질문에 나온 읍면동 이름 목록 (아래 목록에 있는 것만),
 "place": 질문에 나온 리 이름 또는 null,
 "year_from": 비교 기준 연도 또는 null,
 "top": 순위 개수 (기본 5)}}
intent 뜻: reach=동네별 도달 비율, rank=가장 불편한 동네 순위, nearest=특정 동네에서 가까운 시설, simulate=새 시설이 생기면/어디에 생기면 좋을지, compare_year=과거와 비교, unsupported=이 데이터로 답할 수 없음.
category 뜻: {cat_desc}
persona 뜻: adult=일반 성인, senior=어르신, senior_aid=휠체어·지팡이 쓰는 어르신, child_guardian=아이 동반 보호자.
"병원"처럼 의원과 병원급 중 무엇인지 모호하면 category를 null로 둬라.
읍면동 목록: {emds}
질문: {text}"""

EXPLAIN_PROMPT = """제주 생활권 분석 결과를 도민에게 설명하는 두 문장을 한국어로 써라.
규칙: 아라비아 숫자와 퍼센트를 쓰지 마라. 결과에 없는 사실이나 원인을 지어내지 마라. 어느 동네가 상대적으로 좋고 나쁜지만 말해라. 결과에 중앙값이라고 쓰여 있으면 평균이라고 바꿔 쓰지 마라.
결과: {summary}
설명:"""


def read_env(root: Path) -> dict:
    p = Path(root) / ".env"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def _extract_json(s: str):
    if not s:
        return None
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def validate(d: dict, emd_names: list) -> Query | None:
    if not isinstance(d, dict):
        return None
    intent = d.get("intent")
    cat = d.get("category")
    persona = d.get("persona") or "adult"
    if intent not in INTENTS or persona not in PERSONAS:
        return None
    if cat is not None and cat not in CATEGORY_LABELS:
        return None
    if intent != "unsupported" and cat is None:
        return None
    try:
        minutes = _snap_minutes(int(d.get("minutes") or 15))
        top = max(1, min(20, int(d.get("top") or 5)))
    except (TypeError, ValueError):
        return None
    emds = [e for e in (d.get("emds") or []) if e in emd_names]
    yf = d.get("year_from")
    if intent == "compare_year":
        try:
            yf = min(max(int(yf), DATA_YEARS[0]), DATA_YEARS[-1])
        except (TypeError, ValueError):
            return None
    else:
        yf = None
    place = d.get("place") if isinstance(d.get("place"), str) and d.get("place") else None
    return Query(intent=intent, category=cat, persona=persona, minutes=minutes, emds=emds,
                 year_from=yf, place=place, top=top)


class LLMClient:
    def __init__(self, backend: str, model: str, host: str = "", key: str = "", http=None):
        self.backend, self.model, self.host, self.key = backend, model, host, key
        self.http = http

    @property
    def label(self):
        return "Qwen (로컬)" if self.backend == "ollama" else "Gemini (온라인)"

    @classmethod
    def from_env(cls, root: Path, http=None):
        import requests

        http = http or requests
        env = {**read_env(root), **os.environ}
        host = env.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        model = env.get("OLLAMA_MODEL", "qwen3.5:4b")
        try:
            r = http.get(f"{host}/api/tags", timeout=2)
            names = [m.get("name", "") for m in r.json().get("models", [])]
            if any(n == model or n.startswith(model.split(":")[0]) for n in names):
                return cls("ollama", model, host=host, http=http)
        except Exception:
            pass
        key = env.get("GEMINI_API_KEY")
        if key:
            return cls("gemini", env.get("GEMINI_MODEL", "gemini-flash-latest"), key=key, http=http)
        return None

    def _complete(self, prompt: str, as_json: bool) -> str | None:
        try:
            if self.backend == "ollama":
                body = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "stream": False,
                        "think": False, "options": {"temperature": 0}}
                if as_json:
                    body["format"] = "json"
                r = self.http.post(f"{self.host}/api/chat", json=body, timeout=60)
                return r.json()["message"]["content"]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}}
            if as_json:
                body["generationConfig"]["responseMimeType"] = "application/json"
            r = self.http.post(url, params={"key": self.key}, json=body, timeout=30)
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return None

    def parse(self, text: str, emd_names: list) -> Query | None:
        prompt = PARSE_PROMPT.format(
            intents=INTENTS, cats=list(CATEGORY_LABELS), personas=list(PERSONAS),
            cat_desc=", ".join(f"{k}={v}" for k, v in CATEGORY_LABELS.items()),
            emds=", ".join(emd_names), text=text)
        return validate(_extract_json(self._complete(prompt, True)), emd_names)

    def explain(self, summary: dict) -> str | None:
        out = self._complete(EXPLAIN_PROMPT.format(summary=json.dumps(summary, ensure_ascii=False)), False)
        if not out:
            return None
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
        out = out.replace("설명:", "").strip()
        if re.search(r"\d", out) or len(out) > 400 or len(out) < 5:
            return None
        return out


def parse(text: str, emd_names: list, llm: LLMClient | None, place_names: list | None = None) -> tuple:
    rq = rule_parse(text, emd_names, place_names)
    need_llm = rq.clarify is None and (rq.intent == "unsupported" or rq.category is None)
    if llm is not None and need_llm:
        lq = llm.parse(text, emd_names)
        if lq is not None and lq.intent != "unsupported":
            lq.emds = [e for e in lq.emds if e in rq.emds or e in text]
            lq.place = lq.place or rq.place
            lq.explicit = {k: True for k, v in [("category", lq.category), ("emds", lq.emds)] if v}
            lq.explicit.update({k: v for k, v in rq.explicit.items() if k in ("persona", "minutes")})
            return lq, "llm"
    return rq, "rule"
