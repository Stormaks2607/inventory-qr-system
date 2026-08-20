# Tenant Migration Matrix

Status: PLANNING ONLY. Validate against restored staging schema before execution.

Current restored public schema: 19 tables. No current public table may remain accidentally unclassified for tenant migration planning.

General rule: add nullable `tenant_id` first, backfill from the authoritative parent, validate, then add indexes, tenant-scoped uniqueness, composite FKs, and finally `NOT NULL` only after application TenantContext/repositories are live.

Current gate status:

- Tenant #1 foundation: PASSED IN ISOLATED STAGING.
- Composite tenant constraints: PASSED IN ISOLATED STAGING.
- P1D tenant-aware application writes: PASSED IN ISOLATED STAGING.
- `tenant_id` NOT NULL: NEXT SEPARATE ENFORCEMENT GATE.
- Production tenant migration: NOT AUTHORIZED.
- Tenant #2: NOT AUTHORIZED.

## Classification Legend

| Classification | Meaning |
| --- | --- |
| `ROOT` | Tenant-owned operational or master table backfilled directly to Tenant #1 for the current single-organization dataset. |
| `REFERENCE` | Tenant-local reference data. Tenant B may define different values. |
| `DERIVED_CHILD` | Tenant is derived from an authoritative parent relationship. Do not silently assign Tenant #1 if the parent is missing. |
| `POLYMORPHIC_REFERENCE` | References more than one possible entity type. Tenant must be stored and filtered, but composite FK may be impractical. |

## 19-Table Matrix

| Table | Classification | Tenant ownership | Backfill source | Tenant FK/index strategy | Uniqueness implications | Special risks |
| --- | --- | --- | --- | --- | --- | --- |
| `assets` | `ROOT` | Tenant-owned asset registry | Tenant #1 UUID | FK `tenant_id -> tenants`; indexes `(tenant_id, asset_id)`, `(tenant_id, asset_tag_number)` | Current global unique: `asset_tag_number`, `inventory_code`; future likely tenant-scoped: `unique (tenant_id, asset_tag_number)` | Legacy QR depends on asset tags; tags must not change. `inventory_code` needs a Tenant #2 product decision before any destructive uniqueness change. |
| `asset_assignments` | `DERIVED_CHILD` | Tenant-owned assignment history/current holder rows | `assets.tenant_id` via `asset_id` | indexes `(tenant_id, asset_id)`, `(tenant_id, person_id)`, `(tenant_id, location_id)`; composite FKs to assets/persons/locations | none initially | `status` is assignment/technical status, not lifecycle. |
| `asset_transfers` | `DERIVED_CHILD` | Tenant-owned movement records | `assets.tenant_id` via `asset_id` | unique parent pair `(tenant_id, transfer_id)`; indexes `(tenant_id, transfer_id)`, `(tenant_id, asset_id)`; composite FKs to assets, from/to persons, and from/to locations | future optional transfer key uniqueness | Imported Transfer log rows may preserve names without person or location IDs. |
| `asset_transfer_projects` | `DERIVED_CHILD` | Tenant-owned transfer project allocation rows | `asset_transfers.tenant_id` via `transfer_id` | indexes `(tenant_id, transfer_id)`, `(tenant_id, project_id)`; composite FKs to transfer/projects | none initially | `project_number_raw` may exist without resolved `project_id`. |
| `asset_projects` | `DERIVED_CHILD` | Tenant-owned asset funding/current project rows | `assets.tenant_id` via `asset_id` | indexes `(tenant_id, asset_id)`, `(tenant_id, project_id)`, `(tenant_id, donor_id)`; composite FKs to assets/projects/donors | none initially | Purchase-origin/current flags must be preserved. |
| `asset_payments` | `DERIVED_CHILD` | Tenant-owned asset payment rows | `assets.tenant_id` via `asset_id` | indexes `(tenant_id, asset_id)`, `(tenant_id, payment_id)`; composite FK to assets | optional future `(tenant_id, asset_id, payment_number)` | Payment notes and EUR equivalent must be preserved. |
| `persons` | `ROOT` | Tenant-owned employee/account-like rows | Tenant #1 UUID | unique parent pair `(tenant_id, person_id)`; index `(tenant_id, person_id)` | future candidate `(tenant_id, lower(email))` after identity rules | Legacy table mixes employee and account concerns. |
| `person_responsibility_scopes` | `DERIVED_CHILD` | Tenant-owned department/location manager scopes | `persons.tenant_id` via `person_id` | indexes `(tenant_id, person_id)`, `(tenant_id, location_id)`; composite FKs to persons/locations | none initially | Used by department manager scoping. |
| `locations` | `ROOT` | Tenant-owned office/location reference data | Tenant #1 UUID | unique parent pair `(tenant_id, location_id)`; index `(tenant_id, location_id)` | future candidate `(tenant_id, city, office_name)` after cleanup | City/office naming is still evolving. |
| `projects` | `REFERENCE` | Tenant-owned project reference data | Tenant #1 UUID | unique parent pair `(tenant_id, project_id)`; indexes `(tenant_id, project_id)`, `(tenant_id, project_number)` | Current global unique: `project_number`; future tenant-scoped: `unique (tenant_id, project_number)` | Project numbers currently globally unique in practice. |
| `donors` | `REFERENCE` | Tenant-owned donor reference data | Tenant #1 UUID | unique parent pair `(tenant_id, donor_id)`; index `(tenant_id, donor_id)` | future candidate `(tenant_id, donor_name)` | Donor names may be codes, aliases, or abbreviations. |
| `audit_log` | `POLYMORPHIC_REFERENCE` | Tenant-owned audit events | Tenant #1 UUID | indexes `(tenant_id, created_at desc)`, `(tenant_id, entity_type, entity_id)` | optional `(tenant_id, event_key)` where available | `entity_id` is polymorphic; composite FK is impractical. |
| `organization_branding` | `ROOT` with legacy key limitation | Tenant-owned branding settings | Tenant #1 UUID | index `(tenant_id)`; FK `tenant_id -> tenants` | Current global unique/PK: `tenant_key`; future `unique (tenant_id, branding_key)` after redesign | Do not destructively change in P1B. |
| `asset_classifications` | `REFERENCE` | Tenant-local taxonomy | Tenant #1 UUID | unique parent pair `(tenant_id, classification_id)`; indexes `(tenant_id, classification_id)`, `(tenant_id, classification_name)` | Current global unique: `classification_name`; future tenant-scoped: `unique (tenant_id, classification_name)` | Existing global `unique (classification_name)` blocks Tenant #2 independent taxonomy until reworked. |
| `asset_sub_classifications` | `DERIVED_CHILD` | Tenant-local taxonomy child rows | `asset_classifications.tenant_id` via `classification_id` | unique parent pair `(tenant_id, sub_classification_id)`; indexes `(tenant_id, classification_id)`, `(tenant_id, sub_classification_name)`; composite FK to classifications | Current unique: `(classification_id, sub_classification_name)`; future tenant-aware: `unique (tenant_id, classification_id, sub_classification_name)` | Current constraint is not a cross-tenant name blocker because `classification_id` is globally unique and tenants will have different classification rows. |
| `asset_history` | `DERIVED_CHILD` | Tenant-owned legacy asset history rows | `assets.tenant_id` via `asset_id` | index `(tenant_id, asset_id)`; composite FKs to assets and persons for `changed_by` | none initially | Currently zero rows; do not let future rows remain global. |
| `inventory_sessions` | `ROOT` | Tenant-owned inventory session root rows | Tenant #1 UUID for existing single-organization rows | unique parent pair `(tenant_id, session_id)`; indexes `(tenant_id, session_id)`, `(tenant_id, created_by)`, `(tenant_id, location_id)`; composite FKs to persons/locations | future candidate `(tenant_id, session_name)` or session number if business rule exists | Currently zero rows; direct Tenant #1 backfill is acceptable only for this restored pilot dataset. |
| `inventory_records` | `DERIVED_CHILD` | Tenant-owned inventory scan/result rows | `inventory_sessions.tenant_id` via `session_id`; validate against `assets.tenant_id` | indexes `(tenant_id, session_id)`, `(tenant_id, asset_id)`, `(tenant_id, scanned_by)`; composite FKs to sessions/assets/persons | none initially | Constraint enforcement must stop if session and asset tenants differ. |
| `notifications` | `DERIVED_CHILD` plus polymorphic entity reference | Tenant-owned person notification rows | `persons.tenant_id` via `person_id` | indexes `(tenant_id, person_id)`, `(tenant_id, created_at desc)`, `(tenant_id, delivery_status, created_at desc)`; composite FK to persons | none initially | `entity_id` is polymorphic; do not invent an FK. Tenant filter prevents cross-tenant notification leakage. |

## Tenant-Scoped Business Identifiers

Confirmed current global unique constraints preserved in P1B:

- `assets.asset_tag_number`.
- `assets.inventory_code`.
- `projects.project_number`.
- `asset_classifications.classification_name`.
- `organization_branding.tenant_key`.

These do not block Tenant #1 staging rehearsal. They require explicit product/architecture decisions before Tenant #2.

Future tenant-scoped constraints:

- `assets.asset_tag_number`: `unique (tenant_id, asset_tag_number)`.
- `projects.project_number`: `unique (tenant_id, project_number)`.
- `asset_classifications.classification_name`: `unique (tenant_id, classification_name)`.
- `asset_sub_classifications.sub_classification_name`: `unique (tenant_id, classification_id, sub_classification_name)`.

`assets.inventory_code` Tenant #2 gate: decide whether `inventory_code` remains platform-global, or becomes tenant-local with `unique (tenant_id, inventory_code)`. Do not remove the existing global constraint in P1B.

Future candidate constraints requiring business confirmation:

- `persons.email`: possible `unique (tenant_id, lower(email)) where email is not null`.
- `locations.city + office_name`: possible `unique (tenant_id, city, office_name)` when office data is clean.
- `donors.donor_name`: possible `unique (tenant_id, donor_name)`.
- Future disposal case number: `unique (tenant_id, disposal_case_number)`.
- Future inventory session number/name: `unique (tenant_id, inventory_session_number)` or `unique (tenant_id, session_name)` after rules are confirmed.

Technical IDs may remain globally unique.

## Composite FK Plan

Parent unique pairs:

```text
assets(tenant_id, asset_id)
persons(tenant_id, person_id)
locations(tenant_id, location_id)
projects(tenant_id, project_id)
donors(tenant_id, donor_id)
asset_transfers(tenant_id, transfer_id)
asset_classifications(tenant_id, classification_id)
asset_sub_classifications(tenant_id, sub_classification_id)
inventory_sessions(tenant_id, session_id)
```

Child relationships:

```text
asset_assignments(tenant_id, asset_id) -> assets(tenant_id, asset_id)
asset_assignments(tenant_id, person_id) -> persons(tenant_id, person_id)
asset_assignments(tenant_id, location_id) -> locations(tenant_id, location_id)
asset_transfers(tenant_id, asset_id) -> assets(tenant_id, asset_id)
asset_transfers(tenant_id, from_person_id) -> persons(tenant_id, person_id)
asset_transfers(tenant_id, to_person_id) -> persons(tenant_id, person_id)
asset_transfers(tenant_id, from_location_id) -> locations(tenant_id, location_id)
asset_transfers(tenant_id, to_location_id) -> locations(tenant_id, location_id)
asset_transfer_projects(tenant_id, transfer_id) -> asset_transfers(tenant_id, transfer_id)
asset_transfer_projects(tenant_id, project_id) -> projects(tenant_id, project_id)
asset_projects(tenant_id, asset_id) -> assets(tenant_id, asset_id)
asset_projects(tenant_id, project_id) -> projects(tenant_id, project_id)
asset_projects(tenant_id, donor_id) -> donors(tenant_id, donor_id)
asset_payments(tenant_id, asset_id) -> assets(tenant_id, asset_id)
person_responsibility_scopes(tenant_id, person_id) -> persons(tenant_id, person_id)
person_responsibility_scopes(tenant_id, location_id) -> locations(tenant_id, location_id)
organization_branding(tenant_id) -> tenants(tenant_id)
asset_sub_classifications(tenant_id, classification_id) -> asset_classifications(tenant_id, classification_id)
asset_history(tenant_id, asset_id) -> assets(tenant_id, asset_id)
asset_history(tenant_id, changed_by) -> persons(tenant_id, person_id)
inventory_sessions(tenant_id, created_by) -> persons(tenant_id, person_id)
inventory_sessions(tenant_id, location_id) -> locations(tenant_id, location_id)
inventory_records(tenant_id, session_id) -> inventory_sessions(tenant_id, session_id)
inventory_records(tenant_id, asset_id) -> assets(tenant_id, asset_id)
inventory_records(tenant_id, scanned_by) -> persons(tenant_id, person_id)
notifications(tenant_id, person_id) -> persons(tenant_id, person_id)
```

Composite FK is impractical for `audit_log.entity_id` and `notifications.entity_id` because the target table depends on `entity_type`. Alternative: tenant-filter all reads/writes and add validation queries by entity type where practical.

## Known Legacy Limitations

- `organization_branding` currently uses `tenant_key` as PK/global unique. P1B must not destructively redesign it.
- `asset_classifications.classification_name` is globally unique today. This must be removed/reworked before Tenant #2 independent taxonomy.
- `asset_sub_classifications(classification_id, sub_classification_name)` is not itself a cross-tenant naming blocker because `classification_id` is globally unique. The tenant-aware index/FK still improves isolation and consistency.
- `assets.inventory_code` is globally unique today. Decide platform-global versus tenant-local semantics before Tenant #2.

## Storage Tenant #2 Gate

Current Storage object path is globally scoped:

```text
private-inventory-docs/sync/official_inventory.xlsx
```

This is acceptable for Tenant #1 only. Before Tenant #2, define tenant-scoped Storage ownership, for example:

```text
private-inventory-docs/<tenant_id>/sync/official_inventory.xlsx
```

or another explicitly tenant-isolated bucket/path strategy. Future asset photos, inventory evidence, disposal evidence, and attachments must never use globally shared unscoped paths.
