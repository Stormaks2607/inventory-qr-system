alter table asset_projects
add column if not exists is_purchase_origin boolean;

update asset_projects
set is_purchase_origin = true
where is_purchase_origin is null;

alter table asset_projects
alter column is_purchase_origin set default false;

alter table asset_projects
alter column is_purchase_origin set not null;

create index if not exists idx_asset_projects_purchase_origin
on asset_projects (asset_id, is_purchase_origin);

create index if not exists idx_asset_projects_current
on asset_projects (asset_id, is_current);
