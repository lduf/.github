# 0004 — Release poussée directement sur `main` par la CI, sans PR de release

- Statut : Acceptée
- Date : 2026-10-01

## Contexte

Avec l'[ADR 0003](0003-commitizen-semver-conventional-commits.md), la version et
le CHANGELOG sont calculés par la CI. Il reste à décider **comment** ce résultat
atterrit sur `main`. Les outils courants (release-please, changesets) ouvrent
une « PR de release » à merger : c'est une étape manuelle de plus, et une PR
qui traîne en permanence. Lucas veut que **merger une PR suffise**.

## Décision

Après chaque push sur `main`, le workflow réutilisable `release.yml` (dans
`lduf/.github`) :

1. relit `main` à jour, calcule le bump depuis le dernier tag et s'arrête s'il
   n'y en a pas ;
2. pousse **directement sur `main`** un commit `chore(release): vX.Y.Z`
   (version + CHANGELOG), puis crée le tag `vX.Y.Z` ;
3. **dans le même job**, build et pousse l'image GHCR (`X.Y.Z`, `X.Y`,
   `sha-<court>`, plus `latest` en transition) ;
4. exécute l'étape de déploiement selon l'input `deploy_mode`, sauf si le lot
   est marqué `no-deploy`.

### Pièges et parades

| Piège | Parade |
|---|---|
| **Protection de `main`** : les humains ne doivent pas pouvoir pousser directement | Ruleset sur `main` (PR obligatoire, squash only, checks requis) et ruleset sur les tags `v*`. Seule une **GitHub App de release** est déclarée comme *bypass actor*. Le workflow obtient un token d'installation (`actions/create-github-app-token`). Les humains restent bloqués. |
| **Un push fait avec `GITHUB_TOKEN` ne déclenche aucun autre workflow** | Build et push de l'image dans le **même job** que le bump : on ne compte pas sur un workflow déclenché par le tag. |
| **Boucle** : le commit du bot déclenche à nouveau `push: main` | Garde `if: !startsWith(github.event.head_commit.message, 'chore(release):')`. De plus, `chore` ne bumpe jamais : même lancé, le job ne trouverait rien. |
| **Merges rapprochés** (3 ou 4 PR fusionnées à la suite) | `concurrency: { group: release-${{ github.repository }}, cancel-in-progress: false }` : les runs se suivent sans s'annuler. Chaque run relit `main` (`git fetch` + reset sur `origin/main`) avant de calculer. Un run qui trouve déjà tous les commits couverts par le tag précédent ne fait rien. Plusieurs merges peuvent donc donner **une seule release** qui les regroupe : c'est voulu. |
| **Course entre le push du bot et un nouveau merge** | Le push du commit de release est en fast-forward strict. S'il est rejeté parce que `main` a avancé, le job refait fetch, bump et push (nombre de tentatives borné). Le run suivant, en file grâce à `concurrency`, couvrira les commits restants. |

### `deploy_mode` et label `no-deploy`

- Input `deploy_mode` : `portainer-webhook` (défaut tant qu'Oikos n'est pas en
  service) | `oikos-pr` | `none`.
  - `portainer-webhook` : pousse `latest` et appelle le secret
    `PORTAINER_WEBHOOK_URL`.
  - `oikos-pr` : ouvre une PR sur `lduf/oikos` qui met à jour le tag et le
    **digest** de l'image, et copie `observability/`. Pas de `latest`.
- Label **`no-deploy`** sur une PR : la release a **quand même** lieu (version,
  CHANGELOG, tag, image `X.Y.Z`). Seule l'étape de déploiement est sautée.
  - Le workflow retrouve les PR d'origine des commits du lot
    (`GET /repos/{repo}/commits/{sha}/pulls`) et lit leurs labels.
  - Si **au moins une** PR du lot porte `no-deploy`, tout le lot est non
    déployé : l'image contient forcément son changement.
  - **Limite** : `no-deploy` veut dire « pas maintenant », pas « jamais ». La
    prochaine release déployée embarquera ce code, qui est sur `main`. Pour
    retenir une fonctionnalité durablement : feature flag, ou ne pas merger.
  - Pour déployer plus tard une version restée en `no-deploy` : `workflow_dispatch`
    avec la version en input (redéploie l'image existante, sans rebuild), ou
    attendre la release suivante.
  - Le nom `no-deploy` remplace `no-release` : la release a lieu, seul le
    déploiement est retenu.

## Conséquences

- Merger une PR suffit. La release suit en quelques minutes, uniquement si un
  commit le justifie.
- Il faut créer et installer une **GitHub App** (permissions `contents: write`,
  `metadata: read`, et `pull-requests: write` sur `lduf/oikos` pour
  `oikos-pr`). Ses identifiants sont stockés en secrets
  (Client ID en valeur par défaut du workflow, clé privée en secret
  `RELEASE_APP_PRIVATE_KEY`). C'est une action manuelle de
  Lucas, documentée en Phase 2.
- `main` contient des commits qui ne viennent pas d'une PR (ceux du bot). C'est
  attendu, et ils sont identifiables par leur préfixe et leur auteur.
- Les images ne sont publiées **que** sur une release : un merge de `docs` ou
  de `ci` ne produit ni image ni déploiement.

## Alternatives écartées

- **PR de release (release-please)** : une étape manuelle de plus, que Lucas a
  explicitement refusée.
- **PAT fine-grained** comme bypass : possible, mais lié à un compte humain,
  avec une expiration à gérer. On ne le garde qu'en repli si l'App pose
  problème.
- **Workflow de build déclenché par le tag** : il ne se déclenche pas avec
  `GITHUB_TOKEN`, et il dédouble la logique.
