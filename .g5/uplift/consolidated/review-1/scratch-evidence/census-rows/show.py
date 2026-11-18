#!/usr/bin/env python3
"""show.py ID [ID ...] — run from the repository root.

For each obligation id: the census row (start-of-iteration copy in scratch/iteration-64/before/), the block's
governing text and metadata section, every cited proof fn's parameters / requires / ensures header, and the latest
PASS prove receipt for each cited model directory. Read-only.
"""
import csv, glob, json, os, re, sys

sys.path.insert(0, ".g5/Verus_verification/tools")
import census  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEFORE = ".g5/Verus_verification/census/obligations.tsv"


def rows():
    with open(BEFORE, encoding="utf-8", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)}


def block_text(bid):
    for page in sorted(glob.glob(".g5/ontology/**/*.g5.md", recursive=True)):
        lines = open(page, encoding="utf-8").read().split("\n")
        try:
            i = lines.index(f'<a id="{bid}"></a>')
        except ValueError:
            continue
        nxt = next((l for l in lines[i + 1:i + 4] if l.strip()), "")
        if not re.match(r"^\[(I|D) · " + re.escape(bid) + r"\]", nxt):
            continue  # a redirect stub or alias anchor; the canonical block carries the [K · id] tag
        j = i + 1
        while j < len(lines) and not lines[j].startswith("<a id=") and not re.match(r"^#{1,6} ", lines[j]):
            j += 1
        body = "\n".join(lines[i + 1:j]).strip()
        meta = ""
        try:
            k = lines.index(f"### {bid}")
            m = k + 1
            while m < len(lines) and not lines[m].startswith("### ") and not lines[m].startswith("## "):
                m += 1
            meta = "\n".join(lines[k:m]).strip()
        except ValueError:
            pass
        return page, body, meta
    return None, "(block not found)", ""


def latest_prove(model_dir):
    lat = census.latest_receipts(f".g5/Verus_verification/results/{model_dir}")
    f = lat.get(("proof", None))
    if f:
        d = json.load(open(f))
        return f"{f} (verdict {d.get('verdict')})"
    return f"none of kind 'proof'; kinds present: {sorted(set(k[0] for k in lat))}"


def main(ids):
    R = rows()
    for oid in ids:
        r = R.get(oid)
        print("=" * 100)
        if not r:
            print(f"{oid}: not in the start census")
            continue
        for k, v in r.items():
            print(f"{k:18}: {v}")
        page, body, meta = block_text(r["block"])
        print(f"--- block {r['block']} ({page})")
        print(body)
        if meta:
            print("--- metadata")
            print(meta[:3000])
        models = set()
        for loc in census.split_list(r["model_locators"]):
            path, _, item = loc.partition("::")
            path, item = path.strip(), item.strip()
            if "/models/" in path:
                models.add(path.split("/models/")[1].split("/")[0])
            if path.endswith(".rs") and item:
                info = census.proof_fns(path).get(item)
                if info is None:
                    print(f"--- {item}: not a proof fn (spec fn / exec fn / type / other)")
                else:
                    pc = " [POINT CHECK]" if census.is_point_check(item, info) else ""
                    print(f"--- proof fn {item}({info['params'][:300]}){pc}")
                    print(f"    header: {info['header'][:1500]}")
        for m in sorted(models):
            print(f"--- latest PASS prove receipt for {m}: {latest_prove(m)}")


if __name__ == "__main__":
    main(sys.argv[1:])
