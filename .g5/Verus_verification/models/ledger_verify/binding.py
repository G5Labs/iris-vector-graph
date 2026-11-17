"""ledger_verify native binding: the product's verify()/verify(adopt=True) on IRIS vs the model's compare/adopt.

Run through the local runtime wrapper:
    python -B .g5/uplift/consolidated/local-runtime/run_binding.py .g5/Verus_verification/models/ledger_verify/binding.py
Writes only in task-owned namespaces (ledger enabled), with per-run IDs: by default the iteration-60 repair's I60RV
(general cases) and I60RT (temporal text marker; once a relationship with temporal text "true" is committed there, that
namespace never verifies equal again); override with LEDGER_VERIFY_NS / LEDGER_VERIFY_NS_T (the iteration-60 run used
I60LB for the general cases).

The expected side is an UNVERIFIED hand transcription of ledger_verify.rs (canonical projection `canon_get`, the replay
drop rule, `emitted`/`compare`, `adopted_get`/`adopt`, `redrop`, `verify`). The tables' marker is the JSON boolean true and the
replay's marker is the text "true" (two rules, repaired after review 60 FE-1); a node also exists through a label or a
non-reserved property row (FE-2). Its inputs are built by this harness, not by the
product's read_canonical/compare: the tables view from the harness's own SQL reads of Graph_KG.nodes / rdf_labels /
rdf_props / rdf_edges, and the replay view from GraphLedger.reconstruct(head) (the replay fold is bound by the
reconstruction/ledger_content models). The observation is the product's VerificationReport (result, differences
converted to facts), the adoption revision's records and the next verify. Qualifier values are converted as
read_canonical documents (bool → "true"/"false", dict/list → JSON, else str) and the default graph's spellings fold to
None, as `_graph_key` does; both are transcription details outside the model.
"""
import copy
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
import binding_common as bc  # noqa: E402

PIN_DIR = bc.import_pin()
import runtime as rt  # noqa: E402
from iris_vector_graph.ledger import Changeset  # noqa: E402

RESERVED = {"id", "__graph"}


def gkey(g):
    return None if g in (None, "", "\x00", "\x01") else str(g)


def qual_text(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return str(v)


class Ref:
    def __init__(self, mut=None):
        self.mut = mut

    # ---- canon_get over the harness's own table reads
    def canonical(self, rows):
        v = {}
        for nid, g in rows["nodes"]:
            if self.mut == "graph-scoped-node-identity" and gkey(g) is not None:
                continue
            v[("Node", nid)] = "0"
        for s, lab in rows["labels"]:
            v[("Label", s, lab)] = "0"
            if self.mut != "node-from-node-rows-only":
                v[("Node", s)] = "0"
        for s, k, val in rows["props"]:
            if k in RESERVED and self.mut != "reserved-kept":
                continue
            v[("Prop", s, k)] = "" if val is None else str(val)
            if self.mut != "node-from-node-rows-only":
                v[("Node", s)] = "0"
        for s, p, o, g, quals in rows["edges"]:
            q = json.loads(quals) if quals else {}
            marked = q.get("temporal") is True
            if self.mut == "one-marker-rule":
                marked = marked or q.get("temporal") == "true"
            if marked and self.mut != "temporal-row-governed":
                continue
            t = (s, p, o, gkey(g))
            v[("Rel", t)] = "0"
            for k, x in q.items():
                if x is not None:
                    v[("Qual", t, k)] = qual_text(x)
        return v

    # ---- the replay side: GraphState folded by the product reader, the drop rule applied here
    def replay(self, st):
        v = {}
        for nid, ns in st.nodes.items():
            v[("Node", nid)] = "0"
            for lab in ns.labels:
                v[("Label", nid, lab)] = "0"
            for k, x in ns.props.items():
                v[("Prop", nid, k)] = x
        for sid, sx in st.statements.items():
            if sx.quals.get("temporal") == "true" and self.mut != "replay-keeps-marked":
                continue
            t = (sx.s, sx.p, sx.o, gkey(sx.graph))
            v[("Rel", t)] = "0"
            for k, x in sx.quals.items():
                v[("Qual", t, k)] = x
        return v

    @staticmethod
    def owner(f):
        if f[0] in ("Label", "Prop"):
            return ("Node", f[1])
        if f[0] == "Qual":
            return ("Rel", f[1])
        return None

    def compare(self, a, b):
        d = {}
        for f in set(a) | set(b):
            if a.get(f) == b.get(f):
                continue
            o = self.owner(f)
            if o is not None and o in a and o not in b:
                continue
            if self.mut == "new-entity-attributes-dropped" and o is not None and o not in a:
                continue
            d[f] = b.get(f)
        return d

    def adopt(self, a, d):
        out = {}
        for f in set(a) | set(d):
            if f in d:
                if d[f] is not None:
                    out[f] = d[f]
                continue
            o = self.owner(f)
            if o is not None and o in d and d[o] is None and self.mut != "adopt-without-cascade":
                continue
            if f in a:
                out[f] = a[f]
        return out

    def redrop(self, v):
        """The drop rule runs again on the next verify's replay: a tuple whose temporal qualifier text is "true" is
        left out with its qualifiers."""
        if self.mut == "no-redrop":
            return dict(v)
        gone = {f[1] for f, x in v.items() if f[0] == "Qual" and f[2] == "temporal" and x == "true"}
        return {f: x for f, x in v.items() if not (f[0] in ("Rel", "Qual") and f[1] in gone)}

    def next_after_adoption(self, a, b):
        return self.compare(self.redrop(self.adopt(a, self.compare(a, b))), b)

    def verify(self, a, b, adopt):
        d = self.compare(a, b)
        empty = not d
        return {"result": "equal" if empty else "diverges", "adoption": (adopt if self.mut == "adopt-when-equal" else adopt and not empty)}


MUTATIONS = ["adopt-without-cascade", "new-entity-attributes-dropped", "adopt-when-equal", "graph-scoped-node-identity",
             "reserved-kept", "temporal-row-governed", "replay-keeps-marked", "statement-ids-compared", "one-marker-rule",
             "no-redrop", "node-from-node-rows-only"]
# replay-keeps-marked became natively exercisable in the repair: a committed relationship with temporal text "true" is a
# marked statement in the history (the iteration-60 run thought it needed a forged pre-4.6.0 genesis).
NOT_NATIVE = {"statement-ids-compared": "needs a tuple whose table row and history name different statement IDs; not forged",
              "text-marker-premise-dropped": "a proof premise (no_text_marker); its runtime consequence is the no-redrop mutation"}


def read_tables(c):
    cur = c.cursor()
    rows = {}
    cur.execute("SELECT node_id, graph_id FROM Graph_KG.nodes"); rows["nodes"] = [tuple(r) for r in cur.fetchall()]
    cur.execute("SELECT s, label FROM Graph_KG.rdf_labels"); rows["labels"] = [tuple(r) for r in cur.fetchall()]
    cur.execute('SELECT s, "key", val FROM Graph_KG.rdf_props'); rows["props"] = [tuple(r) for r in cur.fetchall()]
    cur.execute("SELECT s, p, o_id, graph_id, qualifiers FROM Graph_KG.rdf_edges"); rows["edges"] = [tuple(r) for r in cur.fetchall()]
    cur.close()
    return rows


def entries_to_facts(entries, st):
    """VerificationReport.differences → {fact: after}; relationship entries name a tuple JSON or a statement ID."""
    d = {}
    for e in entries:
        if e.entity_kind == "node":
            if e.attr == "":
                f = ("Node", e.entity_id); after = None if e.after is None else "0"
            elif e.attr.startswith("label:"):
                f = ("Label", e.entity_id, e.attr[6:]); after = None if e.after is None else "0"
            else:
                f = ("Prop", e.entity_id, e.attr[5:]); after = e.after
        else:
            if e.entity_id.startswith("{"):
                tj = json.loads(e.entity_id)
            else:
                sx = st.statements[e.entity_id]
                tj = {"s": sx.s, "p": sx.p, "o": sx.o, "graph": sx.graph}
            t = (tj["s"], tj["p"], tj["o"], gkey(tj["graph"]))
            if e.attr == "":
                f = ("Rel", t); after = None if e.after is None else "0"
            else:
                f = ("Qual", t, e.attr[5:]); after = e.after
        d[f] = after
    return d


NS_V = os.environ.get("LEDGER_VERIFY_NS", "I60RV")
NS_T = os.environ.get("LEDGER_VERIFY_NS_T", "I60RT")


def facts(entries, st):
    return sorted(map(repr, entries_to_facts(entries, st).items()))


def main():
    stamp = time.strftime("%H%M%S", time.gmtime())
    cases = []
    # ------------------------------------------------------------------ general cases (NS_V)
    c = rt.connect(NS_V); e = rt.engine(c, NS_V); L = e.ledger
    p = f"i60v{stamp}_"
    L.verify(adopt=True)  # start from an equal ledger
    h0 = L.head().seq
    r0 = L.verify(adopt=True)
    st = L.reconstruct(L.head().revision_id)
    rows = read_tables(c)
    cases.append(("V0.equal_no_adoption", {"result": r0.result, "adoption": r0.adoption_revision is not None, "head_moved": L.head().seq - h0},
                  lambda ref, st=st, rows=rows: dict(ref.verify(ref.replay(st), ref.canonical(rows), True), head_moved=int(ref.verify(ref.replay(st), ref.canonical(rows), True)["adoption"]))))
    # recorded content, including a relationship whose temporal qualifier is the text "yes" (governed on both sides)
    cs = Changeset(actor="bindv", actor_type="agent", post_commit_properties={p + "orphan": {"k": "v"}})
    cs.create_node(p + "n1", labels=["L"], properties={"p": "1"}); cs.create_node(p + "n2"); cs.create_node(p + "n3", properties={"q": "x"})
    cs.create_relationship(p + "n1", "K", p + "n2", qualifiers={"w": "1"})
    cs.create_relationship(p + "n2", "Y", p + "n3", qualifiers={"temporal": "yes"})
    L.commit(cs)
    # unrecorded writes of every kind (the post-commit property above is one more: a property row with no node row)
    e.create_node(p + "ux", labels=["X"], properties={"k": "v"})
    e.execute_cypher(f"MATCH (n {{id:'{p}n1'}}) SET n.p = '9' RETURN n.p")
    e.delete_node(p + "n3")
    e.create_edge(p + "n2", "Q", p + "n1", qualifiers={"z": "1"})
    e.delete_edge(p + "n1", "K", p + "n2")
    e.create_edge_temporal(p + "n1", "T", p + "n2", timestamp=1700000000)
    e.create_node(p + "uy", graph="g60v")
    st = L.reconstruct(L.head().revision_id)
    rows = read_tables(c)
    r1 = L.verify()
    cases.append(("V1.entries", {"result": r1.result, "facts": facts(r1.differences, st)}, lambda ref, st=st, rows=rows: {
        "result": ref.verify(ref.replay(st), ref.canonical(rows), False)["result"],
        "facts": sorted(map(repr, ref.compare(ref.replay(st), ref.canonical(rows)).items()))}))
    h1 = L.head()
    r2 = L.verify(adopt=True)
    recs = L.get_revision(r2.adoption_revision.revision_id).records if r2.adoption_revision else []
    r3 = L.verify()
    st3 = L.reconstruct(L.head().revision_id)
    obs2 = {"adoption_parent_is_head": bool(r2.adoption_revision and r2.adoption_revision.parent_id == h1.revision_id),
            "adoption_kind": r2.adoption_revision.kind if r2.adoption_revision else None, "records": len(recs), "next": r3.result,
            "next_facts": facts(r3.differences, st3)}
    cases.append(("V2.adopt_closes", obs2, lambda ref, st=st, rows=rows: {
        "adoption_parent_is_head": ref.verify(ref.replay(st), ref.canonical(rows), True)["adoption"],
        "adoption_kind": "adoption",
        "records": len(obs2_records_expected(ref, st, rows)),
        "next": "equal" if not ref.next_after_adoption(ref.replay(st), ref.canonical(rows)) else "diverges",
        "next_facts": sorted(map(repr, ref.next_after_adoption(ref.replay(st), ref.canonical(rows)).items()))}))
    c.close()
    # ------------------------------------------------------------------ temporal text marker (NS_T)
    c = rt.connect(NS_T); e = rt.engine(c, NS_T); L = e.ledger
    p = f"i60t{stamp}_"
    cs = Changeset(actor="bindv", actor_type="agent")
    for x in ("a", "b", "c", "d", "e", "f"):
        cs.upsert_node(p + x)
    cs.create_relationship(p + "a", "TT", p + "b", qualifiers={"temporal": "true", "w": "2"})   # text "true"
    cs.create_relationship(p + "c", "TB", p + "d", qualifiers={"temporal": True})              # Python True -> "true"
    cs.create_relationship(p + "e", "TY", p + "f", qualifiers={"temporal": "yes"})             # neighbour
    L.commit(cs)
    e.create_edge(p + "a", "UT", p + "d", qualifiers={"temporal": "true"})   # unrecorded, text
    e.create_edge(p + "c", "UB", p + "f", qualifiers={"temporal": True})     # unrecorded, JSON boolean: left out
    st = L.reconstruct(L.head().revision_id)
    rows = read_tables(c)
    r1 = L.verify()
    mine = [f for f in facts(r1.differences, st) if p in f]
    cases.append(("T1.text_marker_entries", {"result": r1.result, "facts": facts(r1.differences, st), "this_run": mine},
                  lambda ref, st=st, rows=rows, p=p: {
                      "result": ref.verify(ref.replay(st), ref.canonical(rows), False)["result"],
                      "facts": sorted(map(repr, ref.compare(ref.replay(st), ref.canonical(rows)).items())),
                      "this_run": [f for f in sorted(map(repr, ref.compare(ref.replay(st), ref.canonical(rows)).items())) if p in f]}))
    h1 = L.head()
    r2 = L.verify(adopt=True)
    recs = L.get_revision(r2.adoption_revision.revision_id).records if r2.adoption_revision else []
    r3 = L.verify()
    st3 = L.reconstruct(L.head().revision_id)
    cases.append(("T2.adoption_never_closes", {
        "adoption_written": r2.adoption_revision is not None, "head_moved": L.head().seq - h1.seq, "records": len(recs),
        "next": r3.result, "next_facts": facts(r3.differences, st3)},
        lambda ref, st=st, rows=rows: {
            "adoption_written": ref.verify(ref.replay(st), ref.canonical(rows), True)["adoption"],
            "head_moved": int(ref.verify(ref.replay(st), ref.canonical(rows), True)["adoption"]),
            "records": len(obs2_records_expected(ref, st, rows)),
            "next": "equal" if not ref.next_after_adoption(ref.replay(st), ref.canonical(rows)) else "diverges",
            "next_facts": sorted(map(repr, ref.next_after_adoption(ref.replay(st), ref.canonical(rows)).items()))}))
    c.close()

    def run(ref):
        return [{"case": n, "expected": f(ref), "observed": o} for n, o, f in cases if f(ref) != o]
    mism = run(Ref())
    detected = {m: bool(run(Ref(m))) for m in MUTATIONS}
    changed = [(n, (dict(o, result="equal") if n == "V1.entries" else o), f) for n, o, f in cases]
    changed_caught = any(f(Ref()) != o for n, o, f in changed)
    native = [m for m in MUTATIONS if m not in NOT_NATIVE]
    verdict = "AGREES" if not mism and all(detected[m] for m in native) and changed_caught else "DISAGREES"
    body = {"verdict": verdict, "comparisons": len(cases), "mismatch_count": len(mism), "mismatches": mism,
            "mutations_detected": detected, "mutations_not_natively_exercisable": NOT_NATIVE, "changed_observation_caught": changed_caught,
            "cases": [{"name": n, "observed": o} for n, o, _ in cases], "fixture": rt.FIXTURE, "namespaces": [NS_V, NS_T], "run_stamp": stamp,
            "pin": bc.pin_identity(PIN_DIR),
            "observed": "GraphLedger.verify / replay.verify -> read_canonical, _drop_temporal_marked, compare, _adoption_items, "
                        "commit(kind='adoption') -> LedgerGenesis.Adopt on IRIS; next verify",
            "substituted": "none for the product; expected side is an unverified transcription of ledger_verify.rs over harness-read tables "
                           "and the product's reconstruct() fold",
            "not_observed": "statement-ID mismatch between table and history; concurrent writers (q-led-006); a node ID with "
                            "property rows in two graphs (q-led-004)"}
    out = bc.write_receipt("ledger_verify", Path(__file__), body)
    d = json.loads(out.read_text())
    for pth in ["iris_vector_graph/ledger/replay.py", "iris_vector_graph/ledger/client.py", "iris_src/src/Graph/KG/LedgerGenesis.cls",
                "iris_src/src/Graph/KG/LedgerApply.cls", "iris_vector_graph/ledger/changeset.py"]:
        d["inputs"][pth] = bc.sha(PIN_DIR / pth)
        assert d["inputs"][pth] == bc.sha(bc.REPO / pth), pth
    d["inputs"][".g5/uplift/consolidated/local-runtime/runtime.py"] = bc.sha(Path(rt.__file__))
    out.write_text(json.dumps(d, indent=2, sort_keys=True, default=str) + "\n")
    print(f"ledger_verify binding: {verdict}; {len(cases)} cases; mismatches {len(mism)}; mutations detected "
          f"{sum(detected.values())}/{len(detected)} (not native: {list(NOT_NATIVE)}); changed caught {changed_caught}; {out}")
    if mism:
        print(json.dumps(mism, indent=1, default=str)[:4000])
    return int(verdict != "AGREES")


def obs2_records_expected(ref, st, rows):
    """Records the adoption revision should hold: one per entry (Adopt records the items it is given)."""
    return list(ref.compare(ref.replay(st), ref.canonical(rows)).items())


if __name__ == "__main__":
    raise SystemExit(main())
