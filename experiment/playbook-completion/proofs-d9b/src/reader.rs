//! Participant contract **Reader** (D-9b): the processes reading ledger records — `history`, `records`, `export`, and
//! the record read of `verify()` (client.py:687-739; replay.py:231-269, 806-835). It sees only its own state: each
//! read in progress, the redaction epoch it saw when it began, and the revisions it has read so far.
//!
//! As built a reader checks the redaction marker once, before reading (`_refuse_while_redacting`, client.py:720-728),
//! then reads the records lazily in pages (5,000 records per page, replay.py:17), with no lock and no later check.
//! One `Page` here is one revision's records as they are at that moment (a page boundary may fall anywhere; one
//! revision per step over-approximates every page size). What the reader may return, and when it must refuse, is the
//! protocol's decision (`protocol_rd`).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;

verus! {

/// A read in progress: the epoch seen at its start, and the revisions read so far (revision i at `view[i]`).
pub struct RdProc { pub e0: nat, pub view: Seq<Seq<Rec>> }

pub struct ReaderS { pub rd: Map<nat, RdProc> }

pub enum ReaderL {
    /// q found no marker and read the epoch e0.
    Begin { q: nat, e0: nat },
    /// q read the next revision's records `rs`.
    Page { q: nat, rs: Seq<Rec> },
    /// q returned its view to its caller.
    Accept { q: nat },
    /// q refused (redaction_in_progress) or gave up to retry.
    Refuse { q: nat },
}

pub open spec fn reader_pre(r: ReaderS, x: ReaderL) -> bool {
    match x {
        ReaderL::Begin { q, e0 } => !r.rd.contains_key(q),
        ReaderL::Page { q, rs } => r.rd.contains_key(q),
        ReaderL::Accept { q } => r.rd.contains_key(q),
        ReaderL::Refuse { q } => r.rd.contains_key(q),
    }
}

pub open spec fn reader_step(r: ReaderS, x: ReaderL) -> ReaderS {
    match x {
        ReaderL::Begin { q, e0 } => ReaderS { rd: r.rd.insert(q, RdProc { e0, view: Seq::empty() }) },
        ReaderL::Page { q, rs } => ReaderS { rd: r.rd.insert(q, RdProc { view: r.rd[q].view.push(rs), ..r.rd[q] }) },
        ReaderL::Accept { q } => ReaderS { rd: r.rd.remove(q) },
        ReaderL::Refuse { q } => ReaderS { rd: r.rd.remove(q) },
    }
}

pub struct Reader;

impl Contract for Reader {
    type S = ReaderS;
    type L = ReaderL;

    open spec fn init(r: ReaderS) -> bool { r.rd == Map::<nat, RdProc>::empty() }

    open spec fn next(r: ReaderS, x: ReaderL, u: ReaderS) -> bool { reader_pre(r, x) && u == reader_step(r, x) }
}

/// The reader's own invariant: none beyond its state's shape.
pub open spec fn reader_inv(r: ReaderS) -> bool { true }

impl SafeContract for Reader {
    open spec fn inv(r: ReaderS) -> bool { reader_inv(r) }

    proof fn init_safe(r: ReaderS) {}

    proof fn step_safe(r: ReaderS, x: ReaderL, u: ReaderS) {}
}

} // verus!
