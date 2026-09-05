"""Test de fumée pour l'interface glisser-déposer : sert la page, upload un
fichier via l'API, vérifie que le cycle tourne et que le rapport est servi.
N'utilise pas le réseau (TestClient, pas de port réel ; /api/fetch-url n'est
pas testé ici car il dépend d'une vraie connexion internet)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from graphwatch.webserver.app import create_app

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def app_client():
    pytest.importorskip("spacy")
    import spacy.util
    if not spacy.util.is_package("fr_core_news_sm") and not spacy.util.is_package("fr_core_news_md"):
        pytest.skip("aucun modèle spaCy fr installé")
    model = "fr_core_news_md" if spacy.util.is_package("fr_core_news_md") else "fr_core_news_sm"

    fastapi_testclient = pytest.importorskip("fastapi.testclient")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        drop_dir = tmp / "dropped"
        drop_dir.mkdir()
        config = {
            "global": {"extractor": "spacy", "spacy": {"model": model},
                       "data_dir": str(tmp / "data"), "notebooks_dir": str(tmp / "notebooks"),
                       "min_corroborating_sources": 1},
            "sources": [{"name": "webui-test", "type": "corpus_folder", "path": str(drop_dir),
                         "interval_minutes": 1440, "extractor": "spacy", "reliability": "B"}],
        }
        config_path = tmp / "config.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        app = create_app(config_path)
        client = fastapi_testclient.TestClient(app)
        yield client


def test_index_page_lists_source(app_client):
    resp = app_client.get("/")
    assert resp.status_code == 200
    assert "webui-test" in resp.text
    assert "dropzone" in resp.text
    assert "paste-input" in resp.text  # champ texte libre (coller du "bordel" directement)
    assert "drop-overlay" in resp.text  # drag & drop global, pas juste la petite boîte


def test_paste_text_uses_same_upload_pipeline(app_client):
    # ce que fait le JS du champ "coller du texte" : fabrique un .md en mémoire
    # et repasse par /api/upload -- même chemin qu'un fichier glissé, pas d'endpoint à part.
    content = "Notes en vrac : la Fondation Clairval finance l'Institut Servan a Grenoble.\n"
    resp = app_client.post(
        "/api/upload",
        data={"source": "webui-test"},
        files={"files": ("colle-2026-01-01T00-00-00-000Z.md", content.encode("utf-8"), "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "graph_url" in data


def test_upload_triggers_cycle_and_serves_report(app_client):
    content = b"La Fondation Clairval a annonce un partenariat avec l'Institut Servan a Grenoble."
    resp = app_client.post(
        "/api/upload",
        data={"source": "webui-test"},
        files={"files": ("note.txt", content, "text/plain")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["saved"] == ["note.txt"]
    assert "graph_url" in data

    report_resp = app_client.get(data["graph_url"])
    assert report_resp.status_code == 200
    assert "graph-canvas" in report_resp.text


def test_upload_markdown_file(app_client):
    content = (
        b"# Note\n\nLa **Fondation Clairval** a annonce un partenariat avec "
        b"l'Institut Servan a Grenoble.\n"
    )
    resp = app_client.post(
        "/api/upload",
        data={"source": "webui-test"},
        files={"files": ("note.md", content, "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["saved"] == ["note.md"]
    assert "graph_url" in data

    report_resp = app_client.get(data["graph_url"])
    assert report_resp.status_code == 200
    assert "graph-canvas" in report_resp.text


def test_fetch_url_rejects_bad_scheme(app_client):
    resp = app_client.post("/api/fetch-url", json={"url": "ftp://example.com", "source": "webui-test"})
    assert resp.status_code == 422
