# ADR 0005: Repository lives on the `bolewood` GitHub org

**Date:** 2026-04-11
**Status:** Accepted

## Context

The repository could live on the maintainer's personal GitHub account (`santhonys`) or on the `bolewood` organization, which corresponds to [Bolewood Group, LLC](https://bolewood.com/). Neither namespace has meaningful stars, track record, or public reputation at the time of this decision.

## Decision

Host the repository at `github.com/bolewood/collegedata-fyi`.

## Why

The track-record question is a non-issue — nobody evaluating a library checks the parent namespace's star count before deciding whether to use it. What matters is the repo itself: README quality, commit activity, issue response times, and whether the code does what it says.

The decision comes down to what shape the project wants to be in five years, not where it's most comfortable this week.

An org signals "project"; a personal account signals "experiment." Contributors are more comfortable opening PRs against an org because they're participating in a project rather than intruding on someone's personal workspace. That matters a lot for the community-cleanup-tool story V1's architecture is designed around.

Orgs also let maintainers be added cleanly. If a contributor turns into a regular (e.g., the author of the first community cleaner), giving them commit access in an org is frictionless. Doing the same on a personal account always feels like letting someone into your house.

Finally, the canonical citation URL becomes `github.com/bolewood/collegedata-fyi` forever. Transferring later is possible and non-destructive, but old static links (HN threads, Wayback captures) won't follow redirects. Picking the right home on day one is cheap; migrating after launch is fine but annoying.

## Trade-offs accepted

- Personal commit activity does not count toward the maintainer's individual GitHub contribution graph by default. Acceptable and solvable via GitHub's contribution settings.
- The org has no prior track record, so "github.com/bolewood/..." carries no implicit credibility. Also true of the personal account, so this is a wash.
