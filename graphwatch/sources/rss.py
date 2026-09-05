"""Source RSS/Atom : rescanne un flux à chaque cycle et renvoie les entrées."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import feedparser

from graphwatch.ingest.normalize import Document
from graphwatch.sources.base import Source

log = logging.getLogger(__name__)


class RSSSource(Source):
    def fetch(self) -> Iterable[Document]:
        url = self.options.get("url")
        if not url:
            raise ValueError(f"source RSS '{self.name}' sans 'url' dans la config")

        parsed = feedparser.parse(url)
        if parsed.bozo and not parsed.entries:
            log.warning("flux RSS illisible pour %s (%s): %s", self.name, url, parsed.bozo_exception)
            return []

        docs = []
        for entry in parsed.entries:
            text = entry.get("summary", "") or entry.get("description", "")
            content_list = entry.get("content")
            if content_list:
                text = " ".join(c.get("value", "") for c in content_list) or text

            published_at = None
            if entry.get("published_parsed"):
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

            docs.append(
                Document(
                    source_name=self.name,
                    origin=entry.get("link", url),
                    title=entry.get("title", ""),
                    text=text,
                    published_at=published_at,
                    extra={"feed_url": url},
                )
            )
        return docs
