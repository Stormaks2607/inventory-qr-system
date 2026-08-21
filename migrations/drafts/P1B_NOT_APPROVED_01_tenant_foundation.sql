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
alter table public.asset_classifications add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.asset_sub_classifications add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.asset_history add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.inventory_sessions add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.inventory_records add column if not exists tenant_id uuid references public.tenants(tenant_id);
alter table public.notifications add column if not exists tenant_id uuid references public.tenants(tenant_id);

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

update public.asset_classifications
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

update public.asset_sub_classifications asc_row
set tenant_id = ac.tenant_id
from public.asset_classifications ac
where asc_row.classification_id = ac.classification_id
  and asc_row.tenant_id is null;

update public.asset_history ah
set tenant_id = a.tenant_id
from public.assets a
where ah.asset_id = a.asset_id
  and ah.tenant_id is null;

-- inventory_sessions is a tenant-owned root. Direct Tenant #1 assignment is acceptable
-- for this rehearsal only because the restored pilot dataset represents one organization.
-- Future multi-tenant imports must not infer this from global state.
update public.inventory_sessions
set tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
where tenant_id is null;

update public.inventory_records ir
set tenant_id = s.tenant_id
from public.inventory_sessions s
where ir.session_id = s.session_id
  and ir.tenant_id is null;

update public.notifications n
set tenant_id = p.tenant_id
from public.persons p
where n.person_id = p.person_id
  and n.tenant_id is null;

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
create index if not exists idx_asset_classifications_tenant_id on public.asset_classifications (tenant_id, classification_id);
create index if not exists idx_asset_classifications_tenant_name on public.asset_classifications (tenant_id, classification_name);
create index if not exists idx_asset_sub_classifications_tenant_id on public.asset_sub_classifications (tenant_id, sub_classification_id);
create index if not exists idx_asset_sub_classifications_tenant_classification on public.asset_sub_classifications (tenant_id, classification_id);
create index if not exists idx_asset_sub_classifications_tenant_name on public.asset_sub_classifications (tenant_id, sub_classification_name);
create index if not exists idx_asset_history_tenant_asset on public.asset_history (tenant_id, asset_id);
create index if not exists idx_asset_history_tenant_changed_by on public.asset_history (tenant_id, changed_by);
create index if not exists idx_inventory_sessions_tenant_session on public.inventory_sessions (tenant_id, session_id);
create index if not exists idx_inventory_sessions_tenant_created_by on public.inventory_sessions (tenant_id, created_by);
create index if not exists idx_inventory_sessions_tenant_location on public.inventory_sessions (tenant_id, location_id);
create index if not exists idx_inventory_records_tenant_session on public.inventory_records (tenant_id, session_id);
create index if not exists idx_inventory_records_tenant_asset on public.inventory_records (tenant_id, asset_id);
create index if not exists idx_inventory_records_tenant_scanned_by on public.inventory_records (tenant_id, scanned_by);
create index if not exists idx_notifications_tenant_person on public.notifications (tenant_id, person_id);
create index if not exists idx_notifications_tenant_created on public.notifications (tenant_id, created_at desc);
create index if not exists idx_notifications_tenant_status on public.notifications (tenant_id, delivery_status, created_at desc);

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
union all select 'organization_branding', count(*) from public.organization_branding where tenant_id is null
union all select 'asset_classifications', count(*) from public.asset_classifications where tenant_id is null
union all select 'asset_sub_classifications', count(*) from public.asset_sub_classifications where tenant_id is null
union all select 'asset_history', count(*) from public.asset_history where tenant_id is null
union all select 'inventory_sessions', count(*) from public.inventory_sessions where tenant_id is null
union all select 'inventory_records', count(*) from public.inventory_records where tenant_id is null
union all select 'notifications', count(*) from public.notifications where tenant_id is null;

-- Cross-owner consistency checks must be zero before enforcement.
select 'asset_sub_classifications_classification_mismatch' check_name, count(*) mismatches
from public.asset_sub_classifications asc_row
join public.asset_classifications ac on ac.classification_id = asc_row.classification_id
where asc_row.tenant_id <> ac.tenant_id
union all select 'asset_history_asset_mismatch', count(*)
from public.asset_history ah
join public.assets a on a.asset_id = ah.asset_id
where ah.tenant_id <> a.tenant_id
union all select 'inventory_records_session_mismatch', count(*)
from public.inventory_records ir
join public.inventory_sessions s on s.session_id = ir.session_id
where ir.tenant_id <> s.tenant_id
union all select 'inventory_records_asset_mismatch', count(*)
from public.inventory_records ir
join public.assets a on a.asset_id = ir.asset_id
where ir.tenant_id <> a.tenant_id
union all select 'notifications_person_mismatch', count(*)
from public.notifications n
join public.persons p on p.person_id = n.person_id
where n.tenant_id <> p.tenant_id;

commit;
