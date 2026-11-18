import json
import os
import sys
import time
import getpass
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://open.jejudatahub.net/api/proxy/{key}/{project}"
HERE = Path(__file__).parent
OUT = HERE / "probe_out"

PAGING_CANDIDATES = [
    {"number": 2, "limit": 100},
    {"page": 2, "size": 100},
    {"pageNo": 2, "numOfRows": 100},
    {"pageNumber": 2, "length": 100},
    {"offset": 100, "limit": 100},
    {"start": 100, "length": 100},
]


def call(api_key, project, params):
    url = BASE.format(key=api_key, project=project)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return -1, str(e)


def summary(body):
    if not isinstance(body, dict):
        return {"raw": str(body)[:200]}
    rows = body.get("data") or []
    first = rows[0] if rows else {}
    return {
        "totCnt": body.get("totCnt"),
        "hasMore": body.get("hasMore"),
        "rows": len(rows),
        "fields": list(first.keys()),
        "first": first,
    }


def main():
    project = os.environ.get("JEJU_PROJECT_KEY") or getpass.getpass("프로젝트키: ").strip()
    apis = json.loads((HERE / "apis.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    report = {}

    for name, a in apis.items():
        status, body = call(a["key"], project, a["params"])
        report[name] = {"name": a["name"], "status": status, **(summary(body) if status == 200 else {"body": body})}
        if status == 200:
            (OUT / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{a['name']}: {status} {report[name].get('totCnt')} {report[name].get('rows')}")
        time.sleep(0.3)

    base_status, base = call(apis["pharmacy"]["key"], project, {})
    base_first = (base or {}).get("data", [{}])[0] if base_status == 200 else None
    paging = []
    for cand in PAGING_CANDIDATES:
        status, body = call(apis["pharmacy"]["key"], project, cand)
        s = summary(body) if status == 200 else {}
        paging.append({
            "params": cand,
            "status": status,
            "rows": s.get("rows"),
            "hasMore": s.get("hasMore"),
            "first_changed": status == 200 and s.get("first") != base_first,
        })
        time.sleep(0.3)
    report["_paging_probe"] = paging

    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n완료: {OUT / 'report.json'}")


if __name__ == "__main__":
    sys.exit(main())
