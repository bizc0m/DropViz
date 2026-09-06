@echo off
REM Lanceur unique : double-clic (port choisi automatiquement par l'OS), ou
REM `launch.bat 9090` pour FORCER un port precis. Si le port force est deja
REM pris par autre chose, run.py bascule tout seul sur un libre -- ce script
REM lit le port REEL dans la sortie du serveur au lieu de deviner
REM (scripts\extract_port.py).
REM
REM NOTE : ce script n'a pas pu etre teste sur une vraie machine Windows
REM (aucune disponible ici pour verifier) -- dis-moi si quelque chose ne
REM marche pas, ce sera corrige vite. launch.sh/.command (Linux/macOS) ont
REM ete testes reellement.
setlocal enabledelayedexpansion
cd /d "%~dp0"

set REQUESTED_PORT=%1

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

set LOG_FILE=%TEMP%\graph-watch-launch.log
del "%LOG_FILE%" >nul 2>&1
if "%REQUESTED_PORT%"=="" (
  echo Demarrage de graph-watch ^(port choisi automatiquement^)...
  start /b "" python -u run.py webui > "%LOG_FILE%" 2>&1
) else (
  echo Demarrage de graph-watch ^(port souhaite : %REQUESTED_PORT%^)...
  start /b "" python -u run.py webui --port %REQUESTED_PORT% > "%LOG_FILE%" 2>&1
)

set PORT=
for /l %%i in (1,1,60) do (
  if not defined PORT (
    for /f %%P in ('python scripts\extract_port.py "%LOG_FILE%" 2^>nul') do set PORT=%%P
    if not defined PORT ping -n 2 127.0.0.1 >nul
  )
)

if not defined PORT (
  echo Le serveur n'a pas repondu a temps. Contenu du log :
  type "%LOG_FILE%"
  goto :eof
)

if not "%REQUESTED_PORT%"=="" if not "%PORT%"=="%REQUESTED_PORT%" (
  echo Port %REQUESTED_PORT% indisponible -- graph-watch tourne sur %PORT% a la place.
)

set URL=http://127.0.0.1:%PORT%
echo graph-watch tourne sur %URL%
start "" %URL%
echo Ferme cette fenetre pour arreter le serveur.
pause >nul
