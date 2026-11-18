import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import answer
from app.llm import LLMClient
from app.query import describe
from app.store import Store


def main():
    lines = (ROOT / "docs" / "holdout_questions.md").read_text(encoding="utf-8").splitlines()
    qs = [m.group(1).strip() for l in lines if (m := re.match(r"^\s*\d+\.\s*(.+)$", l)) and m.group(1).strip()]
    store = Store.load(ROOT)
    llm = LLMClient.from_env(ROOT) if "--llm" in sys.argv else None
    out = ["| 번호 | 질문 | 해석 | 결과 첫 줄 | 맞음(O/X) |", "|---|---|---|---|---|"]
    for i, q in enumerate(qs, 1):
        a = answer(q, store, llm)
        how = "되묻기" if a.query.clarify else ("답할 수 없음" if a.query.intent == "unsupported" else f"{a.query.intent} · {describe(a.query)}")
        first = (a.message or (a.summary[0] if a.summary else "")).replace("|", "/")
        out.append(f"| {i} | {q} | {how} ({a.parsed_by}) | {first} | |")
    p = ROOT / "docs" / "holdout_result.md"
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
