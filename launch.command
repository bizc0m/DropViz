#!/usr/bin/env bash
# Lanceur unique : double-clic (ou `./launch.sh`, ou `./launch.sh 9090` pour
# choisir le port) -- installe si besoin, démarre le serveur, ouvre le
# navigateur tout seul. Rien d'autre à taper.
set -e
cd "$(dirname "$0")"

PORT="${1:-8765}"

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

echo "Démarrage de graph-watch sur le port $PORT..."
python run.py webui --port "$PORT" &
SERVER_PID=$!

# attend que le port réponde vraiment avant d'ouvrir le navigateur -- le
# chargement des dépendances (spaCy, networkx...) prend quelques secondes,
# un sleep fixe arrivait parfois trop tôt et ouvrait une page vide.
URL="http://127.0.0.1:$PORT"
for i in $(seq 1 30); do
  if (exec 3<>/dev/tcp/127.0.0.1/"$PORT") 2>/dev/null; then
    exec 3<&- 3>&-
    break
  fi
  sleep 0.5
done

if command -v xdg-open &> /dev/null; then
  xdg-open "$URL" &> /dev/null &
elif command -v open &> /dev/null; then
  open "$URL"
else
  echo "Ouvre manuellement dans ton navigateur : $URL"
fi

echo "graph-watch tourne sur $URL (PID $SERVER_PID). Ferme cette fenêtre ou Ctrl+C pour arrêter."
wait $SERVER_PID
