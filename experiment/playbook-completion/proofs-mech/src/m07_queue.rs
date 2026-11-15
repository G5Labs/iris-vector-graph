//! M-07 Background job and queue (AX-14, AX-12, AX-11): three sub-machines, each generic over its own trait.
//!
//! The machines are the semantics lane's `models/semantics/src/queue.rs` (read at commit b0433157, working tree of
//! 2026-11-14) restated in Verus:
//! 1. Entry (`QueueEntryPolicy` / `QueueEntryObject`; laws M07-L1, M07-L2): one queue entry and two workers (claim a
//!    PENDING entry with its text, make the result (may fail), write it, mark). `mark`: `Always` marks DONE whenever no
//!    exception was thrown (EmbedQueue.cls:326-327, F-0604), `IfMade` marks ERROR when no result was made; `cas`: the
//!    mark applies only if the text was not re-enqueued meanwhile (without it, F-C0601); `single`: a lock from claim to
//!    mark (the single-consumer premise HD-0604, unenforced at the pin: F-C0670). The explorer's bounds (4 works, one
//!    re-enqueue) are dropped: the laws are proved for any number of claims and re-enqueues.
//! 2. Order (`QueueOrderPolicy` / `QueueOrderObject`; laws M07-L3 and the service part of M07-L4): three node ids
//!    (0, 1 low-collating, 2 high); Enqueue puts an id that is not pending at the end of the queue (id 2 at most once,
//!    the explorer's `high_enqueued`); Serve takes the entry at the policy's index (`pick`: MinId = the first minimal
//!    id, ClaimPendingBatch / ProcessBatch scanning $Order(^EmbedQueue), EmbedQueue.cls:112-133, 258-268, as built,
//!    F-C0605; Fifo = index 0, reviewed; Lifo = the last, control). Ghost `overtakes`: entries served while id 2 is
//!    pending (saturating at 3, as in the explorer). Unbounded as in the explorer (low ids may arrive forever).
//! 3. Resume (`ResumePolicy` / `ResumeObject`; the resume part of M07-L4): a redaction run over three target records,
//!    each call scans one record from the position the policy resumes at (`Restart`: the first record, as built,
//!    LedgerRedact.cls:185-240, F-C1303; `Persist`: the saved cursor, reviewed).
//!
//! Laws (MECHANISMS.md M-07): M07-L1 (invariant) done means done: DONE only with a result made from the current
//! text (or a worker still at work); M07-L2 (invariant) one worker per entry; M07-L3 (invariant) bounded overtaking:
//! overtakes <= N-1 = 2; M07-L4 (progress) under weak fairness of the worker every pending entry is served, and a
//! resumed run can always finish.
//!
//! Obligations (trait proof functions): Entry L1 the mark is IfMade, guarded by the text (cas) and the entry has a
//! single consumer; Entry L2 single consumer; Order L3 and L4 the policy serves the oldest pending entry (index 0
//! of the arrival-ordered queue); Resume L4 a call resumes at the persisted cursor.
//!
//! Fairness premises (explicit hypotheses of the progress theorems, never assumed): Order: the execution is infinite
//! and the worker is weakly fair (whenever id 2 is pending, a Serve step occurs later); Resume: the run is resumed
//! (called) at least as many more times as records remain.
use vstd::prelude::*;
use crate::exec::*;

verus! {

// ================================================================================================ 1. Entry

pub enum Mark { Always, IfMade }
pub struct EntryCfg { pub mark: Mark, pub cas: bool, pub single: bool }
pub enum St { Pending, Done, Error }
pub enum Wk { Idle, Claimed(nat), Made(nat, bool), Written(nat, bool) }

pub struct ES {
    pub status: St,
    pub text: nat,
    pub vec: Option<nat>,
    pub w0: Wk,
    pub w1: Wk,
    pub lock: Option<nat>,
    pub enqueues: nat,
    pub works: nat,
}

pub enum EA { Claim(nat), Make(nat, bool), Write(nat), MarkStep(nat), Enqueue }

pub trait QueueEntryPolicy: Sized {
    spec fn entry_cfg() -> EntryCfg;
}

pub open spec fn entry_s0() -> ES {
    ES { status: St::Pending, text: 0, vec: None, w0: Wk::Idle, w1: Wk::Idle, lock: None, enqueues: 0, works: 0 }
}

pub open spec fn wk(s: ES, i: nat) -> Wk { if i == 0 { s.w0 } else { s.w1 } }
pub open spec fn set_wk(s: ES, i: nat, w: Wk) -> ES { if i == 0 { ES { w0: w, ..s } } else { ES { w1: w, ..s } } }

pub open spec fn entry_step<O: QueueEntryPolicy>(s: ES, a: EA) -> Option<ES> {
    let c = O::entry_cfg();
    match a {
        EA::Claim(i) => {
            if i >= 2 || !(wk(s, i) is Idle) || !(s.status is Pending) || (c.single && s.lock is Some) { None }
            else {
                Some(set_wk(ES { lock: if c.single { Some(i) } else { s.lock }, works: s.works + 1, ..s }, i, Wk::Claimed(s.text)))
            }
        },
        EA::Make(i, ok) => {
            if i >= 2 { None } else {
                match wk(s, i) { Wk::Claimed(t) => Some(set_wk(s, i, Wk::Made(t, ok))), _ => None }
            }
        },
        EA::Write(i) => {
            if i >= 2 { None } else {
                match wk(s, i) {
                    Wk::Made(t, ok) => Some(set_wk(ES { vec: if ok { Some(t) } else { s.vec }, ..s }, i, Wk::Written(t, ok))),
                    _ => None,
                }
            }
        },
        EA::MarkStep(i) => {
            if i >= 2 { None } else {
                match wk(s, i) {
                    Wk::Written(t, ok) => {
                        let st = if !c.cas || s.text == t {
                            match c.mark { Mark::Always => St::Done, Mark::IfMade => if ok { St::Done } else { St::Error } }
                        } else { s.status };
                        Some(set_wk(ES { status: st, lock: if s.lock == Some(i) { None } else { s.lock }, ..s }, i, Wk::Idle))
                    },
                    _ => None,
                }
            }
        },
        EA::Enqueue => Some(ES { status: St::Pending, text: s.text + 1, enqueues: s.enqueues + 1, ..s }),
    }
}

pub struct EntryM<O> { pub o: O }

impl<O: QueueEntryPolicy> Machine for EntryM<O> {
    type S = ES;
    type A = EA;
    open spec fn init(s: ES) -> bool { s == entry_s0() }
    open spec fn step(s: ES, a: EA) -> Option<ES> { entry_step::<O>(s, a) }
}

/// M07-L1 (invariant): done means done.
pub open spec fn law_l1(s: ES) -> bool {
    !(s.status is Done) || (s.vec is Some && (!(s.w0 is Idle) || !(s.w1 is Idle) || s.vec == Some(s.text)))
}

/// M07-L2 (invariant): one worker per entry at a time.
pub open spec fn law_l2(s: ES) -> bool { !(!(s.w0 is Idle) && !(s.w1 is Idle)) }

pub open spec fn obl_l1<O: QueueEntryPolicy>() -> bool {
    O::entry_cfg().mark is IfMade && O::entry_cfg().cas && O::entry_cfg().single
}
pub open spec fn obl_l2<O: QueueEntryPolicy>() -> bool { O::entry_cfg().single }

pub trait QueueEntryObject: QueueEntryPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
}

/// The inductive form of M07-L2: a working worker holds the entry's lock.
pub open spec fn ind_l2(s: ES) -> bool {
    (!(s.w0 is Idle) ==> s.lock == Some(0nat)) && (!(s.w1 is Idle) ==> s.lock == Some(1nat))
}

pub open spec fn written_ok(w: Wk, v: Option<nat>) -> bool {
    match w { Wk::Written(t, ok) => ok ==> v == Some(t), _ => true }
}

/// The inductive form of M07-L1: DONE only with every worker idle and the result of the current text; a written
/// result is the stored one.
pub open spec fn ind_l1(s: ES) -> bool {
    &&& ind_l2(s)
    &&& (s.status is Done ==> s.w0 is Idle && s.w1 is Idle && s.vec == Some(s.text))
    &&& written_ok(s.w0, s.vec)
    &&& written_ok(s.w1, s.vec)
}

pub proof fn lemma_l2_step<O: QueueEntryPolicy>(s: ES, a: EA)
    requires obl_l2::<O>(), ind_l2(s), entry_step::<O>(s, a) is Some,
    ensures ind_l2(entry_step::<O>(s, a)->0),
{
}

pub proof fn lemma_l1_step<O: QueueEntryPolicy>(s: ES, a: EA)
    requires obl_l1::<O>(), ind_l1(s), entry_step::<O>(s, a) is Some,
    ensures ind_l1(entry_step::<O>(s, a)->0),
{
}

pub proof fn theorem_l1<O: QueueEntryPolicy>(s0: ES, ls: Seq<EA>, t: ES)
    requires obl_l1::<O>(), reached::<EntryM<O>>(s0, ls, t),
    ensures law_l1(t), law_l2(t),
{
    let inv = |s: ES| ind_l1(s);
    assert forall|x: ES, a: EA| inv(x) && (#[trigger] EntryM::<O>::step(x, a)) is Some implies inv(EntryM::<O>::step(x, a)->0) by {
        lemma_l1_step::<O>(x, a);
    }
    lemma_reached_inv::<EntryM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l2<O: QueueEntryPolicy>(s0: ES, ls: Seq<EA>, t: ES)
    requires obl_l2::<O>(), reached::<EntryM<O>>(s0, ls, t),
    ensures law_l2(t),
{
    let inv = |s: ES| ind_l2(s);
    assert forall|x: ES, a: EA| inv(x) && (#[trigger] EntryM::<O>::step(x, a)) is Some implies inv(EntryM::<O>::step(x, a)->0) by {
        lemma_l2_step::<O>(x, a);
    }
    lemma_reached_inv::<EntryM<O>>(inv, s0, ls, t);
}

/// The entry sub-mechanism's theorem, once for every object.
pub proof fn theorem_entry<O: QueueEntryObject>(s0: ES, ls: Seq<EA>, t: ES)
    requires reached::<EntryM<O>>(s0, ls, t),
    ensures law_l1(t), law_l2(t),
{
    O::discharge_l1();
    O::discharge_l2();
    theorem_l1::<O>(s0, ls, t);
    theorem_l2::<O>(s0, ls, t);
}

// ================================================================================================ 2. Order

pub struct OS { pub queue: Seq<nat>, pub high_enqueued: bool, pub overtakes: nat, pub served_high: bool }
pub enum OA { Enqueue(nat), Serve }

pub trait QueueOrderPolicy: Sized {
    /// The index of the entry served from a non-empty queue (arrival order: index 0 is the oldest).
    spec fn pick(q: Seq<nat>) -> int;
}

pub open spec fn order_s0() -> OS { OS { queue: Seq::empty(), high_enqueued: false, overtakes: 0, served_high: false } }

pub open spec fn remove_at(q: Seq<nat>, k: int) -> Seq<nat> { q.subrange(0, k) + q.subrange(k + 1, q.len() as int) }

pub open spec fn order_step<O: QueueOrderPolicy>(s: OS, a: OA) -> Option<OS> {
    match a {
        OA::Enqueue(i) => {
            if i >= 3 || s.queue.contains(i) || (i == 2 && s.high_enqueued) { None }
            else { Some(OS { queue: s.queue.push(i), high_enqueued: s.high_enqueued || i == 2, ..s }) }
        },
        OA::Serve => {
            let k = O::pick(s.queue);
            if s.queue.len() == 0 || k < 0 || k >= s.queue.len() { None }
            else {
                let id = s.queue[k];
                let q2 = remove_at(s.queue, k);
                if id == 2 { Some(OS { queue: q2, served_high: true, overtakes: 0, ..s }) }
                else if s.queue.contains(2) {
                    Some(OS { queue: q2, overtakes: if s.overtakes + 1 < 3 { s.overtakes + 1 } else { 3 }, ..s })
                } else { Some(OS { queue: q2, ..s }) }
            }
        },
    }
}

pub struct OrderM<O> { pub o: O }

impl<O: QueueOrderPolicy> Machine for OrderM<O> {
    type S = OS;
    type A = OA;
    open spec fn init(s: OS) -> bool { s == order_s0() }
    open spec fn step(s: OS, a: OA) -> Option<OS> { order_step::<O>(s, a) }
}

/// M07-L3 (invariant): bounded overtaking (N = 3 distinct ids).
pub open spec fn law_l3(s: OS) -> bool { s.overtakes <= 2 }

pub open spec fn pending(s: OS) -> bool { s.queue.contains(2) }

/// The service order serves the oldest pending entry.
pub open spec fn serves_oldest<O: QueueOrderPolicy>() -> bool {
    forall|q: Seq<nat>| q.len() > 0 ==> #[trigger] O::pick(q) == 0
}
pub open spec fn obl_l3<O: QueueOrderPolicy>() -> bool { serves_oldest::<O>() }
pub open spec fn obl_l4<O: QueueOrderPolicy>() -> bool { serves_oldest::<O>() }

pub trait QueueOrderObject: QueueOrderPolicy {
    proof fn discharge_l3() ensures obl_l3::<Self>();
    proof fn discharge_l4() ensures obl_l4::<Self>();
}

pub open spec fn distinct(q: Seq<nat>) -> bool {
    forall|a: int, b: int| 0 <= a < b < q.len() ==> q[a] != q[b]
}

/// Every policy: the queue holds distinct ids below 3; id 2 pending means it was enqueued.
pub open spec fn inv_order(s: OS) -> bool {
    &&& distinct(s.queue)
    &&& forall|k: int| 0 <= k < s.queue.len() ==> #[trigger] s.queue[k] < 3
    &&& s.queue.contains(2) ==> s.high_enqueued
}

pub proof fn lemma_qlen(q: Seq<nat>)
    requires distinct(q), forall|k: int| 0 <= k < q.len() ==> #[trigger] q[k] < 3,
    ensures q.len() <= 3, !q.contains(2) ==> q.len() <= 2,
{
    if q.len() >= 4 {
        assert(q[0] < 3 && q[1] < 3 && q[2] < 3 && q[3] < 3);
        assert(q[0] != q[1] && q[0] != q[2] && q[0] != q[3] && q[1] != q[2] && q[1] != q[3] && q[2] != q[3]);
    }
    if !q.contains(2) && q.len() >= 3 {
        assert(q[0] != 2 && q[1] != 2 && q[2] != 2);
        assert(q[0] < 3 && q[1] < 3 && q[2] < 3);
        assert(q[0] != q[1] && q[0] != q[2] && q[1] != q[2]);
    }
}

pub proof fn lemma_remove_at(q: Seq<nat>, k: int)
    requires 0 <= k < q.len(),
    ensures
        remove_at(q, k).len() == q.len() - 1,
        forall|j: int| 0 <= j < k ==> #[trigger] remove_at(q, k)[j] == q[j],
        forall|j: int| k <= j < q.len() - 1 ==> #[trigger] remove_at(q, k)[j] == q[j + 1],
{
}

pub proof fn lemma_inv_order_step<O: QueueOrderPolicy>(s: OS, a: OA)
    requires inv_order(s), order_step::<O>(s, a) is Some,
    ensures inv_order(order_step::<O>(s, a)->0),
{
    let t = order_step::<O>(s, a)->0;
    match a {
        OA::Enqueue(i) => {
            assert forall|x: int, y: int| 0 <= x < y < t.queue.len() implies t.queue[x] != t.queue[y] by {
                if y == s.queue.len() { assert(s.queue[x] != i); }
            }
            if t.queue.contains(2) && !s.queue.contains(2) {
                let k = choose|k: int| 0 <= k < t.queue.len() && t.queue[k] == 2;
                if k < s.queue.len() { assert(s.queue[k] == 2); }
            }
        },
        OA::Serve => {
            let k = O::pick(s.queue);
            lemma_remove_at(s.queue, k);
            assert forall|x: int, y: int| 0 <= x < y < t.queue.len() implies t.queue[x] != t.queue[y] by {
                let xx = if x < k { x } else { x + 1 };
                let yy = if y < k { y } else { y + 1 };
                assert(t.queue[x] == s.queue[xx] && t.queue[y] == s.queue[yy]);
            }
            assert forall|j: int| 0 <= j < t.queue.len() implies #[trigger] t.queue[j] < 3 by {
                let jj = if j < k { j } else { j + 1 };
                assert(t.queue[j] == s.queue[jj]);
            }
            if t.queue.contains(2) {
                let j = choose|j: int| 0 <= j < t.queue.len() && t.queue[j] == 2;
                let jj = if j < k { j } else { j + 1 };
                assert(s.queue[jj] == 2);
            }
        },
    }
}

/// The inductive form of M07-L3 under its obligation: while id 2 waits at position k, overtakes + k <= 2.
pub open spec fn ind_l3(s: OS) -> bool {
    &&& inv_order(s)
    &&& forall|k: int| 0 <= k < s.queue.len() && s.queue[k] == 2 ==> s.overtakes + k <= 2
    &&& !s.queue.contains(2) ==> s.overtakes == 0
}

pub proof fn lemma_l3_step<O: QueueOrderPolicy>(s: OS, a: OA)
    requires obl_l3::<O>(), ind_l3(s), order_step::<O>(s, a) is Some,
    ensures ind_l3(order_step::<O>(s, a)->0),
{
    lemma_inv_order_step::<O>(s, a);
    let t = order_step::<O>(s, a)->0;
    lemma_qlen(s.queue);
    match a {
        OA::Enqueue(i) => {
            assert(t.overtakes == s.overtakes);
            assert(t.queue.len() == s.queue.len() + 1);
            assert forall|k: int| 0 <= k < t.queue.len() && t.queue[k] == 2 implies t.overtakes + k <= 2 by {
                if k == s.queue.len() {
                    assert(i == 2);
                    assert(!s.queue.contains(2));
                } else {
                    assert(s.queue[k] == 2);
                }
            }
            if !t.queue.contains(2) {
                if s.queue.contains(2) {
                    let k = choose|k: int| 0 <= k < s.queue.len() && s.queue[k] == 2;
                    assert(t.queue[k] == 2);
                }
            }
        },
        OA::Serve => {
            assert(O::pick(s.queue) == 0);
            lemma_remove_at(s.queue, 0);
            if s.queue[0] == 2 {
                assert forall|k: int| 0 <= k < t.queue.len() implies t.queue[k] != 2 by {
                    assert(t.queue[k] == s.queue[k + 1]);
                }
                assert(!t.queue.contains(2));
            } else if s.queue.contains(2) {
                let p = choose|p: int| 0 <= p < s.queue.len() && s.queue[p] == 2;
                assert(p >= 1);
                assert(s.overtakes + p <= 2);
                assert(t.queue[p - 1] == 2);
                assert(t.queue.contains(2));
                assert(t.overtakes == s.overtakes + 1);
                assert forall|k: int| 0 <= k < t.queue.len() && t.queue[k] == 2 implies t.overtakes + k <= 2 by {
                    assert(t.queue[k] == s.queue[k + 1]);
                    assert(s.overtakes + (k + 1) <= 2);
                }
            } else {
                assert forall|k: int| 0 <= k < t.queue.len() implies t.queue[k] != 2 by {
                    assert(t.queue[k] == s.queue[k + 1]);
                    assert(!(s.queue[k + 1] == 2));
                }
                assert(t.overtakes == s.overtakes);
            }
        },
    }
}

pub proof fn theorem_inv_order<O: QueueOrderPolicy>(s0: OS, ls: Seq<OA>, t: OS)
    requires reached::<OrderM<O>>(s0, ls, t),
    ensures inv_order(t),
{
    let inv = |s: OS| inv_order(s);
    assert forall|x: OS, a: OA| inv(x) && (#[trigger] OrderM::<O>::step(x, a)) is Some implies inv(OrderM::<O>::step(x, a)->0) by {
        lemma_inv_order_step::<O>(x, a);
    }
    lemma_reached_inv::<OrderM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l3<O: QueueOrderPolicy>(s0: OS, ls: Seq<OA>, t: OS)
    requires obl_l3::<O>(), reached::<OrderM<O>>(s0, ls, t),
    ensures law_l3(t),
{
    let inv = |s: OS| ind_l3(s);
    assert forall|x: OS, a: OA| inv(x) && (#[trigger] OrderM::<O>::step(x, a)) is Some implies inv(OrderM::<O>::step(x, a)->0) by {
        lemma_l3_step::<O>(x, a);
    }
    lemma_reached_inv::<OrderM<O>>(inv, s0, ls, t);
    if t.queue.contains(2) {
        let k = choose|k: int| 0 <= k < t.queue.len() && t.queue[k] == 2;
    }
}

// ---------------------------------------------------------------- M07-L4, service part: progress under fairness

/// An infinite execution of the order machine (every step is a machine step), as actors::fairness::infinite_execution.
pub open spec fn order_exec<O: QueueOrderPolicy>(st: spec_fn(nat) -> OS, lb: spec_fn(nat) -> OA) -> bool {
    forall|i: nat| #[trigger] order_step::<O>(st(i), lb(i)) == Some(st(i + 1))
}

/// Premise: the worker is weakly fair: whenever id 2 is pending, a Serve step occurs later.
pub open spec fn worker_fair(st: spec_fn(nat) -> OS, lb: spec_fn(nat) -> OA) -> bool {
    forall|i: nat| #[trigger] pending(st(i)) ==> exists|k: nat| k >= i && (#[trigger] lb(k)) is Serve
}

/// The position of id 2 in a queue that holds it.
pub open spec fn pos2(q: Seq<nat>) -> nat {
    choose|k: nat| k < q.len() && q[k as int] == 2
}

pub proof fn lemma_pos2(q: Seq<nat>, k: int)
    requires distinct(q), 0 <= k < q.len(), q[k] == 2,
    ensures pos2(q) == k,
{
    let kk = k as nat;
    assert(kk < q.len() && q[kk as int] == 2);
    let p = pos2(q);
    assert(p < q.len() && q[p as int] == 2);
}

/// One step keeps id 2's position or lowers it; a Serve under the obligation lowers it or serves id 2.
pub proof fn lemma_progress_step<O: QueueOrderPolicy>(s: OS, a: OA)
    requires obl_l4::<O>(), inv_order(s), pending(s), order_step::<O>(s, a) is Some, pending(order_step::<O>(s, a)->0),
    ensures
        pos2((order_step::<O>(s, a)->0).queue) <= pos2(s.queue),
        a is Serve ==> pos2((order_step::<O>(s, a)->0).queue) < pos2(s.queue),
{
    lemma_inv_order_step::<O>(s, a);
    let t = order_step::<O>(s, a)->0;
    let p = choose|p: int| 0 <= p < s.queue.len() && s.queue[p] == 2;
    lemma_pos2(s.queue, p);
    match a {
        OA::Enqueue(i) => {
            assert(t.queue[p] == 2);
            lemma_pos2(t.queue, p);
        },
        OA::Serve => {
            assert(O::pick(s.queue) == 0);
            lemma_remove_at(s.queue, 0);
            let k = choose|k: int| 0 <= k < t.queue.len() && t.queue[k] == 2;
            assert(t.queue[k] == s.queue[k + 1]);
            lemma_pos2(s.queue, k + 1);
            lemma_pos2(t.queue, k);
        },
    }
}

pub proof fn lemma_inv_all<O: QueueOrderPolicy>(st: spec_fn(nat) -> OS, lb: spec_fn(nat) -> OA, j: nat)
    requires order_exec::<O>(st, lb), inv_order(st(0)),
    ensures inv_order(st(j)),
    decreases j,
{
    if j > 0 {
        let m = (j - 1) as nat;
        lemma_inv_all::<O>(st, lb, m);
        assert(order_step::<O>(st(m), lb(m)) == Some(st(m + 1)));
        lemma_inv_order_step::<O>(st(m), lb(m));
    }
}

pub proof fn lemma_nonincreasing<O: QueueOrderPolicy>(st: spec_fn(nat) -> OS, lb: spec_fn(nat) -> OA, i: nat, j: nat)
    requires
        obl_l4::<O>(), order_exec::<O>(st, lb), inv_order(st(0)), i <= j,
        forall|m: nat| i <= m <= j ==> #[trigger] pending(st(m)),
    ensures pos2(st(j).queue) <= pos2(st(i).queue),
    decreases j - i,
{
    if j > i {
        let m = (j - 1) as nat;
        lemma_nonincreasing::<O>(st, lb, i, m);
        assert(pending(st(m)) && pending(st(j)));
        assert(order_step::<O>(st(m), lb(m)) == Some(st(m + 1)));
        lemma_inv_all::<O>(st, lb, m);
        lemma_progress_step::<O>(st(m), lb(m));
    }
}

pub proof fn lemma_served<O: QueueOrderPolicy>(st: spec_fn(nat) -> OS, lb: spec_fn(nat) -> OA, i: nat)
    requires obl_l4::<O>(), order_exec::<O>(st, lb), worker_fair(st, lb), inv_order(st(0)), pending(st(i)),
    ensures exists|k: nat| k >= i && !pending(#[trigger] st(k)),
    decreases pos2(st(i).queue),
{
    let k = choose|k: nat| k >= i && (#[trigger] lb(k)) is Serve;
    if exists|m: nat| i <= m <= k && !pending(#[trigger] st(m)) {
        let m = choose|m: nat| i <= m <= k && !pending(#[trigger] st(m));
        assert(m >= i && !pending(st(m)));
    } else {
        assert forall|m: nat| i <= m <= k implies #[trigger] pending(st(m)) by {}
        lemma_nonincreasing::<O>(st, lb, i, k);
        assert(order_step::<O>(st(k), lb(k)) == Some(st(k + 1)));
        if !pending(st(k + 1)) {
            assert((k + 1) as nat >= i);
        } else {
            lemma_inv_all::<O>(st, lb, k);
            lemma_progress_step::<O>(st(k), lb(k));
            lemma_served::<O>(st, lb, (k + 1) as nat);
        }
    }
}

/// M07-L4, service part: in every infinite execution from a reached state in which the worker is weakly fair,
/// a pending entry (id 2) is eventually served.
pub proof fn theorem_l4_order<O: QueueOrderPolicy>(st: spec_fn(nat) -> OS, lb: spec_fn(nat) -> OA, s0: OS, ls: Seq<OA>, i: nat)
    requires
        obl_l4::<O>(), reached::<OrderM<O>>(s0, ls, st(0)), order_exec::<O>(st, lb), worker_fair(st, lb), pending(st(i)),
    ensures exists|k: nat| k >= i && !pending(#[trigger] st(k)),
{
    theorem_inv_order::<O>(s0, ls, st(0));
    lemma_served::<O>(st, lb, i);
}

/// The order sub-mechanism's theorem, once for every object.
pub proof fn theorem_order<O: QueueOrderObject>(st: spec_fn(nat) -> OS, lb: spec_fn(nat) -> OA, s0: OS, ls: Seq<OA>, t: OS, i: nat)
    requires reached::<OrderM<O>>(s0, ls, t),
    ensures
        law_l3(t),
        reached::<OrderM<O>>(s0, ls, st(0)) && order_exec::<O>(st, lb) && worker_fair(st, lb) && pending(st(i))
            ==> exists|k: nat| k >= i && !pending(#[trigger] st(k)),
{
    O::discharge_l3();
    O::discharge_l4();
    theorem_l3::<O>(s0, ls, t);
    if reached::<OrderM<O>>(s0, ls, st(0)) && order_exec::<O>(st, lb) && worker_fair(st, lb) && pending(st(i)) {
        theorem_l4_order::<O>(st, lb, s0, ls, i);
    }
}

// ================================================================================================ 3. Resume

pub struct RsS { pub tomb: Seq<bool>, pub cursor: nat }
pub enum RsA { Call }

pub trait ResumePolicy: Sized {
    /// The record a call resumes its scan at, given the saved cursor.
    spec fn resume_at(cursor: nat) -> nat;
}

pub open spec fn resume_s0() -> RsS { RsS { tomb: seq![false, false, false], cursor: 0 } }

pub open spec fn finished(s: RsS) -> bool { s.tomb.len() == 3 && s.tomb[0] && s.tomb[1] && s.tomb[2] }

pub open spec fn resume_step<O: ResumePolicy>(s: RsS, a: RsA) -> Option<RsS> {
    if s.tomb.len() != 3 || finished(s) { None }
    else {
        let p = O::resume_at(s.cursor);
        // one call scans one record (its batch budget) from p
        if p < 3 { Some(RsS { tomb: s.tomb.update(p as int, true), cursor: p + 1 }) } else { Some(s) }
    }
}

pub struct ResumeM<O> { pub o: O }

impl<O: ResumePolicy> Machine for ResumeM<O> {
    type S = RsS;
    type A = RsA;
    open spec fn init(s: RsS) -> bool { s == resume_s0() }
    open spec fn step(s: RsS, a: RsA) -> Option<RsS> { resume_step::<O>(s, a) }
}

/// M07-L4, resume part (AG EF): from the state, some run finishes the redaction.
pub open spec fn law_l4_resume<O: ResumePolicy>(s: RsS) -> bool {
    exists|ls: Seq<RsA>| #[trigger] run::<ResumeM<O>>(s, ls) is Some && finished(run::<ResumeM<O>>(s, ls)->0)
}

pub open spec fn obl_l4_resume<O: ResumePolicy>() -> bool { forall|c: nat| #[trigger] O::resume_at(c) == c }

pub trait ResumeObject: ResumePolicy {
    proof fn discharge_l4() ensures obl_l4_resume::<Self>();
}

/// The persisted cursor: records before it are tombstoned, the others not.
pub open spec fn inv_persist(s: RsS) -> bool {
    s.tomb.len() == 3 && s.cursor <= 3 && forall|j: int| 0 <= j < 3 ==> (#[trigger] s.tomb[j] <==> j < s.cursor)
}

pub open spec fn calls(n: nat) -> Seq<RsA> { Seq::new(n, |i: int| RsA::Call) }

pub proof fn lemma_persist_step<O: ResumePolicy>(s: RsS)
    requires obl_l4_resume::<O>(), inv_persist(s), !finished(s),
    ensures
        resume_step::<O>(s, RsA::Call) is Some,
        inv_persist(resume_step::<O>(s, RsA::Call)->0),
        (resume_step::<O>(s, RsA::Call)->0).cursor == s.cursor + 1,
{
    assert(O::resume_at(s.cursor) == s.cursor);
    if s.cursor >= 3 { assert(s.tomb[0] && s.tomb[1] && s.tomb[2]); }
}

/// Under the obligation, `3 - cursor` more calls finish the run (the fairness premise: the run is resumed that many
/// more times).
pub proof fn lemma_finishes<O: ResumePolicy>(s: RsS)
    requires obl_l4_resume::<O>(), inv_persist(s),
    ensures
        run::<ResumeM<O>>(s, calls((3 - s.cursor) as nat)) is Some,
        finished(run::<ResumeM<O>>(s, calls((3 - s.cursor) as nat))->0),
    decreases 3 - s.cursor,
{
    let n = (3 - s.cursor) as nat;
    if s.cursor == 3 {
        assert(calls(n) =~= Seq::<RsA>::empty());
        assert(s.tomb[0] && s.tomb[1] && s.tomb[2]);
    } else {
        if finished(s) { assert(s.tomb[2]); }
        lemma_persist_step::<O>(s);
        let t = resume_step::<O>(s, RsA::Call)->0;
        lemma_finishes::<O>(t);
        assert(calls(n).drop_first() =~= calls((3 - t.cursor) as nat));
        assert(calls(n)[0] == RsA::Call);
    }
}

pub proof fn theorem_l4_resume<O: ResumePolicy>(s0: RsS, ls: Seq<RsA>, t: RsS)
    requires obl_l4_resume::<O>(), reached::<ResumeM<O>>(s0, ls, t),
    ensures
        law_l4_resume::<O>(t),
        run::<ResumeM<O>>(t, calls((3 - t.cursor) as nat)) is Some,
        finished(run::<ResumeM<O>>(t, calls((3 - t.cursor) as nat))->0),
{
    let inv = |s: RsS| inv_persist(s);
    assert forall|x: RsS, a: RsA| inv(x) && (#[trigger] ResumeM::<O>::step(x, a)) is Some implies inv(ResumeM::<O>::step(x, a)->0) by {
        if !finished(x) { lemma_persist_step::<O>(x); }
    }
    assert(inv_persist(resume_s0()));
    lemma_reached_inv::<ResumeM<O>>(inv, s0, ls, t);
    lemma_finishes::<O>(t);
    let w = calls((3 - t.cursor) as nat);
    assert(run::<ResumeM<O>>(t, w) is Some && finished(run::<ResumeM<O>>(t, w)->0));
}

/// The resume sub-mechanism's theorem, once for every object.
pub proof fn theorem_resume<O: ResumeObject>(s0: RsS, ls: Seq<RsA>, t: RsS)
    requires reached::<ResumeM<O>>(s0, ls, t),
    ensures law_l4_resume::<O>(t),
{
    O::discharge_l4();
    theorem_l4_resume::<O>(s0, ls, t);
}

} // verus!
