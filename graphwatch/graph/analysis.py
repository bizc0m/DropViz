"""Analyse structurelle : centralité, communautés, robustesse, signaux de confiance.

Rien ici ne transforme la structure du graphe en verdict sur des personnes —
ces fonctions renvoient des nombres et des regroupements ; l'interprétation
prudente est faite côté génération du notebook (report/notebook_generator.py).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import networkx as nx


@dataclass
class AnalysisResult:
    n_nodes: int
    n_edges: int
    density: float
    n_connected_components: int
    largest_component_size: int
    centrality: dict[str, dict[str, float]]
    communities: dict[str, int]
    modularity: float
    community_stability: float | None
    low_confidence_nodes: list[str] = field(default_factory=list)
    low_confidence_edges: list[tuple[str, str]] = field(default_factory=list)
    single_source_hubs: list[str] = field(default_factory=list)
    # Admiralty Code : suggestion 1-6, calculée -- PAS un jugement humain.
    credibility_nodes: dict[str, int] = field(default_factory=dict)
    credibility_edges: dict[tuple[str, str], int] = field(default_factory=dict)


def basic_stats(graph: nx.Graph) -> dict:
    components = list(nx.connected_components(graph)) if graph.number_of_nodes() else []
    return {
        "n_nodes": graph.number_of_nodes(),
        "n_edges": graph.number_of_edges(),
        "density": nx.density(graph) if graph.number_of_nodes() > 1 else 0.0,
        "n_connected_components": len(components),
        "largest_component_size": max((len(c) for c in components), default=0),
    }


def compute_centrality(graph: nx.Graph) -> dict[str, dict[str, float]]:
    if graph.number_of_nodes() == 0:
        return {"degree": {}, "betweenness": {}, "eigenvector": {}, "pagerank": {}}

    degree = dict(nx.degree_centrality(graph))
    betweenness = dict(nx.betweenness_centrality(graph, weight=None))
    try:
        eigenvector = dict(nx.eigenvector_centrality(graph, max_iter=500, weight="weight"))
    except (nx.PowerIterationFailedConvergence, nx.AmbiguousSolution):
        eigenvector = {n: float("nan") for n in graph.nodes}
    pagerank = dict(nx.pagerank(graph, weight="weight"))

    return {
        "degree": degree,
        "betweenness": betweenness,
        "eigenvector": eigenvector,
        "pagerank": pagerank,
    }


def detect_communities(graph: nx.Graph) -> tuple[dict[str, int], float]:
    """Renvoie (node -> id de communauté, score de modularité).
    Utilise python-louvain si dispo, sinon la modularité gloutonne de networkx."""
    if graph.number_of_nodes() == 0:
        return {}, 0.0

    try:
        import community as community_louvain  # python-louvain
        partition = community_louvain.best_partition(graph, weight="weight", random_state=42)
        modularity = community_louvain.modularity(partition, graph, weight="weight")
        return partition, modularity
    except ImportError:
        communities = list(nx.algorithms.community.greedy_modularity_communities(graph, weight="weight"))
        partition = {}
        for i, comm in enumerate(communities):
            for node in comm:
                partition[node] = i
        modularity = nx.algorithms.community.modularity(graph, communities, weight="weight")
        return partition, modularity


def _pairwise_agreement(part_a: dict[str, int], part_b: dict[str, int], nodes: list[str]) -> float:
    """Fraction de paires de nœuds dont le statut 'même communauté / pas même
    communauté' est identique entre les deux partitions. 1.0 = parfaitement stable."""
    if len(nodes) < 2:
        return 1.0
    sample = nodes if len(nodes) <= 200 else random.sample(nodes, 200)
    agree, total = 0, 0
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            a, b = sample[i], sample[j]
            same_a = part_a.get(a) == part_a.get(b)
            same_b = part_b.get(a) == part_b.get(b)
            agree += int(same_a == same_b)
            total += 1
    return agree / total if total else 1.0


def community_stability(graph: nx.Graph, reference_partition: dict[str, int], n_runs: int = 5,
                          edge_sample_frac: float = 0.8, seed: int = 42) -> float | None:
    """Robustesse : ré-exécute la détection de communautés sur des sous-échantillons
    d'arêtes et mesure l'accord moyen avec la partition de référence.
    Renvoie None si le graphe est trop petit pour que la mesure ait un sens."""
    if graph.number_of_edges() < 5:
        return None

    rng = random.Random(seed)
    nodes = list(graph.nodes)
    edges = list(graph.edges(data=True))
    scores = []

    for _ in range(n_runs):
        k = max(1, int(len(edges) * edge_sample_frac))
        sampled = rng.sample(edges, k)
        sub = nx.Graph()
        sub.add_nodes_from(nodes)
        for u, v, data in sampled:
            sub.add_edge(u, v, **data)
        partition, _ = detect_communities(sub)
        scores.append(_pairwise_agreement(reference_partition, partition, nodes))

    return sum(scores) / len(scores) if scores else None


def confidence_flags(graph: nx.Graph, min_corroborating_sources: int) -> tuple[list[str], list[tuple[str, str]]]:
    """Nœuds/arêtes mentionnés dans moins de N documents distincts (`origins`) ->
    à vérifier avant toute conclusion. Ne dit PAS que c'est faux, dit que ce
    n'est pas corroboré. Compte les DOCUMENTS (origins), pas les sources
    configurées : 5 fichiers dans le même dossier corpus comptent comme 5
    corroborations possibles, pas 1."""
    low_nodes = [
        n for n, d in graph.nodes(data=True)
        if len(d.get("origins", set())) < min_corroborating_sources
    ]
    low_edges = [
        (u, v) for u, v, d in graph.edges(data=True)
        if len(d.get("origins", set())) < min_corroborating_sources
    ]
    return low_nodes, low_edges


def single_source_hubs(graph: nx.Graph, degree_percentile: float = 0.9) -> list[str]:
    """Nœuds à degré élevé mais mentionnés dans un seul document : signal
    d'alerte possible (répétition/spam d'un seul document plutôt que
    corroboration réelle) plutôt qu'une vraie centralité."""
    if graph.number_of_nodes() == 0:
        return []
    degrees = dict(graph.degree())
    if not degrees:
        return []
    sorted_degrees = sorted(degrees.values())
    cutoff_idx = int(len(sorted_degrees) * degree_percentile)
    cutoff = sorted_degrees[min(cutoff_idx, len(sorted_degrees) - 1)]

    flagged = []
    for n, deg in degrees.items():
        if deg < cutoff or deg == 0:
            continue
        origins = graph.nodes[n].get("origins", set())
        if len(origins) <= 1:
            flagged.append(n)
    return flagged


# Admiralty Code : A (totalement fiable) -> F (ne peut être jugée). Ordre pour
# prendre la MEILLEURE fiabilité parmi les sources qui corroborent un nœud/arête.
_RELIABILITY_ORDER = ["A", "B", "C", "D", "E", "F"]


def _credibility_score(reliabilities: set, n_origins: int) -> int:
    """Suggestion de crédibilité info (1=confirmé .. 6=ne peut être jugée),
    dérivée de la fiabilité Admiralty des sources corroborantes et de leur
    nombre. HEURISTIQUE MAISON, pas une échelle validée en soi (contrairement
    à l'Admiralty Code lui-même) -- à afficher comme une suggestion à vérifier,
    jamais comme un verdict."""
    if not reliabilities:
        return 6
    best = min(reliabilities, key=lambda r: _RELIABILITY_ORDER.index(r) if r in _RELIABILITY_ORDER else 99)

    if best in ("A", "B"):
        return 1 if n_origins >= 2 else 2
    if best == "C":
        return 2 if n_origins >= 2 else 3
    if best in ("D", "E"):
        # une source peu fiable répétée par elle-même n'est pas une corroboration ;
        # il faut des origines DIFFÉRENTES pour remonter, pas juste plus de mentions.
        return 3 if n_origins >= 3 else 4
    return 6  # F : inconnue -> "ne peut être jugée", jamais présumée correcte


def compute_credibility(graph: nx.Graph) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    node_credibility = {
        n: _credibility_score(d.get("reliabilities", set()), len(d.get("origins", set())))
        for n, d in graph.nodes(data=True)
    }
    edge_credibility = {
        (u, v): _credibility_score(d.get("reliabilities", set()), len(d.get("origins", set())))
        for u, v, d in graph.edges(data=True)
    }
    return node_credibility, edge_credibility


def run_full_analysis(graph: nx.Graph, min_corroborating_sources: int = 2) -> AnalysisResult:
    stats = basic_stats(graph)
    centrality = compute_centrality(graph)
    communities, modularity = detect_communities(graph)
    stability = community_stability(graph, communities)
    low_nodes, low_edges = confidence_flags(graph, min_corroborating_sources)
    hubs = single_source_hubs(graph)
    credibility_nodes, credibility_edges = compute_credibility(graph)

    return AnalysisResult(
        n_nodes=stats["n_nodes"],
        n_edges=stats["n_edges"],
        density=stats["density"],
        n_connected_components=stats["n_connected_components"],
        largest_component_size=stats["largest_component_size"],
        centrality=centrality,
        communities=communities,
        modularity=modularity,
        community_stability=stability,
        low_confidence_nodes=low_nodes,
        low_confidence_edges=low_edges,
        single_source_hubs=hubs,
        credibility_nodes=credibility_nodes,
        credibility_edges=credibility_edges,
    )
