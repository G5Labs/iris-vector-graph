"""W45: validate_shacl on the frozen shapes (run-isolated continuation fixture; ordinary data, ids unique per run).
Every case validates only its own node ids or a label unique to the run, so other fixture data cannot interfere."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W45_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def main():
    c = runtime.connect(); e = runtime.engine(c)
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    D = f"Drug{TAG}"; Gn = f"Gene{TAG}"; p = f"s{TAG}_"
    shape_min = f"""@prefix sh: <http://www.w3.org/ns/shacl#> .
<urn:ivg:shape/{D}> a sh:NodeShape ; sh:targetClass <urn:ivg:{D}> ;
  sh:property [ sh:path <urn:ivg:prop/approved> ; sh:minCount 1 ; sh:message "a Drug needs an approval year" ] ."""
    shape_int = f"""@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<urn:ivg:shape/{D}i> a sh:NodeShape ; sh:targetClass <urn:ivg:{D}> ;
  sh:property [ sh:path <urn:ivg:prop/approved> ; sh:datatype xsd:integer ] ."""
    shape_str = f"""@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<urn:ivg:shape/{D}s> a sh:NodeShape ; sh:targetClass <urn:ivg:{D}> ;
  sh:property [ sh:path <urn:ivg:prop/code> ; sh:datatype xsd:string ] ."""
    shape_cls = f"""@prefix sh: <http://www.w3.org/ns/shacl#> .
<urn:ivg:shape/{D}c> a sh:NodeShape ; sh:targetClass <urn:ivg:{D}> ;
  sh:property [ sh:path <urn:ivg:INHIBITS{TAG}> ; sh:class <urn:ivg:{Gn}> ] ."""

    def rep(r):
        return {"conforms": r.conforms, "violations": sorted([v.focus_node, v.message, v.severity] for v in r.violations)}

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    ok, bad = p + "ok", p + "bad"
    e.create_node(ok, labels=[D], properties={"approved": 2011})
    e.create_node(bad, labels=[D], properties={"name": "x"})
    case("S1_both", lambda: rep(e.validate_shacl(shape_min, node_ids=[ok, bad])))
    case("S2_valid_only", lambda: rep(e.validate_shacl(shape_min, node_ids=[ok])))
    case("S1_all_graphs", lambda: rep(e.validate_shacl(shape_min)))   # whole namespace; only this run's label is targeted

    sint, sstr = p + "strint", p + "strcode"
    e.create_node(sint, labels=[D], properties={"approved": "2011"})
    e.create_node(sstr, labels=[D], properties={"code": "2011"})
    case("S3_string_2011_vs_integer_shape", lambda: rep(e.validate_shacl(shape_int, node_ids=[sint])))
    case("S3b_string_2011_vs_string_shape", lambda: rep(e.validate_shacl(shape_str, node_ids=[sstr])))
    case("S3c_int_2011_vs_integer_shape", lambda: rep(e.validate_shacl(shape_int, node_ids=[ok])))

    G = f"sg{TAG}"; twin = p + "twin"
    e.create_node(twin, labels=[D], properties={"approved": 1999})
    e.create_node(twin, labels=[D], properties={"name": "no approval here"}, graph=G)
    case("S4_same_id_two_graphs", lambda: rep(e.validate_shacl(shape_min, node_ids=[twin])))
    case("S4b_named_graph_node_only", lambda: rep(e.validate_shacl(shape_min, node_ids=[twin, bad])))

    drug, gene, nolab = p + "drug", p + "gene", p + "nolabel"
    e.create_node(drug, labels=[D], properties={"approved": 2020})
    e.create_node(gene, labels=[Gn])
    e.create_node(nolab, labels=["Other"])
    e.create_edge(drug, f"INHIBITS{TAG}", gene)
    drug2 = p + "drug2"
    e.create_node(drug2, labels=[D], properties={"approved": 2021})
    e.create_edge(drug2, f"INHIBITS{TAG}", nolab)
    case("S5_class_ok", lambda: rep(e.validate_shacl(shape_cls, node_ids=[drug, gene])))
    case("S5b_class_bad", lambda: rep(e.validate_shacl(shape_cls, node_ids=[drug2, nolab])))
    case("S6_class_ok_focus_only", lambda: rep(e.validate_shacl(shape_cls, node_ids=[drug])))

    dest = HERE / f"shacl-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
