# Tenant #1 Production Migration Runbook

Status: PRODUCTION RUNBOOK - NOT AUTHORIZED FOR EXECUTION

This document is an operator checklist for a future production migration of the current single-organization PILOT_PRODUCTION environment to the validated Tenant #1 foundation.

It does not authorize production execution. Do not connect to production, run SQL, change Render settings, merge PRs, enable RLS, create Tenant #2, change global uniqueness, change Storage paths, or begin lifecycle/disposal work from this document alone.

Tenant #1 UUID:

```text
00000000-0000-4000-8000-000000000001
```

## Validated Staging Baseline

The complete Tenant #1 cycle was rehearsed in isolated STAGING:

- Production backup/restore rehearsal succeeded.
- Storage restore was validated by SHA256.
- Tenant foundation populated `tenant_id` on all 19 tenant-owned public tables.
- Missing tenant, unexpected tenant, and cross-owner mismatch checks were all zero.
- P1D TenantContext application writes were validated.
- P1B-02 composite constraints were rehearsed successfully.
- P1B-03 NOT NULL enforcement was rehearsed successfully.
- Final live application audit write passed under NOT NULL.

Current validated application branch: `feature/p1d-tenant-context-writes`.

Current validated P1D head: `8b1851a`.

Current migration planning PR: PR #11, `planning/p1b-tenant-coverage-addendum`.

Current application tenant-awareness PR: PR #12, `feature/p1d-tenant-context-writes`.

Production tenant migration remains NOT AUTHORIZED.

## Production Phase Order

Recommended sequence:

1. PHASE A - Backup and freeze gate.
2. PHASE B - DB foundation migration.
3. PHASE C - Deploy tenant-aware P1D application.
4. PHASE D - Composite tenant constraints.
5. PHASE E - Tenant ID NOT NULL enforcement.
6. PHASE F - Close maintenance window and final GO.

Reasoning: current production DB does not have `tenant_id` columns, so P1D code must not be launched against legacy schema. Legacy production code does not write `tenant_id`, so after nullable tenant columns are added, normal writes must stay frozen until P1D is live and verified. NOT NULL must wait until tenant-aware application writes are proven in production.

## Application And Database Compatibility Matrix

| DB state | Application | Expected compatibility | Operational risk |
| --- | --- | --- | --- |
| State 0: legacy production schema, no `tenant_id` | Current production/main | Compatible | Baseline before migration. |
| State 0: legacy production schema, no `tenant_id` | P1D tenant-aware app | Unsafe | P1D expects tenant-aware DB structure. Do not deploy before foundation schema exists. |
| State 1: tenant foundation columns exist, nullable/backfilled | Legacy app | Reads mostly compatible | Unsafe for open writes: new rows may get NULL `tenant_id`. Keep maintenance/write freeze. |
| State 1: tenant foundation columns exist, nullable/backfilled | P1D app | Compatible | Required state for controlled write smoke before constraints. |
| State 2: composite tenant constraints active | P1D app | Validated compatible in STAGING | Continue smoke and audit validation. |
| State 3: `tenant_id` NOT NULL on all 19 tables | P1D app | Validated compatible in STAGING | Target production state. |
| State 2 or 3 | Legacy app | Unsafe for writes | Do not casually roll back to legacy app while writes are open. |

## Maintenance And Write Freeze Strategy

Recommended approach: planned short maintenance window with normal production access/write traffic disabled.

During the write freeze:

- take or verify the fresh production backup;
- execute foundation/backfill;
- deploy P1D-compatible application with `DEFAULT_TENANT_ID`;
- perform controlled tenant-aware write smoke;
- continue to constraints and NOT NULL only if all gates pass;
- reopen access only after final production smoke passes.

If a full outage is not possible, an alternative is a read-only operational mode with all write paths blocked at the application or access layer. Do not invent unsupported Render features. The selected production approach must be documented by the operator before GO-0.

## PHASE A - Backup And Freeze Gate

Required before any production change:

- fresh `roles.sql`;
- fresh `schema.sql`;
- fresh `data.sql`;
- `manifest.txt`;
- SHA256 hashes for every backup artifact;
- backup directory outside the repository;
- Storage backup or inventory for `private-inventory-docs`;
- exact production connection metadata recorded securely outside the repository;
- backup timestamp;
- current production application commit SHA;
- current DB row counts;
- write freeze start timestamp and operator.

Do not store passwords, connection strings, service keys, or dump files in the repository.

Command templates, placeholders only:

```powershell
supabase db dump --db-url "<PRODUCTION_CONNECTION_STRING>" -f "C:\Users\User\Documents\inventory-qr-backups\<YYYY-MM-DD>\roles.sql" --role-only
supabase db dump --db-url "<PRODUCTION_CONNECTION_STRING>" -f "C:\Users\User\Documents\inventory-qr-backups\<YYYY-MM-DD>\schema.sql"
supabase db dump --db-url "<PRODUCTION_CONNECTION_STRING>" -f "C:\Users\User\Documents\inventory-qr-backups\<YYYY-MM-DD>\data.sql" --use-copy --data-only -x "storage.buckets_vectors" -x "storage.vector_indexes"
Get-FileHash "C:\Users\User\Documents\inventory-qr-backups\<YYYY-MM-DD>\roles.sql" -Algorithm SHA256
Get-FileHash "C:\Users\User\Documents\inventory-qr-backups\<YYYY-MM-DD>\schema.sql" -Algorithm SHA256
Get-FileHash "C:\Users\User\Documents\inventory-qr-backups\<YYYY-MM-DD>\data.sql" -Algorithm SHA256
```

Backup validation:

- dump files exist and are non-zero;
- hashes are recorded in the manifest;
- schema dump contains critical tables such as `assets`, `asset_assignments`, `asset_transfers`, `persons`, `locations`, `projects`, `audit_log`;
- data dump row counts are plausible against production row-count checks;
- Storage objects are enumerated and recorded.

Recommendation: a fresh restore rehearsal immediately before production migration is the safest option if time and an isolated target are available. If not, the completed STAGING rehearsal plus fresh backup verification may be sufficient for this small pilot dataset, but the operator must accept that the fresh backup was not restored before cutover.

If production remains writable after backup, that backup is a recovery checkpoint, not a precise cutover snapshot. Recommended approach: take the fresh backup immediately before or during the write freeze.

## PHASE B - DB Foundation Migration

Reference reviewed draft:

```text
migrations/drafts/P1B_NOT_APPROVED_01_tenant_foundation.sql
```

Expected behavior:

- create `public.tenants`;
- seed Tenant #1 UUID `00000000-0000-4000-8000-000000000001`;
- add nullable `tenant_id` columns to the 19 tenant-owned public tables;
- add basic `tenant_id -> tenants` FKs;
- backfill existing production rows from authoritative ownership;
- run in one transaction;
- stop on error;
- do not blindly rerun a partially applied file.

Expected 19 tenant-owned tables:

```text
assets
asset_assignments
asset_transfers
asset_transfer_projects
asset_projects
asset_payments
persons
person_responsibility_scopes
locations
projects
donors
audit_log
organization_branding
asset_classifications
asset_sub_classifications
asset_history
inventory_sessions
inventory_records
notifications
```

Foundation post-validation:

- Tenant #1 row exists;
- tenant columns exist on 19/19 tables;
- missing tenant = 0;
- unexpected tenant = 0;
- tenant-scoped duplicate checks = 0;
- cross-owner checks = 0;
- data row counts are preserved;
- referential orphan checks remain zero.

Use `docs/operations/TENANT_MIGRATION_PREFLIGHT.md` and `docs/operations/TENANT_MIGRATION_VALIDATION.md` by reference.

## PHASE C - Deploy Tenant-Aware P1D Application

Deploy only after foundation schema exists and validates.

Required production environment variable:

```text
DEFAULT_TENANT_ID=00000000-0000-4000-8000-000000000001
```

Preserve without printing:

- `PUBLIC_BASE_URL`;
- `INTERNAL_API_BASE_URL`;
- all existing production secrets;
- Supabase URL and keys;
- Telegram secrets;
- session secrets.

Required records:

- exact P1D commit SHA deployed;
- production deploy timestamp;
- operator;
- Render service/environment identifier;
- confirmation that production deploy commit matches reviewed code.

Smoke checks after deploy:

- `/health`;
- login/logout;
- dashboard;
- assets list;
- asset detail;
- legacy `/view/{asset_tag}`;
- legacy `/asset/{asset_tag}`;
- audit log;
- Excel page.

## Controlled Pre-Constraint Write Test

After P1D is live and before P1B-02, perform one minimal reversible write.

Preferred test:

1. Choose a known test-safe asset.
2. Edit `Remarks`.
3. Save.
4. Verify the new `audit_log` row has Tenant #1 UUID.
5. Revert `Remarks`.
6. Verify the revert audit row also has Tenant #1 UUID.
7. Rerun missing tenant checks.

Avoid reassignment or transfer in production unless explicitly authorized.

STOP if any new NULL `tenant_id` appears.

## PHASE D - Composite Tenant Constraints

Reference reviewed draft:

```text
migrations/drafts/P1B_NOT_APPROVED_02_tenant_constraints.sql
```

Fresh preflight required:

- missing tenant = 0;
- unexpected tenant = 0;
- cross-owner mismatch = 0;
- tenant-scoped duplicate checks = 0;
- one-shot objects do not already exist;
- expected parent unique pairs can be created;
- no schema drift from rehearsed shape.

Post-validation:

- 35 expected tenant constraints exist;
- 5 expected tenant-scoped indexes exist;
- all tenant constraints have `convalidated = true`;
- app read smoke passes;
- controlled application write passes;
- no new NULL tenant rows.

## PHASE E - Tenant ID NOT NULL Enforcement

Reference reviewed draft from PR #11:

```text
migrations/drafts/P1B_NOT_APPROVED_03_tenant_not_null.sql
```

Fresh preflight required:

- exactly 19 `tenant_id` columns;
- before first execution all 19 are nullable;
- missing tenant = 0;
- unexpected tenant = 0;
- P1B-02 constraints remain present and validated;
- P1D app is live and confirmed tenant-aware;
- no mixed NOT NULL state.

Apply in one transaction.

Post-validation:

- exactly 19 `tenant_id` columns;
- every `tenant_id` column has `is_nullable = NO`;
- missing tenant = 0;
- unexpected tenant = 0;
- tenant constraints remain validated;
- final controlled application write succeeds.

Operational note: `ALTER COLUMN SET NOT NULL` may validate/scan the table and take a strong table lock. This is acceptable for the small isolated STAGING rehearsal, but production requires fresh row counts, a controlled window, and a PostgreSQL locking review. STAGING timings do not guarantee production timings.

## PHASE F - Final Smoke And Close Window

Compact smoke checklist:

- health endpoint;
- login;
- dashboard;
- assets list;
- asset detail;
- search;
- QR `/view/{asset_tag}`;
- legacy `/asset/{asset_tag}`;
- global audit;
- Assignment History;
- Transfer History;
- Excel page;
- classification dropdown;
- sub-classification dropdown;
- controlled remarks edit/revert;
- audit tenant verification;
- missing tenant = 0 after the write;
- no new application errors.

Do not require a real asset transfer in production unless explicitly authorized.

## STOP Conditions

STOP with no improvisation if:

- backup is incomplete;
- backup hashes are missing;
- Storage backup or inventory is incomplete;
- production commit SHA is unknown;
- production deployment commit differs from reviewed code;
- schema differs from rehearsed shape;
- any of 19 tables are missing;
- migration output contains `ERROR`;
- any tenant_id backfill remains NULL;
- unexpected tenant IDs appear;
- cross-owner mismatch > 0;
- duplicate tenant business keys unexpectedly appear;
- composite constraint count differs from expectation;
- expected tenant-scoped index count differs from expectation;
- any tenant constraint has `convalidated = false`;
- P1D app fails health, login, read, or write smoke;
- any new write creates NULL `tenant_id`;
- NOT NULL state is mixed;
- controlled write cannot be safely reverted;
- operator cannot confirm the current phase state.

## Rollback And Recovery

Before foundation COMMIT:

- transaction rollback is expected.

After foundation but before P1D:

- preferred response is forward-fix and deploy P1D if DB is healthy;
- otherwise review a controlled rollback plan.

After P1D deploy:

- application rollback must consider current DB state;
- legacy app may read a tenant-extended nullable schema, but it does not safely write `tenant_id`;
- do not casually roll back to legacy app while writes are open.

After composite constraints:

- dropping constraints is technically possible;
- review exact constraint names and data state before any rollback.

After NOT NULL:

- `ALTER TABLE public.<table> ALTER COLUMN tenant_id DROP NOT NULL;` is technically possible;
- do not execute automatically;
- verify schema state before any rerun.

Catastrophic recovery:

- restore production database from validated backup;
- restore or reconcile Storage separately;
- restore known-good production application commit.

Database logical restore and Storage restore are separate operations. Logical DB dumps do not include physical Storage objects.

## GO / NO-GO Checkpoints

Each checkpoint must be signed by the operator.

| Gate | Required record |
| --- | --- |
| GO-0 backup complete | timestamp, operator, production commit SHA, backup path, hash manifest, DB row counts, decision GO/STOP |
| GO-1 foundation migrated and validated | timestamp, operator, migration draft SHA/source, validation summary, decision GO/STOP |
| GO-2 P1D deployed and tenant-aware write verified | timestamp, operator, deployed commit SHA, env confirmation, write/audit result, decision GO/STOP |
| GO-3 composite constraints validated | timestamp, operator, constraint/index counts, convalidated result, smoke result, decision GO/STOP |
| GO-4 NOT NULL validated | timestamp, operator, 19/19 NOT NULL result, final write result, decision GO/STOP |
| GO-5 final production smoke passed | timestamp, operator, smoke checklist result, monitoring owner, decision GO/STOP |

## Downtime Estimate Template

Do not invent exact minutes. Record actual times during the production window:

| Segment | Start | End | Duration | Notes |
| --- | --- | --- | --- | --- |
| Backup | | | | |
| Write freeze | | | | |
| Foundation migration | | | | |
| Application deploy | | | | |
| Validation | | | | |
| Composite constraints | | | | |
| NOT NULL | | | | |
| Final smoke | | | | |
| Close window | | | | |

STAGING timings, if separately recorded, are reference data only and do not guarantee production timing.

## Storage

Current production Storage bucket:

```text
private-inventory-docs
```

Current Tenant #1 path remains acceptable for this Tenant #1 migration. Do not redesign Storage in this runbook.

Tenant #2 gate: before onboarding Tenant #2, Storage paths must become tenant-scoped, for example:

```text
private-inventory-docs/<tenant_id>/...
```

Storage objects are not automatically included in logical DB dumps.

## Tenant #2 Out Of Scope

Known blockers remain:

- `assets.asset_tag_number` global uniqueness;
- `assets.inventory_code` decision;
- `projects.project_number` global uniqueness;
- `asset_classifications.classification_name` global uniqueness;
- `organization_branding.tenant_key` global PK/uniqueness;
- Storage tenant isolation;
- broader read isolation, RLS, and repository hardening;
- account and tenant membership model.

Do not solve them here.

## PR And Deployment Strategy

Recommended integration order:

1. Review PR #11 as the migration draft and operations documentation package.
2. Review PR #12 as the P1D application compatibility package.
3. Merge or otherwise make PR #11 migration/docs available before production execution because it does not alter runtime behavior by itself.
4. Do not deploy PR #12 code to production before foundation schema exists.
5. During the production migration window, deploy the exact reviewed P1D commit only after PHASE B foundation migration validates.
6. Merge P1D to `main` only when the production DB is ready for tenant-aware code or when deployment is explicitly pinned to the reviewed commit and auto-deploy behavior is controlled by the operator.

Do not assume Render branch switching is the final production method. The operator must record the exact reviewed commit deployed and confirm that production auto-deploy will not launch incompatible code against an incompatible DB state.

## Post-Migration Monitoring

For the first period after migration, check:

- health endpoint;
- application error logs;
- failed DB writes;
- tenant_id NULL attempts or constraint errors;
- audit activity;
- assignment and transfer errors;
- unusual 4xx/5xx responses;
- DB constraint errors.

Do not invent monitoring tooling. If no formal monitoring is configured, use Render logs, Supabase logs/dashboard views, manual smoke checks, and audit-log review.

## Final Reminder

This runbook is not approval. Production execution requires a separate explicit GO decision.
