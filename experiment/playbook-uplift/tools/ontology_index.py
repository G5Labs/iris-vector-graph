#!/usr/bin/env python3
"""Build and check the uplift ontology index (playbook §3.1 gate).

    python experiment/playbook-uplift/tools/ontology_index.py            # check, write INDEX.md
    python experiment/playbook-uplift/tools/ontology_index.py --check    # check, fail if INDEX.md is stale
    python experiment/playbook-uplift/tools/ontology_index.py --self-test

The format is defined in experiment/playbook-uplift/ontology/README.md. The output is deterministic: no
timestamps, sorted keys, so a regenerated INDEX.md is byte-identical when nothing changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
UPLIFT = Path(__file__).resolve().parent.parent
REPO = UPLIFT.parent.parent
MAX_GRADE = 8.0
KINDS = {"R", "D", "B", "T", "I", "X", "P", "Q"}
OUTCOMES = {"ok", "no-op", "refused", "n/a", "open"}
EVIDENCE_KINDS = ("proved", "mc", "live", "run", "ran", "tested", "inspected", "assumed", "open", "finding",
                  "not-implemented")
# "ran" is derived, never written: a `tested:` citation whose test passed in one of this uplift's recorded runs
# (evidence/test-results.json, built by tools/test_results.py).
TEST_RESULTS: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
TRIAGE: Dict[str, str] = {}


def load_test_results(root: Path) -> None:
    TEST_RESULTS.clear()
    TRIAGE.clear()
    p = root / "evidence" / "test-results.json"
    if not p.exists():
        return
    for rid, run in json.loads(p.read_text(encoding="utf-8")).items():
        TRIAGE.update(run.get("triage", {}))
        for path, names in run.get("files", {}).items():
            for name, status in names.items():
                TEST_RESULTS.setdefault((path, name), []).append((rid, status))


def tested_refs(s: "Statement") -> List[Tuple[str, str]]:
    out = []
    for kind, ref in evidence_items(s.evidence):
        if kind == "tested":
            path, _, name = ref.partition("::")
            out.append((path, name.split("::")[-1].split("[")[0]))
    return out
ID_RE = re.compile(r"^[A-Z]{2,4}-[A-Za-z0-9.]+$")


# --------------------------------------------------------------------------- readability

def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1 if re.search(r"\d", word) else 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|[^laeiouy]ed|[^laeiouy]e)$", lambda m: m.group(0)[0], w)
    w = re.sub(r"^y", "", w)
    n = len(re.findall(r"[aeiouy]+", w))
    return max(1, n)


def words_of(text: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", text)]


def sentences_of(text: str) -> int:
    parts = [p for p in re.split(r"[.!?;:]+(?:\s|$)", text.strip()) if words_of(p)]
    return max(1, len(parts))


def fk_grade(text: str) -> float:
    ws = words_of(text)
    if not ws:
        return 0.0
    syl = sum(syllables(w) for w in ws)
    return 0.39 * (len(ws) / sentences_of(text)) + 11.8 * (syl / len(ws)) - 15.59


# --------------------------------------------------------------------------- parsing

@dataclass
class Statement:
    id: str
    parent: str
    kind: str
    text: str
    evidence: str
    source: str
    notes: str
    module: str
    file: str
    order: int


@dataclass
class Cell:
    entity: str
    state: str
    command: str
    outcome: str
    statements: List[str]
    decision: str
    file: str


@dataclass
class Module:
    code: str
    root: str
    title: str
    file: str
    scope: str
    glossary: List[Tuple[str, str]] = field(default_factory=list)
    statements: List[Statement] = field(default_factory=list)
    entities: Dict[str, Tuple[List[str], List[str]]] = field(default_factory=dict)
    cells: List[Cell] = field(default_factory=list)


def split_row(line: str) -> List[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells, cur, i = [], [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def table_after(lines: List[str], heading: str) -> Tuple[List[str], List[List[str]], int]:
    """The first table after a '## heading' line: header cells, rows, line index after it."""
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == f"## {heading}")
    except StopIteration:
        return [], [], -1
    i = start + 1
    while i < len(lines) and not lines[i].lstrip().startswith("|"):
        if lines[i].startswith("## "):
            return [], [], i
        i += 1
    if i >= len(lines):
        return [], [], i
    header = split_row(lines[i])
    i += 2  # skip the separator row
    rows = []
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        rows.append(split_row(lines[i]))
        i += 1
    return header, rows, i


def parse_module(path: Path, errors: List[str], order_base: int) -> Optional[Module]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    rel = path.name
    title = lines[0][2:].strip() if lines and lines[0].startswith("# ") else ""
    fields = {}
    for l in lines[:40]:
        m = re.match(r"^(Module|Root|Scope):\s*(.*)$", l)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    if "Module" not in fields or "Root" not in fields:
        errors.append(f"{rel}: missing 'Module:' or 'Root:' header")
        return None
    mod = Module(fields["Module"], fields["Root"], title, rel, fields.get("Scope", ""))

    header, rows, _ = table_after(lines, "Glossary")
    if header and header[:2] != ["Term", "Defined by"]:
        errors.append(f"{rel}: Glossary columns must be 'Term | Defined by', got {header}")
    for r in rows:
        if len(r) >= 2 and r[0]:
            mod.glossary.append((r[0].strip().lower(), r[1].strip()))

    want = ["Id", "Parent", "Kind", "Statement", "Evidence", "Source", "Notes"]
    header, rows, _ = table_after(lines, "Statements")
    if header != want:
        errors.append(f"{rel}: Statements columns must be {' | '.join(want)}, got {header}")
        return mod
    for k, r in enumerate(rows):
        if len(r) != len(want):
            errors.append(f"{rel}: statement row {k + 1} has {len(r)} cells, want {len(want)}: {r[:1]}")
            continue
        mod.statements.append(Statement(r[0], r[1], r[2], r[3], r[4], r[5], r[6], mod.code, rel, order_base + k))

    for l in lines:
        m = re.match(r"^Entity\s+(.+?):\s*states\s+(.+?);\s*commands\s+(.+)$", l.strip())
        if m:
            states = [s.strip() for s in m.group(2).split(",") if s.strip()]
            cmds = [c.strip() for c in m.group(3).split(",") if c.strip()]
            mod.entities[m.group(1).strip()] = (states, cmds)
    cwant = ["Entity", "State", "Command", "Outcome", "Statements", "Decision"]
    header, rows, _ = table_after(lines, "Cells")
    if header and header != cwant:
        errors.append(f"{rel}: Cells columns must be {' | '.join(cwant)}, got {header}")
    elif header:
        for r in rows:
            if len(r) != len(cwant):
                errors.append(f"{rel}: cell row has {len(r)} cells: {r}")
                continue
            ids = [x.strip() for x in re.split(r"[,; ]+", r[4]) if x.strip()]
            mod.cells.append(Cell(r[0], r[1], r[2], r[3], ids, r[5].strip(), rel))
    return mod


# --------------------------------------------------------------------------- the pinned tree

class Tree:
    def __init__(self, repo: Path, pin: str):
        self.repo, self.pin = repo, pin
        out = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", pin],
                             capture_output=True, text=True, check=True).stdout
        self.paths = set(out.splitlines())
        self.dirs = {str(Path(p).parent) for p in self.paths}
        for p in list(self.dirs):
            while p not in ("", "."):
                p = str(Path(p).parent)
                self.dirs.add(p)
        self._text: Dict[str, Optional[str]] = {}

    def exists(self, path: str) -> bool:
        p = path.rstrip("/")
        return p in self.paths or p in self.dirs

    def text(self, path: str) -> Optional[str]:
        if path not in self._text:
            if path not in self.paths:
                self._text[path] = None
            else:
                r = subprocess.run(["git", "-C", str(self.repo), "show", f"{self.pin}:{path}"],
                                   capture_output=True)
                self._text[path] = r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None
        return self._text[path]


def uplift_hash(paths: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(REPO)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def proof_sources(root: Path) -> List[Path]:
    return sorted(p for p in (root / "proofs").rglob("*") if p.is_file() and p.suffix in (".rs", ".toml")
                  and "target" not in p.parts)


def with_parts(path: Path) -> List[Path]:
    """TRUST.md and trust/*.md (likewise DECISIONS.md, FINDINGS.md): one shared file plus one per module."""
    parts = sorted((path.parent / path.stem.lower()).glob("*.md"))
    return ([path] if path.exists() else []) + parts


def ids_in(path: Path, prefix: str) -> Set[str]:
    out: Set[str] = set()
    for p in with_parts(path):
        out |= set(re.findall(rf"^#{{2,4}}\s+({prefix}-\d+[a-z]?)\b", p.read_text(encoding="utf-8"), re.MULTILINE))
    return out


def human_decisions(path: Path) -> Dict[str, str]:
    """HD ids and their owner, from '### HD-NN ...' blocks with an 'Owner:' line."""
    out: Dict[str, str] = {}
    cur = None
    lines = [l for p in with_parts(path) for l in p.read_text(encoding="utf-8").splitlines()]
    for line in lines:
        m = re.match(r"^#{2,4}\s+(HD-\d+)\b", line)
        if m:
            cur = m.group(1)
            out[cur] = ""
            continue
        m = re.match(r"^\s*[-*]?\s*\**Owner\**:\s*(\w+)", line)
        if m and cur:
            out[cur] = m.group(1).lower()
    return out


# --------------------------------------------------------------------------- checks

SOURCE_PATH_RE = re.compile(
    r"(?<![\w/.-])((?:docs|specs|iris_src|iris_vector_graph|api|sql|src|tests|scripts|config|deploy|docker|"
    r"benchmarks|examples|vendor|skills)/[A-Za-z0-9_./\-]+|[A-Z][A-Z_]+\.md|pyproject\.toml|docker-compose\.yml)"
)


def evidence_items(ev: str) -> List[Tuple[str, str]]:
    out = []
    for raw in [x.strip() for x in ev.split(";") if x.strip()]:
        if raw == "not-implemented":
            out.append(("not-implemented", ""))
            continue
        kind, _, ref = raw.partition(":")
        out.append((kind.strip(), ref.strip()))
    return out


def check(root: Path, tree: Tree, registry: dict) -> Tuple[List[Module], List[str], Dict[str, Statement]]:
    errors: List[str] = []
    files = sorted(p for p in (root / "ontology").glob("[0-9][0-9]-*.md"))
    modules: List[Module] = []
    base = 0
    for f in files:
        m = parse_module(f, errors, base)
        if m:
            modules.append(m)
            base += len(m.statements) + 1
    by_id: Dict[str, Statement] = {}
    for m in modules:
        for s in m.statements:
            if s.id in by_id:
                errors.append(f"{s.file}: duplicate id {s.id} (first in {by_id[s.id].file})")
                continue
            by_id[s.id] = s
    children: Dict[str, List[Statement]] = defaultdict(list)
    roots = 0
    for m in modules:
        if not any(s.id == m.root and s.kind == "R" for s in m.statements):
            errors.append(f"{m.file}: root {m.root} is not a statement of kind R")
        for s in m.statements:
            if by_id.get(s.id) is not s:
                continue
            where = f"{s.file} {s.id}"
            if not ID_RE.match(s.id) or not s.id.startswith(m.code + "-"):
                errors.append(f"{where}: id must be '{m.code}-<suffix>'")
            if s.kind not in KINDS:
                errors.append(f"{where}: kind '{s.kind}' not in {sorted(KINDS)}")
            if s.kind == "R":
                roots += 1
                expect = "-" if s.id == "SYS-0" else "SYS-0"
                if s.parent != expect or s.id != m.root:
                    errors.append(f"{where}: a root's parent is {expect} and its id is the module's Root")
            else:
                p = by_id.get(s.parent)
                if p is None:
                    errors.append(f"{where}: parent does not resolve: '{s.parent}'")
                elif p.order >= s.order:
                    errors.append(f"{where}: parent {s.parent} must come earlier")
                else:
                    children[s.parent].append(s)
            if s.kind == "R":
                children[s.parent].append(s)
            if not s.text:
                errors.append(f"{where}: empty statement")
            if "`" in s.text:
                errors.append(f"{where}: code in the statement text; move it to Source or Notes")
            g = fk_grade(s.text)
            if g > MAX_GRADE:
                errors.append(f"{where}: reading grade {g:.1f} > {MAX_GRADE:.0f}: {s.text}")
            for path in SOURCE_PATH_RE.findall(s.source):
                p = path.rstrip(".,)")
                if not tree.exists(p) and not (root / p).exists() and not (REPO / p).exists():
                    errors.append(f"{where}: Source path '{p}' does not exist at the pin")
            if not s.source.strip():
                errors.append(f"{where}: Source is empty")
            check_evidence(s, tree, registry, root, errors)
    # glossary: definitions and scope
    definers: Dict[str, Set[str]] = defaultdict(set)
    for m in modules:
        for term, sid in m.glossary:
            s = by_id.get(sid)
            if s is None or s.kind != "D":
                errors.append(f"{m.file}: glossary term '{term}' points at '{sid}', which is not a D statement")
                continue
            definers[term].add(sid)
    patterns = {t: re.compile(r"(?<![A-Za-z0-9-])" + re.escape(t).replace(r"\ ", r"[\s-]+") + r"(?:s|es)?(?![A-Za-z0-9-])",
                              re.IGNORECASE) for t in definers}
    for s in sorted(by_id.values(), key=lambda x: x.order):
        scope = in_scope(s, by_id, children)
        for term, pat in patterns.items():
            if not pat.search(s.text):
                continue
            if s.id in definers[term]:
                continue
            if not (definers[term] & scope):
                errors.append(f"{s.file} {s.id}: uses '{term}' before a definition in scope "
                              f"(defined by {', '.join(sorted(definers[term]))})")
    # cells
    decisions = human_decisions(root / "DECISIONS.md")
    for m in modules:
        seen = set()
        for c in m.cells:
            key = (c.entity, c.state, c.command)
            where = f"{m.file} cell {key}"
            if key in seen:
                errors.append(f"{where}: duplicate")
            seen.add(key)
            if c.entity not in m.entities:
                errors.append(f"{where}: entity not declared on an 'Entity' line")
            else:
                st, cmd = m.entities[c.entity]
                if c.state not in st or c.command not in cmd:
                    errors.append(f"{where}: state or command not declared for the entity")
            if c.outcome not in OUTCOMES:
                errors.append(f"{where}: outcome '{c.outcome}' not in {sorted(OUTCOMES)}")
            if c.outcome == "open":
                if decisions.get(c.decision) != "human":
                    errors.append(f"{where}: open cell needs a decision HD-NN owned by the human")
            else:
                if not c.statements:
                    errors.append(f"{where}: cites no statement")
                for sid in c.statements:
                    if sid not in by_id:
                        errors.append(f"{where}: statement '{sid}' does not resolve")
        for ent, (states, cmds) in m.entities.items():
            for st in states:
                for cmd in cmds:
                    if (ent, st, cmd) not in seen:
                        errors.append(f"{m.file}: cell ({ent}, {st}, {cmd}) is not defined")
    return modules, errors, by_id


def in_scope(s: Statement, by_id: Dict[str, Statement], children: Dict[str, List[Statement]]) -> Set[str]:
    out: Set[str] = set()
    node: Optional[Statement] = s
    seen: Set[str] = set()
    while node is not None and node.id not in seen:
        seen.add(node.id)
        if node.kind == "D":
            out.add(node.id)
        for sib in children.get(node.parent, []):
            if sib.order < node.order and sib.kind == "D":
                out.add(sib.id)
        node = by_id.get(node.parent)
    return out


def check_evidence(s: Statement, tree: Tree, registry: dict, root: Path, errors: List[str]) -> None:
    where = f"{s.file} {s.id}"
    items = evidence_items(s.evidence)
    if not items:
        errors.append(f"{where}: no evidence (use inspected/tested/... or open:/not-implemented)")
    trust = ids_in(root / "TRUST.md", "P")
    decisions = human_decisions(root / "DECISIONS.md")
    findings = ids_in(root / "FINDINGS.md", "F")
    kinds = {k for k, _ in items}
    if s.kind == "Q" and "open" not in kinds:
        errors.append(f"{where}: an open question needs open:HD-NN")
    for kind, ref in items:
        if kind not in EVIDENCE_KINDS:
            errors.append(f"{where}: evidence kind '{kind}' unknown")
            continue
        if kind == "inspected":
            m = re.match(r"^(.+?):(\d+)(?:-(\d+))?$", ref)
            if not m:
                errors.append(f"{where}: inspected needs <path>:<line>[-<line>], got '{ref}'")
                continue
            text = tree.text(m.group(1))
            if text is None:
                errors.append(f"{where}: inspected path '{m.group(1)}' not in the pin")
                continue
            n = text.count("\n") + (0 if text.endswith("\n") else 1)
            a, b = int(m.group(2)), int(m.group(3) or m.group(2))
            if not (1 <= a <= b <= n):
                errors.append(f"{where}: inspected lines {a}-{b} outside {m.group(1)} (1-{n})")
        elif kind == "tested":
            path, _, name = ref.partition("::")
            text = tree.text(path)
            if text is None:
                errors.append(f"{where}: tested path '{path}' not in the pin")
                continue
            leaf = name.split("::")[-1].split("[")[0] if name else ""
            if leaf and not re.search(rf"\b(?:def|class)\s+{re.escape(leaf)}\b", text):
                errors.append(f"{where}: tested name '{leaf}' not defined in {path}")
        elif kind in ("run", "live", "mc"):
            entry = registry.get("runs", {}).get(ref)
            if entry is None:
                errors.append(f"{where}: {kind}:{ref} not in evidence/runs.json")
            elif entry.get("kind") != kind or entry.get("result") != "pass":
                errors.append(f"{where}: {kind}:{ref} registry entry is kind={entry.get('kind')} "
                              f"result={entry.get('result')}")
        elif kind == "proved":
            srcs = proof_sources(root)
            body = "\n".join(p.read_text(encoding="utf-8") for p in srcs if p.suffix == ".rs")
            if not re.search(rf"\bproof\s+fn\s+{re.escape(ref)}\b", body):
                errors.append(f"{where}: proved:{ref} is not a proof fn in proofs/")
                continue
            verus = registry.get("verus", {})
            if verus.get("errors") != 0 or verus.get("sources_sha256") != uplift_hash(srcs):
                errors.append(f"{where}: proved:{ref} has no decisive Verus run over the current proof sources")
            elif ref not in set(verus.get("proof_fns", [])):
                errors.append(f"{where}: proved:{ref} is not in the Verus run's verified function list")
        elif kind == "assumed" and ref not in trust:
            errors.append(f"{where}: premise {ref} not in TRUST.md")
        elif kind == "open" and decisions.get(ref) != "human":
            errors.append(f"{where}: decision {ref} not in DECISIONS.md with Owner: human")
        elif kind == "finding" and ref not in findings:
            errors.append(f"{where}: finding {ref} not in FINDINGS.md")
        elif kind == "not-implemented" and not s.source.strip():
            errors.append(f"{where}: not-implemented needs the intent in Source")


# --------------------------------------------------------------------------- index

def classify(s: Statement) -> Set[str]:
    kinds = {k for k, _ in evidence_items(s.evidence)}
    if any(any(st == "pass" for _, st in TEST_RESULTS.get(ref, [])) for ref in tested_refs(s)):
        kinds.add("ran")
    return kinds


def render(modules: List[Module], errors: List[str], by_id: Dict[str, Statement]) -> str:
    out = ["# Ontology index", "",
           "Generated by `experiment/playbook-uplift/tools/ontology_index.py` from the module files in this",
           f"directory. Do not edit. Product pin `{PIN[:8]}`.", ""]
    out += ["## How to read the evidence", "",
            "- **proved**: a Verus proof over the L1/L2 models in `proofs/` (decisive run recorded in `evidence/runs.json`). "
            "Proofs are about models; where the code at the pin differs from the proved design, the statement also cites a finding.",
            "- **mc**: an explicit-state model check in `model/`, exhaustive only within the bounds the machine declares "
            "(see `MODELS.md`). A model is an executable twin, not the code.",
            "- **live**: observed on IRIS Community 2026.1 in the dedicated container by this uplift (logs under `$RUN_DIR`).",
            "- **run**: an upstream test set executed here. **ran**: a cited upstream test (`tested:`) that passed in one of "
            "those runs. **tested**: an upstream test that asserts the statement; not necessarily run here.",
            "- **inspected**: read in production code at the pin. **assumed**: a named premise in `TRUST.md` or `trust/`. "
            "**open**: a decision for the human. **finding**: the code disagrees.", ""]
    out += ["## Gate", ""]
    if errors:
        out += [f"**FAIL**: {len(errors)} violation(s).", ""] + [f"- {e}" for e in errors] + [""]
    else:
        n_cells = sum(len(m.cells) for m in modules)
        out += [f"**PASS**: {len(by_id)} statements in {len(modules)} modules, {n_cells} cells. Every parent "
                "resolves, every statement reads at grade 8 or below, every glossary term is defined in scope, "
                "every evidence reference resolves, and every cell is defined or assigned to the human.", ""]
    out += ["## Modules", "",
            "| Module | File | Statements | R | D | B | T | I | X | P | Q | Cells | Open cells | Max grade |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    tot = Counter()
    for m in modules:
        k = Counter(s.kind for s in m.statements)
        oc = sum(1 for c in m.cells if c.outcome == "open")
        mg = max((fk_grade(s.text) for s in m.statements), default=0.0)
        out.append(f"| {m.code} | {m.file} | {len(m.statements)} | " + " | ".join(str(k[x]) for x in "RDBTIXPQ")
                   + f" | {len(m.cells)} | {oc} | {mg:.1f} |")
        tot.update(k)
        tot["n"] += len(m.statements)
        tot["cells"] += len(m.cells)
        tot["open"] += oc
    out.append(f"| **all** | | {tot['n']} | " + " | ".join(str(tot[x]) for x in "RDBTIXPQ")
               + f" | {tot['cells']} | {tot['open']} | |")
    out += ["", "## Evidence by module", "",
            "Count of statements carrying each evidence kind (a statement may carry several).", "",
            "| Module | " + " | ".join(EVIDENCE_KINDS) + " |", "|---|" + "---:|" * len(EVIDENCE_KINDS)]
    allc = Counter()
    for m in modules:
        c = Counter()
        for s in m.statements:
            c.update(classify(s))
        allc.update(c)
        out.append(f"| {m.code} | " + " | ".join(str(c[k]) for k in EVIDENCE_KINDS) + " |")
    out.append("| **all** | " + " | ".join(str(allc[k]) for k in EVIDENCE_KINDS) + " |")
    out += ["", "## Evidence combinations", "", "| Combination | Statements |", "|---|---:|"]
    combos = Counter("+".join(k for k in EVIDENCE_KINDS if k in classify(s)) or "(none)" for s in by_id.values())
    for combo, n in sorted(combos.items(), key=lambda x: (-x[1], x[0])):
        out.append(f"| {combo} | {n} |")

    def listing(title: str, note: str, pred) -> None:
        rows = [s for s in sorted(by_id.values(), key=lambda x: x.order) if pred(s)]
        out.extend(["", f"## {title} ({len(rows)})", "", note, ""])
        if not rows:
            out.append("None.")
            return
        out.extend(["| Id | Statement | Evidence |", "|---|---|---|"])
        for s in rows:
            out.append(f"| {s.id} | {s.text.replace('|', '/')} | {s.evidence.replace('|', '/')} |")

    test_kinds = {"tested", "run", "live"}
    listing("Proof-only", "Proved, with no test or live observation behind it.",
            lambda s: "proved" in classify(s) and not (classify(s) & test_kinds))
    listing("Proved and observed live", "Proved and also observed on live IRIS in this uplift.",
            lambda s: {"proved", "live"} <= classify(s))
    listing("Not implemented", "The intent states it; no code does it.",
            lambda s: "not-implemented" in classify(s))
    listing("Findings", "The code disagrees with the statement (see FINDINGS.md).",
            lambda s: "finding" in classify(s))
    listing("Open decisions", "Statements waiting on a human decision (see DECISIONS.md).",
            lambda s: "open" in classify(s))
    listing("Premises", "Statements that rest on a named premise (see TRUST.md).",
            lambda s: "assumed" in classify(s))
    listing("Inspection only", "Supported only by reading production code at the pin.",
            lambda s: classify(s) == {"inspected"})
    bad_tests = []
    for st in sorted(by_id.values(), key=lambda x: x.order):
        for ref in tested_refs(st):
            for rid, status in TEST_RESULTS.get(ref, []):
                if status not in ("pass",):
                    why = TRIAGE.get(f"{ref[0]}::{ref[1]}") or TRIAGE.get(ref[0]) or ""
                    bad_tests.append((st.id, f"{ref[0]}::{ref[1]}", rid, status, why))
    out += ["", f"## Cited tests that did not pass in this uplift's runs ({len(bad_tests)})", ""]
    if bad_tests:
        out += ["| Statement | Test | Run | Status | Triage |", "|---|---|---|---|---|"]
        out += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in bad_tests]
    else:
        out.append("None.")
    opens = [(m.code, c) for m in modules for c in m.cells if c.outcome == "open"]
    out += ["", f"## Open cells ({len(opens)})", ""]
    if opens:
        out += ["| Module | Entity | State | Command | Decision |", "|---|---|---|---|---|"]
        out += [f"| {mc} | {c.entity} | {c.state} | {c.command} | {c.decision} |" for mc, c in opens]
    else:
        out.append("None.")
    out += ["", "## Cell outcomes", "", "| Module | ok | no-op | refused | n/a | open |", "|---|---:|---:|---:|---:|---:|"]
    for m in modules:
        c = Counter(x.outcome for x in m.cells)
        out.append(f"| {m.code} | " + " | ".join(str(c[o]) for o in ("ok", "no-op", "refused", "n/a", "open")) + " |")
    return "\n".join(out) + "\n"


def load_registry(root: Path) -> dict:
    p = root / "evidence" / "runs.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def run(root: Path, check_only: bool, only: Optional[List[str]] = None) -> int:
    tree = Tree(REPO, PIN)
    load_test_results(root)
    modules, errors, by_id = check(root, tree, load_registry(root))
    if only:
        mine = [e for e in errors if any(e.startswith(f"{n}-") or f"/{n}-" in e for n in only)]
        for e in mine:
            print("GATE:", e)
        print(f"{len(mine)} violation(s) in files {', '.join(only)} (of {len(errors)} overall); INDEX.md not written")
        return 1 if mine else 0
    text = render(modules, errors, by_id)
    idx = root / "ontology" / "INDEX.md"
    if check_only:
        stale = not idx.exists() or idx.read_text(encoding="utf-8") != text
        for e in errors:
            print("GATE:", e)
        if stale:
            print("GATE: INDEX.md is stale; regenerate it")
        print(f"{len(by_id)} statements, {len(errors)} violation(s), index {'stale' if stale else 'current'}")
        return 1 if errors or stale else 0
    idx.write_text(text, encoding="utf-8")
    for e in errors:
        print("GATE:", e)
    print(f"{len(by_id)} statements, {len(errors)} violation(s); wrote {idx.relative_to(REPO)}")
    return 1 if errors else 0


# --------------------------------------------------------------------------- self-test

GOOD = """# 00 System

Module: SYS
Root: SYS-0

## Glossary

| Term | Defined by |
|---|---|
| graph | SYS-D1 |

## Statements

| Id | Parent | Kind | Statement | Evidence | Source | Notes |
|---|---|---|---|---|---|---|
| SYS-0 | - | R | The product keeps data in IRIS. | inspected:CONTEXT.md:1 | CONTEXT.md | |
| SYS-D1 | SYS-0 | D | A graph is a named part of the data. | inspected:CONTEXT.md:1 | CONTEXT.md | |
"""

MOD = """# 01 Mod

Module: MOD
Root: MOD-0

## Glossary

| Term | Defined by |
|---|---|
| tomb | MOD-D1 |

## Statements

| Id | Parent | Kind | Statement | Evidence | Source | Notes |
|---|---|---|---|---|---|---|
| MOD-0 | SYS-0 | R | Each graph keeps its own data. | inspected:CONTEXT.md:2 | CONTEXT.md | |
| MOD-D1 | MOD-0 | D | A tomb is a mark left where data was. | inspected:CONTEXT.md:2 | CONTEXT.md | |
| MOD-B1 | MOD-0 | B | A tomb keeps its place. | inspected:CONTEXT.md:3 | CONTEXT.md | |
| MOD-B1.1 | MOD-B1 | B | A tomb holds no data. | inspected:CONTEXT.md:3 | CONTEXT.md | |

## Cells

Entity thing: states a, b; commands go

| Entity | State | Command | Outcome | Statements | Decision |
|---|---|---|---|---|---|
| thing | a | go | ok | MOD-B1 | |
| thing | b | go | refused | MOD-B1.1 | |
"""

MUTANTS = [
    ("parent does not resolve", "| MOD-B1.1 | MOD-B1 |", "| MOD-B1.1 | MOD-B9 |"),
    ("reading grade", "A tomb holds no data.",
     "A tombstone representation incorporates cryptographic authentication characteristics."),
    ("before a definition in scope", "| MOD-D1 | MOD-0 | D | A tomb is a mark left where data was.",
     "| MOD-D1 | MOD-B1 | D | A tomb is a mark left where data was."),
    ("is not defined", "| thing | b | go | refused | MOD-B1.1 | |\n", ""),
    ("does not resolve", "| thing | a | go | ok | MOD-B1 |", "| thing | a | go | ok | MOD-B7 |"),
    ("outside", "inspected:CONTEXT.md:3 | CONTEXT.md | |\n| MOD-B1.1", "inspected:CONTEXT.md:99999 | CONTEXT.md | |\n| MOD-B1.1"),
    ("code in the statement", "A tomb keeps its place.", "A tomb keeps its `place`."),
    ("not in TRUST.md", "| MOD-B1 | MOD-0 | B | A tomb keeps its place. | inspected:CONTEXT.md:3",
     "| MOD-B1 | MOD-0 | B | A tomb keeps its place. | assumed:P-99"),
    ("open cell needs a decision", "| thing | b | go | refused | MOD-B1.1 | |", "| thing | b | go | open | | |"),
    ("not in evidence/runs.json", "| MOD-B1 | MOD-0 | B | A tomb keeps its place. | inspected:CONTEXT.md:3",
     "| MOD-B1 | MOD-0 | B | A tomb keeps its place. | live:nothing"),
    ("duplicate id", "| MOD-B1.1 | MOD-B1 |", "| MOD-B1 | MOD-B1 |"),
]


def self_test() -> int:
    tree = Tree(REPO, PIN)
    failures = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "ontology").mkdir()
        (root / "ontology" / "00-system.md").write_text(GOOD)
        (root / "ontology" / "01-mod.md").write_text(MOD)
        _, errs, _ = check(root, tree, {})
        if errs:
            print("self-test: the clean fixture fails:", errs)
            return 1
        print("self-test: clean fixture passes")
        for name, old, new in MUTANTS:
            assert old in MOD, name
            (root / "ontology" / "01-mod.md").write_text(MOD.replace(old, new, 1))
            _, errs, _ = check(root, tree, {})
            hit = any(name in e for e in errs)
            print(f"self-test: {'KILLED' if hit else 'SURVIVED'} {name}")
            failures += 0 if hit else 1
        (root / "ontology" / "01-mod.md").write_text(MOD)
    print(f"self-test: {len(MUTANTS) - failures}/{len(MUTANTS)} injected violations rejected")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--grade", help="print the reading grade of a sentence and exit")
    ap.add_argument("--only", nargs="+", metavar="NN", help="report violations in these module numbers only")
    a = ap.parse_args()
    if a.grade:
        print(f"{fk_grade(a.grade):.2f}")
        return 0
    if a.self_test:
        return self_test()
    return run(UPLIFT, a.check, a.only)


if __name__ == "__main__":
    sys.exit(main())
