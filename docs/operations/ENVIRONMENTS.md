# Environment Model

This project uses three operating environments. Development and automated tests must stay isolated from the pilot production database.

## DEV

Purpose: local development, Codex work, and deterministic automated tests.

Database/data expectations:
- Automated tests must not connect to live Supabase.
- Use `INVENTORY_TEST_MODE=1` for test imports without Supabase credentials.
- Local experiments must use fake data or a disposable non-production database.

Secrets rules:
- Do not commit `.env` files or real service keys.
- Real employee or organization data should not be copied into fixtures.

Deployment expectations:
- Local FastAPI/Uvicorn only unless explicitly testing deployment packaging.
- Set `PUBLIC_BASE_URL` to a local/dev URL when exercising user-visible links outside automated tests.

Migration testing rules:
- Destructive or experimental migrations are not allowed against pilot production.

## STAGING

Purpose: rehearse production-like deployments, migrations, Excel sync, QR lookup, Telegram integrations, and restore drills.

Database/data expectations:
- Separate Supabase project or database from pilot production.
- Use anonymized or explicitly approved sample data.
- Storage buckets must be separate from production buckets.

Secrets rules:
- Use staging-only secrets.
- `ADMIN_SESSION_SECRET` must be unique and strong.
- Bot tokens and Supabase keys must be staging-specific if Telegram tests are enabled.

Deployment expectations:
- Provider-portable deployment target where practical.
- `PUBLIC_BASE_URL` must be configured as the canonical staging URL, for example `https://<staging-render-host>`.
- `INTERNAL_API_BASE_URL` is optional; it may equal `PUBLIC_BASE_URL` while the bot/backend share one service.
- `BOT_TOKEN` should remain unset unless a dedicated staging Telegram bot exists.
- STAGING must not reuse the production Telegram bot token or webhook.

Migration testing rules:
- Every production schema migration must be rehearsed here first.
- Record migration execution, validation queries, and rollback/forward-fix notes.

## PILOT_PRODUCTION

Purpose: live operational inventory for the current organization.

Database/data expectations:
- Contains real operational data.
- No destructive or experimental testing.
- Backups must be confirmed before production migrations.

Secrets rules:
- Production secrets must never be committed or pasted into issue reports.
- `ADMIN_SESSION_SECRET` must be strong; the current fallback value is unsafe for production and must be removed in a future hardening phase.

Deployment expectations:
- User-visible links, QR links, Telegram Mini App links, and callbacks use `PUBLIC_BASE_URL`.
- `PUBLIC_BASE_URL=https://inventory-qr-system.onrender.com` must be explicitly configured in Render for pilot production.
- Provider-specific assumptions should be avoided in new code.

Migration testing rules:
- Product Owner approval is required before production schema changes.
- Prefer additive, backward-compatible migrations.
- Backfill and validation must be scripted and reviewed before execution.
