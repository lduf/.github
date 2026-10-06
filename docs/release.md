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
- Ligne de description lue comme un commit par la release : une ligne qui
  commence par `feat:`, `fix:`, `perf:`, `xxx!:` ou `BREAKING CHANGE:` (hors
  du paragraphe Breaking prévu). La description devient le corps du commit,
  et commitizen teste **chaque ligne** pour calculer la version. La
  reformuler : l'indenter, la mettre entre backticks ou dans une liste.

La longueur de la description n'a pas d'importance : le CHANGELOG ne reprend
que le **titre** de la PR et le paragraphe `BREAKING CHANGE:`.

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
| `oikos-pr` | ouvre une PR de release sur `lduf/oikos` et active son **auto-merge** : elle est fusionnée dès que la CI d'Oikos est verte, sans revue, et le merge déploie (doco-cd). Pas de `latest` |
| `none` | rien |

### `oikos-pr` en détail

Décisions : ADR 0009 (format) et ADR 0011 (auto-merge) d'Oikos.

1. Checkout de `lduf/oikos` avec un token de l'App de release limité à ce
   repo (`contents: write`, `pull-requests: write`).
2. `platform/release/apply.py` d'Oikos écrit la ligne `image:`
   (`X.Y.Z@sha256:<digest>`) de `stacks/<stack>/compose.yml`, et copie
   `observability/` (alertes, leurs tests, dashboard). Il refuse si un point
   manque : le run échoue, rien n'est poussé.
3. Branche `release/<app>-X.Y.Z`, PR, puis `gh pr merge --auto`. Une PR de
   release plus ancienne de la même app encore ouverte est fermée (remplacée).
4. La CI d'Oikos (`validate`) passe → GitHub fusionne → doco-cd déploie.
   CI rouge → la PR reste ouverte, rien n'est déployé : corriger, ou fermer la
   PR.

Inputs : `stack` (dossier `stacks/<stack>` d'Oikos, par défaut le nom du repo,
ex. `stack: aether_run` pour `aether_run_api`) et `oikos_repo` (défaut
`oikos`). Redéploiement d'une version (`workflow_dispatch`) : même chemin,
avec le digest lu dans le registre et `observability/` du tag.

Revenir en arrière : redéployer la version précédente (`workflow_dispatch`),
ou revert de la PR sur Oikos.

## Mettre en place un repo

Sans rien cloner : workflow **`setup-repo`** de `lduf/.github` (Actions → setup-repo → Run
workflow, `gh workflow run setup-repo.yml -R lduf/.github -f repo=mon-app`, ou un agent via
l'API `workflow_dispatch`). Il tourne avec le token de l'App de release.

```bash
# variante locale, depuis un clone de lduf/.github (gh connecté en admin)
scripts/setup-repo.sh lduf/mon-app --key ~/chemin/release-bot.pem
```

**Migration d'un repo qui a déjà des versions** : ajouter `base_tag=vX.Y.Z` (dernière
version publiée) et `base_ref=<sha>` (commit qui la porte, défaut : tête de la branche par
défaut). Sans ce tag, commitizen ne connaît aucune version et la première release repartirait
de `0.1.0`/`1.0.0`. Le tag est posé par l'App (les humains ne peuvent pas pousser de `v*`) ;
rien n'est fait s'il existe déjà au même commit, erreur s'il existe ailleurs.

Les checks requis sont ceux passés en option, sinon ceux du ruleset `main`
existant (une relance ne les écrase pas), sinon `pr-checks / checks` et
`ci / check`. Le script applique le [standard Ktisis](gouvernance.md) :
réglages de merge et d'Actions, alertes Dependabot, label `no-deploy`,
rulesets `main`, `branch-names`, `linear-history` et `release-tags` (seule
l'App de release les contourne), Pages par Actions si le repo a un
`pages.yml`, topic `ktisis`. Il pose aussi l'identité de l'App : variable
`RELEASE_APP_CLIENT_ID` et secret `RELEASE_APP_PRIVATE_KEY`. Il est
idempotent : le relancer remet au standard un repo qui a dérivé. Pour Pages,
l'App doit avoir la permission *Pages: read and write*. L'App doit être installée sur le repo : le plus simple est une
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
  ci:  # just check + build de l'image ; python | go | rust
    if: github.event_name == 'pull_request'
    uses: lduf/.github/.github/workflows/ci-python.yml@main
    permissions: { contents: read }
  release:
    if: github.event_name != 'pull_request'
    uses: lduf/.github/.github/workflows/release.yml@main
    permissions: { contents: read, packages: write, pull-requests: read }
    with: { redeploy_version: "${{ inputs.version }}" }
    secrets: inherit
```

Sur Oikos : `with: { deploy_mode: oikos-pr, redeploy_version: "${{ inputs.version }}" }`
(+ `stack:` si le dossier d'Oikos ne porte pas le nom du repo). L'App de
release doit être installée sur `lduf/oikos` avec `pull-requests: write`.

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
