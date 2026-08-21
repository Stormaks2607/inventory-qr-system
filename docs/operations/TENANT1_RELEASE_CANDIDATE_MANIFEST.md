# Tenant #1 Release Candidate Manifest

Status: RELEASE CANDIDATE RECORD - NOT AUTHORIZED FOR PRODUCTION EXECUTION

Created at: 2026-08-21T14:08:32.9940910+03:00

This manifest records the integration dry-run branch that combines the reviewed Tenant #1 migration package, tenant-aware application, and production runbook. It does not authorize production execution.

## Source SHAs

| Source | SHA |
| --- | --- |
| origin/main base | `076c03456924d3c3e6da5a86a40b792d8403aedd` |
| PR #11 reviewed head | `904ca382c57329c84d77bee6b2a933dbc3d4a70b` |
| PR #12 reviewed head | `8b1851adc3d32121a08a7c9ea3c11edbde897fd4` |
| PR #13 reviewed head | `0d13d4532c05ae3b30f8d7f35a710c3415a16f3d` |
| pre-manifest integrated RC head | `953f60c` |
| final RC SHA | Recorded as the PR head/returned SHA after this manifest commit is created. |

## Migration Artifact SHA256

| Artifact | SHA256 |
| --- | --- |
| `migrations/drafts/P1B_NOT_APPROVED_01_tenant_foundation.sql` | `67085206081759667A16A49FBA7448324EBA98B517BCB543A35AC8842C0F6DD7` |
| `migrations/drafts/P1B_NOT_APPROVED_02_tenant_constraints.sql` | `E16BF1A21E2601A0C679AF2BF1C9B1DF90D612B2F07CED6A8BE6D090AAA1FB10` |
| `migrations/drafts/P1B_NOT_APPROVED_03_tenant_not_null.sql` | `9124C2151A25FD859318714C7ED3D3C2DD2A182E6B1CCB2F15B2A3A31EB6A929` |

## Integration Order

1. PR #11 migration/docs package.
2. PR #12 P1D tenant-aware application.
3. PR #13 production runbook/checklist.

No merge conflicts occurred during this integration dry-run.

## Static Safety Summary

P1B-01:

- `BEGIN` / `COMMIT` present.
- Tenant #1 UUID unchanged: `00000000-0000-4000-8000-000000000001`.
- 19 tenant-owned public tables receive nullable `tenant_id`.
- Backfill behavior is preserved.

P1B-02:

- `BEGIN` / `COMMIT` present.
- 35 tenant constraints present in the draft.
- 5 tenant-scoped unique indexes present in the draft.
- Transfer `from_location_id` and `to_location_id` composite tenant FKs are preserved.
- No active NOT NULL enforcement is added here; the only `SET NOT NULL` text is a commented example.

P1B-03:

- `BEGIN` / `COMMIT` present.
- 19 `ALTER COLUMN tenant_id SET NOT NULL` statements.
- No data repair logic.
- No RLS.
- No Tenant #2 changes.

P1D application behavior:

- Effective application files in the RC match reviewed PR #12 for `app.py`, `bot.py`, `data_access`, and `tests`.
- No functional P1D behavior change was introduced by integration.

## Required Environment Variables

Names only, no secret values:

- `DEFAULT_TENANT_ID`
- `PUBLIC_BASE_URL`
- `INTERNAL_API_BASE_URL`

Expected Tenant #1 value:

```text
DEFAULT_TENANT_ID=00000000-0000-4000-8000-000000000001
```

## Test Results

- `git diff --check` passed.
- `python -m pytest` -> `53 passed in 2.67s`.
- `python -m compileall app.py bot.py data_access tests` -> successful.

## Staging Validation Summary

The integrated RC is based on changes that were individually rehearsed in isolated STAGING:

- production backup/restore rehearsal succeeded;
- Storage restore was validated by SHA256;
- Tenant #1 foundation populated all 19 tenant-owned public tables;
- missing tenant, unexpected tenant, and cross-owner mismatch checks were zero;
- P1D tenant-aware writes passed;
- P1B-02 composite tenant constraints passed;
- P1B-03 NOT NULL enforcement passed;
- final live application audit write passed under NOT NULL.

## Checklist Dry-Run Summary

READY BEFORE WINDOW:

- reviewed PR #11/#12/#13 heads verified;
- migration artifacts integrated in one RC branch;
- production runbook and checklist present;
- required migration paths exist in the RC.

MUST BE DONE AT GO-0:

- production authorization;
- fresh production backup;
- physical Storage export;
- production row counts;
- artifact SHA/hash pinning;
- maintenance/write-freeze authorization;
- deployment-control confirmation.

MUST BE DONE DURING WINDOW:

- write freeze;
- P1B-01 foundation;
- P1D deploy after GO-1;
- pre-constraint controlled write;
- P1B-02 constraints;
- P1B-03 NOT NULL;
- final smoke.

POST-WINDOW:

- health checks;
- application/log review;
- audit review;
- assignment/transfer error review;
- constraint error monitoring.

Ambiguity requiring operator input:

- production auto-deploy behavior;
- exact deployment mechanism for reviewed P1D/RC artifact;
- how to prevent unrelated `main` commits from deploying during the window.

## Known Remaining Limitations

- Assignment and transfer creation are not fully atomic.
- Tenant #2 global uniqueness gates remain open.
- Storage Tenant #2 isolation remains future work.
- Broader read isolation, RLS, and account/tenant membership remain future work.

Production execution status: NOT AUTHORIZED.
