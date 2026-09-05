"""Modèle de document normalisé + utilitaires de nettoyage."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


_WS_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub(" ", text)


def clean_text(text: str) -> str:
    text = strip_html(text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Document:
    """Unité de base ingérée par le pipeline. Provenance obligatoire."""

    source_name: str
    origin: str          # URL, chemin fichier, ou identifiant de requête
    title: str
    text: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: datetime | None = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.text = clean_text(self.text)
        self.title = clean_text(self.title)

    @property
    def doc_id(self) -> str:
        return content_hash(f"{self.source_name}|{self.origin}|{self.text}")
