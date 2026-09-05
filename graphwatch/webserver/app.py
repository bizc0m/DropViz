"""Interface locale glisser-déposer + URL pour alimenter une source
`corpus_folder` sans passer par le CLI. Tourne sur la machine de
l'utilisateur (`python run.py webui`) : la récupération d'URL utilise SA
connexion réseau, pas le sandbox d'exécution de l'agent."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from graphwatch.config import AppConfig, SourceConfig, load_config
from graphwatch.pipeline import CycleResult, run_cycle
from graphwatch.propagation_pipeline import PropagationCycleResult
from graphwatch.webserver.url_fetch import FetchError, fetch_url_text

log = logging.getLogger(__name__)
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _read(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _safe_filename(name: str) -> str:
    name = Path(name).name  # retire tout chemin, garde le nom de fichier seul
    return name or "upload.txt"


def _unique_dest(folder: Path, filename: str) -> Path:
    dest = folder / filename
    if not dest.exists():
        return dest
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 1
    while (folder / f"{stem}-{i}{suffix}").exists():
        i += 1
    return folder / f"{stem}-{i}{suffix}"


def _get_corpus_source(app_config: AppConfig, name: str) -> SourceConfig:
    for s in app_config.sources:
        if s.name == name and s.type == "corpus_folder":
            return s
    raise HTTPException(404, f"source corpus_folder inconnue: {name}")


def _result_payload(saved: list[str], result) -> dict:
    payload = {"ok": True, "saved": saved, "message": f"{len(saved)} fichier(s) ajouté(s)"}
    if isinstance(result, CycleResult):
        payload["notebook_url"] = f"/reports/{result.notebook_path.name}"
        payload["graph_url"] = f"/reports/{result.html_graph_path.name}"
        payload["json_url"] = f"/reports/{result.json_path.name}"
        payload["markdown_url"] = f"/reports/{result.markdown_path.name}"
        payload["graphml_url"] = f"/reports/{result.graphml_path.name}"
        payload["entity_urls"] = [f"/reports/{p.name}" for p in result.entity_paths]
        if result.index_path:
            payload["index_url"] = f"/reports/{result.index_path.name}"
    elif isinstance(result, PropagationCycleResult):
        payload["propagation_urls"] = [f"/reports/{p.name}" for p in result.reports.values()]
        payload["propagation_json_urls"] = [f"/reports/{p.name}" for p in result.json_reports.values()]
    else:
        payload["message"] += " (aucun rapport régénéré)"
    return payload


def _render_index(corpus_sources: list[SourceConfig]) -> str:
    css, js = _read("index.css"), _read("index.js")

    reports_link = '<p class="subtitle"><a href="/reports/index.html">→ voir tous les rapports générés</a></p>'

    if not corpus_sources:
        body = f"""<div class="wrap"><h1>graph-watch</h1>{reports_link}
<div class="empty-note">Aucune source de type <code>corpus_folder</code> dans ta config.
Ajoute-en une dans <code>config.yaml</code> (voir <code>config.example.yaml</code>)
puis recharge cette page.</div></div>"""
        return _shell(css, js, body)

    options = "".join(f'<option value="{s.name}">{s.name} ({s.options.get("path", "?")})</option>' for s in corpus_sources)

    body = f"""<div id="drop-overlay" class="drop-overlay"><div class="drop-overlay-msg">Lâche ici pour ajouter</div></div>
<div class="wrap">
<h1>graph-watch</h1>
{reports_link}
<p class="subtitle">Glisse des fichiers <strong>n'importe où sur la page</strong>, colle une URL, ou colle
du texte en vrac — ça les ajoute à la source choisie et relance immédiatement un cycle d'analyse.
Les fichiers sont écrits directement dans le dossier de la source (<code>corpus_folder</code>),
rien n'est envoyé ailleurs.</p>

<label for="source-select">Source cible</label>
<select id="source-select">{options}</select>

<label>Fichiers</label>
<div id="dropzone" class="dropzone">
  <div class="icon">⤓</div>
  <div class="main">Glisse des fichiers ici, ou clique pour parcourir</div>
  <div class="hint">.txt .md .html .pdf .json .jsonl .csv — un lien glissé depuis l'onglet marche aussi</div>
  <input type="file" id="file-input" multiple>
</div>

<label for="url-input">Ou une URL</label>
<div class="url-row">
  <input type="text" id="url-input" placeholder="https://...">
  <button class="primary" id="url-btn">Ajouter</button>
</div>

<label for="paste-input">Ou colle du texte en vrac (markdown, notes, tout format)</label>
<textarea id="paste-input" placeholder="Colle ici n'importe quel texte -- brouillon, notes en bordel, extrait -- ça part dans le même pipeline qu'un fichier."></textarea>
<div class="paste-row">
  <button class="primary" id="paste-btn">Analyser ce texte</button>
</div>

<div id="log" class="log"></div>
</div>"""
    return _shell(css, js, body)


def _shell(css: str, js: str, body: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>graph-watch — ajouter du contenu</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body>{body}<script>{js}</script></body></html>"""


def create_app(config_path: str | Path) -> FastAPI:
    config_path = Path(config_path)
    app = FastAPI(title="graph-watch")

    @app.get("/", response_class=HTMLResponse)
    def index():
        app_config = load_config(config_path)
        corpus_sources = [s for s in app_config.sources if s.type == "corpus_folder"]
        return HTMLResponse(_render_index(corpus_sources))

    @app.post("/api/upload")
    async def upload(source: str = Form(...), files: list[UploadFile] = File(...)):
        app_config = load_config(config_path)
        source_cfg = _get_corpus_source(app_config, source)
        folder = Path(source_cfg.options["path"])
        folder.mkdir(parents=True, exist_ok=True)

        saved = []
        for f in files:
            data = await f.read()
            if len(data) > 20_000_000:
                log.warning("fichier %s ignoré (> 20 Mo)", f.filename)
                continue
            dest = _unique_dest(folder, _safe_filename(f.filename or "upload.txt"))
            dest.write_bytes(data)
            saved.append(dest.name)

        if not saved:
            raise HTTPException(400, "aucun fichier valide reçu")

        result = run_cycle(app_config, source_cfg, force_report=True)
        log.info("[webui] %d fichier(s) ajoutés à '%s'", len(saved), source_cfg.name)
        return JSONResponse(_result_payload(saved, result))

    @app.post("/api/fetch-url")
    async def fetch_url_endpoint(payload: dict):
        url = str(payload.get("url", "")).strip()
        source = str(payload.get("source", ""))
        if not url:
            raise HTTPException(400, "url manquante")

        app_config = load_config(config_path)
        source_cfg = _get_corpus_source(app_config, source)
        folder = Path(source_cfg.options["path"])
        folder.mkdir(parents=True, exist_ok=True)

        try:
            title, html = fetch_url_text(url)
        except FetchError as e:
            raise HTTPException(422, str(e)) from e

        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        dest = folder / f"url-{digest}.html"
        dest.write_text(f"<!-- source: {url} -->\n<title>{title}</title>\n{html}", encoding="utf-8")

        result = run_cycle(app_config, source_cfg, force_report=True)
        log.info("[webui] URL ajoutée à '%s': %s", source_cfg.name, url)
        return JSONResponse(_result_payload([dest.name], result))

    app_config = load_config(config_path)
    app_config.global_.notebooks_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/reports", StaticFiles(directory=str(app_config.global_.notebooks_dir)), name="reports")

    return app
