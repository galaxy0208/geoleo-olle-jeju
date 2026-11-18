import json
import os
import time
from pathlib import Path

import pandas as pd

import re

URL = "https://dapi.kakao.com/v2/local/search/address.json"
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def read_env(root: Path) -> dict:
    p = root / ".env"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def geocode_one(address, session, key):
    r = session.get(URL, params={"query": address}, headers={"Authorization": f"KakaoAK {key}"}, timeout=10)
    r.raise_for_status()
    docs = r.json().get("documents") or []
    if not docs:
        return None
    return float(docs[0]["y"]), float(docs[0]["x"])


def clean_address(address):
    if not isinstance(address, str):
        return ""
    a = re.sub(r"\([^)]*\)", "", address)
    a = a.split(",")[0]
    a = re.sub(r"\s+\S*층\S*$", "", a.strip())
    return " ".join(a.split())


def keyword_one(name, session, key):
    r = session.get(KEYWORD_URL, params={"query": f"제주 {name}"}, headers={"Authorization": f"KakaoAK {key}"}, timeout=10)
    r.raise_for_status()
    for d in r.json().get("documents") or []:
        if "제주" in (d.get("address_name") or "") and d.get("place_name", "").replace(" ", "") == name.replace(" ", ""):
            return float(d["y"]), float(d["x"])
    return None


def run_geocode(df, session, key, cache_path, delay=0.05):
    cache_path = Path(cache_path)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    df = df.copy()
    status = []

    def lookup(addr):
        if not addr:
            return None
        if addr not in cache:
            cache[addr] = geocode_one(addr, session, key)
            if delay:
                time.sleep(delay)
        return cache[addr]

    for i, r in df.iterrows():
        if pd.notna(r.get("lat")) and pd.notna(r.get("lon")):
            status.append("given")
            continue
        alt = r.get("address_alt") if isinstance(r.get("address_alt"), str) else ""
        tries = [("ok", r.get("address") or ""), ("alt", alt),
                 ("clean", clean_address(r.get("address"))), ("clean", clean_address(alt))]
        hit, tag = None, "fail"
        for t, a in tries:
            hit = lookup(a)
            if hit is not None:
                tag = t
                break
        if hit is None:
            k = f"name::{r.get('name')}"
            if k not in cache:
                cache[k] = keyword_one(r.get("name"), session, key)
                if delay:
                    time.sleep(delay)
            hit = cache[k]
            tag = "keyword" if hit is not None else "fail"
        if hit is None:
            status.append("fail")
            continue
        df.at[i, "lat"], df.at[i, "lon"] = hit
        status.append(tag)
    df["geocode_status"] = status
    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return df


def main():
    import requests

    root = Path(__file__).resolve().parent.parent
    key = os.environ.get("KAKAO_REST_KEY") or read_env(root).get("KAKAO_REST_KEY")
    if not key:
        raise SystemExit(".env 파일에 KAKAO_REST_KEY가 없습니다.")
    df = pd.read_csv(root / "data" / "facilities_raw.csv", encoding="utf-8-sig")
    s = requests.Session()
    try:
        geocode_one("제주특별자치도 제주시 첨단로 241", s, key)
    except Exception as e:
        raise SystemExit(f"Kakao 호출 실패: {e}")
    out = run_geocode(df, s, key, root / "data" / "geocode_cache.json")
    out.to_csv(root / "data" / "facilities.csv", index=False, encoding="utf-8-sig")
    target = out[out.geocode_status != "given"]
    rep = {
        "total": int(len(target)),
        "ok": int((target.geocode_status == "ok").sum()),
        "alt": int((target.geocode_status == "alt").sum()),
        "clean": int((target.geocode_status == "clean").sum()),
        "keyword": int((target.geocode_status == "keyword").sum()),
        "fail": int((target.geocode_status == "fail").sum()),
        "fail_open": int(((target.geocode_status == "fail") & (target.is_open == True)).sum()),
        "fail_names": target[target.geocode_status == "fail"].name.tolist(),
    }
    (root / "data" / "geocode_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: v for k, v in rep.items() if k != "fail_names"})


if __name__ == "__main__":
    main()
