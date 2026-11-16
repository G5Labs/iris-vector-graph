#!/usr/bin/env python3
"""Iteration 25 reconciliation: add crosswalk rows for question-card anchors added by commit 9c649ed9.

The refreshed question cards placed an identity anchor (marked `<!-- question identity -->`) above existing register
entries and moved 15 child questions out of ontology pages into open_questions.md. Existing rows are kept unchanged;
this only appends one row per anchor that has none. Idempotent. Standard library only.
"""
import csv, re, subprocess
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
V = REPO / ".g5/Verus_verification"
TSV = V / "crosswalk/questions.tsv"
BEFORE = "61fe8112"  # last commit before the question-card refresh

def prior_page(anchor):
    out = subprocess.run(["git", "-C", str(REPO), "grep", "-l", f'<a id="{anchor}"></a>', BEFORE, "--", ".g5/ontology"],
                         capture_output=True, text=True).stdout.split()
    return out[0].split(":", 1)[1] if out else ""

rows = list(csv.DictReader(TSV.open(), delimiter="\t"))
for r in rows:
    if r["source_arm"] == "Q" and not r.get("audit evidence"):
        r["audit evidence"] = ".g5/uplift/consolidated/iteration-25/reconcile_question_cards.py"
fields = list(rows[0].keys())
have = {r["canonical_id"] for r in rows}
lines = (V / "open_questions.md").read_text().split("\n")
added = []
for i, line in enumerate(lines):
    for a in re.findall(r'<a id="([^"]+)"', line):
        if a in have:
            continue
        nxt = re.findall(r'<a id="([^"]+)"', lines[i + 1]) if i + 1 < len(lines) else []
        title = next((l[4:] for l in lines[i:i + 4] if l.startswith("### ")), "")[:120]
        if nxt and nxt[0] in have and "question identity" in line:
            rel, note = "question-card identity", f"identity anchor of {nxt[0]}"
        else:
            rel, note = "moved from ontology child Q", f"was a child question in {prior_page(a) or 'no prior ontology page'}"
        r = dict.fromkeys(fields, "")
        r.update({"source_arm": "Q", "source_id": a, "source_path": ".g5/Verus_verification/open_questions.md",
                  "canonical_id": a, "relation": rel, "effect key": title, "source disposition": note,
                  "canonical_path": ".g5/Verus_verification/open_questions.md",
                  "audit disposition": "question-card refresh 9c649ed9; reconciled iteration 25",
                  "audit evidence": ".g5/uplift/consolidated/iteration-25/reconcile_question_cards.py"})
        rows.append(r); have.add(a); added.append((a, rel))
with TSV.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n"); w.writeheader(); w.writerows(rows)
print(f"added {len(added)} rows:", {k: sum(1 for _, r in added if r == k) for k in {r for _, r in added}})
