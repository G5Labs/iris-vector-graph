//! Module 16, L2: the Bolt server's explicit transaction and the Neo4j HTTP commit route at pin 3eaa79cf;
//! refinement of `unit_l1` for every step, the invariant, and the controls F-1601 and F-1610 (executable twin:
//! models/breadth-c/src/unit.rs, machine M2).
//!
//! State: the entry (`Bolt` or `Http`), the unit's phase, the committed (visible) applications of each write, the
//! reviewed design's transaction buffer (`b1`, `b2`: written inside the session's open transaction, not visible), the
//! last attempt's failure (the driver retries after a failed, rolled-back attempt), the attempts and the committed
//! units.
//!
//! **Reviewed design** (F-1601 and F-1610 remedies): the unit's statements run in one engine transaction
//! (`write_txn`), published on COMMIT (Bolt) or when the whole request succeeded (HTTP), and discarded on ROLLBACK or
//! on the first failure. As built:
//! - Bolt: BEGIN and COMMIT answer SUCCESS and do nothing, ROLLBACK only clears pending rows
//!   (bolt_server.py:500-510), and each RUN goes through `engine.execute_cypher`, which commits its own write
//!   (bolt_server.py:579-581; _engine/query.py:1946-1967): control F-1601;
//! - HTTP: `neo4j_tx_commit` runs each statement through `_run_cypher`, which commits it, records a failure and runs
//!   the next statement (cypher_api.py:391-401): control F-1610.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::unit_l1::*;

verus! {

pub enum Entry { Bolt, Http }
pub enum Ph { Idle, Open, AfterW1, Ready, Failed }

pub struct U2 {
    pub entry: Entry, pub ph: Ph, pub w1: nat, pub w2: nat, pub b1: bool, pub b2: bool,
    pub last_failed: bool, pub attempts: nat, pub units: nat,
}

pub enum UL2 {
    /// Bolt BEGIN, or the HTTP request arriving
    Begin,
    /// RUN of the first write (Bolt), or the request's first statement (HTTP)
    Run1,
    /// the second write; `ok` false: it fails (a FAILURE on Bolt; HTTP records the error); `http` the entry
    Run2 { ok: bool, http: bool },
    /// Bolt COMMIT
    Commit,
    /// Bolt ROLLBACK (the driver's, after a FAILURE, or the caller's)
    Rollback,
    /// the driver's managed transaction (execute_write) runs the unit again after a failed, rolled-back attempt
    Retry,
    /// another session reads the visible writes
    Read { a: nat, b: nat },
}

pub open spec fn f1601() -> bool { cfg!(feature = "control_f1601_bolt_run_commits") }
pub open spec fn f1610() -> bool { cfg!(feature = "control_f1610_tx_commit_per_statement") }

/// As built, each statement commits on its own.
pub open spec fn direct(s: U2) -> bool { (s.entry is Bolt && f1601()) || (s.entry is Http && f1610()) }

pub open spec fn one(b: bool) -> nat { if b { 1 } else { 0 } }

pub open spec fn run1(s: U2) -> U2 {
    if direct(s) { U2 { w1: s.w1 + 1, ph: Ph::AfterW1, ..s } } else { U2 { b1: true, ph: Ph::AfterW1, ..s } }
}
/// The reviewed publication of the buffers (COMMIT, or the end of a successful HTTP request).
pub open spec fn publish(s: U2) -> U2 {
    U2 { w1: s.w1 + one(s.b1), w2: s.w2 + one(s.b2), b1: false, b2: false, ph: Ph::Idle, units: s.units + 1, ..s }
}
pub open spec fn run2_ok(s: U2) -> U2 {
    if s.entry is Http {
        if direct(s) { U2 { w2: s.w2 + 1, ph: Ph::Idle, units: s.units + 1, ..s } } else { publish(U2 { b2: true, ..s }) }
    } else {
        if direct(s) { U2 { w2: s.w2 + 1, ph: Ph::Ready, ..s } } else { U2 { b2: true, ph: Ph::Ready, ..s } }
    }
}
pub open spec fn run2_fail(s: U2) -> U2 {
    if s.entry is Http { U2 { b1: false, b2: false, last_failed: true, ph: Ph::Idle, ..s } } else { U2 { ph: Ph::Failed, ..s } }
}
pub open spec fn commit(s: U2) -> U2 { if direct(s) { U2 { ph: Ph::Idle, units: s.units + 1, ..s } } else { publish(s) } }
pub open spec fn rollback(s: U2) -> U2 { U2 { b1: false, b2: false, last_failed: s.ph is Failed, ph: Ph::Idle, ..s } }
pub open spec fn retry(s: U2) -> U2 { U2 { attempts: s.attempts + 1, last_failed: false, ph: Ph::Open, ..s } }

pub open spec fn init2(s: U2) -> bool {
    s.ph is Idle && s.w1 == 0 && s.w2 == 0 && !s.b1 && !s.b2 && !s.last_failed && s.attempts == 0 && s.units == 0
}

pub open spec fn step2(s: U2, l: UL2, t: U2) -> bool {
    match l {
        UL2::Begin => s.ph is Idle && s.attempts == 0 && t == U2 { ph: Ph::Open, attempts: 1, ..s },
        UL2::Run1 => s.ph is Open && t == run1(s),
        UL2::Run2 { ok, http } => s.ph is AfterW1 && http == (s.entry is Http) && t == (if ok { run2_ok(s) } else { run2_fail(s) }),
        UL2::Commit => s.entry is Bolt && s.ph is Ready && t == commit(s),
        UL2::Rollback => s.entry is Bolt && (s.ph is AfterW1 || s.ph is Ready || s.ph is Failed) && t == rollback(s),
        UL2::Retry => s.ph is Idle && s.last_failed && s.attempts < 2 && t == retry(s),
        UL2::Read { a, b } => a == s.w1 && b == s.w2 && t == s,
    }
}

pub open spec fn absu(s: U2) -> U1 { U1 { v1: s.w1, v2: s.w2, done: s.units > 0 } }

pub open spec fn labu(l: UL2) -> Option<UL1> {
    match l {
        UL2::Run2 { ok, http } => if !http { None } else if ok { Some(UL1::Commit) } else { Some(UL1::Abort) },
        UL2::Commit => Some(UL1::Commit),
        UL2::Rollback => Some(UL1::Abort),
        UL2::Read { a, b } => Some(UL1::Read { a, b }),
        _ => None,
    }
}

/// The buffers by phase; a committed unit is over.
pub open spec fn inv16u(s: U2) -> bool {
    &&& inv1(absu(s)) && s.units <= 1
    &&& (s.ph is Idle || s.ph is Open) ==> !s.b1 && !s.b2
    &&& (s.ph is AfterW1 || s.ph is Failed) ==> s.b1 && !s.b2
    &&& s.ph is Ready ==> s.b1 && s.b2
    &&& !(s.ph is Idle) ==> !s.last_failed && s.units == 0 && s.attempts >= 1
    &&& s.units > 0 ==> !s.last_failed && s.attempts >= 1
    &&& s.attempts == 0 ==> !s.last_failed
    &&& s.entry is Http ==> !(s.ph is Ready) && !(s.ph is Failed)
}

pub struct UnitL2;

impl Contract for UnitL2 {
    type S = U2;
    type L = UL2;
    open spec fn init(s: U2) -> bool { init2(s) }
    open spec fn next(s: U2, l: UL2, t: U2) -> bool { inv16u(s) && step2(s, l, t) }
}

pub struct UnitRaw;

impl Contract for UnitRaw {
    type S = U2;
    type L = UL2;
    open spec fn init(s: U2) -> bool { init2(s) }
    open spec fn next(s: U2, l: UL2, t: U2) -> bool { step2(s, l, t) }
}

proof fn lemma_run1(s: U2, t: U2)
    requires inv16u(s), step2(s, UL2::Run1, t),
    ensures inv16u(t), step_or_stutter::<UnitL1>(absu(s), labu(UL2::Run1), absu(t)),
{
    if s.entry is Bolt {
        // a RUN inside a Bolt transaction is not visible before COMMIT (control F-1601 fails here)
        assert(t.w1 == s.w1);
    } else {
        // a statement of a tx/commit request is not visible before the request succeeds (control F-1610 fails here)
        assert(t.w1 == s.w1);
    }
}

proof fn lemma_run2(s: U2, ok: bool, http: bool, t: U2)
    requires inv16u(s), step2(s, UL2::Run2 { ok, http }, t),
    ensures inv16u(t), step_or_stutter::<UnitL1>(absu(s), labu(UL2::Run2 { ok, http }), absu(t)),
{
    if http {
        // the request's success publishes the whole unit, its failure nothing (control F-1610 fails here)
        assert(ok ==> t.w1 == s.w1 + 1 && t.w2 == s.w2 + 1);
    } else {
        // the second RUN is not visible before COMMIT (control F-1601 fails here)
        assert(t.w2 == s.w2);
    }
}

proof fn lemma_commit(s: U2, t: U2)
    requires inv16u(s), step2(s, UL2::Commit, t),
    ensures inv16u(t), step_or_stutter::<UnitL1>(absu(s), labu(UL2::Commit), absu(t)),
{
    // COMMIT publishes both writes (control F-1601 fails here)
    assert(t.w1 == s.w1 + 1 && t.w2 == s.w2 + 1);
}

pub proof fn lemma_step(s: U2, l: UL2, t: U2)
    requires inv16u(s), step2(s, l, t),
    ensures inv16u(t), step_or_stutter::<UnitL1>(absu(s), labu(l), absu(t)),
{
    match l {
        UL2::Run1 => lemma_run1(s, t),
        UL2::Run2 { ok, http } => lemma_run2(s, ok, http, t),
        UL2::Commit => lemma_commit(s, t),
        _ => {}
    }
}

impl Refines<UnitL1> for UnitL2 {
    open spec fn abs(s: U2) -> U1 { absu(s) }
    open spec fn lab(l: UL2) -> Option<UL1> { labu(l) }
    proof fn init_refines(s: U2) {}
    proof fn step_refines(s: U2, l: UL2, t: U2) { lemma_step(s, l, t); }
}

impl SafeContract for UnitL2 {
    open spec fn inv(s: U2) -> bool { inv16u(s) }
    proof fn init_safe(s: U2) {}
    proof fn step_safe(s: U2, l: UL2, t: U2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<U2>, labels: Seq<UL2>, k: int)
    requires execution::<UnitRaw>(states, labels), 0 <= k < states.len(),
    ensures inv16u(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution: readers see whole units only, and a unit commits at most once across the driver's retries.
pub proof fn theorem_raw_executions_refine(states: Seq<U2>, labels: Seq<UL2>)
    requires execution::<UnitRaw>(states, labels),
    ensures
        execution::<UnitL2>(states, labels),
        abstract_execution::<UnitL1>(Seq::new(states.len(), |i: int| absu(states[i])),
                                     Seq::new(labels.len(), |i: int| labu(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv16u(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv16u(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<UnitL2>(states, labels));
    trace_refines::<UnitL2, UnitL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absu(states[i])) =~= Seq::new(states.len(), |i: int| <UnitL2 as Refines<UnitL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labu(labels[i])) =~= Seq::new(labels.len(), |i: int| <UnitL2 as Refines<UnitL1>>::lab(labels[i])));
}

} // verus!
