"""Détection du post 'graine' (origine probable) d'une rumeur.

Méthode : parmi les posts sans parent connu (racines candidates), on
construit l'arbre de chacun et on score par taille + profondeur + comptes
uniques, pondéré par l'ancienneté (les posts plus anciens sont favorisés,
mais pas de façon absolue -- un post ancien qui n'a rien engendré n'est
probablement pas la vraie graine)."""
from __future__ import annotations

from graphwatch.propagation.models import Post, SeedCandidate
from graphwatch.propagation.tree import children_map, tree_metrics


def find_candidate_roots(posts: list[Post]) -> list[Post]:
    """Racines candidates : posts sans parent_id, OU dont le parent n'est pas
    dans le jeu de données (thread partiellement collecté)."""
    ids = {p.id for p in posts}
    return [p for p in posts if not p.parent_id or p.parent_id not in ids]


def score_seed_candidates(
    posts: list[Post],
    weight_recency: float = 0.3,
    weight_size: float = 0.4,
    weight_depth: float = 0.15,
    weight_accounts: float = 0.15,
) -> list[SeedCandidate]:
    """Renvoie les candidats triés par score décroissant (le premier = graine
    retenue). Les poids sont un choix de départ raisonnable, pas une formule
    validée -- à ajuster selon le corpus."""
    if not posts:
        return []

    candidates = find_candidate_roots(posts)
    if not candidates:
        return []

    posts_by_id = {p.id: p for p in posts}
    children = children_map(posts)

    metrics_by_id = {c.id: tree_metrics(c.id, posts_by_id, children) for c in candidates}
    max_size = max((m.size for m in metrics_by_id.values()), default=1) or 1
    max_depth = max((m.depth for m in metrics_by_id.values()), default=1) or 1
    max_accounts = max((m.unique_accounts for m in metrics_by_id.values()), default=1) or 1

    timestamps = sorted(c.posted_at for c in candidates)
    t_min, t_max = timestamps[0], timestamps[-1]
    span = (t_max - t_min).total_seconds() or 1.0

    results = []
    for c in candidates:
        m = metrics_by_id[c.id]
        recency_score = 1.0 - ((c.posted_at - t_min).total_seconds() / span)  # 1 = le plus ancien
        score = (
            weight_recency * recency_score
            + weight_size * (m.size / max_size)
            + weight_depth * (m.depth / max_depth)
            + weight_accounts * (m.unique_accounts / max_accounts)
        )
        results.append(SeedCandidate(
            post_id=c.id, score=round(score, 4),
            tree_size=m.size, tree_depth=m.depth, unique_accounts=m.unique_accounts,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results
