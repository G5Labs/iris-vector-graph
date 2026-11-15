# Lockplans lane: partial state (stopped by the coordinator, 2026-11-15 ~02:10 UTC)

AUDITD restored (EraseAll + PurgeAll under `locks.sh iris`: 0 nodes, 0 edges, 0 props, no probe table mapping,
$TLEVEL 0, locks released). Nothing in flight. Not done: no MATRIX-INPUT.json, no LOCKPLANS.md render, no
`findings/audit/zz-lockplans.json`. `lockplans/01.json`, `05.json`, `10.json` are drafts with `PENDING-LIVE` fields and
cite planned run ids that do not exist (`lockplans-01-setup-gate`, `lockplans-05-temporal-probes`,
`lockplans-10-nkg-probes`); `16.json` is a skeleton; 08/17 JSON not written. Do not integrate them as they are.

Registered runs: models (46/46 checks met) `lockplans-mc-{guard_insert,conn_mutex,tmp_conc,nkg_intern,setup_race}-{as-built,reviewed}`,
`lockplans-control-{same five}`; live `lockplans-08-17-guarded-insert` (run-2), `lockplans-08-17-guarded-insert-r3`.
Not registered: `$RUN_DIR/lockplans/guarded-insert/run-1-crashed-cleanup.log` (harness crash in my map cleanup after 8
decisive cases; same outcomes as run-2/run-3; kept as a failed attempt).

| Module | Done | Not done |
|---|---|---|
| 08 | Live: guarded CREATE loses B's committed write when a concurrent writer's transaction rolls back: 08-edge-matched (no edge after B answered ok), 08-node-nolabel (node gone, B's property orphaned); 08-node-label waits on the FK and is refused -121 (serializable); literal edge -119 refusal; map_sql_table waits on the row lock and is serial (holds); races 13/7 and 19/1 serializable/refused. Model guard_insert. Proposed verdict: violated (candidate finding F-C0811, not yet written). | finding record, 08.json, cell |
| 17 | Live: write_edges loses B's write on rollback (run-2, r3); write_nodes waits on FK, refused -121 (serializable). Model guard_insert (17 variants). Proposed: violated (candidate F-C1711). | finding, 17.json; delete/temporal/Meta obligations are delegated or not-needed (in reasoning only) |
| 16 | Model conn_mutex (HTTP as-built pass, sample as-built violation, controls caught). Probe `probes/conn_share.py` written, NOT run. | live overlap measurement, P-1605 verdict |
| 06 | `06.json` complete from existing evidence (F-C0670 live, HD-0602 live, models): proposed closed/fails. | none required beyond render |
| 01, 05, 10 | Reading drafts (`$RUN_DIR/lockplans/drafts/`), models setup_race / tmp_conc / nkg_intern registered; probes written, NOT run. | live probes, verdicts marked PENDING-LIVE |

Resume (each under the IRIS lock; ≤4 connections):

```bash
source experiment/playbook-completion/environment.sh; P=experiment/playbook-completion/lockplans/probes
bash experiment/playbook-completion/tools/locks.sh iris python $P/conn_share.py $RUN_DIR/lockplans/conn-share --seconds 12
bash experiment/playbook-completion/tools/locks.sh iris python $P/temporal_probes.py $RUN_DIR/lockplans/temporal
bash experiment/playbook-completion/tools/locks.sh iris python $P/nkg_probes.py $RUN_DIR/lockplans/nkg
bash experiment/playbook-completion/tools/locks.sh iris python $P/setup_probes.py $RUN_DIR/lockplans/setup   # last: runs initialize_schema twice
# then fill the PENDING-LIVE fields, write 08/16/17.json and zz-lockplans.json, and:
python3 experiment/playbook-completion/lockplans/render.py
```
