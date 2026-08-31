# Inventory QR — Project Governance

## Source of truth

- GitHub Issues: atomic actionable work.
- GitHub Projects: roadmap/status/priority/iteration tracking when configured.
- Repository `/docs`: product charter, roadmap, architecture, ADRs, phase reports, pilot evidence, compliance mapping and operational runbooks.
- Pull requests: reviewed code/documentation changes linked to Issues.

Do not maintain a second independent task list once an item exists in GitHub.

## Work item lifecycle

Recommended status flow:

`Backlog → Ready → In Progress → Review → Pilot Validation → Done`

`Blocked` can be used from any active state when progress depends on another action.

## Definition of Done

An issue is not Done merely because code was written.

Where applicable, Done requires:

1. acceptance criteria passed;
2. relevant automated tests passed;
3. relevant manual/smoke tests passed;
4. migration/data validation completed;
5. security and tenant-isolation impact checked;
6. documentation updated;
7. pilot validation completed for workflow-changing features;
8. no unresolved P0 defect introduced by the change;
9. linked PR merged or documented outcome completed.

## Priority

- `P0` — security/data-loss/tenant-isolation/release-blocking issue.
- `P1` — required for current phase gate or major pilot workflow.
- `P2` — important but can move within roadmap.
- `P3` — optional, optimization or post-V1 candidate.

## Planning cadence

### Weekly review

Once per week:

- review active iteration;
- check overdue work;
- review blocked items and required next actions;
- review new/high/critical risks;
- check phase-gate health;
- triage pilot observations and bugs.

### Iterations

Use approximately two-week delivery iterations after the engineering-safety foundation exists.

Do not plan 100% of available capacity. Keep room for real pilot bugs and operational incidents.

### Monthly roadmap review

Review actual progress, dependencies, pilot findings, risks and commercial V1 confidence. Reforecast instead of silently allowing dates to become stale.

## Pilot feedback lifecycle

A real-organization request is not automatically a product requirement.

Use:

`Observation → Evidence → Problem → Hypothesis → Issue → Implementation → Test → Pilot validation → Keep / Change / Revert`

Classify findings as:

- bug;
- usability;
- process problem;
- feature request;
- data issue;
- security/control issue;
- organization-specific request.

Prefer configurable/general solutions over hard-coded rules for one organization.

## Bug rule

`Bug → GitHub Issue → Regression test → Fix → Review → Pilot validation if relevant → Release`

Every significant fixed production/pilot bug should become a regression test when technically reasonable.

## CODEX delivery contract

CODEX implementation work should start from an approved issue/specification.

Every completed implementation task must report:

1. files changed;
2. database/migration changes;
3. business rules implemented;
4. tests executed and results;
5. security/data-integrity considerations;
6. documentation updated;
7. known limitations and risks;
8. remaining work.

CODEX must not silently redefine roadmap scope or acceptance criteria.

## Project-management agent role

The project-management agent is a control/analysis layer over the tracker, not an autonomous product owner.

Recommended checks:

- overdue items;
- stale blocked issues;
- P0/P1 aging;
- missing acceptance evidence;
- PRs without linked issues;
- migrations without validation/runbook evidence;
- pilot changes without validation outcome;
- architecture changes without ADR;
- changes in high/critical risks;
- phase-gate criteria not yet demonstrated;
- roadmap drift.

The agent may recommend reprioritization. Final priority, scope, risk acceptance and GO/NO-GO decisions remain with the Product Owner.

## Architecture Decision Records

Create an ADR for material decisions affecting:

- multi-tenancy;
- tenant isolation;
- database architecture;
- authentication/identity;
- API contracts;
- provider portability;
- storage;
- deployment;
- major lifecycle semantics;
- compliance/security model.

An ADR records context, decision, alternatives/trade-offs and consequences.

## Stage gates

Each major phase ends with a documented gate.

Minimum gate review:

- objective achieved;
- required deliverables present;
- acceptance criteria demonstrated;
- tests passed;
- data/migration validation completed where applicable;
- security impact reviewed;
- documentation updated;
- pilot validation completed where applicable;
- open P0/P1 issues reviewed;
- risks updated;
- GO / CONDITIONAL GO / NO-GO decision recorded.

## Release rules

- `v0.x` is pilot/beta software.
- `v1.0` requires explicit commercial release gate.
- Production releases should have release notes and a reproducible migration/deployment path.
- Working pilot data must never be treated as a disposable development environment.
