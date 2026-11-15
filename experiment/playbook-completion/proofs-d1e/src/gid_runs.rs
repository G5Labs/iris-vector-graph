//! The module 02 names-and-readers L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::gid_l1::*;
use crate::gid_l2::*;

verus! {

pub open spec fn g0() -> GS2 { GS2 { nodes_t: Set::empty(), labels_t: Set::empty(), props_t: Set::empty() } }

pub proof fn lemma_g_steps(s: GS2, g: int, n: int, l: int, k: int)
    ensures
        accepts(g) && !s.nodes_t.contains(NK { g, n }) ==> step2(s, GL2::CreateNode { g, n, l, k, ok: true }, add2(s, g, n, l, k)),
        step2(s, GL2::CreateNode { g, n, l, k, ok: false }, s),
        valid(g) ==> step2(s, GL2::EraseGraph { g }, erase2(s, g)),
{
}

} // verus!
