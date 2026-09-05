"""Test de fumée : ingestion d'un vrai PDF (texte, pas image) via corpus_folder,
extraction du texte, passage dans le pipeline complet."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from graphwatch.config import AppConfig, GlobalConfig, LLMConfig, SourceConfig
from graphwatch.pipeline import run_cycle


def _make_test_pdf(path: Path) -> None:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(6, 4))
    fig.text(0.1, 0.8, "Le tribunal correctionnel de Nancy a condamne")
    fig.text(0.1, 0.7, "Denis Aubertin, ancien conseiller regional,")
    fig.text(0.1, 0.6, "a un an de prison avec sursis le 3 mai 2023.")
    fig.savefig(path)
    plt.close(fig)


def test_pdf_text_extraction_and_full_cycle():
    pytest.importorskip("spacy")
    pytest.importorskip("pypdf")
    import spacy.util
    if not spacy.util.is_package("fr_core_news_sm") and not spacy.util.is_package("fr_core_news_md"):
        pytest.skip("aucun modèle spaCy fr installé")
    model = "fr_core_news_md" if spacy.util.is_package("fr_core_news_md") else "fr_core_news_sm"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        corpus_dir, data_dir, notebooks_dir = tmp / "corpus", tmp / "data", tmp / "notebooks"
        corpus_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)
        notebooks_dir.mkdir(parents=True)

        _make_test_pdf(corpus_dir / "jugement.pdf")

        global_cfg = GlobalConfig(
            extractor="spacy", spacy_model=model, llm=LLMConfig(), graph_mode="shared",
            data_dir=data_dir, notebooks_dir=notebooks_dir, min_corroborating_sources=1,
        )
        source_cfg = SourceConfig(
            name="test-pdf", type="corpus_folder", interval_minutes=1440,
            extractor="spacy", options={"path": str(corpus_dir)}, reliability="A",
        )
        app_config = AppConfig(global_=global_cfg, sources=[source_cfg])

        result = run_cycle(app_config, source_cfg)

        assert result is not None
        payload_text = result.json_path.read_text(encoding="utf-8")
        assert "Aubertin" in payload_text or "aubertin" in payload_text.lower()
