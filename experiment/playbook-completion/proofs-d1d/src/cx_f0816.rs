//! Proved counterexample for control `control_f0816_dblabels_unscoped` (F-0816), compiled only with it.
//!
//! The live check b-08-live-f0816: under USE GRAPH 'b08gA', CALL db.labels() listed B08B, a label only graph b08gB
//! has. Here: node 5 of graph 1 has label 7 and node 6 of graph 2 has label 8; db.labels() under USE GRAPH 1 lists
//! label 8's row (not an L1 step).
use vstd::prelude::*;
use actors::protocol::*;
use crate::cys_l1::*;
use crate::cys_l2::*;

verus! {

pub open spec fn s0() -> CS1 { CS1 { nodes: Set::empty(), lab: Set::empty(), edg: Set::empty() } }
pub open spec fn s1() -> CS1 { CS1 { nodes: s0().nodes.insert((1int, 5int)).insert((2int, 6int)), ..s0() } }
pub open spec fn s2() -> CS1 { CS1 { lab: s1().lab.insert((1int, 5int, 7int)), ..s1() } }
pub open spec fn s3() -> CS1 { CS1 { lab: s2().lab.insert((2int, 6int, 8int)), ..s2() } }

pub proof fn counterexample_f0816()
    ensures
        CsL1::init(s0()),
        step2(s0(), CSL1::WNode { g: 1, n: 5 }, CS1 { nodes: s0().nodes.insert((1int, 5int)), ..s0() }),
        step2(CS1 { nodes: s0().nodes.insert((1int, 5int)), ..s0() }, CSL1::WNode { g: 2, n: 6 }, s1()),
        step2(s1(), CSL1::WLab { g: 1, n: 5, l: 7 }, s2()),
        step2(s2(), CSL1::WLab { g: 2, n: 6, l: 8 }, s3()),
        step2(s3(), CSL1::Labels { g: 1, ans: labels2(s3(), 1) }, s3()),
        labels2(s3(), 1).contains((2, 6, 8)),
        !step_or_stutter::<CsL1>(s3(), Some(CSL1::Labels { g: 1, ans: labels2(s3(), 1) }), s3()),
{
    assert(s1().nodes.contains((1, 5)) && s1().nodes.contains((2, 6)));
    assert(s3().lab.contains((2, 6, 8)));
    assert(!labels_of(s3(), 1).contains((2, 6, 8)));
}

} // verus!
