#!/usr/bin/env python3
"""reads3 harness smoke check (not a decisive run): connection, reset, the state walkers, Native API call forms.
One lock hold, starts from lib.reset(), removes its scratch globals."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ni3core as K  # noqa: E402
import lib  # noqa: E402
import iris  # noqa: E402


def main():
    c = lib.conn()
    out = {}
    try:
        lib.reset(c)
        e = K.engine(c)
        K.NI.put(e, K.G1, K.NI.BASE_NODES, K.NI.BASE_EDGES)
        K.NI.put(e, None, K.NI.BASE_NODES, K.NI.BASE_EDGES)
        c.conn.commit()
        out["gstate_G1"] = K.gstate(c, K.G1)
        out["degree"] = str(c.o.classMethodValue("Graph.KG.Adj", "Degree", K.G1, "a", ""))
        out["degc_G1"] = K.walk(c, "^KG", "degc", K.G1)
        e.sync()
        c.conn.commit()
        out["nkg"] = K.nkg_named(c)
        ref = iris.IRISReference(None)
        try:
            n = c.o.classMethodValue("Graph.KG.Edgeless", "Loners", "Graph_KG", K.G1, ref)
            out["loners_ref"] = [str(n), str(ref.getValue())]
        except Exception as ex:  # noqa: BLE001
            out["loners_ref"] = K.errtext(ex)
        try:
            out["void"] = K.cmv("Graph.KG.NKGAccel", "ResetCache")(e, c)
        except Exception as ex:  # noqa: BLE001
            out["void"] = K.errtext(ex)
        try:
            out["value_on_void"] = str(c.o.classMethodValue("Graph.KG.NKGAccel", "ResetCache"))
        except Exception as ex:  # noqa: BLE001
            out["value_on_void"] = K.errtext(ex)
        e.set_multigraph(K.G2, True)
        K.NI.put(e, K.G2, {"a": ([], {}), "b": ([], {})}, [("a", "R", "b"), ("a", "R", "b")])
        c.conn.commit()
        out["multi_rows_G2"] = K.rows(c, K.G2)["rdf_edges"]
        out["kg_G2"] = K.kgstate(c, K.G2, subs=("out",))
        r = e.execute_cypher("CALL ivg.degreeCentrality() YIELD node, score, degree RETURN node, score, degree")
        out["cypher_degc"] = {"rows": [list(map(str, x)) for x in (r.rows or [])][:5], "error": r.error}
        lib.reset(c)
        K.kill_scratch(c)
        c.conn.commit()
    finally:
        c.close()
    print(json.dumps(out, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
