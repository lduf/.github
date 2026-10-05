# .github

Paramètres et références communs à tous les repos `lduf` : modèles d'issues et
de PR, et socle commun des apps générées depuis
[`lduf/ktisis`](https://github.com/lduf/ktisis).

## Sommaire

- [Contrat d'app](docs/app-contract.md) (`contract: v1`) : ce que toute app
  expose et respecte, en Python, Go ou Rust (endpoints, métriques, logs,
  config, arrêt, image, compose). Référence pour Oikos et Iaso.
- [Décisions d'architecture (ADR)](docs/adr/README.md) : Copier, just,
  commitizen, release poussée directement sur `main`, Rust au premier rang,
  contrat commun.
- [Release et contrôles de PR](docs/release.md) : quel titre donne quelle
  release, changement cassant, `no-deploy`, mise en place d'un repo.
- Workflows réutilisables : [`pr-checks.yml`](.github/workflows/pr-checks.yml),
  [`release.yml`](.github/workflows/release.yml), et la qualité par langage
  (`just check` + build de l'image) : [`ci-python.yml`](.github/workflows/ci-python.yml),
  [`ci-go.yml`](.github/workflows/ci-go.yml), [`ci-rust.yml`](.github/workflows/ci-rust.yml).
- [Dashboard Grafana générique](observability/app-generic-dashboard.json)
  (variable `$app`) : vues HTTP communes à toutes les apps.
- [`scripts/setup-repo.sh`](scripts/setup-repo.sh) et [`rulesets/`](rulesets/) :
  réglages de merge, label et rulesets d'un repo en une commande.
- `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md` : modèles par
  défaut de l'organisation.

Les apps sont générées par le template Copier
[`lduf/ktisis`](https://github.com/lduf/ktisis).
