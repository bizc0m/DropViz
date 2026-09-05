"""Chargement et validation de la configuration YAML."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    pass


RELIABILITY_LEVELS = {
    "A": "totalement fiable (historique parfait)",
    "B": "généralement fiable (quelques doutes)",
    "C": "assez fiable (doutes significatifs)",
    "D": "pas vraiment fiable (souvent inexacte)",
    "E": "peu fiable (souvent fausse)",
    "F": "ne peut être jugée (source neuve ou inconnue)",
}


@dataclass
class SourceConfig:
    name: str
    type: str  # rss | corpus_folder | topic
    interval_minutes: int
    extractor: str
    options: dict[str, Any] = field(default_factory=dict)
    # Admiralty Code A-F : jugement humain sur CETTE source, à trancher à la
    # main. "F" par défaut -- pas de confiance présumée tant que non configuré.
    reliability: str = "F"


@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-5"
    api_key_env: str = "ANTHROPIC_API_KEY"

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


@dataclass
class GlobalConfig:
    extractor: str = "spacy"
    spacy_model: str = "fr_core_news_md"
    llm: LLMConfig = field(default_factory=LLMConfig)
    graph_mode: str = "shared"  # shared | per_source
    data_dir: Path = Path("./data")
    notebooks_dir: Path = Path("./notebooks")
    timezone: str = "Europe/Paris"
    min_corroborating_sources: int = 2


@dataclass
class AppConfig:
    global_: GlobalConfig
    sources: list[SourceConfig]

    def source_by_name(self, name: str) -> SourceConfig:
        for s in self.sources:
            if s.name == name:
                return s
        raise ConfigError(f"source inconnue: {name}")


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"fichier de config introuvable: {path}. "
            "Copie config.example.yaml en config.yaml et adapte-le."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    g_raw = raw.get("global", {})
    llm_raw = g_raw.get("llm", {})
    global_cfg = GlobalConfig(
        extractor=g_raw.get("extractor", "spacy"),
        spacy_model=g_raw.get("spacy", {}).get("model", "fr_core_news_md"),
        llm=LLMConfig(
            provider=llm_raw.get("provider", "anthropic"),
            model=llm_raw.get("model", "claude-sonnet-5"),
            api_key_env=llm_raw.get("api_key_env", "ANTHROPIC_API_KEY"),
        ),
        graph_mode=g_raw.get("graph_mode", "shared"),
        data_dir=Path(g_raw.get("data_dir", "./data")),
        notebooks_dir=Path(g_raw.get("notebooks_dir", "./notebooks")),
        timezone=g_raw.get("timezone", "Europe/Paris"),
        min_corroborating_sources=int(g_raw.get("min_corroborating_sources", 2)),
    )

    sources = _parse_sources(raw.get("sources", []), global_cfg)

    # sources validées via `python run.py approve NAME` (queue.py) : un fichier à
    # part, jamais écrit à la main, pour ne pas se battre avec les commentaires
    # de config.yaml. Un nom déjà présent dans config.yaml prend le dessus.
    approved_path = path.parent / APPROVED_SOURCES_FILENAME
    if approved_path.exists():
        approved_raw = yaml.safe_load(approved_path.read_text(encoding="utf-8")) or {}
        existing_names = {s.name for s in sources}
        for s in _parse_sources(approved_raw.get("sources", []), global_cfg):
            if s.name not in existing_names:
                sources.append(s)

    if not sources:
        raise ConfigError(
            f"aucune source définie ({path.name} et {APPROVED_SOURCES_FILENAME} sont vides)"
        )

    global_cfg.data_dir.mkdir(parents=True, exist_ok=True)
    global_cfg.notebooks_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(global_=global_cfg, sources=sources)


def _parse_sources(raw_list: list[dict], global_cfg: GlobalConfig) -> list[SourceConfig]:
    known = {"name", "type", "interval_minutes", "extractor", "reliability"}
    sources = []
    for s in raw_list:
        if "name" not in s or "type" not in s:
            raise ConfigError(f"source mal formée (name/type requis): {s}")
        reliability = str(s.get("reliability", "F")).upper()
        if reliability not in RELIABILITY_LEVELS:
            raise ConfigError(
                f"source '{s['name']}': reliability '{reliability}' invalide, "
                f"attendu une lettre parmi {sorted(RELIABILITY_LEVELS)}"
            )
        sources.append(
            SourceConfig(
                name=s["name"],
                type=s["type"],
                interval_minutes=int(s.get("interval_minutes", 1440)),
                extractor=s.get("extractor", global_cfg.extractor),
                options={k: v for k, v in s.items() if k not in known},
                reliability=reliability,
            )
        )
    return sources


APPROVED_SOURCES_FILENAME = "approved_sources.yaml"


def append_approved_source(config_path: str | Path, source: SourceConfig) -> Path:
    """Ajoute une source validée dans approved_sources.yaml (à côté de config.yaml),
    sans toucher au fichier édité à la main. Appelé par `python run.py approve NAME`."""
    approved_path = Path(config_path).parent / APPROVED_SOURCES_FILENAME
    doc = yaml.safe_load(approved_path.read_text(encoding="utf-8")) if approved_path.exists() else None
    doc = doc or {"sources": []}
    doc.setdefault("sources", [])
    doc["sources"] = [s for s in doc["sources"] if s.get("name") != source.name]
    entry = {"name": source.name, "type": source.type, "interval_minutes": source.interval_minutes,
              "extractor": source.extractor, "reliability": source.reliability, **source.options}
    doc["sources"].append(entry)
    approved_path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return approved_path
