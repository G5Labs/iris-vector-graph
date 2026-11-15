//! Proved counterexample for control `control_f0818_vlp_crosses_graphs` (F-0818), compiled only with it.
//!
//! The live check b-08-live-f0818: an all-graphs variable-length walk from a WITH-carried start followed an edge of one
//! graph from another graph's node of the same id. Here: graph 1 has nodes 5, 6 and 5->6; graph 2 has nodes 6, 7 and
//! 6->7; the walk from (graph 1, node 5) answers 7 (not an L1 step: graph 1 has no path 5 ->* 7).
use vstd::prelude::*;
use actors::protocol::*;
use crate::cys_l1::*;
use crate::cys_l2::*;

verus! {

pub open spec fn s0() -> CS1 { CS1 { nodes: Set::empty(), lab: Set::empty(), edg: Set::empty() } }
pub open spec fn n1() -> CS1 { CS1 { nodes: s0().nodes.insert((1int, 5int)), ..s0() } }
pub open spec fn n2() -> CS1 { CS1 { nodes: n1().nodes.insert((1int, 6int)), ..n1() } }
pub open spec fn n3() -> CS1 { CS1 { nodes: n2().nodes.insert((2int, 6int)), ..n2() } }
pub open spec fn s1() -> CS1 { CS1 { nodes: n3().nodes.insert((2int, 7int)), ..n3() } }
pub open spec fn s2() -> CS1 { CS1 { edg: s1().edg.insert((1int, 5int, 6int)), ..s1() } }
pub open spec fn s3() -> CS1 { CS1 { edg: s2().edg.insert((2int, 6int, 7int)), ..s2() } }

pub proof fn counterexample_f0818()
    ensures
        CsL1::init(s0()),
        step2(s0(), CSL1::WNode { g: 1, n: 5 }, n1()),
        step2(n1(), CSL1::WNode { g: 1, n: 6 }, n2()),
        step2(n2(), CSL1::WNode { g: 2, n: 6 }, n3()),
        step2(n3(), CSL1::WNode { g: 2, n: 7 }, s1()),
        step2(s1(), CSL1::WEdge { g: 1, a: 5, b: 6 }, s2()),
        step2(s2(), CSL1::WEdge { g: 2, a: 6, b: 7 }, s3()),
        step2(s3(), CSL1::Walk { ans: walk2(s3()) }, s3()),
        walk2(s3()).contains((1, 5, 7)),
        !step_or_stutter::<CsL1>(s3(), Some(CSL1::Walk { ans: walk2(s3()) }), s3()),
{
    assert(s1().nodes.contains((1, 5)) && s1().nodes.contains((1, 6)) && s1().nodes.contains((2, 6)) && s1().nodes.contains((2, 7)));
    assert(s3().edg.contains((1, 5, 6)) && s3().edg.contains((2, 6, 7)));
    let x = (1int, 5int, 7int);
    assert(s3().nodes.contains((x.0, x.1)));
    assert(s3().edg.contains((1int, x.1, 6int)) && s3().edg.contains((2int, 6int, x.2)));
    assert(exists|y: int, g1: int, g2: int| #[trigger] s3().edg.contains((g1, x.1, y)) && #[trigger] s3().edg.contains((g2, y, x.2)));
    assert(walk_all(s3()).contains(x));
    assert(!walk_of(s3()).contains((1, 5, 7))) by {
        assert(!s3().edg.contains((1, 5, 7)));
        assert forall|y: int| !(#[trigger] s3().edg.contains((1, 5, y)) && s3().edg.contains((1, y, 7))) by {
            if s3().edg.contains((1, 5, y)) { assert(y == 6); assert(!s3().edg.contains((1, 6, 7))); }
        }
    }
}

} // verus!
