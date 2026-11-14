#!/usr/bin/env python3
"""Aggregate the frame runs into a per-module summary (the decisive check of gate 3.6-frame).

    python aggregate.py OUT.json LIVE.json [LIVE.json ...]

Per module: writer actions run, exercised (no error, >= 1 journaled record), store-level and key-level results,
excursions (node, store, class), declaration gaps, statement-shape classes observed in the journal against the
classes present in the module's source (shape_census.py output, $RUN_DIR/structural/frame/shape-census.json).
Exit 0 always: the verdict is data (excursions are product or declaration results, not harness failures).
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Frame-granular statement-shape classes. The journal records a Set, a $Increment outside a transaction and a Merge
# all as SET records of the nodes written, with the same frame (the nodes named); so the global write classes are
# observed together. A DELETE is by key or by predicate according to the action's key specification.
NODE_WRITE = ["global-set", "global-increment", "global-merge", "native-set", "native-increment"]
JOURNAL_TO_STATIC = {"sql-insert": ["sql-insert", "obj-save"], "sql-update": ["sql-update", "obj-save"],
                     "global-set": NODE_WRITE, "global-increment": NODE_WRITE,
                     "global-kill": ["global-kill", "native-kill"], "sql-ddl-catalog": ["sql-ddl"]}
GRAPHS = {"fg", "fz"}


def delete_kind(a):
    keys = a.get("keys_used") or a.get("keys") or []
    if any(str(k).startswith("prefix:") or k in GRAPHS for k in keys) or len(keys) >= 9:
        return ["sql-delete-predicate", "obj-delete"]
    return ["sql-delete-key", "obj-delete"]


def main() -> int:
    out_p = Path(sys.argv[1])
    census = json.loads((Path(os.environ["RUN_DIR"]) / "structural/frame/shape-census.json").read_text())
    acts = []
    for p in sys.argv[2:]:
        d = json.loads(Path(p).read_text())
        for a in d["actions"]:
            a["_log"] = p
            acts.append(a)
    # later runs of the same action id supersede earlier ones (reruns after a harness fix are listed)
    latest = {}
    for a in acts:
        latest[a["id"]] = a
    per = defaultdict(lambda: {"actions": [], "exercised": 0, "store_ok": 0, "key_ok": 0, "errors": [],
                               "harness_errors": [], "store_excursions": [], "key_excursions": [], "gaps": [],
                               "journal_classes": defaultdict(int), "not_exercised": [],
                               "static_seen": set()})
    for a in latest.values():
        m = per[a["module"]]
        m["actions"].append(a["id"])
        if a.get("harness_error"):
            m["harness_errors"].append(f"{a['id']}: {a['harness_error'][:200]}")
            m["not_exercised"].append(a["id"])
            continue
        chk = a["check"]
        if a.get("error"):
            m["errors"].append(f"{a['id']}: {a['error'][:200]}")
        if not a.get("exercised"):
            m["not_exercised"].append(a["id"] + (" (refused/error)" if a.get("error") else " (no journaled write)"))
        else:
            m["exercised"] += 1
            for n in a.get("written_nodes", []):  # a %KillExtent / extent kill: KILL of a class data global's root
                t, _, node = n.partition(" ")
                if t.startswith("KILL") and "(" not in node and node.endswith("D") and node.startswith("^Graph.KG."):
                    m["static_seen"] |= {"obj-delete", "sql-delete-key", "sql-delete-predicate"}
            for k, v in chk["classes"].items():
                m["journal_classes"][k] += v
                if k == "sql-delete":   # every deleted row was checked against the action's key spec (ids, graph or prefix)
                    for st in ("sql-delete-key", "sql-delete-predicate", "obj-delete"):
                        m["static_seen"].add(st)
        if chk["store_ok"]:
            m["store_ok"] += 1
        else:
            m["store_excursions"] += [dict(x, action=a["id"]) for x in chk["store_excursions"][:8]]
        if chk["key_ok"]:
            m["key_ok"] += 1
        else:
            m["key_excursions"] += [dict(x, action=a["id"]) for x in chk["key_excursions"][:8]]
        m["gaps"] += [f"{a['id']}: {g}" for g in chk["declaration_gaps"]]
    res = {}
    for mod, m in sorted(per.items()):
        static = sorted(census.get(mod, {}).keys())
        seen = set(m["static_seen"])
        for jc in m["journal_classes"]:
            seen |= set(JOURNAL_TO_STATIC.get(jc, []))
        unexercised_classes = [c for c in static if c not in seen]
        res[mod] = {"actions": len(m["actions"]), "exercised": m["exercised"], "store_ok": m["store_ok"],
                    "key_ok": m["key_ok"], "errors": m["errors"], "harness_errors": m["harness_errors"],
                    "not_exercised": m["not_exercised"], "store_excursions": m["store_excursions"][:20],
                    "key_excursions": m["key_excursions"][:30], "declaration_gaps": sorted(set(m["gaps"]))[:30],
                    "journal_classes": dict(m["journal_classes"]), "static_classes": static,
                    "static_classes_unexercised": unexercised_classes, "action_ids": sorted(m["actions"])}
        print(f"{mod}: {m['exercised']}/{len(m['actions'])} exercised, store_ok {m['store_ok']}, key_ok {m['key_ok']}, "
              f"store_exc {len(m['store_excursions'])}, key_exc {len(m['key_excursions'])}, "
              f"classes unexercised {unexercised_classes}")
    out_p.write_text(json.dumps({"inputs": sys.argv[2:], "modules": res}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
