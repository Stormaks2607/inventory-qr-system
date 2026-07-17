create table if not exists public.organization_branding (
    tenant_key varchar primary key,
    company_name varchar,
    report_title varchar,
    report_subtitle text,
    report_theme varchar,
    primary_color varchar,
    accent_color varchar,
    footer_note text,
    issuer_label varchar,
    issuer_signature_label varchar,
    receiver_label varchar,
    receiver_signature_label varchar,
    logo_path text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists organization_branding_tenant_key_uidx
    on public.organization_branding (tenant_key);

alter table public.organization_branding
    add column if not exists company_name varchar,
    add column if not exists report_title varchar,
    add column if not exists report_subtitle text,
    add column if not exists report_theme varchar,
    add column if not exists primary_color varchar,
    add column if not exists accent_color varchar,
    add column if not exists footer_note text,
    add column if not exists issuer_label varchar,
    add column if not exists issuer_signature_label varchar,
    add column if not exists receiver_label varchar,
    add column if not exists receiver_signature_label varchar,
    add column if not exists logo_path text,
    add column if not exists created_at timestamptz not null default now(),
    add column if not exists updated_at timestamptz not null default now();

create or replace function public.set_organization_branding_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_organization_branding_updated_at on public.organization_branding;

create trigger set_organization_branding_updated_at
before update on public.organization_branding
for each row
execute function public.set_organization_branding_updated_at();
