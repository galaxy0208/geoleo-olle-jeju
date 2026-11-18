import json
import os
import sys
import time
import getpass
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://open.jejudatahub.net/api/proxy/{key}/{project}"
HERE = Path(__file__).parent
RAW = HERE / "data_raw"
LOG = HERE / "collect_log.json"

PAGE_CANDIDATES = [
    ("number", "limit"),
    ("pageNo", "numOfRows"),
    ("page", "size"),
    ("page", "limit"),
    ("pageIndex", "pageSize"),
    ("currentPage", "perPage"),
]
OFFSET_CANDIDATES = [("start", "length"), ("offset", "limit"), ("skip", "take")]
SIZES = [1000, 500, 100, 50, 10]
MAX_PAGES = 3000


def call(api_key, project, params, tries=6):
    url = BASE.format(key=api_key, project=project)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return 200, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e.code
            if e.code not in (500, 502, 503, 504, 429):
                return e.code, None
        except Exception as e:
            last = str(e)
        time.sleep(2 * (i + 1))
    return last, None


def rows(body):
    return (body or {}).get("data") or []


def find_paging(api_key, project, base_params, first_row):
    for p, s in PAGE_CANDIDATES:
        for start in (1, 0):
            for size in (10,):
                st, b = call(api_key, project, {**base_params, p: start + 1, s: size}, tries=3)
                r = rows(b)
                if st == 200 and r and r[0] != first_row:
                    return {"kind": "page", "page": p, "size": s, "first": start}
    for o, s in OFFSET_CANDIDATES:
        st, b = call(api_key, project, {**base_params, o: 10, s: 10}, tries=3)
        r = rows(b)
        if st == 200 and r and r[0] != first_row:
            return {"kind": "offset", "offset": o, "size": s}
    return None


def best_size(api_key, project, base_params, paging):
    for n in SIZES:
        params = {**base_params, paging["size"]: n}
        if paging["kind"] == "page":
            params[paging["page"]] = paging["first"]
        else:
            params[paging["offset"]] = 0
        st, b = call(api_key, project, params, tries=3)
        if st == 200 and len(rows(b)) == n:
            return n
    return 10


def fetch_all(api_key, project, base_params, paging, size):
    out = []
    for i in range(MAX_PAGES):
        params = {**base_params, paging["size"]: size}
        if paging["kind"] == "page":
            params[paging["page"]] = paging["first"] + i
        else:
            params[paging["offset"]] = i * size
        st, b = call(api_key, project, params)
        if st != 200:
            return out, f"page {i} failed: {st}"
        r = rows(b)
        out.extend(r)
        if not b.get("hasMore") or not r:
            return out, "ok"
        time.sleep(0.2)
    return out, "max pages"


def main():
    project = os.environ.get("JEJU_PROJECT_KEY") or getpass.getpass("프로젝트키: ").strip()
    apis = json.loads((HERE / "apis.json").read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    RAW.mkdir(exist_ok=True)
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    paging = log.get("_paging")

    for name, a in apis.items():
        if only and name not in only:
            continue
        print(f"[{a['name']}]", flush=True)
        st, b = call(a["key"], project, a["params"])
        if st != 200:
            log[name] = {"status": st}
            print(f"  실패 {st}")
            continue
        first = rows(b)[0] if rows(b) else None
        tot = b.get("totCnt")
        entry = {"status": 200, "totCnt": tot}

        if b.get("hasMore"):
            if not paging:
                paging = find_paging(a["key"], project, a["params"], first)
                log["_paging"] = paging
                print(f"  페이지 옵션: {paging}")
            if paging:
                size = best_size(a["key"], project, a["params"], paging)
                data, note = fetch_all(a["key"], project, a["params"], paging, size)
                entry.update({"rows": len(data), "pageSize": size, "note": note})
            else:
                data = rows(b)
                entry.update({"rows": len(data), "note": "페이지 옵션을 못 찾음"})
        else:
            data = rows(b)
            entry.update({"rows": len(data), "note": "ok"})

        (RAW / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        log[name] = entry
        print(f"  {entry['rows']} / {tot} 건, {entry['note']}")
        LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")

    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n완료: {LOG}")


if __name__ == "__main__":
    main()
