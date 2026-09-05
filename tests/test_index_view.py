"""La page d'accueil unique doit toujours refléter ce qui est réellement dans
notebooks/ -- jamais un lien mort, jamais un fichier généré mais invisible."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

from graphwatch.report.index_view import generate_index


def _touch(path: Path, content: str = "x") -> None:
    path.write_text(content, encoding="utf-8")
    time.sleep(0.01)  # garantit des mtimes distincts pour le tri


def test_generate_index_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        notebooks_dir = Path(tmp)
        output_path = generate_index(notebooks_dir)

        assert output_path == notebooks_dir / "index.html"
        assert output_path.exists()
        html = output_path.read_text(encoding="utf-8")
        assert "graph-watch" in html
        assert "Aucun graphe" in html
        assert "Aucune analyse de propagation" in html
        assert "Aucune fiche" in html


def test_generate_index_categorizes_and_links_real_files():
    with tempfile.TemporaryDirectory() as tmp:
        notebooks_dir = Path(tmp)

        # deux snapshots de la même source -> seul le plus récent doit apparaître
        _touch(notebooks_dir / "source-a__20260101T000000Z.html")
        _touch(notebooks_dir / "source-a__20260102T000000Z.html")
        _touch(notebooks_dir / "source-b__20260101T120000Z.html")
        _touch(notebooks_dir / "source-a__20260102T000000Z__entity-jean-dupont.html")
        _touch(notebooks_dir / "propag-src__une-rumeur__20260103T000000Z_propagation.html")
        # un notebook .ipynb ne doit jamais apparaître dans la page (pas un lien HTML valide)
        _touch(notebooks_dir / "source-a__20260102T000000Z.ipynb")

        output_path = generate_index(notebooks_dir)
        html = output_path.read_text(encoding="utf-8")

        assert 'href="source-a__20260102T000000Z.html"' in html
        assert "source-a__20260101T000000Z.html" not in html  # ancien snapshot exclu
        assert 'href="source-b__20260101T120000Z.html"' in html
        assert 'href="source-a__20260102T000000Z__entity-jean-dupont.html"' in html
        assert "Jean Dupont" in html  # slug -> titre lisible
        assert 'href="propag-src__une-rumeur__20260103T000000Z_propagation.html"' in html
        assert "une-rumeur" in html
        assert ".ipynb" not in html
        # ni graphe ni entité ni propagation classés comme "vide" une fois qu'il y a du contenu
        assert "Aucun graphe" not in html
        assert "Aucune fiche" not in html
        assert "Aucune analyse de propagation" not in html


def test_generate_index_is_idempotent_and_overwrites():
    with tempfile.TemporaryDirectory() as tmp:
        notebooks_dir = Path(tmp)
        _touch(notebooks_dir / "source-a__20260101T000000Z.html")

        first = generate_index(notebooks_dir)
        first_html = first.read_text(encoding="utf-8")

        _touch(notebooks_dir / "source-c__20260101T000000Z.html")
        second = generate_index(notebooks_dir)
        second_html = second.read_text(encoding="utf-8")

        assert first == second
        assert 'href="source-c__20260101T000000Z.html"' not in first_html
        assert 'href="source-c__20260101T000000Z.html"' in second_html
