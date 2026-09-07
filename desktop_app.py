#!/usr/bin/env python3
"""App desktop pour graph-watch (macOS / Windows) : une seule fenêtre
native, aucun port à choisir, aucun onglet de navigateur à retrouver, aucun
terminal à gérer une fois lancée. Utilise l'API webview native du système
(WKWebView sur macOS, WebView2 sur Windows) -- rien à installer en plus sur
ces deux OS. Sur Linux, pas de backend natif équivalent fiable : voir
desktop_app_linux.py (ouvre le navigateur par défaut à la place).

Lancement :  python desktop_app.py
(nécessite `pip install pywebview` -- voir requirements-desktop.txt)
"""
from __future__ import annotations

import sys

from desktop_common import log, start_server_and_wait_ready


def main() -> int:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    try:
        import webview
    except ImportError:
        print("Il manque 'pywebview' : pip install -r requirements-desktop.txt", file=sys.stderr)
        return 1
    except Exception as e:
        # sur Linux, pywebview a besoin d'un backend GTK/Qt système -- une
        # absence de backend remonte ici, pas comme un simple ImportError.
        # Sur Mac/Windows ce cas ne devrait jamais arriver (API native).
        print(f"pywebview n'a pas pu démarrer ({e}).", file=sys.stderr)
        print("Sur Linux, utilise plutôt : python desktop_app_linux.py", file=sys.stderr)
        return 1

    result = start_server_and_wait_ready()
    if result is None:
        return 1
    port, _server_thread = result

    webview.create_window("graph-watch", f"http://127.0.0.1:{port}/", width=1000, height=800, min_size=(700, 500))
    webview.start()
    # la fenêtre fermée = le process se termine = le thread daemon du serveur meurt avec lui
    return 0


if __name__ == "__main__":
    sys.exit(main())
