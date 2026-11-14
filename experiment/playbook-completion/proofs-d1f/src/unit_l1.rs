//! Module 16, L1: a unit of work of two writes sent to a server as one transaction: a Bolt explicit transaction
//! (BEGIN, RUN w1, RUN w2, COMMIT | ROLLBACK, with the Neo4j driver's managed-transaction retry) or one request to the
//! Neo4j HTTP commit route POST /db/neo4j/tx/commit with two statements.
//!
//! State: how many times each write is visible to other sessions (`v1`, `v2`) and whether the unit committed.
//! Business rules (API-B9.10 "a rollback should undo the writes made since the driver began its transaction";
//! API-B8.6.1 and Neo4j's tx/commit contract, P-1612; SYS-I4): **all or none** (a reader sees both writes or neither)
//! and **at most once** (a unit commits once, across the driver's retries).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct U1 { pub v1: nat, pub v2: nat, pub done: bool }

pub enum UL1 { Commit, Abort, Read { a: nat, b: nat } }

pub struct UnitL1;

impl Contract for UnitL1 {
    type S = U1;
    type L = UL1;

    open spec fn init(s: U1) -> bool { s.v1 == 0 && s.v2 == 0 && !s.done }

    open spec fn next(s: U1, l: UL1, t: U1) -> bool {
        match l {
            UL1::Commit => !s.done && t == U1 { v1: s.v1 + 1, v2: s.v2 + 1, done: true },
            UL1::Abort => t == s,
            UL1::Read { a, b } => a == s.v1 && b == s.v2 && t == s,
        }
    }
}

pub open spec fn inv1(s: U1) -> bool { s.v1 == s.v2 && s.v1 == (if s.done { 1nat } else { 0nat }) }

impl SafeContract for UnitL1 {
    open spec fn inv(s: U1) -> bool { inv1(s) }
    proof fn init_safe(s: U1) {}
    proof fn step_safe(s: U1, l: UL1, t: U1) {}
}

/// All or none: another session reads both writes of the unit or neither.
pub proof fn theorem_reader_sees_whole_units(s: U1, a: nat, b: nat)
    requires inv1(s), UnitL1::next(s, UL1::Read { a, b }, s),
    ensures a == b,
{
}

/// At most once: each write of the unit is visible at most once.
pub proof fn theorem_unit_at_most_once(s: U1)
    requires inv1(s),
    ensures s.v1 <= 1 && s.v2 <= 1,
{
}

} // verus!
