//! Module 03, L1 part 3: a bulk write's atomicity (F-0305; WRT-B3.19; USER_GUIDE.md:236-241: with no transaction
//! open, "each write ... is a transaction of its own").
//!
//! State: the committed node rows, what a READ COMMITTED reader of another process sees. Labels: a bulk write of a
//! batch (`Bulk`: committed whole, or not at all when it raises) and a reader (`Read`).
//! Business rule: **no other process sees part of one bulk write**: the committed rows change by whole batches only.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct BS1 { pub rows: Set<int> }

pub enum BL1 {
    Bulk { batch: Set<int>, ok: bool },
    Read { rows: Set<int> },
}

pub struct BulkL1;

impl Contract for BulkL1 {
    type S = BS1;
    type L = BL1;

    open spec fn init(s: BS1) -> bool { s.rows == Set::<int>::empty() }

    open spec fn next(s: BS1, l: BL1, t: BS1) -> bool {
        match l {
            BL1::Bulk { batch, ok } => t == (if ok { BS1 { rows: s.rows.union(batch) } } else { s }),
            BL1::Read { rows } => rows == s.rows && t == s,
        }
    }
}

pub open spec fn inv1(s: BS1) -> bool { true }

impl SafeContract for BulkL1 {
    open spec fn inv(s: BS1) -> bool { inv1(s) }
    proof fn init_safe(s: BS1) {}
    proof fn step_safe(s: BS1, l: BL1, t: BS1) {}
}

/// WRT-B3.19: a bulk write commits all of its batch or changes nothing; a reader sees the committed rows.
pub proof fn theorem_bulk_all_or_nothing(s: BS1, batch: Set<int>, ok: bool, t: BS1)
    requires BulkL1::next(s, BL1::Bulk { batch, ok }, t),
    ensures (ok && forall|x: int| #[trigger] batch.contains(x) ==> t.rows.contains(x)) || (!ok && t == s),
{
}

} // verus!
