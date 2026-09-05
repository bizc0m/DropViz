"""Stockage SQLite des documents ingérés : sert de journal de provenance
et évite de retraiter deux fois le même contenu (dédup par hash)."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from graphwatch.ingest.normalize import Document

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    origin TEXT NOT NULL,
    title TEXT,
    text TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    published_at TEXT,
    processed INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_name);
"""


class DocumentStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def add_if_new(self, doc: Document) -> bool:
        """Insère le document s'il n'existe pas déjà. Renvoie True si nouveau."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            try:
                conn.execute(
                    "INSERT INTO documents "
                    "(doc_id, source_name, origin, title, text, fetched_at, published_at, processed) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                    (
                        doc.doc_id,
                        doc.source_name,
                        doc.origin,
                        doc.title,
                        doc.text,
                        doc.fetched_at.isoformat(),
                        doc.published_at.isoformat() if doc.published_at else None,
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def unprocessed(self, source_name: str) -> list[Document]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM documents WHERE source_name = ? AND processed = 0",
                (source_name,),
            ).fetchall()
        docs = []
        for r in rows:
            docs.append(
                Document(
                    source_name=r["source_name"],
                    origin=r["origin"],
                    title=r["title"] or "",
                    text=r["text"],
                    fetched_at=datetime.fromisoformat(r["fetched_at"]),
                    published_at=datetime.fromisoformat(r["published_at"]) if r["published_at"] else None,
                )
            )
        return docs

    def mark_processed(self, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executemany(
                "UPDATE documents SET processed = 1 WHERE doc_id = ?",
                [(d,) for d in doc_ids],
            )
            conn.commit()

    def stats(self) -> dict:
        with closing(sqlite3.connect(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            by_source = conn.execute(
                "SELECT source_name, COUNT(*) FROM documents GROUP BY source_name"
            ).fetchall()
        return {"total": total, "by_source": dict(by_source)}
