# Standard Ktisis — gouvernance des repos

Règles de fonctionnement de tout repo `lduf` créé ou adopté par Ktisis
(décision : [ADR 0007](adr/0007-standard-ktisis-gouvernance-des-repos.md)).
Chaque règle dit **qui la fait respecter**. Une règle sans mécanisme n'est
qu'une recommandation, et le tableau le dit.

- **Appliquer** : workflow `setup-repo` (ou `scripts/setup-repo.sh`), idempotent.
  Le relancer remet au standard un repo qui a dérivé.
- **Vérifier** : `ktisis audit` dans le repo (section GitHub).
- **Faire évoluer** : PR sur `lduf/.github` (rulesets, script, ce document).
  Le standard est versionné avec ce repo.

## Branches

| Règle | Mécanisme |
|---|---|
| `main` est la seule branche longue. Elle ne reçoit que des PR, jamais de push direct, de force-push ni de suppression | ruleset `main` |
| Une branche porte un **préfixe conventionnel** : `feat/`, `fix/`, `perf/`, `refactor/`, `docs/`, `test/`, `build/`, `ci/`, `chore/`, `style/`, `revert/` (ex. `feat/export-csv`) | ruleset `branch-names` : toute autre création est refusée |
| Préfixes réservés aux outils : `claude/` (Claude Code), `renovate/`, `dependabot/`, `copilot/`, `ktisis/` (mise à jour du template), `release/` (PR de release Oikos), `revert-*` (bouton *Revert* de GitHub) | ruleset `branch-names` |
| Branche supprimée au merge | réglage `delete_branch_on_merge` |
| Une branche vit peu : une PR = un changement, mergée en jours, pas en semaines | recommandation |

Le refus s'affiche au `git push` (« creations being restricted ») : renommer
la branche (`git branch -m feat/…`) puis repousser. Une branche créée avant le
ruleset n'est pas touchée.

## Se mettre à jour : rebase, jamais merge

| Règle | Mécanisme |
|---|---|
| Aucun commit de merge, sur aucune branche | ruleset `linear-history` : un push qui contient un merge est refusé |
| On se met à jour par **rebase** sur `origin/main` | conséquence de la règle précédente |
| Sur GitHub : *Update branch* → **Update with rebase** | bouton affiché (`allow_update_branch`), l'option merge est refusée par le ruleset |

En local, une fois pour toutes :

```bash
git config --global pull.rebase true
git config --global rebase.autoStash true
git config --global push.autoSetupRemote true
```

Puis, sur sa branche : `git fetch && git rebase origin/main && git push --force-with-lease`.
Le force-push est permis sur les branches de travail, interdit sur `main`.

Les PR n'ont **pas** besoin d'être à jour pour être mergées
(`strict_required_status_checks_policy: false`). Après chaque release, le bot
pousse `chore(release)` sur `main` : exiger une branche à jour forcerait un
rebase de toutes les PR ouvertes à chaque release. Le squash rejoue le diff de
la PR sur le `main` du moment. Les checks requis tournent sur la tête de la
PR, et `main` est revalidé par la release.

## Commits et PR

| Règle | Mécanisme |
|---|---|
| Titre de PR en Conventional Commits. Il devient le commit sur `main` et décide de la release | `pr-checks / checks` (requis) |
| Description : *Quoi*, *Pourquoi*, *Breaking ?* | `pr-checks / checks` |
| Merge en **squash** uniquement (titre = titre de PR, corps = description) | réglages de merge + ruleset `main` |
| Checks requis verts : `pr-checks / checks`, `ci / check` (ou ceux propres au repo) | ruleset `main` |
| Conversations de revue résolues avant merge | ruleset `main` (`required_review_thread_resolution`) |
| Pas de version ni de CHANGELOG à la main | `pr-checks / checks` ([release.md](release.md)) |
| Auto-merge autorisé : `gh pr merge --auto --squash` merge dès que les checks passent | réglage `allow_auto_merge` |
| Messages des commits intermédiaires libres : seul le titre de PR compte | — |

## Secrets et sécurité

| Règle | Mécanisme |
|---|---|
| Aucun secret dans git | gitleaks sur les commits de chaque PR (`pr-checks / checks`). Faux positif : empreinte dans `.gitleaksignore` |
| Secrets de prod chiffrés dans Oikos (SOPS), jamais dans le repo de l'app | contrat d'app, revue |
| Vulnérabilités des dépendances signalées | alertes Dependabot (activées par `setup-repo`) |
| Dépendances à jour | Renovate (`renovate.json` du template). Les PR de sécurité de Dependabot restent coupées pour éviter les doublons |
| `GITHUB_TOKEN` en lecture seule par défaut. Chaque workflow déclare ses `permissions`, au plus juste | réglage Actions + template |
| Un workflow ne peut pas approuver de PR | réglage Actions |
| Tags `v*` réservés au bot de release | ruleset `release-tags` |
| Seule l'App de release contourne les rulesets. Aucun humain, admin compris | `bypass_actors` |

Signature des commits : **recommandée, pas exigée**. Avec la règle
« Require signed commits », un seul commit non signé sur la branche bloque le
squash merge, même si GitHub signe le commit final. C'est le cas des commits
des agents et des bots. Les commits de `main` issus d'un squash sont signés
par GitHub. Pour signer ses propres commits en local : clé SSH déclarée en
*Signing key* sur GitHub, `git config --global gpg.format ssh`,
`user.signingkey`, `commit.gpgsign true`.

## GitHub Pages

Publié **par GitHub Actions** (`build_type: workflow`), jamais depuis une
branche `gh-pages`. `setup-repo` l'active si le repo a
`.github/workflows/pages.yml` (généré par le template, MkDocs Material).

> Avec un compte perso, même Pro, un site Pages est **public**, même si le
> repo est privé (Pages privé : organisation en Enterprise Cloud). Ne rien
> publier dans `docs/` qui ne puisse être lu par tous.

## Hygiène du repo

- Wiki et Projects désactivés : la doc vit dans `docs/` (versionnée, revue en
  PR), le suivi dans les issues.
- Topic `ktisis` : marque le repo comme soumis au standard (inventaire).
- Label `no-deploy` ([release.md](release.md)).

## Ce que GitHub Pro n'offre pas (compte perso, repos privés)

| Fonction | Remplacement |
|---|---|
| Secret scanning, push protection | gitleaks dans `pr-checks` |
| Code scanning (CodeQL) | linters stricts de `just check` (ruff/mypy, golangci-lint, clippy) et audits de dépendances (cargo-deny…) |
| Push rulesets (chemins, tailles de fichiers) | revue |
| Merge queue | inutile en solo : squash sans branche à jour (voir plus haut) |
| Pages privé | docs publiques assumées, ou pas de Pages |
