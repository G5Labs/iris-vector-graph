#!/usr/bin/env python3
"""Check the findings files that G5's viewer renders.

Usage: python3 check_findings.py TLA_VERIFICATION_DIR [ONTOLOGY_DIR] [--previous PATH|REF]

The files are `bugs_issues.md` and `design_simplification.md` in the verification
folder (see ../TLC/setup_foundation.md#prepare-material-for-the-viewer). Each entry is an anchor line, a `###`
heading and a status line, optionally followed by a `Run:` line naming the run
that first recorded it:

    <a id="bug-001"></a>
    ### Duplicate order lines bypass the receiving limit

    Severity: High · Decision: Open

    Run: Uplift 2026-10-24

The checker reports malformed entries, duplicate IDs and entries out of order.
An Open entry needs its evidence lines: `Found by:` and `Reproduced by:` in a bug,
`Comparison:` in a simplification; receipts they link must exist, and an entry
that can still change names no `Sources:`. With ONTOLOGY_DIR it also reports ontology links to entry IDs that do not exist,
links from the ontology root to the files, and entries that name an ontology
statement outside the root whose metadata does not link the entry back. With
`--previous` it reports decided entries whose text changed or that disappeared
since an earlier version: a folder holding copies of the two files taken before
editing (the owner's decisions may be uncommitted), or a Git revision.

It changes nothing. Exit status: 0 when clean, 1 when it reports anything,
2 on a usage error. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

FILES = ("bugs_issues.md", "design_simplification.md")
SEVERITIES = ("Critical", "High", "Medium", "Low", "Unranked")
DECISIONS = ("Open", "Need fix", "Defer", "Irrelevant")

ANCHOR_RE = re.compile(r'^<a id="([^"]*)"></a>\s*$')
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
STATUS_RE = re.compile(r"^Severity:[ \t]*(.*?)(?:[ \t]+·[ \t]+Decision:[ \t]*(.*?))?[ \t]*$")
DECISION_RE = re.compile(r"^(Open|Need fix|Defer|Irrelevant)(?=[ \t—–-]|$)[ \t]*(?:[—–-][ \t]*)?(.*)$")
ISSUE_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
LINK_RE = re.compile(r"\]\((?:<([^>\n]*)>|([^)\n]*))\)")


@dataclass
class Entry:
    id: str
    title: str
    level: int
    line: int
    end: int
    status_line: int | None = None
    severity: str = "Unranked"
    decision: str | None = None
    issue: tuple[str, str] | None = None
    run: str | None = None
    run_line: int | None = None
    text: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def actionable(self) -> bool:
        return self.decision is not None


@dataclass
class Issue:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def _structure_lines(lines: list[str]) -> list[bool]:
    """Whether each line can carry structure (it is outside a fenced block)."""
    usable = []
    fence: str | None = None
    for line in lines:
        match = FENCE_RE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)[0] * len(match.group(1))
                usable.append(False)
                continue
            usable.append(True)
        else:
            usable.append(False)
            stripped = line.strip()
            if match and stripped.startswith(fence) and set(stripped) <= {fence[0]}:
                fence = None
    return usable


def parse_status(entry: Entry, text: str) -> None:
    """Read an entry's severity and decision from its status line text."""
    match = STATUS_RE.match(text)
    if not match:
        entry.problems.append("the line after the heading is not a status line `Severity: …`")
        return
    raw_severity, raw_decision = match.group(1).strip(), match.group(2)
    canonical = {s.lower(): s for s in SEVERITIES}.get(raw_severity.lower())
    if canonical is None:
        entry.problems.append(f"unknown severity `{raw_severity}`; use {', '.join(SEVERITIES)}")
    else:
        entry.severity = canonical
    if raw_decision is None:
        return
    decision = DECISION_RE.match(raw_decision.strip())
    if not decision:
        entry.decision = "?"
        entry.problems.append(f"unknown decision `{raw_decision.strip()}`; agents write `Open`")
        return
    entry.decision = decision.group(1)
    rest = decision.group(2)
    link = ISSUE_LINK_RE.search(rest)
    if link:
        entry.issue = (link.group(1), link.group(2))
    if entry.decision == "Open" and rest.strip():
        entry.problems.append("an Open decision has nothing after it")
    if entry.decision in ("Need fix", "Defer") and not link:
        entry.problems.append(f"a `{entry.decision}` decision must link its issue")


def parse(text: str) -> tuple[list[Entry], list[tuple[int, str]]]:
    """Entries of a findings file, and file-level problems as (line, message)."""
    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    usable = _structure_lines(lines)
    problems: list[tuple[int, str]] = []
    starts: list[tuple[int, str, int, str]] = []
    for index, line in enumerate(lines):
        if not usable[index]:
            continue
        anchor = ANCHOR_RE.match(line)
        if not anchor:
            continue
        heading = HEADING_RE.match(lines[index + 1]) if index + 1 < len(lines) else None
        if not heading or len(heading.group(1)) < 2 or not usable[index + 1]:
            problems.append((index + 1, f"anchor `{anchor.group(1)}` is not directly followed by a heading"))
            continue
        starts.append((index, anchor.group(1), len(heading.group(1)), heading.group(2).strip()))
    entries: list[Entry] = []
    for position, (start, entry_id, level, title) in enumerate(starts):
        limit = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        end = limit
        for index in range(start + 2, limit):
            heading = HEADING_RE.match(lines[index]) if usable[index] else None
            if heading and len(heading.group(1)) <= level:
                end = index
                break
        entry = Entry(id=entry_id, title=title, level=level, line=start + 1, end=end + 1)
        entry.text = "\n".join(lines[start:end]).rstrip()
        status = next((i for i in range(start + 2, end) if lines[i].strip()), None)
        if status is not None and usable[status] and lines[status].startswith("Severity:"):
            entry.status_line = status + 1
            parse_status(entry, lines[status].strip())
            # Its own line, because a decision rewrites the end of the status line.
            after = next((i for i in range(status + 1, end) if lines[i].strip()), None)
            if after is not None and usable[after] and lines[after].startswith("Run:"):
                entry.run_line = after + 1
                label = lines[after][len("Run:"):].strip()
                if label:
                    entry.run = label
                else:
                    entry.problems.append("the `Run:` line names no run")
        else:
            entry.problems.append("missing status line `Severity: …` after the heading")
        entries.append(entry)
    return entries, problems


def check_text(path: str, text: str) -> tuple[list[Entry], list[Issue]]:
    entries, file_problems = parse(text)
    issues = [Issue(path, line, message) for line, message in file_problems]
    # A `###` heading without an anchor ends the entry above it, leaving the
    # text below outside every entry; headings inside an entry are `####`.
    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    usable = _structure_lines(lines)
    starts = {entry.line for entry in entries}
    if entries:
        for index in range(entries[0].line, len(lines)):
            heading = HEADING_RE.match(lines[index]) if usable[index] else None
            if heading and len(heading.group(1)) == 3 and index not in starts:
                issues.append(Issue(path, index + 1, f"heading `{heading.group(2).strip()}` has no anchor; an entry needs one, and headings inside an entry are `####`"))
    seen: dict[str, int] = {}
    order = {severity: rank for rank, severity in enumerate(SEVERITIES)}
    last_actionable: Entry | None = None
    first_other: Entry | None = None
    for entry in entries:
        for message in entry.problems:
            issues.append(Issue(path, entry.status_line or entry.line, message))
        if not ID_RE.match(entry.id):
            issues.append(Issue(path, entry.line, f"ID `{entry.id}` must be letters, digits, `.`, `_` or `-`"))
        if entry.id in seen:
            issues.append(Issue(path, entry.line, f"duplicate ID `{entry.id}` (first at line {seen[entry.id]})"))
        else:
            seen[entry.id] = entry.line
        if entry.level != 3:
            issues.append(Issue(path, entry.line + 1, "an entry heading is `###`"))
        if not entry.title:
            issues.append(Issue(path, entry.line + 1, "an entry heading needs a title sentence"))
        if entry.actionable:
            if first_other is not None:
                issues.append(Issue(path, entry.line, f"actionable entry `{entry.id}` comes after other entries (first: `{first_other.id}`)"))
            if last_actionable is not None and order[entry.severity] < order[last_actionable.severity]:
                issues.append(Issue(path, entry.line, f"`{entry.id}` ({entry.severity}) comes after less severe `{last_actionable.id}` ({last_actionable.severity})"))
            last_actionable = entry
        elif first_other is None:
            first_other = entry
    return entries, issues


def _link_targets(text: str) -> list[str]:
    prose_lines = [line for line, ok in zip(text.split("\n"), _structure_lines(text.split("\n"))) if ok]
    prose = re.sub(r"(`+)[\s\S]*?\1", "", "\n".join(prose_lines))
    targets = [(m.group(1) or m.group(2) or "").strip() for m in LINK_RE.finditer(prose)]
    return [re.sub(r'\s+"[^"]*"$', "", target) for target in targets]


def check_ontology_links(ontology: Path, verification: Path, ids: dict[str, set[str]]) -> list[Issue]:
    issues: list[Issue] = []
    targets = {name: (verification / name).resolve() for name in FILES}
    for page in sorted(ontology.rglob("*.g5.md")):
        text = page.read_text(encoding="utf-8")
        lines = text.split("\n")
        root = page.parent.resolve() == ontology.resolve() and page.name == "root.g5.md"
        for href in _link_targets(text):
            href = re.sub(r'\s+"[^"]*"$', "", href)
            if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith("#"):
                continue
            path, _, fragment = href.partition("#")
            path = unquote(path)
            name = Path(path).name
            if name not in FILES:
                continue
            resolved = (page.parent / path).resolve()
            if resolved != targets[name] and not path.rstrip("/").endswith(f"TLA_verification/{name}"):
                continue
            line = next((i + 1 for i, l in enumerate(lines) if href in l), 1)
            if root:
                issues.append(Issue(str(page), line, f"the ontology root links `{name}`; G5's Core Ontology panel lists it instead"))
            if fragment and fragment not in ids.get(name, set()):
                issues.append(Issue(str(page), line, f"`{name}#{fragment}` names no entry"))
    return issues


EVIDENCE = {"bugs_issues.md": ("Found by:", "Reproduced by:"), "design_simplification.md": ("Comparison:",)}
RECEIPT_RE = re.compile(r"(?:^|/)results/[^/]+/[^/]+/receipt\.json$")
SOURCES_RE = re.compile(r"^Sources?:")


def check_evidence(path: str, name: str, entries: list[Entry], verification: Path) -> list[Issue]:
    """An Open entry's evidence lines, and `Sources:` and misplaced `Run:` lines in entries that can change."""
    issues: list[Issue] = []
    for entry in entries:
        if entry.decision not in (None, "Open"):
            continue  # a decided entry keeps its text
        lines = entry.text.split("\n")
        found: dict[str, tuple[int, str]] = {}
        for offset, (line, usable) in enumerate(zip(lines, _structure_lines(lines))):
            if not usable:
                continue
            for label in ("Found by:", "Reproduced by:", "Comparison:"):
                if line.startswith(label):
                    found.setdefault(label, (entry.line + offset, line[len(label):].strip()))
            if SOURCES_RE.match(line):
                issues.append(Issue(path, entry.line + offset, f"`{entry.id}` has a `Sources:` line; link the evidence itself, not the reports the entry replaces"))
            if line.startswith("Run:") and entry.line + offset != entry.run_line:
                issues.append(Issue(path, entry.line + offset, f"`{entry.id}` has a `Run:` line away from its status line; it goes directly after it"))
        if entry.decision == "Open":
            for label in EVIDENCE.get(name, ()):
                if label not in found:
                    issues.append(Issue(path, entry.line, f"`{entry.id}` has no `{label}` line"))
        for label in ("Found by:", "Comparison:"):
            if label not in found:
                continue
            line_no, rest = found[label]
            targets = [unquote(t.partition("#")[0]) for t in _link_targets(rest)]
            for target in targets:
                if RECEIPT_RE.search(target) and not (verification / target).is_file():
                    issues.append(Issue(path, line_no, f"`{entry.id}` links a missing receipt `{target}`"))
            if label == "Comparison:" and not rest.lower().startswith("none") and not (targets and RECEIPT_RE.search(targets[0])):
                issues.append(Issue(path, line_no, f"`{entry.id}`: `Comparison:` starts with the as-built run's receipt, or is `none`"))
    return issues


MARKER_RE = re.compile(r"^\[[A-Z] · ([^\]\s]+)\]\s*$")
# Ontology anchors in the forms the ontology checker accepts.
STATEMENT_ANCHOR_RE = re.compile(r"""^\s*<a\s+(?:id|name)\s*=\s*(["'])(.*?)\1\s*>\s*</a>\s*$""", re.I)


def statement_metadata(page: Path) -> dict[str, str]:
    """Each statement's metadata entry text, under its ID and every alias anchor."""
    lines = page.read_text(encoding="utf-8").split("\n")
    usable = _structure_lines(lines)
    aliases: dict[str, str] = {}
    pending: list[str] = []
    for line, ok in zip(lines, usable):
        anchor = STATEMENT_ANCHOR_RE.match(line) if ok else None
        marker = MARKER_RE.match(line) if ok else None
        if anchor:
            pending.append(anchor.group(2))
        elif marker:
            for alias in pending:
                aliases[alias] = marker.group(1)
            aliases[marker.group(1)] = marker.group(1)
            pending = []
        elif line.strip():
            pending = []
    entries: dict[str, list[str]] = {}
    current: list[str] | None = None
    in_metadata = False
    for line, ok in zip(lines, usable):
        heading = HEADING_RE.match(line) if ok else None
        if heading and len(heading.group(1)) <= 2:
            in_metadata = heading.group(2).strip().lower() == "metadata"
            current = None
        elif heading and in_metadata and len(heading.group(1)) == 3:
            current = entries.setdefault(heading.group(2).strip(), [])
        elif current is not None:
            current.append(line)
    return {alias: "\n".join(entries.get(own, [])) for alias, own in aliases.items()}


DECIDED = ("Need fix", "Defer", "Irrelevant")


def _candidates(page: Path, href: str, ontology: Path) -> list[Path]:
    """Files a relative link may mean, in the viewer's order: as written, then
    without leading `./`, `../` and `/` from the repository root and from `.g5`."""
    path = unquote(href)
    found = [(page.parent / path).resolve()]
    parts = path.split("/")
    while parts and parts[0] in ("", ".", ".."):
        parts.pop(0)
    if parts:
        g5 = ontology.resolve().parent
        found += [(g5.parent / "/".join(parts)).resolve(), (g5 / "/".join(parts)).resolve()]
    return found


def check_back_links(
    verification: Path, ontology: Path, entries_by_file: dict[str, list[Entry]]
) -> list[Issue]:
    """Entries that name a statement whose metadata does not link them back."""
    issues: list[Issue] = []
    root = ontology.resolve()
    cache: dict[Path, dict[str, str]] = {}
    for name, entries in entries_by_file.items():
        target = (verification / name).resolve()
        for entry in entries:
            for href in _link_targets(entry.text):
                path, _, statement = href.partition("#")
                if not statement or re.match(r"^[a-z][a-z0-9+.-]*:", path, re.I):
                    continue
                page = (verification / unquote(path)).resolve()
                if page.suffixes[-2:] != [".g5", ".md"] or root not in page.parents:
                    continue
                # The root never links the findings files.
                if page == root / "root.g5.md":
                    continue
                if page not in cache:
                    cache[page] = statement_metadata(page) if page.is_file() else {}
                metadata = cache[page]
                where = f"{page.relative_to(root)}#{statement}"
                if statement not in metadata:
                    # A decided entry's text is the owner's; nothing to fix there.
                    if entry.decision in DECIDED:
                        continue
                    issues.append(Issue(str(verification / name), entry.line, f"`{entry.id}` links `{where}`, which is not a statement"))
                    continue
                linked = any(
                    target in _candidates(page, back.partition("#")[0], ontology)
                    and unquote(back.partition("#")[2]) == entry.id
                    for back in _link_targets(metadata[statement])
                )
                if not linked:
                    issues.append(Issue(str(verification / name), entry.line, f"`{entry.id}` names `{where}`, whose metadata does not link the entry back"))
    return issues


class UsageError(Exception):
    pass


def previous_text(verification: Path, name: str, previous: str) -> str | None:
    """The file's earlier text: from a folder of copies, or a Git revision."""
    folder = Path(previous)
    if folder.is_dir():
        copy = folder / name
        return copy.read_text(encoding="utf-8") if copy.is_file() else None
    try:
        subprocess.run(
            ["git", "-C", str(verification), "rev-parse", "--verify", "--quiet", f"{previous}^{{commit}}"],
            check=True, capture_output=True, text=True,
        )
        prefix = subprocess.run(
            ["git", "-C", str(verification), "rev-parse", "--show-prefix"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise UsageError(f"--previous {previous} is neither a folder nor a Git revision of this checkout")
    shown = subprocess.run(
        ["git", "-C", str(verification), "show", f"{previous}:{prefix}{name}"],
        capture_output=True, text=True,
    )
    return shown.stdout if shown.returncode == 0 else None


def check_previous(path: str, entries: list[Entry], before: str) -> list[Issue]:
    current = {entry.id: entry for entry in entries}
    issues: list[Issue] = []
    for old in parse(before)[0]:
        if old.decision not in DECIDED:
            continue
        new = current.get(old.id)
        if new is None:
            issues.append(Issue(path, 1, f"decided entry `{old.id}` was removed"))
        elif new.text != old.text:
            issues.append(Issue(path, new.line, f"decided entry `{old.id}` changed; keep its text and status line"))
    return issues


def check(verification: Path, ontology: Path | None = None, previous: str | None = None) -> list[Issue]:
    issues: list[Issue] = []
    ids: dict[str, set[str]] = {}
    entries_by_file: dict[str, list[Entry]] = {}
    for name in FILES:
        path = verification / name
        if not path.is_file():
            if previous:
                before = previous_text(verification, name, previous)
                if before is not None:
                    issues += check_previous(str(path), [], before)
            continue
        entries, found = check_text(str(path), path.read_text(encoding="utf-8"))
        issues += found
        issues += check_evidence(str(path), name, entries, verification)
        ids[name] = {entry.id for entry in entries}
        entries_by_file[name] = entries
        if previous:
            before = previous_text(verification, name, previous)
            if before is not None:
                issues += check_previous(str(path), entries, before)
    if ontology is not None:
        issues += check_ontology_links(ontology, verification, ids)
        issues += check_back_links(verification, ontology, entries_by_file)
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("verification", type=Path, help="the TLA_verification folder")
    parser.add_argument("ontology", type=Path, nargs="?", help="the ontology folder")
    parser.add_argument("--previous", metavar="PATH|REF", help="copies of the files taken before editing, or a Git revision, to compare decided entries with")
    args = parser.parse_args(argv)
    if not args.verification.is_dir():
        parser.error(f"{args.verification} is not a folder")
    if args.ontology is not None and not args.ontology.is_dir():
        parser.error(f"{args.ontology} is not a folder")
    if not args.previous and not any((args.verification / name).is_file() for name in FILES):
        print(f"{args.verification}: no {' or '.join(FILES)}")
        return 0
    try:
        issues = check(args.verification, args.ontology, args.previous)
    except UsageError as error:
        parser.error(str(error))
    for issue in issues:
        print(issue)
    print(f"{len(issues)} problem{'s' if len(issues) != 1 else ''}" if issues else "No problems found.")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
