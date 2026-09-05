"""Fusionne les relations extraites dans le graphe persistant.

Résolution d'entités en cascade (voir `resolve()`), du plus sûr au plus
risqué -- pas de similarité floue en premier recours, pour éviter de fondre
deux personnes différentes en un seul nœud.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from datetime import datetime, timezone

import networkx as nx

from graphwatch.extract.base import Relation

_WS_RE = re.compile(r"\s+")
_LEADING_DETERMINER_RE = re.compile(r"^(l['’]|d['’]|le |la |les |du |des |de la )", re.IGNORECASE)
_LEADING_TITLE_RE = re.compile(
    r"^(maitre|me|monsieur|madame|mademoiselle|mme|mlle|m|docteur|dr|professeur|pr)\.? +",
    re.IGNORECASE,
)
_SMALL_WORDS = {"de", "du", "des", "la", "le", "les", "et", "d", "l", "à", "au", "aux"}
_FUZZY_CUTOFF = 0.90


def normalize_key(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = _WS_RE.sub(" ", name).strip().lower()
    name = _LEADING_DETERMINER_RE.sub("", name).strip()
    name = _LEADING_TITLE_RE.sub("", name).strip()
    return name


def _acronym_of(label: str) -> str:
    words = [w for w in normalize_key(label).split() if w and w not in _SMALL_WORDS]
    return "".join(w[0] for w in words).upper()


def _last_token(label: str) -> str:
    words = normalize_key(label).split()
    return words[-1] if words else ""


def _find_existing_match(graph: nx.Graph, raw_name: str, key: str) -> str | None:
    """Cherche un nœud existant pour `raw_name`/`key` sans passer par le cache
    exact. Renvoie None si rien de fiable, plutôt que de risquer une fusion
    entre deux entités différentes -- un candidat AMBIGU (plusieurs matches)
    ne compte pas comme trouvé."""
    if graph.number_of_nodes() == 0:
        return None

    # 1. acronyme : "ATP" -> "Autorité de Transparence Publique"
    if raw_name.isalpha() and raw_name.isupper() and 2 <= len(raw_name) <= 6:
        matches = [n for n, d in graph.nodes(data=True) if _acronym_of(d.get("label", "")) == raw_name]
        if len(matches) == 1:
            return matches[0]

    # 2. nom de famille seul : "Delassus" -> "Marc Delassus" (si un SEUL candidat)
    if " " not in key and len(key) >= 3:
        matches = [
            n for n, d in graph.nodes(data=True)
            if len(d.get("label", "").split()) >= 2 and _last_token(d.get("label", "")) == key
        ]
        if len(matches) == 1:
            return matches[0]

    # 3. similarité floue sur les libellés déjà vus (fautes de frappe, variantes mineures)
    known_keys = list(graph.graph.get("alias_index", {}).keys())
    close = difflib.get_close_matches(key, known_keys, n=1, cutoff=_FUZZY_CUTOFF)
    if close:
        return graph.graph["alias_index"][close[0]]

    return None


def resolve(graph: nx.Graph, name: str) -> str:
    """Renvoie l'id de nœud canonique pour ce nom, en créant le nœud si besoin.

    Cascade : correspondance exacte connue -> acronyme -> nom de famille seul
    -> similarité floue -- dans cet ordre, du plus sûr au plus risqué. S'arrête
    au premier candidat NON ambigu ; sinon crée un nouveau nœud plutôt que de
    deviner."""
    alias_index = graph.graph.setdefault("alias_index", {})
    key = normalize_key(name)
    if key in alias_index:
        return alias_index[key]

    node_id = _find_existing_match(graph, name.strip(), key) or key
    alias_index[key] = node_id
    return node_id


def merge_relations(graph: nx.Graph, relations: list[Relation]) -> nx.Graph:
    graph.graph.setdefault("alias_index", {})
    now = datetime.now(timezone.utc).isoformat()

    for rel in relations:
        u = resolve(graph, rel.subject)
        v = resolve(graph, rel.object)
        if u == v:
            continue  # pas d'auto-boucle

        for node_id, label in ((u, rel.subject), (v, rel.object)):
            if not graph.has_node(node_id):
                graph.add_node(
                    node_id,
                    label=label.strip(),
                    aliases={label.strip()},
                    source_names={rel.source_name},
                    origins={rel.origin},
                    doc_ids={rel.doc_id},
                    reliabilities={rel.source_reliability},
                    mentions=1,
                    first_seen=now,
                    last_seen=now,
                )
            else:
                data = graph.nodes[node_id]
                data["aliases"].add(label.strip())
                data["source_names"].add(rel.source_name)
                data["origins"].add(rel.origin)
                data["doc_ids"].add(rel.doc_id)
                data["reliabilities"].add(rel.source_reliability)
                data["mentions"] += 1
                data["last_seen"] = now

        if not graph.has_edge(u, v):
            graph.add_edge(
                u, v,
                weight=1,
                predicates={rel.predicate},
                source_names={rel.source_name},
                origins={rel.origin},
                doc_ids={rel.doc_id},
                reliabilities={rel.source_reliability},
                snippets=[rel.snippet],
                confidences=[rel.confidence],
                first_seen=now,
                last_seen=now,
            )
        else:
            data = graph.edges[u, v]
            data["weight"] += 1
            data["predicates"].add(rel.predicate)
            data["source_names"].add(rel.source_name)
            data["origins"].add(rel.origin)
            data["doc_ids"].add(rel.doc_id)
            data["reliabilities"].add(rel.source_reliability)
            if len(data["snippets"]) < 20:  # cap pour ne pas faire exploser la taille du graphe
                data["snippets"].append(rel.snippet)
            data["confidences"].append(rel.confidence)
            data["last_seen"] = now

    return graph
