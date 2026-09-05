"""File de validation humaine : on propose une adresse (RSS/dossier/sujet),
le système va chercher un aperçu, et seulement après approbation explicite
la source devient active et suivie automatiquement par le scheduler.

Pas d'ingestion à l'aveugle : `propose()` ne fait qu'un appel de prévisualisation
(parse le flux, liste les fichiers) — aucun document n'est stocké tant que la
source n'est pas approuvée.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_sources (
    name TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    options_json TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL,
    extractor TEXT NOT NULL,
    reliability TEXT NOT NULL DEFAULT 'F',
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    preview TEXT,
    proposed_at TEXT NOT NULL,
    reviewed_at TEXT
);
"""


@dataclass
class Proposal:
    name: str
    type: str
    options: dict
    interval_minutes: int
    extractor: str
    reliability: str
    status: str
    preview: str
    proposed_at: str
    reviewed_at: str | None


class PendingQueue:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def propose(
        self, *, name: str, type: str, options: dict,
        interval_minutes: int = 1440, extractor: str = "spacy", reliability: str = "F",
    ) -> Proposal:
        preview = _build_preview(type, options)
        now = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO pending_sources "
                "(name, type, options_json, interval_minutes, extractor, reliability, status, preview, proposed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET "
                "type=excluded.type, options_json=excluded.options_json, "
                "interval_minutes=excluded.interval_minutes, extractor=excluded.extractor, "
                "reliability=excluded.reliability, "
                "status='pending', preview=excluded.preview, proposed_at=excluded.proposed_at, reviewed_at=NULL",
                (name, type, json.dumps(options), interval_minutes, extractor, reliability, preview, now),
            )
            conn.commit()
        return self.get(name)

    def get(self, name: str) -> Proposal | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM pending_sources WHERE name = ?", (name,)).fetchone()
        return _row_to_proposal(row) if row else None

    def list(self, status: str | None = "pending") -> list[Proposal]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                rows = conn.execute(
                    "SELECT * FROM pending_sources WHERE status = ? ORDER BY proposed_at", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM pending_sources ORDER BY proposed_at").fetchall()
        return [_row_to_proposal(r) for r in rows]

    def set_status(self, name: str, status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE pending_sources SET status = ?, reviewed_at = ? WHERE name = ?",
                (status, now, name),
            )
            conn.commit()


def _row_to_proposal(row: sqlite3.Row) -> Proposal:
    return Proposal(
        name=row["name"], type=row["type"], options=json.loads(row["options_json"]),
        interval_minutes=row["interval_minutes"], extractor=row["extractor"],
        reliability=row["reliability"],
        status=row["status"], preview=row["preview"] or "",
        proposed_at=row["proposed_at"], reviewed_at=row["reviewed_at"],
    )


def _build_preview(type: str, options: dict) -> str:
    """Appel de prévisualisation SEULEMENT — ne stocke aucun document.
    Sert de base pour la décision humaine avant approbation."""
    try:
        if type == "rss":
            import feedparser
            url = options.get("url", "")
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                return f"⚠ flux illisible: {getattr(parsed, 'bozo_exception', 'erreur inconnue')}"
            titles = [e.get("title", "?") for e in parsed.entries[:5]]
            return f"{len(parsed.entries)} entrée(s). Aperçu: " + " | ".join(titles)

        if type == "corpus_folder":
            folder = Path(options.get("path", ""))
            if not folder.exists():
                return f"⚠ dossier introuvable: {folder}"
            files = [f for f in folder.rglob("*") if f.is_file()]
            return f"{len(files)} fichier(s) trouvé(s). Ex: " + ", ".join(f.name for f in files[:5])

        if type == "topic":
            return f"sujet '{options.get('query', '')}' — nécessite un fetcher branché avant de remonter des documents"

        if type == "post_thread":
            from graphwatch.propagation.ingest import read_posts_from_folder
            folder = Path(options.get("path", ""))
            if not folder.exists():
                return f"⚠ dossier introuvable: {folder}"
            posts = read_posts_from_folder(folder, source_name="preview")
            rumors = sorted({p.rumor for p in posts})
            return f"{len(posts)} post(s), {len(rumors)} rumeur(s): " + ", ".join(rumors[:5])

        return "type de source inconnu, pas d'aperçu disponible"
    except Exception as e:
        return f"⚠ erreur pendant l'aperçu: {e}"
