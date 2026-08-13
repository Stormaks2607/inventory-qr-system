# Migration Runbook

Every future production schema migration must complete this checklist before execution.

## 1. Migration Objective

Describe the business and technical goal. Include the GitHub issue, expected user-visible behavior, and whether this is additive, backfill-only, destructive, or cleanup.

## 2. Affected Tables

List every table, view, function, trigger, storage bucket, and application route affected by the migration.

## 3. Pre-Migration Checks

Record:

- Current deployed Git commit SHA.
- Current application version or deployment ID.
- Row counts for affected tables.
- Known data anomalies relevant to the migration.
- Confirmation that no conflicting sync/import/export job is running.

## 4. Production Backup Confirmation

Confirm:

- Fresh database backup exists.
- Required Supabase Storage objects are backed up.
- Important configuration is documented securely.
- Restore path is known.

## 5. Staging/Test Rehearsal

Apply the migration to staging first. Record:

- Staging project/database used.
- Migration command or SQL executed.
- Execution time.
- Validation results.
- Rollback or forward-fix rehearsal result.

## 6. Additive Strategy

Prefer additive/non-destructive changes:

- Add nullable columns before enforcing `NOT NULL`.
- Backfill separately from structural changes.
- Preserve legacy compatibility during transition.
- Avoid dropping columns until application code and data have been verified.

## 7. Data Backfill Plan

Define:

- Source data.
- Mapping rules.
- Idempotency strategy.
- Handling for unknown or unreliable historical values.
- Expected row counts.

For future lifecycle migration:

```sql
CASE
  WHEN current_status = 'disposed' THEN 'RETIRED'
  ELSE 'ACTIVE'
END
```

If a disposed record has no reliable historical disposal date, `disposed_at` must remain `NULL`.

## 8. Integrity Checks

Prepare validation queries for:

- Missing required references.
- Cross-customer ownership mismatches once customer scoping exists.
- Duplicate business identifiers inside tenant scope.
- Orphaned assignments, transfers, payments, and project allocations.

## 9. Application Compatibility Check

Confirm existing workflows still work:

- asset read/create/edit
- assignment and reassignment
- transfer history
- effective status behavior
- QR lookup
- Excel import/export
- authentication and role authorization

## 10. Post-Migration Validation

Run validation queries and route smoke tests immediately after production execution. Compare key counts with pre-migration records.

## 11. Rollback Or Forward-Fix Strategy

Document the chosen recovery path before production execution:

- restore backup;
- apply corrective migration;
- temporarily disable affected feature;
- redeploy previous application version.

## 12. Evidence Log

Record:

- operator;
- date/time;
- SQL or migration file name;
- affected environment;
- backup reference;
- validation evidence;
- issue link;
- final result.

## 13. Product Owner GO

Production migration requires explicit Product Owner approval after backup confirmation and staging rehearsal evidence are available.
