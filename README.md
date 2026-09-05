# graph-watch

Outil autonome : tu lui donnes un corpus (fichiers déposés dans un dossier),
des flux RSS, et/ou des sujets à suivre — il ingère à intervalle régulier
(configurable par source), construit/maintient un graphe de relations, et
génère automatiquement un notebook Jupyter d'analyse à chaque cycle.

Conçu pour de l'analyse sérieuse : chaque relation garde sa source et sa
citation exacte, les nœuds/arêtes peu corroborés sont signalés, et le
notebook généré rappelle explicitement que la structure d'un graphe n'est
pas une preuve — voir `graphwatch/graph/analysis.py` et
`graphwatch/report/notebook_generator.py`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# modèle NER local (backend "spacy", par défaut)
python -m spacy download fr_core_news_md
# ou pour de l'anglais : python -m spacy download en_core_web_sm
```

Pour le backend LLM (extraction plus fine, sur les sources où tu le configures) :

```bash
export ANTHROPIC_API_KEY="sk-..."
```

## Configuration

```bash
cp config.example.yaml config.yaml
```

Édite `config.yaml` : une entrée par source (`rss`, `corpus_folder`, ou `topic`),
chacune avec son propre `interval_minutes` et son propre `extractor` (`spacy` ou `llm`).

- **`corpus_folder`** : dépose des fichiers `.txt/.md/.html/.pdf/.json/.jsonl/.csv` dans le
  dossier indiqué, à n'importe quel moment. Au cycle suivant, seuls les fichiers
  jamais vus (dédup par hash de contenu) sont traités. C'est le "je balance le
  corpus et ça tourne tout seul".
- **`rss`** : rescanne un flux à chaque cycle, ingère les nouvelles entrées.
- **`topic`** : suit un mot-clé/thème. Ne scrape rien par défaut — tu branches
  ton propre connecteur de recherche autorisé (`graphwatch/sources/topic_search.py`,
  `register_topic_fetcher`) pour éviter d'aller chercher des pages non vérifiées
  à ton insu.

## Lancer

```bash
# un seul cycle, pour tester (toutes les sources, ou --source NAME)
python run.py -v once
python run.py once --source corpus-local-exemple --force   # régénère même sans nouveau doc

# scheduler persistant : tourne en continu, chaque source à son propre rythme
python run.py serve
```

## App desktop (fenêtre native, aucun port à gérer)

```bash
pip install -r requirements-desktop.txt   # une fois -- voir ce fichier pour Linux
python desktop_app.py
```

Une seule fenêtre s'ouvre, comme une vraie app. Le port est choisi
automatiquement par l'OS (libre à chaque lancement) -- plus de "quel port",
plus d'onglet de navigateur à retrouver, plus de terminal à surveiller.
Fermer la fenêtre arrête tout. C'est la même interface que la version
navigateur ci-dessous, juste sans navigateur.

## Interface glisser-déposer + URL (navigateur)

```bash
python run.py webui               # http://127.0.0.1:8765
./launch.sh                       # ou launch.command (Mac) / launch.bat (Windows), double-clic
./launch.sh 9090                  # pour choisir le port toi-même
```

Si le port demandé (8765 par défaut) est déjà pris par autre chose sur ta
machine, `run.py webui` bascule **automatiquement** sur le premier port libre
juste après et l'affiche clairement (`launch.sh`/`.command`/`.bat` lisent
cette info et ouvrent le bon onglet tout seuls, pas besoin de le chercher toi-même).

Une page locale pour ajouter du contenu à la main à une source `corpus_folder` :
glisse des fichiers, ou colle une URL — ça écrit dans le dossier de la source
et relance immédiatement un cycle, avec des liens directs vers le notebook et
le graphe générés. **La récupération d'URL utilise ta connexion réseau** (le
process tourne sur ta machine) — contrairement à un environnement d'agent
sandboxé, il n'y a pas de restriction ici. Aucune source `corpus_folder`
configurée → la page l'indique, ajoutes-en une dans `config.yaml`. Un lien
« voir tous les rapports générés » renvoie vers `notebooks/index.html`
(voir plus bas).

## Ajouter une adresse : proposer → valider → suivi automatique

Pas d'ingestion à l'aveugle. Une nouvelle adresse (flux RSS, dossier, sujet)
passe par une file d'attente : tu la proposes, le système va chercher un
aperçu (sans rien stocker), tu valides, et **seulement alors** elle devient
une source active et suivie automatiquement — sans redémarrer le process si
`serve` tourne déjà (vérifié toutes les 5 min).

```bash
python run.py propose --type rss --name veille-x \
    --url https://exemple.org/feed.xml --interval 360 --reliability C

# -> affiche un aperçu (titres des dernières entrées) avant toute décision
python run.py list-pending
python run.py approve veille-x     # ou: reject veille-x
```

`--reliability` (Admiralty Code A–F) est un jugement humain sur la source
elle-même, à trancher à la proposition — jamais déduit automatiquement.
Idem pour `--type corpus_folder --path ...` et `--type topic --query ...`.

Chaque cycle produit cinq fichiers dans `notebooks/`, horodatés :

- **`<source>__<ts>.ipynb`** : le rapport d'analyse (tableaux, stats, robustesse).
- **`<source>__<ts>.html`** : le **graphe interactif** (canvas + physique maison,
  zéro dépendance externe) — zoom/drag/panoramique, recherche, panneau de détail
  au clic (PageRank, betweenness, sources, extraits), taille des nœuds =
  importance, couleur = communauté, trait pointillé = relation peu corroborée.
  Affiche aussi les badges **Admiralty Code** : `fiab.` (A–F, fiabilité de la
  source, configurée à la main) et `créd.` (1–6, crédibilité suggérée — calculée
  depuis la fiabilité + le nombre de documents indépendants, à vérifier, jamais
  un verdict). Fichier autonome, s'ouvre directement dans un navigateur.
- **`<source>__<ts>.json`** : le graphe brut (`meta`/`nodes`/`edges`, le même
  payload qu'affiche la page interactive) — pour piper dans ton propre script,
  un autre outil, ou le contexte d'un LLM. `meta.setup` rend le fichier
  auto-descriptif : source (nom, type, fiabilité, options), config globale
  (extracteur/modèle utilisé, seuil de corroboration, mode du graphe) — pas
  besoin de retrouver `config.yaml` pour savoir comment ce cycle a tourné.
- **`<source>__<ts>.md`** : rapport texte autonome (stats, top entités, signaux
  de confiance, relations) — pas de cellule de code, à coller dans un wiki/ticket.
- **`<source>__<ts>.graphml`** : pour ouvrir le graphe dans [Gephi](https://gephi.org/)
  (gratuit, à installer toi-même — pas embarqué ni appelé par graph-watch) ou
  tout autre outil compatible GraphML. Contient les métriques déjà calculées
  (`pagerank`, `betweenness`, `community`, `credibility`, `reliability`) en
  attributs directs — dans Gephi : *Apparence* → taille par `pagerank`,
  couleur par `community` (partition), filtre par `credibility`.
- **`<source>__<ts>__entity-<nom>.html`** : une **fiche autonome par entité**
  (les 5 plus centrales par PageRank, générées automatiquement chaque cycle) —
  réseau direct (ego-network), relations détaillées avec extraits et sources,
  badges Admiralty. Exportable/partageable seule, indépendamment du graphe complet.

- **`index.html`** : la **page d'accueil unique** de `notebooks/` — un seul lien
  à garder/partager. Régénérée automatiquement à chaque cycle (toute source
  confondue, graphes et propagation compris) en scannant simplement ce qu'il
  y a réellement dans le dossier : jamais de lien mort vers un fichier
  supprimé, jamais un rapport généré mais introuvable. Trois sections —
  Graphes (le plus récent par source), Propagation, Fiches — chacune avec la
  date de génération. Régénérable à la demande avec `python run.py index`.

Pour n'importe quelle autre entité (pas dans le top 5 auto), à la demande :

```bash
python run.py entity "Nom de la personne ou du groupe" [--source NAME]
```

Recherche par nom exact ou sous-chaîne unique — si plusieurs entités matchent,
ça refuse de deviner et te demande de préciser.

Le graphe "live" (cumulé) et ses snapshots horodatés sont dans `data/graphs/`.
La base SQLite de provenance (quel document, quelle source, quand) est dans
`data/documents.db`.

## Analyse de propagation (source `post_thread`)

Pour un fil de posts déjà structuré (retweets/quotes/réponses avec horodatage
et lien parent explicite) plutôt qu'un corpus de texte libre : détecte la
graine probable de la rumeur, construit l'arbre de propagation, détecte les
pics d'activité (bursts) et calcule les principaux propagateurs.

Aucune collecte automatique de réseau social : tu déposes les fichiers
`.json`/`.jsonl` toi-même (export d'API légitime, corpus déjà autorisé), au
format documenté dans `graphwatch/propagation/models.py`. Génère un jeu
d'exemple fictif pour essayer :

```bash
python scripts/generate_sample_posts.py
python run.py once --source propagation-exemple
```

Produit `<source>__<rumeur>__<ts>_propagation.html` dans `notebooks/` :
frise des bursts (clique une bande pour isoler la période dans l'arbre),
arbre horizontal (couleur = type de post, taille = engagement, anneau blanc
= graine retenue), panneau avec les candidats graine et le classement des
propagateurs (volume, engagement, betweenness).

## Étendre

- **Nouvelle source** : hériter de `graphwatch.sources.base.Source`, l'enregistrer
  dans `graphwatch/sources/__init__.py`.
- **Meilleure résolution d'entités** (alias, quasi-doublons) : tout passe par
  `graphwatch.graph.builder.resolve()` — un seul point à modifier.
- **Autre backend d'extraction** : hériter de `graphwatch.extract.base.Extractor`.

## Tests

```bash
pytest tests/ -v
```
