//! Proved counterexample for control `control_f0802_shortcut_unscoped` (F-0802), compiled only with it.
//!
//! The live check b-08-live-f0802: under USE GRAPH 'b08gA' the count UNION query answered the whole namespace's
//! counts. Here: node 5 in graph 1 and node 6 in graph 2; the shortcut under USE GRAPH 1 counts both (not an L1 step).
use vstd::prelude::*;
use actors::protocol::*;
use crate::cys_l1::*;
use crate::cys_l2::*;

verus! {

pub open spec fn s0() -> CS1 { CS1 { nodes: Set::empty(), lab: Set::empty(), edg: Set::empty() } }
pub open spec fn s1() -> CS1 { CS1 { nodes: s0().nodes.insert((1int, 5int)), ..s0() } }
pub open spec fn s2() -> CS1 { CS1 { nodes: s1().nodes.insert((2int, 6int)), ..s1() } }

pub proof fn counterexample_f0802()
    ensures
        CsL1::init(s0()),
        step2(s0(), CSL1::WNode { g: 1, n: 5 }, s1()),
        step2(s1(), CSL1::WNode { g: 2, n: 6 }, s2()),
        step2(s2(), CSL1::Counts { g: 1, ans: counts2(s2(), 1) }, s2()),
        counts2(s2(), 1).0.contains((2, 6)),
        !step_or_stutter::<CsL1>(s2(), Some(CSL1::Counts { g: 1, ans: counts2(s2(), 1) }), s2()),
{
    assert(s2().nodes.contains((2, 6)));
    assert(!counts_of(s2(), 1).0.contains((2, 6)));
}

} // verus!
