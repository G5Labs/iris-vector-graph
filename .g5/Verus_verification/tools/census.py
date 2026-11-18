#!/usr/bin/env python3
"""Obligation census over the canonical ontology blocks (harness: uplift-scoring.md "Census of ontology obligations").

    python3 .g5/Verus_verification/tools/census.py            # validate, print the census, write census/summary.md
    python3 .g5/Verus_verification/tools/census.py --init     # add missing blocks as not-started (never edits graded rows)
    python3 .g5/Verus_verification/tools/census.py --dir D    # same checks on a working copy of the three TSVs in D

Run from the repository root. Standard library only; deterministic (no clock, no randomness). Exit 0 when every
check passes, 1 otherwise. It never prints a whole-foundation percentage while any block is not-started or partial.

Inputs (.g5/Verus_verification/census/):
  blocks.tsv       one row per canonical block ([I · id] / [D · id]) in .g5/ontology
  obligations.tsv  one row per counted obligation, id <block>#oNN
  excluded.tsv     rationale, undecided alternatives, navigation, evidence annotations, restatements (with owner)

Failures: a block missing from (or unknown to) blocks.tsv; a page or kind that no longer matches; a graded block
(complete or partial) whose governing-text hash changed (STALE); an obligation or exclusion naming an unknown block or
a not-started block; a count in blocks.tsv that disagrees with obligations.tsv; a bad enum value; a model locator whose
file or named item does not resolve; a cited receipt that does not exist, is not the latest of its kind for its model
and label, carries the wrong verdict or whose recorded inputs changed; a parent entailment naming an unknown obligation;
a restatement whose owner does not resolve.
"""
import csv
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

ONT = ".g5/ontology"
V = ".g5/Verus_verification"
CEN = f"{V}/census"
BLOCKS_COLS = ["block", "page", "kind", "sha256", "status", "obligations", "excluded", "structural_zero",
               "parent", "children", "owners_checked", "iteration"]
OBL_COLS = ["id", "block", "locator", "statement", "cases", "observation", "model_locators", "premises", "grade",
            "design_check", "check_scope", "design_receipts", "as_built", "parent_entailment", "gap", "grade_source",
            "iteration"]
EXC_COLS = ["id", "block", "locator", "kind", "owner", "reason", "iteration"]
STATUS = {"complete", "partial", "not-started"}
GRADES = ["full", "partial", "absent", "unassessed"]
CHECKS = ["proved", "bounded", "refuted", "unchecked", "none"]
SCOPES = {"full", "narrowed", "n/a"}
EXC_KINDS = {"rationale", "undecided-alternative", "navigation", "evidence-annotation", "restatement", "definition",
             "cross-reference"}
AS_BUILT_KINDS = {"binding", "native", "upstream-test", "inspection", "none"}

ANCHOR = re.compile(r'^<a id="([^"]+)"></a>\s*$')
TAG = re.compile(r'^\[(I|D) · ([^\]]+)\]\s*$')
HEADING = re.compile(r'^#{1,6} ')
LINK_ID = re.compile(r'\]\(([^)]*)\)')


def sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def parse_ontology():
    """Return {id: {page, kind, sha256, parent, children, order}} for every canonical block."""
    blocks = {}
    order = 0
    for page in sorted(glob.glob(f"{ONT}/**/*.g5.md", recursive=True)):
        lines = open(page, encoding="utf-8").read().split("\n")
        meta_at = next((i for i, l in enumerate(lines) if l.strip() == "## Metadata"), len(lines))
        i = 0
        while i < meta_at:
            m = ANCHOR.match(lines[i])
            if m:
                j = i + 1
                while j < meta_at and not lines[j].strip():
                    j += 1
                t = TAG.match(lines[j]) if j < meta_at else None
                if t and t.group(2) == m.group(1):
                    k = j + 1
                    while k < meta_at and not ANCHOR.match(lines[k]) and not HEADING.match(lines[k]):
                        k += 1
                    body = [l.rstrip() for l in lines[j:k]]
                    while body and not body[-1]:
                        body.pop()
                    bid = m.group(1)
                    if bid in blocks:
                        raise SystemExit(f"duplicate block id {bid} in {page} and {blocks[bid]['page']}")
                    blocks[bid] = {"page": page, "kind": t.group(1),
                                   "sha256": hashlib.sha256("\n".join(body).encode()).hexdigest(),
                                   "parent": [], "children": [], "order": order}
                    order += 1
                    i = k
                    continue
            i += 1
        # metadata: ### id sections, "- Children:" and "- Expands:" lines
        cur = None
        for l in lines[meta_at:]:
            if l.startswith("### "):
                cur = l[4:].strip()
            elif cur in blocks and re.match(r'^- (Children|Expands):', l):
                ids = [u.split("#", 1)[1] for u in LINK_ID.findall(l) if "#" in u]
                key = "children" if l.startswith("- Children:") else "parent"
                blocks[cur][key] += ids
    for b in blocks.values():
        b["parent"] = [x for x in b["parent"] if x in blocks]
        b["children"] = [x for x in b["children"] if x in blocks]
    return blocks


def read_tsv(path, cols):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        if r.fieldnames != cols:
            raise SystemExit(f"{path}: header {r.fieldnames} != {cols}")
        return list(r)


def write_tsv(path, cols, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(r.get(c, "") for c in cols) + "\n")


ITEM_RS = r'(?:\bfn|\bstruct|\benum|\bconst|\btype|\bmacro_rules!)\s+{}\b'


def resolve_locator(loc):
    """path::item -> None if it resolves, else a problem string."""
    path, _, item = loc.partition("::")
    path = path.strip()
    item = item.strip()
    if not os.path.exists(path):
        return f"model file missing: {path}"
    if path.endswith(".rs"):
        if not item:
            return f"no item named in Rust locator {loc}"
        if not re.search(ITEM_RS.format(re.escape(item)), open(path, encoding="utf-8").read()):
            return f"item {item} not found in {path}"
    elif item:
        if item not in open(path, encoding="utf-8").read():
            return f"text {item!r} not found in {path}"
    return None


_latest_cache = {}


def latest_receipts(results_dir):
    """{(kind, label): receipt path} for the latest receipt of each kind/label under results/<model>/."""
    if results_dir in _latest_cache:
        return _latest_cache[results_dir]
    latest = {}
    for f in sorted(glob.glob(f"{results_dir}/*/receipt.json")):
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        kind = d.get("kind")
        if kind == "playbook-crate-rerun":
            key = ("playbook", d.get("label"))
        elif "control" in d and isinstance(d["control"], dict):
            key = ("control", d["control"].get("name"))
        else:
            key = (kind, None)
        latest[key] = f
    _latest_cache[results_dir] = latest
    return latest


def check_receipt(path):
    """None if the cited receipt exists, is the latest of its kind and label, has the expected verdict and fresh
    recorded inputs; else a problem string."""
    if not os.path.exists(path):
        return f"receipt missing: {path}"
    if not path.endswith(".json"):
        return None
    try:
        d = json.load(open(path))
    except ValueError:
        return f"receipt unreadable: {path}"
    if path.startswith(f"{V}/receipts/native/"):
        ins = d.get("_probe_inputs") or {}
        bad = [p for p, x in ins.items() if sha(p) != x]
        return f"native receipt inputs changed: {path}: {bad[:3]}" if bad else None
    if path.startswith(f"{V}/results/"):
        rdir = os.path.dirname(os.path.dirname(path))
        kind = d.get("kind")
        if kind == "playbook-crate-rerun":
            key, want = ("playbook", d.get("label")), ("PASS" if d.get("label") == "baseline" else "EXPECTED_FAIL")
            try:
                tree = subprocess.check_output(["git", "rev-parse", f"HEAD:{d['crate']}"], text=True,
                                               stderr=subprocess.DEVNULL).strip()
            except (subprocess.CalledProcessError, KeyError):
                tree = None
            if tree != d.get("sources", {}).get("tree_at_source"):
                return f"playbook crate tree changed since {path}"
        elif "control" in d and isinstance(d["control"], dict):
            key, want = ("control", d["control"].get("name")), "EXPECTED_FAIL"
        else:
            key, want = (kind, None), ("AGREES" if kind == "binding" else "PASS")
        if latest_receipts(rdir).get(key) != path:
            return f"not the latest {key[0]} receipt{' ' + str(key[1]) if key[1] else ''}: {path} (latest {latest_receipts(rdir).get(key)})"
        if d.get("verdict") != want:
            return f"receipt verdict {d.get('verdict')} != {want}: {path}"
        ins = d.get("inputs") or {}
        if isinstance(ins, dict):
            bad = [p for p, x in ins.items() if sha(p) != x]
            if bad:
                return f"receipt inputs changed (STALE): {path}: {bad[:3]}"
    return None


def split_list(s):
    return [x.strip() for x in s.split(";") if x.strip() and x.strip().lower() not in ("none", "-")]


def pct(a, b):
    return "N/A" if b == 0 else f"{100.0 * a / b:.1f}%"


def main(argv):
    global CEN
    init = "--init" in argv
    if "--dir" in argv:  # validate a working copy elsewhere (same rules, summary written there)
        CEN = argv[argv.index("--dir") + 1]
    blocks = parse_ontology()
    problems, notes = [], []
    os.makedirs(CEN, exist_ok=True)
    brows = read_tsv(f"{CEN}/blocks.tsv", BLOCKS_COLS)
    by_block = {}
    for r in brows:
        if r["block"] in by_block:
            problems.append(f"blocks.tsv: duplicate row {r['block']}")
        by_block[r["block"]] = r
    if init:
        for bid, b in blocks.items():
            if bid not in by_block:
                by_block[bid] = {"block": bid, "page": b["page"], "kind": b["kind"], "sha256": b["sha256"],
                                 "status": "not-started", "obligations": "0", "excluded": "0", "structural_zero": "",
                                 "parent": ",".join(b["parent"]), "children": ",".join(b["children"]),
                                 "owners_checked": "", "iteration": ""}
            elif by_block[bid]["status"] == "not-started":
                by_block[bid].update(sha256=b["sha256"], page=b["page"], kind=b["kind"],
                                     parent=",".join(b["parent"]), children=",".join(b["children"]))
        rows = sorted(by_block.values(), key=lambda r: blocks[r["block"]]["order"] if r["block"] in blocks else 10**9)
        write_tsv(f"{CEN}/blocks.tsv", BLOCKS_COLS, rows)
        print(f"blocks.tsv: {len(rows)} rows")
        return 0

    for bid in blocks:
        if bid not in by_block:
            problems.append(f"block missing from blocks.tsv: {bid} ({blocks[bid]['page']})")
    for bid, r in by_block.items():
        b = blocks.get(bid)
        if b is None:
            problems.append(f"blocks.tsv names a block not in the ontology: {bid}")
            continue
        if r["status"] not in STATUS:
            problems.append(f"{bid}: status {r['status']!r}")
        if r["page"] != b["page"] or r["kind"] != b["kind"]:
            problems.append(f"{bid}: page/kind {r['page']} {r['kind']} != current {b['page']} {b['kind']} (MOVED)")
        if r["sha256"] != b["sha256"]:
            if r["status"] in ("complete", "partial"):
                problems.append(f"STALE {bid}: governing text changed since it was graded")
            else:
                notes.append(f"not-started {bid}: hash refreshed by --init")
        if sorted(r["parent"].split(",") if r["parent"] else []) != sorted(b["parent"]) or \
                sorted(r["children"].split(",") if r["children"] else []) != sorted(b["children"]):
            problems.append(f"{bid}: parent/children differ from the metadata")

    orows = read_tsv(f"{CEN}/obligations.tsv", OBL_COLS)
    erows = read_tsv(f"{CEN}/excluded.tsv", EXC_COLS)
    oids = {}
    count = {}
    for r in orows:
        oid, bid = r["id"], r["block"]
        if oid in oids:
            problems.append(f"duplicate obligation id {oid}")
        oids[oid] = r
        if not re.fullmatch(re.escape(bid) + r"#o\d{2,}", oid):
            problems.append(f"{oid}: id does not have the form <block>#oNN")
        if bid not in blocks or bid not in by_block:
            problems.append(f"{oid}: unknown block {bid}")
            continue
        if by_block[bid]["status"] == "not-started":
            problems.append(f"{oid}: block {bid} is not-started")
        count[bid] = count.get(bid, 0) + 1
        if r["grade"] not in GRADES:
            problems.append(f"{oid}: grade {r['grade']!r}")
        if r["design_check"] not in CHECKS:
            problems.append(f"{oid}: design_check {r['design_check']!r}")
        if r["check_scope"] not in SCOPES:
            problems.append(f"{oid}: check_scope {r['check_scope']!r}")
        for loc in split_list(r["model_locators"]):
            p = resolve_locator(loc)
            if p:
                problems.append(f"{oid}: {p}")
        for rec in split_list(r["design_receipts"]):
            p = check_receipt(rec)
            if p:
                problems.append(f"{oid}: {p}")
        if r["grade"] == "full" and not split_list(r["model_locators"]):
            problems.append(f"{oid}: full without a model locator")
        if r["design_check"] in ("proved", "bounded", "refuted") and not split_list(r["design_receipts"]):
            problems.append(f"{oid}: design check {r['design_check']} without a receipt")
        if r["design_check"] in ("proved", "bounded", "refuted") and r["check_scope"] == "n/a":
            problems.append(f"{oid}: design check {r['design_check']} needs check_scope full or narrowed")
        for ent in split_list(r["as_built"]):
            parts = ent.split(" ", 2)
            if parts[0] not in AS_BUILT_KINDS:
                problems.append(f"{oid}: as_built kind {parts[0]!r}")
            elif parts[0] in ("binding", "native", "upstream-test") and len(parts) == 3:
                path = parts[2].strip()
                p = check_receipt(path) if path.endswith(".json") else (None if os.path.exists(path) else f"missing {path}")
                if p:
                    problems.append(f"{oid}: as_built {p}")
            elif parts[0] in ("binding", "native", "upstream-test"):
                problems.append(f"{oid}: as_built entry needs '<kind> <verdict> <path>': {ent!r}")
    for r in orows:
        for ref in re.findall(r"[A-Za-z0-9_.\-]+#o\d{2,}", r["parent_entailment"]):
            if ref not in oids:
                problems.append(f"{r['id']}: parent entailment names unknown obligation {ref}")
    ecount = {}
    eids = set()
    for r in erows:
        if r["id"] in eids:
            problems.append(f"duplicate exclusion id {r['id']}")
        eids.add(r["id"])
        if not re.fullmatch(re.escape(r["block"]) + r"#x\d{2,}", r["id"]):
            problems.append(f"{r['id']}: id does not have the form <block>#xNN")
        if r["block"] not in by_block:
            problems.append(f"exclusion {r['id']}: unknown block {r['block']}")
            continue
        if by_block[r["block"]]["status"] == "not-started":
            problems.append(f"exclusion {r['id']}: block {r['block']} is not-started")
        if r["kind"] not in EXC_KINDS:
            problems.append(f"exclusion {r['id']}: kind {r['kind']!r}")
        if r["kind"] == "restatement":
            own = r["owner"].strip()
            if not (own in oids or own in blocks):
                problems.append(f"exclusion {r['id']}: restatement owner {own!r} does not resolve")
        ecount[r["block"]] = ecount.get(r["block"], 0) + 1
    for bid, r in by_block.items():
        if bid not in blocks:
            continue
        n = count.get(bid, 0)
        if str(n) != r["obligations"]:
            problems.append(f"{bid}: blocks.tsv obligations {r['obligations']} != {n} rows in obligations.tsv")
        if str(ecount.get(bid, 0)) != r["excluded"]:
            problems.append(f"{bid}: blocks.tsv excluded {r['excluded']} != {ecount.get(bid, 0)} rows in excluded.tsv")
        if r["status"] == "complete" and n == 0 and not r["structural_zero"].strip():
            problems.append(f"{bid}: complete with zero obligations needs a structural-zero reason")
        if r["status"] in ("complete", "partial") and not r["owners_checked"].strip():
            problems.append(f"{bid}: graded block without owners_checked")

    # ---- report ----
    out = []
    P = out.append
    order = sorted(blocks, key=lambda x: (blocks[x]["page"], blocks[x]["order"]))
    st = {s: [b for b in order if by_block.get(b, {}).get("status") == s] for s in STATUS}
    enumerated = [b for b in order if by_block.get(b, {}).get("status") in ("complete", "partial")]
    P("# Obligation census — summary")
    P("")
    P("Generated by `python3 .g5/Verus_verification/tools/census.py` from blocks.tsv, obligations.tsv and excluded.tsv; "
      "regenerating gives identical bytes. Counting rules: [README](README.md).")
    P("")
    P(f"Blocks in the ontology: {len(blocks)}. Complete: {len(st['complete'])}. Partial: {len(st['partial'])}. "
      f"Not started: {len(st['not-started'])}.")
    P("")
    if st["partial"] or st["not-started"]:
        P(f"**enumeration incomplete: whole-foundation percentage unmeasured** "
          f"(enumerated {len(st['complete'])} complete + {len(st['partial'])} partial of {len(blocks)} blocks; "
          f"not-started blocks count zero obligations, not N/A)")
    else:
        P("enumeration complete")
    P("")

    def tally(bids):
        t = {g: 0 for g in GRADES}
        c = {k: 0 for k in CHECKS}
        full_scope = 0
        for r in orows:
            if r["block"] in bids:
                t[r["grade"]] = t.get(r["grade"], 0) + 1
                c[r["design_check"]] = c.get(r["design_check"], 0) + 1
                if r["design_check"] == "proved" and r["check_scope"] == "full":
                    full_scope += 1
        return t, c, full_scope

    def line(name, bids, nb):
        t, c, fs = tally(set(bids))
        tot = sum(t.values())
        lo = pct(t["full"], tot)
        hi = pct(t["full"] + t["unassessed"], tot) if t["unassessed"] else lo
        return (f"| {name} | {nb} | {t['full']} | {t['partial']} | {t['absent']} | {t['unassessed']} | {tot} | {lo} | "
                f"{hi} | {fs} | {c['proved']} | {c['bounded']} | {c['refuted']} | {c['unchecked']} |")

    hdr = ("| {} | blocks | full | partial | absent | unassessed | total | full/total (lower) | (full+unassessed)/total "
           "(upper) | proved, full scope | proved | bounded | refuted | unchecked |")
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    P("## Pooled over the enumerated scope")
    P("")
    P(hdr.format("scope"))
    P(sep)
    P(line("enumerated (complete + partial)", enumerated, len(enumerated)))
    P(line("complete blocks only", st["complete"], len(st["complete"])))
    P("")
    P("`proved, full scope`: obligations whose design check is a proof over their full stated scope. `bounded` "
      "(finite domain), `refuted` (a modeled counterexample of the as-built design) and `unchecked` are counted "
      "separately; `proved` includes proofs over a narrowed scope.")
    P("")
    P("## Per page")
    P("")
    P(hdr.format("page"))
    P(sep)
    pages = sorted({blocks[b]["page"] for b in blocks})
    for pg in pages:
        bids = [b for b in enumerated if blocks[b]["page"] == pg]
        allb = [b for b in order if blocks[b]["page"] == pg]
        done = sum(1 for b in allb if by_block.get(b, {}).get("status") == "complete")
        part = sum(1 for b in allb if by_block.get(b, {}).get("status") == "partial")
        name = f"{pg[len(ONT) + 1:]} ({done} complete, {part} partial of {len(allb)})"
        P(line(name, bids, len(bids)))
    for pg in sorted(set(glob.glob(f"{ONT}/**/*.g5.md", recursive=True)) - set(pages)):
        P(f"| {pg[len(ONT) + 1:]} (no canonical blocks) | 0 | | | | | | N/A | | | | | | |")
    P("")
    P("## Per block (enumerated)")
    P("")
    P("| block | status | full | partial | absent | unassessed | total | full/total | upper | excluded | structural zero |")
    P("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for b in enumerated:
        t, _, _ = tally({b})
        tot = sum(t.values())
        r = by_block[b]
        P(f"| {b} | {r['status']} | {t['full']} | {t['partial']} | {t['absent']} | {t['unassessed']} | {tot} | "
          f"{pct(t['full'], tot)} | {pct(t['full'] + t['unassessed'], tot)} | {r['excluded']} | "
          f"{r['structural_zero'] or ''} |")
    P("")
    P("## Exclusions by kind (enumerated scope)")
    P("")
    kinds = {}
    for r in erows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    for k in sorted(kinds):
        P(f"- {k}: {kinds[k]}")
    P("")
    P("## Checks")
    P("")
    if problems:
        P(f"{len(problems)} problem(s):")
        P("")
        for p in sorted(problems):
            P(f"- FAIL: {p}")
    else:
        P("PASS: every block is in blocks.tsv; no graded block is STALE; every model locator and cited receipt "
          "resolves and is the latest fresh receipt of its kind; counts agree.")
    if notes:
        P("")
        for n in sorted(notes):
            P(f"- note: {n}")
    text = "\n".join(out) + "\n"
    with open(f"{CEN}/summary.md", "w", encoding="utf-8") as f:
        f.write(text)
    print(text, end="")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
