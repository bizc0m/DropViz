"""Scheduler persistant : un job par source, chacun à son propre intervalle
('tous les X' défini dans config.yaml). Process long-running (python run.py serve).

Vérifie aussi périodiquement `approved_sources.yaml` (rempli par
`python run.py approve NAME`) et ajoute automatiquement au planning toute
source nouvellement validée — sans redémarrer le process."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from graphwatch.config import AppConfig, load_config
from graphwatch.pipeline import run_cycle

log = logging.getLogger(__name__)

_SYNC_JOB_ID = "__sync_approved_sources__"
_SYNC_INTERVAL_MINUTES = 5


def _job(state: dict, source_name: str) -> None:
    source_cfg = state["config"].source_by_name(source_name)
    try:
        run_cycle(state["config"], source_cfg)
    except Exception:
        log.exception("[%s] cycle échoué", source_name)


def _schedule_source(scheduler: BlockingScheduler, state: dict, source_cfg, run_immediately: bool) -> None:
    scheduler.add_job(
        _job,
        trigger=IntervalTrigger(minutes=source_cfg.interval_minutes),
        args=[state, source_cfg.name],
        id=source_cfg.name,
        next_run_time=datetime.now() if run_immediately else None,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=source_cfg.interval_minutes * 60,
        replace_existing=True,
    )
    log.info(
        "job planifié: %s (toutes les %d min, extractor=%s)",
        source_cfg.name, source_cfg.interval_minutes, source_cfg.extractor,
    )


def _sync_approved_sources(scheduler: BlockingScheduler, state: dict, config_path: Path) -> None:
    """Recharge la config (fusionne approved_sources.yaml) et planifie
    immédiatement toute source qu'on ne suivait pas encore."""
    try:
        fresh = load_config(config_path)
    except Exception:
        log.exception("rechargement de la config échoué, on garde l'ancienne")
        return

    known_ids = {j.id for j in scheduler.get_jobs()}
    new_ones = [s for s in fresh.sources if s.name not in known_ids]
    state["config"] = fresh
    for source_cfg in new_ones:
        log.info("nouvelle source validée détectée: %s -> planification immédiate", source_cfg.name)
        _schedule_source(scheduler, state, source_cfg, run_immediately=True)


def build_scheduler(app_config: AppConfig, config_path: Path, run_immediately: bool = True) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=app_config.global_.timezone)
    state = {"config": app_config}

    for source_cfg in app_config.sources:
        _schedule_source(scheduler, state, source_cfg, run_immediately)

    scheduler.add_job(
        _sync_approved_sources,
        trigger=IntervalTrigger(minutes=_SYNC_INTERVAL_MINUTES),
        args=[scheduler, state, config_path],
        id=_SYNC_JOB_ID,
        max_instances=1,
        coalesce=True,
    )
    log.info("veille des sources validées: toutes les %d min", _SYNC_INTERVAL_MINUTES)

    return scheduler
