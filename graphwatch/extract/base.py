"""Interface commune aux backends d'extraction entités/relations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from graphwatch.ingest.normalize import Document


@dataclass
class Relation:
    """Une relation extraite, toujours rattachée à sa preuve source.

    confidence : 0-1, estimation de fiabilité de l'extraction elle-même
    (PAS une estimation de vérité du contenu — juste "l'extracteur a-t-il
    bien lu cette relation dans le texte").
    """

    subject: str
    predicate: str
    object: str
    source_name: str
    origin: str
    doc_id: str
    snippet: str
    confidence: float = 1.0
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extractor: str = "unknown"
    # Fiabilité Admiralty Code (A-F) de la SOURCE (pas du contenu) : configurée
    # à la main par source dans config.yaml, jamais déduite automatiquement.
    # "F" (ne peut être jugée) par défaut -- pas de confiance présumée.
    source_reliability: str = "F"


class Extractor(ABC):
    @abstractmethod
    def extract(self, doc: Document) -> list[Relation]:
        ...
