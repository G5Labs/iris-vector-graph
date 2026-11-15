//! Module 05, L1 part 2: one temporal bucket's edges and what the aggregate readers answer (F-0501; TMP-B1.7; the
//! whole-bucket read path of GetAggregate, TemporalIndex.cls:1445-1490; GetVelocity and FindBursts read the bucket
//! counter, TemporalIndex.cls:757-806).
//!
//! State: the temporal edges of one bucket of one (graph, source, predicate, target): `tout[ts]` = weight, ts the
//! offset in the bucket, 0 .. BUCKET - 1 (BUCKET = 300, TemporalIndex.cls:4). Labels: a temporal write in mode
//! insert, skip or update (`Write`), a temporal delete (`Delete`), a whole-bucket aggregate read (`ReadAgg`: count and
//! sum), a bucket-counter read (`ReadBucket`).
//!
//! Business rules: **an update replaces the edge** (CONTEXT.md:173-177: an upsert "replaces the edge"; spec 221): it
//! changes the weight, not the number of edges; **a collision or skip changes nothing** (spec 254 FR-003); **a
//! whole-bucket read answers the number of the bucket's edges and the sum of their weights, and the bucket counter
//! the number of edges** (TMP-B1.7).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub enum Mode { Insert, Skip, Update }

pub open spec fn bw() -> nat { 300 }

pub struct TS1 { pub tout: Map<int, int> }

pub enum TL1 {
    Write { ts: int, w: int, mode: Mode },
    Delete { ts: int },
    ReadAgg { count: int, sum: int },
    ReadBucket { n: int },
}

/// The number of edges at offsets 0 .. n - 1.
pub open spec fn cnt(m: Map<int, int>, n: nat) -> int
    decreases n,
{
    if n == 0 { 0 } else { cnt(m, (n - 1) as nat) + if m.contains_key(n - 1) { 1int } else { 0int } }
}
/// The sum of their weights.
pub open spec fn sm(m: Map<int, int>, n: nat) -> int
    decreases n,
{
    if n == 0 { 0 } else { sm(m, (n - 1) as nat) + if m.contains_key(n - 1) { m[n - 1] } else { 0int } }
}

pub proof fn lemma_cnt_empty(n: nat)
    ensures cnt(Map::<int, int>::empty(), n) == 0, sm(Map::<int, int>::empty(), n) == 0,
    decreases n,
{
    if n > 0 { lemma_cnt_empty((n - 1) as nat); }
}

pub proof fn lemma_cnt_nonneg(m: Map<int, int>, n: nat)
    ensures cnt(m, n) >= 0,
    decreases n,
{
    if n > 0 { lemma_cnt_nonneg(m, (n - 1) as nat); }
}

pub proof fn lemma_cnt_insert(m: Map<int, int>, n: nat, i: int, w: int)
    ensures
        cnt(m.insert(i, w), n) == cnt(m, n) + (if 0 <= i < n && !m.contains_key(i) { 1int } else { 0int }),
        sm(m.insert(i, w), n) == sm(m, n) + (if 0 <= i < n { w - (if m.contains_key(i) { m[i] } else { 0int }) } else { 0int }),
    decreases n,
{
    if n > 0 { lemma_cnt_insert(m, (n - 1) as nat, i, w); }
}

pub proof fn lemma_cnt_remove(m: Map<int, int>, n: nat, i: int)
    ensures
        cnt(m.remove(i), n) == cnt(m, n) - (if 0 <= i < n && m.contains_key(i) { 1int } else { 0int }),
        sm(m.remove(i), n) == sm(m, n) - (if 0 <= i < n && m.contains_key(i) { m[i] } else { 0int }),
    decreases n,
{
    if n > 0 { lemma_cnt_remove(m, (n - 1) as nat, i); }
}

pub struct TaggL1;

impl Contract for TaggL1 {
    type S = TS1;
    type L = TL1;

    open spec fn init(s: TS1) -> bool { s.tout == Map::<int, int>::empty() }

    open spec fn next(s: TS1, l: TL1, t: TS1) -> bool {
        match l {
            TL1::Write { ts, w, mode } =>
                0 <= ts < bw() && if !(mode is Update) && s.tout.contains_key(ts) { t == s } else { t == (TS1 { tout: s.tout.insert(ts, w) }) },
            TL1::Delete { ts } => s.tout.contains_key(ts) && t == (TS1 { tout: s.tout.remove(ts) }),
            TL1::ReadAgg { count, sum } => count == cnt(s.tout, bw()) && sum == sm(s.tout, bw()) && t == s,
            TL1::ReadBucket { n } => n == cnt(s.tout, bw()) && t == s,
        }
    }
}

/// Every edge of the bucket is at an offset of the bucket.
pub open spec fn inv1(s: TS1) -> bool { forall|ts: int| #[trigger] s.tout.contains_key(ts) ==> 0 <= ts < bw() }

impl SafeContract for TaggL1 {
    open spec fn inv(s: TS1) -> bool { inv1(s) }
    proof fn init_safe(s: TS1) {}
    proof fn step_safe(s: TS1, l: TL1, t: TS1) {}
}

/// CONTEXT.md:173-177: an update at an occupied coordinate replaces the edge: the bucket holds as many edges as before
/// and their weights sum to the old sum minus the old weight plus the new one (F-0501's double count is excluded).
pub proof fn theorem_update_replaces_the_edge(s: TS1, ts: int, w: int, t: TS1)
    requires TaggL1::next(s, TL1::Write { ts, w, mode: Mode::Update }, t), s.tout.contains_key(ts),
    ensures cnt(t.tout, bw()) == cnt(s.tout, bw()), sm(t.tout, bw()) == sm(s.tout, bw()) - s.tout[ts] + w,
{
    lemma_cnt_insert(s.tout, bw(), ts, w);
}

/// Spec 254 FR-003: a collision (mode insert) or a skip at an occupied coordinate changes nothing.
pub proof fn theorem_collision_changes_nothing(s: TS1, ts: int, w: int, mode: Mode, t: TS1)
    requires TaggL1::next(s, TL1::Write { ts, w, mode }, t), !(mode is Update), s.tout.contains_key(ts),
    ensures t == s,
{
}

/// TMP-B1.7: a whole-bucket aggregate read answers exactly the number of the bucket's edges and their weight sum.
pub proof fn theorem_aggregate_read_is_exact(s: TS1, count: int, sum: int, t: TS1)
    requires TaggL1::next(s, TL1::ReadAgg { count, sum }, t),
    ensures count == cnt(s.tout, bw()), sum == sm(s.tout, bw()),
{
}

} // verus!
