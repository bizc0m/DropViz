"""Page d'accueil unique : scanne notebooks/ et relie tout ce qui a été généré
(graphes, propagation, fiches) -- régénérée automatiquement à chaque cycle,
donc toujours à jour, jamais un lien mort vers un fichier qui n'existe plus."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_ENTITY_RE = re.compile(r"^(?P<source>.+?)__\d{8}T\d{6}Z__entity-(?P<slug>.+)\.html$")
_PROPAGATION_RE = re.compile(r"^(?P<source>.+?)__(?P<rumor>.+?)__\d{8}T\d{6}Z_propagation\.html$")
_GRAPH_RE = re.compile(r"^(?P<source>.+?)__\d{8}T\d{6}Z\.html$")


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _read(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _card(title: str, meta: str, href: str) -> str:
    return f"""<a class="card" href="{_esc(href)}">
  <div class="card-title">{_esc(title)}</div>
  <div class="card-meta">{_esc(meta)}</div>
</a>"""


def generate_index(notebooks_dir: Path) -> Path:
    notebooks_dir = Path(notebooks_dir)
    files = sorted(notebooks_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)

    graphs, propagations, entities = {}, [], []
    for f in files:
        if m := _ENTITY_RE.match(f.name):
            entities.append((f, m.group("source"), m.group("slug")))
        elif m := _PROPAGATION_RE.match(f.name):
            propagations.append((f, m.group("source"), m.group("rumor")))
        elif m := _GRAPH_RE.match(f.name):
            source = m.group("source")
            if source not in graphs:  # le premier trouvé = le plus récent (tri déjà fait)
                graphs[source] = f

    def mtime_str(f: Path) -> str:
        return datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    graph_cards = "".join(
        _card(source, f"graphe interactif · {mtime_str(f)}", f.name)
        for source, f in graphs.items()
    ) or '<p class="empty">Aucun graphe généré pour l\'instant.</p>'

    propagation_cards = "".join(
        _card(f"{rumor}", f"propagation · source {source} · {mtime_str(f)}", f.name)
        for f, source, rumor in propagations[:20]
    ) or '<p class="empty">Aucune analyse de propagation pour l\'instant.</p>'

    entity_cards = "".join(
        _card(slug.replace("-", " ").title(), f"fiche · source {source} · {mtime_str(f)}", f.name)
        for f, source, slug in entities[:30]
    ) or '<p class="empty">Aucune fiche générée pour l\'instant.</p>'

    css = _read("index_view.css")
    body = f"""<div class="wrap">
  <h1>graph-watch</h1>
  <p class="subtitle">Régénéré automatiquement à chaque cycle — {len(graphs)} source(s), {len(propagations)} analyse(s) de propagation, {len(entities)} fiche(s).</p>

  <h2>Graphes</h2>
  <div class="card-grid">{graph_cards}</div>

  <h2>Propagation</h2>
  <div class="card-grid">{propagation_cards}</div>

  <h2>Fiches</h2>
  <div class="card-grid">{entity_cards}</div>
</div>"""

    html = f"""<title>graph-watch</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{css}
</style>
{body}"""

    output_path = notebooks_dir / "index.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path
