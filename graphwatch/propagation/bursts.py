"""Détection des pics d'activité (bursts) par fenêtrage temporel + seuil médian.

Méthode standard (fenêtres fixes, seuil = k x médiane, fusion des fenêtres
adjacentes) -- documentée, pas une invention maison."""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta

from graphwatch.propagation.models import BurstEvent, Post


def detect_bursts(posts: list[Post], window_minutes: int = 60, multiplier: float = 2.0) -> list[BurstEvent]:
    if len(posts) < 3:
        return []

    timestamps = sorted(p.posted_at for p in posts)
    window = timedelta(minutes=window_minutes)
    start = timestamps[0]
    end = timestamps[-1]

    windows: list[tuple[datetime, datetime, int]] = []
    cursor = start
    while cursor <= end:
        w_end = cursor + window
        count = sum(1 for t in timestamps if cursor <= t < w_end)
        windows.append((cursor, w_end, count))
        cursor = w_end

    counts = [w[2] for w in windows]
    median = statistics.median(counts) if counts else 0
    # plancher : si la médiane est nulle (activité très éparse), on prend un
    # seuil absolu bas plutôt que 0 (qui flaguerait tout comme "burst")
    threshold = max(multiplier * median, 3)

    flagged = [w for w in windows if w[2] >= threshold]
    if not flagged:
        return []

    # fusionne les fenêtres adjacentes en un seul événement
    bursts: list[BurstEvent] = []
    current = [flagged[0]]
    for w in flagged[1:]:
        if w[0] <= current[-1][1]:  # contiguë ou chevauche la précédente
            current.append(w)
        else:
            bursts.append(_finalize_burst(current, median))
            current = [w]
    bursts.append(_finalize_burst(current, median))
    return bursts


def _finalize_burst(windows: list[tuple[datetime, datetime, int]], median: float) -> BurstEvent:
    peak_window = max(windows, key=lambda w: w[2])
    return BurstEvent(
        start=windows[0][0],
        end=windows[-1][1],
        peak=peak_window[0],
        volume=sum(w[2] for w in windows),
        baseline_median=median,
    )
