# 0008 — « Pas de merge, on rebase » vérifié par pr-checks, pas par un ruleset

- Statut : Acceptée (amende [0007](0007-standard-ktisis-gouvernance-des-repos.md))
- Date : 2026-10-06

## Contexte

L'ADR 0007 imposait l'historique linéaire par un ruleset `linear-history`
appliqué à toutes les branches. Sur magic-image et personnal_budget, dont
`main` contient d'anciens commits de merge (avant le squash obligatoire),
GitHub a refusé la création de **toute** nouvelle branche : à la création,
la règle examine l'historique entier de la branche, pas seulement les
nouveaux commits. Plus aucun travail n'était possible dans ces repos.

Au même moment, une PR `copier update` a été mergée avec des marqueurs de
conflit dans le README : rien ne les détectait.

## Décision

- Le ruleset `linear-history` est retiré du standard ; `setup-repo` le
  supprime des repos où il existe.
- `pr-checks / checks` (check requis) échoue si la PR contient un commit de
  merge (`git rev-list --merges base..head`) : on se met toujours à jour par
  rebase, mais seuls les commits de la PR comptent.
- `pr-checks / checks` échoue aussi si un fichier ajouté ou modifié par la
  PR contient des marqueurs de conflit (`<<<<<<<`, `>>>>>>>` en début de
  ligne).
- `main` reste linéaire par le squash obligatoire du ruleset `main`.

## Conséquences

- L'erreur arrive à la PR et non au `git push` : un merge poussé sur une
  branche de travail est accepté par GitHub, mais la PR ne peut pas être
  mergée tant qu'il reste.
- Un repo avec un vieil historique de merges fonctionne normalement.

## Alternatives écartées

- **Garder `linear-history` sur les branches de travail** : bloque tous les
  repos qui ont des merges dans leur historique.
- **`required_linear_history` dans le ruleset `main`** : redondant avec le
  squash obligatoire.
