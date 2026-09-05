"""Extraction par LLM (Claude) : plus fine sur les relations implicites,
mais coûte un appel API par document et nécessite une clé configurée.

Utilise l'outil forcé (tool_choice) pour obtenir un JSON strict et
fiable plutôt que de parser du texte libre.
"""
from __future__ import annotations

import logging
import os

from graphwatch.extract.base import Extractor, Relation
from graphwatch.ingest.normalize import Document

log = logging.getLogger(__name__)

_TOOL_SCHEMA = {
    "name": "record_relations",
    "description": "Enregistre les relations explicitement énoncées dans le texte fourni.",
    "input_schema": {
        "type": "object",
        "properties": {
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "predicate": {
                            "type": "string",
                            "description": "verbe/relation court, ex: 'travaille avec', 'a rencontré', 'finance'",
                        },
                        "object": {"type": "string"},
                        "snippet": {
                            "type": "string",
                            "description": "citation exacte du passage source justifiant la relation",
                        },
                        "confidence": {
                            "type": "number",
                            "description": (
                                "0-1. Mets une confiance BASSE (<0.5) si le texte utilise un "
                                "langage conditionnel/allégué ('selon', 'aurait', 'accusé de'), "
                                "et HAUTE (>0.8) uniquement si le fait est énoncé sans réserve "
                                "par une source qui semble primaire."
                            ),
                        },
                    },
                    "required": ["subject", "predicate", "object", "snippet", "confidence"],
                },
            }
        },
        "required": ["relations"],
    },
}

_SYSTEM_PROMPT = """Tu extrais des relations entre entités (personnes, organisations, lieux, \
événements) STRICTEMENT à partir du texte fourni, pour construire un graphe d'analyse.

Règles impératives :
- N'invente rien. Une relation n'est enregistrée que si elle est explicitement énoncée dans le texte.
- Cite le passage exact (`snippet`) qui justifie chaque relation.
- Si le texte rapporte une allégation, une rumeur, ou utilise un conditionnel ("aurait", \
"selon des sources anonymes", "accusé de"), enregistre quand même la relation mais avec \
une confidence basse — ne la reformule PAS comme un fait établi.
- Tu ne juges pas la véracité du contenu, tu documentes fidèlement ce que le texte affirme \
et avec quelle certitude il l'affirme.
- N'extrais pas de relation à partir d'un simple listing/liste de noms sans lien explicite énoncé."""


class LLMExtractor(Extractor):
    def __init__(self, model: str = "claude-sonnet-5", api_key_env: str = "ANTHROPIC_API_KEY"):
        self.model = model
        self.api_key_env = api_key_env
        self._client = None

    def _load_client(self):
        if self._client is not None:
            return self._client
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"variable d'environnement {self.api_key_env} absente. "
                "Configure ta clé API Anthropic pour utiliser le backend LLM."
            )
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def extract(self, doc: Document) -> list[Relation]:
        if not doc.text.strip():
            return []

        client = self._load_client()
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                tools=[_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "record_relations"},
                messages=[
                    {
                        "role": "user",
                        "content": f"Titre: {doc.title}\n\nTexte:\n{doc.text[:12000]}",
                    }
                ],
            )
        except Exception as e:
            log.warning("appel LLM échoué pour doc %s (%s): %s", doc.doc_id, doc.origin, e)
            return []

        tool_use = next((b for b in resp.content if b.type == "tool_use"), None)
        if tool_use is None:
            log.warning("pas de tool_use dans la réponse LLM pour doc %s", doc.doc_id)
            return []

        relations = []
        for r in tool_use.input.get("relations", []):
            try:
                relations.append(
                    Relation(
                        subject=str(r["subject"]).strip(),
                        predicate=str(r["predicate"]).strip(),
                        object=str(r["object"]).strip(),
                        source_name=doc.source_name,
                        origin=doc.origin,
                        doc_id=doc.doc_id,
                        snippet=str(r.get("snippet", ""))[:500],
                        confidence=float(r.get("confidence", 0.5)),
                        extractor=f"llm:{self.model}",
                    )
                )
            except (KeyError, ValueError, TypeError) as e:
                log.warning("relation LLM mal formée ignorée: %s (%s)", r, e)
        return relations
