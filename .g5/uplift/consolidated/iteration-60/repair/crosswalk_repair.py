"""Iteration-60 repair: crosswalk/decision-links.tsv edits (review 60 BC-1, BC-2 and the repaired formal roles).

Run once from the repository root: python3 .g5/uplift/consolidated/iteration-60/repair/crosswalk_repair.py
1. Relabel the 24 declaration-only class rows (15 errors.py classes, 9 value classes) from models/witnesses to `cites`
   (locator only), keeping them visible; the deciding member (`from_commit_error`, the readers) is bound separately.
2. Refresh the grades of the re-run C-ledger_client / C-ledger_verify rows to the repair binding receipts.
3. Correct the roles the review found contradicted or weakened (`_drop_temporal_marked`, `read_canonical`,
   `_adoption_items`, `Ledger.cls::Commit/CommitInTxn/WriteRevision`, `LedgerStats.cls::Bump/Ensure`).
4. Add rows for the repaired formal roles, with exact pin line ranges.
"""
import ast
import re
import sys

PIN = "/Users/ziniuw/runs/ivg-consolidated-20261114/pin"
TSV = ".g5/Verus_verification/crosswalk/decision-links.tsv"


def py_lines(path, qual):
    tree = ast.parse(open(f"{PIN}/{path}").read())

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = prefix + ch.name
                if q == qual:
                    return f"{ch.lineno}-{ch.end_lineno}"
                r = walk(ch, q + ".")
                if r:
                    return r
    return walk(tree, "")


def cls_lines(path, name):
    L = open(f"{PIN}/{path}").read().split("\n")
    for i, l in enumerate(L):
        if re.match(rf"^(ClassMethod|Method)\s+{re.escape(name)}\(", l):
            j = i
            while j < len(L) and L[j] != "}":
                j += 1
            return f"{i + 1}-{j + 1}"


# Raw tab-separated lines (no CSV quoting): other rows must keep their exact bytes.
_lines = open(TSV).read().split("\n")
assert _lines[-1] == ""
fields = _lines[0].split("\t")
rows = [dict(zip(fields, l.split("\t"))) for l in _lines[1:-1]]
assert all(len(l.split("\t")) == len(fields) for l in _lines[1:-1])
if any("iteration-60 repair" in r["role"] for r in rows):
    sys.exit("already applied")
GC = ("Observed (native binding on local fixture ivg-uplift-next-20261115, namespaces I60RA/I60RC/I60RE; ledger_client "
      "binding AGREES 52 cases, 27/28 mutations detected; iteration-60 repair after review 60)")
GV = ("Observed (native binding on local fixture ivg-uplift-next-20261115, namespaces I60RV/I60RT; ledger_verify binding "
      "AGREES 5 cases, 10/11 mutations detected; iteration-60 repair after review 60)")
DECL = {"iris_vector_graph/ledger/errors.py": ["LedgerError", "LedgerNotEnabledError", "LedgerDisabledError", "StaleHeadError",
                                               "UnknownRevisionError", "IdempotencyConflictError", "ChangesetOperationError",
                                               "ChangesetTooLargeError", "EmptyChangesetError", "ReconstructionTooLargeError",
                                               "LedgerLockTimeoutError", "LedgerTransactionOpenError", "LedgerInconsistencyError",
                                               "NodeNotFoundError", "IdempotencyRedactedError"],
        "iris_vector_graph/ledger/client.py": ["CommitResult", "RevisionInfo", "Revision", "LedgerCounters", "_CommitWireResult"],
        "iris_vector_graph/ledger/export.py": ["ExportSummary"],
        "iris_vector_graph/ledger/replay.py": ["Diff", "DiffEntry", "VerificationReport"]}
declset = {(p, s) for p, l in DECL.items() for s in l}
n = 0
for r in rows:
    k = (r["path"], r["symbol"])
    if k in declset:
        assert r["relation"] in ("models", "witnesses"), k
        r["relation"] = "cites"
        role = r["role"]
        if k == ("iris_vector_graph/ledger/errors.py", "LedgerInconsistencyError"):
            role = "value: transport failure, bad answer, or (repair) a revision row over its column limits (bug-led-015)"
        r["role"] = ("locator only (declaration-only class; relabelled cites in the iteration-60 repair, review 60 BC-1; "
                     "the deciding member is bound separately): " + role)
        r["grade"] = "Inspected only (declaration with no behaviour of its own; outcome observed through the deciding member's binding)"
        n += 1
assert n == 24, n
for r in rows:
    if r["family"] == "C-ledger_client" and r["relation"] != "cites":
        r["grade"] = GC
    if r["family"] == "C-ledger_verify" and r["relation"] != "cites":
        r["grade"] = GV
VR = ".g5/Verus_verification/models/ledger_verify/ledger_verify.rs::"
CR = ".g5/Verus_verification/models/ledger_client/ledger_client.rs::"


def setrole(path, sym, fam, role, item=None, rel=None):
    hit = [r for r in rows if r["path"] == path and r["symbol"] == sym and r["family"] == fam]
    assert len(hit) == 1, (path, sym, fam, len(hit))
    hit[0]["role"] = role
    if item:
        hit[0]["formal item"] = item
    if rel:
        hit[0]["relation"] = rel


R = "iris_vector_graph/ledger/replay.py"
setrole(R, "_drop_temporal_marked", "C-ledger_verify",
        "producer: the replay's marker rule: drops a statement whose qualifier temporal is the TEXT \"true\" (not read_canonical's "
        "JSON-boolean rule; repaired in the iteration-60 repair, review 60 FE-1, bug-led-013)", VR + "replay_marked", "models")
setrole(R, "read_canonical", "C-ledger_verify",
        "producer: tables view: a node from a node, label or non-reserved property row; reserved properties out; a row whose "
        "temporal qualifier is the JSON boolean true out; qualifier values as text (iteration-60 repair, review 60 FE-1, FE-2)")
setrole(R, "_adoption_items", "C-ledger_verify",
        "producer: entries become adoption items; closing the difference holds only when no tables relationship has temporal "
        "text \"true\" (narrowed in the iteration-60 repair)")
L = "iris_src/src/Graph/KG/Ledger.cls"
S = "iris_src/src/Graph/KG/LedgerStats.cls"
setrole(L, "Commit", "C-ledger_client",
        "decision: nested level; head unlock deferred to the outermost transaction end; Bump after the level, which waits and "
        "is lost while another transaction holds the counter row (iteration-60 repair, review 60 FE-3, bug-led-014)")
setrole(L, "CommitInTxn", "C-ledger_client",
        "decision: lock, state, key, redacted key, expected head, empty/size, apply, redaction block, revision row (field "
        "limits), counter row, write; the last three uncounted (iteration-60 repair, review 60 FE-4, FE-5)")
setrole(L, "WriteRevision", "C-ledger_client",
        "writer: revision row (a value over its MAXLEN fails the save -> inconsistent, no pBump: bug-led-015), head, id maps, "
        "commits_ok saved inside the commit's (caller's) transaction; idem bound after (iteration-60 repair)")
setrole(S, "Bump", "C-ledger_client",
        "writer: one counter per counted outcome in its own transaction; while another transaction holds the row its save "
        "waits about 10 s, fails and the count is lost (iteration-60 repair, review 60 FE-3, bug-led-014)")
setrole(S, "Ensure", "C-ledger_client",
        "state: the singleton counter row; a save of it inside a caller's transaction keeps the row locked until that "
        "transaction ends (iteration-60 repair)", CR + "stats_free")
new = []


def add(block, role, path, sym, fam, item, rel, grade):
    lines = py_lines(path, sym) if path.endswith(".py") else cls_lines(path, sym)
    assert lines, (path, sym)
    row = {f: "" for f in fields}
    row.update({"block": block, "role": role + " (iteration-60 repair)", "path": path, "symbol": sym, "pin lines": lines,
                "family": fam, "formal item": item, "relation": rel, "design": "as-built", "grade": grade})
    new.append(row)


add("ledger.verify.scope", "decision: the replay side never carries temporal text \"true\", so a tables relationship with it never verifies equal (bug-led-013)",
    R, "_drop_temporal_marked", "C-ledger_verify", VR + "theorem_text_marker_never_equal", "proves", GV)
add("ledger.verify.scope", "decision: the two marker rules with their neighbours (JSON-true row out of the tables; text-true statement out of the replay; text-true row kept; \"yes\" statement kept)",
    R, "_drop_temporal_marked", "C-ledger_verify", VR + "theorem_temporal_marked_rows_left_out", "proves", GV)
add("ledger.verify", "producer: every canonical view is well formed (a label or property row makes the node)",
    R, "read_canonical", "C-ledger_verify", VR + "lemma_canonical_wf", "proves", GV)
add("ledger.verify", "producer: a property row on an ID with no node row is reported as the node plus the property (review 60 FE-2)",
    R, "read_canonical", "C-ledger_verify", VR + "theorem_orphan_property_reports_node", "proves", GV)
add("ledger.verify", "decision: after adopting a text-\"true\" temporal relationship the next verify still diverges (adoption never closes it)",
    R, "verify", "C-ledger_verify", VR + "theorem_adoption_never_closes_a_text_marker", "proves", GV)
add("ledger.verify.scope", "writer: every qualifier stored as text in the edge row (so a committed temporal \"true\" is not the tables' JSON-boolean marker)",
    "iris_src/src/Graph/KG/LedgerApply.cls", "QualsJson", "C-ledger_verify", VR + "stores_as_text", "models", GV)
add("ledger.verify.scope", "producer: a Python True qualifier becomes the text \"true\" (so it hits the replay's marker)",
    "iris_vector_graph/ledger/changeset.py", "_str_value", "C-ledger_verify", VR + "theorem_marker_rules_differ", "models", GV)
add("ledger.verify.scope", "locator only (intent source): genesis's marker test is the tables' JSON-boolean rule and calls a text \"true\" an ordinary qualifier; genesis capture is outside ledger_verify",
    "iris_src/src/Graph/KG/LedgerGenesis.cls", "TemporalMarked", "C-ledger_verify", VR + "table_marked", "cites",
    "Inspected only (source comment; genesis capture is ledger_content's scope)")
add("ledger.readers", "decision: refuses every revision-ID reader while a redaction is unfinished, before the ID lookup (review 60 FE-6)",
    "iris_vector_graph/ledger/client.py", "GraphLedger._refuse_while_redacting", "C-ledger_client", CR + "seq_read", "models", GC)
add("ledger.readers", "decision: RedactionInProgressError for any ID while redacting; UnknownRevisionError only after",
    "iris_vector_graph/ledger/client.py", "GraphLedger._refuse_while_redacting", "C-ledger_client", CR + "theorem_revision_readers_resolve_ids", "proves", GC)
add("ledger.readers", "reader: the redaction marker the revision-ID readers and verify consult (Graph.KG.LedgerRedact.InProgress); justified shared delegate of the model's `redacting` state",
    "iris_vector_graph/ledger/client.py", "GraphLedger.redaction_in_progress", "C-ledger_client", CR + "seq_read", "models", GC)
add("ledger.observability", "writer: the strict guard's counter call; its Bump is lost while another transaction holds the counter row (bug-led-014)",
    L, "Count", "C-ledger_client", CR + "count_strict", "models", GC)
add("ledger.observability", "decision: which outcomes are counted; nothing is counted while another transaction holds the row",
    S, "Bump", "C-ledger_client", CR + "theorem_uncounted_outcomes", "proves", GC)
add("ledger.commit.caller-transaction", "decision: a counted nested commit keeps the counter row; the competing lock-timeout is not counted",
    S, "Bump", "C-ledger_client", CR + "theorem_caller_transaction_holds_the_head", "proves", GC)
add("ledger.commit.size", "decision: a revision row over its column limits is refused as inconsistent after apply, uncounted; a keyed retry replays first",
    L, "WriteRevision", "C-ledger_client", CR + "theorem_field_limits_checked_after_the_key", "proves", GC)
add("ledger.observability", "decision: redaction-blocked, field-limit and not-enabled refusals move no counter",
    L, "CommitInTxn", "C-ledger_client", CR + "theorem_uncounted_outcomes", "proves", GC)
add("ledger.commit.caller-transaction", "decision: an uncounted nested refusal holds the head but not the counter row (the competing refusal is counted after 30 s)",
    L, "Commit", "C-ledger_client", CR + "theorem_uncounted_nested_refusal_leaves_the_counter_row", "proves", GC)
last = max(i for i, r in enumerate(rows) if r["family"] in ("C-ledger_verify", "C-ledger_client"))
rows[last + 1:last + 1] = new
for r in rows:
    assert all("\t" not in r[f] and "\n" not in r[f] for f in fields)
open(TSV, "w").write("\n".join(["\t".join(fields)] + ["\t".join(r[f] for f in fields) for r in rows]) + "\n")
print("relabelled", n, "added", len(new), "rows", len(rows))
