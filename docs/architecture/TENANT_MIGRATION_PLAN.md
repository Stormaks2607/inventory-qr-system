# P1B Tenant Migration Implementation Plan

Status: PLANNING ONLY. This document does not authorize production execution.

## Objectives

- Prepare an additive, reviewable tenant migration design.
- Keep the current organization as the first tenant without changing asset tags, QR routes, assignments, transfers, status history, or IDs.
- Enable staging rehearsal before any production tenant migration.
- Avoid a big-bang `app.py` refactor.

## Tenant Design

Create a planned `tenants` table:

- `tenant_id uuid primary key`
- `tenant_key text not null`
- `display_name text not null`
- `status text not null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

`tenant_id` is the immutable technical/security key.

`tenant_key` is a human/configuration slug only. It must not be trusted as a security identity.

## Tenant Seed Strategy

Recommended: use a predefined stable UUID for the current pilot organization.

Draft value:

```text
00000000-0000-4000-8000-000000000001
```

Trade-offs:

- Stable UUID is deterministic and idempotent across staging and production rehearsal.
- It avoids accidental creation of different owner IDs on repeated migration attempts.
- It must be treated as a technical bootstrap identifier only, not a secret.
- Keeping this fixed UUID is technically safe because tenant isolation must not rely on UUID secrecy. Authorization must come from trusted TenantContext, repository filters, and database constraints.

Alternative controlled lookup/insert by `tenant_key` is possible, but stable UUID is simpler for validation and restore rehearsal.

## Phased Migration Sequence

Do not deploy as one giant migration.

### Step A: Create Tenants

Create `public.tenants` with timestamps, status check, and tenant key uniqueness.

Deployability: can be deployed independently.

Rollback: safe rollback before data references exist; otherwise forward-fix preferred.

### Step B: Insert Current Organization Tenant

Insert the stable Tenant #1 row idempotently.

Deployability: can be deployed with Step A or separately.

Rollback: forward-fix preferred once rows reference it.

### Step C: Add Nullable Tenant Columns

Add nullable `tenant_id` to tenant-owned tables.

Deployability: separate additive migration.

Rollback: safe if no application depends on the columns.

### Step D: Backfill Current Tenant

Backfill root/master tenant-owned tables directly to the stable tenant UUID where appropriate for the current single-organization pilot.

Relational child tables must derive `tenant_id` from authoritative parents:

- assignments, transfers, asset projects, and payments derive from `assets`;
- transfer project rows derive from `asset_transfers`;
- responsibility scopes derive from `persons`;
- nullable person/location/project/donor references must be validated before FK enforcement.

Do not silently assign Tenant #1 to unresolved child rows. Remaining null `tenant_id` in child tables after parent-derived backfill is a blocking data-integrity condition and requires an explicit data correction decision.

Deployability: separate data migration after backup and staging rehearsal.

Rollback: forward-fix preferred; restore required only if unexpected broad data corruption occurs.

### Step E: Validate Every Row

Run schema preflight, anomaly preflight, and post-backfill validation queries. Do not proceed if any expected tenant-owned row has null or unexpected `tenant_id`, and do not proceed if any orphan child relationship remains.

### Step F: Add Indexes

Add tenant lookup indexes and only confirmed tenant-scoped business indexes.

Deployability: separate migration, preferably concurrently where supported.

### Step G: Add Tenant-Scoped Uniqueness

Introduce only confirmed tenant-scoped unique constraints.

Initial confirmed candidates:

- `assets(tenant_id, asset_tag_number)`;
- `projects(tenant_id, project_number)`.

Future candidates requiring business confirmation:

- `persons(tenant_id, lower(email))`;
- `donors(tenant_id, donor_name)`;
- `locations(tenant_id, city, office_name)`.

Compatibility concern: existing global unique constraints may need to remain temporarily until second tenant support is ready.

### Step H: Add Composite Foreign Keys

Add parent unique pairs `(tenant_id, id)` and child composite FKs `(tenant_id, parent_id)`.

Deployability: split into a second enforcement migration after data validation.

### Step I: Make `tenant_id` NOT NULL Where Safe

Only after validation passes and application code uses TenantContext/repositories.

### Step J: Application Uses TenantContext And Repositories

Start with the minimal slice required for assets, assignments, transfers, people, projects, and audit.

### Step K: Remove Legacy Fallback Later

Remove fallback behavior only after staging and production prove tenant-aware reads/writes are stable.

## TenantContext Design

For the first tenant phase, tenant identity may resolve from trusted server-side configuration.

Never trust:

- form `tenant_id`;
- query-string `tenant_id`;
- URL `tenant_id`;
- client-submitted tenant scope.

Flow:

```text
Request -> authenticated session -> trusted TenantContext -> repository -> tenant-filtered data access
```

Future flow:

```text
user_accounts + tenant_memberships -> selected tenant -> TenantContext
```

Do not implement multi-tenant login during initial Tenant #1 migration.

## Draft Migration Rerun Behavior

Foundation draft: PARTIALLY IDEMPOTENT.

- guarded create/add-column/index statements;
- repeatable root/master and parent-derived backfills;
- still requires preflight and execution log because it changes data in staging.

Constraint/enforcement draft: ONE-SHOT.

- `ALTER TABLE ... ADD CONSTRAINT ...` statements are intentionally not hidden behind broad guards;
- schema preflight must confirm the constraints do not already exist;
- rerun is prohibited unless reviewed.

## Transaction And Lock Strategy

The foundation draft currently groups structural additions, backfill updates, indexes, and validation-friendly selects in one transaction. For the current pilot-size dataset this may be acceptable during staging rehearsal if preflight row counts are modest.

For larger future tenants, split execution into:

1. structural additions;
2. data backfill;
3. validation;
4. indexes and constraint enforcement.

Recommended staging sequence:

1. run schema preflight;
2. run data anomaly preflight;
3. record row counts and estimate lock risk;
4. execute foundation draft in staging only;
5. run post-backfill validation;
6. execute one-shot enforcement draft only if validation is clean;
7. run application smoke tests and pytest.

Do not optimize with batching until row counts show the current transaction strategy is unsafe.

## First Repository Slice

Minimum first slice before tenant enforcement:

### AssetRepository

Methods:

- `list_assets(tenant_id, limit=None)`
- `get_asset_by_id(tenant_id, asset_id)`
- `get_asset_by_tag(tenant_id, asset_tag_number)`
- `create_assets(tenant_id, payloads)`
- `update_asset(tenant_id, asset_id, payload)`
- `asset_tag_exists(tenant_id, asset_tag_number)`

Must migrate before enforcement:

- admin asset list/detail/create/edit;
- QR lookup routes;
- Excel import/export asset matching.

Temporary direct Supabase calls may remain for low-risk admin reference pages until their tables are tenant-scoped and covered.

### AssignmentRepository

Methods:

- `get_current_assignment(tenant_id, asset_id)`
- `list_current_assignments(tenant_id)`
- `close_current_assignments(tenant_id, asset_id, return_date, actor)`
- `insert_assignment(tenant_id, payload)`
- `list_assignment_history(tenant_id, asset_id)`

Must migrate before enforcement:

- assignment update;
- offboarding;
- bulk assignment;
- employee asset list/report.

### TransferRepository

Methods:

- `create_transfer(tenant_id, payload)`
- `insert_transfer_projects(tenant_id, payloads)`
- `list_transfer_history(tenant_id, asset_id)`
- `list_transfer_records(tenant_id)`

Must migrate before enforcement:

- transfer history display;
- assignment-change transfer creation;
- Excel Transfer log import/export.

### PersonRepository

Methods:

- `list_people(tenant_id)`
- `get_person_by_id(tenant_id, person_id)`
- `find_person_by_email_or_phone(tenant_id, value)`
- `update_person(tenant_id, person_id, payload)`

Must migrate before enforcement:

- admin people;
- auth/account login;
- Telegram phone auth;
- offboarding.

### ProjectRepository

Methods:

- `list_projects(tenant_id)`
- `list_donors(tenant_id)`
- `list_asset_projects(tenant_id, asset_id)`
- `insert_asset_projects(tenant_id, payloads)`
- `update_asset_project(tenant_id, asset_project_id, payload)`

Must migrate before enforcement:

- project funding section;
- Excel project import/export;
- transfer project relationships.

### AuditLogRepository

Methods:

- `record_event(tenant_id, payload)`
- `list_recent_events(tenant_id, limit)`
- `list_events(tenant_id, filters)`
- `backfill_transfer_log(tenant_id)`

Must migrate before enforcement:

- dashboard recent changes;
- audit log page;
- sync/offboarding/assignment audit writes.

## RLS Position

Do not enable RLS in P1B.

Reason:

- Current backend Supabase access may bypass RLS depending on key/role.
- Existing route handlers still contain many direct `supabase.table(...)` calls.
- Tenant isolation must first be enforced through trusted TenantContext, repository filters, and PostgreSQL composite constraints.

Layering:

1. trusted TenantContext;
2. repository `tenant_id` filters;
3. tenant-aware PostgreSQL constraints/composite FKs;
4. future RLS/DB-role strategy if enforcement is proven.

## Identity Hard Gate

Do not implement `user_accounts` or `tenant_memberships` during Tenant #1 bootstrap unless technically unavoidable.

Hard gate:

- before a second real/external tenant;
- or before multi-tenant invitation/login;

the identity split must exist.

Current `persons` mixes employee/account concerns. That may remain for Tenant #1 staging rehearsal but not for commercial multi-tenant onboarding.

## Legacy QR Compatibility

Existing routes remain unchanged:

- `/asset/{asset_tag}`
- `/view/{asset_tag}`

Asset tags must not change.

Do not implement `/q/{qr_public_id}` in P1B.

Future `asset_public_refs` should coexist by adding new immutable random public references while legacy Tenant #1 routes continue to resolve existing QR labels. New commercial QR can route through `/q/{public_ref}` without exposing asset tags or tenant scope.

## Organization Branding Legacy Key Model

`organization_branding` currently uses `tenant_key` as the primary key/global unique value. Adding `tenant_id` and a future `(tenant_id, tenant_key)` index does not remove that existing global uniqueness.

For Tenant #1 this is acceptable and no destructive PK change is allowed in P1B.

Hard future gate: before multiple tenants need the same branding slug, such as `default`, redesign the branding key model.

Likely future direction:

- `branding_id uuid primary key`;
- `tenant_id` foreign key;
- `branding_key` or slug;
- `unique (tenant_id, branding_key)`.

Do not implement that redesign in P1B.

## Tenant Isolation Test Plan

Future implementation tests must prove:

- Tenant A cannot read Tenant B asset.
- Tenant A cannot update Tenant B asset.
- Tenant A assignment cannot reference Tenant B person.
- Tenant A assignment cannot reference Tenant B asset.
- Duplicate `asset_tag_number` is allowed across tenants.
- Duplicate `asset_tag_number` is rejected inside the same tenant.
- Tenant B QR/public references cannot leak privileged Tenant A information.
- Repository methods always require trusted `tenant_id`.
- Route handlers do not accept client-submitted tenant scope.

Commercial Tenant B must not be implemented against production data in this phase.

## Gate Recommendation

CONDITIONAL GO for staging tenant migration rehearsal only.

Conditions:

- Product Owner creates/approves a fully separate staging Supabase project and Render environment.
- Backup and restore drill is authorized and executed against staging only.
- Draft SQL is reviewed before execution.
- Tenant-aware repository slice is implemented and tested before NOT NULL/composite FK enforcement.

This does not authorize production tenant migration.
