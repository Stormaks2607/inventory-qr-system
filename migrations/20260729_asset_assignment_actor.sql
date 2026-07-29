alter table public.asset_assignments
    add column if not exists created_by varchar(120),
    add column if not exists updated_by varchar(120);

update public.asset_assignments
set
    created_by = coalesce(
        created_by,
        case
            when notes ilike '%offboarding%' then 'Offboarding'
            when notes ilike '%Excel%' or notes ilike '%Position from Excel%' then 'Excel import'
            else 'Legacy data'
        end
    ),
    updated_by = coalesce(
        updated_by,
        case
            when notes ilike '%offboarding%' then 'Offboarding'
            when notes ilike '%Excel%' or notes ilike '%Position from Excel%' then 'Excel import'
            else 'Legacy data'
        end
    )
where created_by is null
   or updated_by is null;
