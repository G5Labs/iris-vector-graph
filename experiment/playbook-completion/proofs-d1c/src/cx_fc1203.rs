//! Proved counterexample for control `control_fc1203_prefix_from_node_rows` (F-C1203), compiled only with it.
//!
//! The live trace fu-r04-temporal-only-live-b (case P): a prefix tenant with a node (7) and a temporal-only edge
//! 1 -9-> 4 (predicate 9 registered temporal-only, so the edge has no row and its endpoints no node rows);
//! delete_nodes_by_prefix selects the ids from Graph_KG.nodes only, removes node 7 and leaves the edge, which
//! get_edges_in_window still returns. The erase is not an L1 step (something of the prefix remains).
use vstd::prelude::*;
use actors::protocol::*;
use crate::edge_l1::*;
use crate::edge_l2::*;
use crate::edge_runs::*;

verus! {

pub open spec fn e50() -> Ev { Ev { k: k2(), ts: 50 } }
pub open spec fn sel() -> Set<int> { Set::empty().insert(1int).insert(4int).insert(7int) }
pub open spec fn x0() -> ES2 { e0(reg9()) }
pub open spec fn x1() -> ES2 { p_node(x0(), NK { g: 0, n: 7 }) }
pub open spec fn x2() -> ES2 { p_tinsert(x1(), k2(), 50) }
pub open spec fn x3() -> ES2 { p_enodes(x2(), 0, sel()) }

pub proof fn counterexample_fc1203()
    ensures
        init2(x0()),
        step2(x0(), EL2::CreateNode { nk: NK { g: 0, n: 7 } }, x1()),
        step2(x1(), EL2::TInsert { k: k2(), ts: 50 }, x2()),
        x2().tout.contains(e50()) && !x2().rows.contains_key(k2()) && !x2().nodes.contains(NK { g: 0, n: 1 }),
        step2(x2(), EL2::ENodes { g: 0, sel: sel() }, x3()),
        !step_or_stutter::<EdgeL1>(abse(x2()), labe(EL2::ENodes { g: 0, sel: sel() }), abse(x3())),
        !x3().nodes.contains(NK { g: 0, n: 7 }) && x3().tout.contains(e50()),
{
    lemma_p_node(x0(), NK { g: 0, n: 7 });
    assert(!structural(x1().reg, k2()));
    lemma_p_tinsert(x1(), k2(), 50);
    assert(x2().tout.contains(e50()));
    assert(x2().nodes == x1().nodes);
    lemma_p_enodes(x2(), 0, sel());
    let ids = ids_of(x2(), 0, sel());
    assert(!ids.contains(1));
    assert(!ids.contains(4));
    assert(ids.contains(7));
    assert(!hit(0, ids, k2()));
    assert(x3().tout.contains(e50()));
    assert(hit(0, sel(), k2()));
    assert(!erase_ts(abse(x2()).tev, 0, sel()).contains(e50()));
    assert(!x3().nodes.contains(NK { g: 0, n: 7 }));
}

} // verus!
