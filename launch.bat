@echo off
REM Lanceur unique : double-clic -- installe si besoin, demarre le serveur,
REM ouvre le navigateur tout seul. Rien d'autre a taper.
cd /d "%~dp0"

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

echo Demarrage de graph-watch...
start "" http://127.0.0.1:8765
python run.py webui
