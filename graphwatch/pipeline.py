"""Orchestre un cycle complet pour une source : fetch -> stocke -> extrait ->
fusionne dans le graphe -> analyse -> génère le notebook + le graphe interactif."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from graphwatch import __version__ as graphwatch_version
from graphwatch.config import AppConfig, SourceConfig
from graphwatch.extract import build_extractor
from graphwatch.graph.analysis import run_full_analysis
from graphwatch.graph.builder import merge_relations
from graphwatch.graph.store import GraphStore
from graphwatch.ingest.store import DocumentStore
from graphwatch.propagation_pipeline import PropagationCycleResult, run_propagation_cycle
from graphwatch.report.entity_view import generate_entity_view, slugify
from graphwatch.report.graph_export import annotate_for_gephi, build_payload
from graphwatch.report.html_graph import generate_html_graph
from graphwatch.report.index_view import generate_index
from graphwatch.report.markdown_report import generate_markdown_report
from graphwatch.report.notebook_generator import generate_notebook
from graphwatch.sources import build_source

log = logging.getLogger(__name__)

# nombre de fiches individuelles générées automatiquement par cycle, pour les
# entités les plus centrales -- n'importe quelle autre entité reste accessible
# à la demande via `python run.py entity NAME`
AUTO_ENTITY_PROFILES = 5


@dataclass
class CycleResult:
    notebook_path: Path
    html_graph_path: Path
    json_path: Path
    markdown_path: Path
    graphml_path: Path
    entity_paths: list[Path] = field(default_factory=list)
    index_path: Path | None = None
    n_new_docs: int = 0


def run_cycle(
    app_config: AppConfig, source_cfg: SourceConfig, force_report: bool = False
) -> CycleResult | PropagationCycleResult | None:
    """Exécute un cycle pour `source_cfg`. Renvoie les chemins générés,
    ou None si rien de nouveau n'a été traité (et force_report=False).

    Les sources 'post_thread' (analyse de propagation) suivent un pipeline
    entièrement différent -- pas de texte à passer au NER, juste des posts
    déjà structurés -- d'où la délégation immédiate."""
    if source_cfg.type == "post_thread":
        return run_propagation_cycle(app_config, source_cfg, force_report=force_report)

    g = app_config.global_

    doc_store = DocumentStore(g.data_dir / "documents.db")
    graph_key = "shared" if g.graph_mode == "shared" else source_cfg.name
    graph_store = GraphStore(g.data_dir, graph_key=graph_key)

    log.info("[%s] fetch...", source_cfg.name)
    source = build_source(source_cfg)
    fetched = list(source.fetch())

    new_docs = [d for d in fetched if doc_store.add_if_new(d)]
    log.info("[%s] %d document(s) récupérés, %d nouveau(x)", source_cfg.name, len(fetched), len(new_docs))

    if not new_docs and not force_report:
        return None

    extractor = build_extractor(source_cfg.extractor, source_cfg, g)
    relations = []
    for doc in new_docs:
        try:
            doc_relations = extractor.extract(doc)
            for rel in doc_relations:
                rel.source_reliability = source_cfg.reliability  # jugement humain, pas déduit
            relations.extend(doc_relations)
        except Exception:
            log.exception("[%s] extraction échouée pour doc %s (%s)", source_cfg.name, doc.doc_id, doc.origin)

    log.info("[%s] %d relation(s) extraite(s)", source_cfg.name, len(relations))

    graph = graph_store.load_live()
    graph = merge_relations(graph, relations)
    graph_store.save_live(graph)
    snapshot_path = graph_store.snapshot(graph, label=source_cfg.name)

    doc_store.mark_processed([d.doc_id for d in new_docs])

    analysis = run_full_analysis(graph, min_corroborating_sources=g.min_corroborating_sources)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    generated_at = datetime.now(timezone.utc).isoformat()
    cycle_meta = {"source_name": source_cfg.name, "generated_at": generated_at, "n_new_docs": len(new_docs)}
    base = g.notebooks_dir / f"{source_cfg.name}__{ts}"

    notebook_path = generate_notebook(
        cycle_meta=cycle_meta,
        graph_snapshot_path=snapshot_path,
        graph=graph,
        analysis=analysis,
        output_path=base.with_suffix(".ipynb"),
        min_corroborating_sources=g.min_corroborating_sources,
    )
    html_graph_path = generate_html_graph(
        graph=graph,
        analysis=analysis,
        output_path=base.with_suffix(".html"),
        min_corroborating_sources=g.min_corroborating_sources,
        source_name=source_cfg.name,
        generated_at=generated_at,
        n_new_docs=len(new_docs),
    )

    # exports bruts, pour brancher le graphe dans un autre outil (script, LLM,
    # wiki) sans repasser par le HTML ou le notebook -- "setup" rend le JSON
    # auto-descriptif : d'où vient chaque relation ET comment ce cycle a tourné.
    setup = {
        "graphwatchVersion": graphwatch_version,
        "source": {
            "name": source_cfg.name,
            "type": source_cfg.type,
            "extractor": source_cfg.extractor,
            "reliability": source_cfg.reliability,
            "intervalMinutes": source_cfg.interval_minutes,
            "options": source_cfg.options,
        },
        "global": {
            "graphMode": g.graph_mode,
            "minCorroboratingSources": g.min_corroborating_sources,
            "spacyModel": g.spacy_model if source_cfg.extractor == "spacy" else None,
            "llmModel": g.llm.model if source_cfg.extractor == "llm" else None,
        },
    }
    payload = build_payload(
        graph, analysis, source_name=source_cfg.name, generated_at=generated_at,
        n_new_docs=len(new_docs), min_corroborating_sources=g.min_corroborating_sources,
        setup=setup,
    )
    json_path = base.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    markdown_path = generate_markdown_report(
        cycle_meta=cycle_meta, graph=graph, analysis=analysis,
        output_path=base.with_suffix(".md"), min_corroborating_sources=g.min_corroborating_sources,
    )

    graphml_path = base.with_suffix(".graphml")
    graph_store.export_graphml(annotate_for_gephi(graph, analysis), graphml_path)

    # fiches individuelles auto-générées pour les entités les plus centrales --
    # n'importe quelle autre entité reste accessible via `python run.py entity NAME`
    entity_paths: list[Path] = []
    top_entities = sorted(
        analysis.centrality.get("pagerank", {}).items(), key=lambda kv: kv[1], reverse=True
    )[:AUTO_ENTITY_PROFILES]
    for node_id, _score in top_entities:
        label = graph.nodes[node_id].get("label", node_id)
        entity_path = generate_entity_view(
            graph, analysis, node_id,
            output_path=g.notebooks_dir / f"{base.name}__entity-{slugify(label)}.html",
            source_name=source_cfg.name, generated_at=generated_at,
            min_corroborating_sources=g.min_corroborating_sources, setup=setup,
        )
        entity_paths.append(entity_path)

    index_path = generate_index(g.notebooks_dir)

    log.info("[%s] notebook=%s graphe=%s json=%s md=%s graphml=%s +%d fiche(s)",
              source_cfg.name, notebook_path.name, html_graph_path.name,
              json_path.name, markdown_path.name, graphml_path.name, len(entity_paths))
    return CycleResult(
        notebook_path=notebook_path, html_graph_path=html_graph_path,
        json_path=json_path, markdown_path=markdown_path, graphml_path=graphml_path,
        entity_paths=entity_paths, index_path=index_path, n_new_docs=len(new_docs),
    )
