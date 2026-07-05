alter table assets
add column if not exists usage_type varchar not null default 'standard';

update assets
set usage_type = 'low_cost'
where asset_tag_number ilike '%-LC-%';

update assets
set usage_type = 'standard'
where usage_type is null or usage_type = '';

alter table assets
drop constraint if exists assets_usage_type_check;

alter table assets
add constraint assets_usage_type_check
check (usage_type in ('standard', 'low_cost'));

create index if not exists idx_assets_usage_type
on assets (usage_type);
