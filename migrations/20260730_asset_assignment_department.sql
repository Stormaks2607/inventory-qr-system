alter table public.asset_assignments
    add column if not exists assignment_department varchar(255);

update public.asset_assignments aa
set assignment_department = coalesce(
    nullif(aa.assignment_department, ''),
    (
        select nullif(p.department, '')
        from public.persons p
        where p.person_id = aa.person_id
        limit 1
    ),
    (
        select nullif(l.department, '')
        from public.locations l
        where l.location_id = aa.location_id
        limit 1
    )
)
where aa.assignment_department is null;
