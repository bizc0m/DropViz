"""Rapport Markdown autonome (pas de cellules de code, pas d'exécution requise)
-- pensé pour être collé dans un wiki, un ticket, ou donné en contexte à un LLM."""
from __future__ import annotations

from pathlib import Path

import networkx as nx

from graphwatch.graph.analysis import AnalysisResult


def _label(graph: nx.Graph, node_id: str) -> str:
    return graph.nodes[node_id].get("label", node_id) if node_id in graph.nodes else node_id


def _top_n(scores: dict, graph: nx.Graph, n: int = 15) -> list[tuple[str, float]]:
    ranked = sorted(scores.items(), key=lambda kv: (kv[1] if kv[1] == kv[1] else -1), reverse=True)
    return [(_label(graph, node), score) for node, score in ranked[:n]]


def generate_markdown_report(
    *,
    cycle_meta: dict,
    graph: nx.Graph,
    analysis: AnalysisResult,
    output_path: Path,
    min_corroborating_sources: int,
) -> Path:
    lines: list[str] = []
    add = lines.append

    add(f"# Rapport — {cycle_meta.get('source_name', 'toutes sources')}")
    add("")
    add(f"Généré le {cycle_meta.get('generated_at')} · {cycle_meta.get('n_new_docs', 0)} nouveau(x) document(s) ce cycle.")
    add("")
    add("> Ce rapport décrit la structure d'un graphe extrait d'un corpus. Une position centrale "
        "ou une relation ne constituent pas une preuve — voir la section Signaux de confiance.")
    add("")

    add("## Statistiques")
    add("")
    add("| Mesure | Valeur |")
    add("|---|---|")
    add(f"| Entités | {analysis.n_nodes} |")
    add(f"| Relations | {analysis.n_edges} |")
    add(f"| Densité | {analysis.density:.4f} |")
    add(f"| Communautés | {len(set(analysis.communities.values())) if analysis.communities else 0} |")
    add(f"| Modularité | {analysis.modularity:.4f} |")
    stability = f"{analysis.community_stability:.0%}" if analysis.community_stability is not None else "n/a"
    add(f"| Stabilité des communautés | {stability} |")
    add("")

    add("## Top entités (par PageRank)")
    add("")
    add("| Entité | PageRank | Betweenness | Sources | Fiabilité | Crédibilité |")
    add("|---|---|---|---|---|---|")
    for node_id, score in sorted(analysis.centrality.get("pagerank", {}).items(), key=lambda kv: kv[1], reverse=True)[:15]:
        data = graph.nodes[node_id]
        reliabilities = data.get("reliabilities", set())
        best_reliability = min(reliabilities, default="F", key=lambda r: "ABCDEF".index(r) if r in "ABCDEF" else 9)
        credibility = analysis.credibility_nodes.get(node_id, 6)
        n_sources = len(data.get("origins", set()))
        betweenness = analysis.centrality.get("betweenness", {}).get(node_id, 0.0)
        add(f"| {_label(graph, node_id)} | {score:.4f} | {betweenness:.4f} | {n_sources} | {best_reliability} | {credibility}/6 |")
    add("")

    add("## Signaux de confiance")
    add("")
    low_labels = sorted({_label(graph, n) for n in analysis.low_confidence_nodes})
    hub_labels = sorted({_label(graph, n) for n in analysis.single_source_hubs})
    add(f"- **{len(analysis.low_confidence_nodes)} entité(s)** corroborée(s) par moins de "
        f"{min_corroborating_sources} document(s) distinct(s)"
        + (f" : {', '.join(low_labels)}" if low_labels else ""))
    add(f"- **{len(analysis.single_source_hubs)} entité(s)** à degré élevé mais un seul document source"
        + (f" : {', '.join(hub_labels)}" if hub_labels else ""))
    add("")
    add("La crédibilité (1–6) est une heuristique de cet outil (fiabilité de la source × nombre de "
        "documents indépendants), pas une échelle validée en elle-même — à vérifier, pas à citer telle quelle.")
    add("")

    add("## Relations principales")
    add("")
    add("| De | À | Relation(s) | Occurrences | Fiabilité | Crédibilité |")
    add("|---|---|---|---|---|---|")
    edges_by_weight = sorted(graph.edges(data=True), key=lambda e: e[2].get("weight", 1), reverse=True)[:20]
    edge_credibility = {frozenset(k): v for k, v in analysis.credibility_edges.items()}
    for u, v, data in edges_by_weight:
        reliabilities = data.get("reliabilities", set())
        best_reliability = min(reliabilities, default="F", key=lambda r: "ABCDEF".index(r) if r in "ABCDEF" else 9)
        credibility = edge_credibility.get(frozenset((u, v)), 6)
        predicates = ", ".join(sorted(data.get("predicates", [])))
        add(f"| {_label(graph, u)} | {_label(graph, v)} | {predicates} | {data.get('weight', 1)} | {best_reliability} | {credibility}/6 |")
    add("")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
