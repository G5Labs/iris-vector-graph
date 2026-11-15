"""HD-0101 probe: is an engine refused when the namespace's IVG Schema record cannot be read?

Contract under test (ADR-0016 Decision + Consequences, accepted 2026-11-03; spec 262 FR-006):
  an engine whose schema differs from the namespace's record is refused on first access "instead of sharing globals
  silently". ADMIN_GUIDE.md:516-519 documents that without %Native_GlobalAccess the engine "warns that it could not read
  the record and skips the check".

Oracle (two cases, same mismatched engine schema IA0101X; AUDITIA records Graph_KG):
  1. readable record  -> engine.conn raises IVGSchemaError (refused).                      [FR-006 holds]
  2. unreadable record (the Native API read of ^IVG.Deploy raises, simulated in this process only by wrapping the
     engine's Native API handle; this is the failure a role without %Native_GlobalAccess gets) ->
       refused          => fail-closed reading (option b)
       accepted + WARN  => documented fail-open reading (option a, as built)
Nothing is written: no SQL statement is issued on the mismatched engine beyond what construction does.
Verdict: pass when case 1 refuses and case 2 matches the documented fail-open behaviour (the contract under test for
case 2 is ADMIN_GUIDE's description); the record says which reading the outcome supports.
"""
from __future__ import annotations

import logging

import _common as C

from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.schema_name import IVGSchemaError


class _Unreadable:
    """Delegates to the real Native API handle except reads of ^IVG.Deploy, which raise like a <PROTECT>."""

    def __init__(self, real):
        self._real = real

    def get(self, gname, *subs):
        if str(gname).lstrip("^") == "IVG.Deploy":
            raise RuntimeError("<PROTECT> *Resource %Native_GlobalAccess required (simulated by HD-0101 probe)")
        return self._real.get(gname, *subs)

    def isDefined(self, gname, *subs):  # noqa: N802 (driver name)
        if str(gname).lstrip("^") == "IVG.Deploy":
            raise RuntimeError("<PROTECT> *Resource %Native_GlobalAccess required (simulated by HD-0101 probe)")
        return self._real.isDefined(gname, *subs)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def main() -> None:
    c = C.conn()
    try:
        recorded = c.o.get("^IVG.Deploy", "schema")
        C.obs(step="record", recorded=recorded)

        # Case 1: readable record, mismatched engine
        e1 = C.engine(c, schema_prefix="IA0101X")
        try:
            _ = e1.conn
            case1 = "accepted"
        except IVGSchemaError as exc:
            case1 = "refused"
            C.obs(step="case1", error=str(exc)[:200])
        C.obs(step="case1", outcome=case1)

        # Case 2: the record read raises
        cap = _Capture()
        logging.getLogger("iris_vector_graph").addHandler(cap)
        real_iris_obj = IRISGraphEngine._iris_obj
        IRISGraphEngine._iris_obj = lambda self: _Unreadable(real_iris_obj(self))
        try:
            try:
                e2 = C.engine(c, schema_prefix="IA0101X")
                constructed = True
            except IVGSchemaError as exc:
                constructed = False
                C.obs(step="case2-construct", error=str(exc)[:200])
        finally:
            IRISGraphEngine._iris_obj = real_iris_obj
            logging.getLogger("iris_vector_graph").removeHandler(cap)
        case2 = "refused"
        if constructed:
            try:
                _ = e2.conn
                case2 = "accepted"
            except IVGSchemaError as exc:
                case2 = "refused"
                C.obs(step="case2", error=str(exc)[:200])
        warned = [m for m in cap.lines if "could not read this namespace's IVG Schema record" in m]
        C.obs(step="case2", outcome=case2, schema_warning=warned[:1], engine_schema="IA0101X", recorded=recorded)
        C.obs(step="post", record_unchanged=c.o.get("^IVG.Deploy", "schema") == recorded)

        if case1 == "refused" and case2 == "accepted" and warned:
            C.verdict("pass", "readable mismatch refused; unreadable record -> WARNING and a mismatched engine is "
                              "accepted (documented fail-open, option a, as built)")
        elif case1 == "refused" and case2 == "refused":
            C.verdict("pass", "readable mismatch refused; unreadable record also refused (fail-closed)")
        else:
            C.verdict("fail", f"case1={case1} case2={case2} warned={bool(warned)}")
    finally:
        c.close()


if __name__ == "__main__":
    main()
