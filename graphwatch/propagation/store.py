"""Persistance des posts (SQLite) : dédup par id, cumulatif d'un cycle à l'autre."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from graphwatch.propagation.models import Post

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    rumor TEXT NOT NULL,
    account TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    source_name TEXT NOT NULL,
    origin TEXT NOT NULL,
    content TEXT,
    parent_id TEXT,
    type TEXT NOT NULL,
    likes INTEGER NOT NULL DEFAULT 0,
    retweets INTEGER NOT NULL DEFAULT 0,
    replies INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_posts_rumor ON posts(rumor);
"""


class PostStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def add_if_new(self, post: Post) -> bool:
        with closing(sqlite3.connect(self.db_path)) as conn:
            try:
                conn.execute(
                    "INSERT INTO posts (id, rumor, account, posted_at, source_name, origin, "
                    "content, parent_id, type, likes, retweets, replies) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (post.id, post.rumor, post.account, post.posted_at.isoformat(),
                     post.source_name, post.origin, post.content, post.parent_id,
                     post.type, post.likes, post.retweets, post.replies),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def rumors(self) -> list[str]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute("SELECT DISTINCT rumor FROM posts").fetchall()
        return [r[0] for r in rows]

    def posts_for_rumor(self, rumor: str) -> list[Post]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM posts WHERE rumor = ?", (rumor,)).fetchall()
        return [
            Post(
                id=r["id"], rumor=r["rumor"], account=r["account"],
                posted_at=datetime.fromisoformat(r["posted_at"]),
                source_name=r["source_name"], origin=r["origin"],
                content=r["content"] or "", parent_id=r["parent_id"], type=r["type"],
                likes=r["likes"], retweets=r["retweets"], replies=r["replies"],
            )
            for r in rows
        ]
