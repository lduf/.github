# Passation : skyjo-ai (état, décisions, résultats, suite)

Code : dossier `skyjo-ai/`, branche `claude/optimistic-ramanujan-qr5ur0`, PR brouillon #18 de `lduf/.github`
(dépôt choisi par erreur : le code est autonome et peut être déplacé tel quel). Dépendance : `numpy` seul.
Les modèles entraînés ne sont PAS versionnés (`models/` ignoré, ~60 Ko chacun) : à régénérer (commandes plus bas).

## 1. Règles retenues (sources secondaires, pas de texte officiel Magilano consulté)

Sources : regles-du-jeu.net/regles-du-skyjo, regles2jeux.fr/regle-skyjo, officialgamerules.org/skyjo, livret PDF Magilano (cdn.shopify.com … skyjo-regle-du-jeu.pdf).

- 150 cartes : 5×(−2), 10×(−1), 15×0, 10× chacune de 1..12 (ce décompte vient de ma connaissance, pas confirmé par la recherche).
- 12 cartes/joueur, grille 4 colonnes × 3 lignes, 2 retournées au départ (au hasard dans mon implémentation), une carte de pioche lance la défausse.
- Tour : prendre la défausse (échange obligatoire) OU piocher puis échanger, OU défausser et retourner une carte cachée.
- Colonne de 3 cartes visibles identiques : retirée (0 point).
- Fin de manche : un joueur sans carte cachée → dernier tour pour les autres → révélation et comptage.
- Finisseur : score doublé s'il est positif et pas strictement le plus bas. Fin de partie à ≥ 100, plus bas total gagne.
- Premier joueur : plus grosse somme visible (manche 1), ensuite le finisseur précédent.
- **Trois points non confirmés** (sources divergentes/ambiguës), réglables dans `Rules` : (a) score négatif jamais doublé ;
  (b) égalité avec le meilleur = doublé (`double_on_tie`) ; (c) retrait des colonnes aussi à la révélation finale (`clear_on_final_reveal`).

## 2. Architecture

| Fichier | Rôle |
|---|---|
| `skyjo/game.py` | `Round`, `play_game`, `Rules`, `View` (observation à information imparfaite) |
| `skyjo/agents.py` | `RandomAgent`, `GreedyAgent` (heuristique de référence), `NNAgent`, `featurize` (66 features) |
| `skyjo/nn.py` | MLP numpy 66→64→32→(26 logits politique + 1 valeur), rétropropagation manuelle, Adam, save/load `.npz` |
| `skyjo/rl.py` | clonage de comportement (`pretrain_imitation`), acteur-critique REINFORCE+baseline, self-play |
| `skyjo/ga.py` | neuroévolution (élitisme 4, tournoi k=3, croisement uniforme, mutation gaussienne) |
| `skyjo/evaluate.py` | tournois en parties complètes, sièges tirés au sort, multiprocessing |
| `skyjo/cli.py` | `python -m skyjo {demo,evaluate,train-rl,train-ga}` |
| `tests/test_game.py` | 13 tests (paquet, conservation des cartes 2..8 joueurs, colonnes, doublement, gradient numérique…) |

Actions du réseau (26 sorties, masquées) : 0-1 source (pioche/défausse) ; 2-13 placer en case i ; 14-25 défausser et retourner la case i.
Deux décisions par tour (source, puis case) ; la 2e voit la carte en main.
Features notables : valeurs/états des 12 cases, nb de cartes identiques déjà visibles dans la colonne de la carte candidate,
espérance des cartes inconnues (comptage de cartes via la conservation : 150 − visibles − défausse − main),
score projeté vs adversaires, cartes cachées restantes, drapeau « dernier tour ».
**Le réseau ne voit pas les totaux de partie** (pas de notion de course aux 100).

## 3. Récompenses et protocoles

- RL : épisode = une manche à 2–5 joueurs ; tous les sièges apprenants partagent les poids ; 25 % des sièges tenus par `greedy` ;
  récompense terminale `(score moyen adversaires − son score)/10` (doublement inclus), même retour pour toutes les décisions de la manche ;
  avantage normalisé, bonus d'entropie décroissant (0.022→0.002), `vcoef=0.5`, clip de gradient 5.
- GA : fitness = écart de score par manche sur tables de 2–4 joueurs (siège tournant), adversaires = 50 % greedy / 50 % top-5 de la génération précédente, mêmes graines pour toute la génération.
- Garde-fou : une manche s'arrête à `40 × n_joueurs` tours (flag `timed_out`). Nécessaire : des réseaux déterministes aléatoires bouclent indéfiniment
  (le GA a planté une première fois sur « Manche trop longue » avant ce correctif ; avec un plafond à 300 tours il était aussi très lent).
- Astuce perf : `OPENBLAS_NUM_THREADS=1` quand on lance plusieurs processus.

## 4. Chronologie et résultats (une seule graine par méthode, tout en CPU Linux 4 cœurs)

1. Bots de référence (200 parties) : à 3 joueurs greedy gagne 100 % contre 2 `random` (score moyen 14,8 vs ~125) ; à 4 joueurs 3 greedy + 1 random, le random est à ~143.
2. **RL depuis zéro** (600 itérations × 48 manches) : échec net. Entropie quasi figée (~1,6), marge ≈ −13 à −17 points/manche, 0 victoire contre 2 greedy à chaque évaluation (score moyen ~126–130 vs ~32–37). Récompense terminale trop éparse. Arrêté vers l'itération ~200.
3. **GA depuis zéro** (pop 40, 40 générations, sigma 0.15→0.046) : fitness best passe de −42 à environ −20 dès la génération ~15 puis stagne (−13 à −27, très bruitée). Éval finale 3 joueurs vs 2 greedy : 0 victoire, score 124,5 vs 39,5. Échec.
4. **Imitation de greedy** (600 manches, 30 époques) : précision 96 %, perte 1,22→0,13 ; juste après, parité avec greedy (27 % de victoires à 3 joueurs).
5. **RL après imitation** (400 itérations × 48, lr 5e-4, ~7 min) : évals à 100 parties, bruitées (29–45 % de victoires, écart de score −3 à −15 en faveur du réseau). Modèle final, **400 parties par ligne vs greedy** :
   - 2 joueurs : 64 % de victoires (hasard 50 %), score 85,4 vs 104,6
   - 3 joueurs : 46 % (hasard 33 %), 75,8 vs 90,7–93,4
   - 4 joueurs : 29,5 % (hasard 25 %), 78,1 vs 85,8–87,3
   - 6 joueurs : 19,9 % (hasard 16,7 %), 76,5 vs 80,8–83,1
6. **Hybride** (GA 25 générations, pop 40, amorcé par le modèle RL + 2 voisins perturbés par individu, sigma plancher 0.03) : fitness +1 à +8, mais en duel direct à 3 joueurs (600 parties) RL 41 % / hybride 34 % / greedy 24 % (scores 81,6 / 84,9 / 98,8). Le GA d'affinage n'améliore pas le RL.

Statistique : à 400 parties, l'erreur-type d'un taux de victoire est ≈ 2,5 points ; à 100 parties ≈ 5 points. Les écarts RL/hybride sont modestes et à une seule graine.

## 5. Limites / pièges connus

- Un seul adversaire de référence (`greedy`) ; aucune évaluation contre humains ni contre d'autres heuristiques.
- Pas de totaux de partie dans les observations ; entraînement par manche, évaluation par partie.
- Les cartes de départ sont retournées au hasard (pas de choix).
- `train-rl` n'est pas parallélisé (seuls l'évaluation et le GA utilisent `--workers`).
- Hypothèses non testées sur l'échec du GA seul : budget trop faible et espace de 4 000+ poids ; fitness bruitée ; démarrage aléatoire loin de la politique greedy.
- Le seuil « manche bloquée » peut fausser le fitness d'individus qui bouclent (leur manche est comptée telle quelle).

## 6. Reproduire

```bash
cd skyjo-ai && pip install numpy pytest && python -m pytest tests
export OPENBLAS_NUM_THREADS=1
python -m skyjo train-rl --imitate 600 --iterations 400 --rounds 48 --lr 5e-4 --eval-every 50 --eval-games 100 --out models/rl.npz
python -m skyjo train-ga --init models/rl.npz --sigma 0.02 --generations 25 --pop 40 --workers 4 --out models/hybrid.npz
python -m skyjo evaluate --agents nn:models/rl.npz,greedy,greedy --games 400 --workers 4 --seed 123
```

## 7. Pistes pour l'entraînement plus poussé (Mac M2 Max, 96 Go)

Goulot : la simulation Python de parties (pas le calcul du réseau, minuscule) → le GPU/MPS apporte peu tant que le réseau reste petit.
1. Paralléliser les rollouts du RL sur les cœurs (multiprocessing, un jeu de poids partagé en lecture) et grossir les lots (rounds_per_iter ×10).
2. Ajouter aux observations les totaux de partie et le score des adversaires, entraîner sur parties complètes.
3. Ligue de self-play (anciens checkpoints + greedy + hybrides) plutôt que greedy fixe ; PPO ou shaping de récompense par décision (potentiel = score projeté).
4. Évaluations avec plusieurs graines d'entraînement et intervalles de confiance ; plus de 1 000 parties par ligne.
5. GA : budget bien plus grand, population plus large, fitness moins bruitée (plus de tables), sigma adaptatif ; garder l'amorçage par le modèle RL.
6. Si besoin de vitesse : réécrire `Round` vectorisé (numpy/numba) ou en C/Rust.
7. Réseaux plus grands (PyTorch) seulement après 2–4, sinon le goulot reste la simulation.
