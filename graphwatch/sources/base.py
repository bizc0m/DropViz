"""Interface commune à toutes les sources d'ingestion."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from graphwatch.ingest.normalize import Document


class Source(ABC):
    """Une source sait produire une liste de Document à chaque appel de fetch().
    Elle ne gère PAS elle-même la dédup/planification — c'est le pipeline qui s'en charge."""

    def __init__(self, name: str, options: dict):
        self.name = name
        self.options = options

    @abstractmethod
    def fetch(self) -> Iterable[Document]:
        ...
