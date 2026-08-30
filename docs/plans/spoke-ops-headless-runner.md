# Plan: GitHub self-hosted runner on `spoke-ops` for WAF captcha ingest

**Status: reviewed. Do not implement until the gates in §6 are verified.**
Written 2026-08-30. Security review by Fable5 the same day (full text in
§11). Context: the scheduled Playwright worker
(`tools/finder/headless_archive.py`,
`.github/workflows/ops-headless-archive.yml`) can crawl Cloudflare/JS landings
from GitHub-hosted `ubuntu-latest`, but NYU’s 2025-26 CDS is behind an AWS WAF
**visual captcha** keyed on egress IP. Datacenter Chromium never clears it.
`spoke-ops` is a Mac on the home LAN whose residential NAT is expected to pass.

This document is **not** a license to register a runner or change `runs-on`.

## Fable5 verdict (2026-08-30)

**Go with mandatory gates — but not on the originally preferred path.**

- **Primary path:** private ops repo `bolewood/collegedata-ops`. Register the
  runner there. Public contributors have no PR surface that GitHub can
  schedule onto the Mac.
- **Acceptable second path:** org runner group with
  `restricted_to_workflows` pinned to
  `ops-headless-archive.yml@refs/heads/main`, plus a `main` branch ruleset
  (CODEOWNERS without a ruleset is theater). Requires GitHub Team (unverified;
  API 403).
- **Hard no-go:** repository-level runner on the public repo, under any
  settings.
- **Hard no-go:** `SUPABASE_SERVICE_ROLE_KEY` (or any production write
  credential) on the Mac. Split: secretless fetch on `spoke-ops`, upload +
  heartbeat on `ubuntu-latest`.
- **Required, not optional:** network segmentation (VLAN / guest SSID, or
  documented `pf` block of RFC1918 for the runner user).
- **Launchd ranks third:** it forces the Supabase credential to live on disk.

Fable confirmed the plan’s runner-group pin semantics: a fork PR, even with
the same workflow path and labels, runs at `refs/pull/N/merge`, which does
not match `@refs/heads/main`, so the group refuses it. Unique labels only
prevent accidents; they do not stop a fork copying them.

## 1. Why this exists

NYU publishes CDS 2025-26 at a public DAM URL. CloudFront answers with
`x-amzn-waf-action: captcha` and a visual puzzle (“choose all the hats”). A
silent JS token (`aws-waf-token`) is not enough. Wayback CDX is empty; IA save
returns 520. College Transitions still ends at 2024-25. Cursor WebFetch from a
different egress can *render* the Factbook listing, which is how we know the
file is real — we still do not have bytes in `cds_documents`.

GitHub-hosted `ubuntu-latest` is another datacenter IP. Moving Playwright
fetch onto a house Mac is the unattended way to change the WAF score without
solving captchas in CI and without asking a person to download files.

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

Fable ranks a **private-repo GitHub runner** first, an org-group runner on
the public repo second (only with every gate), and a launchd cron third.
Tailscale/CDP is not the primary design.

**Constraint:** registration, launchd, and macOS user setup happen on
`spoke-ops` itself. A cloud agent cannot SSH there. Anthony (or a session
already on that Mac) has to do the host side.

## 3. What is already true in this repo

- `bolewood/collegedata-fyi` is a **public** org repo (MIT, forkable). Org
  login is `bolewood` (type: Organization).
- No `CODEOWNERS`. No branch ruleset on `main` is described in-repo. No
  GitHub Environment on the headless job. No `pull_request_target` or
  `workflow_run` in current workflows (Fable verified all six workflow files).
- CI (`ci.yml`) is `on: pull_request` and **explicitly** `runs-on: ubuntu-latest`.
- `ops-headless-archive.yml` is **only** `schedule` + `workflow_dispatch`
  (collaborators). That trigger set is the right one for a privileged job.
  It currently injects `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.
- Other ops workflows (`ops-extraction-worker.yml`, `ops-finder-probe.yml`,
  `ops-archive-seed-catchup.yml`, `ipeds-release-probe.yml`) also use those
  secrets on `ubuntu-latest`. Comments already mention a future self-hosted
  runner for large Docling drains. Those jobs must **never** land on
  `spoke-ops`.
- GitHub’s own hardening doc: *“self-hosted runners should almost never be
  used for public repositories … because any user can open pull requests
  against the repository and compromise the environment.”*
  ([Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#hardening-for-self-hosted-runners))

This cloud environment could not read org Actions permissions, runner groups,
or the fork-PR approval policy (API 403). Unverifiable settings are a **no**,
not an “unknown we can assume later.”

## 4. Attack model

A self-hosted runner is persistent hardware. A GitHub-hosted VM dies with the
job. If untrusted workflow YAML runs on `spoke-ops`, the attacker gets:

1. **Code execution** as the runner OS user (files, Keychain if that user is
   the daily-driver login, browser profiles, SSH keys, Tailscale, 1Password).
2. **Home LAN** — scan printers, NAS, other Macs, IoT, router admin. The
   runner’s “network path” is the house, not a throwaway GitHub datacenter.
   A dedicated OS user is a filesystem/keychain boundary, **not** a network
   boundary.
3. **Persistence** — launchd, crontab, extra GitHub runners (Shai-Hulud-style
   rogue runners as C2 over `github.com`, which looks like normal Actions
   traffic).
4. **Secrets** — any job that *does* run on that host and is allowed secrets
   can exfiltrate `SUPABASE_SERVICE_ROLE_KEY` (production Postgres + Storage).
   On github.com, fork `pull_request` jobs **never** receive repository
   secrets (there is no toggle that changes this for a public repo). Host
   compromise still lets later *legitimate* jobs leak secrets (`ps`, disk,
   memory). GitHub calls this out explicitly: destroying the runner process
   after a job does not make a reused Mac ephemeral.
5. **Browser-driven host compromise (no GitHub bug required).** The job’s
   purpose is to point Chromium at school-controlled pages. A renderer /
   sandbox-escape chain compromises the Mac with zero GitHub involvement.
   This is why production write credentials must not live on that host.

### 4.1 Fork pull request → `runs-on` matching

Classic public-repo failure:

1. Attacker forks the repo.
2. Adds `.github/workflows/pwn.yml` with
   `on: pull_request` and
   `runs-on: [self-hosted, macOS, spoke-ops, cds-headless]`
   (labels copied from the public workflow file).
3. Opens a PR. If fork-PR workflows run without a maintainer approval, GitHub
   schedules the job onto `spoke-ops`. Unique labels do **not** hide the
   runner; they are in the public YAML. They only prevent *accidents* (CI or
   the extraction worker landing on the Mac).

`pull_request` from a fork does not receive `SUPABASE_SERVICE_ROLE_KEY`. It
still gets host RCE. That is enough.

GitHub’s “approval for running fork pull request workflows” setting is a
human gate. **First-time-contributor-only is not enough:** once a typo-fix PR
merges, that account can later open a workflow PR that runs without approval
(documented against `actions/runner-images`). The setting that matches a
house Mac is **Require approval for all outside collaborators**.

Fable: if the org-group pin is in place, an *approved* malicious fork run
still does **not** land on the Mac (wrong ref). The dangerous human action
shifts to **merging a workflow change to `main`**. Approving “run workflows”
and merging YAML are different buttons; both need to stay hard.

### 4.2 `pull_request_target` / `workflow_run`

Neither exists today. Introducing either, plus a self-hosted `runs-on`, is
how public-repo runners become secret-stealing, not just RCE. This plan
forbids both on any job that can land on `spoke-ops`.

### 4.3 Label squatting and org-wide runners

`runs-on: self-hosted` with no extra labels will match **any** self-hosted
runner attached to the repo or a sharing org group. CI must stay on
`ubuntu-latest`. The spoke-ops runner must use a **conjunction of labels**
that no other job uses. That only prevents accidents. It does not prevent a
fork copying the labels.

If the runner is registered at **org** default group and “allow public
repositories” is on, every public repo in `bolewood` can target it.

### 4.4 Collaborator / stolen-token path

`workflow_dispatch` and `schedule` are collaborator-only. A leaked token with
write access can dispatch the real workflow from a malicious **branch**
unless the runner group is pinned to
`ops-headless-archive.yml@refs/heads/main`.

That pin is only as strong as **write protection on `main`**. CODEOWNERS
without a branch ruleset (required PRs, required reviews, code-owner
approval, no force push, no bypass actors) is theater: a stolen collaborator
token pushes a modified workflow to `main` and the next 08:00 cron runs it
on the Mac.

### 4.5 What this does *not* open

- No inbound port-forward of Chrome CDP to the internet or to this cloud VM.
- No Tailscale subnet router requirement.
- No change to production fetch from Vercel/Supabase Edge (those stay
  datacenter).

## 5. Architecture after review

### 5.1 Primary: private ops repo

```
bolewood/collegedata-ops   (private, forking disabled, no outside collaborators)
  workflow: schedule + workflow_dispatch only
    job fetch (spoke-ops, ephemeral runner, NO secrets)
      checkout bolewood/collegedata-fyi@main (or pinned SHA)
      Playwright fetch NYU (and later captcha-class) bytes
      upload-artifact
    job commit (ubuntu-latest, needs: fetch)
      SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY live only here
      validate artifact, upload to Storage, record cds_documents, heartbeat
```

`spoke-ops` registers a **repo-level** runner on the *private* repo (Fable:
repo-level is fine when the repo is private, forking is off, and there are
no outside collaborators). Labels still unique so a future second private
workflow cannot land by accident.

This eliminates the fork-PR class structurally. It works on any org plan.
Cost: one workflow file outside the main repo (drift: the private workflow
checks out public tooling at `main`). Heartbeats still post to Supabase.

### 5.2 Second: org runner group on the public repo

Only if Anthony confirms **GitHub Team** (or above) with evidence, wants
single-repo ergonomics, and every gate in §6 is verified (screenshots or
API — not “we think it’s on”).

```
spoke-ops
  macOS user `gha-runner` (not Anthony’s login)
    actions/runner --ephemeral (or JIT), outbound to github.com only
      registered to org group `spoke-ops-headless`
        repository access: collegedata-fyi only
        allows_public_repositories: the minimum override for this one public repo
        restricted_to_workflows: true
        selected_workflows:
          bolewood/collegedata-fyi/.github/workflows/ops-headless-archive.yml@refs/heads/main
```

Job shape:

- Keep the daily Cloudflare/Drive pass on `ubuntu-latest`.
- Residential job stays **inline** in that workflow file (Fable: runner
  groups only grant jobs *directly defined* in the selected workflow;
  `uses:` reusable workflows fail closed and will surprise later).
- Split still applies: Mac job secretless + artifact; hosted job has
  secrets.
- Triggers stay `schedule` + `workflow_dispatch`. **Never** `pull_request`,
  `pull_request_target`, or `workflow_run`.
- `permissions: contents: read`. No `id-token: write`, no `contents: write`.
- A GitHub Environment does **not** replace the no-secrets-on-Mac rule.
  Fork PRs never get secrets anyway. If used, the useful knob is a
  deployment-branch policy restricted to `main`, and only after the
  repo-level service-role secret is no longer readable by this job.

A repository-level runner on the **public** repo is **not** an accepted
substitute, including with “approve all external contributors.”

### 5.3 Third: launchd on `spoke-ops` (not GitHub)

Only if both GitHub paths are rejected. A launchd cron runs the same Python.
Fable ranks this below both GitHub paths because the Supabase credential
then lives permanently on disk/keychain, with no hosted job to hand off to.
Loses dispatch, logs, and run history. Heartbeat can still post to Supabase.

### 5.4 Host hardening on `spoke-ops` (mandatory on every path)

- Dedicated unprivileged user `gha-runner`. Not an admin. Not the daily
  iCloud/login user. No sudo. No SSH keys. No `gh` auth, no PATs, no
  personal keychain.
- Home directory contains the runner + Playwright browsers only. No extra
  `.env`.
- Register with `--ephemeral` (or JIT) so each job gets a fresh registration
  and work directory. Runner auto-update on.
- FileVault on. macOS firewall on. Screen lock. Prevent sleep
  (`caffeinate` / Energy settings) so the poll loop stays alive.
- Do not enable Remote Login / Screen Sharing for this user beyond whatever
  Anthony already uses to administer the box.
- Labels: `self-hosted`, `macOS`, `spoke-ops`, `cds-headless`. Never
  advertise a generic-only label set.
- **Network segmentation is required:** VLAN or guest SSID that cannot reach
  NAS, personal Macs, or router admin. Documented minimum if VLAN is
  impossible: `pf` rules blocking RFC1918/link-local egress for
  `gha-runner`, with residual layer-2 exposure accepted in writing.
- Org setting (public-repo path): **disable repository-level self-hosted
  runners** so a workflow cannot register a second runner from Actions
  itself (Shai-Hulud pattern).
- Supply chain for anything that executes on the Mac: third-party actions
  pinned to full SHAs; `requirements-headless.txt` installed with
  `--require-hashes`.

### 5.5 Secrets: split the pipeline before the first credentialed run

Do **not** ship the runner with the service role “and tighten later.”

1. Mac job: Playwright fetch, write files, `actions/upload-artifact`. No
   `SUPABASE_*` env.
2. Hosted job `needs:` the Mac job: validate bytes, call existing upload /
   record path, heartbeat.

Until that split exists, there is no credentialed upload path from
`spoke-ops`. First dispatch is `--only nyu` with dry-run / artifact-only
semantics.

A narrower Supabase ingest role remains a good hardening for the *hosted*
job. It is not a substitute for keeping write credentials off the Mac.

## 6. Go / no-go gates (all required)

YAML `runs-on` changes and runner registration wait until these are true.

1. **Path decision.** Anthony picks private ops repo (default) vs org-group.
   Org-group requires confirmed GitHub Team (or above) with evidence.
2. **No production write credentials on the self-hosted job.** Fetch /
   commit split landed and reviewed.
3. **If org-group path:** group restricted to exactly
   `bolewood/collegedata-fyi/.github/workflows/ops-headless-archive.yml@refs/heads/main`,
   repository allow-list = `collegedata-fyi` only, public-repo access is the
   minimum override. Verified with screenshot or API.
4. **If org-group path:** ruleset on `main` — require PRs, required review,
   code-owner review, `CODEOWNERS` covering `.github/workflows/**`, block
   force pushes, no bypass actors (or bypass restricted to Anthony and
   audited).
5. **Org Actions:** “Require approval for all outside collaborators”;
   disable repository-level self-hosted runner registration if the plan
   allows; default `GITHUB_TOKEN` read-only org-wide; “Allow GitHub Actions
   to create and approve pull requests” off.
6. **Host:** ephemeral runner, dedicated non-admin user, FileVault,
   firewall, no extra remotes, per §5.4.
7. **Network segmentation** per §5.4 (required).
8. **Workflow discipline:** `schedule` + `workflow_dispatch` only; residential
   job inline; `permissions: contents: read`; labels used by exactly one
   job; CI and extraction stay `ubuntu-latest`.
9. **Supply-chain pinning** for Mac-executed actions and pip hashes.
10. **Monitoring:** §8 runbook next to the machine; periodic hosted audit
    that lists org/private-repo runners and (if used) the group’s
    `selected_workflows` and fails on drift.

If the org is on Free and Anthony declines the private ops repo: **no
runner.** NYU stays `waf_captcha` on hosted Chromium.

## 7. Implementation sequence (after gates only)

Docs/settings, then host, then YAML. Do not reverse.

1. Anthony confirms org plan and picks §5.1 vs §5.2. Settings gates verified
   with evidence. Agent cannot read those APIs with current credentials.
2. Split `headless_archive.py` into secretless fetch and hosted commit
   (public repo). Private-ops workflow (or org-group residential job) uses
   that split. No `runs-on: self-hosted` until the split exists.
3. Anthony creates `gha-runner` on `spoke-ops`, VLAN/guest SSID, installs
   [actions/runner](https://github.com/actions/runner) for macOS
   `--ephemeral`, registers to the private repo **or** the restricted org
   group, launchd keep-alive. Python 3.12 + Playwright Chromium as that
   user.
4. First dispatch `--only nyu` artifact-only / dry-run. Expect bytes, not
   `waf_captcha`.
5. Then enable the hosted commit job. Then consider other captcha schools.
   Do not move the whole 20-school crawl onto the house IP on day one.

This cloud agent cannot complete step 3. It can do 2 only after 1 is
confirmed in writing.

## 8. Incident response (write this down next to the runner)

If any untrusted workflow is suspected to have run on `spoke-ops`:

1. Offline the runner (GitHub UI Remove; stop launchd; delete the runner
   directory).
2. Rotate GitHub runner registration; review org and private-repo runner
   lists for extras.
3. Rotate `SUPABASE_SERVICE_ROLE_KEY` if it ever lived on that host, plus
   anything in that user’s keychain.
4. Assume LAN credentials touched until proven otherwise (router, NAS).
5. Reimage or at least new user + new runner dir. Do not “just reinstall
   the runner binary” on a dirty home directory.

Treat any unexpected job queued against the spoke-ops labels as an incident.

## 9. Explicit non-goals

- No captcha-solving service, 2captcha, or “click the hats” automation.
- No exposing Chrome remote debugging on Tailscale as the primary design.
- No moving `ops-extraction-worker` onto `spoke-ops` in this change (Docling
  + service role + house Mac is a larger discussion).
- No applying migrations from this branch. No asking Anthony to download
  the NYU PDF by hand.
- No repository-level runner on `bolewood/collegedata-fyi`.
- No secrets on the self-hosted job.
- No `runs-on` change before the gates are verifiably true.

## 10. Residual risk (accepted if we proceed)

Even with every gate:

- Stolen **org-owner** token can rewrite groups, rulesets, and secrets.
  Compensate with passkeys/2FA and the drift audit (detection, not
  prevention).
- Stolen **collaborator write** token, with the ruleset: cannot push to
  `main`; can dispatch the legitimate workflow from `main` (trusted code —
  nuisance). Without the ruleset, game over.
- Merging a workflow change to `main` is the last human line of defense on
  the org-group path. Review `.github/workflows/` diffs; nothing automates
  that away.
- Chromium compromise while crawling is inherent to the mission. Gates 2, 6,
  and 7 bound blast radius (no secrets, unprivileged ephemeral user,
  segmented network).
- A GitHub enforcement bug in the runner-group pin would expose the Mac on
  the org-group path. Private ops repo does not depend on that check.
- Even on a VLAN, the house is still a residential egress node (spam, C2
  relay) until noticed.

## 11. Fable5 security review (verbatim, 2026-08-30)

Reviewed against this plan (pre-revision), all six files under
`.github/workflows/`, GitHub’s security hardening guidance and runner-group
documentation, plus known fork-PR / rogue-runner failure modes.

### Verdict

Go with mandatory gates — but not on the plan's preferred path. The private
ops repo (original §5.1 option 1) should be the primary design, not the
fallback; the public-repo org-group path is acceptable only if every gate
below is verified in writing; a repo-level runner on the public repo is a
hard no-go under any settings; and the service-role key must not land on
the Mac at all, which the first draft deferred as a follow-up.

### Risk summary for a home Mac on a public repo

GitHub's own guidance is blunt: self-hosted runners should almost never be
attached to public repositories, because anyone on the internet can fork
the repo and open a pull request that executes their code on your hardware.
GitHub-hosted runners are throwaway VMs; `spoke-ops` is a persistent machine
in Anthony's house.

**(a) GitHub scheduling untrusted jobs onto the Mac.** This is the headline
risk and it is real. The default failure mode: an attacker forks
`collegedata-fyi`, adds a workflow with
`runs-on: [self-hosted, macOS, spoke-ops, cds-headless]` (the labels are
public), and opens a PR. With a plain repo-level runner, the only thing
standing between that PR and code execution in the house is GitHub's
fork-approval setting. This exact path was used against
`actions/runner-images`: the attacker fixed a typo to earn the contributor
badge, after which fork workflows ran without approval. This risk **can**
be closed by an org runner group with `restricted_to_workflows` pinned to
`ops-headless-archive.yml@refs/heads/main`. With that pin and write access
to `main` protected, GitHub will not schedule untrusted code onto the Mac
even if a malicious fork run is approved (wrong ref → hosted runner, not
the Mac).

**(b) Secrets on the Mac.** Fork `pull_request` runs never receive repository
secrets on github.com, so the fork path is RCE-only. The secrets risk is
different: any legitimate job that runs on the Mac carries
`SUPABASE_SERVICE_ROLE_KEY` in its process environment, and the Mac is
persistent. If the host is ever compromised — by a GitHub-side failure, or
more plausibly by pointing Chromium at arbitrary school-controlled pages —
every subsequent scheduled run hands the attacker production Postgres and
Storage. No GitHub setting mitigates this. The only real fix is to not put
the key on the Mac.

**(c) LAN lateral movement.** A compromised runner's network position is the
house. A dedicated macOS user does nothing here. Network segmentation
(VLAN/guest SSID, or `pf` rules blocking RFC1918 egress for the runner
user) is the only control that actually addresses this risk.

### What the first draft got right

The attack model was honest. The runner-group pin semantics match GitHub's
docs (full `owner/repo/path@ref`; only jobs directly defined in the
selected workflow qualify). “All outside collaborators,” not first-time
only, is correct. Trigger discipline (`schedule` + `workflow_dispatch`, ban
`pull_request_target` / `workflow_run`) is right. Refusing
repo-level-plus-approval-setting is right. Host hardening, IR runbook, and
keeping Cloudflare/Drive on hosted runners are sound.

### What the first draft got wrong

1. The `refs/heads/main` pin is only as strong as write protection on
   `main`. CODEOWNERS without a branch ruleset is theater.
2. A GitHub Environment, as described, is mostly theater while the service
   role remains a repository secret consumed by five other workflows.
3. Deferring scoped credentials until after the runner ships is the wrong
   order. Browser compromise needs no GitHub bug.
4. “Fork PRs do not get repo secrets *by default*” is imprecise: they never
   do on github.com for a public repo.
5. Reusable-workflow caveat unstated: converting the residential job to
   `uses:` would lose runner-group access (fail-safe, but surprising).
6. Unique labels prevent accidents only.
7. VLAN listed as optional; it is the LAN control.

### Mandatory gates (Fable order)

1. Path decision first. Default to the private ops repo. Public-repo
   org-group only if Team (or above) is confirmed and gates 3–5 are
   verified with evidence. Unverifiable = no.
2. No production write credentials on the self-hosted job. Mac fetches and
   uploads an artifact; `ubuntu-latest` commits to Supabase.
3. If public-repo path: org runner group pin as above.
4. If public-repo path: ruleset on `main`.
5. Org Actions: all-outside-collaborator approval; disable repo-level
   runner registration; read-only `GITHUB_TOKEN`; Actions cannot create or
   approve PRs.
6. `--ephemeral` (or JIT); dedicated non-admin user; no sudo / SSH / `gh` /
   PATs; FileVault; firewall.
7. Network segmentation required.
8. Workflow discipline as in §6.
9. SHA-pin actions; pip `--require-hashes`.
10. IR runbook + periodic runner-inventory audit.

### Recommended path

Private ops repo, promoted from fallback to primary. Org-group is
acceptable second if Team is confirmed and every gate is verified.
Launchd third. Repository-level runner on the public repo is a no-go
regardless of settings.

### Implement / do not implement

Implement only after: (1) path decision, (2) settings/ruleset gates with
evidence, (3) fetch/commit split, (4) host setup, (5) first dispatch
`--only nyu` before any credentialed upload path exists.

Do not implement: any repo-level runner on the public repo; any secrets on
the self-hosted job; any `runs-on` change before the gates are verifiably
true. If the org is on Free and the private ops repo is declined, no
runner.
