import json

from app.llm import LLMClient, parse, validate

EMDS = ["한림읍", "애월읍", "연동"]


class Resp:
    def __init__(self, d):
        self.d = d

    def json(self):
        return self.d


class FakeHttp:
    def __init__(self, content, tags=("qwen3.5:4b",)):
        self.content, self.tags = content, tags

    def get(self, url, timeout=None):
        return Resp({"models": [{"name": t} for t in self.tags]})

    def post(self, url, json=None, params=None, timeout=None):
        return Resp({"message": {"content": self.content}})


def client(content):
    return LLMClient("ollama", "qwen3.5:4b", host="http://x", http=FakeHttp(content))


def test_from_env_detects_ollama(tmp_path):
    c = LLMClient.from_env(tmp_path, http=FakeHttp("{}"))
    assert c.backend == "ollama"


def test_from_env_none(tmp_path):
    assert LLMClient.from_env(tmp_path, http=FakeHttp("{}", tags=())) is None


def test_bad_llm_json_falls_back():
    q, src = parse("한림읍 약국", EMDS, client("이건 JSON이 아님"))
    assert q.category == "pharmacy" and src == "rule"


def test_rule_first_skips_llm():
    q, src = parse("어르신 의원 불편한 동네", EMDS, client("{}"))
    assert src == "rule" and q.category == "clinic"


def test_llm_used_when_rule_fails():
    c = client(json.dumps({"intent": "rank", "category": "pharmacy", "persona": "senior", "minutes": 10, "emds": EMDS, "top": 3}))
    q, src = parse("할머니 감기약 사러 가기 힘든 동네", EMDS, c)
    assert src == "llm" and q.intent == "rank" and q.emds == [] and q.persona == "senior"


def test_validate_rejects_unknown_category():
    assert validate({"intent": "reach", "category": "카페", "persona": "adult"}, EMDS) is None


def test_explain_rejects_numbers():
    assert client("한림읍은 15% 입니다.").explain({"x": 1}) is None
    assert client("읍면 지역이 시내보다 불리합니다.").explain({"x": 1}) == "읍면 지역이 시내보다 불리합니다."


def test_clarify_skips_llm():
    q, src = parse("병원 가까운 곳", EMDS, client("{}"))
    assert q.clarify and src == "rule"
