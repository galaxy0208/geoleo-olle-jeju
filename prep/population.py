import json
from pathlib import Path

import pandas as pd


def build_emd_pop(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    daily = df.groupby(["baseDate", "emd", "ageGroup"], as_index=False).resdPop.sum()
    out = daily.groupby(["emd", "ageGroup"], as_index=False).resdPop.mean()
    out.columns = ["emd", "age_group", "resd_pop"]
    out["resd_pop"] = out.resd_pop.round(1)
    return out


def persona_pop(emd_pop: pd.DataFrame, age_groups: list) -> pd.Series:
    return emd_pop[emd_pop.age_group.isin(age_groups)].groupby("emd").resd_pop.sum()


def main():
    root = Path(__file__).resolve().parent.parent
    rows = json.loads((root / "data_raw" / "floating_pop.json").read_text(encoding="utf-8"))
    out = build_emd_pop(rows)
    out.to_csv(root / "data" / "emd_pop.csv", index=False, encoding="utf-8-sig")
    print(out.pivot(index="emd", columns="age_group", values="resd_pop").head(10).to_string())


if __name__ == "__main__":
    main()
