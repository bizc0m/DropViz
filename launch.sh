#!/usr/bin/env bash
# Lanceur unique : double-clic (ou `./launch.sh`, ou `./launch.sh 9090` pour
# proposer un port) -- installe si besoin, démarre le serveur, ouvre le
# navigateur tout seul sur le port RÉELLEMENT utilisé (si celui demandé est
# déjà pris par autre chose, run.py bascule automatiquement sur un libre --
# ce script lit cette décision au lieu de la deviner).
set -e
cd "$(dirname "$0")"

REQUESTED_PORT="${1:-8765}"

if [ ! -d ".venv" ]; then
  echo "Premier lancement : installation (une minute ou deux)..."
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -r requirements.txt
  python -m spacy download fr_core_news_sm
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ ! -f "config.yaml" ]; then
  cp config.example.yaml config.yaml
  echo "config.yaml créé à partir de l'exemple -- édite-le pour tes sources avant de continuer."
fi

echo "Démarrage de graph-watch (port souhaité : $REQUESTED_PORT)..."
LOG_FILE="$(mktemp)"
python -u run.py webui --port "$REQUESTED_PORT" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# lit le port RÉEL depuis la sortie du serveur (peut différer de celui
# demandé si celui-ci était déjà occupé) -- au lieu de l'espérer.
PORT=""
for i in $(seq 1 60); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Le serveur s'est arrêté avant de démarrer. Détail :"
    cat "$LOG_FILE"
    rm -f "$LOG_FILE"
    exit 1
  fi
  LINE="$(grep -o 'http://[^ ]*' "$LOG_FILE" 2>/dev/null | head -1)"
  if [ -n "$LINE" ]; then
    PORT="${LINE##*:}"
    break
  fi
  sleep 0.5
done
rm -f "$LOG_FILE"

if [ -z "$PORT" ]; then
  echo "Le serveur n'a pas répondu à temps -- relance avec 'python run.py -v webui --port $REQUESTED_PORT' pour voir le détail."
  exit 1
fi

URL="http://127.0.0.1:$PORT"
if [ "$PORT" != "$REQUESTED_PORT" ]; then
  echo "Port $REQUESTED_PORT indisponible -- graph-watch tourne sur $PORT à la place."
fi

if command -v xdg-open &> /dev/null; then
  xdg-open "$URL" &> /dev/null &
elif command -v open &> /dev/null; then
  open "$URL"
else
  echo "Ouvre manuellement dans ton navigateur : $URL"
fi

echo "graph-watch tourne sur $URL (PID $SERVER_PID). Ferme cette fenêtre ou Ctrl+C pour arrêter."
wait $SERVER_PID
