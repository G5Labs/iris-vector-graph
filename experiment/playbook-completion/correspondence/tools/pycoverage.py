#!/usr/bin/env python3
"""Python line coverage of the module 11-14 handler functions in the checked traces.

    python pycoverage.py RUN_DIR... --json OUT

Executable lines of a function are the line numbers its compiled code objects (and nested ones) carry (co_lines),
i.e. exactly the lines the tracer of scenarios.py can report; the def line itself is excluded. A line is exercised
when any run's pycov.json lists it.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

HANDLERS = {
    "iris_vector_graph/ledger/client.py": ["GraphLedger._call", "GraphLedger._call_json", "GraphLedger._refresh_guard",
                                           "GraphLedger._refuse_in_caller_transaction", "GraphLedger.enable",
                                           "GraphLedger.disable", "GraphLedger.set_strict", "GraphLedger.meta",
                                           "GraphLedger.head", "GraphLedger._send_changeset", "GraphLedger.commit",
                                           "GraphLedger._commit", "GraphLedger._apply_post_commit_properties",
                                           "GraphLedger._seq_of", "GraphLedger.history", "GraphLedger.redact",
                                           "GraphLedger.redaction_in_progress", "GraphLedger._refuse_while_redacting",
                                           "GraphLedger.get_revision", "GraphLedger.diff", "GraphLedger.reconstruct",
                                           "GraphLedger.export_reconstruction", "GraphLedger.verify", "_class_value"],
    "iris_vector_graph/ledger/replay.py": ["verify", "read_canonical", "compare", "reconstruct", "iter_records",
                                           "iter_records_sql", "_adoption_items", "_drop_temporal_marked", "GraphState.apply",
                                           "fetch_history", "fetch_revision_info"],
    "iris_vector_graph/ledger/errors.py": ["from_commit_error"],
    "iris_vector_graph/_write_txn.py": ["caller_transaction_level", "write_txn", "WriteTxn.begin", "WriteTxn.commit",
                                        "WriteTxn.rollback", "WriteTxn.native", "WriteTxn._call", "WriteTxn.__enter__",
                                        "WriteTxn.__exit__", "WriteTxn.__init__"],
    "iris_vector_graph/_engine/nodes_edges.py": ["NodesEdgesMixin.erase_graph", "NodesEdgesMixin.delete_nodes_by_prefix",
                                                 "NodesEdgesMixin.erase_all"],
    "iris_vector_graph/stores/iris_sql_store.py": ["IRISGraphStore.delete_nodes_by_prefix", "IRISGraphStore._call_classmethod"],
}


def functions(path: Path):
    src = path.read_text()
    tree = ast.parse(src)
    out = {}

    def visit(node, prefix=""):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, ast.ClassDef):
                visit(ch, prefix + ch.name + ".")
            elif isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[prefix + ch.name] = ch
    visit(tree)
    code = compile(src, str(path), "exec")
    lines_by_first = {}

    def walk(co):
        for c in co.co_consts:
            if hasattr(c, "co_code"):
                lines_by_first.setdefault(c.co_firstlineno, set()).update(
                    ln for _, _, ln in c.co_lines() if ln is not None)
                walk(c)
    walk(code)
    res = {}
    for name, fn in out.items():
        first = min([fn.lineno] + [d.lineno for d in fn.decorator_list])
        ex = set()
        for fl, ls in lines_by_first.items():
            if first <= fl <= fn.end_lineno:
                ex |= {ln for ln in ls if fn.lineno < ln <= fn.end_lineno}
        res[name] = {"lines": f"{fn.lineno}-{fn.end_lineno}", "executable": sorted(ex)}
    return res


def main() -> int:
    runs = [Path(a) for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(sys.argv[sys.argv.index("--json") + 1])
    runs = [r for r in runs if r != out]
    hit = {}
    for r in runs:
        p = r / "pycov.json"
        if p.exists():
            for f, ls in json.loads(p.read_text()).items():
                hit.setdefault(f, set()).update(ls)
    rep = {"runs": [r.name for r in runs], "files": {}}
    for f, names in HANDLERS.items():
        fs = functions(REPO / f)
        src = (REPO / f).read_text().split("\n")
        rows = []
        for n in names:
            if n not in fs:
                rows.append({"function": n, "note": "not found"})
                continue
            ex = fs[n]["executable"]
            un = [ln for ln in ex if ln not in hit.get(f, set())]
            rows.append({"function": n, "lines": fs[n]["lines"], "executable": len(ex), "exercised": len(ex) - len(un),
                         "unexercised": [{"line": ln, "text": src[ln - 1].strip()[:120]} for ln in un]})
        rep["files"][f] = rows
        tot = sum(r.get("executable", 0) for r in rows)
        ex = sum(r.get("exercised", 0) for r in rows)
        print(f"{f}: {ex}/{tot} executable lines of the handler functions exercised")
    out.write_text(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
