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
import posixpath
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ONTOLOGY = ".g5/ontology"
G_TIP = "24c6b0c03e1c84cac6691de45c183fa1cf73940b"
LAST_PRE_MOVE_TABLE = "8ab0f2585"
TABLE = ".g5/Verus_verification/crosswalk/statements.tsv"
CASES = {"ledger.commit": "M03", "temporal.window.sources": "M06", "temporal.window.paging": "M08",
         "temporal.window.paging.release": "M07;M08", "structure.rebuilt.stamp": "M09", "structure.multigraph.count": "M11",
         "algorithms.op.paths.weighted": "M12", "search.embedding.width": "M14", "search.routes.no_fallback": "M14",
         "install.bulk_load.loader": "M23", "install.snapshot.routes": "J01", "install.snapshot.temporal": "J02",
         "structure.adjacency.declare": "M16;J07", "adapters.embedded.no_data": "M17", "query.values.relationship_text": "M18",
         "ledger.commit.admission": "M01", "ledger.idempotency": "M02", "structure.degree.cache.uncommitted": "M10",
         "search.embedding.other_model": "M13", "algorithms.cache": "M21", "algorithms.cache.token": "J04",
         "ledger.commit.serial": "J05", "query.compiled.fallback": "J08;M20", "query.compiled.modes": "J08",
         "ledger.readers": "M04;M05;J03"}


def block_index(pages):
    index = {}
    for path, text in pages:
        body, _, metadata = text.partition("\n## Metadata\n")
        entries = re.split(r"^### (.+)\n", metadata, flags=re.M)
        footer = dict(zip(entries[1::2], entries[2::2]))
        boundaries = list(re.finditer(
            r'^<a id="([^"]+)"></a>\n\[([IDQ]) · \1\]\n|^## .+$', body, re.M
        ))
        for position, match in enumerate(boundaries):
            if not match[1]:
                continue
            block_id = match[1]
            if block_id in index:
                raise ValueError(f"Duplicate statement {block_id} in {path}")
            end = boundaries[position + 1].start() if position + 1 < len(boundaries) else len(body)
            index[block_id] = (path, match[2], body[match.end():end].strip(), footer[block_id].strip())
    return index


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True)


def normalize_links(text, page, index):
    def resolve(match):
        link = match[2]
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:|^/", link):
            return match[0]
        path, sep, fragment = link.partition("#")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(page), path)) if path else page
        if fragment in index and target == index[fragment][0]:
            return match[1] + f"ontology:{fragment}"
        return match[1] + target + sep + fragment

    return re.sub(r"(\]\()([^)\s<>]+)(?=\s|\))", resolve, text)


def comparison(block, index):
    page, kind, body, metadata = block
    return kind, normalize_links(body, page, index), normalize_links(metadata, page, index)


def revision_index(revision):
    paths = git("ls-tree", "-r", "--name-only", revision, "--", ONTOLOGY).splitlines()
    return block_index((path, git("show", f"{revision}:{path}")) for path in paths if path.endswith(".g5.md"))


def make_rows():
    old = revision_index(G_TIP)
    previous = revision_index(LAST_PRE_MOVE_TABLE)
    published = {
        row["g_block"]: row
        for row in csv.DictReader(git("show", f"{LAST_PRE_MOVE_TABLE}:{TABLE}").splitlines(), delimiter="\t")
    }
    current = block_index(
        (page.relative_to(REPO).as_posix(), page.read_text())
        for page in sorted((REPO / ONTOLOGY).rglob("*.g5.md"))
    )
    rows = []
    for bid, block in current.items():
        page, _, _, metadata = block
        pl = re.search(r"^- Playbook:(.*)$", metadata, re.M)
        pids = sorted(set(re.findall(r"\[([A-Z]{3}-[A-Za-z0-9.]+)\]", pl.group(1)))) if pl else []
        content = comparison(block, current)
        if bid in published and bid in previous and content == comparison(previous[bid], previous):
            # Keep the published provenance for blocks that only moved. The
            # earlier generator also counted inter-block whitespace as changes.
            history = published[bid]["since 24c6b0c0"]
        elif bid not in old:
            history = "new"
        elif content == comparison(old[bid], old):
            history = "unchanged"
        else:
            history = "changed"
        if pids:
            relation = "same" if history == "unchanged" else "g-extended-from-p"
        else:
            relation = "g-only"
        rows.append([bid, ";".join(pids), relation, CASES.get(bid, ""), page, history])
    return rows


def main():
    rows = make_rows()
    out = REPO / TABLE
    with open(out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["g_block", "p_statement_ids", "relation", "decision or case id", "page", "since 24c6b0c0"])
        w.writerows(rows)
    from collections import Counter
    print(f"statements.tsv: {len(rows)} blocks", Counter(r[2] for r in rows), Counter(r[5] for r in rows))


if __name__ == "__main__":
    main()
