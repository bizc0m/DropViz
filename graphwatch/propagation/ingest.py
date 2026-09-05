"""Lecture des fichiers de posts (JSON/JSONL) déposés dans un dossier.
Même logique que corpus_folder.py : dépose des fichiers, seuls les posts
jamais vus (par id) sont retraités au cycle suivant."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from dateutil import parser as date_parser

from graphwatch.propagation.models import Post

log = logging.getLogger(__name__)


def _parse_post(raw: dict, source_name: str, origin: str) -> Post | None:
    if "id" not in raw or "account" not in raw or "posted_at" not in raw:
        log.warning("post ignoré (id/account/posted_at requis): %s", raw)
        return None
    metrics = raw.get("metrics", {}) or {}
    try:
        posted_at = date_parser.isoparse(raw["posted_at"]) if isinstance(raw["posted_at"], str) else raw["posted_at"]
    except (ValueError, TypeError) as e:
        log.warning("post %s ignoré, posted_at illisible: %s", raw.get("id"), e)
        return None

    return Post(
        id=str(raw["id"]),
        rumor=str(raw.get("rumor", "default")),
        account=str(raw["account"]),
        posted_at=posted_at,
        source_name=source_name,
        origin=origin,
        content=str(raw.get("content", "")),
        parent_id=str(raw["parent_id"]) if raw.get("parent_id") else None,
        type=str(raw.get("type", "original")),
        likes=int(metrics.get("likes", 0)),
        retweets=int(metrics.get("retweets", 0)),
        replies=int(metrics.get("replies", 0)),
    )


def read_posts_from_folder(path: str | Path, source_name: str) -> list[Post]:
    folder = Path(path)
    if not folder.exists():
        log.warning("dossier de posts introuvable: %s", folder)
        return []

    posts: list[Post] = []
    for f in sorted(folder.rglob("*")):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        try:
            if ext == ".jsonl":
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines()):
                    line = line.strip()
                    if not line:
                        continue
                    post = _parse_post(json.loads(line), source_name, f"{f}#{i}")
                    if post:
                        posts.append(post)
            elif ext == ".json":
                raw = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
                items = raw if isinstance(raw, list) else [raw]
                for i, item in enumerate(items):
                    post = _parse_post(item, source_name, f"{f}#{i}")
                    if post:
                        posts.append(post)
        except Exception:
            log.exception("échec lecture %s", f)
    return posts
