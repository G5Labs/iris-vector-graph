//! Proved counterexample for control `control_f0106_keys_join_on_id` (F-0106), compiled only with it.
//!
//! The live probe breadth-a-live-01-install (p0106_property_keys_cross_graph: graph B's key listed under graph A's
//! label): id 1 holds label 10 and key 20 in the default graph and key 21 in graph 1; get_property_keys(10) answers
//! {20, 21}, which is not an L1 step (no node with label 10 holds key 21 in its own graph).
use vstd::prelude::*;
use actors::protocol::*;
use crate::gid_l1::*;
use crate::gid_l2::*;
use crate::gid_runs::*;

verus! {

pub open spec fn c1() -> GS2 { add2(g0(), 0, 1, 10, 20) }
pub open spec fn c2() -> GS2 { add2(c1(), 1, 1, 11, 21) }
pub open spec fn ks() -> Set<int> { Set::empty().insert(20int).insert(21int) }

pub proof fn counterexample_f0106()
    ensures
        init2(g0()),
        step2(g0(), GL2::CreateNode { g: 0, n: 1, l: 10, k: 20, ok: true }, c1()),
        step2(c1(), GL2::CreateNode { g: 1, n: 1, l: 11, k: 21, ok: true }, c2()),
        step2(c2(), GL2::PropertyKeys { l: 10, keys: ks() }, c2()),
        !step_or_stutter::<GidL1>(absg(c2()), labg(GL2::PropertyKeys { l: 10, keys: ks() }), absg(c2())),
{
    lemma_g_steps(g0(), 0, 1, 10, 20);
    lemma_g_steps(c1(), 1, 1, 11, 21);
    let s = c2();
    assert(s.labels_t.contains(LK { g: 0, n: 1, l: 10 }));
    assert(s.props_t.contains(PK { g: 0, n: 1, k: 20 }));
    assert(s.props_t.contains(PK { g: 1, n: 1, k: 21 }));
    assert forall|k: int| ks().contains(k) <==> (exists|g1: int, g2: int, n: int|
        s.labels_t.contains(LK { g: g1, n, l: 10 }) && s.props_t.contains(PK { g: g2, n, k })) by {
        if k == 20 { assert(s.labels_t.contains(LK { g: 0, n: 1, l: 10 }) && s.props_t.contains(PK { g: 0, n: 1, k: 20 })); }
        if k == 21 { assert(s.labels_t.contains(LK { g: 0, n: 1, l: 10 }) && s.props_t.contains(PK { g: 1, n: 1, k: 21 })); }
    }
    assert(keys2(s, 10, ks()));
    // key 21 is not held, in its own graph, by a node with label 10
    assert(!(exists|g: int, n: int| s.labels_t.contains(LK { g, n, l: 10 }) && s.props_t.contains(PK { g, n, k: 21 })));
    assert(absg(s).labels == s.labels_t && absg(s).props == s.props_t);
    if keys1(absg(s), 10, ks()) { assert(ks().contains(21)); assert(false); }
}

} // verus!
