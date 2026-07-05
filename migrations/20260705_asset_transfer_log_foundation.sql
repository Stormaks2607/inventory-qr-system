alter table asset_transfers
add column if not exists source_log_no integer,
add column if not exists source_row_number integer,
add column if not exists source_asset_type varchar,
add column if not exists asset_tag_snapshot varchar,
add column if not exists from_holder_name varchar,
add column if not exists to_holder_name varchar,
add column if not exists from_project_raw varchar,
add column if not exists to_project_raw varchar,
add column if not exists asset_status varchar,
add column if not exists asset_condition_description text;

create index if not exists idx_asset_transfers_asset_date
on asset_transfers (asset_id, transfer_date);

create index if not exists idx_asset_transfers_asset_tag_snapshot
on asset_transfers (asset_tag_snapshot);

create table if not exists asset_transfer_projects (
    transfer_project_id bigserial primary key,
    transfer_id bigint not null references asset_transfers(transfer_id) on delete cascade,
    direction varchar not null check (direction in ('from', 'to')),
    project_id bigint references projects(project_id),
    project_number_raw varchar,
    allocation_percent numeric,
    created_at timestamptz not null default now()
);

create index if not exists idx_asset_transfer_projects_transfer
on asset_transfer_projects (transfer_id);

create index if not exists idx_asset_transfer_projects_project
on asset_transfer_projects (project_id);
