# Backup And Restore

Status: NOT EXECUTED - REQUIRES EXTERNAL ACTION.

No safe non-production restore drill was executed during P1A because the current Codex environment does not have confirmed staging credentials, Supabase project access boundaries, or Product Owner approval to operate on backup/restore infrastructure.

## What Must Be Backed Up

- Supabase Postgres database, including all public schema tables, constraints, indexes, and functions.
- Supabase Storage buckets, especially the private workbook bucket configured by `SYNC_STORAGE_BUCKET`.
- Application configuration and deployment environment variables.
- Render or future hosting service configuration.
- Telegram bot configuration if enabled.
- Git commit SHA deployed at the time of backup.

## Database Backup

Minimum acceptable production backup before migration:

1. Confirm the target project is `PILOT_PRODUCTION`.
2. Create a fresh Supabase database backup or export using Supabase dashboard/CLI.
3. Record backup timestamp, operator, project reference, and migration objective.
4. Verify the backup is visible and restorable before proceeding.

Preferred staging rehearsal:

1. Restore the production backup into a separate staging Supabase project.
2. Apply the migration in staging.
3. Run validation queries and application smoke tests.
4. Record evidence before approving production execution.

## Storage Backup

Back up all files needed for operational continuity:

- Official Excel workbook template/source file.
- Generated export artifacts if retention is required.
- Branding logos and report assets.
- Future asset photos, disposal evidence, inventory evidence, and documents.

Recommended namespace for future customer-safe storage:

```text
customers/{customer_scope}/sync/
customers/{customer_scope}/branding/
customers/{customer_scope}/assets/
customers/{customer_scope}/photos/
customers/{customer_scope}/documents/
customers/{customer_scope}/evidence/
customers/{customer_scope}/inventory/
customers/{customer_scope}/disposal/
```

## Configuration Backup

Record values or secure references for:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SYNC_STORAGE_BUCKET`
- `BOT_TOKEN`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_SESSION_SECRET`
- Future `PUBLIC_BASE_URL`
- Future `INTERNAL_API_BASE_URL`

Never commit secret values to the repository.

## Restore Procedure

1. Select the restore target: staging first, production only after approval.
2. Restore the database backup into the target Supabase project.
3. Restore required Storage objects into the target buckets.
4. Configure environment variables for the restored application.
5. Deploy the matching Git commit SHA.
6. Run application smoke checks:
   - `/health`
   - admin login/logout
   - asset list and asset detail
   - QR lookup `/asset/{tag}` and `/view/{tag}`
   - Excel sync page load
   - export workbook generation
7. Run data validation checks:
   - asset count by usage type
   - active assignment count
   - payment count
   - project allocation count
   - transfer log count
   - audit log count
8. Record restore result and unresolved issues.

## Limitations

- Current application code still contains many direct Supabase calls, so restore validation depends on route-level smoke checks until repository tests are expanded.
- Current signed-cookie sessions cannot be centrally revoked without future session/membership version checks.
- Current `assets.current_status` remains a legacy technical status field; future lifecycle migrations must be defensive.
