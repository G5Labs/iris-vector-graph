//! Proved counterexample for control `control_f0202_writer_skips_name_check` (F-0202), compiled only with it.
//!
//! The live probe breadth-a-live-02-identity (p0202_reserved_name_writers: create_node and store_node wrote 2 node
//! rows under graph name "0"; delete_node and node_count refused the name): create_node under the reserved name is
//! not an L1 step; afterwards a node row is held by a graph whose index key is the default graph's (0) and that no
//! erase accepts.
use vstd::prelude::*;
use actors::protocol::*;
use crate::gid_l1::*;
use crate::gid_l2::*;
use crate::gid_runs::*;

verus! {

pub open spec fn c1() -> GS2 { add2(g0(), -1, 1, 10, 20) }

pub proof fn counterexample_f0202()
    ensures
        init2(g0()),
        step2(g0(), GL2::CreateNode { g: -1, n: 1, l: 10, k: 20, ok: true }, c1()),
        !step_or_stutter::<GidL1>(absg(g0()), labg(GL2::CreateNode { g: -1, n: 1, l: 10, k: 20, ok: true }), absg(c1())),
        c1().nodes_t.contains(NK { g: -1, n: 1 }) && ikey(-1) == 0,
        forall|t: GS2| !#[trigger] step2(c1(), GL2::EraseGraph { g: -1 }, t),
{
    lemma_g_steps(g0(), -1, 1, 10, 20);
}

} // verus!
