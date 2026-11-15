"""Benign unit check of lead L2 on the pin's ledger/replay.py (no IRIS, no product change)."""
import sys, json
sys.path.insert(0, sys.argv[1])
from iris_vector_graph.ledger.replay import MutationRecord, compute_diff, reconstruct

def rec(seq, op, eid, attr="", prior=None, new=None):
    return MutationRecord(seq=seq, ordinal=0, op=op, entity_kind="node", entity_id=eid, attr=attr, prior=prior, new=new, graph=None)

# revision 1: node n created with prop k=1; revision 2: n deleted; revision 3: n re-created with k=2
r1 = [rec(1, "create_node", "n", new=""), MutationRecord(seq=1, ordinal=1, op="set_prop", entity_kind="node", entity_id="n", attr="k", prior=None, new="1", graph=None)]
r2 = [rec(2, "delete_node", "n", prior="")]
r3 = [rec(3, "create_node", "n", new=""), MutationRecord(seq=3, ordinal=1, op="set_prop", entity_kind="node", entity_id="n", attr="k", prior=None, new="2", graph=None)]
fwd = compute_diff(r2 + r3)      # the range (1, 3]
inv = fwd.inverse()
out = {"forward": [e.to_wire() for e in fwd.entries], "inverse": [e.to_wire() for e in inv.entries]}
# apply each as an ordered script to a node-existence/props state, to see whether order matters
def apply(state, entries):
    st = {k: dict(v) for k, v in state.items()}
    log = []
    for e in entries:
        nid, attr, before, after = e.entity_id, e.attr, e.before, e.after
        if attr == "":
            if after is None:
                if nid not in st: log.append(f"delete of absent {nid}")
                st.pop(nid, None)
            else:
                if nid in st: log.append(f"create of present {nid}")
                st[nid] = {}
        else:
            if nid not in st: log.append(f"set on absent {nid}")
            st.setdefault(nid, {})[attr] = after
    return st, log
s1 = {"n": {"prop:k": "1"}}
s3, log_f = apply(s1, fwd.entries)
s1b, log_i = apply(s3, inv.entries)
out.update({"state_at_1": s1, "forward_applied_to_1": s3, "forward_log": log_f, "inverse_applied_to_3": s1b, "inverse_log": log_i})
print(json.dumps(out, indent=1))
