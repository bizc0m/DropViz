"""Sérialise un graphe + son analyse en JSON pour la vue interactive."""
from __future__ import annotations

import networkx as nx

from graphwatch.graph.analysis import AnalysisResult

_RELIABILITY_ORDER = ["A", "B", "C", "D", "E", "F"]


def _best_reliability(reliabilities: set) -> str:
    if not reliabilities:
        return "F"
    return min(reliabilities, key=lambda r: _RELIABILITY_ORDER.index(r) if r in _RELIABILITY_ORDER else 99)


def build_payload(
    graph: nx.Graph,
    analysis: AnalysisResult,
    *,
    source_name: str,
    generated_at: str,
    n_new_docs: int,
    min_corroborating_sources: int,
    setup: dict | None = None,
) -> dict:
    low_conf_nodes = set(analysis.low_confidence_nodes)
    low_conf_edges = {frozenset(e) for e in analysis.low_confidence_edges}
    hub_nodes = set(analysis.single_source_hubs)
    pagerank = analysis.centrality.get("pagerank", {})
    betweenness = analysis.centrality.get("betweenness", {})
    degree = analysis.centrality.get("degree", {})
    edge_credibility = {frozenset(k): v for k, v in analysis.credibility_edges.items()}

    nodes = []
    for node_id, data in graph.nodes(data=True):
        nodes.append({
            "id": node_id,
            "label": data.get("label", node_id),
            "community": analysis.communities.get(node_id, 0),
            "pagerank": round(pagerank.get(node_id, 0.0), 6),
            "betweenness": round(betweenness.get(node_id, 0.0), 6),
            "degree": round(degree.get(node_id, 0.0), 6),
            "mentions": data.get("mentions", 0),
            "sources": sorted(data.get("origins", [])),
            "aliases": sorted(a for a in data.get("aliases", []) if a != data.get("label")),
            "lowConfidence": node_id in low_conf_nodes,
            "singleSourceHub": node_id in hub_nodes,
            "reliability": _best_reliability(data.get("reliabilities", set())),
            "credibility": analysis.credibility_nodes.get(node_id, 6),
            "firstSeen": data.get("first_seen"),
            "lastSeen": data.get("last_seen"),
        })

    edges = []
    for u, v, data in graph.edges(data=True):
        confidences = data.get("confidences", [1.0])
        edges.append({
            "source": u,
            "target": v,
            "weight": data.get("weight", 1),
            "predicates": sorted(data.get("predicates", [])),
            "sources": sorted(data.get("origins", [])),
            "avgConfidence": round(sum(confidences) / len(confidences), 3) if confidences else 1.0,
            "lowConfidence": frozenset((u, v)) in low_conf_edges,
            "reliability": _best_reliability(data.get("reliabilities", set())),
            "credibility": edge_credibility.get(frozenset((u, v)), 6),
            "snippets": data.get("snippets", [])[:5],
        })

    return {
        "meta": {
            "sourceName": source_name,
            "generatedAt": generated_at,
            "nNewDocs": n_new_docs,
            "nNodes": analysis.n_nodes,
            "nEdges": analysis.n_edges,
            "density": round(analysis.density, 4),
            "modularity": round(analysis.modularity, 4),
            "communityStability": (
                round(analysis.community_stability, 4)
                if analysis.community_stability is not None else None
            ),
            "nCommunities": len(set(analysis.communities.values())) if analysis.communities else 0,
            "minCorroboratingSources": min_corroborating_sources,
            "nLowConfidenceNodes": len(analysis.low_confidence_nodes),
            "nSingleSourceHubs": len(analysis.single_source_hubs),
            "setup": setup or {},
        },
        "nodes": nodes,
        "edges": edges,
    }


def annotate_for_gephi(graph: nx.Graph, analysis: AnalysisResult) -> nx.Graph:
    """Copie du graphe enrichie des métriques calculées (communauté, PageRank,
    betweenness, crédibilité/fiabilité) comme attributs scalaires directs sur
    les nœuds/arêtes -- sans ça, un .graphml n'a que la provenance brute et
    Gephi n'a rien à mapper sur la taille/couleur des nœuds à l'ouverture."""
    g = graph.copy()
    pagerank = analysis.centrality.get("pagerank", {})
    betweenness = analysis.centrality.get("betweenness", {})
    degree = analysis.centrality.get("degree", {})
    low_conf_nodes = set(analysis.low_confidence_nodes)
    low_conf_edges = {frozenset(e) for e in analysis.low_confidence_edges}
    edge_credibility = {frozenset(k): v for k, v in analysis.credibility_edges.items()}

    for node_id, data in g.nodes(data=True):
        data["community"] = analysis.communities.get(node_id, 0)
        data["pagerank"] = round(pagerank.get(node_id, 0.0), 6)
        data["betweenness"] = round(betweenness.get(node_id, 0.0), 6)
        data["degree_centrality"] = round(degree.get(node_id, 0.0), 6)
        data["reliability"] = _best_reliability(data.get("reliabilities", set()))
        data["credibility"] = analysis.credibility_nodes.get(node_id, 6)
        data["low_confidence"] = node_id in low_conf_nodes

    for u, v, data in g.edges(data=True):
        data["reliability"] = _best_reliability(data.get("reliabilities", set()))
        data["credibility"] = edge_credibility.get(frozenset((u, v)), 6)
        data["low_confidence"] = frozenset((u, v)) in low_conf_edges

    return g
