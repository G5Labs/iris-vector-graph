#!/usr/bin/env python3
"""Link TLA+/TLC state machines into ontology metadata and tag linked statements.

Usage: python3 link_verification.py [--dry-run] [--verification-dir DIR] ONTOLOGY_DIR

The verification folder defaults to `TLA_verification/` beside ONTOLOGY_DIR, as in
`.g5/ontology/` and `.g5/TLA_verification/` (see ../TLC/setup_foundation.md#prepare-material-for-the-viewer).

For each `models/<concern>/manifest.json`, every `ontology_ids` entry is resolved to a
statement by its ID or an alias anchor (an extra anchor line directly above the
statement's own anchor). A statement whose metadata has no link into that concern's
folder gets one on a `State machines:` line at the end of its metadata entry.

A statement whose metadata then links a state machine with a manifest and a recorded
run gets the `design-verified` tag, by the same test as the ontology viewer: a
recorded run is a row of `results/index.jsonl` whose `concern` is the folder name and
that has a `label` and an `outcome`. A single weaker verification tag
(`test-coverage`, `manual-check-review`) is replaced; `implementation-verified` is
kept.

Nothing else changes: no link or tag is removed, statement prose is untouched, and
outcomes and freshness are not judged. Unknown or duplicate IDs, conflicting tags and
tag-like bullets that the strict tag rule does not recognize are reported and left as
they are, never guessed.

Exit status: 0 on success; with --dry-run, 1 when changes would be made; 2 on usage
or input errors.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from urllib.parse import quote, unquote

MARKER = re.compile(r"^\[([IDQ]) · ([A-Za-z0-9][A-Za-z0-9._-]*)\]$")
# The statement parsers' anchor rule (`CURRENT_ANCHOR` in the viewer).
ANCHOR = re.compile(r"""^<a\s+(?:id|name)=["']([^"']+)["']\s*></a>$""")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*#*[ \t]*$")
# Link destinations, including unencoded spaces as the viewer accepts them.
LINK = re.compile(r"\]\((?:<([^>\n]*)>|([^)\n]*))\)")
CODE_SPAN = re.compile(r"(`+).*?\1")
VERIFICATION_TAGS = ("test-coverage", "manual-check-review", "design-verified", "implementation-verified")
WEAKER_TAGS = ("test-coverage", "manual-check-review")
STRICT_TAG_BULLET = re.compile(r"^(\s*[-*+]\s+)(" + "|".join(VERIFICATION_TAGS) + r")\s*$")
TAG_LIKE_BULLET = re.compile(r"^\s*[-*+]\s+`?(" + "|".join(VERIFICATION_TAGS) + r")\b")
PROVENANCE_BULLET = re.compile(r"^\s*[-*+]\s+`?(human-provided|human-verified|agent|uncertain)\b")
BLOCK_START = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s|^ {0,3}(?:#|>|```|~~~)")
STATE_MACHINES = "State machines:"


class InputError(Exception):
    """An input the helper cannot read; reported with exit status 2."""


@dataclass
class Statement:
    id: str
    path: Path
    aliases: list[str] = field(default_factory=list)


@dataclass
class OntologyFile:
    path: Path
    lines: list[str]
    # `ends[i]` is the line ending after `lines[i]`; the last line has none.
    ends: list[str]
    newline: str
    statements: list[Statement] = field(default_factory=list)
    # Statement ID -> (first line index of the entry body, end line index exclusive).
    entries: dict[str, tuple[int, int]] = field(default_factory=dict)
    changed: bool = False


@dataclass
class Concern:
    name: str
    folder: Path
    title: str
    ontology_ids: list[str]
    has_run: bool = False


@dataclass
class Report:
    links_added: list[tuple[str, str]] = field(default_factory=list)
    tagged: list[str] = field(default_factory=list)
    replaced: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.links_added or self.tagged or self.replaced)


def fenced_lines(lines: list[str], start: int, end: int) -> set[int]:
    """Indices of lines in or delimiting fenced code blocks."""
    inside: set[int] = set()
    fence: str | None = None
    for index in range(start, end):
        match = FENCE.match(lines[index])
        if fence is None:
            if match:
                fence = match.group(1)
                inside.add(index)
            continue
        inside.add(index)
        if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not lines[index].strip()[len(match.group(1)):].strip():
            fence = None
    return inside


def read_ontology(path: Path) -> OntologyFile:
    try:
        raw = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise InputError(f"{path}: not UTF-8 text ({error})") from error
    pieces = re.split(r"(\r\n|\n)", raw)
    lines, ends = pieces[0::2], pieces[1::2]
    newline = "\r\n" if ends.count("\r\n") > ends.count("\n") else "\n"
    doc = OntologyFile(path=path, lines=lines, ends=ends, newline=newline)
    code = fenced_lines(lines, 0, len(lines))
    footer = None
    for index, line in enumerate(lines):
        if index in code:
            continue
        heading = HEADING.match(line)
        if heading and len(heading.group(1)) == 2 and (heading.group(2) or "").strip() == "Metadata":
            footer = index
            break
        found = MARKER.match(line.strip())
        if not found:
            continue
        anchors: list[str] = []
        back = index - 1
        while back >= 0:
            text = lines[back].strip()
            if not text:
                back -= 1
                continue
            anchor = ANCHOR.match(text)
            if not anchor:
                break
            anchors.insert(0, anchor.group(1))
            back -= 1
        statement = Statement(id=found.group(2), path=path)
        if anchors and anchors[-1] == statement.id:
            statement.aliases = anchors[:-1]
        doc.statements.append(statement)
    if footer is not None:
        current: str | None = None
        start = 0
        for index in range(footer + 1, len(lines) + 1):
            line = lines[index] if index < len(lines) else None
            heading = HEADING.match(line) if line is not None and index not in code else None
            if line is None or (heading and len(heading.group(1)) <= 3):
                if current is not None:
                    doc.entries.setdefault(current, (start, index))
                current = None
                if heading and len(heading.group(1)) == 3:
                    current = (heading.group(2) or "").strip()
                    start = index + 1
                if line is not None and heading and len(heading.group(1)) < 3:
                    break
    return doc


def recorded_concerns(verification: Path, report: Report) -> set[str]:
    """Concerns with a readable run index row: `concern`, `label` and `outcome`."""
    index = verification / "results" / "index.jsonl"
    concerns: set[str] = set()
    if not index.is_file():
        return concerns
    try:
        text = index.read_bytes().decode("utf-8").lstrip("﻿")
    except UnicodeDecodeError as error:
        report.notes.append(f"{index}: not UTF-8 text ({error}); no runs read")
        return concerns
    malformed = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(row, dict) and all(isinstance(row.get(key), str) and row[key] for key in ("concern", "label", "outcome")):
            concerns.add(row["concern"])
        else:
            malformed += 1
    if malformed:
        report.notes.append(f"{index}: {malformed} run index row(s) without concern, label and outcome ignored")
    return concerns


def humanize(name: str) -> str:
    words = re.sub(r"[-_]+", " ", name).strip()
    return words[:1].upper() + words[1:]


def read_concerns(verification: Path, report: Report) -> list[Concern]:
    models = verification / "models"
    if not models.is_dir():
        return []
    recorded = recorded_concerns(verification, report)
    concerns = []
    for folder in sorted(p for p in models.iterdir() if p.is_dir()):
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            continue
        concern = Concern(
            name=folder.name,
            folder=folder.resolve(),
            title=humanize(folder.name),
            ontology_ids=[],
            has_run=folder.name in recorded,
        )
        concerns.append(concern)
        # An unreadable manifest still counts as found, as in the viewer; it
        # just names no statements.
        try:
            manifest = json.loads(manifest_path.read_bytes().decode("utf-8").lstrip("﻿"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            report.notes.append(f"{manifest_path}: unreadable manifest ({error})")
            continue
        if not isinstance(manifest, dict):
            report.notes.append(f"{manifest_path}: manifest is not a JSON object")
            continue
        ids = manifest.get("ontology_ids", [])
        if not isinstance(ids, list):
            report.notes.append(f"{manifest_path}: ontology_ids is not a list")
            ids = []
        title = manifest.get("title")
        if isinstance(title, str) and title.strip():
            concern.title = title.strip()
        concern.ontology_ids = [i for i in ids if isinstance(i, str)]
    return concerns


def destinations(doc: OntologyFile, entry: tuple[int, int]) -> list[str]:
    """Link destinations in a metadata entry, outside code."""
    code = fenced_lines(doc.lines, entry[0], entry[1])
    found = []
    for index in range(entry[0], entry[1]):
        if index in code:
            continue
        for angle, plain in LINK.findall(CODE_SPAN.sub("", doc.lines[index])):
            raw = (angle or re.sub(r'\s+"[^"]*"$', "", plain)).strip()
            if raw:
                found.append(raw)
    return found


def candidates(doc: OntologyFile, destination: str, roots: tuple[Path, ...]) -> list[Path]:
    """Paths a relative link may mean, in the viewer's order: as authored, then
    from the repository root and from `.g5`."""
    path = unquote(destination.split("#", 1)[0].split("?", 1)[0])
    if not path or re.match(r"^[a-z][a-z0-9+.-]*:", destination, re.I) or destination.startswith("//"):
        return []
    found = [Path(os.path.normpath(doc.path.parent / path))]
    parts = path.split("/")
    while parts and parts[0] in ("", ".", ".."):
        parts.pop(0)
    if parts:
        found += [Path(os.path.normpath(root / "/".join(parts))) for root in roots]
    return found


def linked_concerns(doc: OntologyFile, entry: tuple[int, int], models: Path, concerns: dict[str, Concern], roots: tuple[Path, ...]) -> list[Concern]:
    """Concerns whose folder holds a target linked from the metadata entry."""
    found: list[Concern] = []
    for destination in destinations(doc, entry):
        for target in candidates(doc, destination, roots):
            try:
                parts = target.relative_to(models).parts
            except ValueError:
                continue
            concern = concerns.get(parts[0]) if parts else None
            if concern and concern not in found:
                found.append(concern)
    return found


def entry_insert(doc: OntologyFile, statement_id: str, at: int, new_lines: list[str]) -> None:
    if at < len(doc.lines):
        doc.ends[at:at] = [doc.newline] * len(new_lines)
    else:
        doc.ends.extend([doc.newline] * len(new_lines))
    doc.lines[at:at] = new_lines
    doc.changed = True
    shift = len(new_lines)
    for key, (start, end) in list(doc.entries.items()):
        if start > at or (start == at and key != statement_id):
            doc.entries[key] = (start + shift, end + shift)
        elif end >= at:
            doc.entries[key] = (start, end + shift)


def add_link(doc: OntologyFile, statement_id: str, concern: Concern) -> None:
    start, end = doc.entries[statement_id]
    relative = PurePosixPath(os.path.relpath(concern.folder / "manifest.json", doc.path.parent.resolve()).replace(os.sep, "/"))
    title = concern.title.replace("[", "\\[").replace("]", "\\]")
    # Encoded, so a folder name with spaces reads back as the same link.
    link = f"[{title}]({quote(str(relative), safe='/._-~')})"
    for index in range(start, end):
        if doc.lines[index].startswith(STATE_MACHINES):
            doc.lines[index] = doc.lines[index].rstrip() + f"; {link}"
            doc.changed = True
            return
    last = end
    while last > start and not doc.lines[last - 1].strip():
        last -= 1
    entry_insert(doc, statement_id, last, ["", f"{STATE_MACHINES} {link}"])


def tag_design_verified(doc: OntologyFile, statement_id: str, report: Report) -> None:
    start, end = doc.entries[statement_id]
    lines = doc.lines
    code = fenced_lines(lines, start, end)
    strict = [(i, m) for i in range(start, end) if i not in code for m in [STRICT_TAG_BULLET.match(lines[i])] if m]
    tags = sorted({m.group(2) for _, m in strict})
    where = f"{doc.path}: {statement_id}"
    unrecognized = [lines[i].strip() for i in range(start, end) if i not in code and TAG_LIKE_BULLET.match(lines[i]) and not STRICT_TAG_BULLET.match(lines[i])]
    for bullet in unrecognized:
        report.notes.append(f"{where}: unrecognized tag bullet {bullet!r}; left as it is")
    if unrecognized:
        return
    if len(strict) > 1:
        report.notes.append(f"{where}: more than one verification tag ({', '.join(m.group(2) for _, m in strict)}); left as it is")
        return
    if tags == ["design-verified"]:
        return
    if tags == ["implementation-verified"]:
        report.notes.append(f"{where}: kept implementation-verified")
        return
    if tags:
        index, match = strict[0]
        lines[index] = f"{match.group(1)}design-verified"
        doc.changed = True
        report.replaced.append((statement_id, match.group(2)))
        return
    at = None
    for i in range(start, end):
        if i not in code and PROVENANCE_BULLET.match(lines[i]):
            at = i + 1
            # Keep the bullet's continuation lines, indented or not, together.
            while at < end and lines[at].strip() and not BLOCK_START.match(lines[at]):
                at += 1
            break
    if at is not None:
        entry_insert(doc, statement_id, at, ["- design-verified"])
    else:
        first = start
        while first < end and not lines[first].strip():
            first += 1
        new = ["- design-verified"]
        if first < end and not re.match(r"^\s*[-*+]\s", lines[first]):
            new.append("")
        entry_insert(doc, statement_id, first, new)
    report.tagged.append(statement_id)


def write_atomic(doc: OntologyFile) -> None:
    text = "".join(line + end for line, end in zip(doc.lines, doc.ends + [""]))
    # Through a symlink, the file it points to is replaced.
    target = doc.path.resolve()
    handle, temp = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(text.encode("utf-8"))
        os.chmod(temp, target.stat().st_mode & 0o777)
        os.replace(temp, target)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def run(ontology: Path, verification: Path, dry_run: bool) -> Report:
    report = Report()
    docs = [read_ontology(p) for p in sorted(ontology.rglob("*.g5.md")) if not any(part.startswith(".") for part in p.relative_to(ontology).parts)]
    # The viewer's fallbacks: the repository root, then the `.g5` folder.
    g5 = ontology.parent if ontology.parent.name == ".g5" else None
    roots = (g5.parent, g5) if g5 else (ontology.parent,)
    owners: dict[str, list[tuple[OntologyFile, Statement]]] = {}
    for doc in docs:
        for statement in doc.statements:
            owners.setdefault(statement.id, []).append((doc, statement))
    duplicates = {sid for sid, found in owners.items() if len(found) > 1}
    for sid in sorted(duplicates):
        report.notes.append(f"duplicate statement ID {sid!r} in " + ", ".join(str(d.path) for d, _ in owners[sid]))
    by_id = {sid: found[0] for sid, found in owners.items() if sid not in duplicates}
    aliases: dict[str, str] = {}
    ambiguous: set[str] = set()
    for sid, (_, statement) in by_id.items():
        for alias in statement.aliases:
            if alias in by_id or alias in aliases or alias in ambiguous:
                report.notes.append(f"alias {alias!r} of {sid!r} is ambiguous; ignored")
                aliases.pop(alias, None)
                ambiguous.add(alias)
                continue
            aliases[alias] = sid
    concerns = read_concerns(verification, report)
    models = verification / "models"
    by_name = {concern.name: concern for concern in concerns}
    for concern in concerns:
        for raw in concern.ontology_ids:
            sid = raw if raw in by_id else aliases.get(raw)
            if sid is None:
                report.notes.append(f"{concern.name}: unknown ontology ID {raw!r}")
                continue
            doc, _ = by_id[sid]
            if sid not in doc.entries:
                report.notes.append(f"{doc.path}: {sid}: no metadata entry")
                continue
            if concern in linked_concerns(doc, doc.entries[sid], models, by_name, roots):
                continue
            add_link(doc, sid, concern)
            report.links_added.append((sid, concern.name))
    for sid, (doc, _) in sorted(by_id.items()):
        if sid not in doc.entries:
            continue
        linked = linked_concerns(doc, doc.entries[sid], models, by_name, roots)
        if any(c.has_run for c in linked):
            tag_design_verified(doc, sid, report)
    if not dry_run:
        for doc in docs:
            if doc.changed:
                write_atomic(doc)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ontology", type=Path, help="ontology directory, such as .g5/ontology")
    parser.add_argument("--verification-dir", type=Path, help="TLA+/TLC folder (default: TLA_verification beside the ontology)")
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing; exit 1 if any")
    args = parser.parse_args(argv)
    ontology = args.ontology
    if not ontology.is_dir():
        print(f"error: {ontology} is not a directory", file=sys.stderr)
        return 2
    verification = args.verification_dir or ontology.parent / "TLA_verification"
    if not (verification / "models").is_dir():
        print(f"error: {verification}/models not found", file=sys.stderr)
        return 2
    try:
        report = run(ontology.resolve(), verification.resolve(), args.dry_run)
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    verb = "Would add" if args.dry_run else "Added"
    for sid, concern in report.links_added:
        print(f"{verb} link: {sid} -> {concern}")
    for sid in report.tagged:
        print(f"{verb} design-verified: {sid}")
    for sid, old in report.replaced:
        print(f"{'Would replace' if args.dry_run else 'Replaced'} {old} with design-verified: {sid}")
    for note in report.notes:
        print(f"Note: {note}")
    statements = len({sid for sid, _ in report.links_added})
    print(
        f"{len(report.links_added)} link(s) on {statements} statement(s); "
        f"{len(report.tagged)} tagged; {len(report.replaced)} replaced; {len(report.notes)} note(s)."
    )
    return 1 if args.dry_run and report.changed else 0


if __name__ == "__main__":
    sys.exit(main())
