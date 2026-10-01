# Release et contrôles de PR — mode d'emploi

Décisions : [ADR 0003](adr/0003-commitizen-semver-conventional-commits.md) et
[ADR 0004](adr/0004-release-push-direct-sur-main.md). Workflows :
[`pr-checks.yml`](../.github/workflows/pr-checks.yml) et
[`release.yml`](../.github/workflows/release.yml).

## En bref

1. On ouvre une PR. Son **titre** est un Conventional Commit (`feat: …`,
   `fix(api): …`, `feat!: …`). Sa **description** suit le modèle :
   *Quoi*, *Pourquoi*, *Breaking ?*.
2. On merge la PR (squash uniquement : titre et description deviennent le
   commit sur `main`).
3. La CI décide seule : release ou non, quelle version, CHANGELOG, tag, image,
   déploiement. **Personne ne touche à la version ni au CHANGELOG.**

## Quel titre donne quelle release ?

| Titre de PR | Release (≥ 1.0) | Release (0.x) |
|---|---|---|
| `feat!: …`, `fix!: …`, `chore!: …` (+ paragraphe `BREAKING CHANGE:`) | major | minor |
| `feat: …` | minor | minor |
| `fix: …`, `perf: …` | patch | patch |
| `docs`, `chore`, `ci`, `test`, `refactor`, `style`, `build`, `revert` | aucune | aucune |

Plusieurs merges rapprochés peuvent sortir en **une seule** release : le bump
retient le changement le plus fort depuis le dernier tag. Les runs de release
se suivent sans s'annuler, mais GitHub ne garde qu'**un** run en attente : les
runs intermédiaires apparaissent « cancelled » dans l'onglet Actions. C'est
normal et sans perte, car le run suivant relit `main` et couvre tous les
commits.

## Annoncer un changement cassant

Le titre porte `!` **et** la section *Breaking ?* remplace « Non » par un
paragraphe qui commence exactement par `BREAKING CHANGE:` :

```markdown
## Breaking ?

BREAKING CHANGE: la route /items devient /things.
```

Ce paragraphe apparaît tel quel dans la section *Breaking* du CHANGELOG. La CI
refuse un `!` sans paragraphe, et un paragraphe sans `!`.

Sont considérés comme cassants : une API qui change de façon incompatible
(oasdiff le détecte si l'app committe sa spec OpenAPI), une variable
d'environnement supprimée ou renommée, une migration de base non
rétrocompatible. Les deux derniers cas donnent un avertissement, pas un échec.

## Ce que la CI refuse sur une PR (`pr-checks / checks`)

- Titre hors Conventional Commits.
- Section *Quoi*, *Pourquoi* ou *Breaking ?* vide ; *Breaking ?* qui n'est ni
  « Non » ni un paragraphe `BREAKING CHANGE:`.
- Modification de `CHANGELOG.md`.
- Modification du **champ** de version (`[project].version`,
  `[package].version`, `VERSION`…). Ajouter une dépendance dans
  `pyproject.toml` ou `Cargo.toml` reste permis.
- Paragraphe de description qui commence par `feat:`, `fix:` ou `perf:` : il
  finirait dans le CHANGELOG.

## Label `no-deploy`

Une release a quand même lieu (version, CHANGELOG, tag, image `X.Y.Z`) mais
le déploiement est sauté et `latest` ne bouge pas. Si **une** PR d'un lot
porte le label, tout le lot n'est pas déployé : l'image contient ce code.

`no-deploy` veut dire « pas maintenant », pas « jamais » : la prochaine
release déployée embarquera ce code. Pour retenir une fonctionnalité
durablement, utiliser un feature flag, ou ne pas merger.

Déployer plus tard une version restée en `no-deploy` : **Actions → ci → Run
workflow**, version `X.Y.Z`. L'image existante est redéployée sans rebuild.

## Passer en 1.0.0

Décision explicite, jamais automatique. Ouvrir une PR
`chore: sortie de la série 0.x` qui passe `major_version_zero = false` dans la
config commitizen. La prochaine PR cassante (`feat!: …`) produira `1.0.0`.

## Images et déploiement

Sur une release : image GHCR `X.Y.Z`, `X.Y`, `sha-<court>`. Le déploiement
dépend de l'input `deploy_mode` :

| `deploy_mode` | Effet |
|---|---|
| `portainer-webhook` (défaut, transition) | pousse aussi `latest`, puis appelle le secret `PORTAINER_WEBHOOK_URL` |
| `oikos-pr` | ouvre une PR sur `lduf/oikos` (pas encore implémenté) |
| `none` | rien |

## Mettre en place un repo

```bash
# une fois par repo, depuis un clone de lduf/.github (gh connecté en admin)
scripts/setup-repo.sh lduf/mon-app --key ~/chemin/release-bot.pem
```

Le script règle le merge (squash, titre et description de la PR), crée le
label `no-deploy`, crée ou met à jour les rulesets `main` et `release-tags`
(seule l'App de release les contourne) et pose l'identité de l'App : variable `RELEASE_APP_CLIENT_ID` et secret `RELEASE_APP_PRIVATE_KEY`. Il est
idempotent. L'App doit être installée sur le repo : le plus simple est une
installation « All repositories ».

Le `ci.yml` de l'app :

```yaml
name: ci
on:
  pull_request:
    types: [opened, edited, synchronize, reopened, labeled, unlabeled]
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      version: { description: "Version existante à redéployer (X.Y.Z)", required: true }
jobs:
  pr-checks:
    if: github.event_name == 'pull_request'
    uses: lduf/.github/.github/workflows/pr-checks.yml@main
    permissions: { contents: read, pull-requests: read }
  release:
    if: github.event_name != 'pull_request'
    uses: lduf/.github/.github/workflows/release.yml@main
    permissions: { contents: read, packages: write, pull-requests: read }
    with: { redeploy_version: "${{ inputs.version }}" }
    secrets: inherit
```

## Config commitizen de référence

Générée par Copier dans chaque app (`pyproject.toml` en Python, `.cz.toml` en
Go et Rust ; seul `version_provider` change : `uv`, `scm`, `cargo`) :

```toml
[tool.commitizen]
name = "cz_customize"
tag_format = "v$version"
version_provider = "uv"
version_scheme = "semver2"
major_version_zero = true
update_changelog_on_bump = true
bump_message = "chore(release): v$new_version"

[tool.commitizen.customize]
bump_pattern = '^((BREAKING[\-\ ]CHANGE|feat|fix|perf)(\([^()\r\n]*\))?(!)?|\w+(\([^()\r\n]*\))?!):'
bump_map = { '^.+!$' = "MAJOR", '^BREAKING[\-\ ]CHANGE' = "MAJOR", '^feat' = "MINOR", '^fix' = "PATCH", '^perf' = "PATCH" }
bump_map_major_version_zero = { '^.+!$' = "MINOR", '^BREAKING[\-\ ]CHANGE' = "MINOR", '^feat' = "MINOR", '^fix' = "PATCH", '^perf' = "PATCH" }
commit_parser = '^(?P<change_type>feat|fix|perf|BREAKING CHANGE)(?:\((?P<scope>[^()\r\n]*)\))?(?P<breaking>!)?:\s(?P<message>.*)?'
changelog_pattern = '^((BREAKING[\-\ ]CHANGE|feat|fix|perf)(\([^()\r\n]*\))?(!)?|\w+(\([^()\r\n]*\))?!):'
change_type_map = { "BREAKING CHANGE" = "Breaking", feat = "Features", fix = "Fixes", perf = "Performance" }
change_type_order = ["Breaking", "Features", "Fixes", "Performance"]
```
