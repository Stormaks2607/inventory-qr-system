# Tenant Migration Validation

Status: READ ONLY QUERIES. Do not run writes from this document.

Stable Tenant #1 UUID used in draft planning:

```sql
'00000000-0000-4000-8000-000000000001'::uuid
```

## Pre-Migration Validation Queries

### Row Counts

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

### Status Distribution

```sql
select current_status, count(*)
from public.assets
group by current_status
order by count(*) desc, current_status;

select status, count(*)
from public.asset_assignments
group by status
order by count(*) desc, status;
```

### Confirm Legacy Disposed Count

```sql
select count(*) as disposed_asset_count
from public.assets
where current_status = 'disposed';
```

Expected at planning time: `0`. If non-zero, preserve legacy support and do not invent `disposed_at`.

### Duplicate Asset Tags

```sql
select asset_tag_number, count(*)
from public.assets
where asset_tag_number is not null
group by asset_tag_number
having count(*) > 1
order by count(*) desc, asset_tag_number;
```

### Duplicate Project Identifiers

```sql
select project_number, count(*)
from public.projects
where project_number is not null
group by project_number
having count(*) > 1
order by count(*) desc, project_number;
```

### Null And Orphan References

```sql
select count(*) as assignments_missing_assets
from public.asset_assignments aa
left join public.assets a on a.asset_id = aa.asset_id
where aa.asset_id is not null and a.asset_id is null;

select count(*) as assignments_missing_persons
from public.asset_assignments aa
left join public.persons p on p.person_id = aa.person_id
where aa.person_id is not null and p.person_id is null;

select count(*) as assignments_missing_locations
from public.asset_assignments aa
left join public.locations l on l.location_id = aa.location_id
where aa.location_id is not null and l.location_id is null;

select count(*) as transfers_missing_assets
from public.asset_transfers t
left join public.assets a on a.asset_id = t.asset_id
where t.asset_id is not null and a.asset_id is null;

select count(*) as transfer_projects_missing_transfers
from public.asset_transfer_projects atp
left join public.asset_transfers t on t.transfer_id = atp.transfer_id
where atp.transfer_id is not null and t.transfer_id is null;

select count(*) as asset_projects_missing_assets
from public.asset_projects ap
left join public.assets a on a.asset_id = ap.asset_id
where ap.asset_id is not null and a.asset_id is null;

select count(*) as asset_projects_missing_projects
from public.asset_projects ap
left join public.projects p on p.project_id = ap.project_id
where ap.project_id is not null and p.project_id is null;

select count(*) as payments_missing_assets
from public.asset_payments pay
left join public.assets a on a.asset_id = pay.asset_id
where pay.asset_id is not null and a.asset_id is null;
```

## Post-Migration Staging Validation Queries

### Every Tenant-Owned Row Has Tenant

```sql
select 'assets' table_name, count(*) missing_tenant from public.assets where tenant_id is null
union all select 'asset_assignments', count(*) from public.asset_assignments where tenant_id is null
union all select 'asset_transfers', count(*) from public.asset_transfers where tenant_id is null
union all select 'asset_transfer_projects', count(*) from public.asset_transfer_projects where tenant_id is null
union all select 'asset_projects', count(*) from public.asset_projects where tenant_id is null
union all select 'asset_payments', count(*) from public.asset_payments where tenant_id is null
union all select 'persons', count(*) from public.persons where tenant_id is null
union all select 'person_responsibility_scopes', count(*) from public.person_responsibility_scopes where tenant_id is null
union all select 'locations', count(*) from public.locations where tenant_id is null
union all select 'projects', count(*) from public.projects where tenant_id is null
union all select 'donors', count(*) from public.donors where tenant_id is null
union all select 'audit_log', count(*) from public.audit_log where tenant_id is null
union all select 'organization_branding', count(*) from public.organization_branding where tenant_id is null;
```

Expected: all `0`.

### Zero Unexpected Tenant IDs

```sql
select 'assets' table_name, count(*) unexpected from public.assets where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_assignments', count(*) from public.asset_assignments where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_transfers', count(*) from public.asset_transfers where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_projects', count(*) from public.asset_projects where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_payments', count(*) from public.asset_payments where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'persons', count(*) from public.persons where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'locations', count(*) from public.locations where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'projects', count(*) from public.projects where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'donors', count(*) from public.donors where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'audit_log', count(*) from public.audit_log where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid;
```

Expected: all `0`.

### Tenant Uniqueness Valid

```sql
select tenant_id, asset_tag_number, count(*)
from public.assets
group by tenant_id, asset_tag_number
having count(*) > 1;

select tenant_id, project_number, count(*)
from public.projects
where project_number is not null
group by tenant_id, project_number
having count(*) > 1;
```

### No Cross-Owner Relationships

```sql
select count(*) as assignment_asset_mismatch
from public.asset_assignments aa
join public.assets a on a.asset_id = aa.asset_id
where aa.tenant_id <> a.tenant_id;

select count(*) as transfer_asset_mismatch
from public.asset_transfers t
join public.assets a on a.asset_id = t.asset_id
where t.tenant_id <> a.tenant_id;

select count(*) as project_asset_mismatch
from public.asset_projects ap
join public.assets a on a.asset_id = ap.asset_id
where ap.tenant_id <> a.tenant_id;

select count(*) as payment_asset_mismatch
from public.asset_payments pay
join public.assets a on a.asset_id = pay.asset_id
where pay.tenant_id <> a.tenant_id;
```

Expected: all `0`.

## Application Smoke Validation

After staging rehearsal:

- `/health` returns OK.
- Admin login/logout works.
- Asset list opens.
- Asset detail opens.
- Asset edit smoke test works in staging only.
- Assignment update smoke test works in staging only.
- Transfer history shows existing imported and web-created records.
- Legacy QR routes `/asset/{asset_tag}` and `/view/{asset_tag}` still resolve.
- Excel export completes.
- Re-uploading the export does not create unexpected diffs.
- `python -m pytest` passes.

## Rollback And Forward-Fix Summary

| Stage | Recovery |
| --- | --- |
| create tenants only | safe rollback possible before references |
| seed Tenant #1 | forward-fix preferred |
| add nullable columns | safe rollback possible before app dependency |
| backfill | forward-fix preferred; restore if broad corruption |
| add indexes | safe rollback generally possible |
| add unique constraints | drop constraint if incompatible data appears |
| add composite FKs | drop FK if staging finds false assumptions |
| set `tenant_id` not null | restore or forward-fix depending on failure |

No first migration may drop legacy columns, asset tags, IDs, status history, assignments, transfers, or audit history.
