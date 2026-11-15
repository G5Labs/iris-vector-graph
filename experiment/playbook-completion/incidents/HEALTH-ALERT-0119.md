# Container health: alert state 01:19-~02:18 UTC (diagnosed; no recovery action needed)

**Observed.** Docker health `unhealthy` (failing streak 42-45 by 02:16) from shortly after the deliberate crash at
01:19:08 UTC; `iris qlist` reported `alert`; `/irisHealth.sh` fails for any status other than `ok` or `warn`.
Evidence preserved at `health/20261114T021707Z` under $RUN_DIR
(docker inspect with the health log, qlist, iris list, messages.log, alerts.log, the health script, SHA256SUMS).

**Cause (alerts.log, severity 2).**
1. 01:19:10 "Previous system shutdown was abnormal, system forced down or crashed": the orchestrator's deliberate
   SIGKILL of the container in the crash world (`live-crash-world-r2`), under the IRIS lock, with lanes notified.
2. 01:31:40 and 01:46:40 "License limit exceeded" (1, then 316 times): the validation lane's spec-236 scratch-namespace
   fixture (namespace IVG236VAL, created 01:31:18) opened more connections than the Community 8-connection cap.
   Its runs `$RUN_DIR/validation/scratch-236-*` contain licence errors; they are infrastructure results and are being
   rerun with fewer connections under the lock (originals kept).

**Outcome.** No alert was cleared and nothing was restarted: the instance lowered its state from `alert` to `warn`
once no new severity-2 alert followed, and Docker health returned to `healthy` (streak 0) at about 02:18 UTC
(`$SYSTEM.Monitor.State()` = 1 warn, 3 alerts). The service fault was real but external to the product (licence cap,
deliberate crash); no product result depends on the alert. The crash-durability finding F-C1102 is attributed to the
tested setting `SynchCommit=0`.
