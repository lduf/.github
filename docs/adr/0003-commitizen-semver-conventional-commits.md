# 0003 — SemVer calculé par commitizen depuis les Conventional Commits

- Statut : Acceptée
- Date : 2026-10-01

## Contexte

Aujourd'hui, chaque PR doit bumper la version et écrire sa section de
CHANGELOG (workflow `version-check.yml`). C'est le LLM qui le fait :

- les conflits sont fréquents entre PR parallèles ;
- les bumps sont incohérents ;
- les PR portent du bruit sans rapport avec le changement.

On veut que la version **découle** de l'historique, sans intervention humaine
ni LLM.

## Décision

1. **Conventional Commits** est la seule source d'information pour les
   releases. Les repos sont configurés en **squash merge uniquement** : le titre
   de la PR devient le message du commit sur `main`, et la CI le valide.
2. **[commitizen](https://commitizen-tools.github.io/commitizen/)** calcule le
   bump, écrit le CHANGELOG et crée le tag (`cz bump --changelog --yes`). La
   même config sert à valider les titres de PR (`cz check`).
3. **Source de vérité de la version : le tag `vX.Y.Z`.** Les fichiers de
   version ne sont que des reflets mis à jour par le bot :

   | Langage | `version_provider` | Ce que le bot écrit | Lecture au runtime |
   |---|---|---|---|
   | Python | `uv` | `[project].version` de `pyproject.toml` + `uv.lock` | `importlib.metadata.version()` |
   | Rust | `cargo` | `[package].version` de `Cargo.toml` + `Cargo.lock` | `env!("CARGO_PKG_VERSION")` |
   | Go | `scm` (lecture seule, `git describe`) | Rien : pas de fichier `VERSION` | `-ldflags "-X main.version=…"` au build |

4. **Règles de bump** : on prend tous les commits depuis le dernier tag et on
   retient le plus fort.

   | Commit | Bump (≥ 1.0) | Bump (0.x) | Section du CHANGELOG |
   |---|---|---|---|
   | `type!:` ou pied `BREAKING CHANGE:` | major | **minor** | Breaking |
   | `feat` | minor | minor | Features |
   | `fix`, `perf` | patch | patch | Fixes / Performance |
   | `chore`, `docs`, `ci`, `test`, `refactor`, `style`, `build` | aucun | aucun | absent |

   Un minor remet le patch à 0 ; un major remet le minor et le patch à 0.
   Sans commit qui bumpe, il n'y a pas de release.
5. **`major_version_zero = true`** tant que l'app est en `0.x`. Le passage en
   `1.0.0` est une décision explicite de Lucas (`cz bump --increment MAJOR`
   lancé à la main via `workflow_dispatch`), jamais automatique.
6. **Renovate** écrit des commits `fix(deps): …` : une mise à jour de
   dépendance produit un patch.
7. **Personne ne touche à la version ni au CHANGELOG dans une PR.** La CI
   rejette toute PR qui modifie `CHANGELOG.md` ou le **champ** de version (on
   compare le champ, pas le fichier, puisque `pyproject.toml` et `Cargo.toml`
   changent aussi quand on ajoute une dépendance).

### Piège vérifié : les défauts de commitizen ne conviennent pas

Dans le preset `cz_conventional_commits`, la `BUMP_MAP` par défaut fait passer
**`refactor` en PATCH** et le CHANGELOG contient une section *Refactor*. C'est
contraire au point 4. La config commune utilise donc `cz_customize`, qui permet
de redéfinir `bump_map`, `bump_map_major_version_zero`, `change_type_map`,
`change_type_order`, `changelog_pattern` et `commit_parser` (vérifié dans le
code source de commitizen). Esquisse, validée en Phase 2 dans le bac à sable :

```toml
[tool.commitizen]
name = "cz_customize"
tag_format = "v$version"
version_provider = "uv"            # cargo | scm selon le langage
major_version_zero = true
update_changelog_on_bump = true
bump_message = "chore(release): v$new_version"

[tool.commitizen.customize]
bump_pattern = '^((BREAKING[\-\ ]CHANGE|feat|fix|perf)(\([^()]*\))?(!)?|\w+(\([^()]*\))?!):'
bump_map = { '^.+!$' = "MAJOR", '^BREAKING[\-\ ]CHANGE' = "MAJOR", '^feat' = "MINOR", '^fix' = "PATCH", '^perf' = "PATCH" }
bump_map_major_version_zero = { '^.+!$' = "MINOR", '^BREAKING[\-\ ]CHANGE' = "MINOR", '^feat' = "MINOR", '^fix' = "PATCH", '^perf' = "PATCH" }
change_type_map = { feat = "Features", fix = "Fixes", perf = "Performance" }
change_type_order = ["BREAKING CHANGE", "Features", "Fixes", "Performance"]
```

Pour Rust et Go, la même config vit dans `.cz.toml`. Elle est générée par
Copier et mise à jour par `copier update`.

### Détection des changements cassants (contrôles de PR)

- `!` dans le titre ⇔ section *Breaking* remplie dans la description, sinon la
  CI échoue.
- Apps avec API : **oasdiff** compare l'OpenAPI de la base à celui de la PR. Un
  changement cassant détecté sans `!` fait échouer la CI.
- Avertissement, sans blocage, si la PR ajoute une migration de base, ou
  supprime ou renomme une variable d'environnement, sans `!`.

## Conséquences

- Plus aucun conflit de version ou de CHANGELOG entre PR.
- La qualité des releases dépend de la qualité des **titres de PR** : ils sont
  validés en CI, et la description de PR porte la section *Breaking*.
- Le CHANGELOG ne liste que Breaking, Features, Fixes et Performance. Le reste
  (docs, refactor, CI) reste visible dans l'historique Git.
- Go n'a pas de fichier de version : le contrôle « version inchangée » ne
  s'applique pas aux apps Go.
- Le preset est personnalisé : une mise à jour majeure de commitizen doit être
  validée par la CI matrice du template avant d'être adoptée.

## Alternatives écartées

- **cocogitto** : même périmètre, en binaire Rust. C'est l'option de repli si
  commitizen coince, mais ses version providers sont moins riches (pas de
  synchronisation native `uv.lock` / `Cargo.lock`).
- **release-please** : impose une PR de release, contraire à
  l'[ADR 0004](0004-release-push-direct-sur-main.md).
- **semantic-release** : écosystème Node, configuration par plugins, un
  runtime de plus pour des apps Python, Go et Rust.
- **Version écrite par le LLM** : c'est le système actuel, source de conflits
  et d'incohérences.
