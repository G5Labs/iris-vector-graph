"""HD-1704 probe: which width rule do the public low-level vector helpers follow?

Part 1 (no IRIS): normalize_vector pads, truncates and turns NaN/Inf into 0.0, as its docstring promises
(iris_vector_graph/dbapi_utils.py:29-98).
Part 2 (live, AUDITIB scratch table IVGAudit.ib2_vec with a VECTOR(FLOAT, 4) column, dropped at the end):
insert_vector with a 3-wide, a 6-wide and a NaN-holding vector. IRIS enforces a declared VECTOR width at INSERT
(ADR-0005: the column "is where enforcement legitimately lives"); the helper coerces before the column can refuse.
The engine's registry-aware writes refuse a width mismatch (ADR-0006, spec 226/227; tested upstream in
tests/e2e/test_460_r223_vector_width_e2e.py), so that side is not re-run here.

Oracle (stated contract = the helper's docstring): coercion. Pass if the helper pads/truncates/zeroes and the
coerced rows are stored. Option (a) "refuse like the engine" would show as a refusal.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_vector_graph import insert_vector, normalize_vector  # noqa: E402

p1 = {
    "short": normalize_vector([1.0, 2.0], 4),
    "long": normalize_vector([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 4),
    "nonfinite": normalize_vector([1.0, float("nan"), float("inf"), 4.0], 4),
}
for k, v in p1.items():
    print(f"part1 normalize_vector {k}: {v}")
p1_ok = (p1["short"] == [1.0, 2.0, 0.0, 0.0] and p1["long"] == [1.0, 2.0, 3.0, 4.0]
         and p1["nonfinite"] == [1.0, 0.0, 0.0, 4.0])

from iris_conn import Conn  # noqa: E402

c = Conn("AUDITIB")
exists_q = "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'IVGAudit' AND TABLE_NAME = 'ib2_vec'"
try:
    if c.sql(exists_q)[0][0]:
        c.sql("DROP TABLE IVGAudit.ib2_vec")
    c.sql("CREATE TABLE IVGAudit.ib2_vec (k VARCHAR(64) PRIMARY KEY, v VECTOR(FLOAT, 4))")
    c.conn.commit()
    cur = c.conn.cursor()
    ok = {}
    for key, vec in [("w3", [1.0, 2.0, 3.0]), ("w6", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
                     ("nan", [1.0, float("nan"), 3.0, 4.0])]:
        ok[key] = insert_vector(cur, "IVGAudit.ib2_vec", "v", vec, 4, key_columns={"k": key})
    c.conn.commit()
    cur.close()
    # width counted from the stored value's display form (comma-separated components)
    rows = [(k, len(str(v).split(",")), v) for k, v in c.sql("SELECT k, v FROM IVGAudit.ib2_vec ORDER BY k")]
    for r in rows:
        print(f"part2 stored k={r[0]} dim={r[1]} v={r[2]}")
    print(f"part2 insert_vector returned: {ok}")
    # direct SQL with the wrong width, for contrast: the column refuses
    try:
        c.sql("INSERT INTO IVGAudit.ib2_vec (k, v) VALUES ('raw3', TO_VECTOR('[1,2,3]', FLOAT))")
        c.conn.commit()
        raw = "accepted"
    except Exception as e:
        raw = f"refused: {str(e)[:120]}"
    print(f"part2 contrast, raw INSERT of a 3-wide vector into the same column: {raw}")
    p2_ok = all(ok.values()) and len(rows) == 3 and all(int(r[1]) == 4 for r in rows)
finally:
    try:
        if c.sql(exists_q)[0][0]:
            c.sql("DROP TABLE IVGAudit.ib2_vec")
        c.conn.commit()
        print("cleanup: IVGAudit.ib2_vec dropped")
    finally:
        c.close()

print(f"ORACLE (helper docstring: pad, truncate, non-finite -> 0.0): part1={p1_ok} part2_coerced_and_stored={p2_ok}")
print("OUTCOME:", "pass (documented coercion; the width-declared column never gets to refuse)" if (p1_ok and p2_ok) else "fail")
