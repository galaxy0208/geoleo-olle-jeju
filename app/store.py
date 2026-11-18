import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class Store:
    grid: pd.DataFrame
    nearest: pd.DataFrame
    facilities: pd.DataFrame
    facilities_all: pd.DataFrame
    emd_pop: pd.DataFrame
    geocode_report: dict
    distance_report: dict
    stops: pd.DataFrame | None = None
    emd_sgg: dict = field(default_factory=dict)
    graph_path: Path | None = None
    offices: pd.DataFrame | None = None
    _G: object = field(default=None, repr=False)

    @property
    def G(self):
        if self._G is None and self.graph_path is not None:
            from prep.osm_pbf import load_walk_graph
            self._G = load_walk_graph(self.graph_path)
        return self._G

    @property
    def place_names(self) -> list:
        if self.stops is None:
            return []
        ri = self.stops.ri.dropna()
        ri = ri[ri.str.endswith("리")]
        base = self.stops.stationName.dropna().str.replace(r"\(.*?\)|[0-9]+$", "", regex=True).str.strip()
        base = base[base.str.len() >= 3]
        inner = self.stops.stationName.dropna().str.extractall(r"\(([^)]+)\)")[0].str.split(",").explode().str.strip()
        inner = inner[(inner.str.len() >= 3) & ~inner.str.contains("방면|가상")]
        return sorted(set(ri) | set(base) | set(inner))

    @property
    def emds(self) -> list:
        return sorted(self.grid.emd.unique())

    @classmethod
    def load(cls, root: Path) -> "Store":
        root = Path(root)
        d = root / "data"
        rd = lambda p: pd.read_csv(p, encoding="utf-8-sig")
        return cls(
            grid=rd(d / "grid.csv"),
            nearest=pd.read_csv(d / "nearest.csv.gz"),
            facilities=rd(d / "facilities_snapped.csv"),
            facilities_all=rd(d / "facilities.csv"),
            emd_pop=rd(d / "emd_pop.csv"),
            geocode_report=json.loads((d / "geocode_report.json").read_text(encoding="utf-8")),
            distance_report=json.loads((d / "distance_report.json").read_text(encoding="utf-8")),
            stops=rd(d / "stops.csv"),
            emd_sgg={f["properties"]["emd"]: f["properties"]["sgg"] for f in json.loads(
                (root / "data_ext" / "jeju_emd.geojson").read_text(encoding="utf-8"))["features"]},
            graph_path=root / "data_ext" / "jeju_walk.pkl",
            offices=rd(d / "emd_office.csv") if (d / "emd_office.csv").exists() else None,
        )
