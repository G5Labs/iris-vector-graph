//! Module 17, L1: what the product claims about itself to an operator or a program (the status report's unknown
//! parts, the capability claims) and what an install of the pin's metadata gives (the driver).
//!
//! State: the server classes deployed in the namespace (`deployed`, by capability), the installed driver (`drv`, a
//! version code: 100 = 1.0.0, 532 = 5.3.2, 540 = 5.4.0) and the node rows written (`rows`).
//! Business rules:
//! - **the list of parts that can be unknown names every part the report may mark** (OPS-I2.3.3; status.py:10-11
//!   "What EngineStatus.unknown may name");
//! - **an availability claim is a fact about this namespace** and **a call answers only from a deployed class**
//!   (HD-1703 working answer: code support and namespace availability are different facts; the store's capability
//!   list is a static catalogue of what the code supports);
//! - **an install the pin's metadata admits gets a driver the product works with** (F-C1706; OPS-B5.4: write_nodes
//!   skips a duplicate row and keeps its old value).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct O1 { pub deployed: Set<nat>, pub drv: Option<nat>, pub rows: nat }

pub enum OL1 {
    /// initialize_schema compiles a capability's classes
    Deploy { cap: nat },
    /// status(): the parts marked unknown, and the published list of parts that can be unknown (STATUS_PARTS)
    Report { unknown: Set<nat>, parts: Set<nat> },
    /// engine.capabilities: is the capability available in this namespace
    Claim { cap: nat, avail: bool },
    /// store.capabilities(): does the code support the capability (a static catalogue)
    Catalogue { cap: nat, supported: bool },
    /// a call that needs the capability answers (ok) or raises
    Call { cap: nat, ok: bool },
    /// an install of the package (uv sync of the lock, or a fresh resolution) installs driver version v
    Install { v: nat },
    /// store.write_nodes of one row (`dup`: the row exists already)
    WriteNodes { dup: bool, ok: bool },
}

/// The capabilities the code supports (_FULL_CAPABILITIES: every algorithm).
pub open spec fn ncaps() -> nat { 22 }

/// Premise P-D1: driver versions from 5.4.0 on behave as the product expects (typed scores, the duplicate-row error
/// is_duplicate recognises, list parameters); 5.3.2 does not. Observed for 5.3.2 and 5.4.0 only (validation's
/// driver A/B, F-C1706); every other version is an extrapolation.
pub open spec fn drv_ok(v: nat) -> bool { v >= 540 }

pub struct OpscL1;

impl Contract for OpscL1 {
    type S = O1;
    type L = OL1;

    open spec fn init(s: O1) -> bool { s.drv is None && s.rows == 0 }

    open spec fn next(s: O1, l: OL1, t: O1) -> bool {
        match l {
            OL1::Deploy { cap } => t == O1 { deployed: s.deployed.insert(cap), ..s },
            OL1::Report { unknown, parts } => unknown.subset_of(parts) && t == s,
            OL1::Claim { cap, avail } => avail == s.deployed.contains(cap) && t == s,
            OL1::Catalogue { cap, supported } => supported == (cap < ncaps()) && t == s,
            OL1::Call { cap, ok } => ok == s.deployed.contains(cap) && t == s,
            OL1::Install { v } => drv_ok(v) && t == O1 { drv: Some(v), ..s },
            OL1::WriteNodes { dup, ok } => s.drv is Some && ok && t == (if dup { s } else { O1 { rows: s.rows + 1, ..s } }),
        }
    }
}

pub open spec fn inv1(s: O1) -> bool { s.drv is Some ==> drv_ok(s.drv->Some_0) }

impl SafeContract for OpscL1 {
    open spec fn inv(s: O1) -> bool { inv1(s) }
    proof fn init_safe(s: O1) {}
    proof fn step_safe(s: O1, l: OL1, t: O1) {}
}

/// OPS-I2.3.3: every part a report marks unknown is in the published list.
pub proof fn theorem_unknown_parts_are_listed(s: O1, unknown: Set<nat>, parts: Set<nat>, p: nat)
    requires OpscL1::next(s, OL1::Report { unknown, parts }, s), unknown.contains(p),
    ensures parts.contains(p),
{
}

/// HD-1703: availability is a fact about the namespace; the catalogue is about the code. A capability the code
/// supports but this namespace has not deployed is claimed supported and not available, and its calls raise.
pub proof fn theorem_catalogue_is_not_availability(s: O1, cap: nat)
    requires cap < ncaps(), !s.deployed.contains(cap),
    ensures
        OpscL1::next(s, OL1::Catalogue { cap, supported: true }, s),
        OpscL1::next(s, OL1::Claim { cap, avail: false }, s),
        OpscL1::next(s, OL1::Call { cap, ok: false }, s),
        !OpscL1::next(s, OL1::Call { cap, ok: true }, s),
{
}

/// OPS-B5.4 under any admitted install: a duplicate row is skipped and the write succeeds.
pub proof fn theorem_duplicate_is_skipped(s: O1, ok: bool, t: O1)
    requires OpscL1::next(s, OL1::WriteNodes { dup: true, ok }, t),
    ensures ok, t == s,
{
}

} // verus!
