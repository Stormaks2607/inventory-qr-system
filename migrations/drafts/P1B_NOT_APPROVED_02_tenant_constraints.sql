-- P1B DRAFT ONLY - NOT APPROVED FOR PRODUCTION
-- Do not apply to PILOT_PRODUCTION.
-- Intended as a later staging enforcement draft after validation passes.

begin;

alter table public.assets add constraint assets_tenant_asset_id_uidx unique (tenant_id, asset_id);
alter table public.persons add constraint persons_tenant_person_id_uidx unique (tenant_id, person_id);
alter table public.locations add constraint locations_tenant_location_id_uidx unique (tenant_id, location_id);
alter table public.projects add constraint projects_tenant_project_id_uidx unique (tenant_id, project_id);
alter table public.donors add constraint donors_tenant_donor_id_uidx unique (tenant_id, donor_id);
alter table public.asset_transfers add constraint asset_transfers_tenant_transfer_id_uidx unique (tenant_id, transfer_id);

-- Tenant-scoped business uniqueness. Review existing global constraints before applying.
create unique index if not exists assets_tenant_asset_tag_uidx
    on public.assets (tenant_id, asset_tag_number)
    where asset_tag_number is not null;

create unique index if not exists projects_tenant_project_number_uidx
    on public.projects (tenant_id, project_number)
    where project_number is not null;

create unique index if not exists persons_tenant_email_lower_uidx
    on public.persons (tenant_id, lower(email))
    where email is not null;

create unique index if not exists donors_tenant_donor_name_uidx
    on public.donors (tenant_id, donor_name)
    where donor_name is not null;

create unique index if not exists locations_tenant_city_office_uidx
    on public.locations (tenant_id, city, office_name)
    where city is not null and office_name is not null;

create unique index if not exists organization_branding_tenant_key_uidx
    on public.organization_branding (tenant_id, tenant_key);

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

-- NOT NULL enforcement should be a final separate step after application TenantContext/repositories are live.
-- Example only:
-- alter table public.assets alter column tenant_id set not null;

commit;
