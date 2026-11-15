"""HD-0804 probe: what does a caller observe after `CREATE CONSTRAINT ... IS UNIQUE`?

Sources: maintainer commit f4a13d75 (2026-04-30): "IVG has no DDL constraint/index support. Added no-op handler so GQS
schema setup succeeds ... skipping them is correct behavior"; iris_vector_graph/_engine/query.py:1886-1895 (pin);
USER_GUIDE.md:313 ("A query that does not parse raises CypherParseError").
Steps (graph ia-0804): Neo4j 4 and Neo4j 5 uniqueness syntax, a CREATE INDEX, then two CREATEs with the same `email`;
SHOW CONSTRAINTS; the same DDL with read_only=True.
Oracle (which reading each outcome supports):
  DDL raises                                  -> refusal (option c)
  DDL answers with a warning in the result    -> visible no-op (option b)
  DDL answers empty, no warning, duplicate stored -> silent no-op (option a, as built and as the maintainer commit says)
Contract under test is the maintainer's no-op statement (f4a13d75): `pass` when the DDL is accepted as a no-op and
enforces nothing. The record notes what a caller can observe.
"""
from __future__ import annotations

import _common as C

G = "ia-0804"


def run(e, q, **kw):
    try:
        r = e.execute_cypher(q, **kw)
        return {"columns": list(r.columns or []), "rows": [list(x) for x in r.rows], "error": getattr(r, "error", None),
                "metadata": repr(getattr(r, "metadata", None))[:300], "sql": getattr(r, "sql", None)}
    except Exception as ex:  # noqa: BLE001
        return {"raised": f"{type(ex).__name__}: {str(ex)[:200]}"}


def main():
    c = C.conn()
    e = C.engine(c)
    try:
        ddl = {
            "neo4j4_unique": "CREATE CONSTRAINT ON (n:IaU0804) ASSERT n.email IS UNIQUE",
            "neo4j5_unique": "CREATE CONSTRAINT ia0804_u IF NOT EXISTS FOR (n:IaU0804) REQUIRE n.email IS UNIQUE",
            "create_index": "CREATE INDEX ia0804_i FOR (n:IaU0804) ON (n.email)",
        }
        out = {k: run(e, q) for k, q in ddl.items()}
        for k, v in out.items():
            C.obs(ddl=k, **v)
        C.obs(ddl="neo4j5_unique_read_only", **run(e, ddl["neo4j5_unique"], read_only=True))
        C.obs(query="show_constraints", **run(e, "SHOW CONSTRAINTS"))
        w1 = run(e, f"USE GRAPH '{G}' CREATE (:IaU0804 {{id: 'ia0804:a', email: 'x@example.org'}})")
        w2 = run(e, f"USE GRAPH '{G}' CREATE (:IaU0804 {{id: 'ia0804:b', email: 'x@example.org'}})")
        C.obs(write="first", **w1)
        C.obs(write="duplicate", **w2)
        dup = run(e, f"USE GRAPH '{G}' MATCH (n:IaU0804) WHERE n.email = 'x@example.org' RETURN count(n) AS k")
        C.obs(query="count_same_email", **dup)
        accepted = all("raised" not in v and v["rows"] == [] and not v["error"] for v in out.values())
        stored = dup.get("rows") == [[2]]
        if accepted and stored:
            C.verdict("pass", "CREATE CONSTRAINT (both syntaxes) and CREATE INDEX answer an empty result with no error "
                              "or warning, and two nodes with the same 'unique' email are stored: a silent no-op that "
                              "enforces nothing, as the maintainer commit f4a13d75 describes (option a)")
        else:
            C.verdict("fail", f"unexpected: ddl {out}, duplicate count {dup}")
    finally:
        C.obs(step="erase", removed=e.erase_graph(G))
        c.close()


if __name__ == "__main__":
    main()
