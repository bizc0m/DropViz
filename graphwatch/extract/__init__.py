from graphwatch.config import GlobalConfig, SourceConfig
from graphwatch.extract.base import Extractor, Relation
from graphwatch.extract.llm_extractor import LLMExtractor
from graphwatch.extract.spacy_extractor import SpacyExtractor

_spacy_cache: dict[str, SpacyExtractor] = {}
_llm_cache: dict[str, LLMExtractor] = {}


def build_extractor(backend: str, source_cfg: SourceConfig, global_cfg: GlobalConfig) -> Extractor:
    if backend == "spacy":
        model = source_cfg.options.get("spacy_model", global_cfg.spacy_model)
        if model not in _spacy_cache:
            _spacy_cache[model] = SpacyExtractor(model_name=model)
        return _spacy_cache[model]

    if backend == "llm":
        key = f"{global_cfg.llm.model}:{global_cfg.llm.api_key_env}"
        if key not in _llm_cache:
            _llm_cache[key] = LLMExtractor(
                model=global_cfg.llm.model, api_key_env=global_cfg.llm.api_key_env
            )
        return _llm_cache[key]

    raise ValueError(f"backend d'extraction inconnu: {backend}")
