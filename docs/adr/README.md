# Décisions d'architecture (ADR)

Décisions structurantes communes à toutes les apps générées depuis
`lduf/ktisis`. Une ADR est courte et datée. Elle ne se modifie pas
après acceptation : une décision qui change fait l'objet d'une nouvelle ADR,
qui *remplace* l'ancienne (statut mis à jour dans les deux).

| N° | Titre | Statut |
|---|---|---|
| [0001](0001-copier-generation-et-mises-a-jour.md) | Copier pour générer les projets et propager le template | Acceptée |
| [0002](0002-just-interface-commune.md) | just comme interface de commandes commune | Acceptée |
| [0003](0003-commitizen-semver-conventional-commits.md) | SemVer calculé par commitizen depuis les Conventional Commits | Acceptée |
| [0004](0004-release-push-direct-sur-main.md) | Release poussée directement sur `main` par la CI, sans PR de release | Acceptée |
| [0005](0005-rust-langage-de-premier-rang.md) | Rust, langage de premier rang à côté de Python et Go | Acceptée |
| [0006](0006-contrat-app-commun.md) | Un contrat d'app unique pour les trois langages | Acceptée |
| [0007](0007-standard-ktisis-gouvernance-des-repos.md) | Standard Ktisis : règles de repo appliquées par `setup-repo`, vérifiées par `ktisis audit` | Acceptée, amendée par 0008 |
| [0008](0008-rebase-verifie-par-pr-checks.md) | « Pas de merge, on rebase » vérifié par pr-checks, pas par un ruleset | Acceptée |
| [0009](0009-sobriete-ci.md) | CI sobre : déclencheurs restreints, jobs regroupés, matrice du template ciblée | Acceptée |

## Modèle

```markdown
# NNNN — Titre

- Statut : Proposée | Acceptée | Remplacée par NNNN
- Date : AAAA-MM-JJ

## Contexte
Le problème, les contraintes, ce qui force à décider.

## Décision
Ce qu'on fait, formulé de façon vérifiable.

## Conséquences
Ce que ça implique, y compris les coûts et les pièges connus.

## Alternatives écartées
Option — pourquoi non.
```
