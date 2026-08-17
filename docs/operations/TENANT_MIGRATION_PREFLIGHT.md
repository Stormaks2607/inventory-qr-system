# Tenant Migration Preflight

Status: READ ONLY. Run against isolated STAGING before executing any P1B draft migration. Do not run against PILOT_PRODUCTION for rehearsal.

Purpose: verify the actual restored Supabase schema and data shape before tenant migration. Repository migration files are not a substitute for inspecting the live staging schema restored from backup.

If any required table, column, PK, FK, unique constraint, index, row count, or data relationship differs from assumptions, stop the rehearsal and update the plan before running migration SQL.

## Required Tables

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'assets',
    'asset_assignments',
    'asset_transfers',
    'asset_transfer_projects',
    'asset_projects',
    'asset_payments',
    'persons',
    'person_responsibility_scopes',
    'locations',
    'projects',
    'donors',
    'audit_log',
    'organization_branding',
    'asset_classifications',
    'asset_sub_classifications',
    'asset_history',
    'inventory_sessions',
    'inventory_records',
    'notifications'
  )
order by table_name;
```

Expected: 19 rows, every listed table exists.

## Row Counts

```sql
select 'assets' table_name, count(*) row_count from public.assets
union all select 'asset_assignments', count(*) from public.asset_assignments
union all select 'asset_transfers', count(*) from public.asset_transfers
union all select 'asset_transfer_projects', count(*) from public.asset_transfer_projects
union all select 'asset_projects', count(*) from public.asset_projects
union all select 'asset_payments', count(*) from public.asset_payments
union all select 'persons', count(*) from public.persons
union all select 'person_responsibility_scopes', count(*) from public.person_responsibility_scopes
union all select 'locations', count(*) from public.locations
union all select 'projects', count(*) from public.projects
union all select 'donors', count(*) from public.donors
union all select 'audit_log', count(*) from public.audit_log
union all select 'organization_branding', count(*) from public.organization_branding
union all select 'asset_classifications', count(*) from public.asset_classifications
union all select 'asset_sub_classifications', count(*) from public.asset_sub_classifications
union all select 'asset_history', count(*) from public.asset_history
union all select 'inventory_sessions', count(*) from public.inventory_sessions
union all select 'inventory_records', count(*) from public.inventory_records
union all select 'notifications', count(*) from public.notifications
order by table_name;
```

Confirmed staging counts for the six addendum tables:

```text
asset_classifications      8
asset_sub_classifications  36
asset_history              0
inventory_sessions         0
inventory_records          0
notifications              0
```

## Columns, Types, And Nullability

```sql
select
  table_name,
  column_name,
  data_type,
  udt_name,
  is_nullable,
  column_default
from information_schema.columns
where table_schema = 'public'
  and table_name in (
    'assets',
    'asset_assignments',
    'asset_transfers',
    'asset_transfer_projects',
    'asset_projects',
    'asset_payments',
    'persons',
    'person_responsibility_scopes',
    'locations',
    'projects',
    'donors',
    'audit_log',
    'organization_branding',
    'asset_classifications',
    'asset_sub_classifications',
    'asset_history',
    'inventory_sessions',
    'inventory_records',
    'notifications'
  )
order by table_name, ordinal_position;
```

Important addendum column checks:

```sql
select table_name, column_name, data_type, udt_name, is_nullable
from information_schema.columns
where table_schema = 'public'
  and (
    (table_name = 'asset_classifications' and column_name in ('classification_id', 'classification_name', 'description', 'created_at', 'updated_at'))
    or (table_name = 'asset_sub_classifications' and column_name in ('sub_classification_id', 'classification_id', 'sub_classification_name', 'description', 'created_at', 'updated_at'))
    or (table_name = 'asset_history' and column_name in ('history_id', 'asset_id', 'action_type', 'changed_by', 'changed_at', 'old_values', 'new_values'))
    or (table_name = 'inventory_sessions' and column_name in ('session_id', 'session_name', 'start_date', 'end_date', 'status', 'created_by', 'location_id', 'notes', 'created_at', 'updated_at'))
    or (table_name = 'inventory_records' and column_name in ('record_id', 'session_id', 'asset_id', 'scanned_at', 'scanned_by', 'location_found', 'condition', 'photo_url', 'discrepancy_notes', 'gps_coordinates', 'created_at', 'updated_at'))
    or (table_name = 'notifications' and column_name in ('notification_id', 'person_id', 'entity_type', 'entity_id', 'notification_type', 'title', 'message', 'priority', 'delivery_channel', 'delivery_status', 'sent_at', 'delivered_at', 'read_at', 'action_url', 'action_taken', 'action_taken_at', 'retry_count', 'error_message', 'created_at', 'updated_at'))
  )
order by table_name, column_name;
```

## Primary Keys, Foreign Keys, And Unique Constraints

```sql
select
  tc.table_name,
  tc.constraint_name,
  tc.constraint_type,
  string_agg(kcu.column_name, ', ' order by kcu.ordinal_position) as columns
from information_schema.table_constraints tc
left join information_schema.key_column_usage kcu
  on kcu.constraint_schema = tc.constraint_schema
 and kcu.constraint_name = tc.constraint_name
where tc.table_schema = 'public'
  and tc.table_name in (
    'assets',
    'asset_assignments',
    'asset_transfers',
    'asset_transfer_projects',
    'asset_projects',
    'asset_payments',
    'persons',
    'person_responsibility_scopes',
    'locations',
    'projects',
    'donors',
    'audit_log',
    'organization_branding',
    'asset_classifications',
    'asset_sub_classifications',
    'asset_history',
    'inventory_sessions',
    'inventory_records',
    'notifications'
  )
  and tc.constraint_type in ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
group by tc.table_name, tc.constraint_name, tc.constraint_type
order by tc.table_name, tc.constraint_type, tc.constraint_name;
```

Expected addendum relationships:

- `asset_classifications`: PK `classification_id`, unique `classification_name`.
- `asset_sub_classifications`: PK `sub_classification_id`, FK `classification_id -> asset_classifications`, unique `(classification_id, sub_classification_name)`.
- `asset_history`: PK `history_id`, FK `asset_id -> assets`, FK `changed_by -> persons`.
- `inventory_sessions`: PK `session_id`, FK `created_by -> persons`, FK `location_id -> locations`.
- `inventory_records`: PK `record_id`, FK `session_id -> inventory_sessions`, FK `asset_id -> assets`, FK `scanned_by -> persons`.
- `notifications`: PK `notification_id`, FK `person_id -> persons`; `entity_id` is polymorphic and must not receive an invented FK.

Confirmed current global unique constraints to record:

- `assets.asset_tag_number`;
- `assets.inventory_code`;
- `projects.project_number`;
- `asset_classifications.classification_name`;
- `organization_branding.tenant_key`.

These do not block Tenant #1 staging rehearsal. They must be reviewed before Tenant #2. Do not drop or destructively change them in P1B.

## Indexes

```sql
select
  schemaname,
  tablename,
  indexname,
  indexdef
from pg_indexes
where schemaname = 'public'
  and tablename in (
    'assets',
    'asset_assignments',
    'asset_transfers',
    'asset_transfer_projects',
    'asset_projects',
    'asset_payments',
    'persons',
    'person_responsibility_scopes',
    'locations',
    'projects',
    'donors',
    'audit_log',
    'organization_branding',
    'asset_classifications',
    'asset_sub_classifications',
    'asset_history',
    'inventory_sessions',
    'inventory_records',
    'notifications'
  )
order by tablename, indexname;
```

## Existing Tenant Draft Objects

```sql
select table_name, column_name, data_type, udt_name
from information_schema.columns
where table_schema = 'public'
  and column_name = 'tenant_id'
order by table_name;

select constraint_name, table_name, constraint_type
from information_schema.table_constraints
where table_schema = 'public'
  and constraint_name like '%tenant%'
order by table_name, constraint_name;
```

Expected before P1B rehearsal: no tenant migration objects unless a prior failed rehearsal was intentionally retained for review.

## Orphan Checks

### Existing 13-Table Relationships

```sql
select aa.assignment_id, aa.asset_id
from public.asset_assignments aa
left join public.assets a on a.asset_id = aa.asset_id
where aa.asset_id is not null and a.asset_id is null;

select aa.assignment_id, aa.person_id
from public.asset_assignments aa
left join public.persons p on p.person_id = aa.person_id
where aa.person_id is not null and p.person_id is null;

select aa.assignment_id, aa.location_id
from public.asset_assignments aa
left join public.locations l on l.location_id = aa.location_id
where aa.location_id is not null and l.location_id is null;

select t.transfer_id, t.asset_id
from public.asset_transfers t
left join public.assets a on a.asset_id = t.asset_id
where t.asset_id is not null and a.asset_id is null;

select atp.transfer_project_id, atp.transfer_id
from public.asset_transfer_projects atp
left join public.asset_transfers t on t.transfer_id = atp.transfer_id
where atp.transfer_id is not null and t.transfer_id is null;

select ap.asset_project_id, ap.asset_id
from public.asset_projects ap
left join public.assets a on a.asset_id = ap.asset_id
where ap.asset_id is not null and a.asset_id is null;

select ap.asset_project_id, ap.project_id
from public.asset_projects ap
left join public.projects p on p.project_id = ap.project_id
where ap.project_id is not null and p.project_id is null;

select pay.payment_id, pay.asset_id
from public.asset_payments pay
left join public.assets a on a.asset_id = pay.asset_id
where pay.asset_id is not null and a.asset_id is null;

select prs.scope_id, prs.person_id
from public.person_responsibility_scopes prs
left join public.persons p on p.person_id = prs.person_id
where prs.person_id is not null and p.person_id is null;
```

### Addendum Table Relationships

```sql
select asc_row.sub_classification_id, asc_row.classification_id
from public.asset_sub_classifications asc_row
left join public.asset_classifications ac on ac.classification_id = asc_row.classification_id
where ac.classification_id is null;

select ah.history_id, ah.asset_id
from public.asset_history ah
left join public.assets a on a.asset_id = ah.asset_id
where ah.asset_id is not null and a.asset_id is null;

select ah.history_id, ah.changed_by
from public.asset_history ah
left join public.persons p on p.person_id = ah.changed_by
where ah.changed_by is not null and p.person_id is null;

select s.session_id, s.created_by
from public.inventory_sessions s
left join public.persons p on p.person_id = s.created_by
where s.created_by is not null and p.person_id is null;

select s.session_id, s.location_id
from public.inventory_sessions s
left join public.locations l on l.location_id = s.location_id
where s.location_id is not null and l.location_id is null;

select ir.record_id, ir.session_id
from public.inventory_records ir
left join public.inventory_sessions s on s.session_id = ir.session_id
where ir.session_id is not null and s.session_id is null;

select ir.record_id, ir.asset_id
from public.inventory_records ir
left join public.assets a on a.asset_id = ir.asset_id
where ir.asset_id is not null and a.asset_id is null;

select ir.record_id, ir.scanned_by
from public.inventory_records ir
left join public.persons p on p.person_id = ir.scanned_by
where ir.scanned_by is not null and p.person_id is null;

select n.notification_id, n.person_id
from public.notifications n
left join public.persons p on p.person_id = n.person_id
where n.person_id is not null and p.person_id is null;
```

## Duplicate And Taxonomy Checks

```sql
select asset_tag_number, count(*)
from public.assets
where asset_tag_number is not null
group by asset_tag_number
having count(*) > 1;

select project_number, count(*)
from public.projects
where project_number is not null
group by project_number
having count(*) > 1;

select inventory_code, count(*)
from public.assets
where inventory_code is not null
group by inventory_code
having count(*) > 1;

select classification_name, count(*)
from public.asset_classifications
where classification_name is not null
group by classification_name
having count(*) > 1;

select classification_id, sub_classification_name, count(*)
from public.asset_sub_classifications
where sub_classification_name is not null
group by classification_id, sub_classification_name
having count(*) > 1;
```

Current global uniqueness limitations are known legacy constraints. Do not remove them in P1B.

Tenant #2 gates:

- decide whether `inventory_code` remains globally unique across the SaaS platform or becomes tenant-local with `unique (tenant_id, inventory_code)`;
- remove or rework global `asset_classifications.classification_name` uniqueness before independent tenant taxonomy;
- preserve `asset_sub_classifications(classification_id, sub_classification_name)` wording correctly: it is tenant-aware by parent row in practice because `classification_id` is globally unique, although tenant-scoped index/FK remains useful for isolation.

## Status Checks

```sql
select current_status, count(*)
from public.assets
group by current_status
order by count(*) desc, current_status;

select count(*) as disposed_asset_count
from public.assets
where current_status = 'disposed';
```

Expected planning assumption: `disposed_asset_count = 0`.

## Tenant #2 Non-SQL Isolation Gates

These do not block Tenant #1 staging rehearsal, but must be recorded before commercial multi-tenant onboarding:

- Decide whether `assets.inventory_code` remains globally unique or becomes tenant-local with `unique (tenant_id, inventory_code)`.
- Rework global `asset_classifications.classification_name` uniqueness before independent Tenant #2 taxonomy.
- Define tenant-scoped Storage ownership. Current path `private-inventory-docs/sync/official_inventory.xlsx` is acceptable for Tenant #1 only. Future path strategy must be tenant-isolated, for example `private-inventory-docs/<tenant_id>/sync/official_inventory.xlsx`.
- Future asset photos, inventory evidence, disposal evidence, and attachments must not use globally shared unscoped paths.

## Stop Conditions

Stop staging rehearsal before migration if:

- any required table or column is missing or has an unexpected type;
- existing constraints differ from the draft assumptions;
- duplicate asset tags or project numbers exist;
- duplicate inventory codes exist unexpectedly under the current global rule;
- taxonomy uniqueness differs from expected legacy constraints;
- any orphan rows exist in relational child tables;
- any addendum child table cannot derive tenant from its authoritative parent;
- row counts are unexpectedly large for a single transaction;
- `current_status = 'disposed'` is non-zero and lifecycle handling has not been reviewed;
- tenant migration objects already exist and were not intentionally retained for review.
