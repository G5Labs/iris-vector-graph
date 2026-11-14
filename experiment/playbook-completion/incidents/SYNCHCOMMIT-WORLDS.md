# Deliberate container crashes and the SynchCommit reconfiguration (2026-11-14)

All under `tools/locks.sh iris`, while no lane used the container (Q18f). Raw logs: `$RUN_DIR/crash-repeat/`.

| UTC | Action | Evidence |
|---|---|---|
| 16:14:43 | pre-state: Docker healthy, `iris qlist` ok, `iris.cpf` line 327 `SynchCommit=0` | `$RUN_DIR/crash-repeat/pre-sc0.txt` |
| ~16:15 | first attempt refused before any trial (the harness read `Config.Journal`, which has no SynchCommit; nothing ran) | `$RUN_DIR/crash-repeat/sc0-refused-wrong-config-class/` |
| ~16:20-16:31 | six trials under SynchCommit=0: each `docker kill -s KILL` of the container while or right after a 36,000-operation commit, then `docker start`, wait healthy | `live-crash-repeat-sc0` |
| 16:31:53 | `Config.Miscellaneous.Modify(SynchCommit=1)` in %SYS (BEFORE=0 AFTER=1), then `docker restart` (healthy after 8 s), `iris.cpf` 327 `SynchCommit=1` | `$RUN_DIR/crash-repeat/sc1-procedure.log` |
| 16:32-16:43 | six trials under SynchCommit=1 (same kills and restarts) | `live-crash-repeat-sc1` |
| 16:43:56 | restore: `Config.Miscellaneous.Modify(SynchCommit=0)` (BEFORE=1 AFTER=0), `docker restart`, `iris.cpf` 327 `SynchCommit=0`, `qlist` ok, healthy (16:44:03) | `$RUN_DIR/crash-repeat/sc1-procedure.log` |

Each SIGKILL is an abnormal shutdown that IRIS records in `messages.log` and may raise as an alert (as on 2026-11-14 01:19,
`incidents/HEALTH-ALERT-0119.md`); no alert was cleared by the audit. After the last restart Docker reported healthy and
`iris qlist` ok. Every durability result of the audit is attributed to the SynchCommit setting it ran under.
