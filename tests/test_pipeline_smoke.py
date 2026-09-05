"""Test de fumée : fait tourner un cycle complet (corpus_folder -> spaCy ->
graphe -> notebook) sur les fichiers d'exemple, sans réseau ni clé API."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from graphwatch.config import AppConfig, GlobalConfig, LLMConfig, SourceConfig
from graphwatch.pipeline import run_cycle

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("dummy", [True])
def test_full_cycle_corpus_folder_spacy(dummy):
    pytest.importorskip("spacy")
    import spacy.util
    if not spacy.util.is_package("fr_core_news_sm") and not spacy.util.is_package("fr_core_news_md"):
        pytest.skip("aucun modèle spaCy fr installé — voir README pour l'installation")
    model = "fr_core_news_md" if spacy.util.is_package("fr_core_news_md") else "fr_core_news_sm"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir = tmp / "data"
        notebooks_dir = tmp / "notebooks"

        global_cfg = GlobalConfig(
            extractor="spacy",
            spacy_model=model,
            llm=LLMConfig(),
            graph_mode="shared",
            data_dir=data_dir,
            notebooks_dir=notebooks_dir,
            min_corroborating_sources=1,
        )
        source_cfg = SourceConfig(
            name="test-corpus",
            type="corpus_folder",
            interval_minutes=1440,
            extractor="spacy",
            options={"path": str(REPO_ROOT / "corpus_sample")},
            reliability="B",
        )
        app_config = AppConfig(global_=global_cfg, sources=[source_cfg])
        data_dir.mkdir(parents=True)
        notebooks_dir.mkdir(parents=True)

        result = run_cycle(app_config, source_cfg)

        assert result is not None
        assert result.notebook_path.exists()
        assert result.notebook_path.suffix == ".ipynb"
        assert result.html_graph_path.exists()
        assert result.html_graph_path.suffix == ".html"
        html = result.html_graph_path.read_text(encoding="utf-8")
        assert "graph-canvas" in html
        assert "badge-adm" in html  # badges Admiralty présents dans le template

        # exports bruts (JSON / Markdown / GraphML), pour brancher le graphe ailleurs
        assert result.json_path.exists()
        payload = json.loads(result.json_path.read_text(encoding="utf-8"))
        assert payload["meta"]["nNodes"] == len(payload["nodes"])
        assert len(payload["nodes"]) > 0
        assert payload["meta"]["setup"]["source"]["name"] == "test-corpus"
        assert payload["meta"]["setup"]["source"]["reliability"] == "B"
        assert payload["meta"]["setup"]["global"]["spacyModel"] == model

        assert result.markdown_path.exists()
        md = result.markdown_path.read_text(encoding="utf-8")
        assert md.startswith("# Rapport")
        assert "PageRank" in md

        assert result.index_path is not None
        assert result.index_path.exists()
        assert result.index_path.name == "index.html"
        index_html = result.index_path.read_text(encoding="utf-8")
        assert f'href="{result.html_graph_path.name}"' in index_html

        assert result.graphml_path.exists()
        graphml_text = result.graphml_path.read_text(encoding="utf-8")
        assert "<graphml" in graphml_text
        # pas juste la provenance brute : les métriques calculées doivent être
        # dedans, sinon Gephi n'a rien à mapper sur taille/couleur à l'ouverture
        import networkx as nx
        reloaded = nx.read_graphml(result.graphml_path)
        first_node_attrs = next(iter(reloaded.nodes(data=True)))[1]
        assert "pagerank" in first_node_attrs
        assert "community" in first_node_attrs
        assert "credibility" in first_node_attrs

        # un deuxième passage sans nouveau fichier ne doit rien régénérer
        second = run_cycle(app_config, source_cfg)
        assert second is None
