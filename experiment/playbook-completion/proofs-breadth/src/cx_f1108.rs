//! Proved counterexample for control `control_f1108_unguarded_bulk_delete` (F-1108), compiled only with it.
//!
//! Strict mode is on; bulk_delete_adjacency (no guard call, nodes_edges.py:2301-2339) erases an edge row and its
//! statement entry: a governed write landing while the ledger is enabled in strict mode, not an L1 step.
use vstd::prelude::*;
use actors::protocol::*;
use crate::ledger_l1::*;
use crate::ledger_l2::*;
use crate::cx_ledger_common::*;

verus! {

pub open spec fn e1() -> K { K { id: 1, edge: true } }
pub open spec fn l2() -> L2Label { L2Label::EngineWrite { w: Wr::BulkDeleteAdj, k: e1(), v: None, landed: true } }
pub open spec fn c2() -> LS2 { engine_write(c_genesis(true), Wr::BulkDeleteAdj, e1(), None) }

pub proof fn counterexample_f1108()
    ensures
        init2(c_init()),
        step2(c_init(), L2Label::Enable { strict: true, id: 1, recs: seq![], busy: false }, c_genesis(true)),
        step2(c_genesis(true), l2(), c2()),
        strict_on(c_genesis(true).meta) && c2().drift.contains(e1()),
        !step_or_stutter::<L1>(abs11(c_genesis(true)), lab11(l2()), abs11(c2())),
{
    lemma_genesis_step(true);
    assert(!refuses(c_genesis(true), Wr::BulkDeleteAdj));
    assert(step2(c_genesis(true), l2(), c2()));
}

} // verus!
