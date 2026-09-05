from graphwatch.config import SourceConfig
from graphwatch.sources.base import Source
from graphwatch.sources.corpus_folder import CorpusFolderSource
from graphwatch.sources.rss import RSSSource
from graphwatch.sources.topic_search import TopicSource

_REGISTRY = {
    "rss": RSSSource,
    "corpus_folder": CorpusFolderSource,
    "topic": TopicSource,
}


def build_source(cfg: SourceConfig) -> Source:
    cls = _REGISTRY.get(cfg.type)
    if cls is None:
        raise ValueError(f"type de source inconnu: {cfg.type} (source '{cfg.name}')")
    return cls(name=cfg.name, options=cfg.options)
