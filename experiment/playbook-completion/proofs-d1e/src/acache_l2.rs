//! Module 10, L2 part 1: the shared algorithm cache, PageRank's owner and triangle_count's probe over the stored
//! layout at pin 3eaa79cf; refinement of `acache_l1` for every step, the invariant, and controls F-1004, F-1003 and
//! F-C1001.
//!
//! Layout: Graph_KG.nodes rows `nodes`; ^KG("out", 0, a, p, b) `out`; ^KG("__version") `ver` ($Increment by every
//! adjacency write, Adjacency.cls:92, 135, 157, 260, 299); `nver` the reviewed design's node token; ^IVG.AlgoCache
//! (0, algorithm, paramHash) = $LB(token, payload) `cache` (AlgoCache.cls:1-13, Put :45-50); `calls` the calls of
//! `_cached_algorithm` in flight (iris_sql_store.py:921-983) with the token they read; the dictionary's SQL function
//! classes `dict` and ^IVG.Deploy("routines") `rrec`.
//!
//! Steps: `CreateNode` create_node with no edge (node, label and property rows only: no token moves, live
//! b-10-live-cache); `DeleteNode` delete_node through Graph.KG.Eraser.EraseNodeIds, whose InvalidateDerived raises
//! the token and kills ^IVG.AlgoCache (Eraser.cls:1038-1053); `AddEdge` / `DelEdge` an edge write; `LookupHit` /
//! `LookupMiss` AlgoCache.Lookup (token and entry in one call, AlgoCache.cls:27-36); `Compute` the computation on a
//! miss (the call's answer: its linearization point); `Put` AlgoCache.Put under the token read by Lookup;
//! `TriCount` execute_triangle_count (iris_sql_store.py:3977-4006): as built, unless IVG_DISABLE_ARNO, the Arno path's
//! build_kg_adjacency_chunked probes arno_available, which runs _ensure_zf_call_function -> _create_routines: CREATE OR
//! REPLACE FUNCTION for each wrapper the routine record does not list (a class compile, committed) and
//! RoutineRecord.save() (arno_bridge.py:106-134, 360-417; routine_record.py:93-95); `Install` setup's
//! _install_procedures.
//!
//! **Reviewed design** (the findings' remedies and HD-1004): every node create and delete raises a monotonic node
//! token by $Increment, read inside Lookup with the adjacency token and stored in the entry; a hit needs both (F-1004
//! remedy); the PageRank owner lists every node (HD-1004); the read path probes availability without DDL and writes
//! no record (F-C1001 remedy: create the wrappers in setup only). As built the global PageRank key carries the node
//! table's COUNT:MAX token (R313); the reviewed model uses the node token for every cached algorithm instead.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::acache_l1::*;

verus! {

pub struct Ent { pub ver: nat, pub nver: nat, pub ans: Ans }
pub enum Ph { Missed { ver: nat, nver: nat }, Computed { ver: nat, nver: nat, ans: Ans } }
pub struct Call { pub q: Q, pub ph: Ph }

pub struct AS2 {
    pub nodes: Set<int>,
    pub out: Set<Ed>,
    pub ver: nat,
    pub nver: nat,
    pub cache: Map<Q, Ent>,
    pub calls: Map<int, Call>,
    pub dict: Set<int>,
    pub rrec: Set<int>,
}

pub enum AL2 {
    CreateNode { n: int },
    DeleteNode { n: int },
    AddEdge { a: int, b: int },
    DelEdge { a: int, b: int },
    LookupHit { c: int, q: Q, ans: Ans },
    LookupMiss { c: int, q: Q },
    Compute { c: int, q: Q, ans: Ans },
    Put { c: int },
    TriCount,
    Install { names: Set<int> },
}

pub open spec fn f1004() -> bool { cfg!(feature = "control_f1004_create_moves_no_token") }
pub open spec fn f1003() -> bool { cfg!(feature = "control_f1003_owner_cap") }
pub open spec fn fc1001() -> bool { cfg!(feature = "control_fc1001_read_creates_routines") }

/// PageRankGlobalJson stops at 10,000 rows (PageRank.cls:503-520).
pub open spec fn cap() -> nat { 10000 }

/// The $ZF wrappers _zf_wrapper_ddls creates (arno_bridge.py:137-...): twelve names here; the count is immaterial.
pub open spec fn zf() -> Set<int> { Set::<int>::range(1000, 1012) }

pub open spec fn absa(s: AS2) -> AS1 { AS1 { nodes: s.nodes, edges: s.out, dict: s.dict, rrec: s.rrec } }
pub open spec fn fresh2(s: AS2, q: Q) -> Ans { fresh(absa(s), q) }

/// What a computation on a miss answers: as built the owner lists the top 10,000 rows of PageRank (F-1003).
pub open spec fn computes(s: AS2, q: Q, ans: Ans) -> bool {
    if f1003() && q is PageRank {
        ans.over == s.out && ans.rows.subset_of(s.nodes)
            && ans.rows.len() == (if s.nodes.len() <= cap() { s.nodes.len() } else { cap() })
    } else { ans == fresh2(s, q) }
}

pub open spec fn hit(s: AS2, q: Q) -> bool {
    s.cache.contains_key(q) && s.cache[q].ver == s.ver && s.cache[q].nver == s.nver
}

pub open spec fn step2(s: AS2, l: AL2, t: AS2) -> bool {
    match l {
        AL2::CreateNode { n } => !s.nodes.contains(n)
            && t == (AS2 { nodes: s.nodes.insert(n), nver: if f1004() { s.nver } else { s.nver + 1 }, ..s }),
        AL2::DeleteNode { n } => s.nodes.contains(n)
            && t == (AS2 { nodes: s.nodes.remove(n), out: s.out.filter(|e: Ed| e.a != n && e.b != n),
                           ver: s.ver + 1, nver: s.nver + 1, cache: Map::empty(), ..s }),
        AL2::AddEdge { a, b } => s.nodes.contains(a) && s.nodes.contains(b)
            && t == (AS2 { out: s.out.insert(Ed { a, b }), ver: s.ver + 1, ..s }),
        AL2::DelEdge { a, b } => s.out.contains(Ed { a, b })
            && t == (AS2 { out: s.out.remove(Ed { a, b }), ver: s.ver + 1, ..s }),
        AL2::LookupHit { c, q, ans } => !s.calls.contains_key(c) && hit(s, q) && ans == s.cache[q].ans && t == s,
        AL2::LookupMiss { c, q } => !s.calls.contains_key(c) && !hit(s, q)
            && t == (AS2 { calls: s.calls.insert(c, Call { q, ph: Ph::Missed { ver: s.ver, nver: s.nver } }), ..s }),
        AL2::Compute { c, q, ans } => s.calls.contains_key(c) && s.calls[c].q == q && s.calls[c].ph is Missed
            && computes(s, q, ans)
            && t == (AS2 { calls: s.calls.insert(c, Call { q, ph: Ph::Computed {
                    ver: s.calls[c].ph->Missed_ver, nver: s.calls[c].ph->Missed_nver, ans } }), ..s }),
        AL2::Put { c } => s.calls.contains_key(c) && s.calls[c].ph is Computed
            && t == (AS2 { cache: s.cache.insert(s.calls[c].q, Ent { ver: s.calls[c].ph->Computed_ver,
                    nver: s.calls[c].ph->Computed_nver, ans: s.calls[c].ph->Computed_ans }),
                    calls: s.calls.remove(c), ..s }),
        AL2::TriCount => t == (if fc1001() { AS2 { dict: s.dict.union(zf().difference(s.rrec)), rrec: s.rrec.union(zf()), ..s } }
                               else { s }),
        AL2::Install { names } => t == (AS2 { dict: s.dict.union(names), rrec: s.rrec.union(names), ..s }),
    }
}

pub open spec fn init2(s: AS2) -> bool {
    &&& forall|e: Ed| #[trigger] s.out.contains(e) ==> s.nodes.contains(e.a) && s.nodes.contains(e.b)
    &&& s.ver == 0 && s.nver == 0 && s.cache == Map::<Q, Ent>::empty() && s.calls == Map::<int, Call>::empty()
}

pub open spec fn laba(l: AL2) -> Option<AL1> {
    match l {
        AL2::CreateNode { n } => Some(AL1::CreateNode { n }),
        AL2::DeleteNode { n } => Some(AL1::DeleteNode { n }),
        AL2::AddEdge { a, b } => Some(AL1::AddEdge { a, b }),
        AL2::DelEdge { a, b } => Some(AL1::DelEdge { a, b }),
        AL2::LookupHit { c, q, ans } => Some(AL1::Read { q, ans }),
        AL2::LookupMiss { c, q } => None,
        AL2::Compute { c, q, ans } => Some(AL1::Read { q, ans }),
        AL2::Put { c } => None,
        AL2::TriCount => Some(AL1::Triangles),
        AL2::Install { names } => Some(AL1::Install { names }),
    }
}

/// A stored or computed answer whose tokens are the current ones is the fresh answer; every token held is not
/// newer than the current one.
pub open spec fn ent_ok(s: AS2, q: Q, e: Ent) -> bool {
    e.ver <= s.ver && e.nver <= s.nver && (e.ver == s.ver && e.nver == s.nver ==> e.ans == fresh2(s, q))
}
pub open spec fn call_ok(s: AS2, k: Call) -> bool {
    match k.ph {
        Ph::Missed { ver, nver } => ver <= s.ver && nver <= s.nver,
        Ph::Computed { ver, nver, ans } => ent_ok(s, k.q, Ent { ver, nver, ans }),
    }
}

pub open spec fn inv10c(s: AS2) -> bool {
    &&& forall|e: Ed| #[trigger] s.out.contains(e) ==> s.nodes.contains(e.a) && s.nodes.contains(e.b)
    &&& forall|q: Q| #[trigger] s.cache.contains_key(q) ==> ent_ok(s, q, s.cache[q])
    &&& forall|c: int| #[trigger] s.calls.contains_key(c) ==> call_ok(s, s.calls[c])
}

pub struct CacheL2;

impl Contract for CacheL2 {
    type S = AS2;
    type L = AL2;
    open spec fn init(s: AS2) -> bool { init2(s) }
    open spec fn next(s: AS2, l: AL2, t: AS2) -> bool { inv10c(s) && step2(s, l, t) }
}

pub struct CacheRaw;

impl Contract for CacheRaw {
    type S = AS2;
    type L = AL2;
    open spec fn init(s: AS2) -> bool { init2(s) }
    open spec fn next(s: AS2, l: AL2, t: AS2) -> bool { step2(s, l, t) }
}

/// A write that raises a token and keeps the cache, the calls and the routines leaves every entry and call valid.
proof fn lemma_bumped(s: AS2, t: AS2)
    requires inv10c(s), t.cache == s.cache, t.calls == s.calls, t.ver >= s.ver, t.nver >= s.nver,
             t.ver > s.ver || t.nver > s.nver,
             forall|e: Ed| #[trigger] t.out.contains(e) ==> t.nodes.contains(e.a) && t.nodes.contains(e.b),
    ensures inv10c(t),
{
    assert forall|q: Q| #[trigger] t.cache.contains_key(q) implies ent_ok(t, q, t.cache[q]) by { assert(ent_ok(s, q, s.cache[q])); }
    assert forall|c: int| #[trigger] t.calls.contains_key(c) implies call_ok(t, t.calls[c]) by { assert(call_ok(s, s.calls[c])); }
}

proof fn lemma_createnode(s: AS2, n: int, t: AS2)
    requires inv10c(s), step2(s, AL2::CreateNode { n }, t),
    ensures inv10c(t), step_or_stutter::<CacheL1>(absa(s), laba(AL2::CreateNode { n }), absa(t)),
{
    // every stored answer whose tokens are still current is the fresh answer after the write (control F-1004 fails
    // here: the node write moves no token, and an entry answering without the new node stays current)
    assert forall|q: Q| #[trigger] t.cache.contains_key(q) implies ent_ok(t, q, t.cache[q]) by { assert(ent_ok(s, q, s.cache[q])); }
    assert forall|c: int| #[trigger] t.calls.contains_key(c) implies call_ok(t, t.calls[c]) by { assert(call_ok(s, s.calls[c])); }
}

proof fn lemma_compute(s: AS2, c: int, q: Q, ans: Ans, t: AS2)
    requires inv10c(s), step2(s, AL2::Compute { c, q, ans }, t),
    ensures inv10c(t), step_or_stutter::<CacheL1>(absa(s), laba(AL2::Compute { c, q, ans }), absa(t)),
{
    // the computation answers the fresh result: PageRank lists every node (control F-1003 fails here)
    assert(ans == fresh2(s, q));
    assert forall|x: Q| #[trigger] t.cache.contains_key(x) implies ent_ok(t, x, t.cache[x]) by { assert(ent_ok(s, x, s.cache[x])); }
    assert forall|d: int| #[trigger] t.calls.contains_key(d) implies call_ok(t, t.calls[d]) by {
        if d != c { assert(call_ok(s, s.calls[d])); } else { assert(call_ok(s, s.calls[c])); }
    }
}

proof fn lemma_tricount(s: AS2, t: AS2)
    requires inv10c(s), step2(s, AL2::TriCount, t),
    ensures inv10c(t), step_or_stutter::<CacheL1>(absa(s), laba(AL2::TriCount), absa(t)),
{
    // a read writes no SQL function and no routine record (control F-C1001 fails here)
    assert(t.dict == s.dict && t.rrec == s.rrec);
    assert(t == s);
}

proof fn lemma_step(s: AS2, l: AL2, t: AS2)
    requires inv10c(s), step2(s, l, t),
    ensures inv10c(t), step_or_stutter::<CacheL1>(absa(s), laba(l), absa(t)),
{
    match l {
        AL2::CreateNode { n } => lemma_createnode(s, n, t),
        AL2::Compute { c, q, ans } => lemma_compute(s, c, q, ans, t),
        AL2::TriCount => lemma_tricount(s, t),
        AL2::DeleteNode { n } => {
            assert forall|e: Ed| #[trigger] t.out.contains(e) implies t.nodes.contains(e.a) && t.nodes.contains(e.b) by {
                assert(s.out.contains(e));
            }
            assert forall|c: int| #[trigger] t.calls.contains_key(c) implies call_ok(t, t.calls[c]) by { assert(call_ok(s, s.calls[c])); }
            assert(absa(t) == (AS1 { nodes: absa(s).nodes.remove(n), edges: absa(s).edges.filter(|e: Ed| e.a != n && e.b != n), ..absa(s) }));
        }
        AL2::AddEdge { a, b } => {
            assert forall|e: Ed| #[trigger] t.out.contains(e) implies t.nodes.contains(e.a) && t.nodes.contains(e.b) by {
                if e != (Ed { a, b }) { assert(s.out.contains(e)); }
            }
            lemma_bumped(s, t);
        }
        AL2::DelEdge { a, b } => {
            assert forall|e: Ed| #[trigger] t.out.contains(e) implies t.nodes.contains(e.a) && t.nodes.contains(e.b) by {
                assert(s.out.contains(e));
            }
            lemma_bumped(s, t);
        }
        AL2::LookupHit { c, q, ans } => { assert(ent_ok(s, q, s.cache[q])); }
        AL2::LookupMiss { c, q } => {
            assert forall|d: int| #[trigger] t.calls.contains_key(d) implies call_ok(t, t.calls[d]) by {
                if d != c { assert(call_ok(s, s.calls[d])); }
            }
        }
        AL2::Put { c } => {
            assert(call_ok(s, s.calls[c]));
            assert forall|x: Q| #[trigger] t.cache.contains_key(x) implies ent_ok(t, x, t.cache[x]) by {
                if x != s.calls[c].q { assert(ent_ok(s, x, s.cache[x])); }
            }
            assert forall|d: int| #[trigger] t.calls.contains_key(d) implies call_ok(t, t.calls[d]) by { assert(call_ok(s, s.calls[d])); }
        }
        AL2::Install { names } => {
            assert forall|x: Q| #[trigger] t.cache.contains_key(x) implies ent_ok(t, x, t.cache[x]) by { assert(ent_ok(s, x, s.cache[x])); }
            assert forall|d: int| #[trigger] t.calls.contains_key(d) implies call_ok(t, t.calls[d]) by { assert(call_ok(s, s.calls[d])); }
        }
    }
}

impl Refines<CacheL1> for CacheL2 {
    open spec fn abs(s: AS2) -> AS1 { absa(s) }
    open spec fn lab(l: AL2) -> Option<AL1> { laba(l) }
    proof fn init_refines(s: AS2) {}
    proof fn step_refines(s: AS2, l: AL2, t: AS2) { lemma_step(s, l, t); }
}

impl SafeContract for CacheL2 {
    open spec fn inv(s: AS2) -> bool { inv10c(s) }
    proof fn init_safe(s: AS2) {}
    proof fn step_safe(s: AS2, l: AL2, t: AS2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<AS2>, labels: Seq<AL2>, k: int)
    requires execution::<CacheRaw>(states, labels), 0 <= k < states.len(),
    ensures inv10c(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<AS2>, labels: Seq<AL2>)
    requires execution::<CacheRaw>(states, labels),
    ensures
        execution::<CacheL2>(states, labels),
        abstract_execution::<CacheL1>(Seq::new(states.len(), |i: int| absa(states[i])),
                                      Seq::new(labels.len(), |i: int| laba(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv10c(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv10c(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<CacheL2>(states, labels));
    trace_refines::<CacheL2, CacheL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absa(states[i])) =~= Seq::new(states.len(), |i: int| <CacheL2 as Refines<CacheL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| laba(labels[i])) =~= Seq::new(labels.len(), |i: int| <CacheL2 as Refines<CacheL1>>::lab(labels[i])));
}

/// On the layout (ALG-B16.11): an entry AlgoCache.Lookup serves is the fresh answer of the current graph.
pub proof fn theorem_hit_is_fresh(s: AS2, c: int, q: Q, ans: Ans, t: AS2)
    requires inv10c(s), step2(s, AL2::LookupHit { c, q, ans }, t),
    ensures ans == fresh2(s, q),
{
    assert(ent_ok(s, q, s.cache[q]));
}

} // verus!
