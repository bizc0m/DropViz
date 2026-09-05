"""Sérialise l'analyse de propagation en JSON pour la vue interactive."""
from __future__ import annotations

from graphwatch.propagation.models import Post, PropagationResult
from graphwatch.propagation.tree import children_map, layout_horizontal, reachable_from


def build_propagation_payload(
    *, rumor: str, posts: list[Post], result: PropagationResult,
    source_name: str, generated_at: str, setup: dict | None = None,
) -> dict:
    posts_by_id = {p.id: p for p in posts}
    children = children_map(posts)

    reached: set[str] = set()
    positions: dict[str, tuple[int, int]] = {}
    if result.seed_post_id:
        reached, _ = reachable_from(result.seed_post_id, children)
        positions = layout_horizontal(result.seed_post_id, posts_by_id, children)

    posts_json = []
    for p in posts:
        depth, lane = positions.get(p.id, (None, None))
        posts_json.append({
            "id": p.id,
            "account": p.account,
            "content": p.content,
            "postedAt": p.posted_at.isoformat(),
            "parentId": p.parent_id,
            "type": p.type,
            "likes": p.likes,
            "retweets": p.retweets,
            "replies": p.replies,
            "depth": depth,
            "lane": lane,
            "reached": p.id in reached,
        })

    bursts_json = [
        {
            "start": b.start.isoformat(),
            "end": b.end.isoformat(),
            "peak": b.peak.isoformat(),
            "volume": b.volume,
            "baselineMedian": b.baseline_median,
        }
        for b in result.bursts
    ]

    propagators_json = [
        {"account": pr.account, "nPosts": pr.n_posts, "totalEngagement": pr.total_engagement,
         "betweenness": pr.betweenness}
        for pr in result.top_propagators
    ]

    seed_candidates_json = [
        {"postId": c.post_id, "score": c.score, "treeSize": c.tree_size,
         "treeDepth": c.tree_depth, "uniqueAccounts": c.unique_accounts}
        for c in result.seed_candidates
    ]

    return {
        "meta": {
            "rumor": rumor,
            "sourceName": source_name,
            "generatedAt": generated_at,
            "seedPostId": result.seed_post_id,
            "treeSize": result.tree_size,
            "maxDepth": result.max_depth,
            "uniqueAccounts": result.unique_accounts,
            "totalRetweets": result.total_retweets,
            "totalQuotes": result.total_quotes,
            "totalReplies": result.total_replies,
            "unreachedPosts": result.unreached_posts,
            "totalPosts": len(posts),
            "nBursts": len(result.bursts),
            "setup": setup or {},
        },
        "posts": posts_json,
        "bursts": bursts_json,
        "propagators": propagators_json,
        "seedCandidates": seed_candidates_json,
    }
