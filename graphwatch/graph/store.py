"""Persistance du graphe : un graphe "live" (mis à jour à chaque cycle) +
des snapshots horodatés (historique, pour comparer l'évolution dans le temps)."""
from __future__ import annotations

import pickle
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx


class GraphStore:
    def __init__(self, data_dir: str | Path, graph_key: str = "shared"):
        self.dir = Path(data_dir) / "graphs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.graph_key = graph_key
        self.live_path = self.dir / f"{graph_key}.gpickle"

    def load_live(self) -> nx.Graph:
        if self.live_path.exists():
            with self.live_path.open("rb") as f:
                return pickle.load(f)
        return nx.Graph()

    def save_live(self, graph: nx.Graph) -> None:
        with self.live_path.open("wb") as f:
            pickle.dump(graph, f)

    def snapshot(self, graph: nx.Graph, label: str | None = None) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = f"{self.graph_key}__{ts}"
        if label:
            name += f"__{label}"
        path = self.dir / f"{name}.gpickle"
        with path.open("wb") as f:
            pickle.dump(graph, f)
        return path

    def export_graphml(self, graph: nx.Graph, path: str | Path) -> None:
        """Export interopérable (Gephi, etc.) — les attributs non scalaires
        (sets, listes) sont stringifiés car GraphML ne les supporte pas."""
        g = graph.copy()
        g.graph.clear()  # ex: alias_index (dict) -- usage interne, GraphML n'accepte que du scalaire
        for _, data in g.nodes(data=True):
            for k, v in list(data.items()):
                if isinstance(v, (set, list, tuple)):
                    data[k] = "; ".join(sorted(str(x) for x in v))
        for _, _, data in g.edges(data=True):
            for k, v in list(data.items()):
                if isinstance(v, (set, list, tuple)):
                    data[k] = "; ".join(sorted(str(x) for x in v))
        nx.write_graphml(g, path)
