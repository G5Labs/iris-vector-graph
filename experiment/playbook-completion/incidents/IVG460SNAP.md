# IVG460SNAP: disposition (local convention, not a product change)

**What happened.** At 2026-11-13 23:02:53 UTC breadth lane C ran the upstream file `tests/unit/test_snapshot.py` to
collect run evidence for module 18. Its module fixture needs IRIS: it created namespace IVG460SNAP with database
`/usr/irissys/mgr/ivg460snap/` (container `messages.log` lines 456-460) and compiled the pin's unmodified classes into
it; 3 MCP classes failed because `%AI` is absent on Community, so 6 tests errored in fixture setup. The run held no
IRIS lock. Lane record: `live/breadth-c/incident-ivg460snap.json`; run record `c18-run-unit-snapshot` (incomplete).

**Disposition.** Running pinned upstream fixtures that create an isolated scratch namespace is within the verification
scope (operator monitor 2026-11-14T00:12Z). What the lane broke was the local coordination convention (no lock, no
namespace record), not the read-only product rule: no product file changed and only the pin's classes were compiled,
by the product's own fixture. The namespace is left intact for attribution and recorded in `NAMESPACES.md`. The
failed fixture setup stays visible as `c18-run-unit-snapshot` (incomplete; dependency: `%AI` classes absent on IRIS
Community 2026.1); its 6 errored tests are not used as evidence. CONVENTIONS.md now allows such fixtures under the
IRIS lock with a namespace record.

**Uncoordinated connections, 23:02:53-23:03:40 UTC.** The IRIS journal (`$RUN_DIR/checks/incident-journal-window.log`,
from `/usr/irissys/mgr/journal/20261113.001z`) shows writers in that window only in: IVG460SNAP (the fixture and the
class compiler's shared worker jobs, pids 828/833/834/1364), USER (the validation lane's suite chunk), and AUDITB
(breadth lane B, pid 7950). No orchestrator, core, intent or breadth A/C check wrote in that window. Reruns under the
IRIS lock were requested from breadth B and validation (new ids with suffix `-rerun`; originals kept). Two breadth-C
logs contain a communication error (`c15-live-rdf`, `c16-s6-status-maps`), but it is each probe's intended stimulus
(F-1501's failed window read drops the connection on purpose; the status-map probe uses a stub engine on a closed
port), neither ran in the window (no AUDITC writes then), and no log in the registry contains "Unable to allocate a
license" after the connection-cap rule; they are not affected and not rerun.
