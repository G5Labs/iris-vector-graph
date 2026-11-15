#!/usr/bin/env python3
"""The consolidated uplift's gate (reviewed plan section 4.4). Read-only; exit 0 only when every check passes.

    python3 .g5/Verus_verification/tools/check_consolidated.py [--skip-external]

Run from the repository root. Checks, in order:

1. Confinement: nothing outside .g5/, .agents/ and experiment/ differs from the product pin 3eaa79cf (HEAD and the
   working tree); .agents/ and experiment/g5-verus/ equal the guidance arm 24c6b0c0; the two imported playbook trees
   hash as imported from 2d59e578 and have no working-tree change; no untracked, non-ignored file outside .g5/.
2. The five inherited guidance-arm model roots, their model.json and the twin are byte-identical to 24c6b0c0
   (allow-list below, empty).
3. tools/check_evidence.py (freshness of every model's receipts, native observations and playbook crate reruns).
4. The G5 ontology checker over .g5/ontology, and 5. the G5 findings checker over the registers
   ($G5_GUIDE/scripts; skipped with --skip-external, which is then reported as a failure).
6. The ratchet: every entry anchor of the three registers at 24c6b0c0 is still an anchor in the same file.
7. Crosswalks: crosswalk/statements.tsv (blocks exist, playbook IDs exist, every Tier 1 row present);
   crosswalk/{findings,simplifications,questions}.tsv (every source ID exactly once, every canonical ID an anchor of
   the right register, every register anchor has a source row); crosswalk/decision-links.tsv (every symbol resolves
   to exactly one definition at the pin; every formal item to exactly one fn).

Standard library only.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
V = REPO / ".g5/Verus_verification"
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
G_TIP = "24c6b0c03e1c84cac6691de45c183fa1cf73940b"
P_TIP = "2d59e578362cab392b771051f79cd613aae7269c"
TREES = {"experiment/playbook-uplift": "becf53a4f5e975087caa9edfe3268d86bc89e61d",
         "experiment/playbook-completion": "a8fe71298163137a8c9d708c8d17685a8dd5d874"}
G_MODELS = {"ledger_redaction": ["redaction.rs", "model.json", "twin.rs"], "graph_structure": ["graph_structure.rs", "model.json"],
            "temporal": ["temporal.rs", "model.json"], "search": ["search.rs", "model.json"], "platform": ["platform.rs", "model.json"]}
ALLOW_CHANGED: dict[str, str] = {}  # path -> reason; empty: no inherited model was corrected
REGISTERS = ("bugs_issues.md", "design_simplification.md", "open_questions.md")
TIER1 = [("M03", "ledger.commit"), ("M07", "temporal.window.paging.release"), ("M08", "temporal.window.paging"),
         ("M09", "structure.rebuilt.stamp"), ("M11", "structure.multigraph.count"), ("M12", "algorithms.op.paths.weighted"),
         ("M14", "search.embedding.width"), ("M14", "search.routes.no_fallback"), ("M23", "install.bulk_load.loader"),
         ("J01", "install.snapshot.routes"), ("J02", "install.snapshot.temporal"), ("M16", "structure.adjacency.declare"),
         ("J07", "structure.adjacency.declare"), ("M17", "adapters.embedded.no_data"), ("M18", "query.values.relationship_text")]
CROSSWALK_REGISTER = {"findings.tsv": "bugs_issues.md", "simplifications.tsv": "design_simplification.md",
                      "questions.tsv": "open_questions.md"}

failures: list[str] = []


def git(*args: str, check: bool = True) -> str:
    p = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    if check and p.returncode not in (0, 1):
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def git_rc(*args: str) -> int:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True).returncode


def fail(msg: str) -> None:
    failures.append(msg)
    print("FAIL:", msg)


def ok(msg: str) -> None:
    print("ok:  ", msg)


def check_confinement() -> None:
    product = ["--", ".", ":(exclude).g5", ":(exclude).agents", ":(exclude)experiment"]
    for label, args in (("HEAD", [PIN, "HEAD"]), ("working tree", [PIN])):
        if git_rc("diff", "--quiet", *args, *product):
            fail(f"product paths differ from the pin ({label}): " + git("diff", "--stat", *args, *product).strip()[-300:])
        else:
            ok(f"product paths equal the pin 3eaa79cf ({label})")
    for label, args in (("HEAD", [G_TIP, "HEAD"]), ("working tree", [G_TIP])):
        if git_rc("diff", "--quiet", *args, "--", ".agents", "experiment/g5-verus"):
            fail(f".agents or experiment/g5-verus differ from 24c6b0c0 ({label})")
        else:
            ok(f".agents and experiment/g5-verus equal 24c6b0c0 ({label})")
    for path, tree in TREES.items():
        got = git("rev-parse", f"HEAD:{path}").strip()
        if got != tree:
            fail(f"{path} tree {got} != imported {tree}")
        elif git_rc("diff", "--quiet", "HEAD", "--", path) or git("ls-files", "--others", "--exclude-standard", "--", path).strip():
            fail(f"{path} has working-tree changes")
        else:
            ok(f"{path} tree {tree[:8]} as imported, unchanged in the working tree")
    top = sorted(l.split("\t")[1] for l in git("ls-tree", "HEAD", "experiment/").splitlines())
    if top != ["experiment/g5-verus", "experiment/playbook-completion", "experiment/playbook-uplift"]:
        fail(f"unexpected entries under experiment/: {top}")
    stray = [p for p in git("ls-files", "--others", "--exclude-standard").splitlines() if not p.startswith(".g5/")]
    if stray:
        fail(f"untracked files outside .g5/: {stray[:10]}")
    else:
        ok("no untracked, non-ignored file outside .g5/")


def check_inherited_models() -> None:
    bad = []
    for m, files in G_MODELS.items():
        for f in files:
            rel = f".g5/Verus_verification/models/{m}/{f}"
            want = git("rev-parse", f"{G_TIP}:{rel}").strip()
            have = subprocess.run(["git", "hash-object", str(REPO / rel)], capture_output=True, text=True).stdout.strip()
            if want != have and rel not in ALLOW_CHANGED:
                bad.append(rel)
    if bad:
        fail(f"inherited model inputs changed: {bad}")
    else:
        ok(f"the five inherited model roots, model.json files and twin.rs are byte-identical to 24c6b0c0")


def run_tool(label: str, cmd: list[str]) -> None:
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
    if p.returncode != 0:
        fail(f"{label} exited {p.returncode}: {' | '.join(tail)}")
    else:
        ok(f"{label}: {' | '.join(tail)[:220]}")


def anchors(text: str) -> set[str]:
    return set(re.findall(r'<a id="([^"]+)"></a>', text))


def check_ratchet() -> None:
    for name in REGISTERS:
        old = anchors(git("show", f"{G_TIP}:.g5/Verus_verification/{name}"))
        new = anchors((V / name).read_text())
        lost = sorted(old - new)
        if lost:
            fail(f"{name}: {len(lost)} entry IDs from 24c6b0c0 are gone: {lost[:10]}")
        else:
            ok(f"{name}: all {len(old)} entry IDs from 24c6b0c0 are still anchors ({len(new)} now)")


def ontology_ids() -> set[str]:
    ids = set()
    for f in (REPO / ".g5/ontology").rglob("*.g5.md"):
        ids |= set(re.findall(r'^\[[IDQ] · ([^\]]+)\]$', f.read_text(), re.M))
    return ids


def playbook_ids() -> set[str]:
    sys.path.insert(0, str(V / "tools"))
    import playbook_ontology  # noqa: E402
    return set(playbook_ontology.load())


def read_tsv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def check_statements() -> None:
    path = V / "crosswalk/statements.tsv"
    if not path.exists():
        fail("crosswalk/statements.tsv is missing")
        return
    rows = read_tsv(path)
    blocks, pids = ontology_ids(), playbook_ids()
    bad_b = sorted({r["g_block"] for r in rows if r["g_block"] not in blocks and r["relation"] != "p-only-linked"})
    bad_p = sorted({p for r in rows for p in re.split(r"[;, ]+", r["p_statement_ids"].strip()) if p and p not in pids})
    rels = {"same", "g-extended-from-p", "p-only-linked", "g-only", "contradiction"}
    bad_r = sorted({r["relation"] for r in rows if r["relation"] not in rels})
    have = {(c.strip(), r["g_block"]) for r in rows for c in re.split(r"[;, ]+", r.get("decision or case id", "")) if c.strip()}
    missing = [t for t in TIER1 if t not in have]
    for msg, items in (("unknown ontology blocks", bad_b), ("unknown playbook statement IDs", bad_p),
                       ("unknown relations", bad_r), ("Tier 1 rows missing (case, block)", missing)):
        if items:
            fail(f"statements.tsv: {msg}: {items[:12]}")
    if not (bad_b or bad_p or bad_r or missing):
        ok(f"statements.tsv: {len(rows)} rows; blocks and playbook IDs resolve; all {len(TIER1)} Tier 1 rows present")


def check_register_crosswalks() -> None:
    for tsv, reg in CROSSWALK_REGISTER.items():
        path = V / "crosswalk" / tsv
        if not path.exists():
            fail(f"crosswalk/{tsv} is missing")
            continue
        rows = read_tsv(path)
        reg_anchors = anchors((V / reg).read_text())
        seen: dict[tuple[str, str], int] = {}
        for r in rows:
            k = (r["source_arm"], r["source_id"])
            seen[k] = seen.get(k, 0) + 1
        dup = [k for k, n in seen.items() if n > 1]
        bad_c = sorted({r["canonical_id"] for r in rows if r["canonical_id"] not in reg_anchors})
        canon = {r["canonical_id"] for r in rows}
        orphan = sorted(reg_anchors - canon)
        for msg, items in (("source IDs listed more than once", dup), (f"canonical IDs that are not anchors of {reg}", bad_c),
                           (f"{reg} anchors with no source row", orphan)):
            if items:
                fail(f"{tsv}: {msg}: {items[:10]}")
        if not (dup or bad_c or orphan):
            arms = {}
            for r in rows:
                arms[r["source_arm"]] = arms.get(r["source_arm"], 0) + 1
            ok(f"{tsv}: {len(rows)} source rows {arms}; {len(canon)} canonical entries, all anchors of {reg}")
    # completeness against the sources (the counts the reviewed plan states)
    try:
        f_rows = read_tsv(V / "crosswalk/findings.tsv")
        p_f = {r["source_id"] for r in f_rows if r["source_arm"] == "P" and r["source_id"].startswith("F-")}
        g_old = {}
        for name in REGISTERS:
            g_old[name] = anchors(git("show", f"{G_TIP}:.g5/Verus_verification/{name}"))
        g_src = {}
        for tsv, reg in CROSSWALK_REGISTER.items():
            g_src[reg] = {r["source_id"] for r in read_tsv(V / "crosswalk" / tsv) if r["source_arm"] == "G"}
        for reg in REGISTERS:
            miss = sorted(g_old[reg] - g_src[reg])
            if miss:
                fail(f"{reg}: guidance-arm entries with no crosswalk row: {miss[:10]}")
        if len(p_f) < 313:
            fail(f"findings.tsv: {len(p_f)} distinct playbook F- IDs, expected 313")
        else:
            ok(f"findings.tsv: {len(p_f)} distinct playbook finding IDs (expected 313)")
    except FileNotFoundError:
        pass


def py_defs(source: str) -> dict[str, int]:
    out: dict[str, int] = {}

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = f"{prefix}{ch.name}"
                out[q] = out.get(q, 0) + 1
                walk(ch, q + ".")
            elif isinstance(ch, (ast.Assign, ast.AnnAssign)) and not prefix:
                targets = ch.targets if isinstance(ch, ast.Assign) else [ch.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        out[t.id] = out.get(t.id, 0) + 1
    walk(ast.parse(source), "")
    return out


def cls_members(source: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in re.finditer(r"^(?:ClassMethod|Method|Query|Trigger|Parameter|Property)\s+([A-Za-z%][A-Za-z0-9]*)", source, re.M):
        out[m.group(1)] = out.get(m.group(1), 0) + 1
    return out


def check_decision_links() -> None:
    path = V / "crosswalk/decision-links.tsv"
    if not path.exists():
        fail("crosswalk/decision-links.tsv is missing")
        return
    rows = read_tsv(path)
    cache: dict[str, dict[str, int]] = {}
    bad_sym, bad_fn = [], []
    for r in rows:
        p, sym = r["path"], r["symbol"]
        if p not in cache:
            try:
                src = git("show", f"{PIN}:{p}")
            except RuntimeError:
                src = ""
            cache[p] = py_defs(src) if p.endswith(".py") else cls_members(src) if p.endswith(".cls") else {}
        if cache[p].get(sym, 0) != 1:
            bad_sym.append(f"{p}::{sym}")
        item = r.get("formal item", "").strip()
        if item and item != "-":
            fpath, _, fn = item.partition("::")
            fp = REPO / fpath
            n = len(re.findall(rf"\bfn\s+{re.escape(fn)}\b", fp.read_text())) if fp.exists() else 0
            if n != 1:
                bad_fn.append(item)
    if bad_sym:
        fail(f"decision-links.tsv: {len(bad_sym)} symbols do not resolve to exactly one definition at the pin: {sorted(set(bad_sym))[:10]}")
    if bad_fn:
        fail(f"decision-links.tsv: {len(bad_fn)} formal items do not resolve to exactly one fn: {sorted(set(bad_fn))[:10]}")
    if not (bad_sym or bad_fn):
        ok(f"decision-links.tsv: {len(rows)} links; every symbol and formal item resolves uniquely")


def main(argv: list[str]) -> int:
    skip = "--skip-external" in argv
    guide = os.environ.get("G5_GUIDE", "/Users/ziniuw/Desktop/research/G5-Lean-V2/.agents/guidance")
    print("1. confinement"); check_confinement()
    print("2. inherited models"); check_inherited_models()
    print("3. evidence freshness"); run_tool("check_evidence.py", [sys.executable, str(V / "tools/check_evidence.py")])
    if skip:
        fail("G5 ontology and findings checkers skipped (--skip-external)")
    else:
        print("4. ontology"); run_tool("check_ontology.py", [sys.executable, f"{guide}/scripts/check_ontology.py", ".g5/ontology"])
        print("5. findings"); run_tool("check_findings.py", [sys.executable, f"{guide}/scripts/check_findings.py",
                                                             ".g5/Verus_verification", ".g5/ontology"])
    print("6. register ratchet"); check_ratchet()
    print("7. crosswalks"); check_statements(); check_register_crosswalks(); check_decision_links()
    print(f"\n{'PASS' if not failures else f'{len(failures)} FAILURE(S)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
