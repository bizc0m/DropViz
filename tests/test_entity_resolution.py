"""Tests unitaires de la cascade de résolution d'entités (graph/builder.py)."""
from __future__ import annotations

import networkx as nx

from graphwatch.graph.builder import normalize_key, resolve


def _seed_node(graph: nx.Graph, node_id: str, label: str) -> None:
    graph.add_node(node_id, label=label, aliases={label})
    graph.graph.setdefault("alias_index", {})[normalize_key(label)] = node_id


def test_exact_match_case_and_accents():
    g = nx.Graph()
    id1 = resolve(g, "Hélène Ferrand")
    id2 = resolve(g, "HÉLÈNE FERRAND")
    assert id1 == id2


def test_leading_determiner_stripped():
    g = nx.Graph()
    _seed_node(g, resolve(g, "Autorité de Transparence Publique"), "Autorité de Transparence Publique")
    id2 = resolve(g, "l'Autorité de Transparence Publique")
    assert normalize_key("Autorité de Transparence Publique") == normalize_key("l'Autorité de Transparence Publique")
    assert id2 in g.graph["alias_index"].values()


def test_acronym_resolves_to_full_name():
    g = nx.Graph()
    full_id = resolve(g, "Autorité de Transparence Publique")
    _seed_node(g, full_id, "Autorité de Transparence Publique")
    acronym_id = resolve(g, "ATP")
    assert acronym_id == full_id


def test_surname_only_resolves_when_unambiguous():
    g = nx.Graph()
    full_id = resolve(g, "Marc Delassus")
    _seed_node(g, full_id, "Marc Delassus")
    surname_id = resolve(g, "Delassus")
    assert surname_id == full_id


def test_surname_ambiguous_does_not_merge():
    g = nx.Graph()
    id_a = resolve(g, "Marc Delassus")
    _seed_node(g, id_a, "Marc Delassus")
    id_b = resolve(g, "Sophie Delassus")
    _seed_node(g, id_b, "Sophie Delassus")
    surname_id = resolve(g, "Delassus")
    # deux personnes différentes partagent ce nom de famille -> pas de fusion
    assert surname_id not in (id_a, id_b)


def test_fuzzy_typo_match():
    g = nx.Graph()
    full_id = resolve(g, "Hélène Ferrand")
    _seed_node(g, full_id, "Hélène Ferrand")
    typo_id = resolve(g, "Helene Ferand")  # faute de frappe mineure
    assert typo_id == full_id


def test_honorific_title_stripped():
    g = nx.Graph()
    full_id = resolve(g, "Antoine Rieux")
    _seed_node(g, full_id, "Antoine Rieux")
    titled_id = resolve(g, "Maître Antoine Rieux")
    assert titled_id == full_id


def test_fuzzy_does_not_merge_distinct_names():
    g = nx.Graph()
    id_a = resolve(g, "Marc Delassus")
    _seed_node(g, id_a, "Marc Delassus")
    id_b = resolve(g, "Julien Fabre")
    assert id_b != id_a
