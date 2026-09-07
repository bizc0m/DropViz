"""Logique partagée entre desktop_app.py (fenêtre native, Mac/Windows) et
desktop_app_linux.py (navigateur par défaut) : port automatique, config,
démarrage du serveur. Séparé pour ne pas dupliquer entre les deux points
d'entrée que PyInstaller empaquette séparément par OS."""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
from pathlib import Path

if getattr(sys, "frozen", False):
    # empaqueté par PyInstaller : deux dossiers différents et il ne faut pas
    # les confondre --
    # BUNDLE_DIR (sys._MEIPASS) : où sont les fichiers embarqués en lecture
    #   seule (config.example.yaml, templates...), enfoui dans _internal.
    # USER_DIR : à côté de l'exécutable -- c'est là que config.yaml doit être
    #   ÉCRIT pour que l'utilisateur le trouve et puisse l'éditer, pas dans
    #   _internal où il n'ira jamais voir.
    BUNDLE_DIR = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    USER_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    USER_DIR = BUNDLE_DIR
    sys.path.insert(0, str(BUNDLE_DIR))

REPO_ROOT = USER_DIR  # nom conservé pour compat -- c'est l'endroit "utilisateur"

# un double-clic (Finder/Explorer) ne lance pas forcément le process avec le
# dossier de l'exécutable comme dossier courant -- sans ça, les chemins
# relatifs de config.yaml (./data, ./notebooks, ./corpus_sample...) pointent
# n'importe où selon comment l'app a été lancée.
os.chdir(USER_DIR)

log = logging.getLogger("graph-watch.desktop")


def free_port() -> int:
    """Demande à l'OS un port libre -- on ne choisit jamais nous-mêmes un
    numéro fixe, ça évite complètement la classe de bug 'le port est pris'."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ensure_config() -> Path:
    config_path = USER_DIR / "config.yaml"
    if not config_path.exists():
        example = BUNDLE_DIR / "config.example.yaml"
        config_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        log.info("config.yaml créé à partir de l'exemple (%s)", config_path)
    return config_path


def serve(port: int, config_path: Path, ready: threading.Event) -> None:
    import uvicorn

    from graphwatch.webserver.app import create_app

    app = create_app(config_path)

    class _Server(uvicorn.Server):
        def install_signal_handlers(self) -> None:
            pass  # on tourne dans un thread, pas le thread principal -- uvicorn s'y refuse sinon

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = _Server(config)

    def _signal_ready() -> None:
        # attend que uvicorn ait vraiment bindé le port avant de continuer --
        # sinon on ouvrirait une page blanche en arrivant trop tôt.
        while not server.started:
            threading.Event().wait(0.05)
        ready.set()

    threading.Thread(target=_signal_ready, daemon=True).start()
    server.run()


def start_server_and_wait_ready(timeout: float = 30) -> tuple[int, threading.Thread] | None:
    """Démarre le serveur dans un thread daemon, attend qu'il réponde
    vraiment. Renvoie (port, thread) ou None si le démarrage a échoué."""
    config_path = ensure_config()
    port = free_port()
    ready = threading.Event()

    server_thread = threading.Thread(target=serve, args=(port, config_path, ready), daemon=True)
    server_thread.start()

    if not ready.wait(timeout=timeout):
        log.error("le serveur n'a pas démarré à temps")
        return None
    return port, server_thread
