# skyjo-ai

Moteur de jeu **Skyjo** pour 2 à 8 joueurs (règles classiques) et deux façons d'entraîner une IA :
**apprentissage par renforcement** (acteur-critique, self-play) et **algorithme génétique** (neuroévolution).
Dépendance unique : `numpy`.

## Règles implémentées

Sources : [regles-du-jeu.net](https://www.regles-du-jeu.net/regles-du-skyjo/), [regles2jeux.fr](https://regles2jeux.fr/regle-skyjo/), [officialgamerules.org](https://www.officialgamerules.org/skyjo), [livret Magilano](https://cdn.shopify.com/s/files/1/0354/4137/7413/files/skyjo-regle-du-jeu.pdf).

- 150 cartes : 5×(−2), 10×(−1), 15×0, 10× chacune de 1 à 12.
- 12 cartes par joueur en grille 4 colonnes × 3 lignes, 2 retournées au départ ; une carte de la pioche lance la défausse.
- Un tour : prendre la défausse (échange obligatoire) **ou** piocher puis soit échanger, soit défausser et retourner une carte cachée.
- Colonne de 3 cartes visibles identiques : retirée (comptée 0).
- Fin de manche : un joueur n'a plus de carte cachée → tous les autres jouent un dernier tour, puis on compte.
- Le finisseur a son score **doublé** s'il est positif et qu'il n'a pas strictement le plus petit score.
- Fin de partie : un joueur atteint ≥ 100 ; le total le plus bas gagne.

Points où les sources divergent (réglables dans `Rules`, `skyjo/game.py`) : les scores négatifs ne sont jamais doublés ;
une égalité avec le meilleur score déclenche le doublement ; le retrait des colonnes est aussi appliqué à la révélation finale.
Je n'ai pas pu confirmer ces trois points dans le texte officiel, seulement dans des sources secondaires.

## Utilisation

```bash
pip install numpy pytest
python -m pytest tests                                   # tests du moteur
python -m skyjo demo --agents greedy,greedy,random --verbose   # une partie commentée
python -m skyjo train-rl --imitate 600 --iterations 400 --rounds 48 --lr 5e-4 --out models/rl.npz
python -m skyjo train-ga --generations 40 --out models/ga.npz --workers 4
python -m skyjo train-ga --init models/rl.npz --sigma 0.02 --generations 25 --out models/hybrid.npz   # RL puis GA
python -m skyjo evaluate --agents nn:models/rl.npz,greedy,greedy --games 300 --workers 4
```

Les agents acceptés : `random`, `greedy` (heuristique de référence), `nn:<fichier.npz>`.
Le nombre de joueurs est le nombre d'agents listés (2 à 8) ; les sièges sont tirés au sort à chaque partie.

## Architecture

| Fichier | Rôle |
|---|---|
| `skyjo/game.py` | Moteur : `Round`, `play_game`, `Rules`, `View` (observation à information imparfaite) |
| `skyjo/agents.py` | `RandomAgent`, `GreedyAgent`, `NNAgent`, extraction de features |
| `skyjo/nn.py` | MLP acteur-critique numpy, rétropropagation manuelle, Adam, sauvegarde |
| `skyjo/rl.py` | REINFORCE avec baseline (critique), entropie, self-play multi-joueurs |
| `skyjo/ga.py` | Neuroévolution : élitisme, tournoi, croisement uniforme, mutation gaussienne |
| `skyjo/evaluate.py` | Tournois en parties complètes, parallélisables |

**Réseau** : 66 features (cases connues/retirées/valeurs, cartes qui complèteraient une colonne, carte candidate,
espérance des cartes inconnues par comptage de cartes, score projeté vs adversaires, tours restants…) → 64 → 32 → 26 logits
(source ; placer en case i ; défausser et retourner la case i) + une tête valeur. Les actions illégales sont masquées.

**RL** : le réseau est d'abord échauffé par imitation du bot greedy (`--imitate`, clonage de comportement, ~96 % de précision) ; sans cet échauffement, le RL depuis zéro n'a pas appris en 600 itérations (0 victoire contre greedy). Ensuite, un épisode est une manche à N joueurs (2–5). Tous les sièges apprenants partagent les poids ; la récompense est
`(score moyen des adversaires − son score) / 10`, doublement inclus. Une part des sièges est tenue par le bot greedy.

**Génétique** : le génome est le vecteur de poids. Fitness = écart de score par manche sur des tables de 2 à 4 joueurs
(contre greedy et les meilleurs génomes précédents), mêmes graines pour toute la génération. `--init` permet d'amorcer
la population avec un modèle RL (hybride).

## Résultats (une seule graine d'entraînement par méthode)

Modèle RL (échauffement + 400 itérations), 400 parties par ligne, sièges tirés au sort, adversaires = bots `greedy` :

| Table | Victoires du RL | Score moyen RL | Score moyen d'un greedy |
|---|---|---|---|
| 2 joueurs | 64 % (hasard : 50 %) | 85,4 | 104,6 |
| 3 joueurs | 46 % (hasard : 33 %) | 75,8 | 90,7 à 93,4 |
| 4 joueurs | 30 % (hasard : 25 %) | 78,1 | 85,8 à 87,3 |
| 6 joueurs | 20 % (hasard : 17 %) | 76,5 | 80,8 à 83,1 |

Algorithme génétique seul, population aléatoire, 40 générations : **échec** (0 victoire contre greedy à 3 joueurs, score moyen 124 contre 40). L'évolution depuis des poids aléatoires ne rattrape pas l'heuristique dans ce budget.

Hybride (GA 25 générations, population amorcée par le modèle RL, mutations `sigma=0.03`) : bat greedy
(41 % de victoires à 3 joueurs sur 400 parties) mais **n'améliore pas le RL seul** : en duel direct à 3 joueurs
(600 parties, RL / hybride / greedy), victoires 41 % / 34 % / 24 %, scores moyens 81,6 / 84,9 / 98,8.
L'écart RL-hybride est modeste et n'a été mesuré que sur une graine d'entraînement.

Bilan : l'imitation puis le RL donnent le meilleur agent ; le GA seul échoue, et le GA en affinage n'apporte rien ici.
Les agents restent comparés à un seul adversaire de référence (`greedy`), pas à de vrais joueurs humains.

## Limites connues

- Le réseau ne voit pas les totaux de la partie (seulement la manche) : il ne sait pas qu'il vaut mieux finir tôt/tard selon la course à 100.
- Les cartes de départ sont retournées au hasard (pas de choix de l'agent).
- Le RL est entraîné par manche, l'évaluation se fait en parties complètes.
