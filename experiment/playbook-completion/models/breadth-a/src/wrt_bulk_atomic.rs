//! Family wrt_bulk_atomic (module 03; finding F-0305; statement WRT-B3.19).
//!
//! `bulk_create_nodes` (and `bulk_ingest_edges`) with no caller transaction and the server loader available:
//! iris_vector_graph/_engine/nodes_edges.py:1715-1757 (edges 2046-2071). The call opens a WriteTxn on the cursor
//! (`Begin`), then sends the batch in chunks of 1,000 to Graph.KG.EdgeScan.BulkIngestNodesSQL through
//! `iris_obj = txn.native() if txn.joined else self._iris_obj()`; on an engine made by `from_connect`,
//! `_iris_obj()` is a Native API connection of its own (engine.py:1916-1942), i.e. another server process. Each
//! loader call runs TSTART ... TCOMMIT (EdgeScan.cls:352, 424) and on error `TROLLBACK 1` and rethrows
//! (EdgeScan.cls:425-428). On any exception the call rolls the cursor's WriteTxn back and falls back to the SQL path
//! over the whole batch (nodes_edges.py:1754-1757), which itself commits or rolls back and raises.
//!
//! Modeled: a batch of two chunks (A, B); each loader call may succeed or fail; the SQL fallback may succeed or
//! fail. State: committed rows of A and B, rows pending in the cursor's transaction, the call's phase.
//!
//! Designs:
//! - `AsBuilt`: the loader runs in another process, so each chunk's TCOMMIT is a durable commit of its own.
//! - `Reviewed`: the loader runs on the cursor's own process (`txn.native()` in every case, the finding's fix):
//!   each chunk's TSTART/TCOMMIT is a nested level inside the WriteTxn, so nothing is durable before
//!   `txn.commit()`, and `txn.rollback()` takes back every chunk.
//! - `SqlCommit` (negative control): the cursor's process, but each chunk ends with SQL COMMIT, which ends every
//!   level (P-0301).
//!
//! Invariant `WRT-B3.19` (USER_GUIDE.md:236-241: with none open, "each write ... is a transaction of its own"):
//! when the call has returned or raised, the batch's rows are committed all together or not at all.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, SqlCommit }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Phase { Start, Loading(u8), Loaded, Fallback, Returned, Raised }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub committed: [bool; 2],
    pub pending: [bool; 2],
    pub txn_open: bool,
    pub phase: Phase,
}

#[derive(Clone, Debug)]
pub enum A { Begin, ChunkOk, ChunkFail, Commit, FallbackOk, FallbackFail }

pub struct M { pub design: Design }

pub const INV: &str = "WRT-B3.19: a bulk write commits all of its batch or none of it";

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { committed: [false; 2], pending: [false; 2], txn_open: false, phase: Phase::Start }]
    }
    fn actions(&self, _: &S) -> Vec<A> { vec![A::Begin, A::ChunkOk, A::ChunkFail, A::Commit, A::FallbackOk, A::FallbackFail] }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        match a {
            A::Begin => { if s.phase != Phase::Start { return None; } u.txn_open = true; u.phase = Phase::Loading(0); }
            A::ChunkOk => {
                let Phase::Loading(i) = s.phase else { return None };
                let i = i as usize;
                match self.design {
                    Design::AsBuilt => u.committed[i] = true,
                    Design::Reviewed => u.pending[i] = true,
                    Design::SqlCommit => {
                        // COMMIT ends every level: the chunk and everything pending become durable
                        u.committed[i] = true;
                        for j in 0..2 { if s.pending[j] { u.committed[j] = true; } }
                        u.pending = [false; 2];
                    }
                }
                u.phase = if i == 1 { Phase::Loaded } else { Phase::Loading(1) };
            }
            A::ChunkFail => {
                // the loader's TROLLBACK 1 takes back its own chunk; Python rolls back the WriteTxn
                let Phase::Loading(_) = s.phase else { return None };
                u.pending = [false; 2]; u.txn_open = false; u.phase = Phase::Fallback;
            }
            A::Commit => {
                if s.phase != Phase::Loaded { return None; }
                for j in 0..2 { if s.pending[j] { u.committed[j] = true; } }
                u.pending = [false; 2]; u.txn_open = false; u.phase = Phase::Returned;
            }
            A::FallbackOk => { if s.phase != Phase::Fallback { return None; } u.committed = [true; 2]; u.phase = Phase::Returned; }
            A::FallbackFail => { if s.phase != Phase::Fallback { return None; } u.phase = Phase::Raised; }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(INV, |s: &S| !matches!(s.phase, Phase::Returned | Phase::Raised) || s.committed[0] == s.committed[1])]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("the call returns or raises", |s: &S| matches!(s.phase, Phase::Returned | Phase::Raised))]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("03", "wrt_bulk_atomic");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::SqlCommit };
    vec![
        check("wrt_bulk_atomic-as-built-F0305", md, fam, "as-built", "safety", Expect::Violation(INV), &Keep::safety(&ab)),
        check("wrt_bulk_atomic-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &Keep::safety(&rv)),
        check("wrt_bulk_atomic-control-sql-commit", md, fam, "control", "safety", Expect::Violation(INV), &Keep::safety(&ct)),
        check("wrt_bulk_atomic-reviewed-progress", md, fam, "reviewed", "progress", Expect::Pass, &Keep::progress(&rv)),
        reach("wrt_bulk_atomic-reviewed-reach-fallback-raised", md, fam, "reviewed", &rv,
              "never: a chunk fails and the fallback raises", |s: &S| s.phase == Phase::Raised),
        reach("wrt_bulk_atomic-reviewed-reach-returned", md, fam, "reviewed", &rv,
              "never: the whole batch is committed by the loader", |s: &S| s.phase == Phase::Returned && s.committed == [true; 2]),
    ]
}
