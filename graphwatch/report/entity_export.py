"""Sérialise UNE entité + son réseau direct (1 saut) en JSON, pour la fiche
individuelle -- distinct du graphe complet : ici on documente une personne
ou un groupe précis, exportable seul."""
from __future__ import annotations

import networkx as nx

from graphwatch.graph.analysis import AnalysisResult
from graphwatch.report.graph_export import _best_reliability


def find_entity(graph: nx.Graph, query: str) -> str | None:
    """Cherche un nœud par nom (exact d'abord, puis sous-chaîne insensible à
    la casse). Renvoie None si rien, ou si plusieurs candidats sont trouvés
    par sous-chaîne -- pas de choix arbitraire silencieux."""
    from graphwatch.graph.builder import normalize_key

    key = normalize_key(query)
    if key in graph.graph.get("alias_index", {}):
        return graph.graph["alias_index"][key]
    if graph.has_node(key):
        return key

    matches = [n for n, d in graph.nodes(data=True) if key in normalize_key(d.get("label", n))]
    return matches[0] if len(matches) == 1 else None


def build_entity_payload(
    graph: nx.Graph, analysis: AnalysisResult, node_id: str, *,
    source_name: str, generated_at: str, min_corroborating_sources: int, setup: dict | None = None,
) -> dict:
    if not graph.has_node(node_id):
        raise KeyError(f"entité inconnue: {node_id}")

    data = graph.nodes[node_id]
    pagerank = analysis.centrality.get("pagerank", {})
    betweenness = analysis.centrality.get("betweenness", {})
    degree = analysis.centrality.get("degree", {})
    edge_credibility = {frozenset(k): v for k, v in analysis.credibility_edges.items()}
    low_conf_nodes = set(analysis.low_confidence_nodes)

    relations = []
    neighbors = []
    for other_id in graph.neighbors(node_id):
        edata = graph.edges[node_id, other_id]
        odata = graph.nodes[other_id]
        confidences = edata.get("confidences", [1.0])
        relations.append({
            "otherId": other_id,
            "otherLabel": odata.get("label", other_id),
            "otherCommunity": analysis.communities.get(other_id, 0),
            "predicates": sorted(edata.get("predicates", [])),
            "weight": edata.get("weight", 1),
            "avgConfidence": round(sum(confidences) / len(confidences), 3) if confidences else 1.0,
            "reliability": _best_reliability(edata.get("reliabilities", set())),
            "credibility": edge_credibility.get(frozenset((node_id, other_id)), 6),
            "sources": sorted(edata.get("origins", [])),
            "snippets": edata.get("snippets", [])[:5],
        })
        neighbors.append({
            "id": other_id,
            "label": odata.get("label", other_id),
            "community": analysis.communities.get(other_id, 0),
            "pagerank": round(pagerank.get(other_id, 0.0), 6),
            "lowConfidence": other_id in low_conf_nodes,
        })

    relations.sort(key=lambda r: r["weight"], reverse=True)

    return {
        "meta": {
            "sourceName": source_name,
            "generatedAt": generated_at,
            "minCorroboratingSources": min_corroborating_sources,
            "setup": setup or {},
        },
        "entity": {
            "id": node_id,
            "label": data.get("label", node_id),
            "aliases": sorted(a for a in data.get("aliases", []) if a != data.get("label")),
            "community": analysis.communities.get(node_id, 0),
            "mentions": data.get("mentions", 0),
            "pagerank": round(pagerank.get(node_id, 0.0), 6),
            "betweenness": round(betweenness.get(node_id, 0.0), 6),
            "degree": round(degree.get(node_id, 0.0), 6),
            "sources": sorted(data.get("origins", [])),
            "reliability": _best_reliability(data.get("reliabilities", set())),
            "credibility": analysis.credibility_nodes.get(node_id, 6),
            "lowConfidence": node_id in low_conf_nodes,
            "firstSeen": data.get("first_seen"),
            "lastSeen": data.get("last_seen"),
        },
        "neighbors": neighbors,
        "relations": relations,
    }
