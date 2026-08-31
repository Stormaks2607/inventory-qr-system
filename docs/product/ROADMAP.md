# Inventory QR — Commercial Product Roadmap

## Planning horizon

Target: move from the current internal pilot (`v0.x`) toward a commercially operable `v1.0` over approximately 12 months.

Dates are planning targets and must be reforecast from evidence at monthly roadmap reviews.

## Phase 0A — Current-state baseline

**Status:** completed / being documented

### Objective
Document the real pilot architecture, capabilities, data model and risks before further structural changes.

### Exit gate
- real stack documented;
- current tables and workflows identified;
- known specification conflicts documented;
- no production changes required for the analysis.

---

## Phase 0B — Deployment portability assessment

**Target:** August 2026

### Objective
Determine how strongly the current application depends on Render and Supabase and define a provider-neutral deployment direction.

### Required analysis
- Render configuration and hard-coded URLs;
- Supabase Python client usage by database/storage/auth/RPC;
- session behavior with multiple app instances;
- persistent versus temporary filesystem use;
- QR base URL portability;
- Telegram webhook portability;
- environment-variable inventory;
- Docker deployment proposal;
- feasibility of repository/data-access abstraction for new code;
- meaning of `asset_assignments.status`;
- legacy `current_status = disposed` migration implications.

### Exit gate
A portability architecture decision is approved before new commercial-domain modules are introduced.

---

## Phase 0C — Multi-tenancy architecture

**Target:** August–September 2026

### Objective
Design the tenant foundation before adding lifecycle/disposal tables.

### Key decisions
- `organizations` model;
- organization-scoped business data;
- platform user versus organization person/employee;
- `organization_memberships` and organization-scoped roles;
- tenant isolation strategy;
- tenant-scoped uniqueness such as `(organization_id, asset_tag)`;
- prevention of cross-tenant relationships;
- shared-schema default with future dedicated enterprise tenant option;
- safe migration of the current pilot into Tenant #1.

### Exit gate
No unresolved P0 tenant-isolation/data-model question remains.

---

## Phase 1 — Engineering safety foundation

**Target:** September–October 2026

### Objective
Create the safety mechanisms needed for commercial evolution.

### Deliverables
- DEV / STAGING / PILOT-PRODUCTION separation;
- pytest foundation;
- regression tests for core asset workflows;
- backup/restore drill;
- migration and rollback runbook;
- secrets/environment handling rules.

### Exit gate
Risky migrations can be rehearsed and verified without using the live pilot database as a development environment.

---

## Phase 2 — Multi-tenant foundation

**Target:** October–November 2026

### Objective
Implement organization ownership and tenant isolation while preserving the current pilot.

### Deliverables
- organizations;
- memberships/tenant roles;
- `organization_id` in core business entities;
- tenant-scoped uniqueness and integrity controls;
- server-side tenant context;
- synthetic second-tenant isolation test;
- pilot migration and validation.

### Exit gate
Organization A cannot read/write/link Organization B data in automated isolation tests.

---

## Phase 3 — Domain/API and portability refactor

**Target:** November–December 2026

### Objective
Prepare one backend domain model for web, mobile and messaging clients without rewriting the whole pilot at once.

### Deliverables
- domain/service boundaries;
- repository/data-access abstraction for new modules;
- provider-specific Supabase access isolated where practical;
- `/api/v1` conventions;
- Docker deployment contract;
- generic/alternative-host deployment smoke test.

### Exit gate
New commercial modules can be developed without placing business logic directly in route handlers or direct provider calls.

---

## Phase 4 — Asset lifecycle foundation

**Target:** January 2027

### Objective
Implement a separate operational lifecycle dimension.

### Deliverables
- `lifecycle_status`;
- operational useful life and EOL;
- lifecycle reviews;
- structured lifecycle events;
- controlled transitions;
- legacy `current_status = disposed` mapped to `RETIRED` without inventing historical disposal dates;
- lifecycle UI and filters.

### Exit gate
EOL creates review, not automatic disposal; legacy disposed assets remain retired.

---

## Phase 5 — Review, approval and disposal

**Target:** February–March 2027

### Objective
Create a controlled disposal workflow with evidence and physical verification.

### Deliverables
- condition assessment;
- recommendation and decision basis;
- approval/rejection;
- segregation-of-duties controls;
- disposal cases;
- process-linked evidence;
- QR verification;
- controlled/atomic retirement;
- retired-asset operational restrictions.

### Exit gate
No unverified or unauthorized asset can be retired through the standard disposal process.

---

## Phase 6 — Asset observations: photo and GPS

**Target:** March 2027

### Objective
Create historical proof that an asset was physically observed at a given time/place by a known actor.

### Deliverables
- `asset_observations`;
- photo/object-storage abstraction;
- GPS + accuracy metadata;
- source/actor/timestamp;
- privacy/access/retention rules.

### Exit gate
Photo/GPS evidence can be captured without storing image bytes directly in PostgreSQL and without bypassing tenant permissions.

---

## Phase 7 — Inventory sessions

**Target:** March–April 2027

### Objective
Turn inventory into a formal campaign/reconciliation workflow.

### Deliverables
- inventory session and scope;
- expected assets;
- assigned counters/participants;
- QR verification + observations;
- matched/not-found/unexpected/mismatch outcomes;
- reconciliation;
- final report;
- real pilot inventory.

### Exit gate
A real scoped inventory can be completed end to end with evidence and reconciled exceptions.

---

## Phase 8 — Mobile API and identity

**Target:** April–May 2027

### Objective
Expose secure, versioned APIs for end-user/mobile workflows.

### Initial API scope
- My Assets;
- asset details;
- receipt confirmation;
- transfer request;
- inventory participation;
- QR verification;
- photo/GPS observation;
- problem/status reporting.

### Exit gate
Tenant/authorization/API security tests pass before a mobile client depends on the endpoints.

---

## Phase 9 — Mobile MVP

**Target:** May–June 2027

### Objective
Provide a focused employee-facing mobile client rather than duplicating the full admin web application.

### MVP
- login;
- My Assets;
- receipt confirmation;
- transfer request;
- inventory participation;
- QR scan;
- photo + GPS;
- report problem/loss/status issue.

### Exit gate
Pilot users complete target scenarios without using the admin web interface.

---

## Phase 10 — Multi-channel integration layer

**Target:** June–July 2027

### Objective
Turn Telegram into one adapter over shared business logic and establish extension points for future messengers.

### Deliverables
- Telegram adapter refactor;
- channel identity mapping;
- generic adapter conventions for future Teams/WhatsApp/etc.

---

## Phase 11 — SaaS operations and commercial readiness

**Target:** July 2027

### Objective
Make the system operable for external organizations.

### Deliverables
- tenant provisioning/suspension/offboarding;
- plans/limits/feature flags foundation;
- export/deletion/retention controls;
- security baseline;
- secrets review;
- incident response;
- disaster-recovery rehearsal;
- onboarding/support runbooks;
- legal/IP/commercial readiness checkpoint.

### Exit gate
An external tenant can be onboarded and offboarded without code forks or manual database improvisation.

---

## Phase 12 — External beta and Commercial V1 gate

**Target:** July–August 2027

### Objective
Validate the product with an organization other than Design Partner #1 and make a formal GO/NO-GO release decision.

### Exit criteria for `v1.0`
- no open P0 defect;
- agreed P1 threshold met;
- tenant-isolation gate passed;
- security gate passed;
- backup/restore tested;
- migration baseline frozen;
- onboarding/support procedures accepted;
- known limitations documented;
- external beta completed;
- release decision documented.

## Release model

- `v0.4` — current pilot baseline;
- `v0.5` — safety/portability/multi-tenant foundation;
- `v0.6` — domain/API + lifecycle;
- `v0.7` — disposal + observations + inventory;
- `v0.8` — mobile API;
- `v0.9` — mobile MVP + external beta;
- `v1.0` — first commercial release.

## Planning rule

The roadmap is a controlled forecast, not a promise. Scope and dates are updated only after reviewing dependencies, risks, pilot evidence and phase-gate status.
