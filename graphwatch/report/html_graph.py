"""Génère la vue interactive du graphe : un fichier HTML autonome (canvas 2D,
simulation physique maison, panneau de détail, recherche) — sans dépendance
externe obligatoire, pensé pour un usage local hors-ligne comme pour la
publication en page web."""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from graphwatch.graph.analysis import AnalysisResult
from graphwatch.report.graph_export import build_payload

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _read(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def generate_html_graph(
    *,
    graph: nx.Graph,
    analysis: AnalysisResult,
    output_path: Path,
    min_corroborating_sources: int,
    source_name: str,
    generated_at: str,
    n_new_docs: int = 0,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_payload(
        graph, analysis,
        source_name=source_name,
        generated_at=generated_at,
        n_new_docs=n_new_docs,
        min_corroborating_sources=min_corroborating_sources,
    )
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</script", "<\\/script")

    css = _read("graph_view.css")
    js = _read("graph_view.js")

    m = payload["meta"]
    stability = f"{m['communityStability']:.0%}" if m["communityStability"] is not None else "n/a"

    html = f"""<title>Graphe — {source_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{css}
</style>

<div class="topbar">
  <div class="brand">
    <div class="name">{source_name}</div>
    <div class="meta">généré {generated_at} · {n_new_docs} nouveau(x) document(s) ce cycle</div>
  </div>
  <div class="stat-row">
    <div class="stat-tile"><div class="v">{m['nNodes']}</div><div class="k">entités</div></div>
    <div class="stat-tile"><div class="v">{m['nEdges']}</div><div class="k">relations</div></div>
    <div class="stat-tile"><div class="v">{m['nCommunities']}</div><div class="k">communautés</div></div>
    <div class="stat-tile"><div class="v">{m['modularity']:.2f}</div><div class="k">modularité</div></div>
    <div class="stat-tile"><div class="v">{stability}</div><div class="k">stabilité</div></div>
  </div>
  <div class="search-wrap">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/></svg>
    <input id="search-input" type="text" placeholder="rechercher une entité…" autocomplete="off">
  </div>
  <span id="search-count" class="search-count"></span>
</div>

<div class="body-row">
  <div id="stage">
    <canvas id="graph-canvas"></canvas>
    <div class="hint">glisser = déplacer un nœud · fond = panoramique · molette = zoom · clic = détail</div>
    <div id="tooltip" class="tooltip"></div>
  </div>
  <div id="panel" class="panel"></div>
</div>

<script id="graph-data" type="application/json">{payload_json}</script>
<script>
{js}
</script>
"""

    output_path.write_text(html, encoding="utf-8")
    return output_path
