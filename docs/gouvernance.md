# Standard Ktisis — gouvernance des repos

Règles de fonctionnement de tout repo `lduf` créé ou adopté par Ktisis
(décision : [ADR 0007](adr/0007-standard-ktisis-gouvernance-des-repos.md)).
Chaque règle dit **qui la fait respecter**. Une règle sans mécanisme n'est
qu'une recommandation, et le tableau le dit.

- **Appliquer** : workflow `setup-repo` (ou `scripts/setup-repo.sh`), idempotent.
  Le relancer remet au standard un repo qui a dérivé.
- **Réconcilier** : workflow `gouvernance`, chaque lundi. Il rejoue
  `setup-repo` sur tous les repos qui portent le topic `ktisis`. Un réglage
  changé à la main revient au standard ; un échec fait échouer le run
  (e-mail de GitHub). À la demande : `gh workflow run gouvernance.yml -R lduf/.github [-f repo=mon-app]`.
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

### Cycle de vie d'une PR

1. **Brouillon** à l'ouverture, tant que le travail avance.
2. **Ready for review** dès que la PR est prête à merger : CI verte sur le
   dernier commit, description complète, dépendances levées, aucune
   conversation ouverte. Un agent (Claude) passe **lui-même** sa PR en
   *Ready for review* à ce moment-là, sans attendre qu'on le lui demande. Il
   ne merge pas, sauf demande explicite.
3. **Merge** par Lucas (ou auto-merge) : squash.

### Dépendances entre PR

Une PR qui a besoin d'une autre le dit dans sa description, sur une ligne
à elle (hors commentaire HTML) :

```markdown
Dépend de : lduf/.github#11
Dépend de : #12
```

Formes acceptées : `Dépend de`, `Depends on`, `Bloqué par`, `Blocked by`,
suivies de `#N`, `owner/repo#N` ou de l'URL de la PR ou de l'issue.
`pr-checks / checks` échoue tant qu'une PR visée n'est pas **mergée** (ou
qu'une issue visée n'est pas fermée), et pose le label `blocked` : le merge
est impossible. Une PR visée fermée sans merge bloque aussi : retirer la
ligne si la dépendance n'a plus lieu d'être.

Le check ne se relance pas tout seul quand la dépendance est mergée :
*Re-run* du job, ou modifier la description. Un agent qui merge (ou voit
merger) une dépendance relance les PR qui l'attendaient. Pour lire une PR
d'un **autre repo privé**, le `ci.yml` passe `secrets: inherit` à pr-checks
(jeton de l'App de release) ; sans cela, seuls ce repo et les repos publics
sont lisibles.

## Labels

Les mêmes dans tous les repos ([`labels.json`](../labels.json)), créés par
`setup-repo` et maintenus par la réconciliation du lundi. Les autres labels
d'un repo ne sont pas supprimés.

| Famille | Labels | Posé par |
|---|---|---|
| Type | `type: feat`, `type: fix`, `type: perf`, `type: refactor`, `type: docs`, `type: test`, `type: build`, `type: ci`, `type: chore`, `type: style`, `type: revert` | PR : `pr-checks`, d'après le titre. Issue : le modèle d'issue, ou à la main |
| Cassant | `breaking` | `pr-checks`, titre avec `!` |
| Area | `area: back`, `area: front`, `area: api`, `area: auth`, `area: db`, `area: tests`, `area: deps`, `area: deploy`, `area: observability`, `area: ci`, `area: docs`, `area: template` | PR : `pr-checks`, d'après les fichiers modifiés (recalculé à chaque run). Issue : à la main |
| État | `blocked` | `pr-checks`, dépendance non levée |
| Priorité | `urgent` | à la main |
| Release | `no-deploy` | à la main ([release.md](release.md)) |

Sur les PR, `type:`, `area:`, `breaking` et `blocked` sont gérés par
`pr-checks` : un ajout à la main est écrasé au run suivant. Les autres
labels restent libres. Une issue ouverte par un agent porte au moins un
`type:` et une `area:`. Pour que `pr-checks` pose les labels, le `ci.yml`
lui donne `pull-requests: write` ; sinon, simple avertissement.

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

## README et licence des apps

Chaque app Ktisis a le même en-tête de README (généré par le template) :

| Ligne | Contenu | Mis à jour par |
|---|---|---|
| CI | badge du workflow `ci` | GitHub |
| Version | dernière version publiée, CHANGELOG, releases | la release (`release.yml`), entre les balises `<!-- ktisis:version -->` |
| Ktisis | version du template, contrat d'app, ce standard | `copier update` (PR de mise à jour du template) |
| Stack | langage, PostgreSQL, mode d'auth | `copier update` |
| Prod | domaine, image GHCR | `copier update` |
| Docs | site GitHub Pages | `copier update` |
| Licence | licence du code | `copier update` |

Le reste du README appartient à l'app. Ne pas modifier le tableau à la
main : la release et `copier update` le réécrivent.

Licence par défaut : **PolyForm Noncommercial 1.0.0**. Le code est lisible,
modifiable et redistribuable pour tout usage non commercial (personnel,
recherche, enseignement, associations, organismes publics) ; l'usage
commercial, par ou pour une entreprise, est interdit sans accord écrit. Ce
n'est pas une licence open source au sens de l'OSI. Alternatives au
moment de la création (`ktisis new --license`) : `AGPL-3.0-only` (open
source, copyleft fort), `MIT`, `none` (tous droits réservés).

## Hygiène du repo

- Wiki et Projects désactivés : la doc vit dans `docs/` (versionnée, revue en
  PR), le suivi dans les issues.
- Topic `ktisis` : marque le repo comme soumis au standard. La réconciliation
  hebdomadaire ne touche que ces repos : retirer le topic sort un repo du
  périmètre.
- Labels du standard ([plus haut](#labels)).

## Ce que GitHub Pro n'offre pas (compte perso, repos privés)

| Fonction | Remplacement |
|---|---|
| Secret scanning, push protection | gitleaks dans `pr-checks` |
| Code scanning (CodeQL) | linters stricts de `just check` (ruff/mypy, golangci-lint, clippy) et audits de dépendances (cargo-deny…) |
| Push rulesets (chemins, tailles de fichiers) | revue |
| Merge queue | inutile en solo : squash sans branche à jour (voir plus haut) |
| Pages privé | docs publiques assumées, ou pas de Pages |
