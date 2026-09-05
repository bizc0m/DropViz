"""Aide pour launch.bat : lit le fichier de log du serveur et affiche le port
réellement utilisé (celui annoncé dans 'graph-watch webui -> http://...').
Séparé dans un fichier .py plutôt qu'encodé en one-liner dans le .bat --
beaucoup plus simple à relire et à corriger si besoin."""
from __future__ import annotations

import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    sys.exit(1)

log_path = Path(sys.argv[1])
if not log_path.exists():
    sys.exit(1)

match = re.search(r"http://[^:\s]+:(\d+)", log_path.read_text(encoding="utf-8", errors="ignore"))
if match:
    print(match.group(1))
    sys.exit(0)
sys.exit(1)
