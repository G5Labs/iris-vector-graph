#!/usr/bin/env python3
"""Iteration 64 housekeeping of coverage.md (§6.2 of the iteration-63 handoff). Run once from the repository root.

Corrects receipt names whose latest receipt has the same counts, marks the other stale rows with an inline
"**Stale (iteration 64):**" note pointing at the census rows that now hold the grade, adds a census-precedence note and
the two missing model rows (cypher_fns, cypher_exprs). Every edit asserts its anchor text occurs exactly once.
"""
import sys

P = ".g5/Verus_verification/coverage.md"
s = open(P, encoding="utf-8").read()
lines = s.split("\n")
M = "**Stale (iteration 64):**"
CEN = "[census](census/obligations.tsv)"


def find(sub, start=None, last=False):
    hits = [i for i, l in enumerate(lines) if sub in l and (start is None or l.startswith(start))]
    if last and len(hits) == 2 and "superseded by the [round 2 row]" in lines[hits[0]]:
        hits = hits[1:]  # the round-2 row replaces the struck-through original
    if len(hits) != 1:
        sys.exit(f"anchor {sub!r}: {len(hits)} hits")
    return hits[0]


def mark(sub, note, start=None, last=False):
    i = find(sub, start, last)
    l = lines[i]
    if M in l:
        sys.exit(f"already marked: {sub}")
    if l.rstrip().endswith("|"):
        lines[i] = l.rstrip()[:-1].rstrip() + f" {M} {note} |"
    else:
        lines[i] = l.rstrip() + f" {M} {note}"


def replace(sub, old, new):
    i = find(sub)
    assert lines[i].count(old) >= 1, (sub, old)
    lines[i] = lines[i].replace(old, new)


# 1. receipt names (latest receipt has the same verified count and control count)
replace("| [platform](models/platform/platform.rs)", "20261114T002651Z-prove", "20261116T160814Z-prove")
replace("- **Proof receipt:** `results/platform/20261114T002651Z-prove/receipt.json`", "20261114T002651Z-prove",
        "20261116T160814Z-prove")
replace("Latest prove receipt: [results/search/20261114T035601Z-prove", "20261114T035601Z", "20261116T160846Z")
mark("Latest prove receipt: [results/search/20261116T160846Z-prove",
     "the control receipts named here are superseded by the 20261116 reruns; the latest receipt per control is the "
     "newest `results/search/*-control-<name>`.")

replace("| [ledger_redaction](models/ledger_redaction/redaction.rs)", "20261114T044401Z-prove", "20261116T160746Z-prove")

# 2. search rows and gap list
mark("| [search.embedding.other_model](../ontology/features/search.g5.md#search.embedding.other_model) |",
     "the refusal half is modelled since iteration 56 in [install_lifecycle](models/install_lifecycle/NOTES.md); the "
     f"{CEN} rows search.embedding.other_model#o01-#o02 hold the grade.")
mark("| [search.embedding.queue](../ontology/architecture/search-storage-and-indexes.g5.md#search.embedding.queue) |",
     "W-O3a/b assume a queue write that the iteration-36 [embed_queue](models/embed_queue/NOTES.md) binding contradicts "
     f"on IRIS; the {CEN} row search.embedding.queue#o01 holds the grade.")
mark("#### Coverage gaps (no row: not modelled and not observed by B-search)",
     "several items below are modelled since: BM25 scoring and query-time IDF ([bm25_scoring](models/bm25_scoring/NOTES.md)), "
     "fusion ([retrieval_compose](models/retrieval_compose/NOTES.md), [fusion_ranking](models/fusion_ranking/NOTES.md)), "
     "knn, scope and no_fallback ([vector_admission](models/vector_admission/NOTES.md)), width setup and quarantine "
     f"placement ([install_lifecycle](models/install_lifecycle/NOTES.md)). The {CEN} holds the per-obligation grades.")

# 3. graph-structure rows
mark("- **Nodes, edges, reifications CRUD.**",
     "stale for nodes and edges: [node_read](models/node_read/NOTES.md), [node_edge_update](models/node_edge_update/NOTES.md), "
     "[edge_acceptance](models/edge_acceptance/NOTES.md) and [bulk_delete](models/bulk_delete/NOTES.md) model them "
     f"(grades in the {CEN}, structure.node* and structure.edge*). Reifications are still not modelled.")
mark("| [structure.rebuilt.rollback](open_questions.md#structure.rebuilt.rollback) / [algorithms.cache.concurrency]",
     "algorithms.cache.concurrency's current block text is not the text this row grades; the "
     f"{CEN} row algorithms.cache.concurrency#o01 holds the grade.")
mark("| [structure.rebuilt.valid](../ontology/architecture/adjacency-and-derived-data.g5.md#structure.rebuilt.valid) / [algorithms.cache.token]",
     "omits the as-built refutation: node creation moves no token for PPR (F-1004) and a rollback moves none "
     f"(bug-str-002); the {CEN} grades algorithms.cache#o03 and algorithms.cache.token#o01 as refuted.")
mark("| [structure.adjacency.undeclared](../ontology/architecture/adjacency-and-derived-data.g5.md#structure.adjacency.undeclared):",
     "the witness is a modelled as-built divergence, not a \"Proved\" design property, and it covers a raw SQL "
     f"delete only; the {CEN} holds structure.adjacency.undeclared#o02-#o03 at partial.")
mark("| [structure.degree.cache.erase](../ontology/architecture/adjacency-and-derived-data.g5.md#structure.degree.cache.erase):",
     f"the witnesses are modelled as-built counterexamples, graded refuted under census rule 3; see the {CEN} row "
     "structure.degree.cache.erase#o02.")

# 4. temporal rows
mark("| [temporal.structural](../ontology/architecture/adjacency-and-derived-data.g5.md#temporal.structural): forward rule",
     f"census rule 3 grades the modelled exceptions refuted, not suspected; see the {CEN} row temporal.structural#o01.")
mark("| [temporal.structural.adopt](../ontology/architecture/adjacency-and-derived-data.g5.md#temporal.structural.adopt) |",
     f"see the {CEN} row temporal.structural.adopt#o01 (refuted under census rule 3).")
mark("| [temporal.structural.end](../ontology/architecture/adjacency-and-derived-data.g5.md#temporal.structural.end) and [temporal.purge]",
     f"see the {CEN} row temporal.structural.end#o01 (refuted under census rule 3).", start="| [temporal.structural.end]",
     last=True)
mark("* [temporal.edge](../ontology/features/temporal.g5.md#temporal.edge): ts=0 handling",
     "ts=0 is modelled since in [temporal_clock](models/temporal_clock/NOTES.md); the "
     f"{CEN} row temporal.edge#o03 grades it refuted.")
mark("The window reader is still not modelled.",
     "the window reader is modelled since in [temporal_window_reader](models/temporal_window_reader/NOTES.md) "
     f"(grades in the {CEN}, temporal.window*).")

# 5. platform / install rows
mark("| [install.schema.not_ready](../ontology/operations/setup-and-upgrade.g5.md#install.schema.not_ready) |",
     "[install_lifecycle](models/install_lifecycle/NOTES.md) has separate theorems for the error kinds since iteration "
     f"56; the {CEN} rows install.schema.not_ready#oNN hold the grade (#o02 refuted, bug-plt-133).")
mark("| [install.schema.existing](../ontology/operations/setup-and-upgrade.g5.md#i",
     "the explicit-name case is refuted as built (bug-plt-026); the "
     f"{CEN} row install.schema.existing#o04 grades it refuted.")
mark("| [query.writes.ledger](../ontology/features/cypher.g5.md#query.writes.ledger) | D |",
     "\"Proved; Observed\" covers only the strict refusal of the engine path; the "
     f"{CEN} row query.writes.ledger#o01 holds the grade.")
mark("  - Not modelled: `install.schema.name` and `install.schema.classes_follow`.",
     "install.schema.name, install.setup*, install.deploy are modelled since iteration 56 "
     "([install_lifecycle](models/install_lifecycle/NOTES.md), [setup_record](models/setup_record/NOTES.md)); "
     f"grades in the {CEN}.")
mark("  - `query.writes.atomic`, `.adjacency`, `.create-existing`, `.delete-scope`.",
     "query.writes.atomic is partly modelled in [write_routing](models/write_routing/NOTES.md); "
     f"see the {CEN} rows query.writes.atomic#o01-#o05.")

# 6. FHIR, algorithms
mark("- **FHIR:** all of `fhir.*`. No model.",
     "[fhir_tasks](models/fhir_tasks/NOTES.md) (fhir.graph.lifecycle) and [sql_mapping](models/sql_mapping/NOTES.md) "
     f"(fhir.sql_mapping) exist; grades in the {CEN}.")
mark("- **Algorithms:** all of `algorithms.*`: routing, proof gate, cache, operators.",
     "operators and the cache are partly modelled since ([weighted_paths](models/weighted_paths/NOTES.md), "
     "[communities](models/communities/NOTES.md), [ppr_walk](models/ppr_walk/NOTES.md), "
     "[pagerank_admission](models/pagerank_admission/NOTES.md), [traversal_strategy](models/traversal_strategy/NOTES.md)); "
     f"routing and the proof gate are not. Grades in the {CEN}.")
mark("| [algorithms.op.paths.weighted](../ontology/features/algorithms.g5.md#algorithms.op.paths.weighted) (M12) |",
     "[weighted_paths](models/weighted_paths/NOTES.md) (iteration 9) proves the minimum for stable integer scalar "
     f"graphs; the {CEN} row algorithms.op.paths.weighted#o01 holds the grade.")
mark("| [algorithms.cache](../ontology/architecture/algorithm-execution.g5.md#algorithms.cache), [.token]",
     "the census counts the as-built counterexamples (F-1004, bug-str-002) as refutations: "
     f"{CEN} rows algorithms.cache#o03 and algorithms.cache.token#o01.")
mark("| [query.values.relationship_text](../ontology/features/cypher.g5.md#query.values.relationship_text) (M18) |",
     "\"Proved\" holds at the decoder (`parse_rel_prop_text`), not at the Cypher reader; the "
     f"{CEN} row query.values.relationship_text#o04 holds the grade.")
mark("No active formal link: graph algorithm numerics (PageRank, centralities, Leiden, the weighted shortest path's optimality)",
     "the weighted shortest path's optimality ([weighted_paths](models/weighted_paths/NOTES.md)), FHIR task "
     "lifecycle ([fhir_tasks](models/fhir_tasks/NOTES.md)) and SQL mappings ([sql_mapping](models/sql_mapping/NOTES.md)) "
     "have models since this paragraph was written.")

# 7. missing model rows and census precedence note
i = find("| [platform](models/platform/platform.rs) ([NOTES](models/platform/NOTES.md))")
lines.insert(i + 1, "| [cypher_fns](models/cypher_fns/cypher_fns.rs) ([NOTES](models/cypher_fns/NOTES.md)) | Cypher list "
             "functions, dynamic access, range, random and the SQL helper functions (row added in iteration 64) | "
             "[prove](results/cypher_fns/20261117T033035Z-prove/receipt.json) | 16 | 13/13 EXPECTED_FAIL |")
lines.insert(i + 2, "| [cypher_exprs](models/cypher_exprs/cypher_exprs.rs) ([NOTES](models/cypher_exprs/NOTES.md)) | "
             "Cypher slice, string functions, coalesce, conditions and computed values in writes (row added in iteration 64) | "
             "[prove](results/cypher_exprs/20261117T044807Z-prove/receipt.json) | 22 | 22/22 EXPECTED_FAIL |")
j = find("\"May rely on\": *supported within scope*")
lines[j + 1:j + 1] = [
    "",
    "**Census precedence (iteration 64).** The per-obligation grade of every canonical block is in the "
    "[obligation census](census/README.md) ([obligations.tsv](census/obligations.tsv)), checked by "
    "`tools/census.py` including its strict-grade lint. Where a row below disagrees with the census, the census holds. "
    "Rows the iteration-63 census found wrong or stale carry an inline **Stale (iteration 64):** note naming the "
    "census rows that now hold the grade; the rest of this map is the evidence history it was written as.",
]
open(P, "w", encoding="utf-8").write("\n".join(lines))
print("coverage.md updated")
