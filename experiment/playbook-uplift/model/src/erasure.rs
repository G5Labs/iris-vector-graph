//! Machine 3: graph erasure interleaved with ledger commits into the same graph (ADR-0004; F-1114, F-1201).
//!
//! Graph G holds edge e0 (committed, with its live ledger statement). A ledger process P commits changesets that
//! create e1 or delete e0, each in its own transaction under the ledger head lock (Graph.KG.Ledger.Commit):
//! step 1 writes the row and the statement entry (visible to other processes before commit, P-0002; the row is
//! row-locked by P), step 2 commits or rolls back. The eraser E runs Graph.KG.Eraser.EraseGraph(G) in its own
//! transaction: step 1 deletes G's rows (its DELETE waits on a row another transaction holds, so it cannot run
//! while P has an uncommitted row of G; the rows it deletes stay locked until it commits); step 2 kills every
//! statement entry of G it can see (EraseLedgerFor, Eraser.cls:1117-1144: a $Order over ^IVG.Ledger("stmt"),
//! uncommitted entries included); step 3 commits.
//!
//! - `as-built`: the eraser takes no ledger head lock (Eraser.cls; F-1114).
//! - `reviewed`: the eraser takes the head lock from step 1 to step 3.
//!
//! Property (ADR-0004 in both directions, checked whenever no transaction is open): the live statements of G are
//! exactly the live edges of G. ADR-0004 states "no live statement outlives its content"; its converse, "no live
//! edge recorded by the ledger lacks its statement", is what the next ledger delete of that edge relies on.
use explorer::*;
use std::collections::BTreeSet;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum P { Idle, Created, Deleted }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum E { Idle, RowsDeleted, StmtsKilled, Done }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S3 {
    /// committed rows of G
    pub rows: BTreeSet<u8>,
    /// rows as the open transactions see them (committed rows plus P's insert, minus deletes)
    pub view: BTreeSet<u8>,
    /// ledger statement entries of G (globals: visible to every process at once)
    pub stmts: BTreeSet<u8>,
    pub p: P,
    pub e: E,
    /// rows E deleted (locked by E until it commits)
    pub e_deleted: BTreeSet<u8>,
    /// statement entries E killed (restored if it rolled back; it does not here)
    pub head: Option<char>,
    pub commits: u8,
}

#[derive(Clone, Debug)]
pub enum A3 { PCreate, PDelete, PCommit, PRollback, E1, E2, E3 }

pub struct M3 { pub design: Design }

impl Model for M3 {
    type State = S3;
    type Action = A3;
    fn init_states(&self) -> Vec<S3> {
        let one: BTreeSet<u8> = [0].into_iter().collect();
        vec![S3 { rows: one.clone(), view: one.clone(), stmts: one, p: P::Idle, e: E::Idle, e_deleted: BTreeSet::new(),
                  head: None, commits: 0 }]
    }
    fn actions(&self, _: &S3) -> Vec<A3> { vec![A3::PCreate, A3::PDelete, A3::PCommit, A3::PRollback, A3::E1, A3::E2, A3::E3] }
    fn next(&self, s: &S3, a: &A3) -> Option<S3> {
        let mut u = s.clone();
        let locked_by_e = |r: u8| s.e_deleted.contains(&r);
        match a {
            A3::PCreate => {
                if s.p != P::Idle || s.commits >= 2 || s.view.contains(&1) || s.head.is_some() { return None; }
                u.head = Some('P');
                u.view.insert(1);
                u.stmts.insert(1);
                u.p = P::Created;
            }
            A3::PDelete => {
                if s.p != P::Idle || s.commits >= 2 || !s.view.contains(&0) || locked_by_e(0) || s.head.is_some() { return None; }
                u.head = Some('P');
                u.view.remove(&0);
                u.stmts.remove(&0);
                u.p = P::Deleted;
            }
            A3::PCommit => {
                match s.p {
                    P::Created => { u.rows.insert(1); }
                    P::Deleted => { u.rows.remove(&0); }
                    P::Idle => return None,
                }
                u.p = P::Idle;
                u.head = None;
                u.commits += 1;
            }
            A3::PRollback => {
                match s.p {
                    P::Created => { u.view.remove(&1); if s.stmts.contains(&1) { u.stmts.remove(&1); } }
                    P::Deleted => { u.view.insert(0); u.stmts.insert(0); }
                    P::Idle => return None,
                }
                u.p = P::Idle;
                u.head = None;
            }
            A3::E1 => {
                if s.e != E::Idle { return None; }
                // The DELETE waits for a row P has inserted or deleted and not yet committed.
                if s.p != P::Idle { return None; }
                if self.design == Design::Reviewed {
                    if s.head.is_some() { return None; }
                    u.head = Some('E');
                }
                u.e_deleted = s.view.clone();
                u.view.clear();
                u.e = E::RowsDeleted;
            }
            A3::E2 => {
                if s.e != E::RowsDeleted { return None; }
                u.stmts.clear();
                u.e = E::StmtsKilled;
            }
            A3::E3 => {
                if s.e != E::StmtsKilled { return None; }
                for r in &s.e_deleted { u.rows.remove(r); }
                u.e_deleted.clear();
                u.e = E::Done;
                if self.design == Design::Reviewed { u.head = None; }
            }
        }
        // Rows P creates after E's delete are visible to E's later steps but not deleted by them.
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S3>> {
        vec![invariant("statements of G equal the edges of G whenever no transaction is open", |s: &S3| {
            if s.p != P::Idle || matches!(s.e, E::RowsDeleted | E::StmtsKilled) { return true; }
            s.stmts == s.rows
        })]
    }
    fn always_possibly(&self) -> Vec<Invariant<S3>> {
        vec![invariant("quiescent", |s: &S3| s.p == P::Idle && matches!(s.e, E::Idle | E::Done))]
    }
}

pub fn show(c: &Counterexample<S3, A3>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<10} rows={:?} statements={:?} P={:?} E={:?} head={:?}\n", i + 1, format!("{:?}", a),
                        s.rows, s.stmts, s.p, s.e, s.head);
    }
    out
}
