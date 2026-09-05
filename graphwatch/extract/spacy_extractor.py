"""Extraction locale par NER (spaCy) + co-occurrence phrase-à-phrase.

Rapide, gratuit, offline. Ne capture pas la nature sémantique de la relation
(on ne sait pas "qui a fait quoi à qui", seulement "ces entités apparaissent
ensemble") — le `predicate` est donc générique ("cooccurrence"). Suffisant
pour la centralité et la détection de communautés ; pour des relations plus
fines, utiliser le backend LLM.
"""
from __future__ import annotations

import logging
from itertools import combinations

from graphwatch.extract.base import Extractor, Relation
from graphwatch.ingest.normalize import Document

log = logging.getLogger(__name__)

_ENTITY_LABELS = {
    # labels spaCy usuels (modèles fr_core_news_* et en_core_web_*)
    "PER", "PERSON", "ORG", "GPE", "LOC", "NORP", "FAC", "EVENT",
}


class SpacyExtractor(Extractor):
    def __init__(self, model_name: str = "fr_core_news_md"):
        self.model_name = model_name
        self._nlp = None

    def _load(self):
        if self._nlp is not None:
            return self._nlp
        import spacy
        try:
            self._nlp = spacy.load(self.model_name)
        except OSError as e:
            raise RuntimeError(
                f"modèle spaCy '{self.model_name}' non installé. "
                f"Lance: python -m spacy download {self.model_name}"
            ) from e
        return self._nlp

    def extract(self, doc: Document) -> list[Relation]:
        nlp = self._load()
        spacy_doc = nlp(doc.text)

        relations: list[Relation] = []
        for sent in spacy_doc.sents:
            ents = [e for e in sent.ents if e.label_ in _ENTITY_LABELS]
            names = sorted({e.text.strip() for e in ents if e.text.strip()})
            if len(names) < 2:
                continue
            snippet = sent.text.strip()
            for a, b in combinations(names, 2):
                relations.append(
                    Relation(
                        subject=a,
                        predicate="cooccurrence",
                        object=b,
                        source_name=doc.source_name,
                        origin=doc.origin,
                        doc_id=doc.doc_id,
                        snippet=snippet[:500],
                        confidence=1.0,
                        extractor="spacy",
                    )
                )
        return relations
