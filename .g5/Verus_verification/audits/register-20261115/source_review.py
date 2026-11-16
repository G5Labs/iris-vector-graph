"""Inventory every starting ID and its available source/evidence, without executing it."""
from pathlib import Path as _AuditPath
if (_AuditPath(__file__).resolve().parent / "APPLIED.json").exists():
    raise SystemExit("This audit has been applied. Preserve its reviewed registers; replay regressions.py, components.py or verify.py instead of rebuilding history.")

from pathlib import Path
import collections
import hashlib
import json
import re
import subprocess
import urllib.parse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V = ROOT / ".g5/Verus_verification"
I = json.loads((HERE / "starting-inventory.json").read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def paths(text):
    return set(re.findall(r"(?:iris_vector_graph|iris_src|tests|docs|specs|api)/[\w./-]+\.(?:py|cls|md|json)", text))


def resolve(link, base=V):
    link = urllib.parse.unquote(link.split("#")[0])
    if not link or "://" in link:
        return None
    p = (base / link).resolve()
    if not p.is_relative_to(ROOT):
        return None
    return p


catalog = {}
for p in (ROOT / "experiment/playbook-completion/findings/audit").glob("*.json"):
    j = json.loads(p.read_text())
    if isinstance(j, list):
        j = {"findings": j}
    for key in ["findings", "new_findings"]:
        values = j.get(key, [])
        for x in values if isinstance(values, list) else []:
            if isinstance(x, dict) and x.get("id"):
                catalog[x["id"]] = dict(source=str(p.relative_to(ROOT)), entry=x)

ontology = {}
backlinks = collections.defaultdict(list)
for p in (ROOT / ".g5/ontology").rglob("*.md"):
    s = p.read_text()
    before = s.split("## Metadata")[0]
    for m in re.finditer(r'^<a id="([^"]+)"></a>\n\[([IDQ]) · [^\]]+\]\n(.*?)(?=^<a id=|^## |\Z)', before, re.M | re.S):
        ontology[m[1]] = dict(path=str(p.relative_to(ROOT)), kind=m[2], body=m[3].strip())
    for m in re.finditer(r'^### ([^\n]+)\n(.*?)(?=^### |\Z)', s.split("## Metadata")[-1], re.M | re.S):
        for register, ident in re.findall(r'(bugs_issues|open_questions|design_simplification)\.md#([^\s)]+)', m[2]):
            backlinks[(register, ident)].append(m[1])

all_source = {}
review = {}
for kind, items in I.items():
    review[kind] = []
    for x in items:
        text = x["body"]
        links = []
        for link in x["links"]:
            p = resolve(link)
            if p is not None:
                item = dict(path=str(p.relative_to(ROOT)), exists=p.is_file())
                if p.is_file():
                    item["sha256"] = sha(p)
                    # Read only already-sealed, directly linked records. No quarantined search.
                    if p.suffix == ".md" and "experiment/playbook-completion/intent/HD-" in str(p):
                        text += "\n" + p.read_text()
                        item["intent_source_consulted"] = True
                links.append(item)
        inherited = catalog.get(x["id"])
        if inherited:
            text += "\n" + json.dumps(inherited["entry"])
        owners = backlinks.get((kind, x["id"]), [])
        for owner in owners:
            if owner in ontology:
                p = ROOT / ontology[owner]["path"]
                s = p.read_text()
                m = re.search(r'^### ' + re.escape(owner) + r'\n(.*?)(?=^### |\Z)', s, re.M | re.S)
                if m:
                    text += "\n" + m[1]
        refs = paths(text)
        source_records = []
        for rel in sorted(refs):
            p = ROOT / rel
            if rel not in all_source:
                if p.is_file():
                    s = p.read_text(errors="replace")
                    history = subprocess.check_output(["git", "log", "-1", "--format=%H %an %s", "3eaa79cf", "--", rel], cwd=ROOT, text=True).strip()
                    all_source[rel] = dict(exists=True, sha256=sha(p), lines=len(s.splitlines()), last_product_commit=history)
                else:
                    all_source[rel] = dict(exists=False)
            source_records.append(rel)
        review[kind].append(dict(id=x["id"], title=x["title"], owners=owners,
            directly_linked_records=links, source_files=source_records,
            test_files=sorted(p for p in refs if p.startswith("tests/")),
            inherited_evidence=inherited,
            protected_human_status=bool(re.search(r'Decision: (Need fix|Defer|Irrelevant)', x["body"]))))

(HERE / "source-review.json").write_text(json.dumps(review, indent=2) + "\n")
(HERE / "source-catalog.json").write_text(json.dumps(all_source, indent=2) + "\n")
(HERE / "ontology-start.json").write_text(json.dumps(ontology, indent=2) + "\n")
print(json.dumps(dict(entries={k:len(v) for k,v in review.items()}, source_files=len(all_source), missing_sources=sum(not x["exists"] for x in all_source.values()), protected=sum(x["protected_human_status"] for v in review.values() for x in v))))
