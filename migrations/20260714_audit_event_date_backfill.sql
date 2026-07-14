alter table audit_log
add column if not exists event_date timestamptz;

alter table audit_log
add column if not exists event_key varchar(260);

update audit_log
set event_date = created_at
where event_date is null;

create index if not exists audit_log_event_date_idx on audit_log (event_date desc);
create unique index if not exists audit_log_event_key_idx on audit_log (event_key) where event_key is not null;
