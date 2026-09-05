"""Calcul des principaux propagateurs : volume de posts, engagement, et
centralité (betweenness) dans l'arbre -- un compte à betweenness élevée est
un "pont" par lequel beaucoup de branches passent, pas juste un gros poster."""
from __future__ import annotations

import networkx as nx

from graphwatch.propagation.models import Post, Propagator


def top_propagators(posts: list[Post], reached_ids: set[str], top_n: int = 20) -> list[Propagator]:
    subset = [p for p in posts if p.id in reached_ids]
    if not subset:
        return []

    tree = nx.DiGraph()
    for p in subset:
        tree.add_node(p.id)
    for p in subset:
        if p.parent_id and p.parent_id in reached_ids:
            tree.add_edge(p.parent_id, p.id)

    betweenness = nx.betweenness_centrality(tree) if tree.number_of_nodes() > 2 else {n: 0.0 for n in tree.nodes}

    by_account: dict[str, list[Post]] = {}
    for p in subset:
        by_account.setdefault(p.account, []).append(p)

    results = []
    for account, account_posts in by_account.items():
        engagement = sum(p.likes + p.retweets + p.replies for p in account_posts)
        acct_betweenness = max((betweenness.get(p.id, 0.0) for p in account_posts), default=0.0)
        results.append(Propagator(
            account=account,
            n_posts=len(account_posts),
            total_engagement=engagement,
            betweenness=round(acct_betweenness, 5),
        ))

    results.sort(key=lambda r: (r.n_posts, r.total_engagement), reverse=True)
    return results[:top_n]
