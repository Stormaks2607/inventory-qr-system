# Tenant Migration Preflight

Status: READ ONLY. Run against STAGING before executing any P1B draft migration.

Purpose: verify the actual Supabase schema and data shape before migration. Repository migration files are not a substitute for inspecting the live staging schema restored from backup.

If any required table, column, PK, FK, unique constraint, index, or data relationship differs from assumptions, stop the rehearsal and update the plan before running migration SQL.

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
    'organization_branding'
  )
order by table_name;
```

Expected: every listed table exists.

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
    'organization_branding'
  )
order by table_name, ordinal_position;
```

Important columns to confirm before rehearsal:

```sql
select table_name, column_name, data_type, udt_name, is_nullable
from information_schema.columns
where table_schema = 'public'
  and (
    (table_name = 'assets' and column_name in ('asset_id', 'asset_tag_number', 'current_status'))
    or (table_name = 'asset_assignments' and column_name in ('assignment_id', 'asset_id', 'person_id', 'location_id', 'status'))
    or (table_name = 'asset_transfers' and column_name in ('transfer_id', 'asset_id', 'from_person_id', 'to_person_id'))
    or (table_name = 'asset_transfer_projects' and column_name in ('transfer_project_id', 'transfer_id', 'project_id'))
    or (table_name = 'asset_projects' and column_name in ('asset_project_id', 'asset_id', 'project_id', 'donor_id'))
    or (table_name = 'asset_payments' and column_name in ('payment_id', 'asset_id'))
    or (table_name = 'persons' and column_name in ('person_id', 'email'))
    or (table_name = 'person_responsibility_scopes' and column_name in ('scope_id', 'person_id', 'location_id'))
    or (table_name = 'locations' and column_name in ('location_id', 'city', 'office_name'))
    or (table_name = 'projects' and column_name in ('project_id', 'project_number'))
    or (table_name = 'donors' and column_name in ('donor_id', 'donor_name'))
    or (table_name = 'audit_log' and column_name in ('audit_id', 'entity_type', 'entity_id', 'event_key'))
    or (table_name = 'organization_branding' and column_name in ('tenant_key'))
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
    'organization_branding'
  )
  and tc.constraint_type in ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
group by tc.table_name, tc.constraint_name, tc.constraint_type
order by tc.table_name, tc.constraint_type, tc.constraint_name;
```

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
    'organization_branding'
  )
order by tablename, indexname;
```

## Existing Tenant Draft Objects

The foundation draft is partially idempotent, but the enforcement draft is one-shot. Confirm whether any tenant migration objects already exist:

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

## Row Counts For Lock Planning

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
order by table_name;
```

## Data Anomaly Checks

### Orphan Assignments

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
```

### Orphan Transfers

```sql
select t.transfer_id, t.asset_id
from public.asset_transfers t
left join public.assets a on a.asset_id = t.asset_id
where t.asset_id is not null and a.asset_id is null;

select t.transfer_id, t.from_person_id
from public.asset_transfers t
left join public.persons p on p.person_id = t.from_person_id
where t.from_person_id is not null and p.person_id is null;

select t.transfer_id, t.to_person_id
from public.asset_transfers t
left join public.persons p on p.person_id = t.to_person_id
where t.to_person_id is not null and p.person_id is null;
```

### Orphan Transfer Projects

```sql
select atp.transfer_project_id, atp.transfer_id
from public.asset_transfer_projects atp
left join public.asset_transfers t on t.transfer_id = atp.transfer_id
where atp.transfer_id is not null and t.transfer_id is null;

select atp.transfer_project_id, atp.project_id
from public.asset_transfer_projects atp
left join public.projects p on p.project_id = atp.project_id
where atp.project_id is not null and p.project_id is null;
```

### Orphan Asset Projects And Payments

```sql
select ap.asset_project_id, ap.asset_id
from public.asset_projects ap
left join public.assets a on a.asset_id = ap.asset_id
where ap.asset_id is not null and a.asset_id is null;

select ap.asset_project_id, ap.project_id
from public.asset_projects ap
left join public.projects p on p.project_id = ap.project_id
where ap.project_id is not null and p.project_id is null;

select ap.asset_project_id, ap.donor_id
from public.asset_projects ap
left join public.donors d on d.donor_id = ap.donor_id
where ap.donor_id is not null and d.donor_id is null;

select pay.payment_id, pay.asset_id
from public.asset_payments pay
left join public.assets a on a.asset_id = pay.asset_id
where pay.asset_id is not null and a.asset_id is null;
```

### Orphan Responsibility Scopes

```sql
select prs.scope_id, prs.person_id
from public.person_responsibility_scopes prs
left join public.persons p on p.person_id = prs.person_id
where prs.person_id is not null and p.person_id is null;

select prs.scope_id, prs.location_id
from public.person_responsibility_scopes prs
left join public.locations l on l.location_id = prs.location_id
where prs.location_id is not null and l.location_id is null;
```

### Duplicate Or Invalid Identifiers

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

select count(*) as null_asset_tags
from public.assets
where asset_tag_number is null or btrim(asset_tag_number) = '';

select count(*) as null_project_numbers
from public.projects
where project_number is null or btrim(project_number) = '';
```

### Status Checks

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

## Stop Conditions

Stop staging rehearsal before migration if:

- any required table or column is missing or has an unexpected type;
- existing constraints differ from the draft assumptions;
- duplicate asset tags or project numbers exist;
- any orphan rows exist in relational child tables;
- row counts are unexpectedly large for a single transaction;
- `current_status = 'disposed'` is non-zero and lifecycle handling has not been reviewed.
