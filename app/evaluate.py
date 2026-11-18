import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import answer
from app.llm import LLMClient
from app.store import Store

FIELDS = ["intent", "category", "persona", "minutes", "emds"]


def _norm(q):
    return {"intent": q.intent, "category": q.category or "", "persona": q.persona, "minutes": str(q.minutes),
            "emds": ",".join(q.emds)}


def main(use_llm: bool):
    store = Store.load(ROOT)
    llm = LLMClient.from_env(ROOT) if use_llm else None
    rows = list(csv.DictReader(open(ROOT / "tests" / "eval_questions.csv", encoding="utf-8")))
    exact, field_hits, ok_run, times, misses = 0, {f: 0 for f in FIELDS}, 0, [], []
    for r in rows:
        t = time.time()
        try:
            a = answer(r["text"], store, llm)
            ok_run += int(bool(a.summary or a.message))
        except Exception as e:
            misses.append((r["text"], f"오류: {e}"))
            continue
        times.append(time.time() - t)
        got = _norm(a.query)
        hit = {f: got[f] == (r[f] or "") for f in FIELDS}
        for f in FIELDS:
            field_hits[f] += hit[f]
        if all(hit.values()):
            exact += 1
        else:
            misses.append((r["text"], {f: (got[f], r[f]) for f in FIELDS if not hit[f]}))
    n = len(rows)
    print(f"문항 {n}개 | 해석기: {'규칙 + ' + llm.label if llm else '규칙'}")
    print(f"완전 일치 {exact}/{n} ({exact / n:.0%}) | 실행 성공 {ok_run}/{n}")
    print("항목별 정확도: " + ", ".join(f"{f} {v / n:.0%}" for f, v in field_hits.items()))
    print(f"평균 응답 시간 {sum(times) / len(times):.2f}초, 최대 {max(times):.2f}초")
    for m in misses:
        print("  틀림:", m)


if __name__ == "__main__":
    main("--llm" in sys.argv)
