"""Cycle pour une source de type 'post_thread' : ingestion de posts déjà
structurés (fil retweet/quote/reply) -> analyse de propagation par rumeur.

Séparé de pipeline.py car la donnée d'entrée (posts avec threading explicite)
n'a rien à voir avec le pipeline texte->NER des autres types de sources."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from graphwatch import __version__ as graphwatch_version
from graphwatch.config import AppConfig, SourceConfig
from graphwatch.propagation.analysis import run_propagation_analysis
from graphwatch.propagation.export import build_propagation_payload
from graphwatch.propagation.ingest import read_posts_from_folder
from graphwatch.propagation.store import PostStore
from graphwatch.report.index_view import generate_index
from graphwatch.report.propagation_view import generate_propagation_view

log = logging.getLogger(__name__)


@dataclass
class PropagationCycleResult:
    reports: dict[str, Path]  # rumeur -> chemin du rapport HTML généré
    json_reports: dict[str, Path] = field(default_factory=dict)  # rumeur -> chemin du JSON brut
    n_new_posts: int = 0


def run_propagation_cycle(
    app_config: AppConfig, source_cfg: SourceConfig, force_report: bool = False
) -> PropagationCycleResult | None:
    g = app_config.global_
    path = source_cfg.options.get("path")
    if not path:
        raise ValueError(f"source post_thread '{source_cfg.name}' sans 'path' dans la config")

    post_store = PostStore(g.data_dir / "posts.db")

    log.info("[%s] fetch posts...", source_cfg.name)
    fetched = read_posts_from_folder(path, source_cfg.name)
    new_posts = [p for p in fetched if post_store.add_if_new(p)]
    log.info("[%s] %d post(s) lus, %d nouveau(x)", source_cfg.name, len(fetched), len(new_posts))

    if not new_posts and not force_report:
        return None

    rumors = {p.rumor for p in new_posts} or set(post_store.rumors())
    if force_report:
        rumors |= set(post_store.rumors())

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    generated_at = datetime.now(timezone.utc).isoformat()
    reports: dict[str, Path] = {}
    json_reports: dict[str, Path] = {}

    setup = {
        "graphwatchVersion": graphwatch_version,
        "source": {
            "name": source_cfg.name, "type": source_cfg.type,
            "intervalMinutes": source_cfg.interval_minutes, "options": source_cfg.options,
        },
    }

    for rumor in sorted(rumors):
        posts = post_store.posts_for_rumor(rumor)
        if not posts:
            continue
        result = run_propagation_analysis(rumor, posts)
        base = g.notebooks_dir / f"{source_cfg.name}__{rumor}__{ts}_propagation"

        output_path = generate_propagation_view(
            rumor=rumor, posts=posts, result=result,
            output_path=base.with_suffix(".html"),
            source_name=source_cfg.name, generated_at=generated_at, setup=setup,
        )

        payload = build_propagation_payload(
            rumor=rumor, posts=posts, result=result,
            source_name=source_cfg.name, generated_at=generated_at, setup=setup,
        )
        json_path = base.with_suffix(".json")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        log.info("[%s] rumeur '%s': graine=%s, arbre=%d posts, %d burst(s) -> %s (+%s)",
                  source_cfg.name, rumor, result.seed_post_id, result.tree_size,
                  len(result.bursts), output_path.name, json_path.name)
        reports[rumor] = output_path
        json_reports[rumor] = json_path

    generate_index(g.notebooks_dir)
    return PropagationCycleResult(reports=reports, json_reports=json_reports, n_new_posts=len(new_posts))
