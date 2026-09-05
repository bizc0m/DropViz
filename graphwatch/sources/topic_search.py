"""Source 'sujet' : suit un thème/mot-clé plutôt qu'une URL fixe.

Volontairement neutre par défaut : ce module NE scrape rien tout seul.
Tu branches le connecteur de recherche que tu as le droit d'utiliser
(API de presse, moteur interne, etc.) en enregistrant un fetcher — voir
`register_topic_fetcher` ci-dessous. Sans fetcher enregistré, la source
tourne mais ne remonte aucun document (log un avertissement), ce qui
évite d'aller chercher des pages non vérifiées à l'insu de l'utilisateur.
"""
from __future__ import annotations

import logging
from typing import Callable, Iterable

from graphwatch.ingest.normalize import Document
from graphwatch.sources.base import Source

log = logging.getLogger(__name__)

# Signature attendue : fetcher(query: str) -> Iterable[dict]
# chaque dict doit avoir au moins {"origin": str, "title": str, "text": str}
TopicFetcher = Callable[[str], Iterable[dict]]

_REGISTRY: dict[str, TopicFetcher] = {}


def register_topic_fetcher(name: str, fetcher: TopicFetcher) -> None:
    """À appeler dans ton propre code de démarrage (avant run.py) pour brancher
    une vraie source de recherche, ex:

        from graphwatch.sources.topic_search import register_topic_fetcher
        register_topic_fetcher("default", my_news_api_search)
    """
    _REGISTRY[name] = fetcher


class TopicSource(Source):
    def fetch(self) -> Iterable[Document]:
        query = self.options.get("query")
        if not query:
            raise ValueError(f"source topic '{self.name}' sans 'query' dans la config")

        fetcher_name = self.options.get("fetcher", "default")
        fetcher = _REGISTRY.get(fetcher_name)
        if fetcher is None:
            log.warning(
                "aucun fetcher enregistré pour la source topic '%s' "
                "(fetcher='%s') — voir graphwatch/sources/topic_search.py. "
                "0 document remonté ce cycle.",
                self.name, fetcher_name,
            )
            return []

        docs = []
        for item in fetcher(query):
            docs.append(
                Document(
                    source_name=self.name,
                    origin=item.get("origin", query),
                    title=item.get("title", query),
                    text=item.get("text", ""),
                    extra={"query": query},
                )
            )
        return docs
