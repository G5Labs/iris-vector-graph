//! Proved counterexample for control `control_f0206_hydrate_from_default` (F-0206), compiled only with it.
//!
//! The live probes breadth-a-live-02-identity (p0206_cross_graph_hydration) and intent-a-hd0201-unscoped-readers
//! (get_nodes_by_label answered a node hydrated from the default graph with labels it holds there, not the label
//! asked): id 1 holds label 10 in graph 1 and label 11 in the default graph; get_nodes_by_label(10) answers id 1 with
//! labels {11}, which is not an L1 step (the default graph holds no node with label 10).
use vstd::prelude::*;
use actors::protocol::*;
use crate::gid_l1::*;
use crate::gid_l2::*;
use crate::gid_runs::*;

verus! {

pub open spec fn c1() -> GS2 { add2(g0(), 1, 1, 10, 20) }
pub open spec fn c2() -> GS2 { add2(c1(), 0, 1, 11, 21) }
pub open spec fn hd() -> Hyd { Hyd { labels: Set::empty().insert(11int), props: Set::empty().insert(21int) } }
pub open spec fn ans() -> Map<int, Hyd> { Map::empty().insert(1int, hd()) }

pub proof fn counterexample_f0206()
    ensures
        init2(g0()),
        step2(g0(), GL2::CreateNode { g: 1, n: 1, l: 10, k: 20, ok: true }, c1()),
        step2(c1(), GL2::CreateNode { g: 0, n: 1, l: 11, k: 21, ok: true }, c2()),
        step2(c2(), GL2::NodesByLabel { l: 10, ans: ans() }, c2()),
        !step_or_stutter::<GidL1>(absg(c2()), labg(GL2::NodesByLabel { l: 10, ans: ans() }), absg(c2())),
{
    lemma_g_steps(g0(), 1, 1, 10, 20);
    lemma_g_steps(c1(), 0, 1, 11, 21);
    let s = c2();
    assert(s.labels_t.contains(LK { g: 1, n: 1, l: 10 }));
    assert(s.labels_t.contains(LK { g: 0, n: 1, l: 11 }));
    assert(s.props_t.contains(PK { g: 0, n: 1, k: 21 }));
    assert forall|n: int| ans().contains_key(n) <==> ids_of(s, 10, n) && kept(s, n) by {
        if n == 1 { assert(kept(s, 1)); assert(s.labels_t.contains(LK { g: 1, n: 1, l: 10 })); }
        if ids_of(s, 10, n) { let g = choose|g: int| s.labels_t.contains(LK { g, n, l: 10 }); assert(n == 1); }
    }
    assert forall|x: int| hd().labels.contains(x) <==> s.labels_t.contains(LK { g: 0, n: 1, l: x }) by {}
    assert forall|k: int| hd().props.contains(k) <==> s.props_t.contains(PK { g: 0, n: 1, k }) by {}
    assert(hyd2(s, 1, ans()[1]));
    assert(bylabel2(s, 10, ans()));
    assert(!s.labels_t.contains(LK { g: 0, n: 1, l: 10 }));
    assert(absg(s).labels == s.labels_t);
    if bylabel1(absg(s), 10, ans()) { assert(ans().contains_key(1)); assert(false); }
}

} // verus!
