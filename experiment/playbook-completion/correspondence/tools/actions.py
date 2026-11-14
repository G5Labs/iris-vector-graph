"""The static correspondence map: every L2 / participant-contract action of modules 11-14 and the code that implements
it at pin 3eaa79cf (read at the pin; line numbers are of the pinned files). build.py merges the live results into it.

Fields: model (L2 label of experiment/playbook-uplift/proofs/src/l2.rs and the participant-contract labels of
experiment/playbook-completion/proofs/src/{ledger,store,redactor}.rs), handlers (path:lines), methods (class methods
whose lines the coverage report counts for this action), reads/writes (globals, tables; "journal" marks the writes
the journal validates), txn (levels and TSTART/TCOMMIT/TROLLBACK sites), locks (name, mode, timeout, taken, released),
status (server error codes -> Python exception), alpha (the abstraction function's clauses that apply), traces (which
scenarios run it).
"""

L = "iris_src/src/Graph/KG/Ledger.cls"
LA = "iris_src/src/Graph/KG/LedgerApply.cls"
LR = "iris_src/src/Graph/KG/LedgerRedact.cls"
LG = "iris_src/src/Graph/KG/LedgerGenesis.cls"
LV = "iris_src/src/Graph/KG/LedgerRevision.cls"
LS = "iris_src/src/Graph/KG/LedgerStats.cls"
E = "iris_src/src/Graph/KG/Eraser.cls"
A = "iris_src/src/Graph/KG/Adjacency.cls"
T = "iris_src/src/Graph/KG/Txn.cls"
C = "iris_vector_graph/ledger/client.py"
R = "iris_vector_graph/ledger/replay.py"
ER = "iris_vector_graph/ledger/errors.py"
W = "iris_vector_graph/_write_txn.py"
NE = "iris_vector_graph/_engine/nodes_edges.py"
SS = "iris_vector_graph/stores/iris_sql_store.py"

HEAD = {"name": '^IVG.Ledger("head")', "mode": "exclusive", "timeout": "30 s (Ledger.cls:21 LOCKTIMEOUT)"}
ADJW = {"name": "^IVG.AdjW(graphKey)", "mode": 'shared #"S"', "timeout": "5 s; a row writer then writes without it and "
        "SETs ^IVG.AdjNoLock(graphKey) (Adjacency.cls:61-73)"}

ACTIONS = [
    {
        "id": "commit",
        "model": "L2 Commit{cs,key}; Ledger.Commit + Store.Apply (protocol_sys: one Biz commit step)",
        "handlers": [f"{C}:381-400 commit", f"{C}:402-443 _commit", f"{C}:322-379 _send_changeset",
                     f"{L}:397-415 Commit", f"{L}:419-528 CommitInTxn", f"{L}:532-567 WriteRevision",
                     f"{LA}:18-48 ApplyAll and the op handlers {LA}:215-693", f"{LR}:258-269 BlocksCommit",
                     f"{LS}:65-88 Bump", f"{W}:102-277 WriteTxn/write_txn (caller transaction open)", f"{T}:19-58"],
        "methods": {"Graph.KG.Ledger": ["Commit", "CommitInTxn", "WriteRevision", "RevisionResponse", "RevisionObj",
                                        "LargeOut", "Err", "ErrLimit", "MetaGet", "State", "GKey", "NewId", "NowMs"],
                    "Graph.KG.LedgerApply": ["ApplyAll", "Rec", "Enc", "EncNull", "IsReserved", "Run", "NodeExists",
                                             "EnsureEndpoint", "TupleJson", "ParseQuals", "FindEdge", "AllocStmt",
                                             "ResolveRef", "OpCreateNode", "AddLabel", "SetProp", "OpAddLabel",
                                             "OpRemoveLabel", "OpSetProp", "OpRemoveProp", "NodeSnapshotJson",
                                             "DeleteNodeRows", "OpDeleteNode", "QualsJson", "WeightOf", "IsNumeric",
                                             "OpCreateRel", "MergeQuals", "PersistQuals", "OpQual",
                                             "OpCreateTemporalEdge", "OpDeleteRel", "DeleteRelInternal"],
                    "Graph.KG.LedgerRedact": ["BlocksCommit", "Matches", "HasPrefix", "TupleEnds"],
                    "Graph.KG.LedgerStats": ["Bump", "Ensure", "PropertyFor"],
                    "Graph.KG.Txn": ["Begin", "End", "Undo"]},
        "reads": {"globals": ['^||IVG.LedgerStage(token) (staged payload, process-private)', '^IVG.Ledger("meta","state"|"maxOps")',
                              '^IVG.Ledger("head")', '^IVG.Ledger("idBySeq")', '^IVG.Ledger("revById")', '^IVG.Ledger("idem")',
                              '^IVG.Ledger("idemRedacted")', '^IVG.Ledger("redacting") (BlocksCommit)', '^IVG.Ledger("stmt")',
                              '^IVG.Ledger("tuple")', '^IVG.Ledger("stmtNext")', '^IVG.Ledger("redacting","stmt") and '
                              '^||IVG.RedactStmt via Matches', '^KG("out") (when the functional index is absent)'],
                  "tables": ["nodes (NodeExists, graph-blind)", "rdf_labels", "rdf_props", "rdf_edges (FindEdge)",
                             "rdf_reifications", "ledger_revisions (RevisionObj)", "ledger_stats"]},
        "writes": {"globals": ['^IVG.Ledger("rec",seq,ord)', '("head")', '("revById")', '("idBySeq")', '("idem")',
                               '("stmtNext")', '("stmt",id)', '("tuple",s,p,o,gk)', '^KG out/in/gen/__version via '
                               'Adjacency (functional index RowPut/RowRemove or Put/Remove/Reweight)',
                               '^IVG.AdjNoLock(g) ($Increment, survives rollback) when AdjW is not granted',
                               "^NKG (Put interns when built)", "^KG temporal subtrees (create_temporal_edge)"],
                   "tables": ["nodes", "rdf_labels", "rdf_props", "rdf_edges", "rdf_reifications (delete cascade)",
                              "kg_NodeEmbeddings(_optimized) (DeleteNodeRows)", "ledger_revisions (+ ^Graph.KG.LedgerRevisionD/I)",
                              "ledger_stats (WriteRevision; Bump after the transaction)"],
                   "journal": "validated (conformance FOOTPRINT['commit']; frame check over every trace)"},
        "txn": "TSTART Ledger.cls:402 opens one level (nested under the caller's when $TLEVEL>0: client.py:395-400 "
               "write_txn -> Txn.Begin Txn.cls:19-31 opens IVG's level first); CommitInTxn runs inside it; :405 TCOMMIT "
               "when pOk else TROLLBACK 1 (a refusal after partial apply takes back only this level); catch :406-411 "
               "rolls back every level above entry; Bump :413 in its own transaction after (LedgerStats.cls:72-83); "
               "post-commit properties (client.py:445-487) in a further WriteTxn level, after the commit's transaction",
        "locks": [dict(HEAD, taken="Ledger.cls:440, after TSTART :402 and the payload parse :422-438",
                       released="Lock - Ledger.cls:404 before TCOMMIT/TROLLBACK :405 -> deferred to the outermost "
                                "transaction end (contract Locks: deferral; doc :390-396)",
                       note="on a timeout :441-443 the Lock - at :404 is still executed without the lock held"),
                  dict(ADJW, taken="per edge add/remove inside the transaction: Adjacency.Put :86, Remove :150, "
                                   "RowUpdate :523 (functional index Graph.KG.AdjIndex)",
                       released="Lock - :93/:158 inside the transaction -> deferred to its end")],
        "status": "CommitInTxn answers Err JSON (Ledger.cls:61-70): lock_timeout :443, not_enabled :446, disabled :449, "
                  "idempotency_conflict :464, idempotency_redacted :471, unknown_head :480, stale_head :484, empty :492, "
                  "too_large :496 (ErrLimit), failed_op (ApplyAll :26/:45, op_index), redaction_in_progress "
                  "(BlocksCommit LedgerRedact.cls:265), inconsistent (WriteRevision :555/:564, catch :409); "
                  "client.py:405-416 -> errors.py:175-199 from_commit_error -> _WIRE_MAP :156-172 (failed_op with "
                  "reason \"node_not_found: '\" -> NodeNotFoundError); transport exceptions -> inconsistent "
                  "(client.py:352-357); decoder map checked by tools/decoder_map_check.py",
        "alpha": "hist' = hist ++ [lives(new records)], head+1, idem' = idem + {key: seq}; Store.Apply: "
                 "rows' = fold(rows, new records), stmts' = stmt_recs(stmts, records)",
        "traces": ["conf", "ext", "lostack", "f1201", "trace-conformance-ledger (AUDITCORE)"],
    },
    {
        "id": "replay",
        "model": "Ledger.Replay{key} (protocol_sys: a replay changes nothing, HD-1305); L2 retry rule",
        "handlers": [f"{L}:455-465 idempotency branch of CommitInTxn", f"{L}:468-473 idemRedacted refusal",
                     f"{C}:418-443 (a replayed result still applies post-commit properties :430-435, F-1306)"],
        "methods": {"Graph.KG.Ledger": ["CommitInTxn", "RevisionResponse"]},
        "reads": {"globals": ['^IVG.Ledger("idem",key)', '("idemRedacted", sha256(key))'], "tables": ["ledger_revisions"]},
        "writes": {"globals": [], "tables": ["ledger_stats (Bump replays_idem)",
                                             "rdf_props (post-commit properties of the changeset, again)"],
                   "journal": "validated (lostack, ext commit-replay)"},
        "txn": "the commit's level; pOk stays 0 so :405 TROLLBACK 1 of an empty level",
        "locks": [dict(HEAD, taken="Ledger.cls:440 (the replay is answered under the head lock)",
                       released="as commit")],
        "status": "replayed=true in the revision response (Ledger.cls:110-120) -> CommitResult.replayed; a "
                  "different fingerprint -> idempotency_conflict -> IdempotencyConflictError; a redacted key -> "
                  "IdempotencyRedactedError",
        "alpha": "stutter of Ledger and Store (except post-commit properties: Store.Apply outside the ledger)",
        "traces": ["ext", "lostack", "live-lost-ack-commit (AUDITCORE)"],
    },
    {
        "id": "enable-genesis",
        "model": "L2 SetEnabled{true} from never-enabled + the genesis Commit (seq 1); Ledger.SetEnabled + Commit",
        "handlers": [f"{C}:281-297 enable", f"{L}:252-329 Enable", f"{LG}:14-60 Capture", f"{L}:532-567 WriteRevision"],
        "methods": {"Graph.KG.Ledger": ["Enable", "WriteRevision"], "Graph.KG.LedgerGenesis": ["Capture", "TemporalMarked"]},
        "reads": {"globals": ['^IVG.Ledger("meta","state") (unlocked, :254)'], "tables": ["nodes", "rdf_labels", "rdf_props",
                                                                                       "rdf_edges (ORDER BY)"]},
        "writes": {"globals": ['^IVG.Ledger("meta",*)', '("head")=0 then 1', '("stmtNext")=1', '("stmt")', '("tuple")',
                               '("rec",1,*)', '("revById")', '("idBySeq")'],
                   "tables": ["ledger_revisions", "ledger_stats"], "journal": "validated (ext enable-genesis)"},
        "txn": "refuses $TLEVEL>0 (:261); TSTART :265; TCOMMIT :319 / TROLLBACK 1 :268/:301/:307/:315; catch :323-327",
        "locks": [dict(HEAD, taken="Ledger.cls:266 after the unlocked state read :254 (F-1104)",
                       released="Lock - :318 (:300/:306/:314 on errors) before TCOMMIT -> at TCOMMIT")],
        "status": "Err JSON lock_timeout :269, transaction_open :261, inconsistent; client raises from_commit_error",
        "alpha": "enabled' = true; hist' = [lives(genesis records)] with replay(hist') = alpha(rows); rows unchanged",
        "traces": ["ext", "every scenario's setup"],
    },
    {
        "id": "reenable-adoption",
        "model": "L2 SetEnabled{true} from disabled, then an adoption Commit of the unrecorded divergence",
        "handlers": [f"{L}:271-287 Enable (disabled branch)", f"{C}:292-296 verify(adopt=True)", f"{R}:806-859 verify",
                     f"{LG}:82-129 Adopt (CommitInTxn :505-506)"],
        "methods": {"Graph.KG.Ledger": ["Enable", "CommitInTxn"], "Graph.KG.LedgerGenesis": ["Adopt"]},
        "reads": {"globals": ['^IVG.Ledger("tuple")', '("stmt")'], "tables": ["the content tables (read_canonical)"]},
        "writes": {"globals": ['^IVG.Ledger("meta","state")', 'adoption revision as commit'], "tables": ["ledger_stats",
                                                                                                    "ledger_revisions"],
                   "journal": "validated (ext reenable, verify-adopt)"},
        "txn": "Enable's own; the adoption is a separate commit transaction (F-1103: not tied to the compared head)",
        "locks": [dict(HEAD, taken="Enable :266; the adoption commit :440", released="as commit")],
        "status": "as commit", "alpha": "SetEnabled; then Commit whose records make replay(hist) = alpha(rows)",
        "traces": ["ext"],
    },
    {
        "id": "disable-strict",
        "model": "L2 SetEnabled{false}; Ledger.SetEnabled (strict: not in the model)",
        "handlers": [f"{C}:299-309", f"{L}:331-358 Disable", f"{L}:360-383 SetStrict"],
        "methods": {"Graph.KG.Ledger": ["Disable", "SetStrict"]},
        "reads": {"globals": ['^IVG.Ledger("meta","state")'], "tables": []},
        "writes": {"globals": ['^IVG.Ledger("meta","state"|"strict")'], "tables": ["ledger_stats"],
                   "journal": "validated (ext strict-on/off, disable)"},
        "txn": "own TSTART :342/:365, TCOMMIT :351/:374; nested in the caller's level when one is open",
        "locks": [{"name": "none", "note": "no head lock: a commit that already passed its state check (:445-450) "
                                           "commits after a concurrent Disable"}],
        "status": "Err inconsistent -> LedgerInconsistencyError", "alpha": "enabled' = false; nothing else",
        "traces": ["ext"],
    },
    {
        "id": "erase-graph",
        "model": "Store.EraseRows{t} + Store.EraseIndex{t} in one transaction (L2 Erase{t}); reviewed protocol: "
                 "RL::Lock .. RL::Unlock around them (HD-1201)",
        "handlers": [f"{NE}:1473-1527 erase_graph", f"{E}:47-305 EraseGraph", f"{E}:1117-1144 EraseLedgerFor",
                     f"{A}:428-447 RemoveGraph", f"{E}:1038-1053 InvalidateDerived"],
        "methods": {"Graph.KG.Eraser": ["EraseGraph", "EraseLedgerFor", "InvalidateDerived", "CollectOrphanRoutes",
                                        "IsRouteName", "GraphEdgesInNKG", "GraphNodesInNKG", "NodeInterned",
                                        "EraseFHIRGraphRows", "SqlErr"],
                    "Graph.KG.Adjacency": ["RemoveGraph"]},
        "reads": {"globals": ['^IVG.Ledger("stmt") (every entry, dirty, :1121-1131)', '^KG("out",g) (GraphEdgesInNKG)', '^NKG("$NI")'],
                  "tables": ["embedding_registry", "INFORMATION_SCHEMA.TABLES", "rdf_edges", "nodes"]},
        "writes": {"globals": ['^IVG.Ledger("stmt",id), ("tuple",...) of the graph', '^KG out/in/gen/degc/degw/prop/label/deg2p*',
                               '^IVG.GraphMode(g)', '^IVG.AlgoCache', '^NKG (DropNKG)', '^IVG.AdjNoLock(g) (killed)',
                               "temporal subtrees (TemporalIndex.EraseGraph)"],
                   "tables": ["rdf_labels", "rdf_props", "docs", "kg_NodeEmbeddings(_optimized)", "routed kg_emb_*/kg_eemb_*",
                              "FHIR side tables", "rdf_reifications", "kg_EdgeEmbeddings", "rdf_edges", "nodes",
                              "(after commit) DROP TABLE routes, embedding_registry rows"],
                   "journal": "validated (conformance FOOTPRINT['erase'])"},
        "txn": "TSTART :56; TCOMMIT :258; catch :259-261 rolls back every level above entry and rethrows; DDL after "
               "the commit :282-299",
        "locks": [{"name": '^IVG.Ledger("head")', "note": "NOT taken (as built; F-1114, F-1201); the reviewed design "
                                                          "holds it from the row deletes to EraseLedgerFor"},
                  dict(ADJW, taken="rdf_edges DELETE :217 (functional index RowRemove -> Remove -> WriterLock) and "
                                   "RemoveGraph :431 (Adjacency.cls:431, refuses after 5 s -> $$$ThrowOnError :235)",
                       released="Lock - Adjacency.cls:445 inside the transaction -> at TCOMMIT :258")],
        "status": "throws (SqlErr, Eraser.cls:1356-1359) -> Native API exception -> Python raises (nodes_edges.py:1514-1516)",
        "alpha": "rows' = outside(rows, graph g); stmts' = stmts minus g's; hist unchanged",
        "traces": ["ext", "f1201", "live-f1201-reproduced (AUDITCORE)"],
    },
    {
        "id": "erase-nodes",
        "model": "Store.EraseRows + EraseIndex for a prefix target (graph g, ids starting prefix)",
        "handlers": [f"{NE}:1529-1563 delete_nodes_by_prefix", f"{SS}:1420-1450", f"{E}:322-351 EraseNodes",
                     f"{E}:467-636 EraseIdSet", f"{E}:641-680 EraseEdgeRow", f"{A}:396-426 RemoveNode",
                     f"{E}:372-388 EraseNodeIds (same body)"],
        "methods": {"Graph.KG.Eraser": ["EraseNodes", "EraseNodeIds", "EraseIdSet", "EraseEdgeRow", "EraseFHIRNodeRows",
                                        "NKGMayHoldAny", "NodeInterned", "InvalidateDerived", "CollectOrphanRoutes"],
                    "Graph.KG.Adjacency": ["RemoveNode", "RemoveSource", "Remove", "WriterLock"]},
        "reads": {"globals": ['^IVG.Ledger("tuple",s,p,o,gk) (EraseEdgeRow :673)', '^KG("out"/"in", g, id)', '^NKG("$NI")'],
                  "tables": ["nodes (prefix cursor, outside the transaction :333-348)", "rdf_edges (both directions)"]},
        "writes": {"globals": ['^IVG.Ledger("stmt",id), ("tuple",...) per erased edge (:672-677)', "^KG adjacency/prop/label",
                               "^||IVG.EraseIds (process-private)", "^NKG, ^IVG.AlgoCache, version (InvalidateDerived)"],
                   "tables": ["rdf_reifications", "kg_EdgeEmbeddings", "edge routes", "rdf_edges", "rdf_labels", "rdf_props",
                              "docs", "kg_NodeEmbeddings(_optimized)", "node routes", "FHIR node rows", "nodes"],
                   "journal": "validated (conf2, conf, ext)"},
        "txn": "ids collected before the transaction (EraseNodes :331-348); EraseIdSet TSTART :484, TCOMMIT :628, "
               "catch :629-633",
        "locks": [{"name": '^IVG.Ledger("head")', "note": "NOT taken (F-1114)"},
                  dict(ADJW, taken="EraseEdgeRow's DELETE :663 (functional index) and Adjacency.Remove :668; RemoveNode "
                                   "-> RemoveSource :354", released="deferred to TCOMMIT :628")],
        "status": "throws; EraseNodes refuses an empty prefix :324-326", "alpha": "rows' = outside(rows, prefix target)",
        "traces": ["conf", "ext", "trace-conformance-ledger"],
    },
    {
        "id": "erase-edges-all",
        "model": "Store.EraseRows/EraseIndex for an edge set (EraseEdges) or for everything (EraseAll)",
        "handlers": [f"{E}:395-463 EraseEdges", f"{E}:709-845 EraseAll", f"{A}:452-472 RemoveAll"],
        "methods": {"Graph.KG.Eraser": ["EraseEdges", "EraseAll"], "Graph.KG.Adjacency": ["RemoveAll"]},
        "reads": {"globals": ['^KG("out")'], "tables": ["rdf_edges", "embedding_registry"]},
        "writes": {"globals": ['^IVG.Ledger("stmt"), ("tuple") (EraseAll kills both subtrees :810-811)', "^KG, ^NKG, ^ArnoKG",
                               "^IVG.GraphMode, ^IVG.TemporalStructural, ^IVG.AlgoCache"],
                   "tables": ["every content table"], "journal": "validated (ext erase-edges, erase-all)"},
        "txn": "TSTART :414 / :714; TCOMMIT :457 / :814", "locks": [{"name": '^IVG.Ledger("head")', "note": "NOT taken"},
                                                                    dict(ADJW, taken="Remove / RemoveAll :455 (parent "
                                                                         "^IVG.AdjW#S)", released="deferred to TCOMMIT")],
        "status": "throws", "alpha": "rows' = outside(rows, t)", "traces": ["ext"],
    },
    {
        "id": "redact-start",
        "model": "L2 Start{p,t,fresh}; reviewed RL Start = Redactor.Open/Attach + Ledger.Mark in one locked step (HD-1301)",
        "handlers": [f"{C}:633-680 redact", f"{LR}:185-214 Redact opening (state :188-190, marker :202-205, "
                     f"LiveRows :206-210, PrePass :212, cursor :214)", f"{LR}:149-178 LiveRows", f"{LR}:116-141 PrePass",
                     f"{LR}:322-324 BatchInLock writes the marker with the first tombstone"],
        "methods": {"Graph.KG.LedgerRedact": ["Redact", "LiveRows", "PrePass", "MatchString", "TargetDigest",
                                              "TargetText", "Sha256Hex"]},
        "reads": {"globals": ['^IVG.Ledger("meta","state")', '("redacting")', '("rec") (PrePass)'],
                  "tables": ["nodes, rdf_labels, rdf_props, rdf_edges (COUNT, READ UNCOMMITTED)"]},
        "writes": {"globals": ["^||IVG.RedactStmt (process-private, not journaled)"], "tables": [],
                   "journal": "validated: no journaled write before the first batch"},
        "txn": "none: the opening checks run outside any transaction and without the lock",
        "locks": [{"name": "none", "note": "the pin has no Start transaction: the opening reads are unlocked and the "
                                           "marker is written by the first tombstoning batch (F-1302, F-1303); "
                                           "not the reviewed design's atomic Mark"}],
        "status": "Err JSON transaction_open :187, not_enabled :189, disabled :190, invalid_target :191/:195, "
                  "redaction_in_progress :204, inconsistent :207, target_live :209 -> client.py:678-679 "
                  "from_commit_error -> RedactionTargetLiveError, RedactionInProgressError, InvalidRedactionTargetError",
        "alpha": "Redactor.Open + Attach{i=0,j=0} (cursor at the first record, :214); no Ledger step until the first "
                 "tombstone, which also performs Mark (as-built Ledger.Batch sets the marker if none)",
        "traces": ["conf", "ext"],
    },
    {
        "id": "redact-batch",
        "model": "L2 Scan{p} (one record); Ledger.Batch{i,j,t,tomb,ni,nj} (+ Redactor.Advance)",
        "handlers": [f"{LR}:216-226 the batch loop", f"{LR}:275-300 Batch", f"{LR}:302-330 BatchInLock",
                     f"{LR}:333-347 Tombstone", f"{LR}:353-378 ClearRevision", f"{LR}:89-112 Matches",
                     f"{LV}:87-101 RejectUpdate trigger exemption", f"{L}:572-605 CanonicalRecord"],
        "methods": {"Graph.KG.LedgerRedact": ["Batch", "BatchInLock", "Tombstone", "ClearRevision", "Matches",
                                              "HasPrefix", "TupleEnds"],
                    "Graph.KG.Ledger": ["CanonicalRecord"], "Graph.KG.LedgerRevision": ["RejectUpdate"]},
        "reads": {"globals": ['^IVG.Ledger("rec")', '("redacting")', '("redacting","stmt")', "^||IVG.RedactStmt",
                              '("stmt")', '("redactedRev")'], "tables": ["ledger_revisions (idempotency_key)"]},
        "writes": {"globals": ['^IVG.Ledger("rec",seq,ord) := $LB("redacted",digest,flags,op,kind)', '("redacting") (first)',
                               '("redacting","stmt",id)', '("redacting","revs",seq)', '("redacting","n",*)',
                               '("redactedRev",seq)', '("idem",key) killed', '("idemRedacted",sha256(key))'],
                   "tables": ["ledger_revisions (message, source, correlation_id, idempotency_key := NULL)"],
                   "journal": "validated (conformance FOOTPRINT['redact'])"},
        "txn": "TSTART :281; TCOMMIT :288 or TROLLBACK 1 :284/:288; catch :291-296 (one level)",
        "locks": [dict(HEAD, taken="LedgerRedact.cls:282 after TSTART",
                       released="Lock - :289 AFTER TCOMMIT :288 (Redact refuses $TLEVEL>0, so the unlock is immediate)")],
        "status": "Err lock_timeout :285, disabled :305, inconsistent (:295, ClearRevision :356/:357/:375) -> Redact :228 "
                  "returns it -> from_commit_error",
        "alpha": "per tombstone Live(c) -> Tomb(c), c a record of t and not live, digest = SHA-256(CanonicalRecord); "
                 "count += 1, tally += c, marker := marker or t",
        "traces": ["conf", "ext", "trace-conformance-ledger"],
    },
    {
        "id": "redact-final",
        "model": "L2 Final{p,t,ok}; Ledger.Audit{t} + Redactor.Finish (reviewed: under its own marker, after a re-check)",
        "handlers": [f"{LR}:230-234 Redact", f"{LR}:384-407 Final", f"{LR}:409-442 FinalInLock",
                     f"{LR}:446-471 DropStatements", f"{LR}:473-480 ReadCounts", f"{LR}:482-511 Receipt",
                     f"{L}:532-567 WriteRevision (kind redaction)"],
        "methods": {"Graph.KG.LedgerRedact": ["Final", "FinalInLock", "DropStatements", "ReadCounts", "Receipt", "LiveRows"],
                    "Graph.KG.Ledger": ["WriteRevision", "RevisionObj"]},
        "reads": {"globals": ['^IVG.Ledger("redacting",*)', '("stmt")', '("tuple")', '("head")', '("idBySeq")'],
                  "tables": ["content tables (LiveRows re-check under the lock)"]},
        "writes": {"globals": ['^IVG.Ledger("stmt",id) and ("tuple") of the target killed', 'redaction revision '
                               '("rec",head+1,*) ("head") ("revById") ("idBySeq")', '("redacting") killed'],
                   "tables": ["ledger_revisions", "ledger_stats"], "journal": "validated"},
        "txn": "TSTART :389; TCOMMIT :396 or TROLLBACK 1; catch :399-403",
        "locks": [dict(HEAD, taken="LedgerRedact.cls:390", released="Lock - :397 after TCOMMIT (immediate)")],
        "status": "target_live :415, disabled :411, inconsistent :414, lock_timeout :393",
        "alpha": "hist' = hist ++ [Audit{t, n=count}] when marker and count>0; marker None; count 0; stmts unchanged "
                 "(an erased target has no live tuple entry left); FinalInLock removes whichever marker exists (:439, F-1303)",
        "traces": ["conf", "ext"],
    },
    {
        "id": "redact-stop-resume",
        "model": "Redactor.Stop / Open again; reviewed: resume at the marker's cursor (D-1)",
        "handlers": [f"{LR}:217 max_batches exit", f"{LR}:236 ReadCounts for a paused run", f"{LR}:202-205 own marker "
                     f"passes", f"{LR}:214 the cursor restarts at the first record (F-C1303)"],
        "methods": {"Graph.KG.LedgerRedact": ["Redact", "ReadCounts", "Receipt"]},
        "reads": {"globals": ['^IVG.Ledger("redacting")'], "tables": []}, "writes": {"globals": [], "tables": [],
                                                                                    "journal": "n/a"},
        "txn": "a stop between batches loses only the process's cursor; a killed process's open batch is rolled back "
               "by IRIS (contract: Process stop)",
        "locks": [{"name": "head lock of the interrupted batch", "note": "released by process stop (contract)"}],
        "status": "receipt complete=false", "alpha": "Redactor.Stop; Ledger unchanged; resume = Open + Attach{0,0} at the "
                                                    "pin (rewind; progress-only control in proofs)",
        "traces": ["conf (redact(1) then redact(0))", "ext (redact-bounded, redact-resume)", "live-fc1303-bounded-resume"],
    },
    {
        "id": "verify",
        "model": "Reader step (stutter); the verify verdict of M3-readers",
        "handlers": [f"{C}:741-744", f"{R}:806-859 verify", f"{R}:588-642 read_canonical", f"{R}:645-698 compare",
                     f"{L}:158-164 Head", f"{LR}:242-254 InProgress", f"{L}:176-179 StmtForTuple",
                     f"{L}:613-652 Records* (SQL ledger_records)", f"{L}:192-210 RecordVerify"],
        "methods": {"Graph.KG.Ledger": ["Head", "StmtForTuple", "RecordVerify", "RecordsExecute", "RecordsFetch",
                                        "RecordsClose", "RevisionResponse", "RevisionObj"],
                    "Graph.KG.LedgerRedact": ["InProgress"], "Graph.KG.LedgerStats": ["Ensure"]},
        "reads": {"globals": ['^IVG.Ledger("rec")', '("head")', '("redacting")', '("tuple")'],
                  "tables": ["nodes, rdf_labels, rdf_props, rdf_edges (graph-blind, F-1401)", "ledger_revisions"]},
        "writes": {"globals": [], "tables": ["ledger_stats (RecordVerify, own transaction :197-204)"],
                   "journal": "validated (conformance FOOTPRINT['verify'])"},
        "txn": "no transaction around the reads (records and tables are read at different moments, P-1401); "
               "RecordVerify TSTART :197 / TCOMMIT :204",
        "locks": [{"name": "none", "note": "the marker is checked once before reading (F-1402)"}],
        "status": "VerificationReport.result equal | diverges | redaction_in_progress",
        "alpha": "stutter", "traces": ["conf", "ext", "lostack"],
    },
    {
        "id": "readers",
        "model": "Reader steps (get_revision, diff, reconstruct, export, history): stutter; RPL-I1",
        "handlers": [f"{C}:687-739", f"{C}:585-629 history", f"{R}:252-269 iter_records_sql", f"{R}:544-566 reconstruct",
                     f"{L}:613-652 RecordsExecute/Fetch/Close", f"{L}:166-174 SeqOf"],
        "methods": {"Graph.KG.Ledger": ["RecordsExecute", "RecordsFetch", "RecordsClose", "SeqOf", "Head",
                                        "CanonicalRecord"],
                    "Graph.KG.LedgerRedact": ["InProgress"]},
        "reads": {"globals": ['^IVG.Ledger("rec")', '("revById")', '("redacting")'], "tables": ["ledger_revisions"]},
        "writes": {"globals": [], "tables": [], "journal": "validated: no writes (ext readers ops)"},
        "txn": "none", "locks": [{"name": "none", "note": "history() does not refuse while a run is in progress"}],
        "status": "RedactionInProgressError while marked (client.py:687-693); UnknownRevisionError; "
                  "ReconstructionTooLargeError (replay.py:557)", "alpha": "stutter", "traces": ["ext"],
    },
    {
        "id": "post-commit-properties",
        "model": "outside the ledger: Store.Apply of direct writes (premise P-C02); M3-retry's separate property write",
        "handlers": [f"{C}:430-435", f"{C}:445-487 _apply_post_commit_properties", f"{W}:102-272 WriteTxn"],
        "methods": {"Graph.KG.Txn": ["Begin", "End", "Undo"]},
        "reads": {"globals": [], "tables": []},
        "writes": {"globals": [], "tables": ["rdf_props (DELETE + INSERT, default graph)"],
                   "journal": "validated (ext commit-post-commit-property)"},
        "txn": "its own WriteTxn level after the commit's transaction (Txn_Begin/End/Undo)",
        "locks": [{"name": "none", "note": "no head lock; not serialized with erasure (F-1306 race m3-as-built-pcp-race)"}],
        "status": "CommitResult.post_commit_applied / post_commit_error (never raised)",
        "alpha": "Store.Apply outside the ledger: not a Biz step (P-C02)", "traces": ["ext"],
    },
]
