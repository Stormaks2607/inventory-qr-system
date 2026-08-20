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
union all select 'asset_classifications', count(*) from public.asset_classifications
union all select 'asset_sub_classifications', count(*) from public.asset_sub_classifications
union all select 'asset_history', count(*) from public.asset_history
union all select 'inventory_sessions', count(*) from public.inventory_sessions
union all select 'inventory_records', count(*) from public.inventory_records
union all select 'notifications', count(*) from public.notifications
order by table_name;
```

Confirmed staging counts for addendum tables:

```text
asset_classifications      8
asset_sub_classifications  36
asset_history              0
inventory_sessions         0
inventory_records          0
notifications              0
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

### Duplicate Business Identifiers

```sql
select asset_tag_number, count(*)
from public.assets
where asset_tag_number is not null
group by asset_tag_number
having count(*) > 1
order by count(*) desc, asset_tag_number;

select project_number, count(*)
from public.projects
where project_number is not null
group by project_number
having count(*) > 1
order by count(*) desc, project_number;

select inventory_code, count(*)
from public.assets
where inventory_code is not null
group by inventory_code
having count(*) > 1
order by count(*) desc, inventory_code;

select classification_name, count(*)
from public.asset_classifications
where classification_name is not null
group by classification_name
having count(*) > 1
order by count(*) desc, classification_name;

select classification_id, sub_classification_name, count(*)
from public.asset_sub_classifications
where sub_classification_name is not null
group by classification_id, sub_classification_name
having count(*) > 1
order by count(*) desc, classification_id, sub_classification_name;
```

Current global unique constraints preserved in P1B:

- `assets.asset_tag_number`;
- `assets.inventory_code`;
- `projects.project_number`;
- `asset_classifications.classification_name`;
- `organization_branding.tenant_key`.

P1B validation should confirm they remain compatible with Tenant #1 rehearsal. It must not remove or weaken them.

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

select count(*) as sub_classifications_missing_classification
from public.asset_sub_classifications asc_row
left join public.asset_classifications ac on ac.classification_id = asc_row.classification_id
where asc_row.classification_id is not null and ac.classification_id is null;

select count(*) as history_missing_assets
from public.asset_history ah
left join public.assets a on a.asset_id = ah.asset_id
where ah.asset_id is not null and a.asset_id is null;

select count(*) as history_missing_changed_by
from public.asset_history ah
left join public.persons p on p.person_id = ah.changed_by
where ah.changed_by is not null and p.person_id is null;

select count(*) as inventory_sessions_missing_created_by
from public.inventory_sessions s
left join public.persons p on p.person_id = s.created_by
where s.created_by is not null and p.person_id is null;

select count(*) as inventory_sessions_missing_locations
from public.inventory_sessions s
left join public.locations l on l.location_id = s.location_id
where s.location_id is not null and l.location_id is null;

select count(*) as inventory_records_missing_sessions
from public.inventory_records ir
left join public.inventory_sessions s on s.session_id = ir.session_id
where ir.session_id is not null and s.session_id is null;

select count(*) as inventory_records_missing_assets
from public.inventory_records ir
left join public.assets a on a.asset_id = ir.asset_id
where ir.asset_id is not null and a.asset_id is null;

select count(*) as inventory_records_missing_scanned_by
from public.inventory_records ir
left join public.persons p on p.person_id = ir.scanned_by
where ir.scanned_by is not null and p.person_id is null;

select count(*) as notifications_missing_persons
from public.notifications n
left join public.persons p on p.person_id = n.person_id
where n.person_id is not null and p.person_id is null;
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
union all select 'organization_branding', count(*) from public.organization_branding where tenant_id is null
union all select 'asset_classifications', count(*) from public.asset_classifications where tenant_id is null
union all select 'asset_sub_classifications', count(*) from public.asset_sub_classifications where tenant_id is null
union all select 'asset_history', count(*) from public.asset_history where tenant_id is null
union all select 'inventory_sessions', count(*) from public.inventory_sessions where tenant_id is null
union all select 'inventory_records', count(*) from public.inventory_records where tenant_id is null
union all select 'notifications', count(*) from public.notifications where tenant_id is null;
```

Expected: all `0`.

If a relational child cannot derive `tenant_id` from its authoritative parent, constraint enforcement MUST NOT proceed.

### Zero Unexpected Tenant IDs

```sql
select 'assets' table_name, count(*) unexpected from public.assets where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_assignments', count(*) from public.asset_assignments where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_transfers', count(*) from public.asset_transfers where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_transfer_projects', count(*) from public.asset_transfer_projects where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_projects', count(*) from public.asset_projects where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_payments', count(*) from public.asset_payments where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'persons', count(*) from public.persons where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'person_responsibility_scopes', count(*) from public.person_responsibility_scopes where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'locations', count(*) from public.locations where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'projects', count(*) from public.projects where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'donors', count(*) from public.donors where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'audit_log', count(*) from public.audit_log where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'organization_branding', count(*) from public.organization_branding where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_classifications', count(*) from public.asset_classifications where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_sub_classifications', count(*) from public.asset_sub_classifications where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'asset_history', count(*) from public.asset_history where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'inventory_sessions', count(*) from public.inventory_sessions where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'inventory_records', count(*) from public.inventory_records where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid
union all select 'notifications', count(*) from public.notifications where tenant_id <> '00000000-0000-4000-8000-000000000001'::uuid;
```

Expected: all `0`.

### Tenant Uniqueness Valid

```sql
select tenant_id, asset_tag_number, count(*)
from public.assets
where asset_tag_number is not null
group by tenant_id, asset_tag_number
having count(*) > 1;

select tenant_id, project_number, count(*)
from public.projects
where project_number is not null
group by tenant_id, project_number
having count(*) > 1;

-- Future candidate only. P1B preserves existing global inventory_code uniqueness
-- until Product Owner decides platform-global vs tenant-local behavior.
select tenant_id, inventory_code, count(*)
from public.assets
where inventory_code is not null
group by tenant_id, inventory_code
having count(*) > 1;

select tenant_id, classification_name, count(*)
from public.asset_classifications
where classification_name is not null
group by tenant_id, classification_name
having count(*) > 1;

select tenant_id, classification_id, sub_classification_name, count(*)
from public.asset_sub_classifications
where sub_classification_name is not null
group by tenant_id, classification_id, sub_classification_name
having count(*) > 1;
```

Tenant #2 inventory-code gate: before commercial multi-tenant onboarding, decide whether `inventory_code` remains globally unique across the SaaS platform or becomes tenant-local with `unique (tenant_id, inventory_code)`.

Sub-classification wording: current `asset_sub_classifications(classification_id, sub_classification_name)` uniqueness is not itself a cross-tenant name blocker because `classification_id` is globally unique and tenants will have distinct classification rows. Tenant-aware checks still validate isolation and consistency.

### No Cross-Owner Relationships

```sql
select count(*) as assignment_asset_mismatch
from public.asset_assignments aa
join public.assets a on a.asset_id = aa.asset_id
where aa.tenant_id <> a.tenant_id;

select count(*) as assignment_person_mismatch
from public.asset_assignments aa
join public.persons p on p.person_id = aa.person_id
where aa.tenant_id <> p.tenant_id;

select count(*) as assignment_location_mismatch
from public.asset_assignments aa
join public.locations l on l.location_id = aa.location_id
where aa.tenant_id <> l.tenant_id;

select count(*) as transfer_asset_mismatch
from public.asset_transfers t
join public.assets a on a.asset_id = t.asset_id
where t.tenant_id <> a.tenant_id;

select count(*) as transfer_from_person_mismatch
from public.asset_transfers t
join public.persons p on p.person_id = t.from_person_id
where t.tenant_id <> p.tenant_id;

select count(*) as transfer_to_person_mismatch
from public.asset_transfers t
join public.persons p on p.person_id = t.to_person_id
where t.tenant_id <> p.tenant_id;

select count(*) as transfer_from_location_mismatch
from public.asset_transfers t
join public.locations l on l.location_id = t.from_location_id
where t.tenant_id <> l.tenant_id;

select count(*) as transfer_to_location_mismatch
from public.asset_transfers t
join public.locations l on l.location_id = t.to_location_id
where t.tenant_id <> l.tenant_id;

select count(*) as project_asset_mismatch
from public.asset_projects ap
join public.assets a on a.asset_id = ap.asset_id
where ap.tenant_id <> a.tenant_id;

select count(*) as payment_asset_mismatch
from public.asset_payments pay
join public.assets a on a.asset_id = pay.asset_id
where pay.tenant_id <> a.tenant_id;

select count(*) as sub_classification_classification_mismatch
from public.asset_sub_classifications asc_row
join public.asset_classifications ac on ac.classification_id = asc_row.classification_id
where asc_row.tenant_id <> ac.tenant_id;

select count(*) as history_asset_mismatch
from public.asset_history ah
join public.assets a on a.asset_id = ah.asset_id
where ah.tenant_id <> a.tenant_id;

select count(*) as history_person_mismatch
from public.asset_history ah
join public.persons p on p.person_id = ah.changed_by
where ah.tenant_id <> p.tenant_id;

select count(*) as inventory_session_person_mismatch
from public.inventory_sessions s
join public.persons p on p.person_id = s.created_by
where s.tenant_id <> p.tenant_id;

select count(*) as inventory_session_location_mismatch
from public.inventory_sessions s
join public.locations l on l.location_id = s.location_id
where s.tenant_id <> l.tenant_id;

select count(*) as inventory_record_session_mismatch
from public.inventory_records ir
join public.inventory_sessions s on s.session_id = ir.session_id
where ir.tenant_id <> s.tenant_id;

select count(*) as inventory_record_asset_mismatch
from public.inventory_records ir
join public.assets a on a.asset_id = ir.asset_id
where ir.tenant_id <> a.tenant_id;

select count(*) as inventory_record_person_mismatch
from public.inventory_records ir
join public.persons p on p.person_id = ir.scanned_by
where ir.tenant_id <> p.tenant_id;

select count(*) as notification_person_mismatch
from public.notifications n
join public.persons p on p.person_id = n.person_id
where n.tenant_id <> p.tenant_id;
```

Expected: all `0`.

### Tenant ID NOT NULL Validation

Run after `P1B_NOT_APPROVED_03_tenant_not_null.sql` in isolated STAGING.

```sql
select table_name, column_name, is_nullable
from information_schema.columns
where table_schema = 'public'
  and column_name = 'tenant_id'
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

Expected: `19` rows and every row has `is_nullable = NO`.

Retain the existing post-migration validation gates after NOT NULL enforcement:

- missing tenant = `0`;
- unexpected tenant = `0`;
- cross-owner mismatch = `0`;
- tenant constraints remain `convalidated = true`;
- expected tenant-scoped indexes remain present.

`notifications.entity_id` is polymorphic and is intentionally excluded from FK-style validation unless checked by entity-type-specific queries in a later application phase.

## Tenant #2 Commercial Isolation Gates

These are not Tenant #1 rehearsal blockers, but must be closed before onboarding Tenant #2:

- Decide whether `assets.inventory_code` remains platform-global or becomes tenant-local with `unique (tenant_id, inventory_code)`.
- Rework global `asset_classifications.classification_name` uniqueness before independent tenant taxonomy.
- Define tenant-scoped Storage ownership. Current workbook object path `private-inventory-docs/sync/official_inventory.xlsx` is Tenant #1 only.
- Ensure future asset photos, inventory evidence, disposal evidence, and attachments use tenant-isolated bucket/path ownership and never globally shared unscoped paths.

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
- Classification and sub-classification dropdowns still load.
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

No first migration may drop legacy columns, asset tags, IDs, status history, assignments, transfers, audit history, taxonomy rows, inventory rows, or notifications.
