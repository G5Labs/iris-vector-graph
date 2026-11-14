//! Proved counterexample for control `control_f0906_gate_edge_index_only` (F-0906), compiled only with it.
//!
//! The explorer model m09-gate-as-built (reproduced in the model; the edge-only state was not created live, it needs
//! dropping a product index): with idx_edges_adj functional and idx_labels_adj not (ensure_adjacency_index failing
//! between its two declarations), a label write keeps only the row; the gate opens and the native read answers labels
//! from ^KG. Here: label (5, 7) is written; the native label read answers no label (not an L1 step).
use vstd::prelude::*;
use actors::protocol::*;
use crate::nread_l1::*;
use crate::nread_l2::*;
use crate::nread_runs::*;

verus! {

pub open spec fn hs() -> Set<int> { Set::empty().insert(3int) }
pub open spec fn g0() -> NR2 { r0(hs(), true, false, Map::empty()) }
pub open spec fn g1() -> NR2 { p_lwrite(g0(), 5, 7) }

pub proof fn counterexample_f0906()
    ensures
        init2(g0()),
        step2(g0(), NRL2::LWrite { n: 5, l: 7 }, g1()),
        step2(g1(), NRL2::RunLabels { p: 0, u: 3, ans: g1().kg }, after_run(g1(), 0, 3)),
        g1().labs.contains((5, 7)) && !g1().kg.contains((5, 7)),
        !step_or_stutter::<NrL1>(absr(g1()), labr(NRL2::RunLabels { p: 0, u: 3, ans: g1().kg }), absr(after_run(g1(), 0, 3))),
{
    lemma_r_steps(g0(), 0, 3, 0, 5, 7);
    lemma_r_steps(g1(), 0, 3, 0, 5, 7);
    assert(g1().held.contains(3));
    assert(g1().labs.contains((5, 7)));
    assert(!g1().kg.contains((5, 7)));
}

} // verus!
