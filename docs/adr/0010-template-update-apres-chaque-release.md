# 0010 — Mises à jour du template poussées après chaque release

- Statut : Acceptée (remplace le point 6 de [0009](0009-sobriete-ci.md))
- Date : 2026-10-08

## Contexte

L'ADR 0009 avait limité le workflow `template-update` de `lduf/ktisis` au lundi et au
lancement manuel, pour éviter la cascade observée en octobre : 11 releases du template en
6 jours, chacune ouvrant une PR dans chaque app, avec sa CI, sa release et sa PR Oikos.

Mais une fois les autres mesures de 0009 en place, une PR d'app ne coûte plus qu'un job
`pr-checks` et une CI d'une ou deux minutes. Le coût qui justifiait de retirer le
déclenchement a disparu, alors que ce qu'il apportait compte : une PR de mise à jour dans
chaque app dès qu'une version du template sort, sans la lancer à la main.

## Décision

`template-update` repart après chaque release du template (job `template-update` de
`ci.yml`, appel du workflow), en plus du lundi (rattrape une app en retard) et du lancement
manuel. Le reste de 0009 ne change pas.

## Conséquences

- Chaque release du template ouvre ou met à jour une PR `ktisis/template-update` par app en
  retard (branche réécrite, PR existante réutilisée) : plusieurs releases rapprochées ne
  laissent qu'une PR par app, à jour sur la dernière version.
- Les PR sans conflit passent par la CI sobre ; seul le merge d'une PR déclenche la release de
  l'app et son déploiement.
- Le workflow garde son groupe de concurrence : deux releases rapprochées ne se chevauchent
  pas.

## Alternatives écartées

- **Le lundi seulement** : économise quelques minutes de `pr-checks` et de CI, mais retarde
  d'une semaine chaque correction du template et ramène la mise à jour à la main.
