-- P1B DRAFT ONLY - NOT APPROVED FOR PRODUCTION
-- Do not apply to PILOT_PRODUCTION.
-- Intended as a later staging enforcement draft after validation passes.
-- Rerun behavior: ONE-SHOT.
-- Schema preflight must confirm these constraints/indexes do not already exist.
-- If a rerun is needed, stop and review instead of executing blindly.

begin;

alter table public.assets add constraint assets_tenant_asset_id_uidx unique (tenant_id, asset_id);
alter table public.persons add constraint persons_tenant_person_id_uidx unique (tenant_id, person_id);
alter table public.locations add constraint locations_tenant_location_id_uidx unique (tenant_id, location_id);
alter table public.projects add constraint projects_tenant_project_id_uidx unique (tenant_id, project_id);
alter table public.donors add constraint donors_tenant_donor_id_uidx unique (tenant_id, donor_id);
alter table public.asset_transfers add constraint asset_transfers_tenant_transfer_id_uidx unique (tenant_id, transfer_id);
alter table public.asset_classifications add constraint asset_classifications_tenant_classification_id_uidx unique (tenant_id, classification_id);
alter table public.asset_sub_classifications add constraint asset_sub_classifications_tenant_sub_classification_id_uidx unique (tenant_id, sub_classification_id);
alter table public.inventory_sessions add constraint inventory_sessions_tenant_session_id_uidx unique (tenant_id, session_id);

-- Tenant-scoped business uniqueness.
-- Confirmed initial candidates only. Preflight duplicate checks must pass before applying.
-- P1B does not drop existing global unique constraints:
--   assets.asset_tag_number
--   assets.inventory_code
--   projects.project_number
--   asset_classifications.classification_name
--   organization_branding.tenant_key
-- Tenant #2 gate: decide whether inventory_code remains platform-global or becomes
-- tenant-local with unique (tenant_id, inventory_code).
create unique index if not exists assets_tenant_asset_tag_uidx
    on public.assets (tenant_id, asset_tag_number)
    where asset_tag_number is not null;

create unique index if not exists projects_tenant_project_number_uidx
    on public.projects (tenant_id, project_number)
    where project_number is not null;

-- LEGACY LIMITATION: organization_branding currently has tenant_key as the primary key.
-- Adding this tenant-scoped index does not remove the existing global uniqueness.
-- Before multiple tenants need the same branding slug, redesign to branding_id UUID PK.
create unique index if not exists organization_branding_tenant_tenant_key_uidx
    on public.organization_branding (tenant_id, tenant_key);

-- Tenant-local taxonomy uniqueness. Existing asset_classifications.classification_name
-- global uniqueness remains in P1B and must be reworked before Tenant #2
-- independent taxonomy. asset_sub_classifications(classification_id,
-- sub_classification_name) is not itself a cross-tenant name blocker because
-- classification_id is globally unique; this tenant-aware index supports isolation
-- and composite FK consistency.
create unique index if not exists asset_classifications_tenant_name_uidx
    on public.asset_classifications (tenant_id, classification_name);

create unique index if not exists asset_sub_classifications_tenant_classification_name_uidx
    on public.asset_sub_classifications (tenant_id, classification_id, sub_classification_name);

-- Composite FK enforcement. Apply only after no cross-owner mismatches remain.
alter table public.asset_assignments
    add constraint asset_assignments_tenant_asset_fk
    foreign key (tenant_id, asset_id)
    references public.assets (tenant_id, asset_id);

alter table public.asset_assignments
    add constraint asset_assignments_tenant_person_fk
    foreign key (tenant_id, person_id)
    references public.persons (tenant_id, person_id);

alter table public.asset_assignments
    add constraint asset_assignments_tenant_location_fk
    foreign key (tenant_id, location_id)
    references public.locations (tenant_id, location_id);

alter table public.asset_transfers
    add constraint asset_transfers_tenant_asset_fk
    foreign key (tenant_id, asset_id)
    references public.assets (tenant_id, asset_id);

alter table public.asset_transfers
    add constraint asset_transfers_tenant_from_person_fk
    foreign key (tenant_id, from_person_id)
    references public.persons (tenant_id, person_id);

alter table public.asset_transfers
    add constraint asset_transfers_tenant_to_person_fk
    foreign key (tenant_id, to_person_id)
    references public.persons (tenant_id, person_id);

alter table public.asset_transfers
    add constraint asset_transfers_tenant_from_location_fk
    foreign key (tenant_id, from_location_id)
    references public.locations (tenant_id, location_id);

alter table public.asset_transfers
    add constraint asset_transfers_tenant_to_location_fk
    foreign key (tenant_id, to_location_id)
    references public.locations (tenant_id, location_id);

alter table public.asset_transfer_projects
    add constraint asset_transfer_projects_tenant_transfer_fk
    foreign key (tenant_id, transfer_id)
    references public.asset_transfers (tenant_id, transfer_id);

alter table public.asset_transfer_projects
    add constraint asset_transfer_projects_tenant_project_fk
    foreign key (tenant_id, project_id)
    references public.projects (tenant_id, project_id);

alter table public.asset_projects
    add constraint asset_projects_tenant_asset_fk
    foreign key (tenant_id, asset_id)
    references public.assets (tenant_id, asset_id);

alter table public.asset_projects
    add constraint asset_projects_tenant_project_fk
    foreign key (tenant_id, project_id)
    references public.projects (tenant_id, project_id);

alter table public.asset_projects
    add constraint asset_projects_tenant_donor_fk
    foreign key (tenant_id, donor_id)
    references public.donors (tenant_id, donor_id);

alter table public.asset_payments
    add constraint asset_payments_tenant_asset_fk
    foreign key (tenant_id, asset_id)
    references public.assets (tenant_id, asset_id);

alter table public.person_responsibility_scopes
    add constraint person_responsibility_scopes_tenant_person_fk
    foreign key (tenant_id, person_id)
    references public.persons (tenant_id, person_id);

alter table public.person_responsibility_scopes
    add constraint person_responsibility_scopes_tenant_location_fk
    foreign key (tenant_id, location_id)
    references public.locations (tenant_id, location_id);

alter table public.organization_branding
    add constraint organization_branding_tenant_fk
    foreign key (tenant_id)
    references public.tenants (tenant_id);

alter table public.asset_sub_classifications
    add constraint asset_sub_classifications_tenant_classification_fk
    foreign key (tenant_id, classification_id)
    references public.asset_classifications (tenant_id, classification_id);

alter table public.asset_history
    add constraint asset_history_tenant_asset_fk
    foreign key (tenant_id, asset_id)
    references public.assets (tenant_id, asset_id);

alter table public.asset_history
    add constraint asset_history_tenant_changed_by_fk
    foreign key (tenant_id, changed_by)
    references public.persons (tenant_id, person_id);

alter table public.inventory_sessions
    add constraint inventory_sessions_tenant_created_by_fk
    foreign key (tenant_id, created_by)
    references public.persons (tenant_id, person_id);

alter table public.inventory_sessions
    add constraint inventory_sessions_tenant_location_fk
    foreign key (tenant_id, location_id)
    references public.locations (tenant_id, location_id);

alter table public.inventory_records
    add constraint inventory_records_tenant_session_fk
    foreign key (tenant_id, session_id)
    references public.inventory_sessions (tenant_id, session_id);

alter table public.inventory_records
    add constraint inventory_records_tenant_asset_fk
    foreign key (tenant_id, asset_id)
    references public.assets (tenant_id, asset_id);

alter table public.inventory_records
    add constraint inventory_records_tenant_scanned_by_fk
    foreign key (tenant_id, scanned_by)
    references public.persons (tenant_id, person_id);

alter table public.notifications
    add constraint notifications_tenant_person_fk
    foreign key (tenant_id, person_id)
    references public.persons (tenant_id, person_id);

-- notifications.entity_id is polymorphic and intentionally has no FK.

-- NOT NULL enforcement should be a final separate step after application TenantContext/repositories are live.
-- Example only:
-- alter table public.assets alter column tenant_id set not null;

commit;
