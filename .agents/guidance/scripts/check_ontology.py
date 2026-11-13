#!/usr/bin/env python3
"""Read-only structural checks for the Markdown format in ../ontology-format.md.

Pass an ontology directory (only its contract/index Markdown belongs there), or
explicit ontology files. --ontology-root adds that whole directory to the scan,
for example to check global ID uniqueness while working on individual files.
Linked evidence is checked for existence/Markdown anchors, never as ontology.

This is a small Markdown reader, not a Markdown renderer or a semantic validator.
It handles ATX/Setext headings, fenced examples, inline/reference links, escaped
or balanced destination parentheses, angle destinations, heading/HTML anchors and
source-line references. Blocks use explicit anchors within natural sections;
shared evidence summaries may precede the per-block metadata entries.
Indented code, HTML-rendered Markdown and custom heading-ID extensions are not
interpreted. Use fenced examples and ordinary Markdown headings in ontology.
No source, links or network resources are modified or fetched.

Writing warnings cover the mechanical parts of the writing rules in
../ontology-examples.md: more than three sentences in a statement's text outside
its bullets or in one bullet, more than ten bullets in a statement, issue/PR/bug references in statement prose, and a dotted-ID level that no
block defines. They do not change the exit status. The ID-level check needs every
defining page in the scan, so pass the whole ontology or --ontology-root.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit


BLOCK = re.compile(r"^\[([IDQ]) · ([^\s\[\]]+)\]$")
BLOCK_ANCHOR = re.compile(r'''^\s*<a\s+(?:id|name)\s*=\s*(["'])(.*?)\1\s*>\s*</a>\s*$''', re.I)
POSSIBLE_BLOCK = re.compile(
    r"^\s*(?:(?:>|[-+*]|\#{1,6})\s+|\*\*|__)*"
    r"(?:\[{1,2}[IDQ]\d*(?=$|[\s·:.\]\-])|\[\w+\s*·|[IDQ]\s*·)"
)
ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?)|[ \t]*)$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
REFERENCE = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(.*)$")
TAGS = {"agent", "human-provided", "human-verified", "uncertain"}
MAX_SENTENCES = 3
MAX_BULLETS = 10
# Mirrors the Files-view preview-deferral threshold in
# frontend/src/components/files/FileView.tsx (1024 * 1024). Above it the reader
# sees a "Load preview" prompt instead of the rendered page. FileView measures
# JavaScript string length (UTF-16 code units), so this check does too.
MAX_FILE_UTF16 = 1024 * 1024
LIST_ITEM = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
ABBREVIATIONS = {"e.g", "i.e", "etc", "vs", "cf", "approx", "incl"}
PROVENANCE = re.compile(
    r"(?<![\w/&])#\d+\b"
    r"|\b[\w.-]+/[\w.-]+#\d+\b"
    r"|\b(?:PRs?|[Pp]ull requests?|[Ii]ssues?|[Bb]ugs?)\s+#?\d+\b"
)
TRACKER_URL = re.compile(r"\bhttps?://\S+/(?:issues|pull)/\d+\b")


@dataclass(frozen=True)
class Issue:
    path: Path
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.code}: {self.message}"


@dataclass
class Result:
    files: list[Path] = field(default_factory=list)
    blocks: int = 0
    issues: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)


@dataclass(frozen=True)
class Heading:
    start: int
    end: int
    level: int
    title: str


def visible_lines(text: str) -> list[str]:
    """Keep line numbers, masking fenced code and HTML comments."""
    lines = []
    fence = None
    comment = False
    for raw in text.splitlines():
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", raw):
                fence = None
            lines.append("")
            continue
        # Comments can precede text on the same line; preserve its column.
        parts = []
        pos = 0
        while pos < len(raw):
            if comment:
                end = raw.find("-->", pos)
                if end < 0:
                    parts.append(" " * (len(raw) - pos))
                    pos = len(raw)
                else:
                    parts.append(" " * (end + 3 - pos))
                    pos, comment = end + 3, False
            else:
                start = raw.find("<!--", pos)
                if start < 0:
                    parts.append(raw[pos:])
                    pos = len(raw)
                else:
                    parts.append(raw[pos:start])
                    pos, comment = start, True
        line = "".join(parts)
        match = FENCE.match(line)
        if match and not (match[1][0] == "`" and "`" in match[2]):
            fence = (match[1][0], len(match[1]))
            line = ""
        lines.append(line)
    return lines


def headings(lines: list[str]) -> list[Heading]:
    found = []
    for i, line in enumerate(lines):
        match = ATX.match(line)
        if match:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", match[2] or "").strip()
            found.append(Heading(i + 1, i + 1, len(match[1]), title))
        elif i and re.fullmatch(r" {0,3}(?:=+|-+)[ \t]*", line) and lines[i - 1].strip():
            # Setext headings may occupy a paragraph of more than one line.
            start = i - 1
            if ATX.match(lines[start]) or POSSIBLE_BLOCK.match(lines[start]):
                continue
            while start and lines[start - 1].strip() and not ATX.match(lines[start - 1]):
                if POSSIBLE_BLOCK.match(lines[start - 1]) or re.match(r"^\s*[-+*>] ", lines[start - 1]):
                    break
                start -= 1
            title = " ".join(part.strip() for part in lines[start:i])
            found.append(Heading(start + 1, i + 1, 1 if line.lstrip().startswith("=") else 2, title))
    return found


def mask_inline_code(text: str) -> str:
    """Mask matched backtick spans without shifting offsets or newlines."""
    chars = list(text)
    for match in re.finditer(r"(`+)(?!`)(.*?)(?<!`)\1(?!`)", text, re.S):
        for i in range(match.start(), match.end()):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def unescape_markdown(text: str) -> str:
    return unescape(re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", text))


def slug(title: str) -> str:
    code = []

    def save_code(match: re.Match[str]) -> str:
        code.append(match[2])
        return f"\x00{len(code) - 1}\x00"

    title = re.sub(r"(`+)(?!`)(.*?)(?<!`)\1(?!`)", save_code, title)
    title = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", title)
    title = re.sub(r"!?\[([^\]]*)\]\[[^\]]*\]", r"\1", title)
    title = re.sub(r"<[^>]*>", "", title)
    title = re.sub(r"(?<!\w)(__?)(?=\S)(.+?)(?<=\S)\1(?!\w)", r"\2", title)
    title = re.sub(r"\x00(\d+)\x00", lambda match: code[int(match[1])], title)
    title = unescape_markdown(title).lower()
    # Formatting punctuation is absent from GitHub-style heading anchors.
    return "".join(
        "-" if ch.isspace() else ch
        for ch in title
        if ch.isspace() or ch in "_-" or unicodedata.category(ch)[0] in "LNM"
    )


def anchors(text: str) -> set[str]:
    lines = visible_lines(text)
    result = set()
    for heading in headings(lines):
        base = slug(heading.title)
        candidate, count = base, 0
        while candidate in result:
            count += 1
            candidate = f"{base}-{count}"
        result.add(candidate)
    for line in lines:
        for tag in re.findall(r"<[^>]+>", mask_inline_code(line)):
            for match in re.finditer(r"\b(?:id|name)\s*=\s*([\"'])(.*?)\1", tag, re.I):
                result.add(unescape(match[2]))
    return result


def tag_set(lines: list[str]) -> set[str]:
    """Read exact tag prefixes with optional terminal period or delimited provenance."""
    result = set()
    names = "(?:" + "|".join(re.escape(tag) for tag in sorted(TAGS)) + ")"
    token = rf"(?:{names}|`{names}`)"
    prefix = rf"\s*[-+*]\s+({token}(?:\s*[,;·]\s*{token})*)"
    for line in lines:
        match = re.match(prefix + r"(?:\s*\.?\s*$|\s+[—–]\s+|\s*:\s+)", line)
        if match:
            result.update(part.strip().strip("`") for part in re.split(r"[,;·]", match[1]))
    return result


def substantive(lines: list[str]) -> bool:
    return any(line.strip().strip("-+* ") for line in lines if not BLOCK_ANCHOR.fullmatch(line))


def check_structure(path: Path, text: str, result: Result, seen: dict[str, tuple[Path, int]]) -> None:
    lines = visible_lines(text)
    hs = headings(lines)
    footers = [heading for heading in hs if heading.title == "Metadata"]
    for heading in footers:
        if heading.level != 2 or heading.start != heading.end:
            result.issues.append(Issue(path, heading.start, "metadata-heading", "the footer must use '## Metadata'"))
    if len(footers) > 1:
        result.issues.append(Issue(path, footers[1].start, "metadata-duplicate", "only one Metadata footer is permitted"))
    footer = footers[0].start if footers else len(lines) + 1
    body = []
    previous = 0
    defined_labels = {reference_key(match[1]) for line in lines if (match := REFERENCE.match(line))}
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        match = BLOCK.fullmatch(stripped)
        inline = re.sub(r"^(?:(?:>|[-+*]|\#{1,6})\s+|\*\*|__)*", "", stripped)
        ordinary_link = (
            REFERENCE.match(line)
            or re.match(r"^\[[IDQ]\](?:\(|\[)", inline)
            or (re.fullmatch(r"\[([IDQ])\]", inline) and reference_key(inline[1:-1]) in defined_labels)
        )
        if not match and POSSIBLE_BLOCK.match(line) and not ordinary_link:
            result.issues.append(Issue(path, number, "block-syntax", "expected a standalone '[I · stable-id]', '[D · stable-id]' or '[Q · stable-id]'"))
        if match:
            kind, stable_id = match.groups()
            result.blocks += 1
            if line != line.lstrip():
                result.issues.append(Issue(path, number, "block-syntax", "block markers must start at column one"))
            if number > footer:
                result.issues.append(Issue(path, number, "block-placement", "a commitment cannot occur inside the Metadata footer"))
            else:
                body.append((stable_id, kind, number))
            anchor = BLOCK_ANCHOR.fullmatch(lines[previous - 1]) if previous else None
            if not anchor or unescape(anchor[2]) != stable_id or previous >= footer:
                result.issues.append(Issue(path, number, "block-anchor", "each block must follow a matching explicit anchor (blank lines are allowed)"))
            if stable_id in seen:
                other, other_line = seen[stable_id]
                result.issues.append(Issue(path, number, "duplicate-id", f"{stable_id!r} already occurs at {other}:{other_line}"))
            else:
                seen[stable_id] = (path, number)
        if stripped:
            previous = number
    for stable_id, _, number in body:
        boundary = min([heading.start for heading in hs if heading.start > number] + [n for _, _, n in body if n > number] + [len(lines) + 1])
        if not substantive(lines[number:boundary - 1]):
            result.issues.append(Issue(path, number, "block-empty", f"{stable_id!r} has no commitment body"))
    if body and not footers:
        result.issues.append(Issue(path, body[-1][2], "metadata-missing", "commitments require a final '## Metadata' footer"))
        return
    entries = [heading for heading in hs if heading.start > footer and heading.level == 3]
    for heading in hs:
        if heading.start > footer and heading.level <= 2:
            result.issues.append(Issue(path, heading.start, "footer-position", "the Metadata footer must be the final top-level section"))
    body_ids = [stable_id for stable_id, _, _ in body]
    entry_ids = [heading.title for heading in entries]
    if body_ids != entry_ids:
        result.issues.append(Issue(path, min(footer, len(lines) or 1), "metadata-order", "metadata IDs must match commitment IDs exactly, once each and in body order"))
    for stable_id, _, number in body:
        if stable_id not in entry_ids:
            result.issues.append(Issue(path, number, "metadata-missing", f"no metadata entry for {stable_id!r}"))
    seen_entries = set()
    for i, entry in enumerate(entries):
        stable_id = entry.title
        if stable_id in seen_entries:
            result.issues.append(Issue(path, entry.start, "metadata-duplicate", f"duplicate metadata for {stable_id!r}"))
        seen_entries.add(stable_id)
        if stable_id not in body_ids:
            result.issues.append(Issue(path, entry.start, "metadata-extra", f"no commitment owns metadata {stable_id!r}"))
        end = entries[i + 1].start - 1 if i + 1 < len(entries) else len(lines)
        content = lines[entry.end:end]
        if not substantive(content):
            result.issues.append(Issue(path, entry.start, "metadata-empty", f"{stable_id!r} has empty metadata"))
        if any(item_id == stable_id and kind == "Q" for item_id, kind, _ in body) and "uncertain" not in tag_set(content):
            result.issues.append(Issue(path, entry.start, "q-uncertain", f"Q {stable_id!r} requires an explicit 'uncertain' metadata tag"))


def statement_units(lines: list[str], start: int, end: int) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Split a block body into its prose paragraphs and its list items (with continuations)."""
    units: list[tuple[int, bool, list[str]]] = []
    blank = True
    for number in range(start, end):
        line = lines[number - 1]
        stripped = line.strip()
        if not stripped or BLOCK_ANCHOR.fullmatch(line) or stripped.startswith("|"):
            blank = True
            continue
        text = re.sub(r"^\s*(?:>\s*)+", "", line)
        item = bool(LIST_ITEM.match(text))
        in_item = bool(units) and units[-1][1]
        if item:
            units.append((number, True, [LIST_ITEM.sub("", text, count=1)]))
        elif (units and not blank) or (in_item and line[:1].isspace()):
            units[-1][2].append(text.strip())
        else:
            units.append((number, False, [text.strip()]))
        blank = False
    paragraphs = [(number, " ".join(parts)) for number, item, parts in units if not item]
    items = [(number, " ".join(parts)) for number, item, parts in units if item]
    return paragraphs, items


def prose(text: str) -> str:
    """Readable text of a statement unit: no code spans, link targets or HTML."""
    text = mask_inline_code(text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"!?\[([^\]]*)\]\[[^\]]*\]", r"\1", text)
    return re.sub(r"<[^>]*>", " ", text)


def sentence_count(text: str) -> int:
    """Count sentence ends, skipping the final dot of known abbreviations and initials."""
    count, rest = 0, 0
    for match in re.finditer(r"[.!?]+[\"'”’)\]*_]*(?=\s|$)", text):
        word = re.search(r"([\w.]*)$", text[:match.start()])[1].lower()
        if match[0].startswith(".") and (word in ABBREVIATIONS or re.fullmatch(r"\w", word)):
            continue
        count, rest = count + 1, match.end()
    return count + bool(re.search(r"\w", text[rest:]))


def check_writing(path: Path, text: str, result: Result) -> None:
    """Warn about long statements and bullets, too many bullets and provenance in statement prose."""
    lines = visible_lines(text)
    hs = headings(lines)
    footer = next((heading.start for heading in hs if heading.title == "Metadata"), len(lines) + 1)
    markers = [number for number, line in enumerate(lines, 1) if number < footer and BLOCK.fullmatch(line.strip())]
    for number in markers:
        end = min([h.start for h in hs if h.start > number] + [n for n in markers if n > number] + [footer])
        paragraphs, items = statement_units(lines, number + 1, end)
        sentences = sum(sentence_count(prose(unit)) for _, unit in paragraphs)
        if sentences > MAX_SENTENCES:
            result.warnings.append(Issue(path, paragraphs[0][0], "writing-length", f"{sentences} sentences in the statement outside its bullets; keep at most {MAX_SENTENCES}"))
        if len(items) > MAX_BULLETS:
            result.warnings.append(Issue(path, items[MAX_BULLETS][0], "writing-bullets", f"{len(items)} bullets in one statement; keep at most {MAX_BULLETS} or define a new concept with its own statements"))
        for first, unit in items:
            sentences = sentence_count(prose(unit))
            if sentences > MAX_SENTENCES:
                result.warnings.append(Issue(path, first, "writing-length", f"{sentences} sentences in one bullet; keep at most {MAX_SENTENCES}"))
        for first, unit in paragraphs + items:
            plain = prose(unit)
            reference = PROVENANCE.search(plain) or TRACKER_URL.search(mask_inline_code(unit))
            if reference:
                result.warnings.append(Issue(path, first, "writing-provenance", f"{reference[0].strip()!r} cites provenance in statement prose; move it to metadata"))


def check_file_size(path: Path, text: str, result: Result) -> None:
    """Warn when a page exceeds the platform render size and should be split."""
    # UTF-16 code units, matching FileView's JavaScript string-length check: a
    # supplementary character counts as two, as it does in the browser.
    utf16 = len(text.encode("utf-16-le")) // 2
    if utf16 > MAX_FILE_UTF16:
        result.warnings.append(Issue(path, 1, "writing-file-size", f"{utf16} UTF-16 code units exceeds the {MAX_FILE_UTF16} render limit; split into files aligned with the page's abstractions"))


def check_id_levels(result: Result, seen: dict[str, tuple[Path, int]]) -> None:
    """Every dotted-ID level below the top-level name needs its own defining block."""
    reported = set()
    for stable_id, (path, number) in sorted(seen.items(), key=lambda item: (str(item[1][0]), item[1][1])):
        parts = stable_id.split(".")
        for size in range(2, len(parts)):
            level = ".".join(parts[:size])
            if level not in seen and level not in reported:
                reported.add(level)
                result.warnings.append(Issue(path, number, "writing-id-level", f"no block defines the ID level {level!r} used by {stable_id!r}"))


def destination(text: str, start: int) -> tuple[str, int]:
    """Read a Markdown destination; return the raw destination and next offset."""
    pos = start
    while pos < len(text) and text[pos].isspace():
        pos += 1
    begin = pos
    if pos < len(text) and text[pos] == "<":
        pos += 1
        begin = pos
        while pos < len(text) and text[pos] != ">":
            if text[pos] in "\r\n<":
                raise ValueError("invalid angle-bracket link destination")
            pos += 2 if text[pos] == "\\" else 1
        if pos >= len(text):
            raise ValueError("unterminated angle-bracket link destination")
        return text[begin:pos], pos + 1
    depth = 0
    while pos < len(text):
        char = text[pos]
        if char == "\\" and pos + 1 < len(text):
            pos += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if not depth:
                break
            depth -= 1
        elif char.isspace():
            break
        pos += 1
    if depth:
        raise ValueError("unbalanced parentheses in link destination")
    return text[begin:pos], pos


def after_title(text: str, pos: int) -> int:
    before = pos
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos > before and pos < len(text) and text[pos] in "\"'(":
        close = ")" if text[pos] == "(" else text[pos]
        pos += 1
        while pos < len(text) and text[pos] != close:
            pos += 2 if text[pos] == "\\" else 1
        if pos >= len(text):
            raise ValueError("unterminated link title")
        pos += 1
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return pos


def reference_key(label: str) -> str:
    return " ".join(unescape_markdown(label).split()).casefold()


def links(path: Path, text: str, issues: list[Issue]) -> list[tuple[int, str]]:
    lines = visible_lines(text)
    definitions = {}
    found = []
    for i, line in enumerate(lines):
        match = REFERENCE.match(line)
        if not match:
            continue
        raw = match[2]
        if not raw and i + 1 < len(lines):
            raw = lines[i + 1]
            lines[i + 1] = ""
        try:
            target, end = destination(raw, 0)
            if not target or after_title(raw, end) != len(raw):
                raise ValueError("invalid reference-link destination or title")
            key = reference_key(match[1])
            if key not in definitions:
                definitions[key] = target
                found.append((i + 1, target))
        except ValueError as exc:
            issues.append(Issue(path, i + 1, "link-syntax", str(exc)))
        lines[i] = ""
    body = mask_inline_code("\n".join(lines))
    pos = 0
    while pos < len(body):
        if body[pos] == "\\":
            pos += 2
            continue
        if body[pos] != "[":
            pos += 1
            continue
        start, depth = pos, 1
        pos += 1
        while pos < len(body) and depth:
            if body[pos] == "\\":
                pos += 2
                continue
            if body[pos] == "[":
                depth += 1
            elif body[pos] == "]":
                depth -= 1
            pos += 1
        if depth:
            # An ordinary unmatched '[' must not hide later real links.
            pos = start + 1
            continue
        label = body[start + 1:pos - 1]
        number = body.count("\n", 0, start) + 1
        if pos < len(body) and body[pos] == "(":
            try:
                target, end = destination(body, pos + 1)
                end = after_title(body, end)
                if end >= len(body) or body[end] != ")":
                    raise ValueError("inline link must end with ')' after its destination/title")
                found.append((number, target))
                pos = end + 1
            except ValueError as exc:
                issues.append(Issue(path, number, "link-syntax", str(exc)))
        elif pos < len(body) and body[pos] == "[":
            end = body.find("]", pos + 1)
            if end < 0:
                issues.append(Issue(path, number, "link-syntax", "unterminated reference-link label"))
                continue
            key = reference_key(body[pos + 1:end] or label)
            if key not in definitions:
                issues.append(Issue(path, number, "link-reference", f"undefined reference {key!r}"))
            pos = end + 1
        else:
            # Outer bracketed prose can contain a real inner link. Defined
            # shortcut references were already checked at their definition.
            pos = start + 1
    return found


def check_links(path: Path, text: str, result: Result, cache: dict[Path, tuple[set[str], int]]) -> None:
    for number, raw in links(path, text, result.issues):
        target = unescape_markdown(raw)
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("//"):
            continue
        try:
            parsed = urlsplit(target)
            filename = unquote(parsed.path)
            local = (path.parent / filename).resolve() if filename else path
            if not local.exists():
                result.issues.append(Issue(path, number, "link-target", f"missing local target {raw!r}"))
                continue
            fragment = unquote(parsed.fragment)
            if fragment and local.suffix.lower() == ".md" and local.is_file():
                if local not in cache:
                    linked_text = local.read_text(encoding="utf-8")
                    cache[local] = anchors(linked_text), len(linked_text.splitlines())
                known_anchors, line_count = cache[local]
                line_range = re.fullmatch(r"L(\d+)(?:-L(\d+))?", fragment)
                if fragment in known_anchors:
                    continue
                if line_range:
                    first, last = int(line_range[1]), int(line_range[2] or line_range[1])
                    if not 1 <= first <= last <= line_count:
                        result.issues.append(Issue(path, number, "link-anchor", f"invalid source-line range in {raw!r}"))
                else:
                    result.issues.append(Issue(path, number, "link-anchor", f"missing Markdown anchor in {raw!r}"))
        except (OSError, UnicodeError, ValueError) as exc:
            result.issues.append(Issue(path, number, "link-target", f"cannot inspect {raw!r}: {exc}"))


def is_misnamed_g5_ontology_page(path: Path) -> bool:
    """A plain .md file inside a .g5/ontology tree is not an ontology page."""
    parts = path.parts
    inside = any(parts[i] == ".g5" and parts[i + 1] == "ontology" for i in range(len(parts) - 2))
    return inside and not path.name.endswith(".g5.md")


def check_paths(paths: list[Path], ontology_root: Path | None = None) -> Result:
    """Collect the ontology files under the given paths and run every check over them."""
    result = Result()
    files = set()
    inputs = list(paths)
    if ontology_root is not None:
        if not ontology_root.is_dir():
            result.issues.append(Issue(ontology_root, 1, "input", "--ontology-root must be an existing ontology directory"))
        else:
            inputs.append(ontology_root)
    for item in inputs:
        try:
            item = item.resolve()
            if item.is_dir():
                selected = {path.resolve() for path in item.rglob("*") if path.is_file() and path.suffix.lower() == ".md"}
                if not selected:
                    result.issues.append(Issue(item, 1, "input", "ontology directory contains no Markdown files"))
                files.update(selected)
            elif item.is_file() and item.suffix.lower() == ".md":
                files.add(item)
            else:
                result.issues.append(Issue(item, 1, "input", "expected an existing ontology Markdown file or ontology directory"))
        except OSError as exc:
            result.issues.append(Issue(item, 1, "input", str(exc)))
    if not inputs:
        result.issues.append(Issue(Path("."), 1, "input", "provide at least one ontology path"))
    result.files = sorted(files)
    for path in result.files:
        if is_misnamed_g5_ontology_page(path):
            result.issues.append(Issue(path, 1, "ontology-file-name", "Markdown under .g5/ontology is an ontology page only when named *.g5.md; the editor and Diff Graph treat this file as an ordinary file. Rename it to .g5.md or move it out of .g5/ontology."))
    seen, cache = {}, {}
    for path in result.files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            result.issues.append(Issue(path, 1, "input", f"cannot read Markdown: {exc}"))
            continue
        check_structure(path, text, result, seen)
        check_links(path, text, result, cache)
        check_writing(path, text, result)
        check_file_size(path, text, result)
    check_id_levels(result, seen)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", type=Path, nargs="+", help="ontology root directory or explicit ontology Markdown files")
    parser.add_argument("--ontology-root", type=Path, help="also scan this complete ontology directory for cross-file ID checks")
    args = parser.parse_args(argv)
    result = check_paths(args.paths, args.ontology_root)
    for issue in result.issues:
        print(issue, file=sys.stderr)
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"Checked {len(result.files)} ontology Markdown file(s), {result.blocks} block(s): {len(result.issues)} issue(s), {len(result.warnings)} writing warning(s).")
    print("Mechanical structure/local-link checks and writing warnings only; no claim about intent, coverage, provenance truth, readability or implementation correctness.")
    return 2 if any(issue.code == "input" for issue in result.issues) else int(bool(result.issues))


if __name__ == "__main__":
    raise SystemExit(main())
