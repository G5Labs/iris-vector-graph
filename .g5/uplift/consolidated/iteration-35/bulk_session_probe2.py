"""W41 second probe: pending_sync on the loading engine vs an observer engine (run-isolated retest fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W41_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def main():
    c = runtime.connect(); e = runtime.engine(c); o = runtime.connect(); O = runtime.engine(o); out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    ps = lambda: {"loading": e.status().pending_sync, "observer": O.status().pending_sync}
    def session(p, pred):
        with e.bulk_load_session() as s:
            s.add_nodes([{"id": f"{p}{x}", "labels": ["BS"], "properties": {}} for x in "ab"]); s.add_edges([(f"{p}a", f"{p}b", pred)])
    out["cases"]["start"] = ps()
    session(f"bt{TAG}1", "BT1"); out["cases"]["S1_after_session"] = ps()
    cur = c.cursor(); cur.execute("START TRANSACTION"); session(f"bt{TAG}2", "BT2"); out["cases"]["S2_inside_before_commit"] = ps(); cur.execute("COMMIT")
    out["cases"]["S2_after_commit"] = ps(); e.sync(); out["cases"]["S2_after_sync"] = ps()
    cur.execute("START TRANSACTION"); session(f"bt{TAG}3", "BT3"); cur.execute("ROLLBACK"); out["cases"]["S3_after_rollback"] = ps()
    e.sync(); out["cases"]["S3_after_sync"] = ps()
    for x in (c, o): x.close()
    path = HERE / f"bulk-session-observed2-{RUN}.json"; path.write_text(json.dumps(out, indent=1) + "\n"); print(path)
    for k, v in out["cases"].items(): print("==", k, v)
if __name__ == "__main__":
    main()
