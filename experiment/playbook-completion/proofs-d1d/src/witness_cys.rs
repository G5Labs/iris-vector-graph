//! Non-vacuity of the reviewed cys model (compiled without its controls): from the initial state, two graphs come to
//! share node id 6; each scoped read answers its graph's rows; the walk from (1, 5) answers 6 and not 7.
use vstd::prelude::*;
use actors::protocol::*;
use crate::cys_l1::*;
use crate::cys_l2::*;

verus! {

pub open spec fn s0() -> CS1 { CS1 { nodes: Set::empty(), lab: Set::empty(), edg: Set::empty() } }
pub open spec fn n1() -> CS1 { CS1 { nodes: s0().nodes.insert((1int, 5int)), ..s0() } }
pub open spec fn n2() -> CS1 { CS1 { nodes: n1().nodes.insert((1int, 6int)), ..n1() } }
pub open spec fn n3() -> CS1 { CS1 { nodes: n2().nodes.insert((2int, 6int)), ..n2() } }
pub open spec fn n4() -> CS1 { CS1 { nodes: n3().nodes.insert((2int, 7int)), ..n3() } }
pub open spec fn n5() -> CS1 { CS1 { lab: n4().lab.insert((2int, 6int, 8int)), ..n4() } }
pub open spec fn n6() -> CS1 { CS1 { edg: n5().edg.insert((1int, 5int, 6int)), ..n5() } }
pub open spec fn s3() -> CS1 { CS1 { edg: n6().edg.insert((2int, 6int, 7int)), ..n6() } }

pub proof fn witness_cys()
    ensures
        CsL1::init(s0()),
        step2(s0(), CSL1::WNode { g: 1, n: 5 }, n1()),
        step2(n1(), CSL1::WNode { g: 1, n: 6 }, n2()),
        step2(n2(), CSL1::WNode { g: 2, n: 6 }, n3()),
        step2(n3(), CSL1::WNode { g: 2, n: 7 }, n4()),
        step2(n4(), CSL1::WLab { g: 2, n: 6, l: 8 }, n5()),
        step2(n5(), CSL1::WEdge { g: 1, a: 5, b: 6 }, n6()),
        step2(n6(), CSL1::WEdge { g: 2, a: 6, b: 7 }, s3()),
        step2(s3(), CSL1::Labels { g: 1, ans: Set::empty() }, s3()),
        step2(s3(), CSL1::Counts { g: 2, ans: counts2(s3(), 2) }, s3()),
        counts2(s3(), 2).0.contains((2, 7)) && !counts2(s3(), 2).0.contains((1, 5)),
        step2(s3(), CSL1::Walk { ans: walk2(s3()) }, s3()),
        walk2(s3()).contains((1, 5, 6)) && !walk2(s3()).contains((1, 5, 7)),
{
    assert(n4().nodes.contains((2, 6)) && n5().nodes.contains((1, 5)) && n5().nodes.contains((1, 6)) && n6().nodes.contains((2, 7)));
    assert(labels_of(s3(), 1) =~= Set::<(int, int, int)>::empty());
    assert(s3().nodes.contains((2, 7)) && s3().nodes.contains((1, 5)));
    assert(s3().edg.contains((1, 5, 6)));
    assert(walk_of(s3()).contains((1, 5, 6)));
    assert(!walk_of(s3()).contains((1, 5, 7))) by {
        assert(!s3().edg.contains((1, 5, 7)));
        assert forall|y: int| !(#[trigger] s3().edg.contains((1, 5, y)) && s3().edg.contains((1, y, 7))) by {
            if s3().edg.contains((1, 5, y)) { assert(y == 6); assert(!s3().edg.contains((1, 6, 7))); }
        }
    }
}

} // verus!
