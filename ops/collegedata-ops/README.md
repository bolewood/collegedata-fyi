# collegedata-ops (private)

Private GitHub Actions repo for **residential-IP** Playwright fetch on the
home Mac `spoke-ops`. Public contributors cannot open a pull request that
GitHub will schedule onto that machine.

This directory is the source tree. It is **not** a live workflow in
`bolewood/collegedata-fyi`. Copy it to a **private** repository
`bolewood/collegedata-ops`.

The cloud agent that wrote this could not create that GitHub repo (org
create-repo API returned 403). From a machine whose `gh` token can create
private org repos:

```bash
bash tools/ops/bootstrap_collegedata_ops.sh
```

Then finish the host steps below. Do not register this runner on the
public repo.

## What runs where

| Job | Runner | Secrets |
|---|---|---|
| `plan-hosted` | GitHub-hosted `ubuntu-latest` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| `fetch-residential` | `spoke-ops` (`self-hosted,macOS,spoke-ops,cds-headless`) | **none** (job fails if the service role is present) |
| `commit-hosted` | GitHub-hosted `ubuntu-latest` | same as plan |

Default school is `nyu`. Cloudflare/Drive ingest stays on the public
`ops-headless-archive.yml` hosted job.

Until the fetch/commit split is on `main`, the workflow checks out
`cursor/nyu-cds-coverage-audit-339c`. After that PR merges, change the
default `collegedata_ref` in the workflow to `main`.

## GitHub repo settings (required)

1. Visibility: **private**. Forking: **off**.
2. Outside collaborators: none.
3. Actions → General: default `GITHUB_TOKEN` read-only; do not allow Actions
   to create or approve pull requests.
4. Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (same values as the
   public repo; they are only injected into hosted jobs).
5. Do not add a self-hosted runner to `bolewood/collegedata-fyi`.

## spoke-ops host (required)

The cloud agent cannot SSH to `spoke-ops`. Do this on the Mac.

1. Put the Mac on a VLAN or guest SSID that cannot reach NAS, personal
   machines, or router admin (or `pf` block RFC1918 for this user).
2. Create unprivileged user `gha-runner` (no admin, no sudo, no personal
   iCloud, no SSH keys to other hosts).
3. FileVault, firewall, prevent sleep.
4. As `gha-runner`, install the [Actions runner](https://github.com/actions/runner/releases)
   under `$HOME/actions-runner`.
5. Fine-grained PAT **only** for `bolewood/collegedata-ops`, Administration
   read/write (runner registration). Store it in
   `~/.config/collegedata-ops-runner.env` mode `600`:

   ```
   GITHUB_TOKEN=github_pat_...
   ```

6. Copy `spoke-ops/run-loop.sh` next to the runner (or keep this repo
   checked out). `chmod +x`. Launchd KeepAlive running that loop as
   `gha-runner` so an `--ephemeral` runner re-registers after each job.
7. Python 3.12 on PATH for that user (`actions/setup-python` can also
   install it).

Labels must be exactly: `self-hosted,macOS,spoke-ops,cds-headless`.

## First run

1. Confirm the runner is idle in the private repo’s Actions → Runners list.
2. Actions → **Residential headless archive** → Run workflow.
   - `only`: `nyu`
   - `collegedata_ref`: `cursor/nyu-cds-coverage-audit-339c` until merge
3. Expect the Mac job to write a PDF artifact and the hosted commit job to
   insert CDS 2025-26 (or `unchanged_verified` if a later run repeats).

## Incident

Remove the runner in the GitHub UI, stop launchd, delete the runner
directory, rotate the registration PAT. Rotate `SUPABASE_SERVICE_ROLE_KEY`
only if it ever appeared in a spoke-ops job log or env (it must not).
