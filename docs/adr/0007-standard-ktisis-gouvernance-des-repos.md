# 0007 — Standard Ktisis : règles de repo appliquées par `setup-repo`, vérifiées par `ktisis audit`

- Statut : Acceptée, amendée par [0008](0008-rebase-verifie-par-pr-checks.md) (ruleset `linear-history` retiré)
- Date : 2026-10-06

## Contexte

Les conventions de travail (branches, mise à jour, merge, secrets, Pages)
existaient en partie dans les réglages posés par `setup-repo` et en partie
dans la tête de Lucas. Les agents (Claude Code) travaillent aussi dans ces
repos. Une convention qui n'est pas appliquée par la plateforme finit par
dériver. Le compte est un compte perso GitHub Pro : rulesets de branches et de
tags et Pages sur repos privés disponibles. Pas de secret scanning, de
CodeQL ni de push rulesets sur les repos privés, ni de merge queue.

## Décision

- Le **standard** est écrit une fois, dans [`docs/gouvernance.md`](../gouvernance.md)
  de `lduf/.github`. Chaque règle y nomme son mécanisme.
- Il est **appliqué** par `setup-repo` (idempotent) : réglages de merge et
  d'Actions, alertes Dependabot, Pages par Actions, topic `ktisis`, et quatre
  rulesets dont seule l'App de release est exemptée :
  - `main` : PR, squash, checks requis, conversations résolues, ni
    force-push ni suppression ;
  - `branch-names` : création de branche limitée aux préfixes
    conventionnels et aux préfixes des outils (`claude/`, `renovate/`…) ;
  - `linear-history` : aucun commit de merge sur aucune branche, donc mise à
    jour par rebase ;
  - `release-tags` : tags `v*` réservés au bot.
- Labels uniformes (`labels.json` : `type:`, `area:`, `breaking`,
  `blocked`, `urgent`, `no-deploy`), posés automatiquement sur les PR par
  `pr-checks` ; dépendances entre PR (`Dépend de : owner/repo#N`) qui
  bloquent le merge ; un agent passe sa PR en *Ready for review* dès
  qu'elle est prête (ajout du 2026-10-06).
- `pr-checks` ajoute **gitleaks** sur les commits de la PR, à la place du
  secret scanning indisponible.
- Il est **réconcilié** chaque semaine par le workflow `gouvernance` de
  `lduf/.github` : `setup-repo` rejoué sur tous les repos au topic `ktisis`,
  avec le token de l'App de release (installation « All repositories »).
- Il est **vérifié** par `ktisis audit`, qui compare les réglages GitHub du
  repo au standard.
- Il **évolue** par PR sur `lduf/.github`. Relancer `setup-repo` propage la
  nouvelle version à un repo.

## Conséquences

- Un `git push` d'une branche mal nommée, ou d'une branche qui contient un
  merge, est refusé tout de suite, avec un message de GitHub.
- On ne peut plus mettre une PR à jour par *Update branch (merge)* :
  *Update with rebase*, ou rebase local puis `--force-with-lease`.
- Pas d'exigence de branche à jour avant merge : sinon chaque commit
  `chore(release)` du bot imposerait de rebaser toutes les PR ouvertes.
- Un site Pages est public, même pour un repo privé (limite des comptes
  perso).
- Un nouveau préfixe d'outil (autre bot) demande une PR sur
  `rulesets/branch-names.json`.
- Un réglage changé à la main dans un repo `ktisis` est écrasé le lundi
  suivant : une exception passe par le standard (PR sur `lduf/.github`), ou
  par le retrait du topic.

## Alternatives écartées

- **Signature des commits exigée sur `main`** : un commit non signé sur la
  branche de PR bloque le squash, même si GitHub signe le commit final. Les
  commits des agents et des bots ne sont pas signés. Recommandée seulement.
- **Branche à jour exigée (strict)** : coût de rebase à chaque release, sans
  gain avec le squash.
- **Contrôle du nom de branche dans la CI** : arrive après le push, alors que
  le ruleset refuse la création elle-même.
- **Réglages appliqués à la main** : dérivent sans qu'on le voie.
- **Audit seul, sans réconciliation** : signale l'écart mais laisse le repo
  dériver jusqu'à une action manuelle.
