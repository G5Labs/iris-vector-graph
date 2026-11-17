// product 3eaa79cf: temporal statistics readers (W57, iteration 51). Write history -> bucket statistics -> answer.
//   Writers (iris_src/src/Graph/KG/TemporalIndex.cls): WriteStores 80-133 (collision/skip guard 82-86, bucket
//     $Increment 102, tagg count/sum $Increment 117-118, min/max Set 119-124, UpdateHLL 125 / 185-193, NoteLatest 98),
//     InsertEdge 46-65 and BulkInsertCounts 151-183 (both call WriteStores), DeleteTemporalEdge 325-343 ->
//     RemoveTemporalRow 348-360 (bucket $Increment -1, Kill at <= 0) -> RebuildBucketAggregate 455-486 (recompute
//     from the surviving raw edges; Kill when none), PurgeRawBefore 866-920 (raw only; statistics stay),
//     PurgeBucketRange 1050-1065 (tagg and bucket of buckets that hold tagg), HLLEmpty 196-199, HLLAdd 210-224.
//   Readers: GetAggregate 1445-1493 (whole bucket from tagg, cut bucket from tout), GetBucketGroups 1495-1559 with
//     BucketGroupsEvents 1564-1596, GetBucketGroupTargets 1598-1633 (exact window over tout), GetVelocity 757-770,
//     FindBursts 772-806 (predicate argument unused), GetDistinctCount 632-682 (buckets touched, raw HLL estimator),
//     TemporalIndexMS.GetBucketCount and the inherited readers with BUCKETMS (TemporalIndexMS.cls).
//   Python: _engine/temporal.py get_temporal_aggregate 934-959 -> stores/iris_sql_store.py get_temporal_aggregate
//     2971-2987 (`float(val) if val else 0.0` after `str(...)`), get_edge_velocity 852-880, find_burst_nodes
//     882-909, get_bucket_groups 961-1022, get_bucket_group_targets 1024-1047, get_distinct_count 1088-1111,
//     purge_bucket_range 642-654 -> store 2788-2796, purge_raw_before 656-688 -> store 2798-2814.
//   Label sets: InternLabelSet 1341-1391 (sorted keys, values written without escaping), ResolveLabelSet 1394-1397.
// Transactions: Set and Kill are journaled and undone by a rollback; $Increment is not (premise P-INCR, observed in
// bug-tmp-003 and again in iteration 51). The SHA-1 register choice of HLLAdd is a provider input (`hf`).
use vstd::prelude::*;
use vstd::arithmetic::div_mod::*;

verus! {

// =============================================================== state
/// One temporal edge in ^KG("tout"): graph, timestamp, source, predicate, target, weight.
pub struct Ev { pub g: int, pub ts: int, pub s: int, pub p: int, pub o: int, pub w: int }

/// The stores the statistics readers consult. Keys: (g, bucket, s, p) for tagg, (g, bucket, s) for the bucket counter.
pub struct St {
    pub raw: Seq<Ev>,
    pub cnt: Map<(int, int, int, int), int>,
    pub sum: Map<(int, int, int, int), int>,
    pub mn: Map<(int, int, int, int), int>,
    pub mx: Map<(int, int, int, int), int>,
    pub hll: Map<(int, int, int, int), Seq<int>>,
    pub bkt: Map<(int, int, int), int>,
}

pub open spec fn empty_st() -> St {
    St { raw: Seq::empty(), cnt: Map::empty(), sum: Map::empty(), mn: Map::empty(), mx: Map::empty(),
         hll: Map::empty(), bkt: Map::empty() }
}

pub open spec fn get0<K>(m: Map<K, int>, k: K) -> int { if m.contains_key(k) { m[k] } else { 0 } }

/// Bucket width: 300 for Graph.KG.TemporalIndex (seconds), 300000 for TemporalIndexMS (milliseconds).
pub open spec fn bucket_of(ts: int, div: int) -> int { ts / div }

pub open spec fn same_coord(a: Ev, b: Ev) -> bool { a.g == b.g && a.ts == b.ts && a.s == b.s && a.p == b.p && a.o == b.o }

pub open spec fn occupied_at(raw: Seq<Ev>, e: Ev, i: int) -> bool { 0 <= i < raw.len() && same_coord(raw[i], e) }
pub open spec fn occupied(raw: Seq<Ev>, e: Ev) -> bool { exists|i: int| occupied_at(raw, e, i) }

// =============================================================== HLL sketch (16 registers)
pub open spec fn hll_empty() -> Seq<int> { Seq::new(16, |i: int| 0int) }
/// The provider's choice for one target: (register index, rank), from SHA-1 bytes 1 and 2 (HLLAdd 212-220).
pub open spec fn wf_hash(h: (int, int)) -> bool { 0 <= h.0 < 16 && 1 <= h.1 <= 9 }
pub open spec fn hll_add(r: Seq<int>, h: (int, int)) -> Seq<int> {
    if h.1 > r[h.0] { r.update(h.0, h.1) } else { r }
}
pub open spec fn wf_regs(r: Seq<int>) -> bool { r.len() == 16 && forall|i: int| 0 <= i < 16 ==> 0 <= #[trigger] r[i] <= 9 }
pub open spec fn reg_merge(a: Seq<int>, b: Seq<int>) -> Seq<int> {
    Seq::new(16, |i: int| if b[i] > a[i] { b[i] } else { a[i] })
}

/// 512 * Z, where Z = sum of 2^-reg (GetDistinctCount 675-678); each term is 2^(9 - reg) for reg in 0..=9.
pub open spec fn pow2(n: nat) -> int decreases n { if n == 0 { 1 } else { 2 * pow2((n - 1) as nat) } }
pub open spec fn zs(r: Seq<int>, n: int) -> int decreases n {
    if n <= 0 { 0 } else { zs(r, n - 1) + pow2((9 - r[n - 1]) as nat) }
}
pub open spec fn any_set(r: Seq<int>) -> bool { exists|i: int| 0 <= i < 16 && #[trigger] r[i] > 0 }
/// The answer: 0 for an all-zero sketch (line 679), else $Number(0.673 * 16 * 16 / Z, 0), i.e. round-half-up of
/// 88211.456 / zs (Z = zs / 512).
pub open spec fn estimate(r: Seq<int>) -> int {
    if !any_set(r) { 0 } else { (88211456 + 500 * zs(r, 16)) / (1000 * zs(r, 16)) }
}

// =============================================================== writers
pub enum Mode { Insert, Update, Skip }

pub open spec fn k4(e: Ev, div: int) -> (int, int, int, int) { (e.g, bucket_of(e.ts, div), e.s, e.p) }
pub open spec fn k3(e: Ev, div: int) -> (int, int, int) { (e.g, bucket_of(e.ts, div), e.s) }

pub open spec fn hll_of(st: St, k: (int, int, int, int)) -> Seq<int> { if st.hll.contains_key(k) { st.hll[k] } else { hll_empty() } }

/// The store effects of WriteStores once its guard lets the write through (lines 96-131).
pub open spec fn stores_written(st: St, div: int, hf: spec_fn(int) -> (int, int), e: Ev, raw2: Seq<Ev>) -> St {
    let k = k4(e, div);
    let b = k3(e, div);
    let h0 = hll_of(st, k);
    let h1 = hll_add(h0, hf(e.o));
    St {
        raw: raw2,
        bkt: st.bkt.insert(b, get0(st.bkt, b) + 1),
        cnt: st.cnt.insert(k, get0(st.cnt, k) + 1),
        sum: st.sum.insert(k, get0(st.sum, k) + e.w),
        mn: if !st.mn.contains_key(k) || e.w < st.mn[k] { st.mn.insert(k, e.w) } else { st.mn },
        mx: if !st.mx.contains_key(k) || e.w > st.mx[k] { st.mx.insert(k, e.w) } else { st.mx },
        hll: if h1 != h0 { st.hll.insert(k, h1) } else { st.hll },
    }
}

/// WriteStores: "update" has no early return (82-83); otherwise an occupied coordinate returns before any store.
pub open spec fn write(st: St, div: int, hf: spec_fn(int) -> (int, int), m: Mode, e: Ev) -> St {
    if occupied(st.raw, e) {
        match m {
            Mode::Update => stores_written(st, div, hf, e, st.raw.update(choose|i: int| occupied_at(st.raw, e, i), e)),
            _ => st,
        }
    } else {
        stores_written(st, div, hf, e, st.raw.push(e))
    }
}

/// A write inside a caller's transaction that is rolled back: journaled Sets and Kills (raw, min, max, sketch) return
/// to their before-image; $Increment'ed counters (count, sum, bucket) keep the write (P-INCR).
pub open spec fn rolled_back(before: St, after: St) -> St {
    St { raw: before.raw, mn: before.mn, mx: before.mx, hll: before.hll, cnt: after.cnt, sum: after.sum, bkt: after.bkt }
}

/// Events of (g, s, p) with lo <= ts <= hi, summarized.
pub struct Agg { pub count: int, pub sum: int, pub min: Option<int>, pub max: Option<int> }
pub open spec fn zero() -> Agg { Agg { count: 0, sum: 0, min: None, max: None } }
pub open spec fn omin(a: Option<int>, b: Option<int>) -> Option<int> {
    match (a, b) { (None, x) => x, (x, None) => x, (Some(x), Some(y)) => Some(if y < x { y } else { x }) }
}
pub open spec fn omax(a: Option<int>, b: Option<int>) -> Option<int> {
    match (a, b) { (None, x) => x, (x, None) => x, (Some(x), Some(y)) => Some(if y > x { y } else { x }) }
}
pub open spec fn add(a: Agg, b: Agg) -> Agg {
    Agg { count: a.count + b.count, sum: a.sum + b.sum, min: omin(a.min, b.min), max: omax(a.max, b.max) }
}
pub open spec fn one(w: int) -> Agg { Agg { count: 1, sum: w, min: Some(w), max: Some(w) } }
pub open spec fn hit(e: Ev, g: int, s: int, p: int, lo: int, hi: int) -> bool { e.g == g && e.s == s && e.p == p && lo <= e.ts <= hi }

pub open spec fn raw_agg(raw: Seq<Ev>, g: int, s: int, p: int, lo: int, hi: int) -> Agg decreases raw.len() {
    if raw.len() == 0 { zero() } else {
        let r = raw_agg(raw.drop_last(), g, s, p, lo, hi);
        if hit(raw.last(), g, s, p, lo, hi) { add(r, one(raw.last().w)) } else { r }
    }
}
/// The sketch the surviving targets build (RebuildBucketAggregate 474).
pub open spec fn raw_hll(raw: Seq<Ev>, hf: spec_fn(int) -> (int, int), g: int, s: int, p: int, lo: int, hi: int) -> Seq<int> decreases raw.len() {
    if raw.len() == 0 { hll_empty() } else {
        let r = raw_hll(raw.drop_last(), hf, g, s, p, lo, hi);
        if hit(raw.last(), g, s, p, lo, hi) { hll_add(r, hf(raw.last().o)) } else { r }
    }
}

pub open spec fn b_lo(b: int, div: int) -> int { b * div }
pub open spec fn b_hi(b: int, div: int) -> int { (b + 1) * div - 1 }

/// RebuildBucketAggregate: recompute count/sum/min/max/sketch of (g, b, s, p) from the raw edges; Kill when none.
pub open spec fn rebuild(st: St, div: int, hf: spec_fn(int) -> (int, int), k: (int, int, int, int)) -> St {
    let a = raw_agg(st.raw, k.0, k.2, k.3, b_lo(k.1, div), b_hi(k.1, div));
    if a.count == 0 {
        St { cnt: st.cnt.remove(k), sum: st.sum.remove(k), mn: st.mn.remove(k), mx: st.mx.remove(k), hll: st.hll.remove(k), ..st }
    } else {
        St { cnt: st.cnt.insert(k, a.count), sum: st.sum.insert(k, a.sum), mn: st.mn.insert(k, a.min.unwrap()),
             mx: st.mx.insert(k, a.max.unwrap()), hll: st.hll.insert(k, raw_hll(st.raw, hf, k.0, k.2, k.3, b_lo(k.1, div), b_hi(k.1, div))), ..st }
    }
}

/// DeleteTemporalEdge at an occupied coordinate (index i): remove the raw edge, decrement the bucket counter (Kill at
/// <= 0), rebuild the bucket's tagg from the survivors.
pub open spec fn delete_at(st: St, div: int, hf: spec_fn(int) -> (int, int), i: int) -> St {
    let e = st.raw[i];
    let b = k3(e, div);
    let c = get0(st.bkt, b) - 1;
    let st1 = St { raw: st.raw.remove(i), bkt: if c <= 0 { st.bkt.remove(b) } else { st.bkt.insert(b, c) }, ..st };
    rebuild(st1, div, hf, k4(e, div))
}

/// PurgeRawBefore's kill loop for graph g and [lo, hi): raw edges only; statistics stay.
pub open spec fn purge_raw(raw: Seq<Ev>, g: int, lo: int, hi: int) -> Seq<Ev> decreases raw.len() {
    if raw.len() == 0 { raw } else {
        let r = purge_raw(raw.drop_last(), g, lo, hi);
        let e = raw.last();
        if e.g == g && lo <= e.ts < hi { r } else { r.push(e) }
    }
}
pub open spec fn purge_raw_before(st: St, g: int, lo: int, hi: int) -> St { St { raw: purge_raw(st.raw, g, lo, hi), ..st } }

/// PurgeBucketRange: for each bucket in [bs, be] that holds a tagg entry, Kill its tagg and its bucket counters.
pub open spec fn has_tagg(st: St, g: int, b: int) -> bool {
    exists|s: int, p: int| #[trigger] st.cnt.contains_key((g, b, s, p)) || st.sum.contains_key((g, b, s, p))
        || st.mn.contains_key((g, b, s, p)) || st.mx.contains_key((g, b, s, p)) || st.hll.contains_key((g, b, s, p))
}
pub open spec fn in_range(st: St, g: int, bs: int, be: int, kg: int, kb: int) -> bool { kg == g && bs <= kb <= be }
pub open spec fn purge_buckets(st: St, g: int, bs: int, be: int) -> St {
    if bs > be { st } else {
        St {
            raw: st.raw,
            cnt: st.cnt.restrict(st.cnt.dom().filter(|k: (int, int, int, int)| !in_range(st, g, bs, be, k.0, k.1))),
            sum: st.sum.restrict(st.sum.dom().filter(|k: (int, int, int, int)| !in_range(st, g, bs, be, k.0, k.1))),
            mn: st.mn.restrict(st.mn.dom().filter(|k: (int, int, int, int)| !in_range(st, g, bs, be, k.0, k.1))),
            mx: st.mx.restrict(st.mx.dom().filter(|k: (int, int, int, int)| !in_range(st, g, bs, be, k.0, k.1))),
            hll: st.hll.restrict(st.hll.dom().filter(|k: (int, int, int, int)| !in_range(st, g, bs, be, k.0, k.1))),
            bkt: st.bkt.restrict(st.bkt.dom().filter(|k: (int, int, int)| !(in_range(st, g, bs, be, k.0, k.1) && has_tagg(st, g, k.1)))),
        }
    }
}
/// Its return value: the buckets in [b, be] that held tagg.
pub open spec fn purged_count(st: St, g: int, b: int, be: int) -> int decreases be + 1 - b {
    if b > be { 0 } else { (if has_tagg(st, g, b) { 1int } else { 0int }) + purged_count(st, g, b + 1, be) }
}

// =============================================================== readers
pub open spec fn whole(b: int, lo: int, hi: int, div: int) -> bool { b_lo(b, div) >= lo && b_hi(b, div) <= hi }
pub open spec fn imax(a: int, b: int) -> int { if a > b { a } else { b } }
pub open spec fn imin(a: int, b: int) -> int { if a < b { a } else { b } }
pub open spec fn stat_agg(st: St, k: (int, int, int, int)) -> Agg {
    Agg { count: get0(st.cnt, k), sum: get0(st.sum, k),
          min: if st.mn.contains_key(k) { Some(st.mn[k]) } else { None },
          max: if st.mx.contains_key(k) { Some(st.mx[k]) } else { None } }
}
/// One bucket's part of GetAggregate (1458-1485): whole -> tagg; cut -> the raw edges of the cut range.
pub open spec fn bucket_part(st: St, div: int, g: int, s: int, p: int, lo: int, hi: int, b: int) -> Agg {
    if whole(b, lo, hi, div) { stat_agg(st, (g, b, s, p)) }
    else { raw_agg(st.raw, g, s, p, imax(lo, b_lo(b, div)), imin(hi, b_hi(b, div))) }
}
pub open spec fn agg_from(st: St, div: int, g: int, s: int, p: int, lo: int, hi: int, b: int, eb: int) -> Agg
    decreases eb + 1 - b
{
    if b > eb { zero() } else { add(bucket_part(st, div, g, s, p, lo, hi, b), agg_from(st, div, g, s, p, lo, hi, b + 1, eb)) }
}
pub open spec fn get_aggregate(st: St, div: int, g: int, s: int, p: int, lo: int, hi: int) -> Agg {
    agg_from(st, div, g, s, p, lo, hi, bucket_of(lo, div), bucket_of(hi, div))
}

/// GetBucketGroups (1495-1559): the row of (s, p) exists when a whole bucket holds a tagg entry of (s, p) or a cut
/// bucket holds one of its raw edges in the cut range; its values compose like GetAggregate's (the same +$Get
/// defaults). JSON null stands for a missing min or max.
pub open spec fn tagg_present(st: St, k: (int, int, int, int)) -> bool {
    st.cnt.contains_key(k) || st.sum.contains_key(k) || st.mn.contains_key(k) || st.mx.contains_key(k) || st.hll.contains_key(k)
}
pub open spec fn row_part(st: St, div: int, g: int, s: int, p: int, lo: int, hi: int, b: int) -> bool {
    if whole(b, lo, hi, div) { tagg_present(st, (g, b, s, p)) }
    else { raw_agg(st.raw, g, s, p, imax(lo, b_lo(b, div)), imin(hi, b_hi(b, div))).count > 0 }
}
pub open spec fn group_row(st: St, div: int, g: int, s: int, p: int, lo: int, hi: int) -> Option<Agg> {
    if exists|b: int| bucket_of(lo, div) <= b <= bucket_of(hi, div) && #[trigger] row_part(st, div, g, s, p, lo, hi, b) {
        Some(get_aggregate(st, div, g, s, p, lo, hi))
    } else { None }
}

pub enum Metric { Count, Sum, Min, Max, Avg, Other }
/// GetAggregate's answer text: a number, the avg pair (sum, count) rounded by $FN(…,"",6), or "".
pub enum SAns { Num(int), Avg(int, int), Empty }
pub open spec fn server_answer(a: Agg, m: Metric) -> SAns {
    match m {
        Metric::Count => SAns::Num(a.count),
        Metric::Sum => SAns::Num(a.sum),
        Metric::Min => match a.min { Some(x) => SAns::Num(x), None => SAns::Empty },
        Metric::Max => match a.max { Some(x) => SAns::Num(x), None => SAns::Empty },
        Metric::Avg => if a.count == 0 { SAns::Empty } else { SAns::Avg(a.sum, a.count) },
        Metric::Other => SAns::Empty,
    }
}
/// The Python value. The driver answers None for "" (provider, observed); the store converts with
/// `float(str(v)) if str(v) else 0.0`, and str(None) is the truthy text 'None' (iris_sql_store.py 2976-2987).
pub enum Py { Int(int), Float(int), FloatAvg(int, int), Raises }
pub open spec fn py_value(ans: SAns, m: Metric) -> Py {
    match ans {
        SAns::Empty => Py::Raises,
        SAns::Num(x) => match m { Metric::Count => Py::Int(x), _ => Py::Float(x) },
        SAns::Avg(s, c) => Py::FloatAvg(s, c),
    }
}
pub open spec fn get_temporal_aggregate(st: St, div: int, g: int, s: int, p: int, m: Metric, lo: int, hi: int) -> Py {
    py_value(server_answer(get_aggregate(st, div, g, s, p, lo, hi), m), m)
}

// --------------------------------------------------------------- an empty source or predicate (iteration 56)
/// Review 53-55 (challenge to round-2 m2): GetAggregate with source "" or predicate "". Whole bucket:
/// `$Get(^KG("tagg", g, b, "", ...))` raises <SUBSCRIPT>. Cut bucket: the walk visits each timestamp ^KG("tout", g)
/// holds in the cut range (any source's) and `$Order(^KG("tout", g, ts, "", ...))` raises there. A window that holds
/// no whole bucket and meets no timestamp of its graph reads nothing and answers 0, the answer of a valid read.
pub enum KAns { Raises, Agg(Agg) }
pub open spec fn some_whole(lo: int, hi: int, div: int) -> bool {
    exists|b: int| bucket_of(lo, div) <= b <= bucket_of(hi, div) && #[trigger] whole(b, lo, hi, div)
}
pub open spec fn ts_present(st: St, g: int, lo: int, hi: int) -> bool {
    exists|i: int| 0 <= i < st.raw.len() && (#[trigger] st.raw[i]).g == g && lo <= st.raw[i].ts <= hi
}
/// The key arguments: Some(id) for a given key, None for "".
pub open spec fn get_aggregate_keys(st: St, div: int, g: int, s: Option<int>, p: Option<int>, lo: int, hi: int) -> KAns {
    match (s, p) {
        (Some(s1), Some(p1)) => KAns::Agg(get_aggregate(st, div, g, s1, p1, lo, hi)),
        _ => if some_whole(lo, hi, div) || ts_present(st, g, lo, hi) { KAns::Raises } else { KAns::Agg(zero()) },
    }
}
/// get_temporal_aggregate with key arguments (the Python layer passes "" through unchanged).
pub open spec fn get_temporal_aggregate_keys(st: St, div: int, g: int, s: Option<int>, p: Option<int>, m: Metric, lo: int, hi: int) -> Py {
    match get_aggregate_keys(st, div, g, s, p, lo, hi) {
        KAns::Raises => Py::Raises,
        KAns::Agg(a) => py_value(server_answer(a, m), m),
    }
}

/// GetBucketGroupTargets (1598-1633): targets of the raw edges in exactly [lo, hi].
pub open spec fn is_target(st: St, g: int, s: int, p: int, lo: int, hi: int, o: int) -> bool {
    exists|i: int| 0 <= i < st.raw.len() && #[trigger] hit(st.raw[i], g, s, p, lo, hi) && st.raw[i].o == o
}

/// GetVelocity (757-770): the bucket counters of s from (now - window) \ div to now \ div. now: nowTs when > 0,
/// else the wall clock in seconds (also in TemporalIndexMS).
pub open spec fn now_of(now_ts: int, clock_s: int) -> int { if now_ts > 0 { now_ts } else { clock_s } }
/// TemporalIndexMS.GetBucketCount: one bucket counter (0 when absent).
pub open spec fn bucket_count(st: St, g: int, b: int, s: int) -> int { get0(st.bkt, (g, b, s)) }
pub open spec fn bkt_sum(st: St, g: int, s: int, b: int, eb: int) -> int decreases eb + 1 - b {
    if b > eb { 0 } else { get0(st.bkt, (g, b, s)) + bkt_sum(st, g, s, b + 1, eb) }
}
pub open spec fn velocity(st: St, div: int, g: int, s: int, window: int, now_ts: int, clock_s: int) -> int {
    let now = now_of(now_ts, clock_s);
    bkt_sum(st, g, s, (now - window) / div, now / div)
}
/// FindBursts (772-806): every source holding a counter in one of those buckets, with its total, when the total
/// reaches the threshold. The predicate argument is accepted and not read.
pub open spec fn present(st: St, g: int, s: int, b: int, eb: int) -> bool {
    exists|x: int| b <= x <= eb && #[trigger] st.bkt.contains_key((g, x, s))
}
pub open spec fn burst_listed(st: St, div: int, g: int, pred: int, s: int, window: int, threshold: int, now_ts: int, clock_s: int) -> bool {
    let now = now_of(now_ts, clock_s);
    present(st, g, s, (now - window) / div, now / div) && velocity(st, div, g, s, window, now_ts, clock_s) >= threshold
}

/// GetDistinctCount (632-682) for a named source: the sketches of (g, b, s, p) merged over every bucket the window
/// touches, then estimated.
pub open spec fn merged(st: St, g: int, s: int, p: int, b: int, eb: int) -> Seq<int> decreases eb + 1 - b {
    if b > eb { hll_empty() } else {
        let rest = merged(st, g, s, p, b + 1, eb);
        if st.hll.contains_key((g, b, s, p)) { reg_merge(rest, st.hll[(g, b, s, p)]) } else { rest }
    }
}
pub open spec fn distinct(st: St, div: int, g: int, s: int, p: int, lo: int, hi: int) -> int {
    estimate(merged(st, g, s, p, bucket_of(lo, div), bucket_of(hi, div)))
}

// =============================================================== L1 rules the docs state
/// "over exactly [ts_start, ts_end]": the answer is the raw window.
pub open spec fn exact_rule(st: St, div: int, g: int, s: int, p: int, lo: int, hi: int) -> bool {
    get_aggregate(st, div, g, s, p, lo, hi) == raw_agg(st.raw, g, s, p, lo, hi)
}
/// "An empty window or an unknown metric gives 0 or 0.0, never None; a failed server call raises."
pub open spec fn documented_py(a: Agg, m: Metric) -> Py {
    match server_answer(a, m) { SAns::Empty => Py::Float(0), x => py_value(x, m) }
}

// =============================================================== arithmetic lemmas
pub proof fn lemma_bucket_bounds(b: int, div: int)
    requires div > 0,
    ensures b_lo(b, div) / div == b, b_hi(b, div) / div == b,
{
    lemma_fundamental_div_mod_converse(b * div, div, b, 0);
    assert((b + 1) * div - 1 == b * div + (div - 1)) by (nonlinear_arith);
    lemma_fundamental_div_mod_converse((b + 1) * div - 1, div, b, div - 1);
}

pub proof fn lemma_pow2_bounds(n: nat)
    requires n <= 9,
    ensures 1 <= pow2(n) <= 512, n <= 8 ==> pow2(n) <= 256,
{
    reveal_with_fuel(pow2, 10);
    if n == 0 {} else if n == 1 {} else if n == 2 {} else if n == 3 {} else if n == 4 {} else if n == 5 {}
    else if n == 6 {} else if n == 7 {} else if n == 8 {} else { assert(n == 9); }
}

pub proof fn lemma_zs_bounds(r: Seq<int>, n: int)
    requires wf_regs(r), 0 <= n <= 16,
    ensures n <= zs(r, n) <= 512 * n,
            (exists|i: int| 0 <= i < n && #[trigger] r[i] > 0) ==> zs(r, n) <= 512 * n - 256,
    decreases n,
{
    if n > 0 {
        lemma_zs_bounds(r, n - 1);
        let t = (9 - r[n - 1]) as nat;
        lemma_pow2_bounds(t);
        if exists|i: int| 0 <= i < n && #[trigger] r[i] > 0 {
            let i = choose|i: int| 0 <= i < n && #[trigger] r[i] > 0;
            if i < n - 1 { assert(exists|j: int| 0 <= j < n - 1 && #[trigger] r[j] > 0); }
        }
    }
}

// =============================================================== theorems: aggregate reads
/// Valid neighbor (A1, R217 held): a window inside one bucket that it cuts is read edge by edge, so the answer is the
/// raw window, for every state.
pub proof fn theorem_cut_bucket_is_exact(st: St, g: int, s: int, p: int, lo: int, hi: int)
    requires lo <= hi, lo / 300 == hi / 300, !whole(lo / 300, lo, hi, 300),
    ensures exact_rule(st, 300, g, s, p, lo, hi),
{
    let b = lo / 300;
    lemma_bucket_bounds(b, 300);
    assert(b_lo(b, 300) <= lo) by { lemma_fundamental_div_mod(lo, 300); }
    assert(hi <= b_hi(b, 300)) by { lemma_fundamental_div_mod(hi, 300); }
    assert(agg_from(st, 300, g, s, p, lo, hi, b + 1, b) == zero());
    let a = raw_agg(st.raw, g, s, p, lo, hi);
    assert(add(a, zero()) == a);
}

/// A window of exactly one whole bucket answers the bucket's statistics.
/// (The decision GetAggregate makes for a bucket the window holds whole.)
pub proof fn theorem_one_whole_bucket_reads_statistics(st: St, g: int, s: int, p: int, b: int)
    ensures get_aggregate(st, 300, g, s, p, b_lo(b, 300), b_hi(b, 300)) == stat_agg(st, (g, b, s, p)),
{
    lemma_bucket_bounds(b, 300);
    assert(agg_from(st, 300, g, s, p, b_lo(b, 300), b_hi(b, 300), b + 1, b) == zero());
    let a = stat_agg(st, (g, b, s, p));
    assert(add(a, zero()) == a);
}

proof fn lemma_update_keeps_raw_agg(raw: Seq<Ev>, i: int, e: Ev, g: int, s: int, p: int, lo: int, hi: int)
    requires occupied_at(raw, e, i),
    ensures raw_agg(raw.update(i, e), g, s, p, lo, hi).count == raw_agg(raw, g, s, p, lo, hi).count,
    decreases raw.len(),
{
    let r2 = raw.update(i, e);
    if i == raw.len() - 1 {
        assert(r2.drop_last() =~= raw.drop_last());
    } else {
        assert(r2.drop_last() =~= raw.drop_last().update(i, e));
        lemma_update_keeps_raw_agg(raw.drop_last(), i, e, g, s, p, lo, hi);
    }
}

/// bug-tmp-002 (general): an update at any occupied coordinate adds one to the bucket's tagg count and to its bucket
/// counter while the raw edges of the bucket keep their number. A whole-bucket read and the raw window then differ.
pub proof fn theorem_update_counts_twice(st: St, hf: spec_fn(int) -> (int, int), e: Ev)
    requires occupied(st.raw, e),
    ensures ({
        let st2 = write(st, 300, hf, Mode::Update, e);
        let k = k4(e, 300);
        &&& get0(st2.cnt, k) == get0(st.cnt, k) + 1
        &&& get0(st2.bkt, k3(e, 300)) == get0(st.bkt, k3(e, 300)) + 1
        &&& raw_agg(st2.raw, e.g, e.s, e.p, b_lo(k.1, 300), b_hi(k.1, 300)).count
            == raw_agg(st.raw, e.g, e.s, e.p, b_lo(k.1, 300), b_hi(k.1, 300)).count
    }),
{
    let i = choose|i: int| occupied_at(st.raw, e, i);
    lemma_update_keeps_raw_agg(st.raw, i, e, e.g, e.s, e.p, b_lo(bucket_of(e.ts, 300), 300), b_hi(bucket_of(e.ts, 300), 300));
}

/// Valid neighbor (A3 col, V3): an insert at an occupied coordinate changes no store at all.
pub proof fn theorem_collision_changes_nothing(st: St, hf: spec_fn(int) -> (int, int), e: Ev)
    requires occupied(st.raw, e),
    ensures write(st, 300, hf, Mode::Insert, e) == st, write(st, 300, hf, Mode::Skip, e) == st,
{}

/// A3 at the reader: insert w0 then update w1 of one coordinate in an empty store. The whole-bucket read answers
/// count 2, sum w0 + w1 and max(w0, w1); the cut read of the same edge answers count 1, sum w1.
pub proof fn theorem_update_whole_vs_cut(hf: spec_fn(int) -> (int, int), e0: Ev, w1: int, lo: int)
    requires 0 <= e0.ts, b_lo(bucket_of(e0.ts, 300), 300) < lo <= e0.ts,
    ensures ({
        let e1 = Ev { w: w1, ..e0 };
        let b = bucket_of(e0.ts, 300);
        let st2 = write(write(empty_st(), 300, hf, Mode::Insert, e0), 300, hf, Mode::Update, e1);
        &&& get_aggregate(st2, 300, e0.g, e0.s, e0.p, b_lo(b, 300), b_hi(b, 300)).count == 2
        &&& get_aggregate(st2, 300, e0.g, e0.s, e0.p, b_lo(b, 300), b_hi(b, 300)).sum == e0.w + w1
        &&& get_aggregate(st2, 300, e0.g, e0.s, e0.p, lo, b_hi(b, 300)) == one(w1)
    }),
{
    let e1 = Ev { w: w1, ..e0 };
    let b = bucket_of(e0.ts, 300);
    let st1 = write(empty_st(), 300, hf, Mode::Insert, e0);
    assert(!occupied(empty_st().raw, e0));
    assert(st1.raw =~= seq![e0]);
    assert(occupied_at(st1.raw, e1, 0));
    let st2 = write(st1, 300, hf, Mode::Update, e1);
    assert(st2.raw =~= seq![e1]);
    theorem_one_whole_bucket_reads_statistics(st2, e0.g, e0.s, e0.p, b);
    lemma_bucket_bounds(b, 300);
    assert(e0.ts <= b_hi(b, 300)) by { lemma_fundamental_div_mod(e0.ts, 300); }
    assert(lo / 300 == b) by {
        lemma_fundamental_div_mod(e0.ts, 300);
        lemma_fundamental_div_mod_converse(lo, 300, b, lo - b * 300);
    }
    theorem_cut_bucket_is_exact(st2, e0.g, e0.s, e0.p, lo, b_hi(b, 300));
    assert(seq![e1].drop_last() =~= Seq::<Ev>::empty());
    reveal_with_fuel(raw_agg, 2);
    assert(add(zero(), one(w1)) == one(w1));
}

/// bug-tmp-003 sharpened (A4): a rolled-back first write of (g, b, s, p) leaves count 1 and sum w but no min, max or
/// sketch, and no raw edge. Whole-bucket min and max raise in Python while count answers 1; the cut read answers 0.
pub proof fn theorem_rolled_back_first_write(st: St, hf: spec_fn(int) -> (int, int), e: Ev)
    requires
        !occupied(st.raw, e),
        !st.cnt.contains_key(k4(e, 300)), !st.sum.contains_key(k4(e, 300)),
        !st.mn.contains_key(k4(e, 300)), !st.mx.contains_key(k4(e, 300)), !st.hll.contains_key(k4(e, 300)),
    ensures ({
        let st2 = rolled_back(st, write(st, 300, hf, Mode::Insert, e));
        let b = bucket_of(e.ts, 300);
        &&& st2.raw == st.raw
        &&& get_temporal_aggregate(st2, 300, e.g, e.s, e.p, Metric::Count, b_lo(b, 300), b_hi(b, 300)) == Py::Int(1)
        &&& get_temporal_aggregate(st2, 300, e.g, e.s, e.p, Metric::Min, b_lo(b, 300), b_hi(b, 300)) == Py::Raises
        &&& get_temporal_aggregate(st2, 300, e.g, e.s, e.p, Metric::Max, b_lo(b, 300), b_hi(b, 300)) == Py::Raises
        &&& documented_py(stat_agg(st2, k4(e, 300)), Metric::Min) == Py::Float(0)
        &&& get0(st2.bkt, k3(e, 300)) == get0(st.bkt, k3(e, 300)) + 1
        &&& !st2.hll.contains_key(k4(e, 300))
    }),
{
    let st2 = rolled_back(st, write(st, 300, hf, Mode::Insert, e));
    theorem_one_whole_bucket_reads_statistics(st2, e.g, e.s, e.p, bucket_of(e.ts, 300));
}

/// A4 groups (general): the same rolled-back first write gives (s, p) a group row with count 1, sum w and null
/// min and max, while the raw window holds nothing.
pub proof fn theorem_rolled_back_group_row(st: St, hf: spec_fn(int) -> (int, int), e: Ev)
    requires
        !occupied(st.raw, e),
        !st.cnt.contains_key(k4(e, 300)), !st.sum.contains_key(k4(e, 300)),
        !st.mn.contains_key(k4(e, 300)), !st.mx.contains_key(k4(e, 300)), !st.hll.contains_key(k4(e, 300)),
    ensures ({
        let st2 = rolled_back(st, write(st, 300, hf, Mode::Insert, e));
        let b = bucket_of(e.ts, 300);
        group_row(st2, 300, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)) == Some(Agg { count: 1, sum: e.w, min: None, max: None })
    }),
{
    let st2 = rolled_back(st, write(st, 300, hf, Mode::Insert, e));
    let b = bucket_of(e.ts, 300);
    lemma_bucket_bounds(b, 300);
    theorem_one_whole_bucket_reads_statistics(st2, e.g, e.s, e.p, b);
    assert(row_part(st2, 300, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300), b));
}

/// G1 no-event window (held): a window with no tagg entry in its whole buckets and no raw edge in its cut part has
/// no row for (s, p), not a zero row.
pub proof fn theorem_group_row_absent(st: St, g: int, s: int, p: int, lo: int, hi: int)
    requires forall|b: int| bucket_of(lo, 300) <= b <= bucket_of(hi, 300) ==> !#[trigger] row_part(st, 300, g, s, p, lo, hi, b),
    ensures group_row(st, 300, g, s, p, lo, hi).is_none(),
{}

/// Valid neighbor (A4 rbc): the same write committed answers count 1 with its weight as min and max.
pub proof fn theorem_committed_first_write(st: St, hf: spec_fn(int) -> (int, int), e: Ev)
    requires !occupied(st.raw, e), !st.cnt.contains_key(k4(e, 300)), !st.mn.contains_key(k4(e, 300)), !st.mx.contains_key(k4(e, 300)),
    ensures ({
        let st2 = write(st, 300, hf, Mode::Insert, e);
        let b = bucket_of(e.ts, 300);
        &&& get_temporal_aggregate(st2, 300, e.g, e.s, e.p, Metric::Min, b_lo(b, 300), b_hi(b, 300)) == Py::Float(e.w)
        &&& get_temporal_aggregate(st2, 300, e.g, e.s, e.p, Metric::Count, b_lo(b, 300), b_hi(b, 300)) == Py::Int(1)
    }),
{
    theorem_one_whole_bucket_reads_statistics(write(st, 300, hf, Mode::Insert, e), e.g, e.s, e.p, bucket_of(e.ts, 300));
}

/// bug-tmp-009 (general): whenever the server answers "" (a min, max or avg with nothing to report, or an unknown
/// metric), the Python reader raises, where the docstring promises 0.0. Count and sum never raise.
pub proof fn theorem_empty_answer_raises(a: Agg, m: Metric)
    ensures
        server_answer(a, m) == SAns::Empty ==> py_value(server_answer(a, m), m) == Py::Raises && documented_py(a, m) == Py::Float(0),
        a.count == 0 && a.min.is_none() ==> py_value(server_answer(a, Metric::Min), Metric::Min) == Py::Raises,
        py_value(server_answer(a, Metric::Other), Metric::Other) == Py::Raises,
        py_value(server_answer(a, Metric::Count), Metric::Count) == Py::Int(a.count),
{}

proof fn lemma_purge_raw_drops_window(raw: Seq<Ev>, g: int, lo: int, hi: int, s: int, p: int, x: int, y: int)
    requires lo <= x, y < hi,
    ensures raw_agg(purge_raw(raw, g, lo, hi), g, s, p, x, y) == zero(),
    decreases raw.len(),
{
    if raw.len() > 0 {
        lemma_purge_raw_drops_window(raw.drop_last(), g, lo, hi, s, p, x, y);
        let r = purge_raw(raw.drop_last(), g, lo, hi);
        let e = raw.last();
        if !(e.g == g && lo <= e.ts < hi) {
            assert(r.push(e).drop_last() =~= r);
        }
    }
}

/// temporal.stats.after-purge (A5, general): a raw purge of [lo, hi) leaves every statistic and bucket counter as it
/// was, and any window inside [lo, hi) finds no raw edge: a whole-bucket read answers what it answered before, a cut
/// read answers nothing.
pub proof fn theorem_raw_purge_keeps_statistics(st: St, g: int, lo: int, hi: int, s: int, p: int, x: int, y: int)
    requires lo <= x, y < hi,
    ensures ({
        let st2 = purge_raw_before(st, g, lo, hi);
        &&& st2.cnt == st.cnt && st2.sum == st.sum && st2.mn == st.mn && st2.mx == st.mx && st2.hll == st.hll && st2.bkt == st.bkt
        &&& raw_agg(st2.raw, g, s, p, x, y) == zero()
    }),
{
    lemma_purge_raw_drops_window(st.raw, g, lo, hi, s, p, x, y);
}

/// A5 at the reader: a cut read inside a raw-purged range answers 0 for every state; a one-bucket whole read keeps
/// the bucket's statistics.
pub proof fn theorem_raw_purge_whole_vs_cut(st: St, g: int, s: int, p: int, b: int, x: int)
    requires b_lo(b, 300) < x <= b_hi(b, 300),
    ensures ({
        let st2 = purge_raw_before(st, g, b_lo(b, 300), b_hi(b, 300) + 1);
        &&& get_aggregate(st2, 300, g, s, p, b_lo(b, 300), b_hi(b, 300)) == stat_agg(st, (g, b, s, p))
        &&& get_aggregate(st2, 300, g, s, p, x, b_hi(b, 300)) == zero()
    }),
{
    let st2 = purge_raw_before(st, g, b_lo(b, 300), b_hi(b, 300) + 1);
    theorem_one_whole_bucket_reads_statistics(st2, g, s, p, b);
    lemma_bucket_bounds(b, 300);
    assert(x / 300 == b) by { lemma_fundamental_div_mod_converse(x, 300, b, x - b * 300); }
    theorem_cut_bucket_is_exact(st2, g, s, p, x, b_hi(b, 300));
    lemma_purge_raw_drops_window(st.raw, g, b_lo(b, 300), b_hi(b, 300) + 1, s, p, x, b_hi(b, 300));
}

/// A6 (general): a bucket-range purge of b removes every statistic of b in g and, because b held tagg, its bucket
/// counters; raw edges stay. A whole-bucket read of b then answers count 0 with no min (Python raises on min), while
/// a cut read of b keeps answering its raw edges.
pub proof fn theorem_bucket_purge_whole_vs_cut(st: St, g: int, s: int, p: int, b: int, x: int)
    requires b_lo(b, 300) < x <= b_hi(b, 300), st.cnt.contains_key((g, b, s, p)),
    ensures ({
        let st2 = purge_buckets(st, g, b, b);
        &&& st2.raw == st.raw
        &&& get_aggregate(st2, 300, g, s, p, b_lo(b, 300), b_hi(b, 300)) == zero()
        &&& get_temporal_aggregate(st2, 300, g, s, p, Metric::Min, b_lo(b, 300), b_hi(b, 300)) == Py::Raises
        &&& get_aggregate(st2, 300, g, s, p, x, b_hi(b, 300)) == raw_agg(st.raw, g, s, p, x, b_hi(b, 300))
        &&& !st2.bkt.contains_key((g, b, s))
        &&& purged_count(st, g, b, b) == 1
    }),
{
    let st2 = purge_buckets(st, g, b, b);
    assert(has_tagg(st, g, b));
    theorem_one_whole_bucket_reads_statistics(st2, g, s, p, b);
    lemma_bucket_bounds(b, 300);
    assert(x / 300 == b) by { lemma_fundamental_div_mod_converse(x, 300, b, x - b * 300); }
    theorem_cut_bucket_is_exact(st2, g, s, p, x, b_hi(b, 300));
    assert(!st2.cnt.contains_key((g, b, s, p)));
    assert(!st2.mn.contains_key((g, b, s, p)));
    assert(!st2.mx.contains_key((g, b, s, p)));
    assert(!st2.sum.contains_key((g, b, s, p)));
    assert(purged_count(st, g, b + 1, b) == 0);
}

/// Neighbor of A6 (the return value): bucket_start > bucket_end removes nothing and returns 0.
pub proof fn theorem_bucket_purge_reversed_range(st: St, g: int, bs: int, be: int)
    requires bs > be,
    ensures purge_buckets(st, g, bs, be) == st, purged_count(st, g, bs, be) == 0,
{}

/// A6b (general, q-tmp-002's mirror): after a bucket-range purge of b, deleting an edge of b whose (s, p) keeps a
/// surviving edge in b recreates the bucket's statistics from the survivors, while its bucket counter stays gone.
/// Aggregates and velocity then disagree about the same bucket.
pub proof fn theorem_delete_after_bucket_purge_recreates(st: St, hf: spec_fn(int) -> (int, int), i: int)
    requires
        0 <= i < st.raw.len(), st.cnt.contains_key(k4(st.raw[i], 300)),
        ({ let e = st.raw[i]; let b = bucket_of(e.ts, 300);
           raw_agg(st.raw.remove(i), e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)).count >= 1 }),
    ensures ({
        let e = st.raw[i];
        let b = bucket_of(e.ts, 300);
        let st1 = purge_buckets(st, e.g, b, b);
        let st2 = delete_at(st1, 300, hf, i);
        &&& stat_agg(st2, k4(e, 300)).count == raw_agg(st2.raw, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)).count
        &&& stat_agg(st2, k4(e, 300)).count >= 1
        &&& !st2.bkt.contains_key(k3(e, 300))
    }),
{
    let e = st.raw[i];
    let b = bucket_of(e.ts, 300);
    let st1 = purge_buckets(st, e.g, b, b);
    assert(has_tagg(st, e.g, b));
    assert(!st1.bkt.contains_key(k3(e, 300)));
    assert(st1.raw == st.raw);
}

/// Valid neighbor (A7, temporal.delete): a delete recomputes the bucket's statistics from the surviving edges.
pub proof fn theorem_delete_rebuilds_from_survivors(st: St, hf: spec_fn(int) -> (int, int), i: int)
    requires 0 <= i < st.raw.len(),
    ensures ({
        let e = st.raw[i];
        let b = bucket_of(e.ts, 300);
        let st2 = delete_at(st, 300, hf, i);
        let a = raw_agg(st2.raw, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300));
        &&& st2.raw == st.raw.remove(i)
        &&& stat_agg(st2, k4(e, 300)).count == a.count && stat_agg(st2, k4(e, 300)).min == a.min
        &&& get_aggregate(st2, 300, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)).min == a.min
    }),
{
    let e = st.raw[i];
    let b = bucket_of(e.ts, 300);
    let st2 = delete_at(st, 300, hf, i);
    theorem_one_whole_bucket_reads_statistics(st2, e.g, e.s, e.p, b);
    let a = raw_agg(st2.raw, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300));
    if a.count != 0 { lemma_raw_agg_nonempty(st2.raw, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)); }
    else { lemma_raw_agg_empty(st2.raw, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)); }
}

proof fn lemma_raw_agg_nonempty(raw: Seq<Ev>, g: int, s: int, p: int, lo: int, hi: int)
    ensures raw_agg(raw, g, s, p, lo, hi).count != 0 ==> raw_agg(raw, g, s, p, lo, hi).min.is_some() && raw_agg(raw, g, s, p, lo, hi).max.is_some(),
            raw_agg(raw, g, s, p, lo, hi).count >= 0,
    decreases raw.len(),
{ if raw.len() > 0 { lemma_raw_agg_nonempty(raw.drop_last(), g, s, p, lo, hi); } }

proof fn lemma_raw_agg_empty(raw: Seq<Ev>, g: int, s: int, p: int, lo: int, hi: int)
    ensures raw_agg(raw, g, s, p, lo, hi).count == 0 ==> raw_agg(raw, g, s, p, lo, hi).min.is_none(),
    decreases raw.len(),
{ if raw.len() > 0 { lemma_raw_agg_empty(raw.drop_last(), g, s, p, lo, hi); lemma_raw_agg_nonempty(raw.drop_last(), g, s, p, lo, hi); } }

/// G4 / A5-A6 targets (held): the target list reads the raw edges of exactly the window, so a raw purge empties it
/// and a bucket-range purge leaves it.
pub proof fn theorem_targets_follow_raw(st: St, g: int, s: int, p: int, lo: int, hi: int, bs: int, be: int, o: int)
    ensures
        is_target(purge_buckets(st, g, bs, be), g, s, p, lo, hi, o) == is_target(st, g, s, p, lo, hi, o),
        !is_target(purge_raw_before(st, g, lo, hi + 1), g, s, p, lo, hi, o),
{
    let st2 = purge_buckets(st, g, bs, be);
    assert(st2.raw == st.raw);
    assert(is_target(st2, g, s, p, lo, hi, o) == is_target(st, g, s, p, lo, hi, o));
    lemma_purge_targets(st.raw, g, lo, hi, s, p);
}

proof fn lemma_purge_targets(raw: Seq<Ev>, g: int, lo: int, hi: int, s: int, p: int)
    ensures forall|i: int| 0 <= i < purge_raw(raw, g, lo, hi + 1).len() ==> !#[trigger] hit(purge_raw(raw, g, lo, hi + 1)[i], g, s, p, lo, hi),
    decreases raw.len(),
{
    if raw.len() > 0 {
        lemma_purge_targets(raw.drop_last(), g, lo, hi, s, p);
        let r = purge_raw(raw.drop_last(), g, lo, hi + 1);
        let e = raw.last();
        if !(e.g == g && lo <= e.ts < hi + 1) {
            assert forall|i: int| 0 <= i < r.push(e).len() implies !#[trigger] hit(r.push(e)[i], g, s, p, lo, hi) by {
                if i < r.len() { assert(r.push(e)[i] == r[i]); }
            }
        }
    }
}

// =============================================================== theorems: velocity and bursts
proof fn lemma_bkt_sum_bump(st: St, st2: St, g: int, s: int, k: int, b: int, eb: int)
    requires
        st2.bkt == st.bkt.insert((g, k, s), get0(st.bkt, (g, k, s)) + 1),
    ensures
        bkt_sum(st2, g, s, b, eb) == bkt_sum(st, g, s, b, eb) + (if b <= k <= eb { 1int } else { 0int }),
    decreases eb + 1 - b,
{
    if b <= eb { lemma_bkt_sum_bump(st, st2, g, s, k, b + 1, eb); }
}

/// V1 (general, held): a fresh event of s raises s's velocity by exactly one when its bucket lies between
/// (now - window) \ 300 and now \ 300, whatever its timestamp's place in the window, and by nothing otherwise.
/// So an event up to a bucket before now - window counts, and so does one after now in now's bucket.
pub proof fn theorem_velocity_counts_touched_buckets(st: St, hf: spec_fn(int) -> (int, int), e: Ev, window: int, now_ts: int, clock_s: int)
    requires !occupied(st.raw, e),
    ensures ({
        let now = now_of(now_ts, clock_s);
        let inb = (now - window) / 300 <= bucket_of(e.ts, 300) <= now / 300;
        velocity(write(st, 300, hf, Mode::Insert, e), 300, e.g, e.s, window, now_ts, clock_s)
            == velocity(st, 300, e.g, e.s, window, now_ts, clock_s) + (if inb { 1int } else { 0int })
    }),
{
    let now = now_of(now_ts, clock_s);
    lemma_bkt_sum_bump(st, write(st, 300, hf, Mode::Insert, e), e.g, e.s, bucket_of(e.ts, 300), (now - window) / 300, now / 300);
}

/// V1 at the boundaries, for every store: with now = T + 650 and window 300 (T a multiple of 300), a fresh event at
/// T + 300 (50 s before now - window) raises velocity by one and one at T + 299 by nothing; with now = T + 301, a
/// fresh event at T + 590 (after now) raises it by one.
pub proof fn theorem_velocity_boundaries(st: St, hf: spec_fn(int) -> (int, int), e: Ev, t: int, clock_s: int)
    requires t >= 300, t % 300 == 0, !occupied(st.raw, e),
    ensures
        e.ts == t + 300 ==> velocity(write(st, 300, hf, Mode::Insert, e), 300, e.g, e.s, 300, t + 650, clock_s)
            == velocity(st, 300, e.g, e.s, 300, t + 650, clock_s) + 1,
        e.ts == t + 299 ==> velocity(write(st, 300, hf, Mode::Insert, e), 300, e.g, e.s, 300, t + 650, clock_s)
            == velocity(st, 300, e.g, e.s, 300, t + 650, clock_s),
        e.ts == t + 590 ==> velocity(write(st, 300, hf, Mode::Insert, e), 300, e.g, e.s, 300, t + 301, clock_s)
            == velocity(st, 300, e.g, e.s, 300, t + 301, clock_s) + 1,
{
    theorem_velocity_counts_touched_buckets(st, hf, e, 300, t + 650, clock_s);
    theorem_velocity_counts_touched_buckets(st, hf, e, 300, t + 301, clock_s);
    let q = t / 300;
    lemma_fundamental_div_mod(t, 300);
    lemma_fundamental_div_mod_converse(t + 350, 300, q + 1, 50);
    lemma_fundamental_div_mod_converse(t + 300, 300, q + 1, 0);
    lemma_fundamental_div_mod_converse(t + 650, 300, q + 2, 50);
    lemma_fundamental_div_mod_converse(t + 299, 300, q, 299);
    lemma_fundamental_div_mod_converse(t + 1, 300, q, 1);
    lemma_fundamental_div_mod_converse(t + 590, 300, q + 1, 290);
    lemma_fundamental_div_mod_converse(t + 301, 300, q + 1, 1);
}

/// F-0508 (B1, general): the burst list does not depend on the predicate argument.
pub proof fn theorem_bursts_ignore_predicate(st: St, g: int, p1: int, p2: int, s: int, window: int, thr: int, now_ts: int, clock_s: int)
    ensures burst_listed(st, 300, g, p1, s, window, thr, now_ts, clock_s) == burst_listed(st, 300, g, p2, s, window, thr, now_ts, clock_s),
{}

/// B2 (held): the threshold is inclusive: a present source with velocity equal to the threshold is listed, and not
/// with threshold one higher.
pub proof fn theorem_burst_threshold_inclusive(st: St, g: int, pr: int, s: int, window: int, now_ts: int, clock_s: int)
    requires ({ let now = now_of(now_ts, clock_s); present(st, g, s, (now - window) / 300, now / 300) }),
    ensures ({
        let v = velocity(st, 300, g, s, window, now_ts, clock_s);
        burst_listed(st, 300, g, pr, s, window, v, now_ts, clock_s) && !burst_listed(st, 300, g, pr, s, window, v + 1, now_ts, clock_s)
    }),
{}

/// bug-tmp-002 at the velocity reader (V3): after an update at an occupied coordinate followed by its delete, the
/// bucket counter still claims one event although no raw edge of s remains in the bucket.
pub proof fn theorem_update_then_delete_leaves_velocity(hf: spec_fn(int) -> (int, int), e0: Ev, w1: int)
    requires 0 <= e0.ts,
    ensures ({
        let e1 = Ev { w: w1, ..e0 };
        let st2 = write(write(empty_st(), 300, hf, Mode::Insert, e0), 300, hf, Mode::Update, e1);
        let st3 = delete_at(st2, 300, hf, 0);
        &&& st3.raw.len() == 0
        &&& get0(st3.bkt, k3(e0, 300)) == 1
        &&& !st3.cnt.contains_key(k4(e0, 300))
    }),
{
    let e1 = Ev { w: w1, ..e0 };
    let st1 = write(empty_st(), 300, hf, Mode::Insert, e0);
    assert(!occupied(empty_st().raw, e0));
    assert(st1.raw =~= seq![e0]);
    assert(occupied_at(st1.raw, e1, 0));
    let st2 = write(st1, 300, hf, Mode::Update, e1);
    assert(st2.raw =~= seq![e1]);
    let st3 = delete_at(st2, 300, hf, 0);
    assert(st3.raw =~= Seq::<Ev>::empty());
    assert(raw_agg(st3.raw, e0.g, e0.s, e0.p, b_lo(bucket_of(e0.ts, 300), 300), b_hi(bucket_of(e0.ts, 300), 300)) == zero());
}

/// TemporalIndexMS with the default now (V/M, the recorded divergence): now is the wall clock in seconds while the
/// buckets are milliseconds / 300000, so any event whose millisecond timestamp is later than the seconds clock lies
/// beyond the window and is never counted.
pub proof fn theorem_ms_default_now_misses(st: St, hf: spec_fn(int) -> (int, int), e: Ev, window: int, clock_s: int)
    requires !occupied(st.raw, e), 0 <= window, 0 <= clock_s, e.ts > clock_s + 300000,
    ensures
        velocity(write(st, 300000, hf, Mode::Insert, e), 300000, e.g, e.s, window, 0, clock_s)
            == velocity(st, 300000, e.g, e.s, window, 0, clock_s),
{
    lemma_bkt_sum_bump(st, write(st, 300000, hf, Mode::Insert, e), e.g, e.s, bucket_of(e.ts, 300000), (clock_s - window) / 300000, clock_s / 300000);
    lemma_fundamental_div_mod(clock_s, 300000);
    lemma_fundamental_div_mod(e.ts, 300000);
}

// =============================================================== theorems: distinct-count estimate
/// D (general): an all-zero sketch answers 0.
pub proof fn theorem_distinct_empty_is_zero()
    ensures estimate(hll_empty()) == 0,
{
    assert(!any_set(hll_empty()));
}

/// bug-tmp-103 (general): any sketch with at least one register set answers at least 11, so no window can report
/// 1 to 10 distinct targets.
pub proof fn theorem_distinct_nonempty_at_least_eleven(r: Seq<int>)
    requires wf_regs(r), any_set(r),
    ensures estimate(r) >= 11,
{
    lemma_zs_bounds(r, 16);
    let z = zs(r, 16);
    assert(16 <= z <= 7936);
    assert(88211456 + 500 * z >= 11 * (1000 * z));
    lemma_div_is_ordered(11 * (1000 * z), 88211456 + 500 * z, 1000 * z);
    lemma_div_by_multiple(11, 1000 * z);
}

/// bug-tmp-103 (general): a sketch built from one target, whatever its register and rank, answers exactly 11.
pub proof fn theorem_distinct_one_target_is_eleven(h: (int, int))
    requires wf_hash(h),
    ensures estimate(hll_add(hll_empty(), h)) == 11,
{
    let r = hll_add(hll_empty(), h);
    assert(r =~= hll_empty().update(h.0, h.1));
    assert(any_set(r)) by { assert(r[h.0] > 0); }
    assert(wf_regs(r));
    lemma_zs_one(r, h, 16);
    let z = zs(r, 16);
    lemma_pow2_bounds((9 - h.1) as nat);
    assert(7681 <= z <= 7936);
    let d = 1000 * z;
    let x = 88211456 + 500 * z;
    assert(11 * d <= x && x < 12 * d);
    lemma_fundamental_div_mod_converse(x, d, 11, x - 11 * d);
}

proof fn lemma_zs_one(r: Seq<int>, h: (int, int), n: int)
    requires wf_hash(h), r =~= hll_empty().update(h.0, h.1), 0 <= n <= 16,
    ensures zs(r, n) == (if h.0 < n { 512 * (n - 1) + pow2((9 - h.1) as nat) } else { 512 * n }),
    decreases n,
{
    if n > 0 {
        lemma_zs_one(r, h, n - 1);
        assert(pow2(9) == 512) by { reveal_with_fuel(pow2, 10); }
    }
}

/// Idempotence of a repeated target (D1 d1): adding the same target again changes no register.
pub proof fn theorem_same_target_twice(r: Seq<int>, h: (int, int))
    requires wf_hash(h), r.len() == 16,
    ensures hll_add(hll_add(r, h), h) == hll_add(r, h),
{}

/// D2 (held, general): a window that only touches a bucket merges that bucket's whole sketch, so a target written
/// before the window's start in the same bucket is counted: one write of one target into an empty store, read over
/// any window whose buckets include the target's bucket, answers 11; a window of later buckets answers 0.
pub proof fn theorem_distinct_window_rounded_out(hf: spec_fn(int) -> (int, int), e: Ev, lo: int, hi: int)
    requires wf_hash(hf(e.o)), 0 <= e.ts, 0 <= lo <= hi, lo / 300 == bucket_of(e.ts, 300), hi / 300 == lo / 300,
    ensures
        distinct(write(empty_st(), 300, hf, Mode::Insert, e), 300, e.g, e.s, e.p, lo, hi) == 11,
{
    let st = write(empty_st(), 300, hf, Mode::Insert, e);
    let b = bucket_of(e.ts, 300);
    assert(!occupied(empty_st().raw, e));
    let h1 = hll_add(hll_empty(), hf(e.o));
    assert(h1 != hll_empty()) by { assert(h1[hf(e.o).0] != hll_empty()[hf(e.o).0]); }
    assert(st.hll.contains_key((e.g, b, e.s, e.p)));
    assert(merged(st, e.g, e.s, e.p, b + 1, b) == hll_empty());
    assert(reg_merge(hll_empty(), h1) =~= h1);
    theorem_distinct_one_target_is_eleven(hf(e.o));
}

// =============================================================== theorems: label sets
/// InternLabelSet's canonical text for string values, keys already in collation order (1355-1378): no escaping.
pub open spec fn qt() -> Seq<char> { seq!['"'] }
pub open spec fn enc(v: Seq<char>) -> Seq<char> { qt() + v + qt() }
/// JSON string escaping of quotes and backslashes (the repair; used by control `escape-values`).
pub open spec fn esc(v: Seq<char>) -> Seq<char> decreases v.len() {
    if v.len() == 0 { v } else {
        let c = v.last();
        esc(v.drop_last()) + (if c == '"' || c == '\\' { seq!['\\', c] } else { seq![c] })
    }
}
pub open spec fn pair_text(k: Seq<char>, v: Seq<char>) -> Seq<char> { qt() + k + qt() + seq![':'] + enc(v) }
pub open spec fn body(ps: Seq<(Seq<char>, Seq<char>)>) -> Seq<char> decreases ps.len() {
    if ps.len() == 0 { Seq::empty() }
    else if ps.len() == 1 { pair_text(ps[0].0, ps[0].1) }
    else { body(ps.drop_last()) + seq![','] + pair_text(ps.last().0, ps.last().1) }
}
pub open spec fn canon(ps: Seq<(Seq<char>, Seq<char>)>) -> Seq<char> { seq!['{'] + body(ps) + seq!['}'] }

/// bug-tmp-104 (general): for any keys k1, k2 and string values v1, v2, the one-key set {k1: v1 + '","' + k2 + '":"' + v2}
/// and the two-key set {k1: v1, k2: v2} have the same canonical text, hence the same hash; resolving either answers
/// the two-key text.
pub proof fn theorem_label_sets_collide(k1: Seq<char>, v1: Seq<char>, k2: Seq<char>, v2: Seq<char>)
    ensures ({
        let inj = v1 + qt() + seq![','] + qt() + k2 + qt() + seq![':'] + qt() + v2;
        canon(seq![(k1, inj)]) == canon(seq![(k1, v1), (k2, v2)])
    }),
{
    let inj = v1 + qt() + seq![','] + qt() + k2 + qt() + seq![':'] + qt() + v2;
    let two = seq![(k1, v1), (k2, v2)];
    assert(two.drop_last() =~= seq![(k1, v1)]);
    assert(body(two.drop_last()) == pair_text(k1, v1));
    assert(body(seq![(k1, inj)]) == pair_text(k1, inj));
    assert(pair_text(k1, inj) =~= pair_text(k1, v1) + seq![','] + pair_text(k2, v2));
}

// ------------------------------------------------------------- label sets: value kinds (iteration 53, review M1)
/// A label-set value as InternLabelSet sees it after %FromJSON (1355-1378). `Num` carries IRIS's number text
/// (provider), `Nested` an object or array (its JSON text, which InternLabelSet never reads).
pub enum LVal { Str(Seq<char>), Num(Seq<char>), Bool(bool), Null, Nested(Seq<char>) }
/// The text written for one value. The else branch (1376) concatenates `val`, which for an object or array is an
/// object reference: `r` is that reference's text in this call ("NN@%Library.DynamicObject"), a per-call provider
/// input that does not depend on the value's content.
pub open spec fn val_text(v: LVal, r: Seq<char>) -> Seq<char> {
    match v {
        LVal::Str(t) => enc(t),
        LVal::Num(t) => t,
        LVal::Bool(b) => if b { seq!['t', 'r', 'u', 'e'] } else { seq!['f', 'a', 'l', 's', 'e'] },
        LVal::Null => seq!['n', 'u', 'l', 'l'],
        LVal::Nested(j) => enc(r),
    }
}
pub open spec fn scalar(v: LVal) -> bool { !(v is Nested) }
pub open spec fn pair_t(k: Seq<char>, vt: Seq<char>) -> Seq<char> { qt() + k + qt() + seq![':'] + vt }
pub open spec fn body_t(ps: Seq<(Seq<char>, Seq<char>)>) -> Seq<char> decreases ps.len() {
    if ps.len() == 0 { Seq::empty() }
    else if ps.len() == 1 { pair_t(ps[0].0, ps[0].1) }
    else { body_t(ps.drop_last()) + seq![','] + pair_t(ps.last().0, ps.last().1) }
}
/// The (key, value text) pairs of one call; `refs[i]` is the reference text of value i in that call.
pub open spec fn texts(ps: Seq<(Seq<char>, LVal)>, refs: Seq<Seq<char>>) -> Seq<(Seq<char>, Seq<char>)> {
    Seq::new(ps.len(), |i: int| (ps[i].0, val_text(ps[i].1, refs[i])))
}
/// The canonical text one InternLabelSet call hashes and stores.
pub open spec fn canon_v(ps: Seq<(Seq<char>, LVal)>, refs: Seq<Seq<char>>) -> Seq<char> { seq!['{'] + body_t(texts(ps, refs)) + seq!['}'] }
/// ^KG("labelset"): texts stored once each (SHA-1 taken as injective on these texts, premise P-SHA1); append-only.
pub open spec fn intern(store: Set<Seq<char>>, ps: Seq<(Seq<char>, LVal)>, refs: Seq<Seq<char>>) -> Set<Seq<char>> {
    store.insert(canon_v(ps, refs))
}

/// Valid neighbor (general): a set whose values are all strings, numbers, booleans or null has one canonical text
/// whatever the per-call references, so interning it again returns the same hash and stores nothing new.
pub proof fn theorem_scalar_sets_idempotent(store: Set<Seq<char>>, ps: Seq<(Seq<char>, LVal)>, r1: Seq<Seq<char>>, r2: Seq<Seq<char>>)
    requires r1.len() == ps.len(), r2.len() == ps.len(), forall|i: int| 0 <= i < ps.len() ==> scalar(#[trigger] ps[i].1),
    ensures canon_v(ps, r1) == canon_v(ps, r2), intern(intern(store, ps, r1), ps, r2) == intern(store, ps, r1),
{
    assert(texts(ps, r1) =~= texts(ps, r2));
    assert(intern(intern(store, ps, r1), ps, r2) =~= intern(store, ps, r1));
}

/// bug-tmp-105 (general): the content of a nested value never reaches the canonical text. Two sets that differ only
/// inside nested values, interned with the same references, share one text and hash.
pub proof fn theorem_nested_content_ignored(ps1: Seq<(Seq<char>, LVal)>, ps2: Seq<(Seq<char>, LVal)>, refs: Seq<Seq<char>>)
    requires
        ps1.len() == ps2.len(), refs.len() == ps1.len(),
        forall|i: int| 0 <= i < ps1.len() ==> (#[trigger] ps1[i]).0 == ps2[i].0
            && (ps1[i].1 == ps2[i].1 || (ps1[i].1 is Nested && ps2[i].1 is Nested)),
    ensures canon_v(ps1, refs) == canon_v(ps2, refs),
{
    assert forall|i: int| 0 <= i < ps1.len() implies #[trigger] texts(ps1, refs)[i] == texts(ps2, refs)[i] by {
        if ps1[i].1 != ps2[i].1 {
            assert(val_text(ps1[i].1, refs[i]) == enc(refs[i]));
            assert(val_text(ps2[i].1, refs[i]) == enc(refs[i]));
        }
    }
    assert(texts(ps1, refs) =~= texts(ps2, refs));
}

proof fn lemma_body_t_last(ts: Seq<(Seq<char>, Seq<char>)>)
    requires ts.len() >= 1,
    ensures ({
        let pre: Seq<char> = if ts.len() == 1 { Seq::empty() } else { body_t(ts.drop_last()) + seq![','] };
        body_t(ts) == pre + pair_t(ts.last().0, ts.last().1)
    }),
{
    if ts.len() == 1 { assert(ts[0] == ts.last()); assert(Seq::<char>::empty() + pair_t(ts[0].0, ts[0].1) =~= pair_t(ts[0].0, ts[0].1)); }
}

/// bug-tmp-105 (general): when the last key in sorted order holds a nested value and the two calls' references for it
/// differ, the same set gets two canonical texts, so two hashes, and the second call appends a second entry.
pub proof fn theorem_nested_value_hash_per_call(store: Set<Seq<char>>, ps: Seq<(Seq<char>, LVal)>, r1: Seq<Seq<char>>, r2: Seq<Seq<char>>)
    requires
        ps.len() >= 1, r1.len() == ps.len(), r2.len() == ps.len(), ps.last().1 is Nested, r1.last() != r2.last(),
        forall|i: int| 0 <= i < ps.len() - 1 ==> #[trigger] r1[i] == r2[i],
    ensures
        canon_v(ps, r1) != canon_v(ps, r2),
        intern(intern(store, ps, r1), ps, r2).contains(canon_v(ps, r1)),
        intern(intern(store, ps, r1), ps, r2).contains(canon_v(ps, r2)),
{
    let n = ps.len() as int;
    let t1 = texts(ps, r1);
    let t2 = texts(ps, r2);
    assert(t1.drop_last() =~= t2.drop_last()) by {
        assert forall|i: int| 0 <= i < n - 1 implies #[trigger] t1.drop_last()[i] == t2.drop_last()[i] by {
            assert(r1[i] == r2[i]);
        }
    }
    lemma_body_t_last(t1);
    lemma_body_t_last(t2);
    let pre: Seq<char> = if n == 1 { Seq::empty() } else { body_t(t1.drop_last()) + seq![','] };
    let k = ps.last().0;
    assert(t1.last() == (k, enc(r1.last())));
    assert(t2.last() == (k, enc(r2.last())));
    let a = seq!['{'] + pre + qt() + k + qt() + seq![':'] + qt();
    assert(canon_v(ps, r1) =~= a + r1.last() + qt() + seq!['}']);
    assert(canon_v(ps, r2) =~= a + r2.last() + qt() + seq!['}']);
    if canon_v(ps, r1) == canon_v(ps, r2) {
        let c1 = canon_v(ps, r1);
        assert(c1.len() == canon_v(ps, r2).len());
        assert(r1.last().len() == r2.last().len());
        assert(c1.subrange(a.len() as int, a.len() + r1.last().len() as int) =~= r1.last());
        assert(canon_v(ps, r2).subrange(a.len() as int, a.len() + r2.last().len() as int) =~= r2.last());
    }
}

// ------------------------------------------------------------- the millisecond writer and the seconds readers (review m1)
/// bug-tmp-106 (general): TemporalIndexMS writes the same ^KG("tagg") and ^KG("bucket") nodes, keyed by its own
/// bucket number. For an event at x seconds stored as x * 1000 ms the ms bucket equals the seconds bucket of x, so a
/// seconds whole-bucket read counts it although its stored timestamp lies far outside the window and the raw window
/// read (and any cut window) misses it. Neighbor: the same event written by the seconds class is counted by both.
pub proof fn theorem_ms_edge_in_seconds_whole_bucket(st: St, hf: spec_fn(int) -> (int, int), e: Ev, x: int)
    requires
        x > 0, e.ts == x * 1000, !occupied(st.raw, e),
        get0(st.cnt, (e.g, x / 300, e.s, e.p)) == 0,
        raw_agg(st.raw, e.g, e.s, e.p, b_lo(x / 300, 300), b_hi(x / 300, 300)).count == 0,
    ensures ({
        let b = x / 300;
        let st_ms = write(st, 300000, hf, Mode::Insert, e);
        let es = Ev { ts: x, ..e };
        &&& k4(e, 300000) == k4(es, 300)
        &&& get_aggregate(st_ms, 300, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)).count == 1
        &&& raw_agg(st_ms.raw, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)).count == 0
        &&& (!occupied(st.raw, es) ==> raw_agg(write(st, 300, hf, Mode::Insert, es).raw, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)).count == 1)
    }),
{
    let b = x / 300;
    assert((x * 1000) / 300000 == x / 300) by {
        lemma_fundamental_div_mod(x, 300);
        let q = x / 300; let r = x % 300;
        assert(x * 1000 == q * 300000 + r * 1000) by (nonlinear_arith) requires x == 300 * q + r;
        lemma_fundamental_div_mod_converse(x * 1000, 300000, q, r * 1000);
    }
    let st_ms = write(st, 300000, hf, Mode::Insert, e);
    theorem_one_whole_bucket_reads_statistics(st_ms, e.g, e.s, e.p, b);
    lemma_bucket_bounds(b, 300);
    assert(b_hi(b, 300) < x * 1000) by {
        lemma_fundamental_div_mod(x, 300);
        assert(b * 300 <= x);
        assert(b_hi(b, 300) == b * 300 + 299);
    }
    assert(st_ms.raw.drop_last() =~= st.raw);
    assert(!hit(e, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)));
    let es = Ev { ts: x, ..e };
    if !occupied(st.raw, es) {
        let st_s = write(st, 300, hf, Mode::Insert, es);
        assert(st_s.raw.drop_last() =~= st.raw);
        lemma_fundamental_div_mod(x, 300);
        assert(hit(es, e.g, e.s, e.p, b_lo(b, 300), b_hi(b, 300)));
    }
}

// =============================================================== theorems: an empty key (iteration 56, bug-tmp-108)
/// bug-tmp-108, general: for every state, graph and key, an aggregate read with an empty source (or predicate) over a
/// window that holds no whole bucket and meets no timestamp of its graph answers count 0 and sum 0, silently; the
/// owner's rule (temporal.stats.window: an aggregate read needs a source and a predicate) asks for a refusal.
pub proof fn theorem_empty_key_quiet_cut_window_answers_zero(st: St, div: int, g: int, k: int, lo: int, hi: int)
    requires !some_whole(lo, hi, div), !ts_present(st, g, lo, hi),
    ensures
        get_temporal_aggregate_keys(st, div, g, None, Some(k), Metric::Count, lo, hi) == Py::Int(0),
        get_temporal_aggregate_keys(st, div, g, Some(k), None, Metric::Sum, lo, hi) == Py::Float(0),
        get_temporal_aggregate_keys(st, div, g, None, None, Metric::Count, lo, hi) == Py::Int(0),
{}

/// Neighbors: the same empty-key read raises when the window holds a whole bucket, or when any edge of the graph
/// (any source) has a timestamp in the cut range.
pub proof fn theorem_empty_key_raises_with_whole_bucket_or_event(st: St, div: int, g: int, k: int, lo: int, hi: int, b: int, i: int)
    requires
        (bucket_of(lo, div) <= b <= bucket_of(hi, div) && whole(b, lo, hi, div))
            || (0 <= i < st.raw.len() && st.raw[i].g == g && lo <= st.raw[i].ts <= hi),
    ensures
        get_temporal_aggregate_keys(st, div, g, None, Some(k), Metric::Count, lo, hi) == Py::Raises,
        get_temporal_aggregate_keys(st, div, g, Some(k), None, Metric::Count, lo, hi) == Py::Raises,
{
    if bucket_of(lo, div) <= b <= bucket_of(hi, div) && whole(b, lo, hi, div) { assert(some_whole(lo, hi, div)); }
    else { assert(ts_present(st, g, lo, hi)); }
}

/// Witness on the binding's fixture: one edge at T+50 in a 300-second bucket starting at T; the empty-source count over
/// [T+100, T+200] answers 0, over [T+10, T+100] it raises.
pub proof fn theorem_empty_key_witness(e: Ev, t: int)
    requires t % 300 == 0, t >= 0, e.ts == t + 50,
    ensures ({
        let st = St { raw: seq![e], cnt: Map::empty(), sum: Map::empty(), mn: Map::empty(), mx: Map::empty(),
                      hll: Map::empty(), bkt: Map::empty() };
        &&& get_temporal_aggregate_keys(st, 300, e.g, None, Some(e.p), Metric::Count, t + 100, t + 200) == Py::Int(0)
        &&& get_temporal_aggregate_keys(st, 300, e.g, None, Some(e.p), Metric::Count, t + 10, t + 100) == Py::Raises
    }),
{
    let st = St { raw: seq![e], cnt: Map::empty(), sum: Map::empty(), mn: Map::empty(), mx: Map::empty(),
                  hll: Map::empty(), bkt: Map::empty() };
    assert(bucket_of(t + 100, 300) == t / 300) by (nonlinear_arith) requires t % 300 == 0, t >= 0;
    assert(bucket_of(t + 200, 300) == t / 300) by (nonlinear_arith) requires t % 300 == 0, t >= 0;
    assert(b_lo(t / 300, 300) == t) by (nonlinear_arith) requires t % 300 == 0, t >= 0;
    assert(!some_whole(t + 100, t + 200, 300));
    assert(!ts_present(st, e.g, t + 100, t + 200));
    assert(st.raw[0] == e);
    assert(ts_present(st, e.g, t + 10, t + 100));
}

} // verus!
