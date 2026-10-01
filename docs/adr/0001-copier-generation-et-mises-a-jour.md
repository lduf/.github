# 0001 — Copier pour générer les projets et propager le template

- Statut : Acceptée
- Date : 2026-10-01

## Contexte

Aujourd'hui, `project_template` contient deux starters (`starters/python`,
`starters/go`). Au démarrage, la skill `kickstart` remonte le starter retenu
par des `git mv`, puis supprime l'autre. Ce mécanisme a trois défauts :

- il ne gère qu'un axe de choix (le langage), alors qu'il en faut au moins trois
  (langage, base de données, mode d'auth) ;
- il dépend d'un LLM qui exécute correctement une suite de commandes
  manuelles ;
- une fois le projet créé, **aucune évolution du template ne se propage** : les
  apps divergent dès le premier jour.

## Décision

Le template devient un **template [Copier](https://copier.readthedocs.io/)**.

- Questions posées à la génération (`copier.yml`) : `app_name`, `domain`,
  `lang` (`python` | `go` | `rust`), `with_db` (bool), `auth_mode`
  (`oidc` | `proxy` | `public`).
- Fichiers et blocs conditionnels en Jinja (noms de fichiers et contenus) : un
  seul arbre de sortie, pas de `git mv`.
- Les réponses sont enregistrées dans `.copier-answers.yml`, committé dans
  l'app : c'est ce qui rend possible `copier update`.
- Le template est versionné par des **tags Git** (`vX.Y.Z`) : `copier update`
  applique le diff entre le tag d'origine et le tag cible, avec un merge à
  trois voies.
- La CI du template génère une matrice `lang × with_db × auth_mode` et exécute
  `just check` et le build de l'image sur chaque combinaison.

## Conséquences

- Les évolutions du template (contrat, CI, Dockerfile, conventions) se
  propagent aux apps par `copier update`, en PR, conflits compris.
- Les fichiers templatés (`*.jinja`) ne sont plus exécutables tels quels dans le
  repo du template : seule la CI matrice prouve qu'ils sont verts. Elle est
  donc obligatoire.
- La personnalisation propre à l'app doit rester hors des zones fortement
  templatées, sinon chaque `copier update` produit des conflits. Le guide de
  migration (Phase 5) le précise.
- Copier devient un outil de dev requis (`uvx copier`, pas d'installation
  globale).

## Alternatives écartées

- **Garder les `git mv`** : pas de propagation, axes de choix limités.
- **cookiecutter** : pas d'équivalent natif à `copier update`. Cruft le
  complète, mais c'est un outil de plus.
- **Un repo template par langage** : trois fois la maintenance des éléments
  communs (contrat, compose, observabilité, docs).
