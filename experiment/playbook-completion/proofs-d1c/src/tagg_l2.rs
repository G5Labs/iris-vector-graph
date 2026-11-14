//! Module 05, L2 part 2: one bucket's stores at pin 3eaa79cf; refinement of `tagg_l1` for every step, the invariant,
//! and the control F-0501.
//!
//! State (production names; one graph, source, predicate and target, one bucket):
//! - `tout`   ^KG("tout", g, ts, s, p, o) = weight
//! - `bucket` ^KG("bucket", g, b, s): the source's bucket counter ($Increment per write, TemporalIndex.cls:100)
//! - `count`, `sum` ^KG("tagg", g, b, s, p, "count"/"sum") ($Increment, TemporalIndex.cls:117-118)
//! (min, max, the HLL sketch, edgeprop and tin are not modelled.)
//!
//! **Reviewed design** (F-0501 remedy, the explorer's tmp_bucket reviewed design): an update at an occupied coordinate
//! adds (new - old) to the sum and changes neither the count nor the bucket counter. As built, WriteStores' update
//! skips the collision check (TemporalIndex.cls:82-83) and then counts the edge again in bucket, count and sum.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::tagg_l1::*;

verus! {

pub struct TS2 { pub tout: Map<int, int>, pub bucket: int, pub count: int, pub sum: int }

pub enum TL2 {
    /// InsertEdge / BulkInsert -> WriteStores (TemporalIndex.cls:46-130).
    Write { ts: int, w: int, mode: Mode },
    /// DeleteTemporalEdge -> RemoveTemporalRow (TemporalIndex.cls:325-364) -> RebuildBucketAggregate (455-488).
    Delete { ts: int },
    /// GetAggregate over the whole bucket (TemporalIndex.cls:1460-1471).
    ReadAgg { count: int, sum: int },
    /// GetVelocity / FindBursts read the bucket counter.
    ReadBucket { n: int },
}

pub open spec fn f0501() -> bool { cfg!(feature = "control_f0501_update_counted_again") }

pub open spec fn init2(s: TS2) -> bool { s.tout == Map::<int, int>::empty() && s.bucket == 0 && s.count == 0 && s.sum == 0 }

pub open spec fn step2(s: TS2, l: TL2, t: TS2) -> bool {
    match l {
        TL2::Write { ts, w, mode } =>
            0 <= ts < bw() && if !(mode is Update) && s.tout.contains_key(ts) {
                t == s
            } else if !f0501() && s.tout.contains_key(ts) {
                t == (TS2 { tout: s.tout.insert(ts, w), sum: s.sum - s.tout[ts] + w, ..s })
            } else {
                t == (TS2 { tout: s.tout.insert(ts, w), bucket: s.bucket + 1, count: s.count + 1, sum: s.sum + w })
            },
        TL2::Delete { ts } =>
            s.tout.contains_key(ts)
                && t == (TS2 { tout: s.tout.remove(ts), bucket: if s.bucket - 1 <= 0 { 0 } else { s.bucket - 1 },
                               count: cnt(s.tout.remove(ts), bw()), sum: sm(s.tout.remove(ts), bw()) }),
        TL2::ReadAgg { count, sum } => count == s.count && sum == s.sum && t == s,
        TL2::ReadBucket { n } => n == s.bucket && t == s,
    }
}

pub open spec fn abst(s: TS2) -> TS1 { TS1 { tout: s.tout } }
pub open spec fn labt(l: TL2) -> Option<TL1> {
    match l {
        TL2::Write { ts, w, mode } => Some(TL1::Write { ts, w, mode }),
        TL2::Delete { ts } => Some(TL1::Delete { ts }),
        TL2::ReadAgg { count, sum } => Some(TL1::ReadAgg { count, sum }),
        TL2::ReadBucket { n } => Some(TL1::ReadBucket { n }),
    }
}

/// TMP-B1.7 on the layout: the aggregate and the counter describe exactly the edges tout holds.
pub open spec fn inv05t(s: TS2) -> bool {
    &&& inv1(abst(s))
    &&& s.count == cnt(s.tout, bw()) && s.sum == sm(s.tout, bw()) && s.bucket == cnt(s.tout, bw())
}

pub struct TaggL2;

impl Contract for TaggL2 {
    type S = TS2;
    type L = TL2;
    open spec fn init(s: TS2) -> bool { init2(s) }
    open spec fn next(s: TS2, l: TL2, t: TS2) -> bool { inv05t(s) && step2(s, l, t) }
}

pub struct TaggRaw;

impl Contract for TaggRaw {
    type S = TS2;
    type L = TL2;
    open spec fn init(s: TS2) -> bool { init2(s) }
    open spec fn next(s: TS2, l: TL2, t: TS2) -> bool { step2(s, l, t) }
}

proof fn lemma_write(s: TS2, ts: int, w: int, mode: Mode, t: TS2)
    requires inv05t(s), step2(s, TL2::Write { ts, w, mode }, t),
    ensures inv05t(t), step_or_stutter::<TaggL1>(abst(s), labt(TL2::Write { ts, w, mode }), abst(t)),
{
    lemma_cnt_insert(s.tout, bw(), ts, w);
    if !(mode is Update) && s.tout.contains_key(ts) {
    } else {
        if s.tout.contains_key(ts) {
            // an update replaces the edge: count and bucket counter unchanged, the sum adjusted
            // (control F-0501 fails here)
            assert(t.count == cnt(t.tout, bw()) && t.bucket == cnt(t.tout, bw()) && t.sum == sm(t.tout, bw()));
        }
        assert(t.tout == s.tout.insert(ts, w));
        assert forall|x: int| #[trigger] t.tout.contains_key(x) implies 0 <= x < bw() by {
            if x != ts { assert(s.tout.contains_key(x)); assert(abst(s).tout.contains_key(x)); }
        }
    }
}

proof fn lemma_delete(s: TS2, ts: int, t: TS2)
    requires inv05t(s), step2(s, TL2::Delete { ts }, t),
    ensures inv05t(t), step_or_stutter::<TaggL1>(abst(s), labt(TL2::Delete { ts }), abst(t)),
{
    lemma_cnt_remove(s.tout, bw(), ts);
    lemma_cnt_nonneg(s.tout.remove(ts), bw());
    assert(abst(s).tout.contains_key(ts));
    assert(0 <= ts < bw());
    assert forall|x: int| #[trigger] t.tout.contains_key(x) implies 0 <= x < bw() by {
        assert(s.tout.contains_key(x));
        assert(abst(s).tout.contains_key(x));
    }
}

proof fn lemma_step(s: TS2, l: TL2, t: TS2)
    requires inv05t(s), step2(s, l, t),
    ensures inv05t(t), step_or_stutter::<TaggL1>(abst(s), labt(l), abst(t)),
{
    match l {
        TL2::Write { ts, w, mode } => lemma_write(s, ts, w, mode, t),
        TL2::Delete { ts } => lemma_delete(s, ts, t),
        TL2::ReadAgg { count, sum } => {}
        TL2::ReadBucket { n } => {}
    }
}

impl Refines<TaggL1> for TaggL2 {
    open spec fn abs(s: TS2) -> TS1 { abst(s) }
    open spec fn lab(l: TL2) -> Option<TL1> { labt(l) }
    proof fn init_refines(s: TS2) {}
    proof fn step_refines(s: TS2, l: TL2, t: TS2) { lemma_step(s, l, t); }
}

impl SafeContract for TaggL2 {
    open spec fn inv(s: TS2) -> bool { inv05t(s) }
    proof fn init_safe(s: TS2) { lemma_cnt_empty(bw()); }
    proof fn step_safe(s: TS2, l: TL2, t: TS2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<TS2>, labels: Seq<TL2>, k: int)
    requires execution::<TaggRaw>(states, labels), 0 <= k < states.len(),
    ensures inv05t(states[k]),
    decreases k,
{
    if k == 0 {
        lemma_cnt_empty(bw());
    } else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution every state of which satisfies L1's business invariant.
pub proof fn theorem_raw_executions_refine(states: Seq<TS2>, labels: Seq<TL2>)
    requires execution::<TaggRaw>(states, labels),
    ensures
        execution::<TaggL2>(states, labels),
        abstract_execution::<TaggL1>(Seq::new(states.len(), |i: int| abst(states[i])),
                                     Seq::new(labels.len(), |i: int| labt(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv05t(#[trigger] states[i]) && inv1(abst(states[i])),
{
    assert forall|i: int| 0 <= i < states.len() implies inv05t(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<TaggL2>(states, labels));
    trace_refines::<TaggL2, TaggL1>(states, labels);
    refinement_preserves_safety::<TaggL2, TaggL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| abst(states[i])) =~= Seq::new(states.len(), |i: int| <TaggL2 as Refines<TaggL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labt(labels[i])) =~= Seq::new(labels.len(), |i: int| <TaggL2 as Refines<TaggL1>>::lab(labels[i])));
}

} // verus!
