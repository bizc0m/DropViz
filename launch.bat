@echo off
REM Lanceur unique : double-clic (port 8765 par defaut), ou en ligne de
REM commande `launch.bat 9090` pour choisir le port -- installe si besoin,
REM demarre le serveur, ouvre le navigateur tout seul.
cd /d "%~dp0"

set PORT=%1
if "%PORT%"=="" set PORT=8765

if not exist ".venv" (
  echo Premier lancement : installation ^(une minute ou deux^)...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -q -r requirements.txt
  python -m spacy download fr_core_news_sm
) else (
  call .venv\Scripts\activate.bat
)

if not exist "config.yaml" (
  copy config.example.yaml config.yaml
  echo config.yaml cree a partir de l'exemple -- edite-le pour tes sources avant de continuer.
)

echo Demarrage de graph-watch sur le port %PORT%...
start "" http://127.0.0.1:%PORT%
python run.py webui --port %PORT%
