# Plan: GitHub self-hosted runner on `spoke-ops` for WAF captcha ingest

**Status: plan only. Do not implement until the security review in this
document is accepted.** Written 2026-08-30. Context: the scheduled Playwright
worker (`tools/finder/headless_archive.py`,
`.github/workflows/ops-headless-archive.yml`) can crawl Cloudflare/JS landings
from GitHub-hosted `ubuntu-latest`, but NYU’s 2025-26 CDS is behind an AWS WAF
**visual captcha** keyed on egress IP. Datacenter Chromium never clears it.
`spoke-ops` is a Mac on the home LAN whose residential NAT is expected to pass.

This plan is the proposed shape for putting a GitHub Actions runner on that
Mac. It is **not** a license to register the runner or change `runs-on`.

## 1. Why this exists

NYU publishes CDS 2025-26 at a public DAM URL. CloudFront answers with
`x-amzn-waf-action: captcha` and a visual puzzle (“choose all the hats”). A
silent JS token (`aws-waf-token`) is not enough. Wayback CDX is empty; IA save
returns 520. College Transitions still ends at 2024-25. Cursor WebFetch from a
different egress can *render* the Factbook listing, which is how we know the
file is real — we still do not have bytes in `cds_documents`.

GitHub-hosted `ubuntu-latest` is another datacenter IP. Moving the same
Playwright job onto a house Mac is the unattended way to change the WAF
score without solving captchas in CI and without asking a person to download
files.

Cloudflare / Google Drive schools in `waf_blocked_urls.yaml` do **not** need
this. They should keep running on GitHub-hosted Chromium. Only the captcha
class (today: NYU) needs residential egress.

## 2. Why a GitHub runner, not Tailscale-to-Chrome

Two ways to get house-IP Chromium:

| | GitHub Actions runner on `spoke-ops` | Tailscale / SSH into a browser on `spoke-ops` |
|---|---|---|
| Unattended daily cron | Yes (`schedule:` already exists) | Needs a long-lived agent or a person |
| Inbound ports on the house | None. Runner **polls outbound** to `github.com` | CDP `:9222` or SSH must be reachable on the tailnet |
| Blast radius if abused | Job code runs as a local user on the Mac, with whatever that user can see on the LAN | Same, plus an open debug port if CDP is exposed |
| This cloud-agent VM | Cannot reach `spoke-ops` (no SSH config, no Tailscale CLI, no DNS) | Same. Anthony’s laptop/tailnet can; this pod cannot |

The runner is the simpler unattended shape **if** GitHub’s public-repo controls
are actually in place. Tailscale remains the fallback if the review says “do
not attach a runner to a public repo.”

**Constraint:** registration, launchd, and macOS user setup happen on
`spoke-ops` itself. A cloud agent cannot SSH there. Anthony (or a session
already on that Mac) has to do the host side.

## 3. What is already true in this repo

- `bolewood/collegedata-fyi` is a **public** org repo (MIT, forkable). Org
  login is `bolewood` (type: Organization).
- No `CODEOWNERS`. No GitHub Environment on the headless job. No
  `pull_request_target` in current workflows.
- CI (`ci.yml`) is `on: pull_request` and **explicitly** `runs-on: ubuntu-latest`.
- `ops-headless-archive.yml` is **only** `schedule` + `workflow_dispatch`
  (collaborators). That trigger set is the right one for a privileged job.
  It currently injects `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.
- Other ops workflows (`ops-extraction-worker.yml`, `ops-finder-probe.yml`,
  …) also use those secrets on `ubuntu-latest`. Comments already mention a
  future self-hosted runner for large Docling drains. Those jobs must **never**
  accidentally land on `spoke-ops`.
- GitHub’s own hardening doc: *“self-hosted runners should almost never be
  used for public repositories … because any user can open pull requests
  against the repository and compromise the environment.”*
  ([Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#hardening-for-self-hosted-runners))

This cloud environment could not read org Actions permissions, runner groups,
or the fork-PR approval policy (API 403). Those settings are **unknown** and
are go/no-go gates, not assumptions.

## 4. Attack model (this is the whole question)

A self-hosted runner is persistent hardware. A GitHub-hosted VM dies with the
job. If untrusted workflow YAML runs on `spoke-ops`, the attacker gets:

1. **Code execution** as the runner OS user (files, Keychain if that user is
   the daily-driver login, browser profiles, SSH keys, Tailscale, 1Password).
2. **Home LAN** — scan printers, NAS, other Macs, IoT, router admin. The
   runner’s “network path” is the house, not a throwaway GitHub datacenter.
3. **Persistence** — launchd, crontab, extra GitHub runners (Shai-Hulud-style
   rogue runners as C2 over `github.com`, which looks like normal Actions
   traffic).
4. **Secrets** — any job that *does* run on that host and is allowed secrets
   can exfiltrate `SUPABASE_SERVICE_ROLE_KEY` (production Postgres + Storage).
   Fork `pull_request` jobs do **not** get repo secrets by default. Compromise
   of the **host** still lets later *legitimate* jobs leak secrets (`ps`,
   disk, memory). GitHub calls this out explicitly: destroying the runner
   process after a job does not make a reused Mac ephemeral.

### 4.1 Fork pull request → `runs-on` matching

Classic public-repo failure:

1. Attacker forks the repo.
2. Adds `.github/workflows/pwn.yml` with
   `on: pull_request` and
   `runs-on: [self-hosted, macOS, spoke-ops, cds-headless]`
   (labels copied from the public workflow file).
3. Opens a PR. If fork-PR workflows run without a maintainer approval, GitHub
   schedules the job onto `spoke-ops`. Unique labels do **not** hide the
   runner; they are in the public YAML.

`pull_request` from a fork does not receive `SUPABASE_SERVICE_ROLE_KEY`. It
still gets host RCE. That is enough.

GitHub’s “approval for running fork pull request workflows” setting is the
human gate. **First-time-contributor-only is not enough:** once a typo-fix PR
merges, that account can later open a workflow PR that runs without approval.
The setting that matches a house Mac is **Require approval for all external
contributors**. GitHub still warns: if a maintainer then *approves* the
workflow run, untrusted code executes on your hardware. Approving “run
workflows” is not the same as merging the PR.

### 4.2 `pull_request_target` / `workflow_run`

Neither exists today. Introducing either, plus a self-hosted `runs-on`, is
how public-repo runners become secret-stealing, not just RCE. This plan
forbids both on any job that can land on `spoke-ops`.

### 4.3 Label squatting and org-wide runners

`runs-on: self-hosted` with no extra labels will match **any** self-hosted
runner attached to the repo or a sharing org group. CI must stay on
`ubuntu-latest`. The spoke-ops runner must use a **conjunction of labels**
that no other job uses. That only prevents *accidents* (extraction worker,
CI). It does not prevent a fork copying the labels.

If the runner is registered at **org** default group and “allow public
repositories” is on, every public repo in `bolewood` can target it.

### 4.4 Collaborator / stolen-token path

`workflow_dispatch` and `schedule` are collaborator-only. A leaked
`GITHUB_TOKEN` or a compromised GitHub user with write access can dispatch
the real workflow from a malicious **branch** unless the runner group is
pinned to `ops-headless-archive.yml@refs/heads/main`. Pinning is the
control that makes “only the workflow file on `main` may use this machine”
true. Without a runner group, any collaborator branch that copies the labels
can run on the Mac.

### 4.5 What this does *not* open

- No inbound port-forward of Chrome CDP to the internet or to this cloud VM.
- No Tailscale subnet router requirement.
- No change to production fetch from Vercel/Supabase Edge (those stay
  datacenter).

## 5. Proposed architecture (only if gates pass)

**Preferred: org runner group, not a repo-level runner.**

`bolewood` is an Organization, so runner groups exist as a product surface.
Custom groups beyond Default require **GitHub Team** (or above). Confirm the
org plan before choosing a path.

```
spoke-ops
  macOS user `gha-runner` (not Anthony’s login)
    actions/runner process (launchd, outbound to github.com only)
      registered to org group `spoke-ops-headless`
        repository access: collegedata-fyi only
        allow public repositories: required for this one repo, not “all”
        restricted_to_workflows: true
        selected_workflows:
          bolewood/collegedata-fyi/.github/workflows/ops-headless-archive.yml@refs/heads/main
```

Job shape after gates:

- Keep the daily Cloudflare/Drive pass on `ubuntu-latest` (current workflow,
  or a `archive-hosted` job).
- Add a **second** job `archive-residential` (or a separate workflow file)
  with `runs-on: [self-hosted, macOS, spoke-ops, cds-headless]`,
  `if:` so it only runs when `spoke-ops` is online / when the dispatch
  input asks for captcha-class schools, defaulting to `--only nyu` until the
  YAML worklist has a `needs_residential_ip` flag.
- Triggers stay `schedule` + `workflow_dispatch`. **Never** `pull_request`,
  `pull_request_target`, or `workflow_run`.
- `permissions: contents: read` stays. No `id-token: write`, no
  `contents: write`.
- Secrets: GitHub Environment `spoke-ops-headless` holding
  `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` (or a narrower ingest role).
  Environment protection: required reviewer **or** (weaker) no fork access,
  which Environments already default for forks. Cron jobs from `main` should
  not wait on a human every morning — so the Environment is for *binding
  secrets to this job*, not for a daily approval. The runner-group workflow
  pin is the execution gate; the Environment is defense-in-depth for secrets
  if some other job is mis-labeled.

**Do not** register a repository-level runner on the public repo if the org
can disable repository-level runners and use a group instead. Repo-level
runners are targetable by any workflow in that repo that matches labels,
including a fork-PR workflow file, unless GitHub’s fork-approval setting
holds. Runner-group `restricted_to_workflows` is the technical control;
fork approval is the human control. We want both.

### 5.1 If GitHub Team / custom groups are unavailable

**Do not attach a runner to the public repo.** Use one of:

1. **Private ops repo** (`bolewood/collegedata-ops`, not public). Register
   the runner there. Workflow on the private repo checks out
   `bolewood/collegedata-fyi@main` (pin SHA or `main`) and runs
   `headless_archive.py`. Secrets live only on the private repo. Public
   contributors cannot open a PR that GitHub will schedule onto the Mac.
2. **Tailscale fallback:** a launchd job on `spoke-ops` (not GitHub) runs the
   same Python on a cron, with secrets in the `gha-runner` keychain or a
   root-owned file mode `0600`. No GitHub job targeting. Heartbeat still
   posts to Supabase. This is operationally more home-grown but removes the
   public-repo runner class of bugs.

A repo-level runner on a public repo plus “approve first-time contributors
only” is **not** an accepted substitute.

### 5.2 Host hardening on `spoke-ops` (mandatory, even with groups)

- Dedicated unprivileged user `gha-runner`. Not an admin. Not the daily
  iCloud/login user. No sudo. No SSH keys that can reach other machines.
- Home directory contains the runner + Playwright browsers only. No
  checkout of other private repos, no `.env` with extra cloud keys.
- FileVault on. macOS firewall on. Screen lock. Prevent sleep
  (`caffeinate` / Energy settings) so the poll loop stays alive.
- Do not enable Remote Login / Screen Sharing for this user beyond whatever
  Anthony already uses to administer the box.
- Runner labels: `self-hosted`, `macOS`, `spoke-ops`, `cds-headless`. Never
  advertise a generic-only label set.
- Org setting: **disable repository-level self-hosted runners** so a future
  workflow cannot register a second runner from Actions itself (Shai-Hulud
  pattern).
- Optional VLAN / guest Wi-Fi for `spoke-ops` so a compromised job cannot
  talk to NAS or personal Macs. This is the real LAN mitigation; a dedicated
  OS user does not stop layer-2 scans.

### 5.3 Secrets blast radius

Today the headless job uses the **service role**. On a house Mac that is a
production-db-from-the-kitchen risk.

Follow-up (can ship after the runner, should not block NYU ingest if the
gates pass): a Supabase role that can insert `cds_documents` / Storage
objects and write `pipeline_station_heartbeat`, and cannot dump
`institution_directory` or rotate keys. Until then, treat a suspected
runner compromise as **rotate `SUPABASE_SERVICE_ROLE_KEY` immediately**.

## 6. Go / no-go gates (all required)

Implementation of YAML `runs-on` changes and runner registration waits until
every line is true:

1. Fable review of this plan is **go** or **go with the gates below** — not
   no-go.
2. Org Actions: **Require approval for all external contributors** on fork
   PR workflow runs (not first-time only).
3. Org Actions: repository-level self-hosted runners **disabled** (or
   documented why not, if GitHub plan cannot).
4. Custom runner group exists, **restricted to the single workflow file
   pinned at `refs/heads/main`**, repository allow-list is only
   `collegedata-fyi`, public-repo access is the minimum override.
5. If (4) is impossible (Free org / no extra groups): **private ops repo or
   local launchd**, not a public-repo runner.
6. `spoke-ops` uses a dedicated unprivileged user, not Anthony’s login.
7. `CODEOWNERS` covers `.github/workflows/` so workflow edits need a
   designated owner.
8. No job other than the captcha ingest uses the `spoke-ops` / `cds-headless`
   labels. CI and extraction stay `ubuntu-latest`.
9. The ingest workflow (or the residential job) **never** gains
   `pull_request`, `pull_request_target`, or `workflow_run`.

If Fable says no-go even with (2)–(9), stop. NYU stays `waf_captcha` on
hosted Chromium until a private-ops or launchd path is designed.

## 7. Implementation sequence (after gates only)

Work that is **docs/settings**, then **host**, then **YAML**. Do not reverse.

1. Anthony confirms GitHub org plan (Team vs Free) and sets gates 2–4 in the
   org UI. Agent cannot read those APIs with current credentials.
2. Anthony creates `gha-runner` on `spoke-ops`, installs
   [actions/runner](https://github.com/actions/runner) for macOS, registers
   into the group with the labels above, launchd keep-alive. Python 3.12 +
   Playwright Chromium as that user.
3. Agent (after 1–2): `CODEOWNERS`; GitHub Environment; split
   `ops-headless-archive.yml` hosted vs residential jobs; heartbeat already
   exists (`headless_archive`). Small unit tests stay on hosted CI.
4. Dispatch `--only nyu` against spoke-ops. Expect `inserted` for 2025-26 or
   a new failure mode (not `waf_captcha` from CloudFront).
5. Only then consider adding a YAML flag for other captcha schools. Do not
   move the whole 20-school crawl onto the house IP on day one (bandwidth,
   and no need).

This cloud agent still cannot complete step 2. It can do 3 only after 1–2
are confirmed in writing.

## 8. Incident response (write this down next to the runner)

If any untrusted workflow is suspected to have run on `spoke-ops`:

1. Offline the runner (GitHub UI Remove; stop launchd; delete the runner
   directory).
2. Rotate GitHub runner registration; review org runner list for extras.
3. Rotate `SUPABASE_SERVICE_ROLE_KEY` and anything in that user’s keychain.
4. Assume LAN credentials touched until proven otherwise (router, NAS).
5. Reimage or at least new user + new runner dir. Do not “just reinstall
   the runner binary” on a dirty home directory.

## 9. Explicit non-goals

- No captcha-solving service, 2captcha, or “click the hats” automation.
- No exposing Chrome remote debugging on Tailscale as the primary design.
- No moving `ops-extraction-worker` onto `spoke-ops` in this change (Docling
  + service role + house Mac is a larger discussion).
- No applying migrations from this branch. No asking Anthony to download
  the NYU PDF by hand.

## 10. Questions for the security review

1. With gates 2–9, is an org-group runner on a **home Mac** attached to a
   **public** repo acceptable, or is the private-ops / launchd path the only
   responsible option?
2. Does `restricted_to_workflows` pinned at
   `…/ops-headless-archive.yml@refs/heads/main` actually refuse a fork PR
   whose workflow file has the same path and the spoke-ops labels? Call out
   any GitHub semantics we are wrong about.
3. Is injecting the **service role** onto that Mac an unacceptable
   concentration of risk even if execution is gated?
4. Residual LAN risk: is a dedicated OS user enough, or is “no runner on a
   machine that can see the rest of the house” a hard requirement?
5. Any additional org/repo settings this plan missed (Actions allowed
   actions list, SHA-pinning actions, `GITHUB_TOKEN` permissions, disable
   Actions on forks, etc.)?
