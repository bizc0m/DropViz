#!/usr/bin/env python3
"""App desktop pour graph-watch (Linux) : pas de fenêtre native (pywebview
n'a pas de backend fiable et autonome sur Linux -- ça dépend d'un paquet
système GTK/Qt qu'on ne peut pas garantir présent), donc on ouvre le
navigateur par défaut à la place. Reste autonome : aucun Python à installer
à la main, aucun port à choisir, aucun terminal à gérer -- juste un onglet
de navigateur au lieu d'une fenêtre dédiée.

Lancement :  python desktop_app_linux.py
"""
from __future__ import annotations

import sys
import webbrowser

from desktop_common import log, start_server_and_wait_ready


def main() -> int:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    result = start_server_and_wait_ready()
    if result is None:
        return 1
    port, server_thread = result

    url = f"http://127.0.0.1:{port}/"
    print(f"graph-watch -> {url}  (Ctrl+C pour arrêter)")
    webbrowser.open(url)

    try:
        server_thread.join()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
