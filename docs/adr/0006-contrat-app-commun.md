# 0006 — Un contrat d'app unique pour les trois langages

- Statut : Acceptée
- Date : 2026-10-01

## Contexte

Oikos (déploiement GitOps : Doco-CD, modèles compose, CI de gouvernance) et
Iaso (agents qui trient les erreurs lues dans Loki) sont construits en
parallèle. Pour fonctionner sans configuration par app, ils ont besoin que
toutes les apps se comportent pareil. Il s'agit des endpoints de santé, des
noms de métriques, du schéma de logs, des labels compose et de l'arrêt propre,
quel que soit le langage.

## Décision

- Le **contrat d'app** est rédigé une seule fois, dans
  [`docs/app-contract.md`](../app-contract.md) de `lduf/.github`. C'est la
  référence commune : `project_template`, Oikos, Iaso et les apps y renvoient
  au lieu de le recopier.
- Il est versionné (`contract: v1`). Un changement incompatible ouvre une `v2`
  et une nouvelle ADR.
- Il porte sur le **comportement observable** (HTTP, métriques, logs, config,
  signaux, image, compose), pas sur le choix des librairies.
- Un **dashboard Grafana générique** (variable `$app`) dans `lduf/.github` ne
  repose que sur les noms de métriques communs. Chaque app ne livre que son
  dashboard spécifique et ses alertes (`observability/`).
- Le respect du contrat est vérifié par la CI matrice du template : endpoints,
  `healthcheck`, format de log, `/metrics` sur 9300, arrêt sur SIGTERM.

## Conséquences

- Oikos peut scraper, router et superviser une nouvelle app à partir de ses
  seuls labels compose. Iaso peut requêter les erreurs de toutes les apps avec
  la même requête LogQL.
- Toute évolution transverse (nouvel endpoint, nouveau champ de log) passe par
  le contrat, puis par le template et `copier update`.
- Les apps existantes ne sont pas conformes aujourd'hui (logs non structlog,
  pas de `/readyz`, pas de métriques). Le guide de migration (Phase 5) traite
  ce point.

## Alternatives écartées

- **Contrat implicite dans chaque starter** : il dériverait entre les langages,
  et Oikos et Iaso n'auraient pas de référence stable.
- **Contrat dans `project_template`** : il serait lié au cycle du template,
  alors qu'Oikos et Iaso le consomment indépendamment.
