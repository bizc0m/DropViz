"""Fiche autonome pour UNE entité (personne, organisation, groupe) : réseau
direct (ego-network radial), relations détaillées avec extraits et sources,
badges Admiralty. Pensée pour être exportée/partagée seule, indépendamment
du graphe complet."""
from __future__ import annotations

import json
import re
from pathlib import Path

import networkx as nx

from graphwatch.graph.analysis import AnalysisResult
from graphwatch.report.entity_export import build_entity_payload

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _read(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def slugify(label: str) -> str:
    return _SLUG_RE.sub("-", label.lower()).strip("-") or "entite"


def generate_entity_view(
    graph: nx.Graph, analysis: AnalysisResult, node_id: str, *,
    output_path: Path, source_name: str, generated_at: str,
    min_corroborating_sources: int, setup: dict | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_entity_payload(
        graph, analysis, node_id, source_name=source_name, generated_at=generated_at,
        min_corroborating_sources=min_corroborating_sources, setup=setup,
    )
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</script", "<\\/script")

    css, js = _read("entity_view.css"), _read("entity_view.js")
    e = payload["entity"]

    warn = ""
    if e["lowConfidence"]:
        warn = f'<span class="warn-badge">⚠ corroboré par &lt; {min_corroborating_sources} document(s)</span>'

    aliases_html = ""
    if e["aliases"]:
        chips = "".join(f'<span class="chip">{_esc(a)}</span>' for a in e["aliases"])
        aliases_html = f'<div style="margin-top:14px"><div class="chip-list">{chips}</div></div>'

    sources_html = "".join(f'<span class="chip">{_esc(s)}</span>' for s in e["sources"])

    rel_cards = []
    for r in payload["relations"]:
        low = ' low-conf' if r["credibility"] >= 5 else ""
        snippet = f'<div class="rel-snippet">« {_esc(r["snippets"][0])} »</div>' if r["snippets"] else ""
        src_chips = "".join(f'<span class="chip">{_esc(s)}</span>' for s in r["sources"][:6])
        rel_cards.append(f"""<div class="rel-card{low}" id="rel-{_esc(r['otherId'])}">
  <div class="rel-head">
    <span class="rel-target">{_esc(r['otherLabel'])}</span>
    <span class="rel-count">×{r['weight']} · fiab. {r['reliability']} · créd. {r['credibility']}/6</span>
  </div>
  <div class="rel-predicates">{_esc(', '.join(r['predicates']))}</div>
  {snippet}
  <div class="chip-list" style="margin-top:8px">{src_chips}</div>
</div>""")

    body = f"""<div class="wrap">
  <div class="header">
    <div>
      <div class="name">{_esc(e['label'])}</div>
      <div class="meta">source {_esc(source_name)} · généré {generated_at}</div>
      <div style="margin-top:10px">
        <span class="community-tag" style="background:{communityBg(e['community'])};color:{communityFg(e['community'])}">communauté #{e['community']}</span>
        <span class="badge-adm {admClass(e['reliability'], is_reliability=True)}">fiab. {e['reliability']}</span>
        <span class="badge-adm {admClass(e['credibility'], is_reliability=False)}">créd. {e['credibility']}/6</span>
        {warn}
      </div>
      {aliases_html}
    </div>
  </div>

  <div class="stat-row">
    <div class="stat-tile"><div class="v">{e['mentions']}</div><div class="k">mentions</div></div>
    <div class="stat-tile"><div class="v">{len(payload['relations'])}</div><div class="k">relations</div></div>
    <div class="stat-tile"><div class="v">{e['pagerank']:.4f}</div><div class="k">pagerank</div></div>
    <div class="stat-tile"><div class="v">{e['betweenness']:.4f}</div><div class="k">betweenness</div></div>
    <div class="stat-tile"><div class="v">{len(e['sources'])}</div><div class="k">sources</div></div>
  </div>

  <h2>Réseau direct</h2>
  <div id="ego-stage">
    <canvas id="ego-canvas"></canvas>
    <div class="ego-hint">survole = détail · clic = va à la relation · pointillé = peu corroboré</div>
    <div id="tooltip" class="tooltip"></div>
  </div>

  <h2>Sources ({len(e['sources'])})</h2>
  <div class="chip-list">{sources_html}</div>

  <h2>Relations ({len(payload['relations'])})</h2>
  {''.join(rel_cards) if rel_cards else '<p style="color:var(--ink-dim)">Aucune relation enregistrée.</p>'}

  <div class="footer-note">
    Première mention : {e['firstSeen'] or 'n/a'} · Dernière mention : {e['lastSeen'] or 'n/a'}.<br>
    La crédibilité (1–6) est une heuristique (fiabilité de la source × nombre de documents indépendants),
    pas un verdict — à vérifier avant toute conclusion.
  </div>
</div>

<script id="entity-data" type="application/json">{payload_json}</script>
<script>
{js}
</script>
"""

    html = f"""<title>{_esc(e['label'])} — fiche</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{css}
</style>
{body}"""

    output_path.write_text(html, encoding="utf-8")
    return output_path


_COMMUNITY_COLORS = ["#4fb3a9", "#d99a5b", "#8f8fd9", "#d98fa0", "#8fbf8a", "#6fa8d9", "#c2a15c", "#5cb0d9"]


def communityFg(i: int) -> str:
    return _COMMUNITY_COLORS[i % len(_COMMUNITY_COLORS)]


def communityBg(i: int) -> str:
    hexc = _COMMUNITY_COLORS[i % len(_COMMUNITY_COLORS)].lstrip("#")
    r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
    return f"rgba({r},{g},{b},0.18)"


def admClass(value, *, is_reliability: bool) -> str:
    if is_reliability:
        if value in ("A", "B"):
            return "good"
        if value == "C":
            return "mid"
        return "unknown"
    if value <= 2:
        return "good"
    if value <= 4:
        return "mid"
    return "unknown"


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
