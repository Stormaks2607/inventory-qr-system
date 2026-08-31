# Inventory QR — Product Charter

## Purpose

Inventory QR is evolving from an internal QR-based asset register into a commercial multi-tenant Asset Lifecycle Management SaaS platform.

The product should help organizations control physical and IT assets throughout their operational lifecycle: registration, assignment, transfer, physical verification, inventory, condition review, disposal and retirement.

## Initial target market

Commercial V1 is primarily designed for:

- NGOs and INGOs;
- small and medium distributed organizations;
- organizations with project/donor-funded assets;
- teams that need lightweight asset control without implementing a full ERP/EAM suite.

The architecture should remain generic enough to support broader commercial customers later.

## Product interfaces

The platform is expected to expose the same business logic through multiple channels:

- Web application;
- REST/API clients;
- Telegram bot / Telegram Mini App;
- future mobile application;
- future messenger adapters such as Teams, WhatsApp or other channels;
- future external integrations.

Business rules must live in the backend/domain layer rather than being duplicated in each client.

## Core product domains

1. Organizations / tenants
2. Users, memberships and organization-scoped roles
3. Persons / employees
4. Assets
5. Locations
6. Projects and donors
7. Assignments and custody
8. Transfers / movement history
9. Asset observations (photo, GPS, timestamp, actor)
10. Inventory sessions and reconciliation
11. Lifecycle reviews
12. Approval and disposal
13. Audit / evidence trail
14. Reporting and export
15. Integration/channel adapters

## Commercial architecture principles

### Multi-tenant by design

Commercial data must be organization-scoped. Shared infrastructure may be used for normal customers, while the architecture should allow future dedicated database/storage deployments for enterprise customers.

### API-centric

Web, mobile and messaging interfaces must converge on the same domain services and APIs.

### Deployment portability

Render and Supabase are current infrastructure choices, not permanent business-architecture dependencies. The product should be deployable through a documented Docker contract and should isolate provider-specific integrations.

### PostgreSQL as the transactional source of truth

The core data model remains relational. Business integrity should be enforced server-side and, where appropriate, by database constraints.

### Evidence and auditability

Important asset decisions must be reconstructable: who acted, what changed, when, why, under which organization, and with what supporting evidence.

### Backward-compatible evolution

The current pilot is a live system. Large architectural changes must use additive migrations, staging validation, rollback plans and regression tests.

## Pilot model

The current real organization acts as Design Partner #1.

Pilot feedback is treated as product evidence, not automatic product requirements.

Expected decision cycle:

Observation → Evidence → Problem → Hypothesis → Issue → Implementation → Test → Pilot validation → Keep / Change / Revert.

## Standards direction

The product should be designed with future alignment in mind for:

- ISO/IEC 19770-1 — IT Asset Management;
- ISO 55001 — Asset Management;
- ISO/TS 55010 — alignment of financial and non-financial asset management;
- ISO/IEC 25010 / 25051 — software product quality/conformity;
- future ISO/IEC 27001 readiness for the operating organization;
- IAS 16 / IPSAS 45 compatibility at the integration/accounting boundary.

No certification or compliance claim should be made without formal assessment.

## Explicit non-goals for Commercial V1

Commercial V1 is not intended to become:

- a full accounting ledger;
- a depreciation/NBV engine;
- an ERP replacement;
- a procurement system;
- an HRIS;
- a full enterprise EAM comparable to SAP.

## Release model

- `v0.x` — internal pilot and external beta;
- `v1.0` — first commercial production release after tenant isolation, security, backup/restore, onboarding, support and release-readiness gates are passed.
