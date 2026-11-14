"""Declared write stores of an entry point, read from the registered footprint files (never widened here).

Formats: footprints/01-06.json (entry_points[].writes = [{store, ops, at}]), footprints/07-11.json
(entry_points[].writes = {tables, globals} as text), footprints/15,17,18.json (entries[].writes = ["sql:..",
"global:.."] with comments), correspondence/correspondence.json (actions[].writes = {globals, tables} as text, where a
'("head")' item continues the previous global's root). The parse keeps every global root (^Name) and every table
named; free-text table groups are expanded only where the text names them ('kg_NodeEmbeddings(_optimized)',
'routed kg_emb_*/kg_eemb_*', 'FHIR side tables', 'every content table', '^Graph.KG.LedgerRevisionD/I').
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

PC = Path(__file__).resolve().parents[2]
CONTENT = ["nodes", "rdf_edges", "rdf_labels", "rdf_props"]
TABLE_WORD = re.compile(r"\b(?:Graph_KG\.)?([A-Za-z_][A-Za-z0-9_]*)")
KNOWN_TABLES = {"nodes", "rdf_edges", "rdf_labels", "rdf_props", "rdf_reifications", "docs", "embedding_registry",
                "embedding_quarantine", "kg_NodeEmbeddings", "kg_NodeEmbeddings_optimized", "kg_EdgeEmbeddings",
                "ledger_revisions", "ledger_stats", "fhir_bridges", "code_crosswalk", "rdf_namespaces",
                "table_mappings", "relationship_mappings", "fhir_graphs", "fhir_definitions", "fhir_unresolved",
                "fhir_canonical_refs", "embedding_route_state"}


def _load(path):
    return json.loads((PC / path).read_text())


def _from_text_globals(items: List[str]) -> List[str]:
    out, last_root = [], None
    for it in items:
        roots = re.findall(r"\^(?!\|\|)[%A-Za-z][\w.%]*", it)
        if it.strip().startswith("(") and last_root:
            m = re.match(r'\s*\("?([^",)]*)', it)
            out.append(f"global:{last_root}" + (f'("{m.group(1)}")' if m and m.group(1) else ""))
        for r in roots:
            if r.endswith("D/I") or "LedgerRevisionD/I" in it:
                pass
            out.append("global:" + r)
            last_root = r
        if "LedgerRevisionD/I" in it:
            out += ["global:^Graph.KG.LedgerRevisionD", "global:^Graph.KG.LedgerRevisionI"]
        if re.search(r"\^KG\b", it) is None and re.search(r"\bKG (out|in|adjacency)", it):
            out.append("global:^KG")
    return out


def _from_text_tables(items: List[str]) -> List[str]:
    out = []
    for it in items:
        low = it.lower()
        if "every content table" in low:
            out += [f"sql:Graph_KG.{t}" for t in CONTENT]
        if "kg_nodeembeddings(_optimized)" in low:
            out += ["sql:Graph_KG.kg_NodeEmbeddings", "sql:Graph_KG.kg_NodeEmbeddings_optimized"]
        if "kg_emb_" in low or "node routes" in low:
            out.append("sql:Graph_KG.kg_emb_*")
        if "kg_eemb_" in low or "edge routes" in low:
            out.append("sql:Graph_KG.kg_eemb_*")
        if "fhir side tables" in low or "fhir node rows" in low:
            out.append("sql:Graph_KG.fhir_*")
        for m in TABLE_WORD.finditer(it):
            w = m.group(1)
            if w in KNOWN_TABLES or w.lower() in {t.lower() for t in KNOWN_TABLES}:
                out.append(f"sql:Graph_KG.{w}")
        out += ["global:" + r for r in re.findall(r"\^(?!\|\|)[%A-Za-z][\w.%]*", it)]
        if "LedgerRevisionD/I" in it:
            out += ["global:^Graph.KG.LedgerRevisionD", "global:^Graph.KG.LedgerRevisionI"]
    return out


def declared(module: str, entry: str) -> dict:
    """{'stores': [...], 'source': 'path#entry', 'raw': ...}; raises KeyError if the entry is not declared."""
    if module in ("12", "13", "14") or entry.startswith("corr:"):
        name = entry.split(":", 1)[1] if entry.startswith("corr:") else entry
        for a in _load("correspondence/correspondence.json")["actions"]:
            if a["id"] == name:
                w = a["writes"]
                return {"stores": sorted(set(_from_text_globals(w.get("globals", [])) +
                                             _from_text_tables(w.get("tables", [])))),
                        "source": f"correspondence/correspondence.json#actions[{name}].writes", "raw": w}
        raise KeyError(entry)
    d = _load(f"footprints/{module}.json")
    eps = d.get("entry_points") or d.get("entries") or []
    for e in eps:
        if (e.get("id") or e.get("entry")) != entry:
            continue
        w = e.get("writes")
        if isinstance(w, dict):
            stores = _from_text_globals(w.get("globals", [])) + _from_text_tables(w.get("tables", []))
            for txt in w.get("globals", []) + w.get("tables", []):
                m = re.match(r"\s*as ([A-Za-z]\w*)", txt)       # "as Build": the class method's own declaration
                if m:
                    for e2 in eps:
                        if (e2.get("id") or "").endswith("." + m.group(1)) and e2 is not e:
                            w2 = e2.get("writes") or {}
                            stores += _from_text_globals(w2.get("globals", [])) + _from_text_tables(w2.get("tables", []))
                            break
        else:
            stores = []
            for x in w or []:
                s = x["store"] if isinstance(x, dict) else x
                if s.startswith(("sql:", "global:")):
                    s0 = s.split(" ")[0]
                    if "<dynamic" in s0 or "kg_emb_<route>" in s:
                        stores.append("sql:Graph_KG.kg_emb_*")
                        stores.append("sql:Graph_KG.kg_eemb_*")
                        stores.append("sql:Graph_KG.kg_NodeEmbeddings")
                        stores.append("sql:Graph_KG.kg_EdgeEmbeddings")
                        continue
                    if "[process-private" in s:
                        continue
                    stores.append(s0)
                else:
                    stores += _from_text_globals([s]) + _from_text_tables([s])
        return {"stores": sorted(set(stores)), "source": f"footprints/{module}.json#{entry}", "raw": w}
    raise KeyError(entry)


if __name__ == "__main__":
    import sys
    print(json.dumps(declared(sys.argv[1], sys.argv[2]), indent=1)[:3000])
