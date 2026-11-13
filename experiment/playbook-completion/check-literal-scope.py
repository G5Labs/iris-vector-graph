"""Check the playbook's literal glossary rule against the submitted IVG modules.

Usage: python3 check-literal-scope.py /path/to/experiment/playbook-uplift
Pass --details to see every distinct statement/term pair.
"""

import argparse
import re
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("uplift", type=Path)
parser.add_argument("--details", action="store_true")
args = parser.parse_args()
sys.dont_write_bytecode = True
sys.path.insert(0, str(args.uplift.resolve() / "tools"))
from ontology_index import parse_module

modules = []
statements = {}
errors = []
for path in sorted((args.uplift / "ontology").glob("[0-9][0-9]-*.md")):
    module = parse_module(path, errors, len(statements) + len(modules))
    if module:
        modules.append(module)
        statements.update((s.id, s) for s in module.statements)
if errors:
    sys.exit("\n".join(errors))

failures = set()
for module in modules:
    patterns = {
        term: re.compile(
            r"(?<![A-Za-z0-9-])" + re.escape(term).replace(r"\ ", r"[\s-]+")
            + r"(?:s|es)?(?![A-Za-z0-9-])", re.IGNORECASE
        )
        for term, _ in module.glossary
    }
    for statement in module.statements:
        scope = {statement.id}
        scope.update(s.id for s in module.statements
                     if s.parent == statement.parent and s.order < statement.order)
        node = statement
        while node.parent in statements:
            node = statements[node.parent]
            scope.add(node.id)
        for term, definer in module.glossary:
            if definer not in scope and patterns[term].search(statement.text):
                failures.add((statement.id, term))

if args.details:
    for statement_id, term in sorted(failures):
        print(f"{statement_id}\t{term}")
print(f"{len(failures)} statement/term pairs in {len({s for s, _ in failures})} statements")
