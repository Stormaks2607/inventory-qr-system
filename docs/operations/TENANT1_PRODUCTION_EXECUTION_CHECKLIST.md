# Tenant #1 Production Execution Checklist

Status: OPERATOR CHECKLIST - NOT AUTHORIZED FOR EXECUTION

Tenant #1 UUID: `00000000-0000-4000-8000-000000000001`

Do not place secrets, passwords, connection strings, backup files, or Storage exports in the repository.

## PRE-MIGRATION

- [ ] Production migration explicitly authorized.
- [ ] Operator assigned.
- [ ] Maintenance/write-freeze window approved.
- [ ] Current production application commit SHA recorded.
- [ ] Reviewed P1D commit SHA recorded.
- [ ] PR #11 migration drafts reviewed.
- [ ] PR #12 application changes reviewed.
- [ ] Production schema confirmed to match rehearsed assumptions.
- [ ] Storage backup/inventory approach confirmed.
- [ ] Rollback owner assigned.

## BACKUP

- [ ] Backup directory outside repository created.
- [ ] `roles.sql` created.
- [ ] `schema.sql` created.
- [ ] `data.sql` created.
- [ ] Dump files are non-zero.
- [ ] SHA256 hashes recorded.
- [ ] Manifest created.
- [ ] Critical tables confirmed in schema dump.
- [ ] Production row counts recorded.
- [ ] Storage objects enumerated/backed up.
- [ ] Backup timestamp recorded.

## WRITE FREEZE

- [ ] Normal production write access disabled or maintenance mode started.
- [ ] Freeze start timestamp recorded.
- [ ] Operator confirmed no normal user writes should occur.
- [ ] Final pre-foundation row counts recorded.

## FOUNDATION

- [ ] Fresh preflight from `TENANT_MIGRATION_PREFLIGHT.md` passed.
- [ ] `P1B_NOT_APPROVED_01_tenant_foundation.sql` source confirmed.
- [ ] Foundation migration executed in authorized production window.
- [ ] Tenant #1 row exists.
- [ ] 19/19 tenant-owned tables have `tenant_id`.
- [ ] Missing tenant = 0.
- [ ] Unexpected tenant = 0.
- [ ] Cross-owner mismatch = 0.
- [ ] Tenant-scoped duplicate checks = 0.
- [ ] Row counts preserved.
- [ ] GO-1 signed.

## P1D DEPLOY

- [ ] `DEFAULT_TENANT_ID=00000000-0000-4000-8000-000000000001` configured.
- [ ] `PUBLIC_BASE_URL` preserved.
- [ ] `INTERNAL_API_BASE_URL` preserved if configured.
- [ ] Existing production secrets preserved.
- [ ] Exact reviewed P1D commit deployed.
- [ ] Health endpoint passes.
- [ ] Login/logout passes.
- [ ] Dashboard opens.
- [ ] Assets list opens.
- [ ] Asset detail opens.
- [ ] Legacy `/view/{asset_tag}` route works.
- [ ] Legacy `/asset/{asset_tag}` route works.
- [ ] Audit log opens.
- [ ] Excel page opens.
- [ ] Controlled remarks edit/revert completed.
- [ ] New audit rows have Tenant #1 UUID.
- [ ] Missing tenant = 0 after write.
- [ ] GO-2 signed.

## PRE-CONSTRAINT VALIDATION

- [ ] Missing tenant = 0.
- [ ] Unexpected tenant = 0.
- [ ] Cross-owner mismatch = 0.
- [ ] Tenant-scoped duplicate checks = 0.
- [ ] One-shot constraint objects do not already exist unexpectedly.
- [ ] Schema still matches rehearsed shape.

## CONSTRAINTS

- [ ] `P1B_NOT_APPROVED_02_tenant_constraints.sql` source confirmed.
- [ ] Composite constraint migration executed in authorized production window.
- [ ] 35 expected constraints exist.
- [ ] 5 expected tenant-scoped indexes exist.
- [ ] All tenant constraints `convalidated = true`.
- [ ] App read smoke passes.
- [ ] Controlled application write passes.
- [ ] Missing tenant = 0 after write.
- [ ] GO-3 signed.

## NOT NULL

- [ ] `P1B_NOT_APPROVED_03_tenant_not_null.sql` source confirmed.
- [ ] Exactly 19 `tenant_id` columns exist.
- [ ] Before first execution all 19 are nullable.
- [ ] Missing tenant = 0.
- [ ] Unexpected tenant = 0.
- [ ] P1B-02 constraints remain validated.
- [ ] P1D app is live and tenant-aware.
- [ ] NOT NULL migration executed in authorized production window.
- [ ] 19/19 `tenant_id` columns are `is_nullable = NO`.
- [ ] Final controlled application write succeeds.
- [ ] GO-4 signed.

## FINAL SMOKE

- [ ] Health endpoint passes.
- [ ] Login passes.
- [ ] Dashboard opens.
- [ ] Assets list opens.
- [ ] Asset detail opens.
- [ ] Search works.
- [ ] QR `/view/{asset_tag}` works.
- [ ] Legacy `/asset/{asset_tag}` works.
- [ ] Global audit opens.
- [ ] Assignment History displays.
- [ ] Transfer History displays.
- [ ] Excel page opens.
- [ ] Classification dropdown loads.
- [ ] Sub-classification dropdown loads.
- [ ] Controlled remarks edit/revert works.
- [ ] Audit tenant verification passes.
- [ ] GO-5 signed.

## CLOSE WINDOW

- [ ] Write freeze lifted only after GO-5.
- [ ] Production status communicated.
- [ ] Backup artifacts retained outside repository.
- [ ] Final production commit SHA recorded.
- [ ] Final DB validation summary recorded.
- [ ] No unresolved STOP condition remains.

## POST-MIGRATION MONITORING

- [ ] Health checked after window.
- [ ] Render/application logs reviewed.
- [ ] Supabase logs/dashboard reviewed where available.
- [ ] Failed DB writes checked.
- [ ] Tenant constraint errors checked.
- [ ] Audit activity reviewed.
- [ ] Assignment/transfer errors checked.
- [ ] Unusual 4xx/5xx responses checked.
- [ ] Manual smoke repeated if errors appear.
