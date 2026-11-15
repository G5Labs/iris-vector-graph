#!/usr/bin/env python3
"""Regenerate .g5/Verus_verification/crosswalk/statements.tsv: one row per governing ontology block, with the playbook
statement IDs its metadata names under `Playbook:`, the relation and the public case it owns.

    python3 .g5/Verus_verification/tools/make_statements.py

Relations: `g-extended-from-p` (the block was extended or written in the consolidated uplift from the playbook
statements it names, checked at the pin), `same` (an unchanged block whose `Playbook:` line names statements with the
same rule), `p-only-linked` (unused here), `g-only` (no playbook statement is linked from this block yet: not compared,
which is not a claim that the playbook arm has nothing), `contradiction` (none found). Standard library only.
"""
import csv
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
G_TIP = "24c6b0c03e1c84cac6691de45c183fa1cf73940b"
CASES = {"ledger.commit": "M03", "temporal.window.sources": "M06", "temporal.window.paging": "M08",
         "temporal.window.paging.release": "M07;M08", "structure.rebuilt.stamp": "M09", "structure.multigraph.count": "M11",
         "algorithms.op.paths.weighted": "M12", "search.embedding.width": "M14", "search.routes.no_fallback": "M14",
         "install.bulk_load.loader": "M23", "install.snapshot.routes": "J01", "install.snapshot.temporal": "J02",
         "structure.adjacency.declare": "M16;J07", "adapters.embedded.no_data": "M17", "query.values.relationship_text": "M18",
         "ledger.commit.admission": "M01", "ledger.idempotency": "M02", "structure.degree.cache.uncommitted": "M10",
         "search.embedding.other_model": "M13", "algorithms.cache": "M21", "algorithms.cache.token": "J04",
         "ledger.commit.serial": "J05", "query.compiled.fallback": "J08;M20", "query.compiled.modes": "J08",
         "ledger.readers": "M04;M05;J03"}


def blocks(text):
    body, _, meta = text.partition("\n## Metadata")
    ids = re.findall(r"^\[[IDQ] · ([^\]]+)\]$", body, re.M)
    out = {}
    for i in ids:
        m = re.search(r"^### " + re.escape(i) + r"\n(.*?)(?=^### |\Z)", meta, re.M | re.S)
        out[i] = (m.group(1) if m else "", re.search(r'<a id="' + re.escape(i) + r'"></a>\n\[[IDQ] · [^\]]+\]\n(.*?)(?=\n<a id=|\n## |\Z)', body, re.S))
    return out


def main():
    rows = []
    for page in sorted((REPO / ".g5/ontology").rglob("*.g5.md")):
        rel = str(page.relative_to(REPO))
        text = page.read_text()
        try:
            old = subprocess.run(["git", "-C", str(REPO), "show", f"{G_TIP}:{rel}"], capture_output=True, text=True, check=True).stdout
        except subprocess.CalledProcessError:
            old = ""
        old_blocks = blocks(old) if old else {}
        for bid, (meta, bodym) in blocks(text).items():
            pl = re.search(r"^- Playbook:(.*)$", meta, re.M)
            pids = sorted(set(re.findall(r"\[([A-Z]{3}-[A-Za-z0-9.]+)\]", pl.group(1)))) if pl else []
            changed = bid not in old_blocks or (old_blocks[bid][1] and bodym and old_blocks[bid][1].group(1) != bodym.group(1)) or \
                (bid in old_blocks and old_blocks[bid][0] != meta)
            if pids:
                relation = "g-extended-from-p" if changed else "same"
            else:
                relation = "g-only"
            rows.append([bid, ";".join(pids), relation, CASES.get(bid, ""), rel, "new" if bid not in old_blocks else ("changed" if changed else "unchanged")])
    out = REPO / ".g5/Verus_verification/crosswalk/statements.tsv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["g_block", "p_statement_ids", "relation", "decision or case id", "page", "since 24c6b0c0"])
        w.writerows(rows)
    from collections import Counter
    print(f"statements.tsv: {len(rows)} blocks", Counter(r[2] for r in rows), Counter(r[5] for r in rows))


if __name__ == "__main__":
    main()
