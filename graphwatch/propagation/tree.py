"""Construction de l'arbre de propagation et calcul de ses métriques."""
from __future__ import annotations

from dataclasses import dataclass

from graphwatch.propagation.models import Post


@dataclass
class TreeMetrics:
    size: int
    depth: int
    unique_accounts: int
    total_retweets: int
    total_quotes: int
    total_replies: int


def children_map(posts: list[Post]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for p in posts:
        if p.parent_id:
            children.setdefault(p.parent_id, []).append(p.id)
    return children


def reachable_from(root_id: str, children: dict[str, list[str]]) -> tuple[set[str], int]:
    """BFS depuis root_id. Renvoie (ids atteints, profondeur max)."""
    seen = {root_id}
    frontier = [root_id]
    depth = 0
    while frontier:
        next_frontier = []
        for node_id in frontier:
            for child_id in children.get(node_id, []):
                if child_id not in seen:
                    seen.add(child_id)
                    next_frontier.append(child_id)
        if next_frontier:
            depth += 1
        frontier = next_frontier
    return seen, depth


def tree_metrics(root_id: str, posts_by_id: dict[str, Post], children: dict[str, list[str]]) -> TreeMetrics:
    reached, depth = reachable_from(root_id, children)
    subset = [posts_by_id[pid] for pid in reached if pid in posts_by_id]
    return TreeMetrics(
        size=len(subset),
        depth=depth,
        unique_accounts=len({p.account for p in subset}),
        total_retweets=sum(1 for p in subset if p.type == "retweet"),
        total_quotes=sum(1 for p in subset if p.type == "quote"),
        total_replies=sum(1 for p in subset if p.type == "reply"),
    )


def layout_horizontal(root_id: str, posts_by_id: dict[str, Post], children: dict[str, list[str]]) -> dict[str, tuple[int, int]]:
    """Position (depth, lane) de chaque post atteignable depuis root_id, pour
    un rendu en arbre horizontal (racine à gauche). `lane` : les feuilles
    reçoivent des lanes séquentielles ; un nœud interne prend la moyenne
    (arrondie) de ses enfants -- layout simple, suffisant pour un rendu lisible."""
    positions: dict[str, tuple[int, int]] = {}
    next_lane = [0]

    def visit(node_id: str, depth: int) -> int:
        kids = children.get(node_id, [])
        kids = [k for k in kids if k in posts_by_id]
        if not kids:
            lane = next_lane[0]
            next_lane[0] += 1
            positions[node_id] = (depth, lane)
            return lane
        lanes = [visit(k, depth + 1) for k in kids]
        lane = round(sum(lanes) / len(lanes))
        positions[node_id] = (depth, lane)
        return lane

    if root_id in posts_by_id:
        visit(root_id, 0)
    return positions
