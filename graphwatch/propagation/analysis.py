"""Orchestre l'analyse de propagation complète pour une rumeur."""
from __future__ import annotations

from graphwatch.propagation.bursts import detect_bursts
from graphwatch.propagation.models import Post, PropagationResult
from graphwatch.propagation.propagators import top_propagators
from graphwatch.propagation.seed import score_seed_candidates
from graphwatch.propagation.tree import children_map, reachable_from, tree_metrics


def run_propagation_analysis(rumor: str, posts: list[Post]) -> PropagationResult:
    if not posts:
        return PropagationResult(
            rumor=rumor, seed_post_id=None, tree_size=0, max_depth=0, unique_accounts=0,
            total_retweets=0, total_quotes=0, total_replies=0, unreached_posts=0,
        )

    candidates = score_seed_candidates(posts)
    seed_id = candidates[0].post_id if candidates else None

    posts_by_id = {p.id: p for p in posts}
    children = children_map(posts)

    if seed_id:
        reached, _ = reachable_from(seed_id, children)
        metrics = tree_metrics(seed_id, posts_by_id, children)
    else:
        reached, metrics = set(), None

    bursts = detect_bursts(posts)
    propagators = top_propagators(posts, reached) if reached else []

    return PropagationResult(
        rumor=rumor,
        seed_post_id=seed_id,
        tree_size=metrics.size if metrics else 0,
        max_depth=metrics.depth if metrics else 0,
        unique_accounts=metrics.unique_accounts if metrics else 0,
        total_retweets=metrics.total_retweets if metrics else 0,
        total_quotes=metrics.total_quotes if metrics else 0,
        total_replies=metrics.total_replies if metrics else 0,
        unreached_posts=len(posts) - len(reached),
        bursts=bursts,
        top_propagators=propagators,
        seed_candidates=candidates[:10],
    )
