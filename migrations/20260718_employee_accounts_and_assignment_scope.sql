alter table public.persons
    add column if not exists password_hash text,
    add column if not exists account_role varchar not null default 'employee',
    add column if not exists must_change_password boolean not null default false,
    add column if not exists last_login_at timestamptz;

create unique index if not exists persons_email_lower_uidx
    on public.persons (lower(email))
    where email is not null and btrim(email) <> '';

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'persons_account_role_check'
    ) then
        alter table public.persons
            add constraint persons_account_role_check
            check (account_role in ('employee', 'department_manager', 'asset_manager', 'viewer', 'admin'));
    end if;
end;
$$;

alter table public.asset_assignments
    add column if not exists assignment_scope varchar not null default 'personal',
    add column if not exists custody_note text;

update public.asset_assignments
set assignment_scope = 'personal'
where assignment_scope is null;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'asset_assignments_assignment_scope_check'
    ) then
        alter table public.asset_assignments
            add constraint asset_assignments_assignment_scope_check
            check (assignment_scope in ('personal', 'department_shared', 'warehouse'));
    end if;
end;
$$;
