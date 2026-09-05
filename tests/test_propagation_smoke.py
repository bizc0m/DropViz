"""Test de fumée : cycle complet d'analyse de propagation (post_thread ->
seed/bursts/propagateurs -> vue HTML) sur le jeu de données d'exemple."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from graphwatch.config import AppConfig, GlobalConfig, LLMConfig, SourceConfig
from graphwatch.pipeline import run_cycle
from graphwatch.propagation_pipeline import PropagationCycleResult

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_propagation_cycle():
    posts_dir = REPO_ROOT / "posts_sample"
    if not any(posts_dir.glob("*.jsonl")):
        import subprocess
        subprocess.run(["python", str(REPO_ROOT / "scripts" / "generate_sample_posts.py")], check=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_dir, notebooks_dir = tmp / "data", tmp / "notebooks"
        data_dir.mkdir(parents=True)
        notebooks_dir.mkdir(parents=True)

        global_cfg = GlobalConfig(
            extractor="spacy", llm=LLMConfig(), graph_mode="shared",
            data_dir=data_dir, notebooks_dir=notebooks_dir, min_corroborating_sources=1,
        )
        source_cfg = SourceConfig(
            name="test-propagation", type="post_thread", interval_minutes=1440,
            extractor="spacy", options={"path": str(posts_dir)},
        )
        app_config = AppConfig(global_=global_cfg, sources=[source_cfg])

        result = run_cycle(app_config, source_cfg)

        assert isinstance(result, PropagationCycleResult)
        assert result.n_new_posts > 0
        assert "fermeture-parc-central" in result.reports
        report_path = result.reports["fermeture-parc-central"]
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert "tree-canvas" in html
        assert "burst-canvas" in html

        assert "fermeture-parc-central" in result.json_reports
        json_path = result.json_reports["fermeture-parc-central"]
        assert json_path.exists()
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["meta"]["setup"]["source"]["name"] == "test-propagation"
        assert payload["meta"]["totalPosts"] == len(payload["posts"])

        # deuxième passage sans nouveau post -> rien de nouveau
        second = run_cycle(app_config, source_cfg)
        assert second is None
