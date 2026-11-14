# USER redeploy by a module-08 unit test (local convention, not a product change)

**What happened.** At 2026-11-13 23:01:48-23:01:50 UTC (USER class dictionary TimeChanged 67887,82908-82910) breadth
lane B's module-08 worker ran `tests/unit/test_r115_read_only_verdict_independent.py` without `IVG_NAMESPACE`. Its
IRIS-backed test class's session fixture (`tests/conftest.py:_deploy_objectscript`) reloaded into namespace USER (the
validation lane's) every pin class whose hash differed from `^IVGDeployed(USER, file)`: about 45 classes recompiled
from the unchanged pin sources; 3 MCP classes failed (`%AI` absent). No IRIS lock was held. Lane record:
`$RUN_DIR/breadth-b/live/08-incident-user-deploy.json`, log `$RUN_DIR/breadth-b/live/08-unit-tests-incident.log`.

**Disposition.** Same as IVG460SNAP: running the pin's own fixture is in scope; the lapse was the missing lock and the
wrong namespace. Only pin sources were compiled, by the product's own deploy path. The validation lane is asked to
treat 23:01:45-23:03:40 UTC as the affected window for USER and to rerun any suite chunk that overlapped it under the
lock (new `-rerun` ids, originals kept). Breadth B's own in-window runs were rerun and matched.
