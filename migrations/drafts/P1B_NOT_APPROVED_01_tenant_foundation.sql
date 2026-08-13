-- P1B DRAFT ONLY - NOT APPROVED FOR PRODUCTION
-- Do not apply to PILOT_PRODUCTION.
-- Intended first for staging review/rehearsal after backup and Product Owner authorization.
-- Rerun behavior: PARTIALLY IDEMPOTENT.
--   - create/add-column/index steps are guarded.
--   - backfill updates are repeatable for rows that still have NULL tenant_id.
--   - this draft must still be preceded by schema and data-anomaly preflight.

begin;

create table if not exists public.tenants (
    tenant_id uuid primary key,
    tenant_key text not null,
    display_name text not null,
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint tenants_status_check check (status in ('active', 'inactive', 'suspended'))
);

create unique index if not exists tenants_tenant_key_uidx
    on public.tenants (tenant_key);

insert into public.tenants (tenant_id, tenant_key, display_name, status)
values (
    '00000000-0000-4000-8000-000000000001'::uuid,
    'pilot',
    'Current pilot organization',
    'active'
)
on conflict (tenant_id) do update
set
    tenant_key = excluded.tenant_key,
    display_name = excluded.display_name,
    status = excluded.status,
    updated_at = now();

alter table public.assets add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.asset_assignments add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.asset_transfers add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.asset_transfer_projects add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.asset_projects add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.asset_payments add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.persons add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.person_responsibility_scopes add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.locations add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.projects add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.donors add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.audit_log add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.organization_branding add column if not exists tenant_id uuid references public.tenants(tenant_id);

update public.assets
set tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
where tenant_id is null;

update public.persons
set tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
where tenant_id is null;

update public.locations
set tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
where tenant_id is null;

update public.projects
set tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
where tenant_id is null;

update public.donors
set tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
where tenant_id is null;

update public.audit_log
set tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
where tenant_id is null;

update public.organization_branding
set tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
where tenant_id is null;

update public.asset_assignments aa
set tenant_id = a.tenant_id
from public.assets a
where aa.asset_id = a.asset_id
  and aa.tenant_id is null;

update public.asset_transfers t
set tenant_id = a.tenant_id
from public.assets a
where t.asset_id = a.asset_id
  and t.tenant_id is null;

update public.asset_transfer_projects atp
set tenant_id = t.tenant_id
from public.asset_transfers t
where atp.transfer_id = t.transfer_id
  and atp.tenant_id is null;

update public.asset_projects ap
set tenant_id = a.tenant_id
from public.assets a
where ap.asset_id = a.asset_id
  and ap.tenant_id is null;

update public.asset_payments pay
set tenant_id = a.tenant_id
from public.assets a
where pay.asset_id = a.asset_id
  and pay.tenant_id is null;

update public.person_responsibility_scopes prs
set tenant_id = p.tenant_id
from public.persons p
where prs.person_id = p.person_id
  and prs.tenant_id is null;

create index if not exists idx_assets_tenant_asset_id on public.assets (tenant_id, asset_id);
create index if not exists idx_assets_tenant_asset_tag on public.assets (tenant_id, asset_tag_number);
create index if not exists idx_asset_assignments_tenant_asset on public.asset_assignments (tenant_id, asset_id);
create index if not exists idx_asset_assignments_tenant_person on public.asset_assignments (tenant_id, person_id);
create index if not exists idx_asset_assignments_tenant_location on public.asset_assignments (tenant_id, location_id);
create index if not exists idx_asset_transfers_tenant_asset on public.asset_transfers (tenant_id, asset_id);
create index if not exists idx_asset_transfer_projects_tenant_transfer on public.asset_transfer_projects (tenant_id, transfer_id);
create index if not exists idx_asset_projects_tenant_asset on public.asset_projects (tenant_id, asset_id);
create index if not exists idx_asset_payments_tenant_asset on public.asset_payments (tenant_id, asset_id);
create index if not exists idx_persons_tenant_person_id on public.persons (tenant_id, person_id);
create index if not exists idx_locations_tenant_location_id on public.locations (tenant_id, location_id);
create index if not exists idx_projects_tenant_project_id on public.projects (tenant_id, project_id);
create index if not exists idx_donors_tenant_donor_id on public.donors (tenant_id, donor_id);
create index if not exists idx_audit_log_tenant_created on public.audit_log (tenant_id, created_at desc);
create index if not exists idx_organization_branding_tenant on public.organization_branding (tenant_id);

-- Validation-friendly checks.
-- Root/master rows are expected to have missing_tenant = 0 after this draft.
-- Relational child rows must also be 0 before enforcement. If any child row remains
-- NULL, that indicates an orphan/anomalous relationship that requires explicit data
-- correction. Do not silently assign Tenant #1 to those rows.
select 'assets' table_name, count(*) missing_tenant from public.assets where tenant_id is null
union all select 'asset_assignments', count(*) from public.asset_assignments where tenant_id is null
union all select 'asset_transfers', count(*) from public.asset_transfers where tenant_id is null
union all select 'asset_transfer_projects', count(*) from public.asset_transfer_projects where tenant_id is null
union all select 'asset_projects', count(*) from public.asset_projects where tenant_id is null
union all select 'asset_payments', count(*) from public.asset_payments where tenant_id is null
union all select 'persons', count(*) from public.persons where tenant_id is null
union all select 'person_responsibility_scopes', count(*) from public.person_responsibility_scopes where tenant_id is null
union all select 'locations', count(*) from public.locations where tenant_id is null
union all select 'projects', count(*) from public.projects where tenant_id is null
union all select 'donors', count(*) from public.donors where tenant_id is null
union all select 'audit_log', count(*) from public.audit_log where tenant_id is null
union all select 'organization_branding', count(*) from public.organization_branding where tenant_id is null;

commit;
