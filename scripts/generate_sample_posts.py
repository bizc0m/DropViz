#!/usr/bin/env python3
"""Génère un jeu de posts fictif (fil de propagation) pour tester/démontrer
le module graphwatch.propagation. Contenu entièrement inventé, sujet neutre."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(7)

OUT = Path(__file__).resolve().parent.parent / "posts_sample" / "rumor-parc-central.jsonl"
RUMOR = "fermeture-parc-central"
T0 = datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc)

accounts_amplifiers = ["@usager_quartier", "@voisin_curieux", "@alerte_locale", "@infos_rapides", "@quartier_nord"]
accounts_skeptics = ["@fact_checkeur", "@mairie_watch", "@verif_locale"]

posts = []


def add(id_, account, t, parent=None, type_="original", content="", likes=0, retweets=0, replies=0):
    posts.append({
        "id": id_, "rumor": RUMOR, "account": account,
        "posted_at": t.isoformat(),
        "parent_id": parent, "type": type_, "content": content,
        "metrics": {"likes": likes, "retweets": retweets, "replies": replies},
    })


# graine
add("p0", "@alice_riveraine", T0, content="On me dit que le parc central fermerait dès demain, sans annonce officielle ?!",
    likes=4, retweets=2, replies=1)

# première vague de retweets (lente, ~1/10min)
t = T0
for i in range(6):
    t = t + timedelta(minutes=random.randint(8, 15))
    acc = random.choice(accounts_amplifiers)
    add(f"p_rt_{i}", acc, t, parent="p0", type_="retweet", likes=random.randint(0, 5))

# burst : un compte "infos_rapides" relaie fort -> pic d'activité vers t+2h
burst_start = T0 + timedelta(hours=2)
add("p_trigger", "@infos_rapides", burst_start, parent="p0", type_="quote",
    content="🚨 Le parc central fermerait dès demain selon plusieurs riverains.", likes=40, retweets=25)

t = burst_start
for i in range(22):
    t = t + timedelta(minutes=random.randint(1, 5))
    acc = random.choice(accounts_amplifiers + ["@passant_" + str(i)])
    parent = "p_trigger" if random.random() < 0.7 else random.choice([p["id"] for p in posts if p["type"] in ("retweet", "quote")])
    add(f"p_burst_{i}", acc, t, parent=parent, type_="retweet", likes=random.randint(0, 8))

# réponses sceptiques, réparties après le burst
t = burst_start + timedelta(minutes=40)
for i, acc in enumerate(accounts_skeptics):
    t = t + timedelta(minutes=random.randint(10, 30))
    add(f"p_skeptic_{i}", acc, t, parent="p_trigger", type_="reply",
        content="Aucune décision officielle trouvée sur le site de la mairie à ce stade, à vérifier.",
        likes=random.randint(3, 12), replies=1)

# démenti officiel qui referme la boucle
t_reply = t + timedelta(minutes=45)
add("p_official", "@mairie_officielle", t_reply, parent="p_trigger", type_="reply",
    content="Aucune fermeture prévue. Le parc reste ouvert selon les horaires habituels.",
    likes=61, retweets=30, replies=4)

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as f:
    for p in posts:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

print(f"{len(posts)} posts écrits dans {OUT}")
