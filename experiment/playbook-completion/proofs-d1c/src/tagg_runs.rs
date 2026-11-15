//! The bucket L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::tagg_l1::*;
use crate::tagg_l2::*;

verus! {

pub open spec fn t0() -> TS2 { TS2 { tout: Map::empty(), bucket: 0, count: 0, sum: 0 } }
pub open spec fn p_write(s: TS2, ts: int, w: int, mode: Mode) -> TS2 {
    if !(mode is Update) && s.tout.contains_key(ts) { s }
    else if !f0501() && s.tout.contains_key(ts) { TS2 { tout: s.tout.insert(ts, w), sum: s.sum - s.tout[ts] + w, ..s } }
    else { TS2 { tout: s.tout.insert(ts, w), bucket: s.bucket + 1, count: s.count + 1, sum: s.sum + w } }
}
pub open spec fn p_delete(s: TS2, ts: int) -> TS2 {
    TS2 { tout: s.tout.remove(ts), bucket: if s.bucket - 1 <= 0 { 0 } else { s.bucket - 1 },
          count: cnt(s.tout.remove(ts), bw()), sum: sm(s.tout.remove(ts), bw()) }
}

pub proof fn lemma_t_steps(s: TS2, ts: int, w: int, mode: Mode)
    ensures
        0 <= ts < bw() ==> step2(s, TL2::Write { ts, w, mode }, p_write(s, ts, w, mode)),
        s.tout.contains_key(ts) ==> step2(s, TL2::Delete { ts }, p_delete(s, ts)),
        step2(s, TL2::ReadAgg { count: s.count, sum: s.sum }, s),
        step2(s, TL2::ReadBucket { n: s.bucket }, s),
{
}

} // verus!
