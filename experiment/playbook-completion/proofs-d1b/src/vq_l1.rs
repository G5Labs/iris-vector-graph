//! Module 06 (vectors), L1 part 2: the embed queue's requests and answers (HD-0604; F-0604, F-C0601; VEC-I7.18,
//! VEC-Q7.24).
//!
//! State, per node id (node-keyed entries, reqId = node id: EmbedQueue.cls:18-19): the current request's text
//! version `text` (one version per `Enqueue`; a re-enqueue overwrites the text, EmbedQueue.cls:35-60), its status
//! `st` (PENDING / DONE / ERROR), and `vec`: the text version the node's stored vector was made from.
//!
//! Business rules (transition rules; `inv1` is their consequence):
//! - **an entry is DONE only with a vector made from its current text** (VEC-I7.18; the enqueue docstring: the
//!   latest request is the one to honour, F-C0601): `Mark{done: true}` needs `vec == text`;
//! - **each request is answered once, by one worker** (HD-0604: single active consumer, maintainer commit 5bb149ed):
//!   `Mark` needs the entry PENDING, and a worker stores a vector only for a PENDING request (`Embed`);
//! - a vector is made from a text that was enqueued for the node (`ver <= text`).
//!
//! Not modelled: free-text entries (`txt:<n>`), graphs and routes (the Enqueue refusal across graphs), ClearDone,
//! the identity registry (F-0603), timing.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub enum St { Pending, Done, Error }

pub struct QS1 {
    pub text: Map<int, nat>,
    pub st: Map<int, St>,
    pub vec: Map<int, nat>,
}

pub enum QL1 {
    /// enqueue_for_embedding / Graph.KG.EmbedQueue.Enqueue: a new request (text version) for the node.
    Enqueue { node: int },
    /// A vector made from text version `ver` is stored for the node.
    Embed { node: int, ver: nat },
    /// The request is answered: DONE or ERROR.
    Mark { node: int, done: bool },
}

pub open spec fn next_ver(text: Map<int, nat>, node: int) -> nat {
    if text.contains_key(node) { (text[node] + 1) as nat } else { 1 }
}

pub struct QueueL1;

impl Contract for QueueL1 {
    type S = QS1;
    type L = QL1;

    open spec fn init(s: QS1) -> bool {
        s.text == Map::<int, nat>::empty() && s.st == Map::<int, St>::empty() && s.vec == Map::<int, nat>::empty()
    }

    open spec fn next(s: QS1, l: QL1, t: QS1) -> bool {
        match l {
            QL1::Enqueue { node } =>
                t == QS1 { text: s.text.insert(node, next_ver(s.text, node)), st: s.st.insert(node, St::Pending), ..s },
            QL1::Embed { node, ver } => {
                &&& s.st.contains_key(node) && s.st[node] is Pending
                &&& s.text.contains_key(node) && 1 <= ver <= s.text[node]
                &&& t == QS1 { vec: s.vec.insert(node, ver), ..s }
            },
            QL1::Mark { node, done } => {
                &&& s.st.contains_key(node) && s.st[node] is Pending
                &&& (done ==> s.vec.contains_key(node) && s.vec[node] == s.text[node])
                &&& t == QS1 { st: s.st.insert(node, if done { St::Done } else { St::Error }), ..s }
            },
        }
    }
}

pub open spec fn inv1(s: QS1) -> bool {
    &&& forall|n: int| #[trigger] s.st.contains_key(n) <==> s.text.contains_key(n)
    &&& forall|n: int| #[trigger] s.text.contains_key(n) ==> s.text[n] >= 1
    &&& forall|n: int| #[trigger] s.vec.contains_key(n) ==> s.text.contains_key(n) && 1 <= s.vec[n] <= s.text[n]
    &&& forall|n: int| #[trigger] s.st.contains_key(n) && s.st[n] is Done ==> s.vec.contains_key(n) && s.vec[n] == s.text[n]
}

impl SafeContract for QueueL1 {
    open spec fn inv(s: QS1) -> bool { inv1(s) }

    proof fn init_safe(s: QS1) {}

    proof fn step_safe(s: QS1, l: QL1, t: QS1) {
        match l {
            QL1::Enqueue { node } => {
                assert forall|n: int| #[trigger] t.vec.contains_key(n) implies t.text.contains_key(n) && 1 <= t.vec[n] <= t.text[n] by {
                    assert(s.vec.contains_key(n));
                }
            }
            QL1::Embed { node, ver } => {}
            QL1::Mark { node, done } => {}
        }
    }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// VEC-I7.18 and the re-enqueue rule: a DONE entry's vector was made from its current text.
pub proof fn theorem_done_has_current_vector(s: QS1, n: int)
    requires inv1(s), s.st.contains_key(n), s.st[n] is Done,
    ensures s.vec.contains_key(n), s.vec[n] == s.text[n],
{
}

/// HD-0604: a request is answered once: after a mark the entry is not PENDING, and only a new `Enqueue` of that node
/// makes it PENDING again (so no second worker's mark or vector lands on an answered request).
pub proof fn theorem_answered_once(s: QS1, l: QL1, t: QS1, n: int)
    requires QueueL1::next(s, l, t), s.st.contains_key(n), !(s.st[n] is Pending), t.st.contains_key(n), t.st[n] is Pending,
    ensures l == (QL1::Enqueue { node: n }),
{
}

/// HD-0604: no vector is stored for, and no mark lands on, an entry that is not PENDING.
pub proof fn theorem_no_work_on_answered_entry(s: QS1, l: QL1, t: QS1, n: int)
    requires QueueL1::next(s, l, t), s.st.contains_key(n), !(s.st[n] is Pending),
    ensures l != (QL1::Mark { node: n, done: true }), l != (QL1::Mark { node: n, done: false }),
            forall|v: nat| l != (QL1::Embed { node: n, ver: v }),
{
}

} // verus!
