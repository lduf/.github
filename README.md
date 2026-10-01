# .github

Paramètres et références communs à tous les repos `lduf` : modèles d'issues et
de PR, et socle commun des apps générées depuis
[`lduf/project_template`](https://github.com/lduf/project_template).

## Sommaire

- [Contrat d'app](docs/app-contract.md) (`contract: v1`) : ce que toute app
  expose et respecte, en Python, Go ou Rust (endpoints, métriques, logs,
  config, arrêt, image, compose). Référence pour Oikos et Iaso.
- [Décisions d'architecture (ADR)](docs/adr/README.md) : Copier, just,
  commitizen, release poussée directement sur `main`, Rust au premier rang,
  contrat commun.
- `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md` : modèles par
  défaut de l'organisation.

À venir : workflows réutilisables (`pr-checks.yml`, `ci-python.yml`,
`ci-go.yml`, `ci-rust.yml`, `release.yml`) et dashboard Grafana générique.
