//! Module 06 (vectors), L2 part 2: the embed queue over `^EmbedQueue` and the vector rows, with its workers, at pin
//! 3eaa79cf; refinement of `vq_l1` for every step, the invariant, and the controls HD-0604, F-0604, F-C0601.
//!
//! State (production names):
//! - `text`  `^EmbedQueue(node, "text")` (a version stands for the text; Enqueue overwrites it, EmbedQueue.cls:51-58)
//! - `st`    `^EmbedQueue(node, "status")` = PENDING | DONE | ERROR
//! - `rows`  the node's vector row (`INSERT OR UPDATE ... TO_VECTOR`, EmbedQueue.cls:318-325; or the Python
//!           worker's store), as the text version it was made from
//! - `wk`    workers in flight: the IRIS task's `ProcessBatch` (EmbedQueue.cls:258-338) and the Python
//!           `process_embed_queue` (embeddings.py:1900-1990: ClaimPendingBatch, one model call, SetResult); each
//!           works an entry in four steps: claim (read PENDING and the text), embed, write the vector, mark
//! - `lock`  reviewed design only: one worker lock per namespace, held from claim to mark (HD-0604 (b))
//!
//! **Design** (reviewed): a single active consumer (the lock); the mark is ERROR when no vector was made (F-0604
//! remedy) and is written only if the entry's text is still the one the worker read (F-C0601 remedy: a version
//! check). At the pin none holds: ClaimPendingBatch is a plain scan with no claim state (EmbedQueue.cls:22-25,
//! 112-134), ProcessBatch sets DONE whenever no exception was thrown (:307-327), and no mark checks the text.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vq_l1::*;

verus! {

pub enum WPh { Claimed, Embedded, Written }
/// A worker on one entry: the node, the text version it read, whether its model call made a vector, its phase.
pub struct WK { pub node: int, pub ver: nat, pub ok: bool, pub ph: WPh }

pub struct QS2 {
    pub text: Map<int, nat>,
    pub st: Map<int, St>,
    pub rows: Map<int, nat>,
    pub wk: Map<nat, WK>,
    pub lock: Option<nat>,
}

pub enum QL2 {
    Enqueue { node: int },
    Claim { w: nat, node: int },
    Embed { w: nat, ok: bool },
    /// The vector write; `wrote` is the version written (None: no vector was made, nothing written).
    Write { w: nat, node: int, wrote: Option<nat> },
    /// The status write; `out` is the status written (None: nothing written).
    Mark { w: nat, node: int, out: Option<bool> },
}

pub open spec fn hd0604() -> bool { cfg!(feature = "control_hd0604_two_consumers") }
pub open spec fn f0604() -> bool { cfg!(feature = "control_f0604_done_without_vector") }
pub open spec fn fc0601() -> bool { cfg!(feature = "control_fc0601_no_version_check") }

/// What the mark writes: reviewed, the status for this worker's result, only if the text is unchanged.
pub open spec fn mark_out(s: QS2, w: nat) -> Option<bool> {
    let k = s.wk[w];
    if fc0601() || s.text[k.node] == k.ver { Some(f0604() || k.ok) } else { None }
}

pub open spec fn init2(s: QS2) -> bool {
    &&& s.text == Map::<int, nat>::empty() && s.st == Map::<int, St>::empty() && s.rows == Map::<int, nat>::empty()
    &&& s.wk == Map::<nat, WK>::empty() && s.lock is None
}

pub open spec fn step2(s: QS2, l: QL2, t: QS2) -> bool {
    match l {
        QL2::Enqueue { node } =>
            t == QS2 { text: s.text.insert(node, next_ver(s.text, node)), st: s.st.insert(node, St::Pending), ..s },
        QL2::Claim { w, node } => {
            &&& !s.wk.contains_key(w) && s.st.contains_key(node) && s.st[node] is Pending && s.text.contains_key(node)
            &&& (hd0604() || s.lock is None)
            &&& t == QS2 { wk: s.wk.insert(w, WK { node, ver: s.text[node], ok: false, ph: WPh::Claimed }),
                           lock: if hd0604() { s.lock } else { Some(w) }, ..s }
        },
        QL2::Embed { w, ok } => {
            &&& s.wk.contains_key(w) && s.wk[w].ph is Claimed
            &&& t == QS2 { wk: s.wk.insert(w, WK { ok, ph: WPh::Embedded, ..s.wk[w] }), ..s }
        },
        QL2::Write { w, node, wrote } => {
            &&& s.wk.contains_key(w) && s.wk[w].ph is Embedded && s.wk[w].node == node
            &&& wrote == (if s.wk[w].ok { Some(s.wk[w].ver) } else { None })
            &&& t == QS2 { rows: if s.wk[w].ok { s.rows.insert(node, s.wk[w].ver) } else { s.rows },
                           wk: s.wk.insert(w, WK { ph: WPh::Written, ..s.wk[w] }), ..s }
        },
        QL2::Mark { w, node, out } => {
            &&& s.wk.contains_key(w) && s.wk[w].ph is Written && s.wk[w].node == node
            &&& out == mark_out(s, w)
            &&& t == QS2 { st: match out { Some(d) => s.st.insert(node, if d { St::Done } else { St::Error }), None => s.st },
                           wk: s.wk.remove(w), lock: if s.lock == Some(w) { None } else { s.lock }, ..s }
        },
    }
}

// ------------------------------------------------------------------------------------------------ invariant

pub open spec fn inv_dom(s: QS2) -> bool {
    &&& forall|n: int| #[trigger] s.st.contains_key(n) <==> s.text.contains_key(n)
    &&& forall|n: int| #[trigger] s.text.contains_key(n) ==> s.text[n] >= 1
    &&& forall|n: int| #[trigger] s.rows.contains_key(n) ==> s.text.contains_key(n) && 1 <= s.rows[n] <= s.text[n]
}

/// A single active consumer: every worker in flight holds the lock.
pub open spec fn inv_one(s: QS2) -> bool { forall|w: nat| #[trigger] s.wk.contains_key(w) ==> s.lock == Some(w) }

/// A worker in flight works a PENDING entry whose text is at or after the version it read; once written with a
/// vector, the node's row is that version.
pub open spec fn inv_wk(s: QS2) -> bool {
    forall|w: nat| #[trigger] s.wk.contains_key(w) ==> {
        let k = s.wk[w];
        &&& s.text.contains_key(k.node) && 1 <= k.ver <= s.text[k.node]
        &&& s.st[k.node] is Pending
        &&& (k.ph is Written && k.ok ==> s.rows.contains_key(k.node) && s.rows[k.node] == k.ver)
    }
}

pub open spec fn inv06q(s: QS2) -> bool { inv_dom(s) && inv_one(s) && inv_wk(s) }

pub struct QueueL2;

impl Contract for QueueL2 {
    type S = QS2;
    type L = QL2;
    open spec fn init(s: QS2) -> bool { init2(s) }
    open spec fn next(s: QS2, l: QL2, t: QS2) -> bool { inv06q(s) && step2(s, l, t) }
}

pub struct QueueRaw;

impl Contract for QueueRaw {
    type S = QS2;
    type L = QL2;
    open spec fn init(s: QS2) -> bool { init2(s) }
    open spec fn next(s: QS2, l: QL2, t: QS2) -> bool { step2(s, l, t) }
}

// ------------------------------------------------------------------------------------------------ the abstraction

pub open spec fn absq(s: QS2) -> QS1 { QS1 { text: s.text, st: s.st, vec: s.rows } }

pub open spec fn labq(l: QL2) -> Option<QL1> {
    match l {
        QL2::Enqueue { node } => Some(QL1::Enqueue { node }),
        QL2::Claim { w, node } => None,
        QL2::Embed { w, ok } => None,
        QL2::Write { w, node, wrote } => match wrote { Some(v) => Some(QL1::Embed { node, ver: v }), None => None },
        QL2::Mark { w, node, out } => match out { Some(d) => Some(QL1::Mark { node, done: d }), None => None },
    }
}

// ------------------------------------------------------------------------------------------------ step lemmas

proof fn lemma_enqueue(s: QS2, node: int, t: QS2)
    requires inv06q(s), step2(s, QL2::Enqueue { node }, t),
    ensures inv06q(t), step_or_stutter::<QueueL1>(absq(s), labq(QL2::Enqueue { node }), absq(t)),
{
    assert forall|n: int| #[trigger] t.rows.contains_key(n) implies t.text.contains_key(n) && 1 <= t.rows[n] <= t.text[n] by {
        assert(s.rows.contains_key(n));
    }
    assert forall|w: nat| #[trigger] t.wk.contains_key(w) implies {
        let k = t.wk[w];
        &&& t.text.contains_key(k.node) && 1 <= k.ver <= t.text[k.node]
        &&& t.st[k.node] is Pending
        &&& (k.ph is Written && k.ok ==> t.rows.contains_key(k.node) && t.rows[k.node] == k.ver)
    } by {
        assert(s.wk.contains_key(w));
    }
}

proof fn lemma_claim(s: QS2, w: nat, node: int, t: QS2)
    requires inv06q(s), step2(s, QL2::Claim { w, node }, t),
    ensures inv06q(t), step_or_stutter::<QueueL1>(absq(s), labq(QL2::Claim { w, node }), absq(t)),
{
    // a second worker waits for the lock (control HD-0604 fails here)
    assert(s.lock is None);
    assert forall|v: nat| #[trigger] t.wk.contains_key(v) implies t.lock == Some(v) by {
        if v != w { assert(s.wk.contains_key(v)); assert(false); }
    }
    assert forall|v: nat| #[trigger] t.wk.contains_key(v) implies {
        let k = t.wk[v];
        &&& t.text.contains_key(k.node) && 1 <= k.ver <= t.text[k.node]
        &&& t.st[k.node] is Pending
        &&& (k.ph is Written && k.ok ==> t.rows.contains_key(k.node) && t.rows[k.node] == k.ver)
    } by {
        if v != w { assert(s.wk.contains_key(v)); }
    }
}

proof fn lemma_embed(s: QS2, w: nat, ok: bool, t: QS2)
    requires inv06q(s), step2(s, QL2::Embed { w, ok }, t),
    ensures inv06q(t), step_or_stutter::<QueueL1>(absq(s), labq(QL2::Embed { w, ok }), absq(t)),
{
    assert forall|v: nat| #[trigger] t.wk.contains_key(v) implies t.lock == Some(v) by { assert(s.wk.contains_key(v)); }
    assert forall|v: nat| #[trigger] t.wk.contains_key(v) implies {
        let k = t.wk[v];
        &&& t.text.contains_key(k.node) && 1 <= k.ver <= t.text[k.node]
        &&& t.st[k.node] is Pending
        &&& (k.ph is Written && k.ok ==> t.rows.contains_key(k.node) && t.rows[k.node] == k.ver)
    } by {
        assert(s.wk.contains_key(v));
    }
}

proof fn lemma_write(s: QS2, w: nat, node: int, wrote: Option<nat>, t: QS2)
    requires inv06q(s), step2(s, QL2::Write { w, node, wrote }, t),
    ensures inv06q(t), step_or_stutter::<QueueL1>(absq(s), labq(QL2::Write { w, node, wrote }), absq(t)),
{
    let k = s.wk[w];
    assert(s.wk.contains_key(w));
    assert forall|n: int| #[trigger] t.rows.contains_key(n) implies t.text.contains_key(n) && 1 <= t.rows[n] <= t.text[n] by {
        if !(n == node && k.ok) { assert(s.rows.contains_key(n)); }
    }
    assert forall|v: nat| #[trigger] t.wk.contains_key(v) implies t.lock == Some(v) by { assert(s.wk.contains_key(v)); }
    assert forall|v: nat| #[trigger] t.wk.contains_key(v) implies {
        let j = t.wk[v];
        &&& t.text.contains_key(j.node) && 1 <= j.ver <= t.text[j.node]
        &&& t.st[j.node] is Pending
        &&& (j.ph is Written && j.ok ==> t.rows.contains_key(j.node) && t.rows[j.node] == j.ver)
    } by {
        assert(s.wk.contains_key(v));
        if v != w { assert(s.lock == Some(v) && s.lock == Some(w)); }
    }
}

proof fn lemma_mark(s: QS2, w: nat, node: int, out: Option<bool>, t: QS2)
    requires inv06q(s), step2(s, QL2::Mark { w, node, out }, t),
    ensures inv06q(t), step_or_stutter::<QueueL1>(absq(s), labq(QL2::Mark { w, node, out }), absq(t)),
{
    let k = s.wk[w];
    assert(s.wk.contains_key(w));
    if out == Some(true) {
        // DONE only when a vector was made (control F-0604 fails here) ...
        assert(k.ok);
        // ... and from the text the entry still holds (control F-C0601 fails here)
        assert(s.text[node] == k.ver);
        assert(s.rows.contains_key(node) && s.rows[node] == s.text[node]);
    }
    assert forall|n: int| #[trigger] t.st.contains_key(n) <==> t.text.contains_key(n) by {}
    assert forall|v: nat| #[trigger] t.wk.contains_key(v) implies t.lock == Some(v) by {
        assert(s.wk.contains_key(v));
        assert(s.lock == Some(v) && s.lock == Some(w));
    }
    assert forall|v: nat| #[trigger] t.wk.contains_key(v) implies {
        let j = t.wk[v];
        &&& t.text.contains_key(j.node) && 1 <= j.ver <= t.text[j.node]
        &&& t.st[j.node] is Pending
        &&& (j.ph is Written && j.ok ==> t.rows.contains_key(j.node) && t.rows[j.node] == j.ver)
    } by {
        assert(s.wk.contains_key(v));
        assert(s.lock == Some(v) && s.lock == Some(w));
    }
}

proof fn lemma_step(s: QS2, l: QL2, t: QS2)
    requires inv06q(s), step2(s, l, t),
    ensures inv06q(t), step_or_stutter::<QueueL1>(absq(s), labq(l), absq(t)),
{
    match l {
        QL2::Enqueue { node } => lemma_enqueue(s, node, t),
        QL2::Claim { w, node } => lemma_claim(s, w, node, t),
        QL2::Embed { w, ok } => lemma_embed(s, w, ok, t),
        QL2::Write { w, node, wrote } => lemma_write(s, w, node, wrote, t),
        QL2::Mark { w, node, out } => lemma_mark(s, w, node, out, t),
    }
}

impl Refines<QueueL1> for QueueL2 {
    open spec fn abs(s: QS2) -> QS1 { absq(s) }
    open spec fn lab(l: QL2) -> Option<QL1> { labq(l) }
    proof fn init_refines(s: QS2) {}
    proof fn step_refines(s: QS2, l: QL2, t: QS2) { lemma_step(s, l, t); }
}

impl SafeContract for QueueL2 {
    open spec fn inv(s: QS2) -> bool { inv06q(s) }
    proof fn init_safe(s: QS2) {}
    proof fn step_safe(s: QS2, l: QL2, t: QS2) { lemma_step(s, l, t); }
}

// ------------------------------------------------------------------------------------------------ theorems

proof fn lemma_raw_inv_at(states: Seq<QS2>, labels: Seq<QL2>, k: int)
    requires execution::<QueueRaw>(states, labels), 0 <= k < states.len(),
    ensures inv06q(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution every state of which satisfies L1's business invariant.
pub proof fn theorem_raw_executions_refine(states: Seq<QS2>, labels: Seq<QL2>)
    requires execution::<QueueRaw>(states, labels),
    ensures
        execution::<QueueL2>(states, labels),
        abstract_execution::<QueueL1>(Seq::new(states.len(), |i: int| absq(states[i])),
                                      Seq::new(labels.len(), |i: int| labq(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv06q(#[trigger] states[i]) && inv1(absq(states[i])),
{
    assert forall|i: int| 0 <= i < states.len() implies inv06q(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<QueueL2>(states, labels));
    trace_refines::<QueueL2, QueueL1>(states, labels);
    refinement_preserves_safety::<QueueL2, QueueL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absq(states[i])) =~= Seq::new(states.len(), |i: int| <QueueL2 as Refines<QueueL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labq(labels[i])) =~= Seq::new(labels.len(), |i: int| <QueueL2 as Refines<QueueL1>>::lab(labels[i])));
}

/// HD-0604 on the layout: at most one worker is in flight.
pub proof fn theorem_single_consumer(s: QS2, v: nat, w: nat)
    requires inv06q(s), s.wk.contains_key(v), s.wk.contains_key(w),
    ensures v == w,
{
}

} // verus!
