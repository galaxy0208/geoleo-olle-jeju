import time
from pathlib import Path

from app.llm import LLMClient

EMDS = ["한림읍", "애월읍", "연동", "노형동", "표선면", "구좌읍"]
QS = [
    "한림읍 어르신 걸어서 약국 갈 수 있는 비율",
    "아이랑 10분 안에 소아과 못 가는 동네 3곳",
    "애월읍에 보건진료소가 새로 생기면 어디가 좋아",
]


def main():
    root = Path(__file__).resolve().parent.parent
    c = LLMClient.from_env(root)
    if c is None:
        print("LLM을 찾지 못했습니다. Ollama가 켜져 있는지 확인하세요.")
        return
    print(f"사용 모델: {c.label} {c.model}")
    for q in QS:
        t = time.time()
        r = c.parse(q, EMDS)
        print(f"{time.time() - t:.1f}초 | {q}\n  -> {r.to_dict() if r else '해석 실패'}")
    t = time.time()
    print(f"{time.time() - t:.1f}초 | 설명:", c.explain({"질문": "어르신 의원 접근", "가장 불편한 동네": ["애월읍", "한림읍"], "가장 좋은 동네": ["일도1동"]}))


if __name__ == "__main__":
    main()
