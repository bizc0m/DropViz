"""Génère un notebook .ipynb à partir d'un graphe + de son analyse.

Principe : le notebook est auto-suffisant et reproductible — ses cellules
de code rechargent le snapshot du graphe et RECALCULENT l'analyse plutôt
que d'incruster des chiffres figés. Les cellules markdown, elles,
embarquent les chiffres calculés au moment de la génération pour donner
une lecture immédiate sans avoir à exécuter le notebook.
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

from graphwatch.graph.analysis import AnalysisResult
import networkx as nx

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _label(graph: nx.Graph, node_id: str) -> str:
    return graph.nodes[node_id].get("label", node_id) if node_id in graph.nodes else node_id


def _top_n(scores: dict[str, float], graph: nx.Graph, n: int = 10) -> list[tuple[str, float]]:
    ranked = sorted(scores.items(), key=lambda kv: (kv[1] if kv[1] == kv[1] else -1), reverse=True)  # NaN-safe
    return [(_label(graph, node), score) for node, score in ranked[:n]]


def _markdown_table(rows: list[tuple[str, float]], headers: tuple[str, str]) -> str:
    lines = [f"| {headers[0]} | {headers[1]} |", "|---|---|"]
    for name, score in rows:
        lines.append(f"| {name} | {score:.4f} |")
    return "\n".join(lines)


def generate_notebook(
    *,
    cycle_meta: dict,
    graph_snapshot_path: Path,
    graph: nx.Graph,
    analysis: AnalysisResult,
    output_path: Path,
    min_corroborating_sources: int,
) -> Path:
    nb = nbf.v4.new_notebook()
    cells = []

    # --- 1. Contexte + avertissement méthodologique --------------------
    cells.append(nbf.v4.new_markdown_cell(f"""# Rapport d'analyse de graphe — {cycle_meta.get('source_name', 'toutes sources')}

Généré automatiquement le **{cycle_meta.get('generated_at')}**.
Cycle basé sur {cycle_meta.get('n_new_docs', 0)} nouveau(x) document(s) ingéré(s)
depuis le dernier passage (total cumulé dans le graphe : {analysis.n_nodes} entités,
{analysis.n_edges} relations).

> **Lecture obligatoire avant les résultats** : les métriques ci-dessous décrivent la
> *structure* du graphe (qui est central, qui est regroupé avec qui) telle qu'observée
> dans le corpus ingéré. Elles ne constituent PAS une preuve de fait sur les entités
> concernées. Une position centrale peut aussi bien refléter une couverture médiatique
> abondante, un biais de collecte, ou une simple homonymie mal résolue. Voir la section
> *Signaux de confiance* en fin de notebook avant toute conclusion.
"""))

    # --- 2. Rechargement reproductible ----------------------------------
    cells.append(nbf.v4.new_markdown_cell("## 1. Rechargement du graphe (reproductible)"))
    cells.append(nbf.v4.new_code_cell(f"""import sys, pickle
import networkx as nx

sys.path.insert(0, r"{_PROJECT_ROOT}")  # rend `graphwatch` importable quel que soit le cwd
from graphwatch.graph.analysis import run_full_analysis

with open(r"{Path(graph_snapshot_path).resolve()}", "rb") as f:
    graph = pickle.load(f)

analysis = run_full_analysis(graph, min_corroborating_sources={min_corroborating_sources})
print(f"{{analysis.n_nodes}} entités, {{analysis.n_edges}} relations, "
      f"densité={{analysis.density:.4f}}, modularité={{analysis.modularity:.4f}}")
"""))

    # --- 3. Statistiques descriptives -----------------------------------
    cells.append(nbf.v4.new_markdown_cell(f"""## 2. Statistiques descriptives

- Entités (nœuds) : **{analysis.n_nodes}**
- Relations (arêtes) : **{analysis.n_edges}**
- Densité : **{analysis.density:.4f}**
- Composantes connexes : **{analysis.n_connected_components}** (la plus grande : {analysis.largest_component_size} nœuds)
"""))

    # --- 4. Centralité ----------------------------------------------------
    top_pagerank = _top_n(analysis.centrality["pagerank"], graph)
    top_betweenness = _top_n(analysis.centrality["betweenness"], graph)
    cells.append(nbf.v4.new_markdown_cell(f"""## 3. Centralité

**Top 10 par PageRank** (importance pondérée par les connexions des voisins) :

{_markdown_table(top_pagerank, ("Entité", "PageRank"))}

**Top 10 par betweenness** (position de "pont" entre groupes) :

{_markdown_table(top_betweenness, ("Entité", "Betweenness"))}
"""))
    cells.append(nbf.v4.new_code_cell("""import pandas as pd

df_centrality = pd.DataFrame({
    "label": [graph.nodes[n].get("label", n) for n in graph.nodes],
    "degree": [analysis.centrality["degree"].get(n, 0) for n in graph.nodes],
    "betweenness": [analysis.centrality["betweenness"].get(n, 0) for n in graph.nodes],
    "pagerank": [analysis.centrality["pagerank"].get(n, 0) for n in graph.nodes],
    "n_sources": [len(graph.nodes[n].get("origins", [])) for n in graph.nodes],
    "credibility_1to6": [analysis.credibility_nodes.get(n, 6) for n in graph.nodes],
}).sort_values("pagerank", ascending=False)

df_centrality.head(20)
"""))

    # --- 5. Communautés -----------------------------------------------------
    cells.append(nbf.v4.new_markdown_cell(f"""## 4. Communautés

Détection par modularité (Louvain si disponible). Score de modularité : **{analysis.modularity:.4f}**
(au-delà de ~0.3, la structure en communautés est généralement considérée significative).

**Stabilité (robustesse)** : {"non calculée (graphe trop petit)" if analysis.community_stability is None
else f"**{analysis.community_stability:.2%}** d'accord moyen entre 5 ré-échantillonnages à 80% des arêtes. Un score bas (<70%) signifie que le découpage en communautés est sensible au bruit et ne doit pas être sur-interprété."}
"""))
    cells.append(nbf.v4.new_code_cell("""import matplotlib.pyplot as plt

pos = nx.spring_layout(graph, seed=42, weight="weight")
community_ids = [analysis.communities.get(n, -1) for n in graph.nodes]

fig, ax = plt.subplots(figsize=(10, 8))
nx.draw_networkx_edges(graph, pos, alpha=0.2, ax=ax)
nx.draw_networkx_nodes(graph, pos, node_color=community_ids, cmap="tab20", node_size=80, ax=ax)
labels = {n: graph.nodes[n].get("label", n) for n in graph.nodes if graph.degree(n) >= df_centrality["degree"].quantile(0.8)}
nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8, ax=ax)
ax.set_title("Communautés détectées (nœuds étiquetés = degré dans le top 20%)")
ax.axis("off")
plt.tight_layout()
plt.show()
"""))

    # --- 6. Signaux de confiance / limites --------------------------------
    low_nodes_labels = sorted({_label(graph, n) for n in analysis.low_confidence_nodes})[:30]
    hub_labels = sorted({_label(graph, n) for n in analysis.single_source_hubs})[:30]
    cred_values = list(analysis.credibility_nodes.values())
    n_confirmed = sum(1 for c in cred_values if c <= 2)
    n_doubtful = sum(1 for c in cred_values if c in (3, 4))
    n_unjudged = sum(1 for c in cred_values if c >= 5)
    cells.append(nbf.v4.new_markdown_cell(f"""## 5. Signaux de confiance — À LIRE avant toute conclusion

- **{len(analysis.low_confidence_nodes)} entité(s)** corroborée(s) par moins de
  {min_corroborating_sources} source(s) distincte(s) — à vérifier avant d'être citées :
  {", ".join(low_nodes_labels) if low_nodes_labels else "_aucune_"}
- **{len(analysis.single_source_hubs)} entité(s) à degré élevé mais alimentées par une seule source** —
  la centralité observée peut refléter la répétition d'une seule source plutôt qu'une
  corroboration réelle : {", ".join(hub_labels) if hub_labels else "_aucune_"}

**Admiralty Code** (fiabilité source A–F configurée par toi, crédibilité info 1–6
*calculée* à partir de la fiabilité + du nombre de documents indépendants — colonne
`credibility_1to6` du tableau de centralité ci-dessus) :
- {n_confirmed} entité(s) en zone "confirmé/probable" (1–2)
- {n_doubtful} entité(s) en zone "douteux" (3–4)
- {n_unjudged} entité(s) "ne peut être jugée" (5–6) — typiquement les sources non notées (F par défaut)

La crédibilité 1–6 est une **heuristique de ce projet**, pas une échelle validée en
elle-même (contrairement à l'Admiralty Code source A–F, qui est un standard réel) —
à traiter comme une suggestion à vérifier, jamais comme un verdict.

**Rappel** : ce rapport documente une structure de graphe dérivée d'un corpus donné, avec
son niveau d'incertitude. Toute conclusion nommant des personnes ou organisations
identifiables doit être recoupée avec des sources primaires fiables avant publication.
"""))

    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
        "language_info": {"name": "python"},
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        nbf.write(nb, f)
    return output_path
