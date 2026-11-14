//! Participant contract **Store**: the live content and its statement index, with the erasure steps.
//! It sees only its own state.
//!
//! State (pin 3eaa79cf):
//! - `rows`     the content tables keyed by (graph, id): Graph_KG.nodes, rdf_labels, rdf_props, rdf_edges.
//! - `stmts`    the live statement index `^IVG.Ledger("tuple", s, p, o, graphKey)` (Ledger.cls:9) of edge rows.
//! - `erasing`  an erasure transaction that has deleted its target's rows and not yet its statement entries
//!              (Eraser.EraseGraph: the SQL deletes, then EraseLedgerFor, Eraser.cls:1117-1144, then commit).
//!
//! The store accepts writes at any time (tables have no notion of an erasure in progress): that is the as-built
//! component. Serializing erasure with commits is the protocol's job (`protocol_sys`, HD-1201).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;

verus! {

pub struct StoreS {
    pub rows: Map<Key, int>,
    pub stmts: Set<Key>,
    pub erasing: Option<Tgt>,
}

pub enum StoreL {
    /// Apply a changeset's records to the tables and the statement index (LedgerApply, or a direct write such as
    /// the client's post-commit properties, client.py:430-487).
    Apply { cs: Seq<Content> },
    /// The erasure's row deletes (one open transaction).
    EraseRows { t: Tgt },
    /// The erasure's statement cleanup and commit (EraseLedgerFor).
    EraseIndex { t: Tgt },
}

pub open spec fn in_erasing(e: Option<Tgt>) -> spec_fn(Key) -> bool {
    |k: Key| e is Some && member(e->0, k)
}

pub open spec fn store_apply(s: StoreS, cs: Seq<Content>) -> StoreS {
    StoreS { rows: replay_recs(s.rows, lives(cs)), stmts: stmt_recs(s.stmts, lives(cs)), ..s }
}

pub open spec fn store_erase_rows(s: StoreS, t: Tgt) -> StoreS {
    StoreS { rows: outside(s.rows, t), erasing: Some(t), ..s }
}

pub open spec fn store_erase_index(s: StoreS, t: Tgt) -> StoreS {
    StoreS { stmts: s.stmts.filter(|k: Key| !member(t, k)), erasing: None, ..s }
}

pub open spec fn store_pre(s: StoreS, x: StoreL) -> bool {
    match x {
        StoreL::Apply { cs } => true,
        StoreL::EraseRows { t } => s.erasing is None,
        StoreL::EraseIndex { t } => s.erasing == Some(t),
    }
}

pub open spec fn store_step(s: StoreS, x: StoreL) -> StoreS {
    match x {
        StoreL::Apply { cs } => store_apply(s, cs),
        StoreL::EraseRows { t } => store_erase_rows(s, t),
        StoreL::EraseIndex { t } => store_erase_index(s, t),
    }
}

pub struct Store;

impl Contract for Store {
    type S = StoreS;
    type L = StoreL;

    open spec fn init(s: StoreS) -> bool {
        &&& s.rows == Map::<Key, int>::empty()
        &&& s.stmts == Set::<Key>::empty()
        &&& s.erasing is None
    }

    open spec fn next(s: StoreS, x: StoreL, u: StoreS) -> bool {
        store_pre(s, x) && u == store_step(s, x)
    }
}

/// The store's own invariant: no dangling statement entry outside an open erasure (every entry is an edge's and
/// names a live edge row, unless the open erasure covers it). The converse (every live edge has its entry) is not
/// the store's to keep: it needs commits serialized with erasure (`biz::inv_stmts`).
pub open spec fn store_inv(s: StoreS) -> bool {
    stmts_ok(s.rows, s.stmts, in_erasing(s.erasing))
}

pub proof fn lemma_store_safe(s: StoreS, x: StoreL)
    requires store_inv(s), store_pre(s, x),
    ensures store_inv(store_step(s, x)),
{
    let u = store_step(s, x);
    match x {
        StoreL::Apply { cs } => {
            lemma_stmts_recs(s.rows, s.stmts, lives(cs), in_erasing(s.erasing));
        }
        StoreL::EraseRows { t } => {
            assert forall|k: Key| #[trigger] u.stmts.contains(k) implies k.edge && (u.rows.contains_key(k) || in_erasing(u.erasing)(k)) by {
                assert(s.stmts.contains(k));
                if !member(t, k) { assert(u.rows.contains_key(k)); }
            }
        }
        StoreL::EraseIndex { t } => {
            assert forall|k: Key| #[trigger] u.stmts.contains(k) implies k.edge && (u.rows.contains_key(k) || in_erasing(u.erasing)(k)) by {
                assert(s.stmts.contains(k));
                assert(!member(t, k));
            }
        }
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
