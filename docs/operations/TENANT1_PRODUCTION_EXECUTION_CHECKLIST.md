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
- [ ] Exact reviewed PR #11 commit SHA recorded.
- [ ] PR #12 application changes reviewed.
- [ ] Production auto-deploy behavior recorded and controlled.
- [ ] Production schema confirmed to match rehearsed assumptions.
- [ ] Storage backup/inventory approach confirmed.
- [ ] Rollback owner assigned.
- [ ] Foundation post-COMMIT recovery decision owner assigned.

## BACKUP

- [ ] Backup directory outside repository created.
- [ ] `roles.sql` created.
- [ ] Raw `roles.sql` SHA256 recorded.
- [ ] Restore-safe `roles.restore.sql` prepared if restore rehearsal/recovery requires it.
- [ ] `roles.restore.sql` change from raw file documented exactly.
- [ ] `roles.restore.sql` SHA256 recorded.
- [ ] `schema.sql` created.
- [ ] `data.sql` created.
- [ ] Dump files are non-zero.
- [ ] SHA256 hashes recorded.
- [ ] Manifest created.
- [ ] Critical tables confirmed in schema dump.
- [ ] Production row counts recorded.
- [ ] Storage physical export complete for every current object in `private-inventory-docs`.
- [ ] Storage full object path inventory recorded.
- [ ] Storage object sizes recorded.
- [ ] Storage SHA256 hash recorded for each exported object.
- [ ] Storage exported object count matches Storage metadata count.
- [ ] Backup timestamp recorded.
- [ ] P1B-01 SHA256 recorded.
- [ ] P1B-02 SHA256 recorded.
- [ ] P1B-03 SHA256 recorded.
- [ ] Exact P1D SHA recorded.
- [ ] Exact production artifact/deploy commit SHA recorded.

## WRITE FREEZE

- [ ] Normal production write access disabled or maintenance mode started.
- [ ] Freeze start timestamp recorded.
- [ ] Operator confirmed no normal user writes should occur.
- [ ] Final pre-foundation row counts recorded.

## FOUNDATION

- [ ] Fresh preflight from `TENANT_MIGRATION_PREFLIGHT.md` passed.
- [ ] `P1B_NOT_APPROVED_01_tenant_foundation.sql` source confirmed.
- [ ] `P1B_NOT_APPROVED_01_tenant_foundation.sql` hash verified immediately before execution.
- [ ] Foundation migration executed in authorized production window.
- [ ] Tenant #1 row exists.
- [ ] 19/19 tenant-owned tables have `tenant_id`.
- [ ] Missing tenant = 0.
- [ ] Unexpected tenant = 0.
- [ ] Cross-owner mismatch = 0.
- [ ] Tenant-scoped duplicate checks = 0.
- [ ] Row counts preserved.
- [ ] Writes remain frozen after foundation COMMIT until P1D write smoke passes.
- [ ] GO-1 signed.

## P1D DEPLOY

- [ ] `DEFAULT_TENANT_ID=00000000-0000-4000-8000-000000000001` configured.
- [ ] `PUBLIC_BASE_URL` preserved.
- [ ] `INTERNAL_API_BASE_URL` preserved if configured.
- [ ] Existing production secrets preserved.
- [ ] Production auto-deploy behavior confirmed controlled before P1D runtime starts.
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
- [ ] `P1B_NOT_APPROVED_02_tenant_constraints.sql` hash verified immediately before execution.
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
- [ ] `P1B_NOT_APPROVED_03_tenant_not_null.sql` hash verified immediately before execution.
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
