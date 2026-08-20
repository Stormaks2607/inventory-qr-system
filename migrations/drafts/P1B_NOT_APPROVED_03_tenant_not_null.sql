-- P1B DRAFT ONLY - NOT APPROVED FOR PRODUCTION
-- Do not apply to PILOT_PRODUCTION.
-- Intended as a separate Tenant #1 staging enforcement draft after:
--   1. tenant_id backfill has completed for all current tenant-owned tables;
--   2. composite tenant constraints have been rehearsed and validated;
--   3. tenant-aware P1D application writes are deployed and smoke-tested.
-- Rerun behavior: ONE-SHOT.
-- Fresh preflight is mandatory before execution:
--   - every table below must have tenant_id;
--   - every table below must have zero NULL tenant_id values;
--   - current single-tenant STAGING must have zero unexpected tenant IDs;
--   - P1B-02 tenant FK/composite FK constraints must exist and be convalidated;
--   - if some tenant_id columns are already NOT NULL and some are nullable, stop.
-- If any statement fails, stop and review. Do not blindly rerun a partial or
-- previously applied draft. Production execution requires separate authorization.
-- This draft intentionally contains no automatic data repair.

begin;

alter table public.assets
    alter column tenant_id set not null;

alter table public.asset_assignments
    alter column tenant_id set not null;

alter table public.asset_transfers
    alter column tenant_id set not null;

alter table public.asset_transfer_projects
    alter column tenant_id set not null;

alter table public.asset_projects
    alter column tenant_id set not null;

alter table public.asset_payments
    alter column tenant_id set not null;

alter table public.persons
    alter column tenant_id set not null;

alter table public.person_responsibility_scopes
    alter column tenant_id set not null;

alter table public.locations
    alter column tenant_id set not null;

alter table public.projects
    alter column tenant_id set not null;

alter table public.donors
    alter column tenant_id set not null;

alter table public.audit_log
    alter column tenant_id set not null;

alter table public.organization_branding
    alter column tenant_id set not null;

alter table public.asset_classifications
    alter column tenant_id set not null;

alter table public.asset_sub_classifications
    alter column tenant_id set not null;

alter table public.asset_history
    alter column tenant_id set not null;

alter table public.inventory_sessions
    alter column tenant_id set not null;

alter table public.inventory_records
    alter column tenant_id set not null;

alter table public.notifications
    alter column tenant_id set not null;

commit;
