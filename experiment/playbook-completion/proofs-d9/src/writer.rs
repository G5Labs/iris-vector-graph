//! Participant contract **Writer** (new in D-9): the ledger-bypassing content writers, i.e. every process that writes
//! a content row outside a ledger commit (the writer census's 46 undeclared writers: EdgeScan bulk ingest, FHIRGraph,
//! TemporalPolicy.DropRows, Adjacency.RetractTemporalRow(s), the SQL store's write_nodes/write_edges/delete_edges,
//! nodes_edges store_node/bulk_ingest_edges, engine.create_node on a non-strict ledger, POST /admin/load, schema
//! inference and migrations). It sees only its own state: the open transactions and each one's undo record.
//!
//! - `open[k]`: an open transaction that wrote row k, with the row and provenance it found (`before`, `was`): its undo
//!   record (IRIS keeps the before-image of every SET/KILL/row write of an open transaction; E-ROLLBACK-OTHER).
//!   A writer's multi-row transaction is represented as one open transaction per row whose ends happen together;
//!   every interleaving of those is an execution here, so this over-approximates multi-row transactions.
//! - `Begin { k, before, was }`: the write itself (the protocol gives the store the row's new value and gives this
//!   participant the before-image); `Commit { k }`; `Abort { k }` (rollback or process stop, E-STOP).
//!
//! As built the writers take no ledger lock, never read the marker, and write at any moment (F-C1301, F-C1307).
//! Which of their transactions may overlap which redaction or erasure step is the protocol's decision
//! (`protocol_top`); the writer contract itself permits all of them.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;

verus! {

pub struct BTx { pub before: Option<int>, pub was: bool }

pub struct WrS { pub open: Map<Key, BTx> }

pub enum WrL {
    Begin { k: Key, before: Option<int>, was: bool },
    Commit { k: Key },
    Abort { k: Key },
}

pub open spec fn wr_pre(w: WrS, x: WrL) -> bool {
    match x {
        WrL::Begin { k, before, was } => !w.open.contains_key(k),
        WrL::Commit { k } => w.open.contains_key(k),
        WrL::Abort { k } => w.open.contains_key(k),
    }
}

pub open spec fn wr_step(w: WrS, x: WrL) -> WrS {
    match x {
        WrL::Begin { k, before, was } => WrS { open: w.open.insert(k, BTx { before, was }) },
        WrL::Commit { k } => WrS { open: w.open.remove(k) },
        WrL::Abort { k } => WrS { open: w.open.remove(k) },
    }
}

pub struct Writer;

impl Contract for Writer {
    type S = WrS;
    type L = WrL;

    open spec fn init(w: WrS) -> bool { w.open == Map::<Key, BTx>::empty() }

    open spec fn next(w: WrS, x: WrL, u: WrS) -> bool { wr_pre(w, x) && u == wr_step(w, x) }
}

/// The writer's own invariant: none beyond its state's shape (at most one open transaction per row is the map
/// itself). Everything about what its transactions may do to the redaction is the protocols' and Biz's.
pub open spec fn wr_inv(w: WrS) -> bool { true }

impl SafeContract for Writer {
    open spec fn inv(w: WrS) -> bool { wr_inv(w) }

    proof fn init_safe(w: WrS) {}

    proof fn step_safe(w: WrS, x: WrL, u: WrS) {}
}

} // verus!
