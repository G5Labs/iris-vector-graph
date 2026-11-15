# FHIR task producer panel before iteration8 model

Input seal `9e6a876feac7306bd442bacfff4b28a2fac436d4`; product3eaa79cf.
Inherited source-first selection/predictions are [iteration7's panel](../iteration-7/next-survey-PAIRS.md)
and [survey](../iteration-7/next-survey-fhir.md). This is builder-visible discovery,
not held-out evaluation. Child scope is new fhir_tasks package and fhir-prefixed
iteration8 artifacts only; root owns native runtime and integration.

The canonical `fhir.graph.lifecycle` requires own-task schedule/update/removal and
refuses a restored ID naming another task without changes. Imported P `fhir_l2`
prefilters a one-graph task set and takes `Schedule/Unschedule{ok}` as input; it
cannot derive raw class/namespace/Settings ownership or the final task status.
Known separate task/registry write issue F-C1501 remains inherited, not a new bug.

| Neighbor to retain | Current intended/as-built prediction to model and test |
|---|---|
| registry ID absent / stale object ID / own object | create / replace with fresh task / reuse same ID |
| own / wrong class / wrong namespace / wrong GraphId / missing GraphId | mutate only own; other existing objects refuse before task or registry writes |
| duplicate Settings GraphId entries in opposite order | last matching key wins; preserve raw alternating list before deriving ownership |
| interval None / explicit0/59 /60/61 | retain registered seconds / caller refusal /1 minute/2 minutes |
| registered interval<60 with caller None / explicit60 | server refusal / valid override |
| task save/delete failure / later registry SQL failure | first failure stops before SQL; later failure preserves task write and old registry |
| stale ID unschedule / own-task unschedule | clear ID with removedfalse / delete object and clear ID with removedtrue |
| schedule SQL failure then retry / unschedule SQL failure then retry | preserve saved orphan or changed own task; retry derives behavior from actual resulting raw state |
| final registry status / actual task map | reader reports stored ID/interval, does not establish that ID exists or belongs to graph |
| OnTask SyncOnce busy/ok/error/throw or malformed reply | busy/ok successful invocation; error or thrown/parser failure fails; saved GraphId drives call |

No ownership boolean replaces task fields. Provider outcome inputs describe save,
delete or SQL boundaries, never ownership. Pre-effect provider failures are scoped;
actual partial Task Manager failures, Settings/native equality, background execution,
concurrent object-open/ID reuse and full FHIR SyncOnce remain provider limits.
Controls alter deciding rules and execute the same journey/oracle; no arbitrary
changed observed value will be called a substantive correspondence detection.
