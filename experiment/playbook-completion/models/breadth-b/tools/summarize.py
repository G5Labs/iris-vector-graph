#!/usr/bin/env python3
"""Print breadth lane B per-module counts from the output files (read-only)."""
import collections, json, sys
from pathlib import Path
C = Path(__file__).resolve().parents[3]
res = json.loads((C / "models/breadth-b/RESULTS.json").read_text())["checks"]
for m in sys.argv[1:] or ["07", "08", "09", "10", "11"]:
    inv = json.loads((C / f"models/breadth-b/inventory/{m}.json").read_text())
    fp = json.loads((C / f"footprints/{m}.json").read_text())["entry_points"]
    fa = json.loads((C / f"findings/audit/{m}.json").read_text())
    md = json.loads((C / f"modules/{m}.json").read_text())
    jv = [e for e in fp if e.get("journal_validation")]
    mism = [e["id"] for e in jv if e["journal_validation"].get("match") is False]
    disp = collections.Counter(f["disposition"] for f in fa["findings"])
    outc = collections.Counter(f.get("outcome") for f in fa["findings"])
    mc = collections.Counter((c["design"], c["result"]) for c in res if c["module"] == m)
    gb = collections.Counter(v.get("status") for v in (md.get("gates_by_id") or {}).values())
    so_raw = md.get("storage_order") or []
    so = so_raw.get("counts") if isinstance(so_raw, dict) else collections.Counter(str(x.get("disposition"))[:20] for x in so_raw)
    so = so or {k: (len(v) if isinstance(v, list) else v) for k, v in so_raw.items() if k != "input"}
    so = {**so, "gate": (md.get("gates_by_id") or {}).get("3.4-storage-order", {}).get("status")}
    print(f"== {m}: entry points {inv['counts']['entry_points']}, uncovered {inv['counts']['omissions']}, "
          f"cells {inv['counts']['cells']}, cells w/o entry {inv['counts']['cells_without_entry_point']}")
    print(f"   footprints {len(fp)}, journal-validated {len(jv)}, mismatches {mism}")
    print(f"   models {dict(mc)}")
    print(f"   findings {len(fa['findings'])} disp {dict(disp)} outcome {dict(outc)}")
    print(f"   new {[(n['id'], n.get('severity'), n.get('disposition'), n['title'][:90]) for n in fa.get('new_findings', [])]}")
    print(f"   env_features {len(md.get('env_features', []))}; gates_by_id {dict(gb)}; storage_order {dict(so)}")
