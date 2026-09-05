# graph-watch — plan produit

Document vivant. Édité au fil de l'eau, pas figé — c'est la mémoire du projet,
pas une promesse marketing.

## En une phrase

Un moteur autonome, local, qui transforme un flux de documents (texte, posts,
fils sociaux) en graphe de relations sourcé et audité — sans jamais présenter
une corrélation comme une preuve.

## Ce qui existe aujourd'hui

| Bloc | État | Où |
|---|---|---|
| Ingestion (RSS, dossier corpus, fil de posts) | ✅ testé | `graphwatch/sources/`, `graphwatch/propagation/ingest.py` |
| Extraction (spaCy local / LLM) | ✅ testé | `graphwatch/extract/` |
| Résolution d'entités (cascade sûre, anti-fusion) | ✅ testé, 7 tests dédiés | `graphwatch/graph/builder.py` |
| Analyse (centralité, communautés, robustesse) | ✅ testé | `graphwatch/graph/analysis.py` |
| Admiralty Code (fiabilité source, crédibilité suggérée) | ✅ testé | `graphwatch/graph/analysis.py` |
| Analyse de propagation (graine, bursts, propagateurs) | ✅ testé | `graphwatch/propagation/` |
| Graphe interactif HTML | ✅ testé, capture vérifiée | `graphwatch/report/html_graph.py` |
| Vue propagation HTML | ✅ testé, capture vérifiée | `graphwatch/report/propagation_view.py` |
| Fiche individuelle (personne/groupe) | ✅ testé, capture vérifiée | `graphwatch/report/entity_view.py` |
| Exports JSON / Markdown / GraphML | ✅ testé | `graphwatch/report/graph_export.py`, `markdown_report.py` |
| File de validation (propose → approve) | ✅ testé | `graphwatch/queue.py` |
| Interface glisser-déposer + URL | ✅ testé | `graphwatch/webserver/` |
| Scheduler persistant, ajout de sources à chaud | ✅ testé | `graphwatch/scheduler.py` |

Rien de tout ça n'est câblé à un sujet précis — architecture générique,
vérifié en construisant sur trois domaines différents (documents fictifs
d'entreprise, fils de propagation, condamnations d'élus fictifs).

## Principes non négociables

Ce ne sont pas des détails d'implémentation, ce sont les règles qui font que
l'outil reste défendable :

1. **Aucune ingestion à l'aveugle.** `topic` ne scrape rien sans fetcher
   branché explicitement. `webui` ne récupère que l'URL que *toi* tu donnes.
2. **La fiabilité d'une source est un jugement humain**, jamais déduit — la
   valeur par défaut est toujours "inconnue" (F), pas "fiable".
3. **La crédibilité calculée (1–6) est une suggestion, jamais un verdict** —
   affichée partout avec ce rappel, dans le HTML, le Markdown, le JSON.
4. **La résolution d'entités refuse de deviner en cas d'ambiguïté** — mieux
   vaut deux nœuds séparés à tort qu'une fusion erronée entre deux personnes.
5. **Toute relation reste tracée jusqu'à sa source exacte** (fichier, extrait).

## Leviers déjà réglables (les "ajustements sur les biais")

| Levier | Où le régler | Effet |
|---|---|---|
| Fiabilité d'une source (A–F) | `config.yaml`, champ `reliability` par source | Change la crédibilité calculée de tout ce qui vient de cette source |
| Seuil de corroboration | `global.min_corroborating_sources` | Nombre de documents indépendants avant qu'une entité sorte de "faible confiance" |
| Backend d'extraction | `extractor: spacy \| llm` par source | Précision des relations (spaCy = co-occurrence brute, LLM = relations typées + confiance) |
| Modèle spaCy | `global.spacy.model` | Petit modèle = rapide mais imprécis sur les noms composés (vu en pratique sur ce projet) |
| Seuil de similarité floue (résolution d'entités) | `graphwatch/graph/builder.py::_FUZZY_CUTOFF` (0.90) | Plus bas = fusionne plus de variantes, mais risque plus de faux positifs |
| Poids de la formule de crédibilité | `graphwatch/graph/analysis.py::_credibility_score` | Comment fiabilité + nombre de sources se combinent en note 1–6 |
| Nombre de fiches auto-générées | `graphwatch/pipeline.py::AUTO_ENTITY_PROFILES` (5) | Combien d'entités récupèrent une fiche à chaque cycle sans le demander |
| Fenêtre / seuil de burst | `graphwatch/propagation/bursts.py` (60 min, ×2 médiane) | Sensibilité de la détection de pics d'activité |

Rien de tout ça n'a d'interface de réglage dédiée aujourd'hui — c'est du
`config.yaml` ou du code. Une vraie UI de réglage est dans la feuille de
route (voir plus bas) si le besoin se confirme.

## Feuille de route

**Court terme (le plus rentable)**
- Panneau de réglage dans `webui` pour les leviers ci-dessus (au lieu d'éditer
  `config.yaml`/le code à la main).
- Diff entre cycles : "qu'est-ce qui a changé depuis le dernier passage"
  plutôt que relire tout le graphe.
- ~~Page d'accueil unique qui relie graphe / propagation / fiches~~ — fait :
  `notebooks/index.html`, régénérée à chaque cycle (`graphwatch/report/index_view.py`).

**Moyen terme**
- Alertes (mail/webhook) quand un nouveau nœud saute en centralité ou qu'une
  fiche change de statut de confiance.
- Résolution d'entités : alias manuels persistés (aujourd'hui la cascade est
  automatique seulement).
- Export GraphML/JSON pour une fiche individuelle (aujourd'hui : graphe entier
  ou fiche HTML, pas de JSON par personne).

**Non prévu (choix assumé, pas un oubli)**
- Réécriture Neo4j/Node/React — le stack Python actuel (networkx + FastAPI)
  suffit à l'échelle visée ; changer de stack sans besoin concret serait du
  travail perdu.
- Module "narrative layers" façon Pizzagate (couches thématiques type
  "pédophilie/satanisme" avec scoring de centralité d'acteur) — refusé plus
  tôt dans ce projet, la position ne change pas : ce type de structure fait
  le travail de désignation même avec un badge "réfuté" à côté.
- Multi-utilisateur / auth / SaaS — outil local mono-utilisateur par design.
- Scraping automatique de réseaux sociaux — `post_thread` attend des fichiers
  que tu fournis, jamais une collecte automatique.

## Comment faire évoluer ce document

Ce fichier vit dans le repo (`PRODUCT_PLAN.md`). Quand une feature de la
feuille de route est construite, elle bascule dans le tableau "ce qui existe
aujourd'hui" avec son état de test réel — pas de case cochée sans preuve.
