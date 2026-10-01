#!/usr/bin/env bash
# Configure un repo d'app selon les conventions communes (ADR 0004,
# docs/release.md). Idempotent : peut être relancé sans risque.
#
#   - merge : squash uniquement, titre de PR = titre du commit, description =
#     corps du commit (porte le « BREAKING CHANGE: »), branche supprimée ;
#   - label no-deploy ;
#   - rulesets « main » (PR obligatoire, squash, checks requis, pas de
#     force-push) et « release-tags » (tags v* réservés au bot), avec la
#     GitHub App de release comme seul acteur qui contourne ;
#   - secrets RELEASE_APP_ID / RELEASE_APP_PRIVATE_KEY si --key est fourni.
#
# Prérequis : gh authentifié avec un compte admin du repo, jq. L'App doit
# être installée sur le repo (le plus simple : installation « All
# repositories », une fois pour toutes).
#
# Usage :
#   scripts/setup-repo.sh lduf/mon-app [--key ~/release-bot.pem]
#                         [--check "pr-checks / checks"]... [--app-id 5153118]
set -euo pipefail

APP_ID=5153118
KEY=""
CHECKS=()
REPO=""

usage() { sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --key) KEY="$2"; shift 2 ;;
    --check) CHECKS+=("$2"); shift 2 ;;
    --app-id) APP_ID="$2"; shift 2 ;;
    -h|--help) usage ;;
    -*) echo "Option inconnue : $1" >&2; usage 1 ;;
    *) REPO="$1"; shift ;;
  esac
done
[ -n "$REPO" ] || usage 1
[ ${#CHECKS[@]} -gt 0 ] || CHECKS=("pr-checks / checks")

HERE="$(cd "$(dirname "$0")/.." && pwd)"
GITHUB_ACTIONS_APP_ID=15368  # les checks requis doivent venir de GitHub Actions

echo "==> $REPO : réglages de merge"
gh api -X PATCH "repos/$REPO" --silent \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -f squash_merge_commit_title=PR_TITLE \
  -f squash_merge_commit_message=PR_BODY \
  -F delete_branch_on_merge=true

echo "==> $REPO : label no-deploy"
if gh api "repos/$REPO/labels/no-deploy" --silent 2>/dev/null; then
  gh api -X PATCH "repos/$REPO/labels/no-deploy" --silent \
    -f color=d93f0b -f description="Release sans déploiement (voir docs/release.md)"
else
  gh api -X POST "repos/$REPO/labels" --silent -f name=no-deploy \
    -f color=d93f0b -f description="Release sans déploiement (voir docs/release.md)"
fi

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
upsert_ruleset "$HERE/rulesets/release-tags.json"

if [ -n "$KEY" ]; then
  echo "==> $REPO : secrets de la GitHub App"
  gh secret set RELEASE_APP_ID --repo "$REPO" --body "$APP_ID"
  gh secret set RELEASE_APP_PRIVATE_KEY --repo "$REPO" < "$KEY"
fi

echo "OK. Vérifier que l'App de release est installée sur $REPO."
