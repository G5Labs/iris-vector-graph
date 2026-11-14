#!/usr/bin/env python3
"""Check the completion ontology against playbook §3.1 and write INDEX.md.

    python3 experiment/playbook-completion/ontology/tools/ontology_check.py            # check, write INDEX.md
    python3 experiment/playbook-completion/ontology/tools/ontology_check.py --check    # check, fail if INDEX.md is stale
    python3 experiment/playbook-completion/ontology/tools/ontology_check.py --self-test
    python3 experiment/playbook-completion/ontology/tools/ontology_check.py --ontology DIR  # check DIR, write nothing
    python3 experiment/playbook-completion/ontology/tools/ontology_check.py --pairs DIR [--matcher literal|strong]

Derived from experiment/playbook-uplift/tools/ontology_index.py (submission 9c3719c1). Every check of that tool is
kept. Changes (see ../METHOD.md):

- Term scope is the playbook's literal rule (decision HD-0001): a statement may use a term of its module glossary
  only when the term is defined (kind D) by the statement itself, by an ancestor, or by an earlier statement with
  the same parent. The submitted tool's extension to earlier siblings of an ancestor is removed.
- Term matching is at least as strong as check-literal-scope.py: case-insensitive whole words, plural s/es, space
  and hyphen interchangeable (also inside hyphenated terms), and y/ies plurals.
- New rules: a term used before its definition in document order; a definer that is not kind D or whose text does
  not contain the term; a definer in another module; a duplicate glossary row; a term of another module's glossary
  used without a local definition; local restatements must be kind D, come after the primary definer, repeat its
  text and say "Same meaning as <primary>" in Notes; a parent in another module.
- Completion evidence: `mc:C-<id>`, `live:C-<id>`, `trace:C-<id>`, `run:C-<id>` resolve to
  experiment/playbook-completion/evidence/runs/<id>.json with the same kind and result pass; `proved:C-<fn>` needs a
  `proof fn <fn>` under experiment/playbook-completion/proofs and a registered proof run with result pass that lists
  the fn in `proof_fns` and whose `sources_sha256` equals the current proof sources (print it with --proof-hash).

Every message carries a rule tag in brackets, e.g. "[scope]". The output is deterministic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Pattern, Set, Tuple

PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parent.parent                      # experiment/playbook-completion
REPO = COMPLETION.parent.parent
ORIGINAL = REPO / "experiment" / "playbook-uplift"   # read-only submission: registry, proofs, TRUST, DECISIONS, ...
LITERAL_SCRIPT = COMPLETION / "check-literal-scope.py"
EXPECTED_LITERAL = (1392, 1002)                       # pairs, statements on the original modules (task statement)
MAX_GRADE = 8.0
KINDS = {"R", "D", "B", "T", "I", "X", "P", "Q"}
OUTCOMES = {"ok", "no-op", "refused", "n/a", "open"}
EVIDENCE_KINDS = ("proved", "mc", "trace", "live", "run", "ran", "tested", "inspected", "assumed", "open", "finding",
                  "not-implemented")
# Completion evidence: evidence kind -> registry kind of experiment/playbook-completion/evidence/runs/<id>.json
COMPLETION_KINDS = {"mc": "mc", "live": "live", "trace": "trace", "run": "run", "proved": "proof"}
# Audit dispositions that are evidence about the product (experiment/playbook-completion/findings/audit/*.json). A
# statement that cites such a finding and also carries proved: or mc: must qualify each of those items [model-only].
PRODUCT_DISPOSITIONS = {"reproduced-live", "reproduced-test", "confirmed-source"}
# An intent-undecided finding whose evidence includes a run on the product (live, run or trace) is also evidence about
# the product: the behaviour is observed there; only its intent is open (review R2-08). It drives [model-only] too.
UNDECIDED_DISPOSITIONS = {"intent-undecided"}
PRODUCT_EVIDENCE_KINDS = {"live", "run", "trace"}
# Findings whose `intended` names a statement that carries proved: without citing the finding (review R2-03).
REPRODUCED_DISPOSITIONS = {"reproduced-live", "reproduced-test", "reproduced-model", "confirmed-source"}
MODEL_KINDS = ("proved", "mc")
QUALIFIERS = {"model-only"}
SAME_MEANING_RE = re.compile(r"Same meaning as ([A-Z]{2,4}-[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)")
ID_RE = re.compile(r"^[A-Z]{2,4}-[A-Za-z0-9.]+$")
SYSTEM = "SYS"
TEST_RESULTS: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
TRIAGE: Dict[str, str] = {}


@dataclass
class Ctx:
    ontology: Path      # directory with the NN-*.md module files
    original: Path      # the original submission root (evidence/runs.json, proofs/, TRUST.md, ...)
    completion: Path    # the completion root (evidence/runs/<id>.json, proofs/)


def default_ctx() -> Ctx:
    return Ctx(COMPLETION / "ontology", ORIGINAL, COMPLETION)


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


# --------------------------------------------------------------------------- readability (unchanged)

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


# --------------------------------------------------------------------------- term matching

def literal_pattern(term: str) -> Pattern[str]:
    """Exactly the pattern of experiment/playbook-completion/check-literal-scope.py (used by the differential)."""
    return re.compile(r"(?<![A-Za-z0-9-])" + re.escape(term).replace(r"\ ", r"[\s-]+")
                      + r"(?:s|es)?(?![A-Za-z0-9-])", re.IGNORECASE)


def strong_pattern(term: str) -> Pattern[str]:
    """A superset of literal_pattern: hyphens inside a term also match spaces, and a final consonant+y also
    matches ies. Case-insensitive whole words with plural s/es as before."""
    words = [w for w in re.split(r"[\s-]+", term.strip()) if w]
    last = words[-1]
    if re.search(r"[^aeiou]y$", last, re.IGNORECASE):
        tail = re.escape(last[:-1]) + r"(?:y(?:s|es)?|ies)"
    else:
        tail = re.escape(last) + r"(?:s|es)?"
    body = r"[\s-]+".join([re.escape(w) for w in words[:-1]] + [tail])
    return re.compile(r"(?<![A-Za-z0-9-])" + body + r"(?![A-Za-z0-9-])", re.IGNORECASE)


MATCHERS: Dict[str, Callable[[str], Pattern[str]]] = {"literal": literal_pattern, "strong": strong_pattern}


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
class Gloss:
    term: str
    primary: str
    restated: List[str] = field(default_factory=list)

    @property
    def definers(self) -> List[str]:
        return [self.primary] + self.restated


@dataclass
class Module:
    code: str
    root: str
    title: str
    file: str
    scope: str
    glossary: List[Gloss] = field(default_factory=list)
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
        errors.append(f"{rel}: [format] missing 'Module:' or 'Root:' header")
        return None
    mod = Module(fields["Module"], fields["Root"], title, rel, fields.get("Scope", ""))

    header, rows, _ = table_after(lines, "Glossary")
    if header and header not in (["Term", "Defined by"], ["Term", "Defined by", "Restated by"]):
        errors.append(f"{rel}: [format] Glossary columns must be 'Term | Defined by' or "
                      f"'Term | Defined by | Restated by', got {header}")
    for r in rows:
        if len(r) >= 2 and r[0]:
            restated = [x for x in re.split(r"[,; ]+", r[2]) if x] if len(r) >= 3 else []
            mod.glossary.append(Gloss(r[0].strip().lower(), r[1].strip(), restated))

    want = ["Id", "Parent", "Kind", "Statement", "Evidence", "Source", "Notes"]
    header, rows, _ = table_after(lines, "Statements")
    if header != want:
        errors.append(f"{rel}: [format] Statements columns must be {' | '.join(want)}, got {header}")
        return mod
    for k, r in enumerate(rows):
        if len(r) != len(want):
            errors.append(f"{rel}: [format] statement row {k + 1} has {len(r)} cells, want {len(want)}: {r[:1]}")
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
        errors.append(f"{rel}: [format] Cells columns must be {' | '.join(cwant)}, got {header}")
    elif header:
        for r in rows:
            if len(r) != len(cwant):
                errors.append(f"{rel}: [format] cell row has {len(r)} cells: {r}")
                continue
            ids = [x.strip() for x in re.split(r"[,; ]+", r[4]) if x.strip()]
            mod.cells.append(Cell(r[0], r[1], r[2], r[3], ids, r[5].strip(), rel))
    return mod


def load_modules(ontology: Path, errors: List[str]) -> Tuple[List[Module], Dict[str, Statement]]:
    modules: List[Module] = []
    base = 0
    for f in sorted(ontology.glob("[0-9][0-9]-*.md")):
        m = parse_module(f, errors, base)
        if m:
            modules.append(m)
            base += len(m.statements) + 1
    by_id: Dict[str, Statement] = {}
    for m in modules:
        for s in m.statements:
            if s.id in by_id:
                errors.append(f"{s.file}: [duplicate-id] duplicate id {s.id} (first in {by_id[s.id].file})")
                continue
            by_id[s.id] = s
    return modules, by_id


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


def sources_hash(paths: Iterable[Path], base: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(base)).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def proof_sources(proofs: Path) -> List[Path]:
    if not proofs.exists():
        return []
    return sorted(p for p in proofs.rglob("*") if p.is_file() and p.suffix in (".rs", ".toml")
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


# --------------------------------------------------------------------------- evidence

SOURCE_PATH_RE = re.compile(
    r"(?<![\w/.-])((?:docs|specs|iris_src|iris_vector_graph|api|sql|src|tests|scripts|config|deploy|docker|"
    r"benchmarks|examples|vendor|skills)/[A-Za-z0-9_./\-]+|[A-Z][A-Z_]+\.md|pyproject\.toml|docker-compose\.yml)"
)


def evidence_quals(ev: str) -> List[Tuple[str, str, List[str]]]:
    """Evidence items as (kind, ref, qualifiers). A qualifier is a trailing bracket, e.g.
    'proved:theorem_x [model-only]'."""
    out = []
    for raw in [x.strip() for x in ev.split(";") if x.strip()]:
        quals: List[str] = []
        m = re.match(r"^(.*?)\s*\[([a-z-]+)\]$", raw)
        if m:
            raw, quals = m.group(1).strip(), [m.group(2)]
        if raw == "not-implemented":
            out.append(("not-implemented", "", quals))
            continue
        kind, _, ref = raw.partition(":")
        out.append((kind.strip(), ref.strip(), quals))
    return out


def evidence_items(ev: str) -> List[Tuple[str, str]]:
    return [(k, r) for k, r, _ in evidence_quals(ev)]


def load_audit(completion: Path) -> Dict[str, dict]:
    """Finding records of experiment/playbook-completion/findings/audit/*.json (a list, or an object with
    'findings' and 'new_findings')."""
    out: Dict[str, dict] = {}
    d = completion / "findings" / "audit"
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else list(data.get("findings", [])) + list(data.get("new_findings", []))
        for f in items:
            if isinstance(f, dict) and f.get("id"):
                out[f["id"]] = dict(f, _file=p.name)
    return out


class Evidence:
    """Loaded once per check: the original registry and documents, and the completion run records."""

    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        p = ctx.original / "evidence" / "runs.json"
        self.registry = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        self.trust = ids_in(ctx.original / "TRUST.md", "P")
        self.decisions = human_decisions(ctx.original / "DECISIONS.md")
        self.findings = ids_in(ctx.original / "FINDINGS.md", "F")
        self.audit = load_audit(ctx.completion)
        self.orig_srcs = proof_sources(ctx.original / "proofs")
        self.orig_proof_body = "\n".join(p.read_text(encoding="utf-8") for p in self.orig_srcs if p.suffix == ".rs")
        self.orig_hash = sources_hash(self.orig_srcs, REPO) if self.orig_srcs else ""
        self.comp_srcs = proof_sources(ctx.completion / "proofs")
        self.comp_proof_body = "\n".join(p.read_text(encoding="utf-8") for p in self.comp_srcs if p.suffix == ".rs")
        self.comp_hash = sources_hash(self.comp_srcs, ctx.completion) if self.comp_srcs else ""
        self.runs_dir = ctx.completion / "evidence" / "runs"
        self._records: Dict[str, Optional[dict]] = {}

    def record(self, rid: str) -> Optional[dict]:
        if rid not in self._records:
            p = self.runs_dir / f"{rid}.json"
            try:
                self._records[rid] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
            except (OSError, ValueError):
                self._records[rid] = None
        return self._records[rid]

    def all_records(self) -> List[dict]:
        out = []
        if self.runs_dir.is_dir():
            for p in sorted(self.runs_dir.glob("*.json")):
                r = self.record(p.stem)
                if r is not None:
                    out.append(r)
        return out


def check_completion_ref(where: str, kind: str, ref: str, ev: Evidence, errors: List[str]) -> None:
    rid = ref[2:]
    want = COMPLETION_KINDS.get(kind)
    if want is None:
        errors.append(f"{where}: [evidence] {kind}:{ref}: completion references exist only for "
                      f"{', '.join(sorted(COMPLETION_KINDS))}")
        return
    if not rid or not re.match(r"^[A-Za-z0-9_.\-]+$", rid):
        errors.append(f"{where}: [evidence] {kind}:{ref}: malformed completion reference")
        return
    if kind == "proved":
        if not re.search(rf"\bproof\s+fn\s+{re.escape(rid)}\b", ev.comp_proof_body):
            errors.append(f"{where}: [evidence] proved:{ref}: no proof fn {rid} in experiment/playbook-completion/proofs")
            return
        ok = [r for r in ev.all_records()
              if r.get("kind") == "proof" and r.get("result") == "pass" and r.get("product_pin") == PIN
              and rid in (r.get("proof_fns") if isinstance(r.get("proof_fns"), list)
                          else re.split(r"[,\s]+", str(r.get("proof_fns", ""))))
              and r.get("sources_sha256") == ev.comp_hash]
        if not ok:
            errors.append(f"{where}: [evidence] proved:{ref}: no registered proof run with result pass lists {rid} "
                          f"over the current completion proof sources (sha256 {ev.comp_hash[:12] or 'none'})")
        return
    rec = ev.record(rid)
    if rec is None:
        errors.append(f"{where}: [evidence] {kind}:{ref}: no record evidence/runs/{rid}.json")
    elif rec.get("id") != rid or rec.get("kind") != want or rec.get("result") != "pass" \
            or rec.get("product_pin") != PIN:
        errors.append(f"{where}: [evidence] {kind}:{ref}: record is id={rec.get('id')} kind={rec.get('kind')} "
                      f"result={rec.get('result')} pin={str(rec.get('product_pin'))[:8]}; want kind={want} "
                      f"result=pass pin={PIN[:8]}")


def check_evidence(s: Statement, tree: Tree, ev: Evidence, errors: List[str]) -> None:
    where = f"{s.file} {s.id}"
    items = evidence_items(s.evidence)
    if not items:
        errors.append(f"{where}: [evidence] no evidence (use inspected/tested/... or open:/not-implemented)")
    kinds = {k for k, _ in items}
    if s.kind == "Q" and "open" not in kinds:
        errors.append(f"{where}: [evidence] an open question needs open:HD-NN")
    for kind, ref in items:
        if kind not in EVIDENCE_KINDS or kind == "ran":
            errors.append(f"{where}: [evidence] evidence kind '{kind}' unknown")
            continue
        if kind in COMPLETION_KINDS and ref.startswith("C-"):
            check_completion_ref(where, kind, ref, ev, errors)
            continue
        if kind == "trace":
            errors.append(f"{where}: [evidence] trace:{ref}: trace evidence exists only as trace:C-<id>")
        elif kind == "inspected":
            m = re.match(r"^(.+?):(\d+)(?:-(\d+))?$", ref)
            if not m:
                errors.append(f"{where}: [evidence] inspected needs <path>:<line>[-<line>], got '{ref}'")
                continue
            text = tree.text(m.group(1))
            if text is None:
                errors.append(f"{where}: [evidence] inspected path '{m.group(1)}' not in the pin")
                continue
            n = text.count("\n") + (0 if text.endswith("\n") else 1)
            a, b = int(m.group(2)), int(m.group(3) or m.group(2))
            if not (1 <= a <= b <= n):
                errors.append(f"{where}: [evidence] inspected lines {a}-{b} outside {m.group(1)} (1-{n})")
        elif kind == "tested":
            path, _, name = ref.partition("::")
            text = tree.text(path)
            if text is None:
                errors.append(f"{where}: [evidence] tested path '{path}' not in the pin")
                continue
            leaf = name.split("::")[-1].split("[")[0] if name else ""
            if leaf and not re.search(rf"\b(?:def|class)\s+{re.escape(leaf)}\b", text):
                errors.append(f"{where}: [evidence] tested name '{leaf}' not defined in {path}")
        elif kind in ("run", "live", "mc"):
            entry = ev.registry.get("runs", {}).get(ref)
            if entry is None:
                errors.append(f"{where}: [evidence] {kind}:{ref} not in evidence/runs.json")
            elif entry.get("kind") != kind or entry.get("result") != "pass":
                errors.append(f"{where}: [evidence] {kind}:{ref} registry entry is kind={entry.get('kind')} "
                              f"result={entry.get('result')}")
        elif kind == "proved":
            if not re.search(rf"\bproof\s+fn\s+{re.escape(ref)}\b", ev.orig_proof_body):
                errors.append(f"{where}: [evidence] proved:{ref} is not a proof fn in proofs/")
                continue
            verus = ev.registry.get("verus", {})
            if verus.get("errors") != 0 or verus.get("sources_sha256") != ev.orig_hash:
                errors.append(f"{where}: [evidence] proved:{ref} has no decisive Verus run over the current proof sources")
            elif ref not in set(verus.get("proof_fns", [])):
                errors.append(f"{where}: [evidence] proved:{ref} is not in the Verus run's verified function list")
        elif kind == "assumed" and ref not in ev.trust:
            errors.append(f"{where}: [evidence] premise {ref} not in TRUST.md")
        elif kind == "open" and ev.decisions.get(ref) != "human":
            errors.append(f"{where}: [evidence] decision {ref} not in DECISIONS.md with Owner: human")
        elif kind == "finding" and ref.startswith("F-C") and ref not in ev.audit:
            errors.append(f"{where}: [evidence] finding {ref} not in experiment/playbook-completion/findings/audit")
        elif kind == "finding" and not ref.startswith("F-C") and ref not in ev.findings:
            errors.append(f"{where}: [evidence] finding {ref} not in FINDINGS.md")
        elif kind == "not-implemented" and not s.source.strip():
            errors.append(f"{where}: [evidence] not-implemented needs the intent in Source")
    check_model_only(s, ev, errors)


def observed_on_product(f: Optional[dict]) -> bool:
    """A finding record that is evidence about the product: its disposition is reproduced-live, reproduced-test or
    confirmed-source, or it is intent-undecided and its own evidence includes a live, run or trace item."""
    if not f:
        return False
    if f.get("disposition") in PRODUCT_DISPOSITIONS:
        return True
    if f.get("disposition") in UNDECIDED_DISPOSITIONS:
        return any(isinstance(e, dict) and e.get("kind") in PRODUCT_EVIDENCE_KINDS for e in f.get("evidence") or [])
    return False


def product_findings(s: Statement, ev: "Evidence") -> List[str]:
    """Findings the statement cites that are evidence about the product (observed_on_product)."""
    return [ref for kind, ref in evidence_items(s.evidence)
            if kind == "finding" and observed_on_product(ev.audit.get(ref))]


def check_model_only(s: Statement, ev: "Evidence", errors: List[str]) -> None:
    where = f"{s.file} {s.id}"
    for kind, ref, quals in evidence_quals(s.evidence):
        for q in quals:
            if q not in QUALIFIERS:
                errors.append(f"{where}: [evidence] unknown qualifier [{q}] on {kind}:{ref}")
            elif kind not in MODEL_KINDS:
                errors.append(f"{where}: [evidence] [{q}] qualifies only proved: or mc:, not {kind}:{ref}")
    bad = product_findings(s, ev)
    if not bad:
        return
    for kind, ref, quals in evidence_quals(s.evidence):
        if kind in MODEL_KINDS and "model-only" not in quals:
            errors.append(f"{where}: [model-only] {kind}:{ref} sits beside {', '.join(bad)} (audit disposition "
                          f"{', '.join(sorted({ev.audit[b]['disposition'] for b in bad}))}): the product violates "
                          f"the statement, so mark it '{kind}:{ref} [model-only]'")


# --------------------------------------------------------------------------- the literal scope rule

def literal_scope(s: Statement, module: Module, by_id: Dict[str, Statement]) -> Set[str]:
    """The statement, its ancestors (parent chain), and earlier statements with the same parent. Nothing else."""
    scope = {s.id}
    scope.update(x.id for x in module.statements if x.parent == s.parent and x.order < s.order)
    node, seen = s, {s.id}
    while node.parent in by_id and node.parent not in seen:
        node = by_id[node.parent]
        seen.add(node.id)
        scope.add(node.id)
    return scope


def scope_pairs(modules: List[Module], by_id: Dict[str, Statement], matcher: str = "strong",
                primary_only: bool = False) -> Set[Tuple[str, str]]:
    """(statement id, term) pairs where a module glossary term is used and no definer of it is in literal scope.
    primary_only: count only the 'Defined by' column (the original format has no restatements)."""
    make = MATCHERS[matcher]
    out: Set[Tuple[str, str]] = set()
    for m in modules:
        pats = {g.term: make(g.term) for g in m.glossary}
        for s in m.statements:
            scope = literal_scope(s, m, by_id)
            for g in m.glossary:
                definers = {g.primary} if primary_only else set(g.definers)
                if not (definers & scope) and pats[g.term].search(s.text):
                    out.add((s.id, g.term))
    return out


# --------------------------------------------------------------------------- checks

def check(ctx: Ctx, tree: Tree) -> Tuple[List[Module], List[str], Dict[str, Statement]]:
    errors: List[str] = []
    modules, by_id = load_modules(ctx.ontology, errors)
    ev = Evidence(ctx)
    for m in modules:
        if not any(s.id == m.root and s.kind == "R" for s in m.statements):
            errors.append(f"{m.file}: [root] root {m.root} is not a statement of kind R")
        for s in m.statements:
            if by_id.get(s.id) is not s:
                continue
            where = f"{s.file} {s.id}"
            if not ID_RE.match(s.id) or not s.id.startswith(m.code + "-"):
                errors.append(f"{where}: [id] id must be '{m.code}-<suffix>'")
            if s.kind not in KINDS:
                errors.append(f"{where}: [kind] kind '{s.kind}' not in {sorted(KINDS)}")
            if s.kind == "R":
                expect = "-" if s.id == "SYS-0" else "SYS-0"
                if s.parent != expect or s.id != m.root:
                    errors.append(f"{where}: [parent] a root's parent is {expect} and its id is the module's Root")
            else:
                p = by_id.get(s.parent)
                if p is None:
                    errors.append(f"{where}: [parent] parent does not resolve: '{s.parent}'")
                elif p.order >= s.order:
                    errors.append(f"{where}: [parent] parent {s.parent} must come earlier")
                elif p.module != s.module:
                    errors.append(f"{where}: [parent] parent {s.parent} is in another module")
            if not s.text:
                errors.append(f"{where}: [text] empty statement")
            if "`" in s.text:
                errors.append(f"{where}: [text] code in the statement text; move it to Source or Notes")
            g = fk_grade(s.text)
            if g > MAX_GRADE:
                errors.append(f"{where}: [grade] reading grade {g:.1f} > {MAX_GRADE:.0f}: {s.text}")
            for path in SOURCE_PATH_RE.findall(s.source):
                p = path.rstrip(".,)")
                if not tree.exists(p) and not (ctx.original / p).exists() and not (REPO / p).exists():
                    errors.append(f"{where}: [source] Source path '{p}' does not exist at the pin")
            if not s.source.strip():
                errors.append(f"{where}: [source] Source is empty")
            check_evidence(s, tree, ev, errors)
    check_glossary(modules, by_id, errors)
    check_cells(modules, by_id, ev, errors)
    check_uncited_findings(modules, by_id, ev, errors)
    return modules, errors, by_id


def check_uncited_findings(modules: List[Module], by_id: Dict[str, Statement], ev: "Evidence",
                           errors: List[str]) -> None:
    """[uncited-finding] (review R2-03): a statement that a reproduced finding's `intended` field names as the
    contract it violates, that carries a proved: item and does not cite the finding. The [model-only] rule fires only
    on cited findings, so a missing citation would otherwise keep a proof tag on a contradicted statement unmarked."""
    codes = sorted({m.code for m in modules}, key=len, reverse=True)
    if not codes:
        return
    sid = re.compile(rf"(?<![A-Za-z0-9-])((?:{'|'.join(map(re.escape, codes))})-[A-Z]*\d+(?:\.\d+)*[a-z]?)(?![A-Za-z0-9])")
    for fid, f in sorted(ev.audit.items()):
        if f.get("disposition") not in REPRODUCED_DISPOSITIONS:
            continue
        for name in dict.fromkeys(sid.findall(str(f.get("intended", "")))):
            s = by_id.get(name)
            if s is None:
                continue
            items = evidence_items(s.evidence)
            if any(k == "proved" for k, _ in items) and not any(k == "finding" and r == fid for k, r in items):
                errors.append(f"{s.file} {s.id}: [uncited-finding] {fid} ({f.get('disposition')}) names {s.id} in "
                              f"its intended contract and the statement carries proved: without citing it; cite "
                              f"finding:{fid} (its proof items then need [model-only]) or correct the finding")


def check_glossary(modules: List[Module], by_id: Dict[str, Statement], errors: List[str]) -> None:
    make = MATCHERS["strong"]
    valid: Dict[str, Dict[str, Gloss]] = {}
    for m in modules:
        valid[m.code] = {}
        seen: Set[str] = set()
        for g in m.glossary:
            if g.term in seen:
                errors.append(f"{m.file}: [glossary-duplicate] term '{g.term}' has more than one row")
                continue
            seen.add(g.term)
            pat = make(g.term)
            ok = True
            for k, sid in enumerate(g.definers):
                role = "definer" if k == 0 else "restatement"
                s = by_id.get(sid)
                if s is None:
                    errors.append(f"{m.file}: [definer-kind] glossary term '{g.term}' points at '{sid}', "
                                  f"which is not a statement")
                    ok = False
                    continue
                if s.kind != "D":
                    errors.append(f"{m.file}: [definer-kind] glossary term '{g.term}' {role} {sid} is kind "
                                  f"{s.kind}, not D")
                    ok = False
                if s.module != m.code:
                    errors.append(f"{m.file}: [cross-module] glossary term '{g.term}' {role} {sid} is in module "
                                  f"{s.module}; define it again locally")
                    ok = False
                if not pat.search(s.text):
                    errors.append(f"{m.file}: [definer-text] glossary term '{g.term}' {role} {sid} does not "
                                  f"contain the term: {s.text}")
                    ok = False
            p = by_id.get(g.primary)
            for sid in g.restated:
                s = by_id.get(sid)
                if s is None or p is None:
                    continue
                cited = SAME_MEANING_RE.findall(s.notes)
                if g.primary not in cited:
                    errors.append(f"{m.file} {sid}: [restatement] restates '{g.term}' but Notes do not say "
                                  f"'Same meaning as {g.primary}'")
                    ok = False
                if " ".join(s.text.split()) != " ".join(p.text.split()):
                    errors.append(f"{m.file} {sid}: [restatement] text differs from the primary definition "
                                  f"{g.primary}")
                    ok = False
                if s.order <= p.order:
                    errors.append(f"{m.file} {sid}: [restatement] comes before the primary definition {g.primary}")
                    ok = False
                if " ".join(s.evidence.split()) != " ".join(p.evidence.split()):
                    errors.append(f"{m.file} {sid}: [restatement] evidence differs from the primary definition "
                                  f"{g.primary}'s")
                    ok = False
            if len(set(g.definers)) != len(g.definers):
                errors.append(f"{m.file}: [glossary-duplicate] term '{g.term}' lists a definer twice")
            if ok:
                valid[m.code][g.term] = g
    # every D statement that cites "Same meaning as X" for a same-module X must be a listed restatement of X's term
    listed = {sid for m in modules for g in m.glossary for sid in g.restated}
    for m in modules:
        own = {s.id for s in m.statements}
        for s in m.statements:
            for x in SAME_MEANING_RE.findall(s.notes):
                if s.kind == "D" and x in own and s.id not in listed \
                        and not any(g.primary == s.id for g in m.glossary):
                    errors.append(f"{s.file} {s.id}: [restatement] says 'Same meaning as {x}' but is not listed "
                                  f"in the glossary")
    # the literal scope rule, document order, and terms of other modules
    sys_terms = {g.term for m in modules if m.code == SYSTEM for g in m.glossary}
    for m in modules:
        pats = {g.term: make(g.term) for g in m.glossary}
        own_terms = set(pats)
        for s in m.statements:
            scope = literal_scope(s, m, by_id)
            for g in m.glossary:
                if not pats[g.term].search(s.text):
                    continue
                definers = set(g.definers)
                if not (definers & scope):
                    errors.append(f"{s.file} {s.id}: [scope] uses '{g.term}' with no definition in scope "
                                  f"(defined by {g.primary}"
                                  + (f"; restated by {', '.join(g.restated)}" if g.restated else "") + ")")
                p = by_id.get(g.primary)
                if p is not None and p.module == m.code and p.order > s.order:
                    errors.append(f"{s.file} {s.id}: [order] uses '{g.term}' before its definition {g.primary} "
                                  f"in document order")
        if m.code == SYSTEM:
            continue
        for other in modules:
            if other is m or other.code == SYSTEM:
                continue
            for g in other.glossary:
                if g.term in own_terms or g.term in sys_terms:
                    continue
                pat = make(g.term)
                for s in m.statements:
                    if pat.search(s.text):
                        errors.append(f"{s.file} {s.id}: [foreign-term] uses '{g.term}' from module {other.code}'s "
                                      f"glossary; define it in module {m.code}")


def check_cells(modules: List[Module], by_id: Dict[str, Statement], ev: Evidence, errors: List[str]) -> None:
    for m in modules:
        seen = set()
        for c in m.cells:
            key = (c.entity, c.state, c.command)
            where = f"{m.file} cell {key}"
            if key in seen:
                errors.append(f"{where}: [cell] duplicate")
            seen.add(key)
            if c.entity not in m.entities:
                errors.append(f"{where}: [cell] entity not declared on an 'Entity' line")
            else:
                st, cmd = m.entities[c.entity]
                if c.state not in st or c.command not in cmd:
                    errors.append(f"{where}: [cell] state or command not declared for the entity")
            if c.outcome not in OUTCOMES:
                errors.append(f"{where}: [cell] outcome '{c.outcome}' not in {sorted(OUTCOMES)}")
            if c.outcome == "open":
                if ev.decisions.get(c.decision) != "human":
                    errors.append(f"{where}: [cell] open cell needs a decision HD-NN owned by the human")
            else:
                if not c.statements:
                    errors.append(f"{where}: [cell] cites no statement")
                for sid in c.statements:
                    if sid not in by_id:
                        errors.append(f"{where}: [cell] statement '{sid}' does not resolve")
        for ent, (states, cmds) in m.entities.items():
            for st in states:
                for cmd in cmds:
                    if (ent, st, cmd) not in seen:
                        errors.append(f"{m.file}: [cell] cell ({ent}, {st}, {cmd}) is not defined")


# --------------------------------------------------------------------------- index

INDEX_KINDS = ("proved", "proved (model-only)", "mc", "mc (model-only)", "trace", "live", "run", "ran", "tested",
               "inspected", "assumed", "open", "finding", "not-implemented")
PRODUCT_KINDS = {"trace", "live", "run", "ran", "tested", "inspected"}


def classify(s: Statement) -> Set[str]:
    kinds = {f"{k} (model-only)" if k in MODEL_KINDS and "model-only" in q else k
             for k, _, q in evidence_quals(s.evidence)}
    if any(any(st == "pass" for _, st in TEST_RESULTS.get(ref, [])) for ref in tested_refs(s)):
        kinds.add("ran")
    return kinds


def render(modules: List[Module], errors: List[str], by_id: Dict[str, Statement],
           audit: Optional[Dict[str, dict]] = None) -> str:
    audit = audit or {}
    out = ["# Ontology index", "",
           "Generated by `experiment/playbook-completion/ontology/tools/ontology_check.py` from the module files in",
           f"this directory. Do not edit. Product pin `{PIN[:8]}`. Evidence without a `C-` prefix resolves against the",
           "original submission (`experiment/playbook-uplift/`); `C-` references resolve against",
           "`experiment/playbook-completion/evidence/runs/`.", ""]
    out += ["## How to read the evidence", "",
            "- **proved**: a Verus proof over the L1/L2 models in `proofs/` (decisive run recorded in `evidence/runs.json`). "
            "Proofs are about models; where the code at the pin differs from the proved design, the statement also cites a finding.",
            "- **mc**: an explicit-state model check in `model/`, exhaustive only within the bounds the machine declares "
            "(see `MODELS.md`). A model is an executable twin, not the code.",
            "- **proved (model-only)**, **mc (model-only)**: the item carries `[model-only]` because the statement also "
            "cites a finding whose audit disposition (reproduced-live, reproduced-test or confirmed-source, in "
            "`experiment/playbook-completion/findings/audit/`) shows the product at the pin violates it. The proof or "
            "model check is about a modelled design; it is not evidence that the product holds the statement. The "
            "checker rejects an unqualified proved:/mc: item beside such a finding.",
            "- **trace**: a real execution trace replayed through a machine (completion runs only).",
            "- **live**: observed on IRIS Community 2026.1 in the dedicated container (logs under `$RUN_DIR`).",
            "- **run**: an upstream test set executed here. **ran**: a cited upstream test (`tested:`) that passed in one of "
            "those runs. **tested**: an upstream test that asserts the statement; not necessarily run here.",
            "- **inspected**: read in production code at the pin. **assumed**: a named premise in `TRUST.md` or `trust/`. "
            "**open**: a decision for the human. **finding**: the code disagrees.", ""]
    out += ["## Gate", ""]
    if errors:
        out += [f"**FAIL**: {len(errors)} violation(s).", ""] + [f"- {e}" for e in errors] + [""]
    else:
        n_cells = sum(len(m.cells) for m in modules)
        n_terms = sum(len(m.glossary) for m in modules)
        n_rest = len({sid for m in modules for g in m.glossary for sid in g.restated})
        out += [f"**PASS**: {len(by_id)} statements in {len(modules)} modules, {n_cells} cells, {n_terms} glossary "
                f"terms ({n_rest} local restatements). Every parent resolves, every statement reads at grade 8 or "
                "below, every module glossary term a statement uses is defined by the statement, an ancestor or an "
                "earlier statement with the same parent (literal rule, HD-0001) and never before its definition, "
                "every evidence reference resolves, every proof or model-check item beside a finding that shows the product "
                "violates the statement is marked model-only, and every cell is defined or assigned to the human.", ""]
    out += ["## Modules", "",
            "| Module | File | Statements | R | D | B | T | I | X | P | Q | Terms | Restated | Cells | Open cells | Max grade |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    tot = Counter()
    for m in modules:
        k = Counter(s.kind for s in m.statements)
        oc = sum(1 for c in m.cells if c.outcome == "open")
        mg = max((fk_grade(s.text) for s in m.statements), default=0.0)
        nr = len({sid for g in m.glossary for sid in g.restated})
        out.append(f"| {m.code} | {m.file} | {len(m.statements)} | " + " | ".join(str(k[x]) for x in "RDBTIXPQ")
                   + f" | {len(m.glossary)} | {nr} | {len(m.cells)} | {oc} | {mg:.1f} |")
        tot.update(k)
        tot["n"] += len(m.statements)
        tot["terms"] += len(m.glossary)
        tot["rest"] += nr
        tot["cells"] += len(m.cells)
        tot["open"] += oc
    out.append(f"| **all** | | {tot['n']} | " + " | ".join(str(tot[x]) for x in "RDBTIXPQ")
               + f" | {tot['terms']} | {tot['rest']} | {tot['cells']} | {tot['open']} | |")
    restated = {sid for m in modules for g in m.glossary for sid in g.restated}
    out += ["", "## Evidence by module", "",
            "Count of statements carrying each evidence kind (a statement may carry several). Local restatements "
            f"({len(restated)}) repeat their primary definition and its evidence, so they are left out of this table, "
            "the combinations and the listings below.", "",
            "| Module | " + " | ".join(INDEX_KINDS) + " |", "|---|" + "---:|" * len(INDEX_KINDS)]
    allc = Counter()
    for m in modules:
        c = Counter()
        for s in m.statements:
            if s.id not in restated:
                c.update(classify(s))
        allc.update(c)
        out.append(f"| {m.code} | " + " | ".join(str(c[k]) for k in INDEX_KINDS) + " |")
    out.append("| **all** | " + " | ".join(str(allc[k]) for k in INDEX_KINDS) + " |")
    out += ["", "## Model evidence and product evidence", "",
            "Statements (restatements left out). Product evidence: inspected, tested, ran, run, live or trace. Model "
            "evidence: proved or mc. A product finding is a cited finding whose audit disposition is reproduced-live, "
            "reproduced-test or confirmed-source, or intent-undecided with live, run or trace evidence (observed on "
            "the product; its intent is open).", "",
            "| Module | Statements | Product evidence | Model evidence | of which model-only | Model evidence, no product "
            "evidence | Product finding | Product finding and model evidence |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    mt = Counter()
    for m in modules:
        c = Counter()
        for s in m.statements:
            if s.id in restated:
                continue
            k = classify(s)
            model = {x for x in k if x.startswith(("proved", "mc"))}
            pf = any(kind == "finding" and observed_on_product(audit.get(ref))
                     for kind, ref in evidence_items(s.evidence))
            c["n"] += 1
            c["product"] += bool(k & PRODUCT_KINDS)
            c["model"] += bool(model)
            c["model-only"] += any(x.endswith("(model-only)") for x in model)
            c["model-no-product"] += bool(model) and not (k & PRODUCT_KINDS)
            c["pf"] += pf
            c["pf-model"] += pf and bool(model)
        mt.update(c)
        out.append(f"| {m.code} | {c['n']} | {c['product']} | {c['model']} | {c['model-only']} | "
                   f"{c['model-no-product']} | {c['pf']} | {c['pf-model']} |")
    out.append(f"| **all** | {mt['n']} | {mt['product']} | {mt['model']} | {mt['model-only']} | "
               f"{mt['model-no-product']} | {mt['pf']} | {mt['pf-model']} |")
    out += ["", "## Evidence combinations", "", "| Combination | Statements |", "|---|---:|"]
    combos = Counter("+".join(k for k in INDEX_KINDS if k in classify(s)) or "(none)" for s in by_id.values()
                     if s.id not in restated)
    for combo, n in sorted(combos.items(), key=lambda x: (-x[1], x[0])):
        out.append(f"| {combo} | {n} |")

    def listing(title: str, note: str, pred) -> None:
        rows = [s for s in sorted(by_id.values(), key=lambda x: x.order) if s.id not in restated and pred(s)]
        out.extend(["", f"## {title} ({len(rows)})", "", note, ""])
        if not rows:
            out.append("None.")
            return
        out.extend(["| Id | Statement | Evidence |", "|---|---|---|"])
        for s in rows:
            out.append(f"| {s.id} | {s.text.replace('|', '/')} | {s.evidence.replace('|', '/')} |")

    test_kinds = {"tested", "run", "live", "trace"}
    listing("Proof-only", "Proved, with no test, trace or live observation behind it.",
            lambda s: "proved" in classify(s) and not (classify(s) & test_kinds))
    listing("Proved and observed live", "Proved (not model-only) and also observed on live IRIS.",
            lambda s: {"proved", "live"} <= classify(s))
    listing("Model-only proofs and model checks",
            "Proved or model-checked as a design while a cited finding shows the product at the pin violates the "
            "statement (items marked [model-only]).",
            lambda s: any(x.endswith("(model-only)") for x in classify(s)))
    listing("Not implemented", "The intent states it; no code does it.",
            lambda s: "not-implemented" in classify(s))
    listing("Findings", "The code disagrees with the statement (original FINDINGS.md; F-C ids and every audit "
                        "disposition in experiment/playbook-completion/findings/audit/).",
            lambda s: "finding" in classify(s))
    listing("Open decisions", "Statements waiting on a human decision (see the original DECISIONS.md).",
            lambda s: "open" in classify(s))
    listing("Premises", "Statements that rest on a named premise (see the original TRUST.md).",
            lambda s: "assumed" in classify(s))
    listing("Inspection only", "Supported only by reading production code at the pin.",
            lambda s: classify(s) == {"inspected"})
    bad_tests = []
    for st in sorted(by_id.values(), key=lambda x: x.order):
        if st.id in restated:
            continue
        for ref in tested_refs(st):
            for rid, status in TEST_RESULTS.get(ref, []):
                if status not in ("pass",):
                    why = TRIAGE.get(f"{ref[0]}::{ref[1]}") or TRIAGE.get(ref[0]) or ""
                    bad_tests.append((st.id, f"{ref[0]}::{ref[1]}", rid, status, why))
    out += ["", f"## Cited tests that did not pass in the original uplift's runs ({len(bad_tests)})", ""]
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


def tally(errors: List[str]) -> str:
    c = Counter(m.group(1) for e in errors for m in [re.search(r"\[([a-z-]+)\]", e)] if m)
    return ", ".join(f"{k}={v}" for k, v in sorted(c.items())) or "none"


def run(ctx: Ctx, check_only: bool, only: Optional[List[str]] = None, tree: Optional[Tree] = None,
        print=print) -> int:
    tree = tree or Tree(REPO, PIN)
    load_test_results(ctx.original)
    modules, errors, by_id = check(ctx, tree)
    if only:
        mine = [e for e in errors if any(e.startswith(f"{n}-") or f"/{n}-" in e for n in only)]
        for e in mine:
            print("GATE:", e)
        print(f"{len(mine)} violation(s) in files {', '.join(only)} (of {len(errors)} overall); INDEX.md not written")
        return 1 if mine else 0
    text = render(modules, errors, by_id, load_audit(ctx.completion))
    idx = ctx.ontology / "INDEX.md"
    if check_only:
        stale = not idx.exists() or idx.read_text(encoding="utf-8") != text
        for e in errors:
            print("GATE:", e)
        if stale:
            print("GATE: [index] INDEX.md is stale; regenerate it")
        print(f"{len(by_id)} statements, {len(errors)} violation(s) by rule: {tally(errors)}; "
              f"index {'stale' if stale else 'current'}")
        return 1 if errors or stale else 0
    idx.write_text(text, encoding="utf-8")
    for e in errors:
        print("GATE:", e)
    print(f"{len(by_id)} statements, {len(errors)} violation(s) by rule: {tally(errors)}; wrote "
          f"{idx.relative_to(REPO) if idx.is_relative_to(REPO) else idx}")
    return 1 if errors else 0


# --------------------------------------------------------------------------- self-test

GOOD_SYS = """# 00 System

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

# The positive control. MOD-D1 defines "tomb" for the root's children; MOD-B1 uses it as a later sibling; MOD-B1.1
# and MOD-B1.2 use it through the local restatement MOD-D1a (an earlier statement with the same parent); MOD-B2 is a
# child of the definition MOD-D2 and its child MOD-B2.1 uses "out-degree" written with a space and in the plural
# ("registries" is checked the same way). The C- evidence resolves against the fixture's completion records. MOD-B4
# cites a finding reproduced live, so its proof item is marked [model-only]; MOD-B5's finding is reproduced only in a
# model, so its model check needs no mark.
GOOD_MOD = """# 01 Mod

Module: MOD
Root: MOD-0

## Glossary

| Term | Defined by | Restated by |
|---|---|---|
| tomb | MOD-D1 | MOD-D1a |
| out-degree | MOD-D2 | |
| registry | MOD-D3 | |

## Statements

| Id | Parent | Kind | Statement | Evidence | Source | Notes |
|---|---|---|---|---|---|---|
| MOD-0 | SYS-0 | R | Each part keeps its own data. | inspected:CONTEXT.md:2 | CONTEXT.md | |
| MOD-D1 | MOD-0 | D | A tomb is a mark left where data was. | inspected:CONTEXT.md:2 | CONTEXT.md | |
| MOD-B1 | MOD-0 | B | A tomb keeps its place. | inspected:CONTEXT.md:3; mc:C-good-mc | CONTEXT.md | |
| MOD-D1a | MOD-B1 | D | A tomb is a mark left where data was. | inspected:CONTEXT.md:2 | CONTEXT.md | Same meaning as MOD-D1. |
| MOD-B1.1 | MOD-B1 | B | A tomb holds no data. | inspected:CONTEXT.md:3; live:C-good-live | CONTEXT.md | |
| MOD-B1.2 | MOD-B1 | B | Tombs stay in line. | inspected:CONTEXT.md:3; trace:C-good-trace; proved:C-lemma_good | CONTEXT.md | |
| MOD-D2 | MOD-0 | D | The out-degree of a node is how many links leave it. | inspected:CONTEXT.md:4 | CONTEXT.md | |
| MOD-B2 | MOD-D2 | B | The out-degree is kept up to date. | inspected:CONTEXT.md:4 | CONTEXT.md | |
| MOD-B2.1 | MOD-B2 | B | Out degrees are never less than zero. | inspected:CONTEXT.md:4 | CONTEXT.md | |
| MOD-D3 | MOD-0 | D | A registry is a list of names. | inspected:CONTEXT.md:5 | CONTEXT.md | |
| MOD-B3 | MOD-D3 | B | Registries are kept in one place. | inspected:CONTEXT.md:5 | CONTEXT.md | |
| MOD-B4 | MOD-0 | B | A part keeps its own marks. | inspected:CONTEXT.md:6; proved:C-lemma_good [model-only]; finding:F-C9901 | CONTEXT.md | |
| MOD-B5 | MOD-0 | B | A part keeps its own name. | inspected:CONTEXT.md:7; mc:C-good-mc; finding:F-C9902 | CONTEXT.md | |

## Cells

Entity thing: states a, b; commands go

| Entity | State | Command | Outcome | Statements | Decision |
|---|---|---|---|---|---|
| thing | a | go | ok | MOD-B1 | |
| thing | b | go | refused | MOD-B1.1 | |
"""

OTHER_MOD = """# 02 Other

Module: OTH
Root: OTH-0

## Glossary

| Term | Defined by |
|---|---|
| beacon | OTH-D1 |

## Statements

| Id | Parent | Kind | Statement | Evidence | Source | Notes |
|---|---|---|---|---|---|---|
| OTH-0 | SYS-0 | R | Each part sends a sign. | inspected:CONTEXT.md:6 | CONTEXT.md | |
| OTH-D1 | OTH-0 | D | A beacon is a sign that a part is alive. | inspected:CONTEXT.md:6 | CONTEXT.md | |
"""

PROOF_RS = "verus! {\nproof fn lemma_good() ensures true {}\n}\n"

D1_ROW = "| MOD-D1 | MOD-0 | D | A tomb is a mark left where data was. | inspected:CONTEXT.md:2 | CONTEXT.md | |\n"
B1_ROW = "| MOD-B1 | MOD-0 | B | A tomb keeps its place. | inspected:CONTEXT.md:3; mc:C-good-mc | CONTEXT.md | |\n"
D1A_ROW = ("| MOD-D1a | MOD-B1 | D | A tomb is a mark left where data was. | inspected:CONTEXT.md:2 | CONTEXT.md | "
           "Same meaning as MOD-D1. |\n")
MOD = "completion/ontology/01-mod.md"

# name, rule tag that must fire, [(fixture file, old text, new text), ...]. Every control must be rejected with its
# tag; the unmutated fixture must be accepted with zero violations.
CONTROLS = [
    ("aunt (ancestor-sibling) definition: the use's only definition is an earlier sibling of its parent", "[scope]",
     [(MOD, D1A_ROW, ""), (MOD, "| tomb | MOD-D1 | MOD-D1a |", "| tomb | MOD-D1 | |")]),
    ("later definition: the definition comes after the use, same parent", "[order]",
     [(MOD, D1_ROW + B1_ROW, B1_ROW + D1_ROW)]),
    ("later definition is also out of literal scope", "[scope]",
     [(MOD, D1_ROW + B1_ROW, B1_ROW + D1_ROW)]),
    ("missing parent", "[parent]", [(MOD, "| MOD-B1.1 | MOD-B1 |", "| MOD-B1.1 | MOD-B9 |")]),
    ("parent in another (earlier) module", "[parent] parent SYS-D1 is in another module",
     [(MOD, "| MOD-B1.1 | MOD-B1 |", "| MOD-B1.1 | SYS-D1 |")]),
    ("reading grade above 8", "[grade]", [(MOD, "A tomb holds no data.",
                                           "A tombstone representation incorporates cryptographic authentication "
                                           "characteristics.")]),
    ("non-D definer", "[definer-kind]", [(MOD, "| tomb | MOD-D1 | MOD-D1a |", "| tomb | MOD-B1 | MOD-D1a |")]),
    ("definer text lacks the term", "[definer-text]", [(MOD, "| registry | MOD-D3 | |", "| registry | MOD-D2 | |")]),
    ("glossary term mapped to a statement in another module", "[cross-module]",
     [(MOD, "| registry | MOD-D3 | |", "| registry | MOD-D3 | |\n| beacon | OTH-D1 | |")]),
    ("term of another module's glossary used without a local definition", "[foreign-term]",
     [(MOD, "Registries are kept in one place.", "Registries are kept in one beacon.")]),
    ("restatement without 'Same meaning as <primary>'", "[restatement]",
     [(MOD, "CONTEXT.md | Same meaning as MOD-D1. |", "CONTEXT.md | Local copy. |")]),
    ("restatement whose text differs from the primary", "[restatement]",
     [(MOD, "| MOD-D1a | MOD-B1 | D | A tomb is a mark left where data was.",
       "| MOD-D1a | MOD-B1 | D | A tomb is a mark that never goes away.")]),
    ("restatement placed before the primary", "[restatement]",
     [(MOD, D1A_ROW, ""), (MOD, D1_ROW, D1A_ROW.replace("| MOD-B1 |", "| MOD-0 |") + D1_ROW)]),
    ("restatement not listed in the glossary", "[restatement]",
     [(MOD, "| tomb | MOD-D1 | MOD-D1a |", "| tomb | MOD-D1 | |")]),
    ("duplicate glossary row", "[glossary-duplicate]",
     [(MOD, "| registry | MOD-D3 | |", "| registry | MOD-D3 | |\n| tomb | MOD-D1 | |")]),
    ("matcher: y/ies plural used out of scope", "[scope]", [(MOD, "| MOD-B3 | MOD-D3 |", "| MOD-B3 | MOD-B2 |")]),
    ("matcher: hyphenated term written with a space, out of scope", "[scope]",
     [(MOD, "| MOD-B2 | MOD-D2 |", "| MOD-B2 | MOD-0 |")]),
    ("completion evidence: missing record", "[evidence]", [(MOD, "mc:C-good-mc", "mc:C-no-such-run")]),
    ("completion evidence: record with result fail", "[evidence]", [(MOD, "live:C-good-live", "live:C-failed-live")]),
    ("completion evidence: evidence kind differs from the record's kind", "[evidence]",
     [(MOD, "live:C-good-live", "mc:C-good-live")]),
    ("completion evidence: record for another product pin", "[evidence]",
     [("completion/evidence/runs/good-mc.json", PIN, "0" * 40)]),
    ("completion evidence: proof fn missing", "[evidence]", [(MOD, "proved:C-lemma_good", "proved:C-lemma_missing")]),
    ("completion evidence: proof sources changed after the proof run", "[evidence]",
     [("completion/proofs/src/lib.rs", "ensures true {}", "ensures true { }")]),
    ("completion evidence: trace without a C- record", "[evidence]",
     [(MOD, "trace:C-good-trace", "trace:good-trace")]),
    # the submitted tool's controls, kept
    ("cell not defined", "[cell]", [(MOD, "| thing | b | go | refused | MOD-B1.1 | |\n", "")]),
    ("cell statement does not resolve", "[cell]",
     [(MOD, "| thing | a | go | ok | MOD-B1 |", "| thing | a | go | ok | MOD-B7 |")]),
    ("open cell without a human decision", "[cell]",
     [(MOD, "| thing | b | go | refused | MOD-B1.1 | |", "| thing | b | go | open | | |")]),
    ("inspected lines outside the file", "[evidence]",
     [(MOD, "inspected:CONTEXT.md:3; live:C-good-live", "inspected:CONTEXT.md:99999; live:C-good-live")]),
    ("code in the statement", "[text]", [(MOD, "A tomb keeps its place.", "A tomb keeps its `place`.")]),
    ("premise not in TRUST.md", "[evidence]",
     [(MOD, "inspected:CONTEXT.md:3; mc:C-good-mc", "assumed:P-99; mc:C-good-mc")]),
    ("original registry id missing", "[evidence]",
     [(MOD, "inspected:CONTEXT.md:3; mc:C-good-mc", "live:nothing; mc:C-good-mc")]),
    ("derived evidence kind 'ran' written by hand", "[evidence]",
     [(MOD, "inspected:CONTEXT.md:3; mc:C-good-mc", "ran:tests/x.py; mc:C-good-mc")]),
    ("duplicate id", "[duplicate-id]", [(MOD, "| MOD-B1.1 | MOD-B1 |", "| MOD-B1 | MOD-B1 |")]),
    # model evidence versus product evidence
    ("proved: beside a finding reproduced live, without [model-only]", "[model-only]",
     [(MOD, "proved:C-lemma_good [model-only]; finding:F-C9901", "proved:C-lemma_good; finding:F-C9901")]),
    ("mc: beside an original-id finding confirmed in the audit, without [model-only]", "[model-only]",
     [(MOD, "mc:C-good-mc; finding:F-C9902", "mc:C-good-mc; finding:F-9903")]),
    ("[model-only] on evidence that is not a proof or a model check", "[evidence] [model-only] qualifies only",
     [(MOD, "inspected:CONTEXT.md:6; proved", "inspected:CONTEXT.md:6 [model-only]; proved")]),
    ("unknown qualifier", "[evidence] unknown qualifier",
     [(MOD, "proved:C-lemma_good [model-only]", "proved:C-lemma_good [model-safe]")]),
    ("F-C finding not in the findings audit", "[evidence] finding F-C9999",
     [(MOD, "finding:F-C9901", "finding:F-C9999")]),
    ("restatement whose evidence differs from the primary", "[restatement] evidence differs",
     [(MOD, "| MOD-D1a | MOD-B1 | D | A tomb is a mark left where data was. | inspected:CONTEXT.md:2 |",
       "| MOD-D1a | MOD-B1 | D | A tomb is a mark left where data was. | inspected:CONTEXT.md:3 |")]),
    # review R2-03 / R2-08
    ("proved: on a statement a reproduced finding's intended names, the finding not cited", "[uncited-finding]",
     [("completion/findings/audit/13.json", '"intended": "MOD-B4"', '"intended": "MOD-B4; MOD-B1.2"')]),
    ("mc: beside an intent-undecided finding observed live, without [model-only]", "[model-only]",
     [(MOD, "inspected:CONTEXT.md:3; mc:C-good-mc | CONTEXT.md", "inspected:CONTEXT.md:3; mc:C-good-mc; finding:F-C9904 | CONTEXT.md")]),
]


def write_fixture(root: Path) -> Ctx:
    ont = root / "completion" / "ontology"
    ont.mkdir(parents=True)
    (ont / "00-system.md").write_text(GOOD_SYS)
    (ont / "01-mod.md").write_text(GOOD_MOD)
    (ont / "02-other.md").write_text(OTHER_MOD)
    orig = root / "original"
    (orig / "evidence").mkdir(parents=True)
    (orig / "evidence" / "runs.json").write_text(json.dumps({"runs": {}}))
    (orig / "FINDINGS.md").write_text("# Findings\n\n### F-9903 An original finding\n")
    audit = root / "completion" / "findings" / "audit"
    audit.mkdir(parents=True)
    (audit / "13.json").write_text(json.dumps([
        {"id": "F-C9901", "disposition": "reproduced-live", "intended": "MOD-B4"},
        {"id": "F-C9902", "disposition": "reproduced-model", "intended": "MOD-B5"},
        {"id": "F-C9904", "disposition": "intent-undecided", "intended": "",
         "evidence": [{"kind": "live", "ref": "good-live"}]}]))
    (audit / "01.json").write_text(json.dumps({"module": "01", "findings": [
        {"id": "F-9903", "disposition": "reproduced-test", "intended": "MOD-B5"}], "new_findings": []}))
    comp = root / "completion"
    (comp / "proofs" / "src").mkdir(parents=True)
    (comp / "proofs" / "src" / "lib.rs").write_text(PROOF_RS)
    runs = comp / "evidence" / "runs"
    runs.mkdir(parents=True)
    h = sources_hash(proof_sources(comp / "proofs"), comp)
    recs = {"good-mc": ("mc", "pass", {}), "good-live": ("live", "pass", {}), "good-trace": ("trace", "pass", {}),
            "failed-live": ("live", "fail", {}),
            "good-proof": ("proof", "pass", {"proof_fns": "lemma_good", "sources_sha256": h})}
    for rid, (kind, result, extra) in recs.items():
        rec = {"id": rid, "kind": kind, "result": result, "product_pin": PIN, **extra}
        (runs / f"{rid}.json").write_text(json.dumps(rec, indent=2))
    return Ctx(ont, orig, comp)


def literal_script_pairs(original: Path) -> Set[Tuple[str, str]]:
    r = subprocess.run([sys.executable, "-B", str(LITERAL_SCRIPT), str(original), "--details"],
                       capture_output=True, text=True, check=True)
    pairs = set()
    for line in r.stdout.splitlines():
        if "\t" in line:
            a, b = line.split("\t")
            pairs.add((a, b))
    return pairs


def differential() -> int:
    """The literal rule of this tool against the independent check-literal-scope.py, on the ORIGINAL modules."""
    errors: List[str] = []
    modules, by_id = load_modules(ORIGINAL / "ontology", errors)
    if errors:
        print("differential: the original modules do not parse:", errors[:5])
        return 1
    mine = scope_pairs(modules, by_id, "literal", primary_only=True)
    theirs = literal_script_pairs(ORIGINAL)
    n_s = len({s for s, _ in mine})
    ok = mine == theirs and (len(mine), n_s) == EXPECTED_LITERAL
    print(f"differential: this tool (literal rule, literal matcher) on the original modules: {len(mine)} pairs in "
          f"{n_s} statements; check-literal-scope.py: {len(theirs)} pairs in {len({s for s, _ in theirs})} "
          f"statements; expected {EXPECTED_LITERAL[0]}/{EXPECTED_LITERAL[1]}; only this tool={len(mine - theirs)}, "
          f"only the script={len(theirs - mine)} -> {'EQUAL' if ok else 'DIFFERENT'}")
    strong = scope_pairs(modules, by_id, "strong", primary_only=True)
    sup = theirs <= strong
    extra = sorted(strong - theirs)
    print(f"differential: this tool (literal rule, strong matcher, the gate's setting) on the original modules: "
          f"{len(strong)} pairs in {len({s for s, _ in strong})} statements; superset of the script's pairs: {sup}; "
          f"{len(extra)} extra pair(s): {', '.join(f'{a}/{b}' for a, b in extra) or 'none'}")
    return 0 if ok and sup else 1


def self_test() -> int:
    tree = Tree(REPO, PIN)
    failures = 0
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        ctx = write_fixture(root)
        _, errs, _ = check(ctx, tree)
        if errs:
            print("self-test: POSITIVE CONTROL REJECTED:", *errs, sep="\n  ")
            return 1
        print("self-test: positive control accepted (0 violations; exercises a restatement, a definition parent, "
              "out degree / registries spellings, mc/live/trace/proved C- evidence, an F-C finding with a "
              "[model-only] proof, a model-reproduced finding beside an unmarked model check)")
        for name, tag, edits in CONTROLS:
            saved = {}
            broken = False
            for rel, old, new in edits:
                path = root / rel
                text = path.read_text()
                saved.setdefault(path, text)
                if old not in text:
                    broken = True
                    break
                path.write_text(text.replace(old, new, 1))
            if broken:
                print(f"self-test: BROKEN CONTROL {name}: anchor text not in the fixture")
                failures += 1
            else:
                _, errs, _ = check(ctx, tree)
                hit = [e for e in errs if tag in e]
                print(f"self-test: {'REJECTED' if hit else 'ACCEPTED (control failed)'} {tag} {name}"
                      + (f"\n    -> {hit[0]}" if hit else ""))
                failures += 0 if hit else 1
            for path, text in saved.items():
                path.write_text(text)
        # the index: write it, edit it by hand, then --check must call it stale
        out: List[str] = []
        rc_write = run(ctx, False, tree=tree, print=lambda *a: out.append(" ".join(map(str, a))))
        idx = ctx.ontology / "INDEX.md"
        idx.write_text(idx.read_text().replace("**PASS**", "**PASS** (edited)"))
        rc_check = run(ctx, True, tree=tree, print=lambda *a: out.append(" ".join(map(str, a))))
        hit = rc_write == 0 and rc_check == 1 and any("[index]" in l for l in out)
        print(f"self-test: {'REJECTED' if hit else 'ACCEPTED (control failed)'} [index] hand-edited INDEX.md")
        failures += 0 if hit else 1
    total = len(CONTROLS) + 1
    print(f"self-test: {total - failures}/{total} negative controls rejected")
    rc = differential()
    ok = not failures and not rc
    print(f"self-test: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def system_terms() -> int:
    """Informational: the gate checks each statement against its own module's glossary (playbook §3.1, as
    check-literal-scope.py does). SYS terms used in other modules are outside that gate; under the literal rule the
    SYS definitions are earlier siblings of each module root, so they would never be in scope there."""
    errors: List[str] = []
    modules, by_id = load_modules(default_ctx().ontology, errors)
    sysmod = next(m for m in modules if m.code == SYSTEM)
    pats = {g.term: strong_pattern(g.term) for g in sysmod.glossary}
    pairs = set()
    for m in modules:
        if m.code == SYSTEM:
            continue
        own = {g.term for g in m.glossary}
        for s in m.statements:
            for t, p in pats.items():
                if t not in own and p.search(s.text):
                    pairs.add((s.id, t))
    by_term = Counter(t for _, t in pairs)
    print(f"{len(pairs)} statement/term pairs in {len({s for s, _ in pairs})} statements outside SYS use a SYS "
          f"glossary term (not gated): " + ", ".join(f"{t}={n}" for t, n in by_term.most_common()))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--differential", action="store_true", help="only the differential against check-literal-scope.py")
    ap.add_argument("--grade", help="print the reading grade of a sentence and exit")
    ap.add_argument("--only", nargs="+", metavar="NN", help="report violations in these module numbers only")
    ap.add_argument("--pairs", type=Path, metavar="ONTOLOGY_DIR",
                    help="print the literal-rule statement/term pairs of a module directory and exit")
    ap.add_argument("--matcher", choices=sorted(MATCHERS), default="strong")
    ap.add_argument("--ontology", type=Path, metavar="DIR",
                    help="check the modules in DIR instead (never writes; INDEX.md there is compared, not written)")
    ap.add_argument("--primary-only", action="store_true", help="with --pairs: ignore restatements")
    ap.add_argument("--proof-hash", action="store_true", help="print the completion proof sources hash")
    ap.add_argument("--system-terms", action="store_true",
                    help="report (not gate) uses of SYS glossary terms outside module SYS")
    a = ap.parse_args()
    if a.grade:
        print(f"{fk_grade(a.grade):.2f}")
        return 0
    if a.proof_hash:
        print(sources_hash(proof_sources(COMPLETION / "proofs"), COMPLETION))
        return 0
    if a.pairs:
        errors: List[str] = []
        modules, by_id = load_modules(a.pairs, errors)
        pairs = scope_pairs(modules, by_id, a.matcher, a.primary_only)
        for s, t in sorted(pairs):
            print(f"{s}\t{t}")
        print(f"{len(pairs)} statement/term pairs in {len({s for s, _ in pairs})} statements")
        return 1 if pairs or errors else 0
    if a.system_terms:
        return system_terms()
    if a.differential:
        return differential()
    if a.self_test:
        return self_test()
    if a.ontology:
        ctx = default_ctx()
        ctx.ontology = a.ontology.resolve()
        return run(ctx, True, a.only)
    return run(default_ctx(), a.check, a.only)


if __name__ == "__main__":
    sys.exit(main())
