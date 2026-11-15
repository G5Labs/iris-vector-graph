#!/usr/bin/env python3
"""Regenerate .g5/Verus_verification/families.tsv: one row per retained formal family of both arms and of this
consolidation, with its status, design attribute, recorded result and the local rerun read from the receipts.

    python3 .g5/Verus_verification/tools/make_families.py

The hand-maintained part is the table FAMILIES below (status, scope and reasons); the "local rerun" column is computed
from results/<family>/*/receipt.json. Standard library only.
"""
import csv
import glob
import json
import os

V = ".g5/Verus_verification"
R = f"{V}/results"
PC = "experiment/playbook-completion"
H = ["family_id", "arm", "path", "kind", "design", "scope", "status", "recorded result and where", "local rerun", "premises file"]


def receipts(fam):
    out = []
    for x in sorted(glob.glob(f"{R}/{fam}/*/receipt.json")):
        try:
            out.append((x, json.load(open(x))))
        except Exception:
            pass
    return out


def g_rerun(m):
    spec = json.load(open(f"{V}/models/{m}/model.json"))
    rs = receipts(m)
    proves = [(x, d) for x, d in rs if d.get("kind") == "proof" and "/20261115T" in x]
    latest = {}
    for x, d in rs:
        if d.get("kind") == "control":
            latest[d["control"]["name"]] = (x, d)
    if not proves:
        return "not re-run here"
    px, pd = proves[-1]
    ctl = [latest.get(c["name"]) for c in spec["controls"]]
    fresh = [c for c in ctl if c and c[1]["verdict"] == "EXPECTED_FAIL" and "20261115" in c[0]]
    return (f"{px.replace(V + '/', '')} {pd['verdict']} {pd['observed']['verified']} verified; "
            f"{len(fresh)} of {len(spec['controls'])} controls EXPECTED_FAIL in this run (results/{m}/20261115T*-control-*)")


def p_rerun(fam):
    rs = [(x, d) for x, d in receipts(fam) if d.get("kind") == "playbook-crate-rerun"]
    base = [(x, d) for x, d in rs if d["label"] == "baseline" and d["verdict"] == "PASS"]
    errs = [x for x, d in rs if d["verdict"] in ("ERROR", "TIMEOUT")]
    if not base:
        return "not re-run here"
    bx, bd = base[-1]
    s = f"{bx.replace(V + '/', '')} PASS {bd['root']['verified']} verified"
    s += " (matches RESULTS.json)" if bd.get("matches_record") else " (the arm recorded no RESULTS.json for this crate)"
    latest = {}
    for x, d in rs:
        if d["label"] != "baseline":
            latest[d["label"]] = d
    if latest:
        ok = sum(1 for d in latest.values() if d["verdict"] == "EXPECTED_FAIL" and d.get("matches_record"))
        s += f"; {ok} of {len(latest)} controls EXPECTED_FAIL at the recorded error locations"
    if errs:
        s += f"; {len(errs)} retained ERROR receipt(s) with no verdict (cargo up to date, nothing verified)"
    return s


def c_rerun(m):
    spec = json.load(open(f"{V}/models/{m}/model.json"))
    rs = receipts(m)
    proves = [(x, d) for x, d in rs if d.get("kind") == "proof"]
    latest = {}
    for x, d in rs:
        if d.get("kind") == "control":
            latest[d["control"]["name"]] = d
    if not proves:
        return "no receipt yet"
    px, pd = proves[-1]
    ok = sum(1 for c in spec["controls"] if latest.get(c["name"], {}).get("verdict") == "EXPECTED_FAIL")
    return f"{px.replace(V + '/', '')} {pd['verdict']} {pd['observed']['verified']} verified; {ok} of {len(spec['controls'])} controls EXPECTED_FAIL"


G = [
    ("ledger_redaction", "commit admission, erasure scope, the redaction lifecycle, replay and verify", "active",
     "41 verified, 16 controls; results/ledger_redaction/20261114T034942Z-prove at 24c6b0c0"),
    ("graph_structure", "graph keys, the degree cache, keyed adjacency writers, the algorithm-cache token", "active",
     "67 verified, 22 controls; results/graph_structure/20261114T000451Z-prove at 24c6b0c0"),
    ("temporal", "temporal writes and collisions, buckets and aggregates, marked rows, purge, erase hooks", "active",
     "113 verified, 33 controls; results/temporal/20261114T040433Z-prove at 24c6b0c0"),
    ("search", "BM25 counters, the embed queue, routes and widths, model identity per route", "active",
     "56 verified, 27 controls; results/search/20261114T035601Z-prove at 24c6b0c0"),
    ("platform", "the IVG Schema record and refusals, the strict-mode write surface, compiled-plan eligibility and stamps",
     "active", "51 verified, 30 controls; results/platform/20261114T002651Z-prove at 24c6b0c0"),
]

P = [
    ("playbook-uplift-proofs", "experiment/playbook-uplift/proofs", "verus", "reviewed",
     "L1 business machine and L2 algorithmic machine of the redaction slice", "superseded",
     "53 verified (experiment/playbook-uplift/MODELS.md:39; experiment/playbook-uplift/evidence/runs.json)",
     "superseded within the playbook arm by proofs-d9c; for the governing ontology the redaction family is G-ledger_redaction (as-built)",
     "experiment/playbook-uplift/MODELS.md"),
    ("playbook-uplift-model", "experiment/playbook-uplift/model", "explorer", "as-built and reviewed variants",
     "redaction, erasure, readers and retry machines, bounded exhaustive exploration", "overlapping",
     "11 of 11 checks met (experiment/playbook-uplift/MODELS.md)",
     "overlaps G-ledger_redaction (as-built Verus, all sizes) for the same decisions; kept as bounded evidence",
     "experiment/playbook-uplift/MODELS.md"),
    ("playbook-proofs", f"{PC}/proofs", "verus", "reviewed", "participant contracts Ledger, Store, Redactor and their Protocol2 composition",
     "superseded", "88 verified, 5 controls; RESULTS.json; registry core-proofs-baseline",
     "successor proofs-d9 (removes three premises the pin violates), then d9b, d9c", None),
    ("playbook-proofs-breadth", f"{PC}/proofs-breadth", "verus", "reviewed", "modules 11 (ledger_l1/l2) and 04 (adj_l1/l2)",
     "overlapping", "94 verified, 7 controls; RESULTS.json; registry proofs-breadth-baseline",
     "same machines as proofs-pa3 with premise P-A3 (an eraser of g overlaps no writer of g), which the pin violates; pa3 is preferred", None),
    ("playbook-proofs-pa3", f"{PC}/proofs-pa3", "verus", "reviewed",
     "modules 11 and 04 without premise P-A3: ledger commit, abort, head lock, idempotency binding; adjacency generations", "active",
     "108 verified, 9 controls; RESULTS.json; registry proofs-pa3-baseline",
     "active for ledger admission/record composition and idempotency binding (public M02/J05; M03 partial: operation failures and prior records missing); its adjacency part overlaps G-graph_structure (as-built), which is active for M10", None),
    ("playbook-proofs-d1b", f"{PC}/proofs-d1b", "verus", "reviewed", "modules 18 (snap_l2) and 06 (vidx_l2 IVF lifecycle, vq_l2 embed queue)",
     "active", "92 verified, 11 controls; RESULTS.json; registry proofs-d1b-baseline",
     "active (partial) for snapshots: abstract contents without per-route width or the per-graph reader", None),
    ("playbook-proofs-d1c", f"{PC}/proofs-d1c", "verus", "reviewed", "modules 03 (edge_l2, stmt_l2, bulk_l2) and 05 (tagg_l2)",
     "active", "111 verified, 10 controls; RESULTS.json; registry proofs-d1c-baseline",
     "active (partial) for bulk checkpoints; edge and temporal rows overlap G-temporal", None),
    ("playbook-proofs-d1d", f"{PC}/proofs-d1d", "verus", "reviewed", "modules 07 (bmn, bmw), 08 (cys, cyw), 09 (nread, planc)",
     "active", "118 verified, 21 controls; RESULTS.json; registry proofs-d1d-baseline",
     "active for compiled-plan pending and failed builds (public J08; planc_l2), overlapping G-platform for stamps and eligibility", None),
    ("playbook-proofs-d1e", f"{PC}/proofs-d1e", "verus", "reviewed", "modules 01 (inst), 02 (gid, gmode), 10 (acache, atrav)",
     "active", "115 verified, 15 controls; RESULTS.json; registry proofs-d1e-baseline",
     "active for abstract cached algorithm answers (public M21/J04 partial: CDLP/WCC variants missing; acache_l2 keys freshness on a node token nver the pin lacks; the pin's behavior is control_f1004_create_moves_no_token, finding F-1004) and graph-scoped reads (gid_l2; the pin is control_f0206_hydrate_from_default, finding F-0206)", None),
    ("playbook-proofs-d1f", f"{PC}/proofs-d1f", "verus", "reviewed", "modules 15 (fhir), 16 (call, unit, auth), 17 (sqla, opsc)",
     "active", "115 verified, 17 controls; RESULTS.json; registry proofs-d1f-baseline",
     "the only formal family for FHIR sync and the HTTP and Bolt unit of work; reviewed designs only", None),
    ("playbook-proofs-d9", f"{PC}/proofs-d9", "verus", "reviewed", "erase/redact/replay protocol under the pin's real premises",
     "superseded", "115 verified, 7 controls; RESULTS.json; registry proofs-d9-baseline", "successor proofs-d9b", None),
    ("playbook-proofs-d9b", f"{PC}/proofs-d9b", "verus", "reviewed",
     "d9 plus revision metadata, retry keys, statement history, readers, the scan bound", "superseded",
     "158 verified, 15 controls; RESULTS.json; registry proofs-d9b-baseline", "successor proofs-d9c", None),
    ("playbook-proofs-d9c", f"{PC}/proofs-d9c", "verus", "reviewed",
     "d9b with bypass writers honouring the marker and F-1306 as the pin writes it", "overlapping",
     "158 verified, 16 controls; RESULTS.json; registry proofs-d9c-baseline",
     "current version of the playbook protocol; overlaps G-ledger_redaction, which is as-built and preferred for the redaction decisions", None),
    ("playbook-proofs-env", f"{PC}/proofs-env", "env-contract", "environment specification",
     "the IRIS 2026.1 contract as a Verus specification linked to the participant contracts", "supporting",
     "305 verified, 17 controls; RESULTS.json; registry proofs-env-baseline", "extended by proofs-env2; its results stay valid", None),
    ("playbook-proofs-env2", f"{PC}/proofs-env2", "env-contract", "environment specification",
     "proofs-env extended by the clauses outside its subset", "supporting",
     "433 verified, 22 controls; RESULTS.json; registry proofs-env2-baseline", "", None),
    ("playbook-proofs-mech", f"{PC}/proofs-mech", "verus", "mechanism laws (as-built variants as controls)",
     "the 13 shared mechanisms proved once over a trait", "supporting", "1,149 verified, 120 controls; RESULTS.json",
     "controls not re-run here (120 controls took about 37 minutes on the VM)", None),
    ("playbook-proofs-sys", f"{PC}/proofs-sys", "verus", "composed model (as-built as a control)",
     "module-00 axioms over the composed mechanisms", "supporting", "256 verified, 12 controls; RESULTS.json", "", None),
    ("playbook-proofs-stmt", f"{PC}/proofs-stmt", "verus", "hand-translated program", "EraseGraph handler as a program in the contract model",
     "partial", "110 verified (development run, registry proofs-stmt-dev-baseline); PARTIAL.md", "partial, not integrated; do not cite its drafts", None),
    ("playbook-models-breadth-a", f"{PC}/models/breadth-a", "explorer", "as-built and reviewed variants", "modules 01-06 machines",
     "supporting", "104 of 104 checks met; RESULTS.json; registry breadth-a-mc-*", "", None),
    ("playbook-models-breadth-b", f"{PC}/models/breadth-b", "explorer", "as-built and reviewed variants", "modules 07-11 machines",
     "supporting", "132 of 132 checks met; RESULTS.json", "", None),
    ("playbook-models-breadth-c", f"{PC}/models/breadth-c", "explorer", "as-built and reviewed variants", "modules 00 and 15-18 machines",
     "supporting", "39 of 39 checks met; RESULTS.json", "", None),
    ("playbook-models-core", f"{PC}/models/core", "explorer", "as-built and reviewed variants", "core erase/redact/replay machines",
     "supporting", "82 of 82 checks met, 0 truncated; RESULTS.json", "", None),
    ("playbook-models-core-partition", f"{PC}/models/core-partition", "explorer", "as-built and reviewed variants",
     "core machines partitioned per family", "supporting", "16 of 16 checks met; RESULTS.json; peak 17.1 GB", "", None),
    ("playbook-models-semantics", f"{PC}/models/semantics", "explorer", "as-built and reviewed variants",
     "mechanism instances (the twins proofs-mech reasons about)", "supporting", "272 of 272 checks met; RESULTS.json", "", None),
    ("playbook-simulator", f"{PC}/simulator", "native-probes", "as-built (observed)",
     "randomized schedules through the real product with an independent oracle", "supporting",
     "304 schedules, 16,051 operations; SIMULATOR.md, results.json", "observed on the playbook VM's IRIS", None),
    ("playbook-iris-contract", f"{PC}/iris-contract", "env-contract", "environment specification",
     "executable IRIS 2026.1 contract validated against the engine (round r6)", "supporting", "CONTRACT.md, VALIDATED_ROUND r6", "", None),
    ("playbook-contract-2", f"{PC}/contract-2", "env-contract", "environment specification", "second contract round and its coverage",
     "supporting", "COVERAGE-2.md, VALIDATED.json", "", None),
    ("playbook-lockplans", f"{PC}/lockplans", "explorer", "as-built and reviewed variants", "lock plans for modules 01, 05, 06, 08, 10, 16, 17",
     "partial", "46 of 46 model checks registered (lockplans-mc-*); live drafts PENDING-LIVE; PARTIAL.md",
     "partial, not integrated; candidates F-C0811 and F-C1711 are unfiled", None),
]

C = [  # this consolidation's new model directories: (name, scope, design, status, premises/notes)
    ("edge_acceptance", "ordinary create/store duplicate returns, temporal adoption, endpoint/refusal and SQL/adjacency distinction; one triple", "as-built transcription", "active"),
    ("vector_threshold", "optional inclusive cosine predicate and binds before row limit; adapted SQLite provider, no IRIS claim", "as-built transcription", "active"),
    ("aql_frontend", "numeric suffix lexer, typed depth AST/hops and literal null/text-null operators; query execution unproved", "as-built transcription", "active"),
    ("pagerank_admission", "COUNT:MAX node key, lazy hit/miss census and raw self-loop/isolate producer; numerics and concurrency unproved", "as-built transcription", "active"),
    ("history_diff", "named range/inverse and continuous per-attribute endpoints; deletion snapshot correction and range-prior lifecycle witness", "as-built transcription", "active"),
    ("node_read", "numeric Python writer, CY_TYPED tag/escape and batched node inclusion/aliases; scalar subset", "as-built transcription", "active"),
    ("ndjson_import", "raw kind selection, node admission, width refusal, duplicate counts and prefix state; node projection only", "as-built transcription", "active"),
    ("route_recheck", "NativeRoute held-call counter, trial reset, next-path selection and permanent SQL failure; drift disabled", "as-built transcription", "active"),
    ("warm_sources", "WarmFill guard, globals source census/count and whole-graph stamp; ObjectScript inspected only", "as-built transcription", "active"),
    ("temporal_window_reader", "the paged temporal window reader: window_spec, the Python cursor's paging and handle release, the server's filter and page producer", "as-built transcription", "active"),
    ("freshness_stamp", "Freshness and TraversalKHop.Fresh: a rebuilt store is current only when stamped and equal to the token", "as-built transcription", "active"),
    ("embedded_no_data", "the embedded cursor's no-row rule and row counts over its three execution paths and the batch call", "as-built transcription", "active"),
    ("rel_prop_text", "the relationship property text decoder by input class (ASCII canonical rule)", "reviewed (ASCII); the as-built pattern departs, see NOTES", "active"),
    ("index_declaration", "GraphSchema.ensure_adjacency_index as an ordered action list from catalog state", "as-built transcription", "active"),
    ("ledger_apply", "raw admitted changeset operations produce prior/new records, stop at first failure and roll back before revision publication; one graph", "as-built transcription", "active"),
    ("reconstruction", "named revision structural count/content projection, raw meta normalization, per-prefix bound and stream/export fold; full content/diff unproved", "as-built transcription", "active"),
    ("fusion_ranking", "Python first-rank producer, mathematical RRF scores, strict pair winner and provider catch/modes; general sort/details observed only", "as-built transcription", "active"),
    ("bulk_delete", "raw ID normalization, batch continuation, primary then cleanup failure, partial live effects and DeleteResult counts; one explicit graph", "as-built transcription", "active"),
    ("writer_id_reader", "writer paths into the Cypher id reader (create_node, bulk_create_nodes, BulkIngestNodesSQL)", "as-built transcription", "active"),
    ("row_limit_dialect", "the TOP / FETCH FIRST selector by engine construction path and query shape", "as-built transcription", "active"),
]


def premises(path):
    for name in ("PROOFS.md", "PARTIAL.md", "MODELS.md", "SIMULATOR.md", "CONTRACT.md", "COVERAGE-2.md"):
        if os.path.exists(f"{path}/{name}"):
            return f"{path}/{name}"
    return f"{PC}/TRUST.md"


def main():
    rows = []
    for m, scope, st, rec in G:
        rows.append([f"G-{m}", "G", f"{V}/models/{m}", "verus", "as-built (with repaired variants and witnesses)", scope, st, rec,
                     g_rerun(m), f"{V}/models/{m}/NOTES.md"])
    rows.append(["G-ledger_redaction-twin", "G", f"{V}/models/ledger_redaction/twin.rs", "twin", "as-built",
                 "exec functions proved equal to the model's match_string, has_prefix and matches; trusted line adapter", "supporting",
                 "51 verified, binary built; results/ledger_redaction/20261114T000124Z-twin",
                 "not re-run: the binding probe that uses it needs the guidance VM's IRIS", f"{V}/models/ledger_redaction/NOTES.md"])
    nobs = len(glob.glob(f"{V}/receipts/native/*.json"))
    rows.append(["G-native-probes", "G", f"{V}/native/probes", "native-probes", "as-built (observed)",
                 f"{nobs} final-candidate observations of public product entry points on the guidance arm's IRIS (x86_64 VM)", "active",
                 f"receipts/native/*.json ({nobs}); receipts/native/earlier/",
                 "not re-observed: no IVG IRIS here; rule 3 also forbids repeating the security-relevant probes", f"{V}/native/harness.py"])
    for fid, path, kind, design, scope, st, rec, why, prem in P:
        if kind in ("verus", "env-contract") and st != "partial" and os.path.exists(f"{path}/Cargo.toml"):
            rr = p_rerun(fid)
            if rr == "not re-run here":
                rr = "not re-run here: inherited; registry record named"
        elif fid in ("playbook-models-core", "playbook-models-core-partition"):
            rr = "not re-run: recorded peak memory above 8 GB (reviewed plan section 3.3)"
        elif fid == "playbook-uplift-model":
            rr = "not re-run: refinement-reviewed peaked at 10.4 GB on the VM"
        elif kind == "native-probes":
            rr = "not re-run: needs the playbook VM's IRIS; inherited"
        elif st == "partial":
            rr = "not re-run: partial lane"
        else:
            rr = "not re-run here: inherited (explorer or contract lane; registry record named)"
        rows.append([fid, "P", path, kind, design, scope, f"{st}: {why}" if why else st, rec, rr, prem or premises(path)])
    for m, scope, design, st in C:
        if not os.path.exists(f"{V}/models/{m}/model.json"):
            continue
        spec = json.load(open(f"{V}/models/{m}/model.json"))
        rows.append([f"C-{m}", "consolidated", f"{V}/models/{m}", "verus", design, scope, st,
                     f"new here: {spec.get('expected_verified')} expected verified, {len(spec['controls'])} controls",
                     c_rerun(m), f"{V}/models/{m}/NOTES.md"])
    with open(f"{V}/families.tsv", "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(H)
        w.writerows(rows)
    print(f"families.tsv: {len(rows)} families")


if __name__ == "__main__":
    main()
