# Tenant Migration Matrix

Status: PLANNING ONLY. Validate against staging schema before execution.

General rule: add nullable `tenant_id` first, backfill, validate, then add indexes, tenant-scoped uniqueness, composite FKs, and finally `NOT NULL`.

| Table | Tenant-owned | Current PK | Current FK notes | Add tenant_id | Nullability transition | Backfill source | Required index | Tenant-scoped uniqueness | Composite FK plan | Compatibility concerns | Validation query | Rollback/forward-fix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `assets` | YES | `asset_id` | parent for assignments, transfers, projects, payments | yes | nullable -> not null | stable Tenant #1 UUID | `(tenant_id, asset_id)`, `(tenant_id, asset_tag_number)` | `(tenant_id, asset_tag_number)` | parent unique `(tenant_id, asset_id)` | legacy QR uses `asset_tag_number`; tags must not change | count null/unexpected tenant; duplicate tags per tenant | forward-fix preferred after backfill |
| `asset_assignments` | YES | `assignment_id` | `asset_id`, `person_id`, `location_id` | yes | nullable -> not null | from parent asset or stable Tenant #1 | `(tenant_id, asset_id)`, `(tenant_id, person_id)`, `(tenant_id, location_id)` | none initially | FK `(tenant_id, asset_id)` -> assets; `(tenant_id, person_id)` -> persons; `(tenant_id, location_id)` -> locations | `status` is technical assignment status, not lifecycle | no null tenant; no cross-owner refs | forward-fix preferred |
| `asset_transfers` | YES | `transfer_id` | `asset_id`, from/to person IDs | yes | nullable -> not null | from parent asset or stable Tenant #1 | `(tenant_id, transfer_id)`, `(tenant_id, asset_id)` | optional `(tenant_id, transfer_key)` if transfer_key exists later | FK to assets and persons by tenant | imported Transfer log rows may have holder names without person IDs | no orphan asset/person refs | forward-fix preferred |
| `asset_transfer_projects` | YES | `transfer_project_id` | `transfer_id`, `project_id` | yes | nullable -> not null | from parent transfer | `(tenant_id, transfer_id)`, `(tenant_id, project_id)` | none initially | FK `(tenant_id, transfer_id)` -> asset_transfers; `(tenant_id, project_id)` -> projects | `project_number_raw` may exist without project_id | no orphan transfer/project refs | forward-fix preferred |
| `asset_projects` | YES | `asset_project_id` | `asset_id`, `project_id`, `donor_id` | yes | nullable -> not null | from parent asset | `(tenant_id, asset_id)`, `(tenant_id, project_id)`, `(tenant_id, donor_id)` | none initially | FK to assets/projects/donors by tenant | purchase-origin/current flags must be preserved | no orphan project/donor refs | forward-fix preferred |
| `asset_payments` | YES | `payment_id` | `asset_id` | yes | nullable -> not null | from parent asset | `(tenant_id, asset_id)`, `(tenant_id, payment_id)` | optional `(tenant_id, asset_id, payment_number)` later | FK `(tenant_id, asset_id)` -> assets | payment notes and EUR equivalent must be preserved | no orphan asset refs | forward-fix preferred |
| `persons` | YES | `person_id` | parent for assignments/scopes/auth-like fields | yes | nullable -> not null | stable Tenant #1 UUID | `(tenant_id, person_id)` | likely `(tenant_id, lower(email))` where email not null; maybe phone later | parent unique `(tenant_id, person_id)` | currently mixes employee and account concerns | no null tenant; duplicate emails per tenant | forward-fix preferred |
| `person_responsibility_scopes` | YES | `scope_id` | `person_id`, `location_id` | yes | nullable -> not null | from parent person | `(tenant_id, person_id)`, `(tenant_id, location_id)` | none initially | FK to persons/locations by tenant | used by department manager scoping | no orphan person/location refs | forward-fix preferred |
| `locations` | YES | `location_id` | parent for assignments/scopes | yes | nullable -> not null | stable Tenant #1 UUID | `(tenant_id, location_id)`, `(tenant_id, city, office_name)` | `(tenant_id, city, office_name)` after cleanup | parent unique `(tenant_id, location_id)` | city/office naming still evolving | duplicate city/office per tenant | forward-fix preferred |
| `projects` | YES | `project_id` | parent for asset_projects/transfer projects | yes | nullable -> not null | stable Tenant #1 UUID | `(tenant_id, project_id)`, `(tenant_id, project_number)` | `(tenant_id, project_number)` | parent unique `(tenant_id, project_id)` | project_number currently globally unique in practice | duplicate project numbers per tenant | forward-fix preferred |
| `donors` | YES | `donor_id` | parent for asset_projects | yes | nullable -> not null | stable Tenant #1 UUID | `(tenant_id, donor_id)`, `(tenant_id, donor_name)` | `(tenant_id, donor_name)` | parent unique `(tenant_id, donor_id)` | donor display names may be codes | duplicate donor names per tenant | forward-fix preferred |
| `audit_log` | YES | `audit_id` | weak references by entity_type/entity_id | yes | nullable -> not null | stable Tenant #1 UUID | `(tenant_id, created_at desc)`, `(tenant_id, entity_type, entity_id)` | optional `(tenant_id, event_key)` where event_key not null | composite FK impractical because entity_id is polymorphic | history must remain visible after migration | no null tenant; counts preserved | forward-fix preferred |
| `organization_branding` | CONDITIONAL | `tenant_key` | no technical tenant FK yet | yes, but special handling | nullable -> not null after tenant mapping | map `tenant_key='default'` to Tenant #1 | `(tenant_id)`, `(tenant_id, tenant_key)` | `(tenant_id, tenant_key)` | FK `tenant_id` -> tenants | existing `tenant_key` is branding slug, not security identity | every branding row has tenant_id | forward-fix preferred |

## Tenant-Scoped Business Identifiers

Must become tenant-scoped before commercial multi-tenant use:

- `assets.asset_tag_number`: `UNIQUE (tenant_id, asset_tag_number)`.
- `projects.project_number`: `UNIQUE (tenant_id, project_number)`.
- `persons.email`: `UNIQUE (tenant_id, lower(email)) WHERE email IS NOT NULL`.
- `persons.phone` or Telegram phone if formalized later.
- `locations.city + office_name`: `UNIQUE (tenant_id, city, office_name)` when office data is clean.
- `donors.donor_name`: `UNIQUE (tenant_id, donor_name)`.
- Future disposal case number: `UNIQUE (tenant_id, disposal_case_number)`.
- Future inventory session number: `UNIQUE (tenant_id, inventory_session_number)`.

Technical IDs may remain globally unique.

## Composite FK Plan

Parent unique pairs:

```sql
assets: unique (tenant_id, asset_id)
persons: unique (tenant_id, person_id)
locations: unique (tenant_id, location_id)
projects: unique (tenant_id, project_id)
donors: unique (tenant_id, donor_id)
asset_transfers: unique (tenant_id, transfer_id)
```

Child relationships:

```text
asset_assignments(tenant_id, asset_id) -> assets(tenant_id, asset_id)
asset_assignments(tenant_id, person_id) -> persons(tenant_id, person_id)
asset_assignments(tenant_id, location_id) -> locations(tenant_id, location_id)
asset_transfers(tenant_id, asset_id) -> assets(tenant_id, asset_id)
asset_transfers(tenant_id, from_person_id) -> persons(tenant_id, person_id)
asset_transfers(tenant_id, to_person_id) -> persons(tenant_id, person_id)
asset_transfer_projects(tenant_id, transfer_id) -> asset_transfers(tenant_id, transfer_id)
asset_transfer_projects(tenant_id, project_id) -> projects(tenant_id, project_id)
asset_projects(tenant_id, asset_id) -> assets(tenant_id, asset_id)
asset_projects(tenant_id, project_id) -> projects(tenant_id, project_id)
asset_projects(tenant_id, donor_id) -> donors(tenant_id, donor_id)
asset_payments(tenant_id, asset_id) -> assets(tenant_id, asset_id)
person_responsibility_scopes(tenant_id, person_id) -> persons(tenant_id, person_id)
person_responsibility_scopes(tenant_id, location_id) -> locations(tenant_id, location_id)
organization_branding(tenant_id) -> tenants(tenant_id)
```

Composite FK is impractical for `audit_log.entity_id` because the target table depends on `entity_type`. Alternative: tenant-filter all audit reads/writes and add validation queries by entity type where practical.
