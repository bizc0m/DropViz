#!/usr/bin/env python3
"""App desktop pour graph-watch : une seule fenêtre native, aucun port à
choisir, aucun onglet de navigateur à retrouver, aucun terminal à gérer une
fois lancée. Le port est choisi automatiquement (libre sur la machine) et
reste invisible -- ce n'est plus un problème de l'utilisateur.

Lancement :  python desktop_app.py
(nécessite `pip install pywebview` -- voir requirements-desktop.txt)
"""
from __future__ import annotations

import logging
import socket
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

log = logging.getLogger("graph-watch.desktop")


def _free_port() -> int:
    """Demande à l'OS un port libre -- on ne choisit jamais nous-mêmes un
    numéro fixe, ça évite complètement la classe de bug 'le port est pris'."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ensure_config() -> Path:
    config_path = REPO_ROOT / "config.yaml"
    if not config_path.exists():
        example = REPO_ROOT / "config.example.yaml"
        config_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        log.info("config.yaml créé à partir de l'exemple (%s)", config_path)
    return config_path


def _serve(port: int, config_path: Path, ready: threading.Event) -> None:
    import uvicorn

    from graphwatch.webserver.app import create_app

    app = create_app(config_path)

    class _Server(uvicorn.Server):
        def install_signal_handlers(self) -> None:
            pass  # on tourne dans un thread, pas le thread principal -- uvicorn s'y refuse sinon

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = _Server(config)

    def _signal_ready() -> None:
        # attend que uvicorn ait vraiment bindé le port avant de créer la fenêtre --
        # sinon la fenêtre peut s'ouvrir sur une page blanche si elle arrive trop tôt.
        while not server.started:
            threading.Event().wait(0.05)
        ready.set()

    threading.Thread(target=_signal_ready, daemon=True).start()
    server.run()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    try:
        import webview
    except ImportError:
        print("Il manque 'pywebview' : pip install -r requirements-desktop.txt", file=sys.stderr)
        return 1
    except Exception as e:
        # sur Linux, pywebview a besoin d'un backend GTK/Qt système -- une
        # absence de backend remonte ici, pas comme un simple ImportError
        print(f"pywebview n'a pas pu démarrer ({e}).", file=sys.stderr)
        print("Sur Linux, installe un backend : sudo apt install python3-gi gir1.2-webkit2-4.1"
              "  (ou : pip install pyqt6 pyqt6-webengine)", file=sys.stderr)
        print("Sinon, utilise la version navigateur : ./launch.sh", file=sys.stderr)
        return 1

    config_path = _ensure_config()
    port = _free_port()
    ready = threading.Event()

    server_thread = threading.Thread(target=_serve, args=(port, config_path, ready), daemon=True)
    server_thread.start()

    if not ready.wait(timeout=30):
        log.error("le serveur n'a pas démarré à temps")
        return 1

    webview.create_window("graph-watch", f"http://127.0.0.1:{port}/", width=1000, height=800, min_size=(700, 500))
    webview.start()
    # la fenêtre fermée = le process se termine = le thread daemon du serveur meurt avec lui
    return 0


if __name__ == "__main__":
    sys.exit(main())
