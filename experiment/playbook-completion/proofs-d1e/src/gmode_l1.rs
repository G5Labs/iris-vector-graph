//! Module 02 (graph identity), L1 part 2: multigraph mode for one triple of one graph (spec 234), as a business
//! contract.
//!
//! State: the triple's edges `keys` (by edge identity) and the graph's mode `multi`. Labels: `SetOn`, `SetOff{ok}`
//! (GraphMode.Set(g, 0): refused while the triple has parallel edges), `Single{k, added}` (a single-edge writer:
//! create_edge, store_edge, a Cypher CREATE in mode off), `Parallel{k}` (a Cypher CREATE in multigraph mode adds a
//! parallel edge), `Delete{k}` (Cypher's per-edge DELETE). Business rule (spec 234 FR-002, GID-I4.10): **a graph
//! whose mode is off never holds two edges of one triple**: a single-edge writer adds an edge only to a triple that
//! has none, and only multigraph mode adds a parallel edge.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct MS1 { pub keys: Set<int>, pub multi: bool }

pub enum ML1 {
    SetOn,
    SetOff { ok: bool },
    Single { k: int, added: bool },
    Parallel { k: int },
    Delete { k: int },
}

pub open spec fn next1(s: MS1, l: ML1, t: MS1) -> bool {
    match l {
        ML1::SetOn => t == (MS1 { multi: true, ..s }),
        ML1::SetOff { ok } => if ok { s.keys.len() <= 1 && t == (MS1 { multi: false, ..s }) } else { t == s },
        ML1::Single { k, added } =>
            if added { s.keys == Set::<int>::empty() && t == (MS1 { keys: s.keys.insert(k), ..s }) } else { t == s },
        ML1::Parallel { k } => s.multi && !s.keys.contains(k) && t == (MS1 { keys: s.keys.insert(k), ..s }),
        ML1::Delete { k } => s.keys.contains(k) && t == (MS1 { keys: s.keys.remove(k), ..s }),
    }
}

pub struct ModeL1;

impl Contract for ModeL1 {
    type S = MS1;
    type L = ML1;
    open spec fn init(s: MS1) -> bool { s.keys == Set::<int>::empty() && !s.multi }
    open spec fn next(s: MS1, l: ML1, t: MS1) -> bool { next1(s, l, t) }
}

/// GID-I4.10: mode off, at most one edge of the triple.
pub open spec fn inv1(s: MS1) -> bool { !s.multi ==> s.keys.len() <= 1 }

pub proof fn lemma_l1_safe(s: MS1, l: ML1, t: MS1)
    requires inv1(s), next1(s, l, t),
    ensures inv1(t),
{
}

impl SafeContract for ModeL1 {
    open spec fn inv(s: MS1) -> bool { inv1(s) }
    proof fn init_safe(s: MS1) {}
    proof fn step_safe(s: MS1, l: ML1, t: MS1) { lemma_l1_safe(s, l, t); }
}

/// Spec 234 FR-002: in a graph whose mode is off, no step makes a triple hold two edges.
pub proof fn theorem_mode_off_single_edge(s: MS1, l: ML1, t: MS1)
    requires inv1(s), next1(s, l, t), !t.multi,
    ensures t.keys.len() <= 1,
{
    lemma_l1_safe(s, l, t);
}

/// A single-edge writer never adds a parallel edge, whatever the mode.
pub proof fn theorem_single_writer_never_parallel(s: MS1, k: int, added: bool, t: MS1)
    requires next1(s, ML1::Single { k, added }, t),
    ensures t.keys.len() <= 1 || t == s,
{
}

} // verus!
