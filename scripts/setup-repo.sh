#!/usr/bin/env bash
# Configure un repo d'app selon les conventions communes (ADR 0004,
# docs/release.md). Idempotent : peut être relancé sans risque.
#
#   - merge : squash uniquement, titre de PR = titre du commit, description =
#     corps du commit (porte le « BREAKING CHANGE: »), branche supprimée,
#     auto-merge permis, bouton « Update branch » affiché ; wiki et projets
#     désactivés ;
#   - Actions : GITHUB_TOKEN en lecture seule par défaut (chaque workflow
#     déclare ses permissions), pas d'approbation de PR par les workflows ;
#   - alertes Dependabot (les PR de mise à jour restent à Renovate) ;
#   - labels standard (labels.json : type, zone, bloqué, urgent, no-deploy) ;
#   - rulesets, avec la GitHub App de release comme seul acteur qui contourne :
#     « main » (PR obligatoire, squash, checks requis, conversations résolues,
#     pas de force-push ni de suppression), « branch-names »
#     (création de branche limitée aux préfixes conventionnels),
#     « linear-history » (aucun commit de merge sur aucune branche : on se met
#     à jour par rebase) et « release-tags » (tags v* réservés au bot) ;
#   - GitHub Pages publié par GitHub Actions (build_type workflow) si le repo
#     a un .github/workflows/pages.yml ;
#   - topic « ktisis » : le repo entre dans le périmètre de la réconciliation
#     hebdomadaire (workflow gouvernance, docs/gouvernance.md) ;
#   - variable RELEASE_APP_CLIENT_ID (identifiant public de l'App) et, si --key
#     est fourni, secret RELEASE_APP_PRIVATE_KEY ;
#   - avec --base-tag, tag de base vX.Y.Z (migration d'un repo qui a déjà des
#     versions : commitizen repart de ce tag au lieu de 0.1.0). Posé sur
#     --base-ref (sha, défaut : tête de la branche par défaut) ; rien si le tag
#     existe déjà au même commit, erreur s'il existe ailleurs.
#
# Prérequis : gh authentifié avec un compte admin du repo, jq. L'App doit
# être installée sur le repo (le plus simple : installation « All
# repositories », une fois pour toutes).
#
# Usage :
#   scripts/setup-repo.sh lduf/mon-app [--key ~/release-bot.pem]
#                         [--check "pr-checks / checks"]...
#                         [--base-tag v1.13.0 [--base-ref <sha>]]
#   Checks requis : ceux de --check ; sinon ceux du ruleset « main » existant
#   (une relance ne les écrase pas) ; sinon pr-checks / checks + ci / check.
#
# Identité de la GitHub App de release : variables d'environnement
# RELEASE_APP_ID (ID numérique, pour le bypass des rulesets) et
# RELEASE_APP_CLIENT_ID (pour le token des workflows), ou options --app-id /
# --client-id. Valeurs par défaut : l'App lduf-release-bot.
set -euo pipefail

APP_ID="${RELEASE_APP_ID:-5153118}"
CLIENT_ID="${RELEASE_APP_CLIENT_ID:-Iv23li1N00eylQ1llniH}"
KEY=""
BASE_TAG=""
BASE_REF=""
CHECKS=()
REPO=""

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --key) KEY="$2"; shift 2 ;;
    --check) CHECKS+=("$2"); shift 2 ;;
    --app-id) APP_ID="$2"; shift 2 ;;
    --client-id) CLIENT_ID="$2"; shift 2 ;;
    --base-tag) BASE_TAG="$2"; shift 2 ;;
    --base-ref) BASE_REF="$2"; shift 2 ;;
    -h|--help) usage ;;
    -*) echo "Option inconnue : $1" >&2; usage 1 ;;
    *) REPO="$1"; shift ;;
  esac
done
[ -n "$REPO" ] || usage 1
if [ -n "$BASE_TAG" ] && ! [[ "$BASE_TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "--base-tag attendu au format vX.Y.Z : $BASE_TAG" >&2; exit 1
fi

HERE="$(cd "$(dirname "$0")/.." && pwd)"
GITHUB_ACTIONS_APP_ID=15368  # les checks requis doivent venir de GitHub Actions

echo "==> $REPO : réglages de merge"
gh api -X PATCH "repos/$REPO" --silent \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -f squash_merge_commit_title=PR_TITLE \
  -f squash_merge_commit_message=PR_BODY \
  -F delete_branch_on_merge=true \
  -F allow_auto_merge=true \
  -F allow_update_branch=true \
  -F has_wiki=false \
  -F has_projects=false

echo "==> $REPO : permissions des workflows"
gh api -X PUT "repos/$REPO/actions/permissions/workflow" --silent \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=false

echo "==> $REPO : alertes Dependabot"
gh api -X PUT "repos/$REPO/vulnerability-alerts" --silent

echo "==> $REPO : labels standard (labels.json)"
# Crée ou met à jour les labels du standard ; les autres labels du repo
# restent en place (les supprimer les retirerait des issues et des PR).
while IFS= read -r label; do
  name=$(jq -r .name <<<"$label")
  enc=$(jq -rn --arg n "$name" '$n | @uri')
  if gh api "repos/$REPO/labels/$enc" --silent 2>/dev/null; then
    jq '{color, description}' <<<"$label" \
      | gh api -X PATCH "repos/$REPO/labels/$enc" --input - --silent
  else
    gh api -X POST "repos/$REPO/labels" --input - --silent <<<"$label"
  fi
done < <(jq -c '.[]' "$HERE/labels.json")

main_id=$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name == "main") | .id' | head -1)
if [ ${#CHECKS[@]} -eq 0 ] && [ -n "$main_id" ]; then
  mapfile -t CHECKS < <(gh api "repos/$REPO/rulesets/$main_id" --jq \
    '.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context')
fi
[ ${#CHECKS[@]} -gt 0 ] || CHECKS=("pr-checks / checks" "ci / check")
echo "==> $REPO : checks requis : $(IFS=,; echo "${CHECKS[*]}")"

checks_json=$(printf '%s\n' "${CHECKS[@]}" \
  | jq -R --argjson app "$GITHUB_ACTIONS_APP_ID" '{context: ., integration_id: $app}' \
  | jq -s .)

upsert_ruleset() {
  local file="$1" name body id
  body=$(jq --argjson app "$APP_ID" --argjson checks "$checks_json" '
      .bypass_actors |= map(.actor_id = $app)
      | .rules |= map(if .type == "required_status_checks"
                      then .parameters.required_status_checks = $checks else . end)' "$file")
  name=$(jq -r .name <<<"$body")
  id=$(gh api "repos/$REPO/rulesets" --jq ".[] | select(.name == \"$name\") | .id" | head -1)
  if [ -n "$id" ]; then
    echo "==> $REPO : ruleset « $name » mis à jour (#$id)"
    gh api -X PUT "repos/$REPO/rulesets/$id" --input - --silent <<<"$body"
  else
    echo "==> $REPO : ruleset « $name » créé"
    gh api -X POST "repos/$REPO/rulesets" --input - --silent <<<"$body"
  fi
}
upsert_ruleset "$HERE/rulesets/main.json"
upsert_ruleset "$HERE/rulesets/branch-names.json"
upsert_ruleset "$HERE/rulesets/linear-history.json"
upsert_ruleset "$HERE/rulesets/release-tags.json"

echo "==> $REPO : topic ktisis"
gh api "repos/$REPO/topics" --jq '{names: (.names + ["ktisis"] | unique)}' \
  | gh api -X PUT "repos/$REPO/topics" --input - --silent

if gh api "repos/$REPO/contents/.github/workflows/pages.yml" --silent 2>/dev/null; then
  echo "==> $REPO : GitHub Pages par GitHub Actions"
  # L'App doit avoir la permission « Pages: write » ; sans elle, on prévient
  # sans échouer : le reste de la configuration est déjà en place.
  if gh api "repos/$REPO/pages" --silent 2>/dev/null; then
    pages_cmd=(gh api -X PUT "repos/$REPO/pages" --silent -f build_type=workflow)
  else
    pages_cmd=(gh api -X POST "repos/$REPO/pages" --silent -f build_type=workflow)
  fi
  if ! "${pages_cmd[@]}"; then
    echo "::warning::Pages non configuré sur $REPO : donner « Pages: read and write » à l'App de release, puis relancer."
  fi
fi

echo "==> $REPO : variable RELEASE_APP_CLIENT_ID"
gh variable set RELEASE_APP_CLIENT_ID --repo "$REPO" --body "$CLIENT_ID"

if [ -n "$KEY" ]; then
  echo "==> $REPO : clé privée de la GitHub App"
  gh secret set RELEASE_APP_PRIVATE_KEY --repo "$REPO" < "$KEY"
fi

if [ -n "$BASE_TAG" ]; then
  if [ -z "$BASE_REF" ]; then
    branch=$(gh api "repos/$REPO" --jq .default_branch)
    BASE_REF=$(gh api "repos/$REPO/commits/$branch" --jq .sha)
  else
    BASE_REF=$(gh api "repos/$REPO/commits/$BASE_REF" --jq .sha)  # sha court ou branche -> sha complet
  fi
  # Sur un 404, gh api écrit quand même le corps d'erreur sur stdout : tester
  # l'existence d'abord, lire le sha ensuite.
  existing=""
  if gh api "repos/$REPO/git/ref/tags/$BASE_TAG" --silent 2>/dev/null; then
    existing=$(gh api "repos/$REPO/git/ref/tags/$BASE_TAG" --jq .object.sha)
  fi
  if [ -z "$existing" ]; then
    echo "==> $REPO : tag de base $BASE_TAG sur ${BASE_REF:0:7}"
    gh api -X POST "repos/$REPO/git/refs" --silent -f "ref=refs/tags/$BASE_TAG" -f "sha=$BASE_REF"
  elif [ "$existing" = "$BASE_REF" ]; then
    echo "==> $REPO : tag $BASE_TAG déjà en place"
  else
    echo "Tag $BASE_TAG déjà présent sur ${existing:0:7}, pas sur ${BASE_REF:0:7} : rien n'est modifié." >&2
    exit 1
  fi
fi

echo "OK. Vérifier que l'App de release est installée sur $REPO."
