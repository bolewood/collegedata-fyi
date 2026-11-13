#!/bin/bash
# Re-register an ephemeral GitHub Actions runner after each job.
# Runs as the unprivileged gha-runner user. The PAT in runner.env must
# be a fine-grained token for bolewood/collegedata-ops only, with
# Administration: Read and write (runner registration). Not a Supabase key.
set -euo pipefail

ROOT="${RUNNER_ROOT:-$HOME/actions-runner}"
ENV_FILE="${RUNNER_ENV:-$HOME/.config/collegedata-ops-runner.env}"
REPO_URL="${REPO_URL:-https://github.com/bolewood/collegedata-ops}"
LABELS="${RUNNER_LABELS:-self-hosted,macOS,spoke-ops,cds-headless}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing $ENV_FILE" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is not set in $ENV_FILE" >&2
  exit 1
fi

cd "$ROOT"

mint_token() {
  local attempt json
  for attempt in 1 2 3 4 5 6; do
    json="$(curl -fsS -X POST \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/bolewood/collegedata-ops/actions/runners/registration-token" \
      || true)"
    if TOKEN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$json" 2>/dev/null)" \
      && [[ -n "${TOKEN}" ]]; then
      return 0
    fi
    echo "registration-token mint failed (attempt ${attempt}); retrying" >&2
    sleep $((attempt * 5))
  done
  return 1
}

while true; do
  # Guest-Wi-Fi DNS blips leave a half-configured ephemeral runner. --replace
  # does not overwrite a local .runner; remove it before minting a new token.
  if [[ -f .runner ]]; then
    ./config.sh remove --unattended || true
    rm -f .runner .credentials .credentials_rsaparams
  fi
  if ! mint_token; then
    echo "could not mint a registration token; sleeping" >&2
    sleep 30
    continue
  fi
  ./config.sh --unattended --replace --ephemeral \
    --url "$REPO_URL" \
    --token "$TOKEN" \
    --labels "$LABELS" \
    --name "${RUNNER_NAME:-spoke-ops}"
  ./run.sh || true
  sleep 5
done
