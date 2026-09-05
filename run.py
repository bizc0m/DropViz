#!/usr/bin/env python3
"""Point d'entrée.

  python run.py serve                          -> scheduler persistant (tourne en continu)
  python run.py once [--source NAME] [--force]  -> un seul cycle puis quitte
  python run.py webui [--host 127.0.0.1] [--port 8765]
      -> interface glisser-déposer + URL, tourne avec TA connexion réseau

  python run.py propose --type rss --url URL --name NAME
  python run.py propose --type corpus_folder --path PATH --name NAME
  python run.py propose --type topic --query "..." --name NAME
  python run.py propose --type post_thread --path PATH --name NAME
      -> ajoute une adresse candidate à la file, avec aperçu, en attente de validation

  python run.py list-pending [--status pending|approved|rejected|all]
  python run.py approve NAME   -> la source devient active (suivie au prochain cycle)
  python run.py reject NAME

  python run.py entity "Marc Delassus" [--source NAME]
      -> fiche autonome pour CETTE entité (réseau direct, relations, sources) --
         pas besoin d'attendre le prochain cycle ni de faire partie du top 5 auto

  python run.py index
      -> régénère notebooks/index.html (un seul lien vers tout ce qui a été
         généré) -- automatique à chaque cycle, cette commande sert juste à
         la forcer à la demande (ex: après avoir supprimé un fichier à la main)
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from graphwatch.config import SourceConfig, append_approved_source, load_config
from graphwatch.graph.analysis import run_full_analysis
from graphwatch.graph.store import GraphStore
from graphwatch.pipeline import CycleResult, run_cycle
from graphwatch.propagation_pipeline import PropagationCycleResult
from graphwatch.queue import PendingQueue
from graphwatch.report.entity_export import find_entity
from graphwatch.report.entity_view import generate_entity_view, slugify
from graphwatch.report.index_view import generate_index
from graphwatch.scheduler import build_scheduler


def _port_is_free(host: str, port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _pick_port(host: str, requested: int) -> int:
    """Si le port demandé est déjà pris par autre chose sur la machine,
    bascule automatiquement sur le premier libre juste après -- au lieu de
    planter avec 'Address already in use', ce qui est de loin l'erreur la
    plus fréquente en pratique (un autre outil tourne déjà dessus)."""
    if _port_is_free(host, requested):
        return requested
    print(f"port {requested} déjà occupé (par un autre programme) -- recherche d'un port libre...")
    for candidate in range(requested + 1, requested + 51):
        if _port_is_free(host, candidate):
            return candidate
    raise RuntimeError(f"aucun port libre trouvé entre {requested} et {requested + 50}")


def cmd_webui(args) -> int:
    import uvicorn

    from graphwatch.webserver.app import create_app

    load_config(args.config)  # échoue tôt et clairement si la config est invalide
    app = create_app(args.config)
    port = _pick_port(args.host, args.port)
    print(f"graph-watch webui -> http://{args.host}:{port}  (Ctrl+C pour arrêter)")
    uvicorn.run(app, host=args.host, port=port, log_level="warning")
    return 0


def cmd_entity(args) -> int:
    app_config = load_config(args.config)
    g = app_config.global_

    if g.graph_mode == "shared":
        graph_key = "shared"
    else:
        if not args.source:
            print("mode per_source : --source requis pour savoir quel graphe charger", file=sys.stderr)
            return 1
        graph_key = args.source

    graph = GraphStore(g.data_dir, graph_key=graph_key).load_live()
    if graph.number_of_nodes() == 0:
        print("graphe vide -- lance au moins un cycle d'abord (`python run.py once`)", file=sys.stderr)
        return 1

    node_id = find_entity(graph, args.name)
    if node_id is None:
        print(f"aucune entité trouvée pour '{args.name}' (aucun match, ou plusieurs candidats ambigus -- précise le nom)", file=sys.stderr)
        return 1

    analysis = run_full_analysis(graph, min_corroborating_sources=g.min_corroborating_sources)
    label = graph.nodes[node_id].get("label", node_id)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = generate_entity_view(
        graph, analysis, node_id,
        output_path=g.notebooks_dir / f"entity__{slugify(label)}__{ts}.html",
        source_name=graph_key, generated_at=datetime.now(timezone.utc).isoformat(),
        min_corroborating_sources=g.min_corroborating_sources,
    )
    print(f"fiche générée pour '{label}' -> {output_path}")
    return 0


def cmd_index(args) -> int:
    app_config = load_config(args.config)
    output_path = generate_index(app_config.global_.notebooks_dir)
    print(f"page d'accueil régénérée -> {output_path}")
    return 0


def cmd_serve(args) -> int:
    app_config = load_config(args.config)
    scheduler = build_scheduler(app_config, Path(args.config), run_immediately=True)
    print("graph-watch démarré. Ctrl+C pour arrêter.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    return 0


def cmd_once(args) -> int:
    app_config = load_config(args.config)
    sources = [app_config.source_by_name(args.source)] if args.source else app_config.sources
    for source_cfg in sources:
        result = run_cycle(app_config, source_cfg, force_report=args.force)
        if result is None:
            print(f"[{source_cfg.name}] -> rien de nouveau")
        elif isinstance(result, PropagationCycleResult):
            print(f"[{source_cfg.name}] {result.n_new_posts} nouveau(x) post(s)")
            for rumor, path in result.reports.items():
                print(f"[{source_cfg.name}] propagation '{rumor}' -> {path}")
        elif isinstance(result, CycleResult):
            print(f"[{source_cfg.name}] notebook -> {result.notebook_path}")
            print(f"[{source_cfg.name}] graphe interactif -> {result.html_graph_path}")
            for entity_path in result.entity_paths:
                print(f"[{source_cfg.name}] fiche -> {entity_path}")
            if result.index_path:
                print(f"[{source_cfg.name}] page d'accueil -> {result.index_path}")
    return 0


def cmd_propose(args) -> int:
    app_config = load_config(args.config)
    queue = PendingQueue(app_config.global_.data_dir / "pending_sources.db")

    if args.type == "rss":
        options = {"url": args.url}
    elif args.type in ("corpus_folder", "post_thread"):
        options = {"path": args.path}
    elif args.type == "topic":
        options = {"query": args.query}
    else:
        print(f"type inconnu: {args.type}", file=sys.stderr)
        return 1

    proposal = queue.propose(
        name=args.name, type=args.type, options=options,
        interval_minutes=args.interval, extractor=args.extractor, reliability=args.reliability,
    )
    print(f"proposé: {proposal.name} ({proposal.type}), fiabilité={proposal.reliability}")
    print(f"aperçu : {proposal.preview}")
    print(f"-> python run.py approve {proposal.name}   (ou reject)")
    return 0


def cmd_list_pending(args) -> int:
    app_config = load_config(args.config)
    queue = PendingQueue(app_config.global_.data_dir / "pending_sources.db")
    status = None if args.status == "all" else args.status
    proposals = queue.list(status=status)
    if not proposals:
        print("rien à afficher.")
        return 0
    for p in proposals:
        print(f"[{p.status}] {p.name} ({p.type}, toutes les {p.interval_minutes} min, "
              f"extractor={p.extractor}, fiabilité={p.reliability})")
        print(f"    aperçu : {p.preview}")
        print(f"    proposé le {p.proposed_at}" + (f", relu le {p.reviewed_at}" if p.reviewed_at else ""))
    return 0


def cmd_approve(args) -> int:
    app_config = load_config(args.config)
    queue = PendingQueue(app_config.global_.data_dir / "pending_sources.db")
    proposal = queue.get(args.name)
    if proposal is None:
        print(f"aucune proposition nommée '{args.name}'", file=sys.stderr)
        return 1

    source_cfg = SourceConfig(
        name=proposal.name, type=proposal.type, interval_minutes=proposal.interval_minutes,
        extractor=proposal.extractor, options=proposal.options, reliability=proposal.reliability,
    )
    approved_path = append_approved_source(args.config, source_cfg)
    queue.set_status(args.name, "approved")
    print(f"approuvé -> ajouté à {approved_path}")
    print("actif au prochain `python run.py once`, ou repris automatiquement sous 5 min si `serve` tourne déjà.")
    return 0


def cmd_reject(args) -> int:
    app_config = load_config(args.config)
    queue = PendingQueue(app_config.global_.data_dir / "pending_sources.db")
    if queue.get(args.name) is None:
        print(f"aucune proposition nommée '{args.name}'", file=sys.stderr)
        return 1
    queue.set_status(args.name, "rejected")
    print(f"rejeté: {args.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="graph-watch")
    parser.add_argument("--config", default="config.yaml", help="chemin du fichier de config")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="scheduler persistant (tourne en continu)").set_defaults(func=cmd_serve)

    p_once = sub.add_parser("once", help="un seul cycle puis quitte")
    p_once.add_argument("--source", help="limite à cette source")
    p_once.add_argument("--force", action="store_true", help="régénère même sans nouveau document")
    p_once.set_defaults(func=cmd_once)

    p_webui = sub.add_parser("webui", help="interface glisser-déposer + URL (tourne avec ta connexion réseau)")
    p_webui.add_argument("--host", default="127.0.0.1")
    p_webui.add_argument("--port", type=int, default=8765)
    p_webui.set_defaults(func=cmd_webui)

    p_entity = sub.add_parser("entity", help="fiche autonome pour une entité précise (à la demande)")
    p_entity.add_argument("name", help="nom (ou approchant) de la personne/organisation")
    p_entity.add_argument("--source", help="requis si graph_mode: per_source")
    p_entity.set_defaults(func=cmd_entity)

    sub.add_parser("index", help="régénère la page d'accueil (notebooks/index.html) à la demande").set_defaults(func=cmd_index)

    p_propose = sub.add_parser("propose", help="proposer une adresse candidate (en attente de validation)")
    p_propose.add_argument("--name", required=True)
    p_propose.add_argument("--type", required=True, choices=["rss", "corpus_folder", "topic", "post_thread"])
    p_propose.add_argument("--url", help="pour --type rss")
    p_propose.add_argument("--path", help="pour --type corpus_folder / post_thread")
    p_propose.add_argument("--query", help="pour --type topic")
    p_propose.add_argument("--interval", type=int, default=1440, dest="interval")
    p_propose.add_argument("--extractor", default="spacy", choices=["spacy", "llm"])
    p_propose.add_argument("--reliability", default="F", choices=["A", "B", "C", "D", "E", "F"],
                            help="Admiralty Code : fiabilité de CETTE source (A=totalement fiable .. F=inconnue)")
    p_propose.set_defaults(func=cmd_propose)

    p_list = sub.add_parser("list-pending", help="lister les propositions")
    p_list.add_argument("--status", default="pending", choices=["pending", "approved", "rejected", "all"])
    p_list.set_defaults(func=cmd_list_pending)

    p_approve = sub.add_parser("approve", help="valider une proposition -> devient une source active")
    p_approve.add_argument("name")
    p_approve.set_defaults(func=cmd_approve)

    p_reject = sub.add_parser("reject", help="rejeter une proposition")
    p_reject.add_argument("name")
    p_reject.set_defaults(func=cmd_reject)

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
