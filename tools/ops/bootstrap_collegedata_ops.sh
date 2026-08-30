#!/usr/bin/env bash
# Create private bolewood/collegedata-ops and push the bundle in
# ops/collegedata-ops/. Run from the collegedata-fyi repo root with a
# GitHub token that can create private repositories in the bolewood org.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/ops/collegedata-ops"
OWNER="${OPS_OWNER:-bolewood}"
REPO="${OPS_REPO:-collegedata-ops}"
FULL="$OWNER/$REPO"

if [[ ! -d "$SRC/.github/workflows" ]]; then
  echo "missing bundle at $SRC" >&2
  exit 1
fi

if ! command -v gh >/dev/null; then
  echo "gh CLI is required" >&2
  exit 1
fi

if gh repo view "$FULL" >/dev/null 2>&1; then
  echo "repo $FULL already exists; pushing bundle to origin main" >&2
else
  gh repo create "$FULL" --private \
    --description "Private residential-IP Playwright fetch for collegedata.fyi. Do not attach this runner to public repos." \
    --disable-wiki --disable-issues
fi

# Collaborator forks of a private repo are still a PR surface. Turn forking off.
gh api -X PATCH "repos/$FULL" \
  -F allow_forking=false \
  -F has_wiki=false \
  -F has_projects=false \
  -F has_issues=false \
  >/dev/null

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

rsync -a --exclude .git "$SRC/" "$TMP/"
chmod +x "$TMP/spoke-ops/run-loop.sh"
cd "$TMP"
git init -b main
git add .
git status
git commit -m "Initial private residential headless-archive workflow"
git remote add origin "https://github.com/${FULL}.git"
git push -u origin main

echo
echo "Created/updated https://github.com/${FULL}"
echo "Next:"
echo "  1. Add secrets SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (hosted jobs only)."
echo "  2. On spoke-ops, follow ops/collegedata-ops/README.md (dedicated user, VLAN, runner loop)."
echo "  3. Dispatch Residential headless archive with only=nyu."
