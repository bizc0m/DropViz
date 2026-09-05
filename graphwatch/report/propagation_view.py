"""Génère la vue interactive de propagation (arbre horizontal + frise de
bursts + top propagateurs) : un fichier HTML autonome, même famille de design
que html_graph.py mais pour une structure fondamentalement différente
(arbre temporel, pas un graphe de communautés)."""
from __future__ import annotations

import json
from pathlib import Path

from graphwatch.propagation.export import build_propagation_payload
from graphwatch.propagation.models import Post, PropagationResult

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _read(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def generate_propagation_view(
    *, rumor: str, posts: list[Post], result: PropagationResult,
    output_path: Path, source_name: str, generated_at: str, setup: dict | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_propagation_payload(
        rumor=rumor, posts=posts, result=result,
        source_name=source_name, generated_at=generated_at, setup=setup,
    )
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</script", "<\\/script")

    css = _read("propagation_view.css")
    js = _read("propagation_view.js")
    m = payload["meta"]

    html = f"""<title>Propagation — {rumor}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{css}
</style>

<div class="topbar">
  <div class="brand">
    <div class="name">Propagation — {rumor}</div>
    <div class="meta">source {source_name} · généré {generated_at}</div>
  </div>
  <div class="stat-row">
    <div class="stat-tile"><div class="v">{m['totalPosts']}</div><div class="k">posts</div></div>
    <div class="stat-tile"><div class="v">{m['treeSize']}</div><div class="k">dans l'arbre</div></div>
    <div class="stat-tile"><div class="v">{m['maxDepth']}</div><div class="k">profondeur</div></div>
    <div class="stat-tile"><div class="v">{m['uniqueAccounts']}</div><div class="k">comptes</div></div>
    <div class="stat-tile"><div class="v">{m['nBursts']}</div><div class="k">bursts</div></div>
    <div class="stat-tile"><div class="v">{m['unreachedPosts']}</div><div class="k">hors arbre</div></div>
  </div>
</div>

<div class="body-row">
  <div class="main-col">
    <div id="burst-strip">
      <canvas id="burst-canvas"></canvas>
      <div class="burst-hint">clique un burst pour isoler cette période dans l'arbre</div>
    </div>
    <div id="tree-stage">
      <canvas id="tree-canvas"></canvas>
      <div class="hint">glisser = panoramique · molette = zoom · clic = détail du post</div>
      <div id="tooltip" class="tooltip"></div>
    </div>
  </div>
  <div id="panel" class="panel"></div>
</div>

<script id="propagation-data" type="application/json">{payload_json}</script>
<script>
{js}
</script>
"""

    output_path.write_text(html, encoding="utf-8")
    return output_path
