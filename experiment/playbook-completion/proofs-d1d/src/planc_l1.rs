//! Module 09, L1 part 1: answers of natively planned reads whose walk may run compiled (spec 257, ADR-0014).
//!
//! Sources: docs/adr/0014-native-plans-are-compiled-to-classes-at-run-time.md:19 ("A compiled class answers exactly as
//! the interpreter does"); NAT-I3 (a read never runs code written for another plan shape); NAT-T5.16 (a ready entry
//! runs only the class written for its own shape); spec 253 FR-002 (a native result equals the SQL path's).
//!
//! Abstraction (explicit): the data are one value `db`; a plan shape is an integer; the interpreter's answer for a
//! shape over the data is `interp(shape, db) = (shape, db)`: an answer identifies the shape it was computed for, so code
//! written for one shape answers differently for another (as the live collision did: [[2]] where SQL answered [[1]]).
//! Each anchor's walk is one answer.
//!
//! Business rule: **every answer of a read of shape s is the interpreter's answer for s over the data at that moment.**
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct PC1 { pub db: int }
pub enum PCL1 { Write { db: int }, Answer { s: int, a: (int, int) } }

pub open spec fn interp(shape: int, db: int) -> (int, int) { (shape, db) }

pub struct PcL1;

impl Contract for PcL1 {
    type S = PC1;
    type L = PCL1;
    open spec fn init(s: PC1) -> bool { true }
    open spec fn next(s: PC1, l: PCL1, t: PC1) -> bool {
        match l {
            PCL1::Write { db } => t == (PC1 { db }),
            PCL1::Answer { s: sh, a } => t == s && a == interp(sh, s.db),
        }
    }
}

impl SafeContract for PcL1 {
    open spec fn inv(s: PC1) -> bool { true }
    proof fn init_safe(s: PC1) {}
    proof fn step_safe(s: PC1, l: PCL1, t: PC1) {}
}

/// ADR-0014:19 / NAT-I3: an answer for shape s is s's own, whatever ran it.
pub proof fn theorem_every_answer_is_its_shapes(s: PC1, sh: int, a: (int, int), t: PC1)
    requires PcL1::next(s, PCL1::Answer { s: sh, a }, t),
    ensures a == interp(sh, s.db), a.0 == sh,
{
}

} // verus!
