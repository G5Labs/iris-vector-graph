//! Participant contract **Store** (D-9): the content tables as other processes see them (READ UNCOMMITTED), the
//! statement index, the ghost provenance of each key, and the erasure's open transaction **with its rollback**.
//! It sees only its own state.
//!
//! State (pin 3eaa79cf):
//! - `rows`    the content tables keyed by (graph, id) as every process reads them: IRIS contract clause E-VIS
//!             (`iris-contract/CONTRACT.md` "Visibility": SQL SELECT reads uncommitted rows) — an open transaction's
//!             writes are visible at once.
//! - `unrec`   ghost: the keys whose current row (present or absent) was last written outside the ledger (a
//!             ledger-bypassing writer, the 46 undeclared writers of the writer census). A ledger write of a key
//!             removes it; a rollback restores its earlier status. Nothing in the product holds this; it is how the
//!             model says "this row is not the content of any ledger record" (core model M2's incarnations).
//! - `stmts`   the live statement index `^IVG.Ledger("tuple", s, p, o, graphKey)` (Ledger.cls:9) — globals, unisolated.
//! - `shist`   (D-9b) the statement **history** `^IVG.Ledger("stmt", id) = $LB(s, p, o, graph, createdSeq, deletedSeq)`
//!             (Ledger.cls:8): the edges that have an entry, live or closed. A create opens one; a delete closes it and
//!             the closed entry stays (it holds the edge's endpoints and graph); the erasure's EraseLedgerFor kills every
//!             entry of its graph, live or closed (Eraser.cls:1117-1144); the redaction's DropStatements kills the
//!             target's entries, live or closed (LedgerRedact.cls:444-471). One key stands for every statement id of
//!             that edge.
//! - `erasing` an open erasure transaction (Eraser.EraseGraph / EraseIdSet, Eraser.cls:47-261): its target `e`, the
//!             rows it deleted `saved` and the statement entries it killed `sst` (its undo log), and whether its
//!             statement cleanup (EraseLedgerFor, cls:1117-1144) ran. Its TCOMMIT may be only an inner level of a
//!             caller's transaction (E-NEST; erase_graph inside a caller transaction, F-C1201), so the erasure stays
//!             open after its cleanup until the outermost transaction commits (`EraseCommit`) or rolls back
//!             (`EraseAbort`: clause E-ROLLBACK-OTHER, value-based: a row present again is left alone; E-STOP: a
//!             stopped process rolls back).
//!
//! The store accepts every write at any time, as built (tables have no notion of an erasure or a redaction in
//! progress). Row locks, serialization with the ledger and with redaction are the protocols' decisions.
//! Its own invariant is therefore only structural: with rollback, the statement index's consistency with the rows
//! depends on coordination and is a business invariant (`biz::key_ok`), not the store's.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;

verus! {

pub struct Ers { pub e: Dom, pub saved: Map<Key, int>, pub sst: Set<Key>, pub ssh: Set<Key>, pub idx: bool }

pub struct StoreS {
    pub rows: Map<Key, int>,
    pub unrec: Set<Key>,
    pub stmts: Set<Key>,
    pub shist: Set<Key>,
    pub erasing: Option<Ers>,
}

pub enum StoreL {
    /// Apply a ledger changeset's records to the tables and the statement index (LedgerApply).
    Apply { cs: Seq<Content> },
    /// The erasure's row deletes (its transaction opens).
    EraseRows { e: Dom },
    /// The erasure's statement cleanup (EraseLedgerFor); the transaction stays open.
    EraseIndex,
    /// The erasure's outermost commit.
    EraseCommit,
    /// The erasure's rollback (caller TROLLBACK, driver rollback(), or process stop).
    EraseAbort,
    /// A non-ledger write of row k (insert/update `Some(v)`, delete `None`), visible at once.
    Write { k: Key, v: Option<int> },
    /// Its rollback: k's row and provenance as they were before it.
    Undo { k: Key, before: Option<int>, was: bool },
    /// The redaction's final DropStatements (statement cleanup of the target): live and closed entries.
    Drop { sc: Dom },
}

pub open spec fn store_apply(s: StoreS, cs: Seq<Content>) -> StoreS {
    StoreS {
        rows: replay_recs(s.rows, lives(cs)),
        stmts: stmt_recs(s.stmts, lives(cs)),
        shist: shist_recs(s.shist, lives(cs)),
        unrec: unrec_recs(s.unrec, lives(cs)),
        ..s
    }
}

pub open spec fn store_erase_rows(s: StoreS, e: Dom) -> StoreS {
    StoreS {
        rows: outside(s.rows, e),
        erasing: Some(Ers { e, saved: inside(s.rows, e), sst: Set::empty(), ssh: Set::empty(), idx: false }),
        ..s
    }
}

pub open spec fn store_erase_index(s: StoreS) -> StoreS {
    let r = s.erasing->0;
    StoreS {
        stmts: s.stmts.filter(|k: Key| !member(r.e, k)),
        shist: s.shist.filter(|k: Key| !member(r.e, k)),
        erasing: Some(Ers { sst: s.stmts.filter(|k: Key| member(r.e, k)), ssh: s.shist.filter(|k: Key| member(r.e, k)), idx: true, ..r }),
        ..s
    }
}

pub open spec fn store_erase_commit(s: StoreS) -> StoreS { StoreS { erasing: None, ..s } }

pub open spec fn store_erase_abort(s: StoreS) -> StoreS {
    let r = s.erasing->0;
    StoreS { rows: r.saved.union_prefer_right(s.rows), stmts: s.stmts.union(r.sst), shist: s.shist.union(r.ssh), erasing: None, ..s }
}

pub open spec fn store_write(s: StoreS, k: Key, v: Option<int>) -> StoreS {
    StoreS { rows: oset(s.rows, k, v), unrec: s.unrec.insert(k), ..s }
}

pub open spec fn store_undo(s: StoreS, k: Key, before: Option<int>, was: bool) -> StoreS {
    StoreS { rows: oset(s.rows, k, before), unrec: if was { s.unrec.insert(k) } else { s.unrec.remove(k) }, ..s }
}

pub open spec fn store_drop(s: StoreS, sc: Dom) -> StoreS {
    StoreS { stmts: s.stmts.filter(|k: Key| !member(sc, k)), shist: s.shist.filter(|k: Key| !member(sc, k)), ..s }
}

pub open spec fn store_pre(s: StoreS, x: StoreL) -> bool {
    match x {
        StoreL::EraseRows { e } => s.erasing is None,
        StoreL::EraseIndex => s.erasing is Some && !s.erasing->0.idx,
        StoreL::EraseCommit => s.erasing is Some && s.erasing->0.idx,
        StoreL::EraseAbort => s.erasing is Some,
        _ => true,
    }
}

pub open spec fn store_step(s: StoreS, x: StoreL) -> StoreS {
    match x {
        StoreL::Apply { cs } => store_apply(s, cs),
        StoreL::EraseRows { e } => store_erase_rows(s, e),
        StoreL::EraseIndex => store_erase_index(s),
        StoreL::EraseCommit => store_erase_commit(s),
        StoreL::EraseAbort => store_erase_abort(s),
        StoreL::Write { k, v } => store_write(s, k, v),
        StoreL::Undo { k, before, was } => store_undo(s, k, before, was),
        StoreL::Drop { sc } => store_drop(s, sc),
    }
}

pub struct Store;

impl Contract for Store {
    type S = StoreS;
    type L = StoreL;

    open spec fn init(s: StoreS) -> bool {
        &&& s.rows == Map::<Key, int>::empty()
        &&& s.unrec == Set::<Key>::empty()
        &&& s.stmts == Set::<Key>::empty()
        &&& s.shist == Set::<Key>::empty()
        &&& s.erasing is None
    }

    open spec fn next(s: StoreS, x: StoreL, u: StoreS) -> bool {
        store_pre(s, x) && u == store_step(s, x)
    }
}

/// The open erasure's undo log lies in its target; killed statement entries are edges' and exist only after cleanup.
pub open spec fn ers_inv(r: Ers) -> bool {
    &&& forall|k: Key| #[trigger] r.saved.contains_key(k) ==> member(r.e, k)
    &&& forall|k: Key| #[trigger] r.sst.contains(k) ==> k.edge && member(r.e, k) && r.idx
    &&& forall|k: Key| #[trigger] r.ssh.contains(k) ==> k.edge && member(r.e, k) && r.idx
}

/// The store's own invariant (structural only): statement entries are edges'; the open erasure's undo log is well formed.
pub open spec fn store_inv(s: StoreS) -> bool {
    &&& forall|k: Key| #[trigger] s.stmts.contains(k) ==> k.edge
    &&& forall|k: Key| #[trigger] s.shist.contains(k) ==> k.edge
    &&& s.erasing is Some ==> ers_inv(s.erasing->0)
}

pub proof fn lemma_store_safe(s: StoreS, x: StoreL)
    requires store_inv(s), store_pre(s, x),
    ensures store_inv(store_step(s, x)),
{
    let u = store_step(s, x);
    match x {
        StoreL::Apply { cs } => {
            assert forall|k: Key| #[trigger] u.stmts.contains(k) implies k.edge by {
                lemma_recs_at(s.rows, s.rows, s.stmts, s.unrec, lives(cs), k);
            }
            assert forall|k: Key| #[trigger] u.shist.contains(k) implies k.edge by {
                lemma_shist_at(s.shist, lives(cs), k);
            }
        }
        StoreL::EraseAbort => {
            let r = s.erasing->0;
            assert forall|k: Key| #[trigger] u.stmts.contains(k) implies k.edge by {
                if !s.stmts.contains(k) { assert(r.sst.contains(k)); }
            }
            assert forall|k: Key| #[trigger] u.shist.contains(k) implies k.edge by {
                if !s.shist.contains(k) { assert(r.ssh.contains(k)); }
            }
        }
        _ => {}
    }
}

impl SafeContract for Store {
    open spec fn inv(s: StoreS) -> bool { store_inv(s) }

    proof fn init_safe(s: StoreS) {}

    proof fn step_safe(s: StoreS, x: StoreL, u: StoreS) {
        lemma_store_safe(s, x);
    }
}

} // verus!
