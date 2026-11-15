//! M2: a multi-statement unit of work sent to a server: a Bolt explicit transaction (BEGIN, RUN w1, RUN w2,
//! COMMIT | ROLLBACK) with the Neo4j driver's managed-transaction retry, and the Neo4j HTTP "begin and commit"
//! request POST /db/neo4j/tx/commit with two statements (F-1601, F-1610; module 16).
//!
//! As built at 3eaa79cf:
//! - Bolt: BEGIN and COMMIT answer SUCCESS and do nothing; ROLLBACK only clears pending rows
//!   (iris_vector_graph/bolt_server.py:500-510); each RUN goes through `engine.execute_cypher`, which commits its own
//!   write (bolt_server.py:579-581, iris_vector_graph/_engine/query.py:1946-1967). A driver's managed transaction
//!   (`session.execute_write`) rolls back and re-runs the whole unit after a transient failure.
//! - HTTP: `neo4j_tx_commit` runs each statement through `_run_cypher`, which commits it; a failing statement is
//!   recorded and the next still runs (iris_vector_graph/cypher_api.py:379-410).
//! Reviewed (F-1601/F-1610 "what would close it"): the unit's statements run in one engine transaction
//! (`write_txn`), published on COMMIT (on success of the whole request) and discarded on ROLLBACK (the first failure).
//!
//! Properties:
//! - `unit atomicity`: whenever no unit is open, w1 and w2 are visible the same number of times (all or none);
//! - `at most once`: each write is visible at most once, across the driver's retry;
//! - always possibly: the session is idle again;
//! - witness: a committed unit with both writes visible.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, ControlRollbackKeepsFirstWrite }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Entry { Bolt, HttpTxCommit }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Phase { Idle, Open, AfterW1, Ready, Failed }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub phase: Phase,
    /// visible (committed) applications of each statement's write
    pub w1: u8,
    pub w2: u8,
    /// the reviewed design's transaction buffer
    pub buf1: bool,
    pub buf2: bool,
    /// the last attempt failed and ended (rolled back, or the HTTP request answered)
    pub last_failed: bool,
    pub attempts: u8,
    pub committed_units: u8,
}

#[derive(Clone, Debug)]
pub enum A { Begin, Run1, Run2 { ok: bool }, Commit, Rollback, DriverRetry }

pub struct M { pub design: Design, pub entry: Entry }

impl M {
    fn per_statement_commit(&self) -> bool { self.design == Design::AsBuilt }
    fn discard(&self, s: &S, t: &mut S) {
        match self.design {
            Design::AsBuilt => {} // nothing to undo: every statement already committed
            Design::Reviewed => {}
            Design::ControlRollbackKeepsFirstWrite => { if s.buf1 { t.w1 += 1; } }
        }
        t.buf1 = false;
        t.buf2 = false;
    }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { phase: Phase::Idle, w1: 0, w2: 0, buf1: false, buf2: false, last_failed: false, attempts: 0,
                 committed_units: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::Begin, A::Run1, A::Run2 { ok: true }, A::Run2 { ok: false }, A::Commit, A::Rollback, A::DriverRetry]
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut t = s.clone();
        match a {
            A::Begin => {
                if s.phase != Phase::Idle || s.attempts > 0 { return None; }
                t.phase = Phase::Open;
                t.attempts = 1;
            }
            A::Run1 => {
                if s.phase != Phase::Open { return None; }
                if self.per_statement_commit() { t.w1 += 1; } else { t.buf1 = true; }
                t.phase = Phase::AfterW1;
            }
            A::Run2 { ok } => {
                if s.phase != Phase::AfterW1 { return None; }
                if *ok {
                    if self.per_statement_commit() { t.w2 += 1; } else { t.buf2 = true; }
                    t.phase = Phase::Ready;
                    if self.entry == Entry::HttpTxCommit {
                        // the request succeeded as a whole: the reviewed design commits it here
                        if !self.per_statement_commit() { t.w1 += u8::from(s.buf1); t.w2 += 1; t.buf1 = false; t.buf2 = false; }
                        t.committed_units += 1;
                        t.phase = Phase::Idle;
                    }
                } else if self.entry == Entry::HttpTxCommit {
                    // the error is recorded and the request answered 400; as built w1 stays committed
                    self.discard(s, &mut t);
                    t.last_failed = true;
                    t.phase = Phase::Idle;
                } else {
                    t.phase = Phase::Failed; // Bolt FAILURE: the driver must ROLLBACK
                }
            }
            A::Commit => {
                if s.phase != Phase::Ready || self.entry != Entry::Bolt { return None; }
                if !self.per_statement_commit() {
                    t.w1 += u8::from(s.buf1);
                    t.w2 += u8::from(s.buf2);
                    t.buf1 = false;
                    t.buf2 = false;
                }
                t.committed_units += 1;
                t.phase = Phase::Idle;
            }
            A::Rollback => {
                // as built: bolt_server.py:505-510 clears pending rows only
                if self.entry != Entry::Bolt || !matches!(s.phase, Phase::AfterW1 | Phase::Ready | Phase::Failed) {
                    return None;
                }
                self.discard(s, &mut t);
                t.last_failed = s.phase == Phase::Failed;
                t.phase = Phase::Idle;
            }
            A::DriverRetry => {
                // the driver's managed transaction re-runs the unit after a failed, rolled-back attempt
                // (for HTTP: the client resends the request after a 400 for a transient error)
                if s.phase != Phase::Idle || !s.last_failed || s.attempts >= 2 { return None; }
                t.attempts += 1;
                t.last_failed = false;
                t.phase = Phase::Open;
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("unit atomicity", |s: &S| !(s.phase == Phase::Idle && s.w1 != s.w2)),
            invariant("at most once", |s: &S| s.w1 <= 1 && s.w2 <= 1),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("the session is idle again", |s: &S| s.phase == Phase::Idle)]
    }
}

pub struct Witness { pub m: M }
impl Model for Witness {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { self.m.init_states() }
    fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
    fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant("a committed unit with both writes visible",
                       |s: &S| !(s.committed_units == 1 && s.w1 == 1 && s.w2 == 1 && s.phase == Phase::Idle))]
    }
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<20} phase={:?} visible w1={} w2={} buffered=({},{}) attempts={} committed={}\n",
                        i + 1, format!("{:?}", a), s.phase, s.w1, s.w2, s.buf1, s.buf2, s.attempts, s.committed_units);
    }
    out
}
