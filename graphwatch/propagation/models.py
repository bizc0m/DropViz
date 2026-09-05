"""Modèle de données pour l'analyse de propagation (fonction 1).

Contrairement au pipeline entités/relations (texte -> NER), ici la donnée
d'entrée est déjà structurée : des posts avec un fil explicite (parent_id).
Format attendu (JSON ou JSONL), un objet par post :

    {
      "id": "p1",                        # identifiant unique, requis
      "rumor": "rumor-x",                # regroupe les posts d'une même rumeur/sujet
      "account": "@alice",               # requis
      "content": "texte du post",
      "posted_at": "2024-01-01T10:00:00Z",  # requis, ISO 8601
      "parent_id": null,                 # id du post parent, ou null si racine
      "type": "original",                # original | retweet | quote | reply
      "metrics": {"likes": 10, "retweets": 5, "replies": 2}
    }

Aucune collecte automatique n'est faite : tu fournis les fichiers toi-même
(export API légitime, extraction déjà autorisée, etc.) -- voir README.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Post:
    id: str
    rumor: str
    account: str
    posted_at: datetime
    source_name: str
    origin: str
    content: str = ""
    parent_id: str | None = None
    type: str = "original"  # original | retweet | quote | reply
    likes: int = 0
    retweets: int = 0
    replies: int = 0


@dataclass
class BurstEvent:
    start: datetime
    end: datetime
    peak: datetime
    volume: int
    baseline_median: float


@dataclass
class SeedCandidate:
    post_id: str
    score: float
    tree_size: int
    tree_depth: int
    unique_accounts: int


@dataclass
class Propagator:
    account: str
    n_posts: int
    total_engagement: int
    betweenness: float


@dataclass
class PropagationResult:
    rumor: str
    seed_post_id: str | None
    tree_size: int
    max_depth: int
    unique_accounts: int
    total_retweets: int
    total_quotes: int
    total_replies: int
    unreached_posts: int  # posts de la rumeur non atteignables depuis le seed retenu
    bursts: list[BurstEvent] = field(default_factory=list)
    top_propagators: list[Propagator] = field(default_factory=list)
    seed_candidates: list[SeedCandidate] = field(default_factory=list)
