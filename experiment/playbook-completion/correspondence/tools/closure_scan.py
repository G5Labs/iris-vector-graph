#!/usr/bin/env python3
"""§3.6 closure / §3.4 ownership for the ledger state: every product writer of ^IVG.Ledger and the ledger tables,
mapped to the modelled action that owns it, or reported as unmodelled.

    python closure_scan.py [--json OUT] [--self-test]

Sites: ObjectScript lines that Set / Kill / Merge / $Increment ^IVG.Ledger (iris_src/src/**/*.cls); SQL text that
INSERTs / UPDATEs / DELETEs ledger_revisions or ledger_stats; Python code that names ^IVG.Ledger or the ledger storage
in a write path (the snapshot restore). Each site's enclosing method is mapped through OWNER to an action of
actions.py; a site whose method is not in OWNER is unmodelled. --self-test adds a synthetic writer and requires it
to be reported.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
# a write target: ^IVG.Ledger(...) followed by "=" (Set), or after Kill / Merge, or inside $Increment
WRITE = re.compile(r"\^IVG\.Ledger(?:\((?:[^()]|\([^()]*\))*\))?\s*=(?!=)|\b(?:Kill|K)\s+[^;]*?\^IVG\.Ledger\b|"
                   r"\b(?:Merge|M)\s+\^IVG\.Ledger\b|\$I(?:ncrement)?\(\^IVG\.Ledger", re.I)
SQLW = re.compile(r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+[\w.]*ledger_(revisions|stats)", re.I)
DECL = re.compile(r"^(ClassMethod|Method|Trigger)\s+([%\w]+)")

OWNER = {
    "Graph.KG.Ledger.Enable": "enable-genesis / reenable", "Graph.KG.Ledger.Disable": "disable-strict",
    "Graph.KG.Ledger.SetStrict": "disable-strict", "Graph.KG.Ledger.CommitInTxn": "commit / replay",
    "Graph.KG.Ledger.WriteRevision": "commit / genesis / redact-final", "Graph.KG.Ledger.PurgeAll": "ADMIN (test reset; not modelled)",
    "Graph.KG.Ledger.RecordVerify": "verify (ledger_stats only)",
    "Graph.KG.LedgerApply.AllocStmt": "commit", "Graph.KG.LedgerApply.DeleteRelInternal": "commit",
    "Graph.KG.LedgerGenesis.Adopt": "reenable-adoption", "Graph.KG.LedgerGenesis.Capture": "enable-genesis",
    "Graph.KG.LedgerRedact.BatchInLock": "redact-batch", "Graph.KG.LedgerRedact.Tombstone": "redact-batch",
    "Graph.KG.LedgerRedact.ClearRevision": "redact-batch", "Graph.KG.LedgerRedact.FinalInLock": "redact-final",
    "Graph.KG.LedgerRedact.DropStatements": "redact-final",
    "Graph.KG.Eraser.EraseEdgeRow": "erase-nodes / erase-edges (EraseIndex, no head lock: F-1114)",
    "Graph.KG.Eraser.EraseLedgerFor": "erase-graph (EraseIndex, no head lock: F-1114)",
    "Graph.KG.Eraser.EraseAll": "erase-all (EraseIndex, no head lock)",
    "Graph.KG.LedgerStats.Bump": "commit (stats)", "Graph.KG.LedgerStats.Ensure": "commit (stats)",
}


def cls_sites(root: Path):
    for p in sorted(root.rglob("*.cls")):
        cls = ".".join(p.relative_to(root).with_suffix("").parts)
        meth = None
        for i, ln in enumerate(p.read_text().split("\n"), 1):
            m = DECL.match(ln)
            if m:
                meth = m.group(2)
            t = ln.strip()
            if t.startswith(("//", "///", ";")):
                continue
            if WRITE.search(t) or SQLW.search(t):
                yield {"site": f"{p.relative_to(REPO)}:{i}", "method": f"{cls}.{meth}", "text": t[:120]}


def py_sites(root: Path):
    for p in sorted(root.rglob("*.py")):
        text = p.read_text()
        for i, ln in enumerate(text.split("\n"), 1):
            t = ln.strip()
            if t.startswith("#"):
                continue
            if ('"IVG.Ledger"' in t or "'^IVG.Ledger" in t or '"^IVG.Ledger' in t) and ("(" in t or "," in t) and \
                    not t.startswith(('"""', "'''")) and "IVG.Ledger" in t and ("[[" in t or ".set(" in t or ".kill(" in t):
                yield {"site": f"{p.relative_to(REPO)}:{i}", "method": "python", "text": t[:120]}
            if SQLW.search(t):
                yield {"site": f"{p.relative_to(REPO)}:{i}", "method": "python", "text": t[:120]}


def scan(extra=None):
    sites = list(cls_sites(REPO / "iris_src" / "src")) + list(py_sites(REPO / "iris_vector_graph")) + (extra or [])
    for s in sites:
        s["owner"] = OWNER.get(s["method"])
        if s["method"] == "python" and "snapshot" in s["site"]:
            s["owner"] = None
            s["note"] = "restore_snapshot writes the archive's ^IVG.Ledger and ledger storage (F-1801): no modelled action"
    return sites


def main() -> int:
    if "--self-test" in sys.argv:
        fake = {"site": "synthetic:1", "method": "Graph.KG.Fake.Writer", "text": 'Set ^IVG.Ledger("head") = 0'}
        res = scan([fake])
        caught = any(s["site"] == "synthetic:1" and s["owner"] is None for s in res)
        print("closure self-test", "PASS" if caught else "FAIL")
        return 0 if caught else 1
    res = scan()
    un = [s for s in res if s["owner"] is None]
    out = {"sites": res, "unmodelled": un, "n_sites": len(res), "n_unmodelled": len(un)}
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, indent=1))
    print(f"{len(res)} writer sites of the ledger state; {len(un)} not owned by a modelled action")
    for s in un:
        print("  UNMODELLED", s["site"], s["method"], s.get("note", ""), s["text"][:80])
    return 0 if not un else 1


if __name__ == "__main__":
    raise SystemExit(main())
