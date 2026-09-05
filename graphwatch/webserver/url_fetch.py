"""Récupération d'une URL fournie explicitement par l'utilisateur via l'UI.

Tourne sur LA MACHINE DE L'UTILISATEUR (pas dans un sandbox partagé) : c'est
un choix explicite de l'utilisateur d'ajouter cette adresse précise, pas un
crawl automatique. Garde-fous minimaux car c'est un outil local mono-utilisateur,
pas un service exposé -- ne pas exposer ce endpoint sur un réseau non fiable."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

MAX_BYTES = 5_000_000
TIMEOUT_SECONDS = 15
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


class FetchError(Exception):
    pass


def fetch_url_text(url: str) -> tuple[str, str]:
    """Renvoie (titre, html_brut). Lève FetchError avec un message clair
    en cas de problème (schéma interdit, timeout, réponse trop grosse, etc.)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FetchError(f"schéma non autorisé: {parsed.scheme or '(vide)'} -- seuls http/https sont acceptés")
    if not parsed.netloc:
        raise FetchError("URL invalide")

    try:
        resp = requests.get(
            url, timeout=TIMEOUT_SECONDS, stream=True,
            headers={"User-Agent": "graph-watch/0.1 (outil local, ajout manuel par un utilisateur)"},
        )
    except requests.RequestException as e:
        raise FetchError(f"échec de la requête: {e}") from e

    if resp.status_code >= 400:
        raise FetchError(f"réponse HTTP {resp.status_code}")

    content = bytearray()
    for chunk in resp.iter_content(chunk_size=65536):
        content.extend(chunk)
        if len(content) > MAX_BYTES:
            raise FetchError(f"réponse trop volumineuse (> {MAX_BYTES // 1_000_000} Mo)")

    html = content.decode(resp.encoding or "utf-8", errors="ignore")
    title_match = _TITLE_RE.search(html)
    title = title_match.group(1).strip() if title_match else parsed.netloc
    return title, html
