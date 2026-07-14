create table if not exists audit_log (
    audit_id bigserial primary key,
    created_at timestamptz not null default now(),
    actor varchar(120),
    source varchar(120),
    entity_type varchar(80) not null,
    entity_id bigint,
    entity_label varchar(200),
    action varchar(80) not null,
    field_name varchar(120),
    old_value text,
    new_value text,
    summary text
);

create index if not exists audit_log_created_at_idx on audit_log (created_at desc);
create index if not exists audit_log_entity_idx on audit_log (entity_type, entity_id);
