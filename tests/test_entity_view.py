"""Test de fumée : fiches individuelles auto-générées (top pagerank) et
recherche d'entité par nom (graphwatch.report.entity_export.find_entity)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from graphwatch.config import AppConfig, GlobalConfig, LLMConfig, SourceConfig
from graphwatch.pipeline import run_cycle
from graphwatch.report.entity_export import find_entity

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_auto_entity_profiles_generated():
    import pytest
    pytest.importorskip("spacy")
    import spacy.util
    if not spacy.util.is_package("fr_core_news_sm") and not spacy.util.is_package("fr_core_news_md"):
        pytest.skip("aucun modèle spaCy fr installé")
    model = "fr_core_news_md" if spacy.util.is_package("fr_core_news_md") else "fr_core_news_sm"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir, notebooks_dir = tmp / "data", tmp / "notebooks"
        data_dir.mkdir(parents=True)
        notebooks_dir.mkdir(parents=True)

        global_cfg = GlobalConfig(
            extractor="spacy", spacy_model=model, llm=LLMConfig(), graph_mode="shared",
            data_dir=data_dir, notebooks_dir=notebooks_dir, min_corroborating_sources=1,
        )
        source_cfg = SourceConfig(
            name="test-entity", type="corpus_folder", interval_minutes=1440,
            extractor="spacy", options={"path": str(REPO_ROOT / "corpus_sample")}, reliability="B",
        )
        app_config = AppConfig(global_=global_cfg, sources=[source_cfg])

        result = run_cycle(app_config, source_cfg)

        assert result is not None
        assert len(result.entity_paths) > 0
        for p in result.entity_paths:
            assert p.exists()
            html = p.read_text(encoding="utf-8")
            assert "ego-canvas" in html
            assert "rel-card" in html or "Aucune relation" in html

        # find_entity : match exact, sous-chaîne unique, et ambiguïté -> None
        from graphwatch.graph.store import GraphStore
        graph = GraphStore(data_dir, graph_key="shared").load_live()
        any_label = next(iter(graph.nodes(data=True)))[1]["label"]
        assert find_entity(graph, any_label) is not None
        assert find_entity(graph, "ceci-nexiste-pas-du-tout-xyz") is None
