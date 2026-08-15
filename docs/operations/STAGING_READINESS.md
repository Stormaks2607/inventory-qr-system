# P1B Staging Readiness

Status: PLANNING ONLY. No production schema, data, or Supabase configuration changes were made.

Baseline:

- Branch checked before work: `main`
- Baseline commit: `5499926 P1A - Engineering safety foundation before tenant migration`
- Baseline tests: `python -m pytest` -> 28 passed

## Recommended Staging Architecture

Recommendation: OPTION A - separate Supabase project plus separate Render service/environment.

This is the safest practical staging target for the current stack because it exercises the same deployment shape as pilot production while keeping database, Storage, secrets, session cookies, Telegram behavior, and Excel files separate.

## Options Assessed

### Option A: Separate Supabase Project + Separate Render Service

Recommended.

Required separation:

- separate Supabase PostgreSQL database;
- separate Supabase Storage buckets;
- separate Supabase keys;
- separate Render service and environment variables;
- separate `ADMIN_SESSION_SECRET`;
- separate `PUBLIC_BASE_URL`;
- staging-only Excel workbook and generated exports;
- Telegram disabled by default or configured with a staging-only bot.

Advantages:

- Closest to production deployment behavior.
- Restore drill can validate Supabase, Storage, Render runtime configuration, Excel sync/export, QR routes, and sessions.
- Reduces risk of accidental writes to `PILOT_PRODUCTION`.

Trade-offs:

- Requires Product Owner setup of a staging Supabase project and Render service.
- May require extra Supabase/Render plan capacity.

### Option B: Separate Supabase Project + Local/Docker Staging App

Acceptable fallback for early rehearsal.

Advantages:

- Lower hosting setup effort.
- Keeps production database and Storage separated if Supabase staging project is used.

Trade-offs:

- Does not validate Render runtime behavior, public callbacks, cookie/domain behavior, or Telegram Mini App links as accurately.
- Less useful for production deployment rehearsal.

### Option C: Shared Supabase Project With Separate Schema

Not recommended.

Reason: the current application uses direct `public` schema Supabase calls throughout `app.py`. Shared-project staging would be too easy to misconfigure and could risk pilot data.

## Environment Variable Matrix

| Variable | DEV | STAGING | PILOT_PRODUCTION | Required | Sensitive | Must differ |
| --- | --- | --- | --- | --- | --- | --- |
| `SUPABASE_URL` | unset for tests; disposable local/staging value for manual dev | staging Supabase URL | production Supabase URL | yes outside test mode | no | yes |
| `SUPABASE_KEY` | unset for tests; disposable key for manual dev | staging key only | production key only | yes outside test mode | yes | yes |
| `INVENTORY_TEST_MODE` | `1` for automated tests | unset unless running isolated tests | unset | test-only | no | yes |
| `SYNC_STORAGE_BUCKET` | optional; fake/local when testing | staging-only private bucket | production private bucket | optional with default | no | yes |
| `BOT_TOKEN` | unset unless testing a dev bot | staging bot token or unset | production bot token if Telegram enabled | optional | yes | yes if enabled |
| `ADMIN_USERNAME` | local admin username | staging admin username | production admin username | optional with unsafe default | yes-ish | yes |
| `ADMIN_PASSWORD` | local password | staging password | production password | optional with unsafe default | yes | yes |
| `ADMIN_SESSION_SECRET` | local strong value or test fallback only | staging strong random value | production strong random value | should be required in production later | yes | yes |
| `PUBLIC_BASE_URL` | local/dev public URL when needed; test mode uses `http://testserver` | `https://<staging-render-host>` | `https://inventory-qr-system.onrender.com` explicitly configured in Render | required outside test mode | no | yes |
| `INTERNAL_API_BASE_URL` | optional local/internal URL | optional; may equal `PUBLIC_BASE_URL` while bot/backend share one service | optional internal URL if bot/backend are split | optional | no/depends | usually yes |
| `REGISTRATION_TRANSFER_EXPORT_FROM` | optional test/dev cutoff | staging cutoff matching rehearsal data | production cutoff | optional | no | environment-specific |
| `BRANDING_SETTINGS_PATH` | currently hardcoded local path | should not rely on local disk for staging | should not rely on local disk for production | currently hardcoded | no | yes if externalized |
| `BRANDING_UPLOAD_DIR` | currently hardcoded local path | should use Storage or persistent staging volume | should use Storage or persistent production volume | currently hardcoded | no | yes if externalized |

Security notes:

- Do not print or commit actual secret values.
- `ADMIN_SESSION_SECRET = "replace-this-session-secret"` remains an unsafe fallback and must be hardened in a future security phase.
- `PUBLIC_BASE_URL` is environment-driven and must not silently fall back to the production Render URL.

## Telegram Strategy

Default P1B recommendation: disable Telegram in staging unless a staging bot token and staging public URL exist.

For initial staging, leave `BOT_TOKEN` unset unless a dedicated staging bot exists.

If enabled:

- use a separate Telegram bot;
- point Mini App and report links to staging `PUBLIC_BASE_URL`;
- use `INTERNAL_API_BASE_URL` only for service-to-service backend calls if bot/backend are split;
- never reuse the production bot token in staging;
- never call or modify the production Telegram webhook from staging;
- validate contact sharing and asset list access only with approved test accounts/data.

## Excel And Storage Separation

Staging must use a separate private Storage bucket from production. The official workbook restored into staging should be a copy of the production workbook or an anonymized rehearsal workbook, never the production bucket object itself.

Smoke checks:

- upload staging workbook;
- generate preview;
- apply only to staging database;
- export workbook;
- re-upload export and confirm no unexpected changes.

## Safe Test Data Policy

- Automated tests use monkeypatches/fakes and no live Supabase.
- Staging may use restored pilot data only after Product Owner approval.
- DEV must not use `PILOT_PRODUCTION` for destructive or experimental testing.

## Backup Readiness

Backup procedure must capture:

- PostgreSQL database backup/export;
- Supabase Storage bucket contents;
- runtime configuration references;
- deployed Git commit SHA;
- Render/runtime configuration needed for restore.

Backup evidence to record:

- operator;
- timestamp;
- source Supabase project;
- backup artifact/reference;
- Storage artifact/reference;
- verification that artifacts exist;
- retention expectation.

## Restore Drill Status

RESTORE DRILL = BLOCKED - EXTERNAL ACTION REQUIRED.

Required Product Owner actions:

1. Create or identify a separate staging Supabase project.
2. Create staging Storage bucket(s), including a staging value for `SYNC_STORAGE_BUCKET`.
3. Create or identify a separate staging Render service/environment.
4. Provide staging-only runtime variables through Render/Supabase UI, not in chat.
5. Confirm whether pilot data may be restored into staging for rehearsal.
6. Approve execution of the restore drill.

Do not execute a restore automatically.

## Required Preflight Before Migration

Before any draft migration runs in staging:

1. Run the schema preflight in `docs/operations/TENANT_MIGRATION_PREFLIGHT.md`.
2. Run the data anomaly preflight in the same document.
3. Record row counts for transaction/lock planning.
4. Stop if orphan child rows, duplicate confirmed business identifiers, or unexpected schema differences exist.

Relational child rows must not receive Tenant #1 as a silent fallback. They must derive tenant ownership from authoritative parent rows, or the migration must stop for explicit data correction.

## Restore Drill Checklist

When authorized, restore `PILOT_PRODUCTION` backup into staging and verify:

- schema restored;
- row counts restored;
- Storage restored;
- application can connect;
- admin login works;
- asset list works;
- asset detail works;
- assignment flow smoke test works;
- transfer flow smoke test works;
- legacy QR routes `/asset/{asset_tag}` and `/view/{asset_tag}` work;
- Excel sync/export smoke behavior works;
- `python -m pytest` remains passing.
