# Least-privilege checks (versions and privilege lane)

The operator authorised a disposable least-privilege IRIS user and role on the dedicated audit container
(`ivg-playbook-20261113-audit-iris`, IRIS 2026.1 Build 234U, Community). This file records the principal's exact scope
and what it settled. Every command ran under `tools/locks.sh iris`, with at most 4 connections at once. AUDITB's data
was written and erased only through the pin's API (`IRISGraphEngine.erase_all / create_node / create_edge / sync`).
Nothing was compiled, and no namespace or database was created or reconfigured. Driver: 5.3.2 (the pin's `uv.lock`).

## The principal (scope, exact)

| Item | Value | Evidence |
|---|---|---|
| Role | `IVGAUDIT_RO_ROLE`. Resources `%DB_%DEFAULT:R`, `%Native_ClassExecution:U`, `%Native_GlobalAccess:U`. No granted roles, no `%All` | `ver-priv-create`, `ver-priv-final` |
| User | `IVGAUDIT_RO`. Roles: `IVGAUDIT_RO_ROLE` only. Default namespace `AUDITB`. ChangePassword 0. **Enabled 0 at the end** (login refused: `Access Denied`) | `ver-priv-final` (`r3/privileges-final.log`, `r3/login-after-disable.log`) |
| SQL privileges (AUDITB only) | `SELECT ON SCHEMA Graph_KG` (grantor `_SYSTEM`) and `EXECUTE ON SCHEMA Graph_KG` (grantor `irisowner`, the terminal user of `grant.os`). Nothing on any other schema or namespace | `Security.SQLPrivileges`, `ver-priv-final` |
| Effective permissions (as the user, `$SYSTEM.Security.Check`) | `%DB_%DEFAULT` READ; `%Native_ClassExecution` USE; `%Native_GlobalAccess` USE; `%All`, `%DB_USER`, `%DB_IRISSYS` none. A Native-API global SET is refused with `<PROTECT>`. `create_node` and SQL INSERT are refused with -99 | `ver-priv-r2`, `ver-priv-r3` |
| Password | Generated (30 characters) into `$RUN_DIR/versions/secrets/ivgaudit_ro.pw`, mode 600, directory mode 700, outside the repository. It reached IRIS only as the environment variable `IVGAUDIT_PW`, passed by name (`docker exec -e IVGAUDIT_PW`) to `create.os`, which reads it with `$System.Util.GetEnviron`. A `grep -F -f` over every lane log, the registry and the repository finds it nowhere else | this file |

This is ADMIN_GUIDE section 3's **reading** row (ADMIN_GUIDE.md:459-461, recipe :470-491), made as its recipe says: role and
user in `%SYS`, then the two `GRANT`s as SQL in the namespace.

**Scope wider than "AUDITB read".** No resource `%DB_AUDITB` exists. AUDITB's one database (`/usr/irissys/mgr/auditb/`,
globals and routines) has the resource `%DB_%DEFAULT`, as the product's own guide warns for a database created without
one (ADMIN_GUIDE.md:493-497). Fifteen databases share it: AUDITA, AUDITB, AUDITC, AUDITCORE, AUDITENV, AUDITIA, AUDITIB,
IVG236VAL, IVG262FC1306, IVG262FPA, IVG262FPG, IVG262REC, IVG460SNAP and IVG460SNAPVAL (`ver-priv-inspect`). While the
user was enabled it could therefore read the globals of all of them over the Native API. SQL privileges were granted only
in AUDITB. Narrowing this to one database needs a dedicated resource assigned to AUDITB's database, which reconfigures
the container. It was not done, and is the operator's decision. The user was enabled only during the three probe rounds
(04:23:07-04:23:09, 04:31:05-04:31:10, 04:45:43-04:45:47 UTC) and is now disabled. It is left in place, as instructed.

Other changes to the container: none. The reader's scratch files went to `/tmp/ivgaudit-versions-<stamp>/` and were
removed by the reader's own `DeleteDir`, which `docker exec ls` confirms. AUDITB's tables are empty after each round
(the census before round r1: every Graph_KG table at 0 rows except `embedding_registry` with 3 rows, which the pin's
`erase_all` empties).

## Rounds

| Run | Result | What it shows |
|---|---|---|
| `ver-priv-r1` | **incomplete (invalid for the revoke)** | The REVOKE ran as `_SYSTEM` without `AS`, while the grant's grantor was `irisowner`. It removed nothing: IRIS revokes only the current user's grants without `AS` (SQLCODE 100, no error), as the pin itself notes (`iris_vector_graph/_engine/legacy.py:539-540`). The reader's SQL still answered, and `privileges-after.log` lists the grant. This was a harness error, not a product result. It is kept, not reused. Its pre-revoke and F-C1803 parts are valid |
| `ver-priv-r2` | pass | Grantor-aware revoke (`AS "irisowner"`, `AS "_SYSTEM"`), confirmed by `CheckPrivilege` = 0 for the user and the role. Asked with one unlabelled id-anchored query only |
| `ver-priv-r3` | pass | The discriminating round: three native shapes (label scan, labelled id anchor, unlabelled id anchor), each asked of the running engine, of a fresh engine, and of `Exec.Run` called directly |

## HD-0901: does a running engine notice a revoked SQL right? (`ver-priv-r3`, `ver-priv-r2`)

Setup: graph a -> b -> c -> d (KNOWS, each node labelled P). Engine R1 was built as the reader while it held SELECT,
and it answered all three shapes natively (`_native_answers` +1 each). Then
`REVOKE SELECT ON SCHEMA Graph_KG FROM IVGAUDIT_RO_ROLE` ran (both grantors), with `CheckPrivilege(rdf_edges, s)` = 0.

| Query | Running engine R1 (privilege answer cached True) | Fresh engine R2 | `Graph.KG.Cypher.Exec.Run` called directly by the revoked user |
|---|---|---|---|
| `MATCH (a:P)-[:KNOWS]->(b) RETURN a.node_id, b.node_id` (label scan: `^KG("label")`, Exec.cls:832-845) | **3 rows, answered natively** | gate closed ("missing SELECT on a Graph_KG table"); SQL path -99, no rows | **3 rows** |
| `MATCH (a:P {node_id: 'a'})-[:KNOWS]->(b) RETURN b.node_id` (labelled id anchor: `^KG("label", g, L, id)`, Exec.cls:873-880) | **[b], answered natively** | -99, no rows | **[b]** |
| `MATCH (a {node_id: 'a'})-[:KNOWS]->(b) RETURN b.node_id` (unlabelled id anchor: SQL on `Graph_KG.nodes`, Exec.cls:855-871) | refused: `Cypher anchor SQLCODE -99`. The engine warns and falls back to SQL, which returns -99 and no rows | -99, no rows | refused (`Cypher anchor SQLCODE -99`) |
| the same connection's own SQL (`SELECT COUNT(*) FROM Graph_KG.rdf_edges`) | -99 at once | -99 | — |

Also: the revoked user still reads `^KG` over the Native API (`isDefined` 10; subscripts `__version`, `deg2p`, `in`,
`label`, `out`, ...). After the SELECT was granted again, R2 kept its cached `False` and stayed on SQL (native delta 0)
until a new engine is built (iris_vector_graph/engine.py:559-586, "Cached per engine").

**Answer (live, 2026.1).** The IRIS server process sees a REVOKE at once: the next SQL prepare on the same connection is
refused. The engine's Python gate is asked once per engine and never again. A running engine therefore keeps reading the
graph after its user lost SELECT, for every plan whose anchor and walk read only `^KG` (label scans, labelled id
anchors). Plans whose anchor is a SQL lookup (an unlabelled id, and by the source also property anchors, Exec.cls:882-903)
fail at that lookup, which IRIS checks as the caller. Distinguishing traces from HD-0901: `Read; Revoke; Read` violates
P1 ("a native read implies the grant is held now") for the ^KG-only shapes, as built. It satisfies P1' (FR-011 as
written, "cached per process and user"), because R1's check predates the revoke. A fresh engine satisfies P1. HD-0901
stays an **intent** question (the maintainer chooses between FR-011 and R280). The as-built behaviour is now
`live`, no longer `inspected` only. The index half of HD-0901 (an out-of-band DROP INDEX) was not run: it is DDL on
product tables.

## F-0908: the executor checks no privilege (`ver-priv-r3`)

`Graph.KG.Cypher.Exec.Run` (iris_src/src/Graph/KG/Cypher/Exec.cls:32-72) was called over the Native API by a user that
holds **no SELECT on any Graph_KG table**, with the plans the engine built for the label-scan and labelled-id queries.
It answered the graph's rows. The only refusal is incidental: an anchor the executor resolves through dynamic SQL
(`%SQL.Statement`, run as the caller). F-0908 moves from `confirmed-source` to **reproduced-live**: FR-011's executor-side
check is absent, and the database resource plus `%Native_ClassExecution` is the effective boundary, as ADMIN_GUIDE.md:565-570
and SqlPrivilege.cls:9-10 state. Which contract holds stays HD-0901's intent question.

## Breadth C's reader checks (F-C1803, module 18; `ver-priv-r1`, `ver-priv-r2`)

Breadth C (modules 15-18) recorded one reading-role check it could not run: whether a user holding only the documented
reading role reaches `Graph.KG.Snapshot`'s file helpers (`modules/18.json` blockers; `findings/audit/18.json` F-C1803).
Modules 16 and 17 record no reader-role check: 16's blockers are the web application, `%AI` and FHIR, and 17's are
installer recipes. Run as `IVGAUDIT_RO`, both rounds gave the same result:

- `FileExists('/etc/hostname')` = 1, `GetFileSize` = 33, and `ReadFileChunk` returned the container's host name.
  `ReadFileChunk('/usr/irissys/iris.cpf')` returned the instance configuration's first lines.
- `ExportGlobals('/tmp/ivgaudit-versions-<stamp>/', [^KG])` created the directory and wrote `^KG.gof` (2,498 bytes).
  `WriteFileChunk` wrote a file there, and `ReadFileChunk` read it back. `docker exec ls -ln` shows both files, owned by
  the IRIS server's OS user (uid 51773).
- `DeleteDir` of that directory answered 1, and `ls` then finds nothing.

So a role with the database at **R** reads and writes server files and exports globals to them through IVG's classes.
F-C1803's reading-role reachability, recorded `confidence: medium` ("not on a live call as that role"), is now
**live**: read, write, export and delete as the documented reading role.

Also confirmed for the reading row: reads answer (native and SQL path), and every write is refused (`create_node` and
INSERT -99, global SET `<PROTECT>`). This matches ADMIN_GUIDE.md:455-457 on Community 2026.1.

## What still needs the operator

- A per-namespace database resource (for example `%DB_AUDITB` on AUDITB's database) if the reader's database scope must
  be one namespace. This changes the container's database configuration.
- Deleting the disabled user and role when the experiment ends (they are left in place, disabled, as instructed).
