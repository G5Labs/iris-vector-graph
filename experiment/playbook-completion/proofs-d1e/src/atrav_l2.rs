//! Module 10, L2 part 2: shortest paths, variable-length expansion and label propagation over the adjacency index at
//! pin 3eaa79cf; refinement of `atrav_l1` for every step, the invariant, and controls HD-1003 and F-1008.
//!
//! Layout: `out` ^KG("out", g, a, p, b) and `inn` ^KG("in", g, b, p, a) (stored here as the entry at b towards a),
//! both written by the row's functional index (one predicate); `nodes0` the default graph's node rows; `cdlp` each
//! CDLPJson call's local labels (Algorithms.cls:93-186).
//!
//! Steps: `AddNode`, `AddEdge`, `DelEdge` (the row and both index entries); `SpLength` IRISGraphStore.
//! shortest_path_length -> TraversalPaths.ShortestLength (iris_sql_store.py:2162-2181; TraversalPaths.cls:117-...:
//! the source side follows out entries, the target side in entries, "both" reads the other kind too); `SpPaths`
//! execute_shortest_path -> ShortestPathJson (iris_sql_store.py:2183-2215: "in" reversed by the caller;
//! TraversalPaths.cls:5-80: out entries for "out"/"both", in entries for "both", a zero-length path when the ends
//! are equal); `VarLen` VarLength.Ends (VarLength.cls:44-51: with pAll every graph key holding out entries;
//! Adjacent, :126-148, reads a node's entries in every graph of pGraphs at each hop); `CdlpInit` / `CdlpRound` /
//! `CdlpEnd` CDLPJson's label set-up (every node with an out or in entry of graph 0, its own label), a round (a node
//! takes a label of one of its neighbours or keeps its own; which one is numerics), and kg_CDLP's answer, completed
//! with the edgeless nodes labelled with themselves (complete_labels, iris_vector_graph/_edgeless.py:109-114). The
//! answer of a shortest path or an expansion is any answer the routine's contract allows over what it reads: the
//! model checks the contract, not the search.
//!
//! **Reviewed design** (HD-1003 working answer, F-1008 remedy): ShortestLength and ShortestPathJson refuse a direction
//! outside their set (CheckDirection), and shortest_path_length reverses "in" as execute_shortest_path does; the
//! every-graph expansion walks each graph separately (the first hop fixes the graph). Premise P-T1 (a writer of the
//! default graph never overlaps a CDLP call) is a guard on the writers here; the pin does not enforce it.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::atrav_l1::*;

verus! {

pub struct TS2 { pub nodes0: Set<int>, pub out: Set<E>, pub inn: Set<E>, pub cdlp: Map<int, Map<int, int>> }

pub enum TL2 {
    AddNode { n: int },
    AddEdge { g: int, a: int, b: int },
    DelEdge { g: int, a: int, b: int },
    SpLength { a: int, b: int, maxh: nat, dir: Dir, ans: Sp },
    SpPaths { a: int, b: int, maxh: nat, dir: Dir, ans: Sp },
    VarLen { start: int, lo: nat, hi: nat, all: bool, ends: Set<int> },
    CdlpInit { c: int },
    CdlpRound { c: int, nl: Map<int, int> },
    CdlpEnd { c: int, labels: Map<int, int> },
}

pub open spec fn hd1003() -> bool { cfg!(feature = "control_hd1003_direction_unchecked") }
pub open spec fn f1008() -> bool { cfg!(feature = "control_f1008_every_graph_mixed") }

pub open spec fn rev(e: E) -> E { E { g: e.g, a: e.b, b: e.a } }

/// What a routine reads for "out" (the out entries of graph 0) and for "both" (its out and in entries).
pub open spec fn rd_out(s: TS2) -> spec_fn(int, int) -> bool { st_out(s.out, 0) }
pub open spec fn rd_both(s: TS2) -> spec_fn(int, int) -> bool {
    |x: int, y: int| s.out.contains(E { g: 0, a: x, b: y }) || s.inn.contains(E { g: 0, a: x, b: y })
}

/// shortest_path_length -> ShortestLength.
pub open spec fn splength2(s: TS2, a: int, b: int, maxh: nat, dir: Dir, ans: Sp) -> bool {
    if hd1003() {
        // as built: "in" passed through, and every direction but "both" read as "out" (TraversalPaths.cls:122)
        if dir is Both { shortest(rd_both(s), a, b, maxh, ans) } else { shortest(rd_out(s), a, b, maxh, ans) }
    } else {
        match dir {
            Dir::Out => shortest(rd_out(s), a, b, maxh, ans),
            Dir::In => shortest(rd_out(s), b, a, maxh, ans),
            Dir::Both => shortest(rd_both(s), a, b, maxh, ans),
            Dir::Other => ans is Refused,
        }
    }
}

/// execute_shortest_path -> ShortestPathJson.
pub open spec fn sppaths2(s: TS2, a: int, b: int, maxh: nat, dir: Dir, ans: Sp) -> bool {
    match dir {
        Dir::Out => shortest(rd_out(s), a, b, maxh, ans),
        Dir::In => shortest(rd_out(s), b, a, maxh, ans),
        Dir::Both => shortest(rd_both(s), a, b, maxh, ans),
        // as built: no entry is read for another direction: the zero-length path or none (TraversalPaths.cls:15-24, 45, 70)
        Dir::Other => if hd1003() { ans == (if a == b { Sp::Len { n: 0 } } else { Sp::NoPath }) } else { ans is Refused },
    }
}

/// Adjacent over every graph in scope at each hop (VarLength.cls:126-148).
pub open spec fn st_any(es: Set<E>, all: bool) -> spec_fn(int, int) -> bool {
    |x: int, y: int| exists|g: int| (all || g == 0) && #[trigger] es.contains(E { g, a: x, b: y })
}
pub open spec fn reach2(s: TS2, start: int, lo: nat, hi: nat, all: bool, x: int) -> bool {
    if f1008() { exists|l: nat| lo <= l <= hi && #[trigger] walk(st_any(s.out, all), start, x, l) }
    else { reach1(s.out, start, lo, hi, all, x) }
}

pub open spec fn varlen2(s: TS2, start: int, lo: nat, hi: nat, all: bool, ends: Set<int>) -> bool {
    forall|x: int| #[trigger] ends.contains(x) <==> reach2(s, start, lo, hi, all, x)
}

pub open spec fn adj0(out: Set<E>, inn: Set<E>, n: int, m: int) -> bool {
    out.contains(E { g: 0, a: n, b: m }) || inn.contains(E { g: 0, a: n, b: m })
}
pub open spec fn endpoint0(out: Set<E>, inn: Set<E>, n: int) -> bool { exists|m: int| #[trigger] adj0(out, inn, n, m) }
pub open spec fn lab_or(lab: Map<int, int>, m: int) -> int { if lab.contains_key(m) { lab[m] } else { m } }
pub open spec fn round_ok(out: Set<E>, inn: Set<E>, lab: Map<int, int>, nl: Map<int, int>) -> bool {
    nl.dom() == lab.dom()
        && forall|n: int| #[trigger] nl.contains_key(n) ==>
            (nl[n] == lab[n] || exists|m: int| m != n && #[trigger] adj0(out, inn, n, m) && nl[n] == lab_or(lab, m))
}
pub open spec fn loners(nodes0: Set<int>, out: Set<E>, inn: Set<E>) -> Set<int> { nodes0.filter(|n: int| !endpoint0(out, inn, n)) }
pub open spec fn init_labels(nodes0: Set<int>, out: Set<E>, inn: Set<E>) -> Map<int, int> {
    Map::new(nodes0.filter(|n: int| endpoint0(out, inn, n)), |n: int| n)
}
pub open spec fn end_labels(nodes0: Set<int>, out: Set<E>, inn: Set<E>, lab: Map<int, int>) -> Map<int, int> {
    Map::new(lab.dom().union(loners(nodes0, out, inn)), |n: int| lab_or(lab, n))
}

pub open spec fn step2(s: TS2, l: TL2, t: TS2) -> bool {
    match l {
        TL2::AddNode { n } => s.cdlp == Map::<int, Map<int, int>>::empty() && t == (TS2 { nodes0: s.nodes0.insert(n), ..s }),
        TL2::AddEdge { g, a, b } => s.cdlp == Map::<int, Map<int, int>>::empty()
            && (g == 0 ==> s.nodes0.contains(a) && s.nodes0.contains(b))
            && t == (TS2 { out: s.out.insert(E { g, a, b }), inn: s.inn.insert(E { g, a: b, b: a }), ..s }),
        TL2::DelEdge { g, a, b } => s.cdlp == Map::<int, Map<int, int>>::empty() && s.out.contains(E { g, a, b })
            && t == (TS2 { out: s.out.remove(E { g, a, b }), inn: s.inn.remove(E { g, a: b, b: a }), ..s }),
        TL2::SpLength { a, b, maxh, dir, ans } => splength2(s, a, b, maxh, dir, ans) && t == s,
        TL2::SpPaths { a, b, maxh, dir, ans } => sppaths2(s, a, b, maxh, dir, ans) && t == s,
        TL2::VarLen { start, lo, hi, all, ends } => varlen2(s, start, lo, hi, all, ends) && t == s,
        TL2::CdlpInit { c } => !s.cdlp.contains_key(c) && t == (TS2 { cdlp: s.cdlp.insert(c, init_labels(s.nodes0, s.out, s.inn)), ..s }),
        TL2::CdlpRound { c, nl } => s.cdlp.contains_key(c) && round_ok(s.out, s.inn, s.cdlp[c], nl)
            && t == (TS2 { cdlp: s.cdlp.insert(c, nl), ..s }),
        TL2::CdlpEnd { c, labels } => s.cdlp.contains_key(c) && labels == end_labels(s.nodes0, s.out, s.inn, s.cdlp[c])
            && t == (TS2 { cdlp: s.cdlp.remove(c), ..s }),
    }
}

pub open spec fn init2(s: TS2) -> bool {
    s.out == Set::<E>::empty() && s.inn == Set::<E>::empty() && s.cdlp == Map::<int, Map<int, int>>::empty()
}

pub open spec fn abst(s: TS2) -> TS1 { TS1 { nodes0: s.nodes0, edges: s.out } }

pub open spec fn labt(l: TL2) -> Option<TL1> {
    match l {
        TL2::AddNode { n } => Some(TL1::AddNode { n }),
        TL2::AddEdge { g, a, b } => Some(TL1::AddEdge { g, a, b }),
        TL2::DelEdge { g, a, b } => Some(TL1::DelEdge { g, a, b }),
        TL2::SpLength { a, b, maxh, dir, ans } => Some(TL1::Path { a, b, maxh, dir, ans }),
        TL2::SpPaths { a, b, maxh, dir, ans } => Some(TL1::Path { a, b, maxh, dir, ans }),
        TL2::VarLen { start, lo, hi, all, ends } => Some(TL1::VarLen { start, lo, hi, all, ends }),
        TL2::CdlpInit { c } => None,
        TL2::CdlpRound { c, nl } => None,
        TL2::CdlpEnd { c, labels } => Some(TL1::Cdlp { labels }),
    }
}

/// A call's labels: every node of the default graph with an entry, each labelled with a node of the default graph.
pub open spec fn lab_ok(nodes0: Set<int>, out: Set<E>, inn: Set<E>, lab: Map<int, int>) -> bool {
    (forall|n: int| #[trigger] lab.contains_key(n) <==> nodes0.contains(n) && endpoint0(out, inn, n))
        && (forall|n: int| #[trigger] lab.contains_key(n) ==> nodes0.contains(lab[n]))
}

/// L1's invariant on the out entries; the in entries mirror the out entries; every CDLP call's labels are sound.
pub open spec fn inv10t(s: TS2) -> bool {
    &&& forall|e: E| #[trigger] s.out.contains(e) && e.g == 0 ==> s.nodes0.contains(e.a) && s.nodes0.contains(e.b)
    &&& forall|e: E| #[trigger] s.inn.contains(e) <==> s.out.contains(rev(e))
    &&& forall|c: int| #[trigger] s.cdlp.contains_key(c) ==> lab_ok(s.nodes0, s.out, s.inn, s.cdlp[c])
}

pub struct TravL2;

impl Contract for TravL2 {
    type S = TS2;
    type L = TL2;
    open spec fn init(s: TS2) -> bool { init2(s) }
    open spec fn next(s: TS2, l: TL2, t: TS2) -> bool { inv10t(s) && step2(s, l, t) }
}

pub struct TravRaw;

impl Contract for TravRaw {
    type S = TS2;
    type L = TL2;
    open spec fn init(s: TS2) -> bool { init2(s) }
    open spec fn next(s: TS2, l: TL2, t: TS2) -> bool { step2(s, l, t) }
}

/// With the mirror, reading out and in entries of graph 0 is walking the default graph's edges both ways.
pub proof fn lemma_both(s: TS2)
    requires forall|e: E| #[trigger] s.inn.contains(e) <==> s.out.contains(rev(e)),
    ensures forall|x: int, y: int| #[trigger] rd_both(s)(x, y) == st_both(s.out, 0)(x, y),
{
    assert forall|x: int, y: int| #[trigger] rd_both(s)(x, y) == st_both(s.out, 0)(x, y) by {
        assert(s.inn.contains(E { g: 0, a: x, b: y }) == s.out.contains(rev(E { g: 0, a: x, b: y })));
    }
}

proof fn lemma_splength(s: TS2, a: int, b: int, maxh: nat, dir: Dir, ans: Sp, t: TS2)
    requires inv10t(s), step2(s, TL2::SpLength { a, b, maxh, dir, ans }, t),
    ensures inv10t(t), step_or_stutter::<TravL1>(abst(s), labt(TL2::SpLength { a, b, maxh, dir, ans }), abst(t)),
{
    lemma_both(s);
    lemma_shortest_ext(rd_both(s), st_both(s.out, 0), a, b, maxh, ans);
    // the length answers the direction asked, "in" reversed, another refused (control HD-1003 fails here)
    assert(path1(s.out, a, b, maxh, dir, ans));
}

proof fn lemma_sppaths(s: TS2, a: int, b: int, maxh: nat, dir: Dir, ans: Sp, t: TS2)
    requires inv10t(s), step2(s, TL2::SpPaths { a, b, maxh, dir, ans }, t),
    ensures inv10t(t), step_or_stutter::<TravL1>(abst(s), labt(TL2::SpPaths { a, b, maxh, dir, ans }), abst(t)),
{
    lemma_both(s);
    lemma_shortest_ext(rd_both(s), st_both(s.out, 0), a, b, maxh, ans);
    // the paths answer the direction asked, another refused (control HD-1003 fails here)
    assert(path1(s.out, a, b, maxh, dir, ans));
}

proof fn lemma_varlen(s: TS2, start: int, lo: nat, hi: nat, all: bool, ends: Set<int>, t: TS2)
    requires inv10t(s), step2(s, TL2::VarLen { start, lo, hi, all, ends }, t),
    ensures inv10t(t), step_or_stutter::<TravL1>(abst(s), labt(TL2::VarLen { start, lo, hi, all, ends }), abst(t)),
{
    // every end is reached by a walk inside one graph (control F-1008 fails here)
    assert(forall|x: int| reach2(s, start, lo, hi, all, x) == reach1(s.out, start, lo, hi, all, x));
    assert(varlen1(abst(s).edges, start, lo, hi, all, ends));
}

proof fn lemma_cdlpround(s: TS2, c: int, nl: Map<int, int>, t: TS2)
    requires inv10t(s), step2(s, TL2::CdlpRound { c, nl }, t),
    ensures inv10t(t), step_or_stutter::<TravL1>(abst(s), labt(TL2::CdlpRound { c, nl }), abst(t)),
{
    let lab = s.cdlp[c];
    assert(lab_ok(s.nodes0, s.out, s.inn, lab));
    assert forall|n: int| #[trigger] nl.contains_key(n) implies s.nodes0.contains(nl[n]) by {
        assert(lab.dom().contains(n));
        if nl[n] != lab[n] {
            let m = choose|m: int| m != n && #[trigger] adj0(s.out, s.inn, n, m) && nl[n] == lab_or(lab, m);
            if s.inn.contains(E { g: 0, a: n, b: m }) { assert(s.out.contains(rev(E { g: 0, a: n, b: m }))); }
            else { assert(s.out.contains(E { g: 0, a: n, b: m })); }
        }
    }
    assert forall|n: int| #[trigger] nl.contains_key(n) <==> s.nodes0.contains(n) && endpoint0(s.out, s.inn, n) by {
        assert(nl.dom().contains(n) == lab.dom().contains(n));
    }
    assert(lab_ok(t.nodes0, t.out, t.inn, nl));
    assert forall|d: int| #[trigger] t.cdlp.contains_key(d) implies lab_ok(t.nodes0, t.out, t.inn, t.cdlp[d]) by {
        if d != c { assert(s.cdlp.contains_key(d)); }
    }
}

proof fn lemma_cdlpend(s: TS2, c: int, labels: Map<int, int>, t: TS2)
    requires inv10t(s), step2(s, TL2::CdlpEnd { c, labels }, t),
    ensures inv10t(t), step_or_stutter::<TravL1>(abst(s), labt(TL2::CdlpEnd { c, labels }), abst(t)),
{
    let lab = s.cdlp[c];
    assert(lab_ok(s.nodes0, s.out, s.inn, lab));
    let lo = loners(s.nodes0, s.out, s.inn);
    assert(lab.dom().union(lo) =~= s.nodes0) by {
        assert forall|n: int| lab.dom().union(lo).contains(n) <==> s.nodes0.contains(n) by {
            assert(lab.dom().contains(n) == lab.contains_key(n));
        }
    }
    assert(labels.dom() == s.nodes0);
    assert forall|n: int| #[trigger] labels.contains_key(n) implies s.nodes0.contains(labels[n]) by {
        assert(labels[n] == lab_or(lab, n));
    }
    assert(cdlp1(abst(s), labels));
    assert forall|d: int| #[trigger] t.cdlp.contains_key(d) implies lab_ok(t.nodes0, t.out, t.inn, t.cdlp[d]) by {
        assert(s.cdlp.contains_key(d));
    }
}

proof fn lemma_step(s: TS2, l: TL2, t: TS2)
    requires inv10t(s), step2(s, l, t),
    ensures inv10t(t), step_or_stutter::<TravL1>(abst(s), labt(l), abst(t)),
{
    match l {
        TL2::SpLength { a, b, maxh, dir, ans } => lemma_splength(s, a, b, maxh, dir, ans, t),
        TL2::SpPaths { a, b, maxh, dir, ans } => lemma_sppaths(s, a, b, maxh, dir, ans, t),
        TL2::VarLen { start, lo, hi, all, ends } => lemma_varlen(s, start, lo, hi, all, ends, t),
        TL2::CdlpRound { c, nl } => lemma_cdlpround(s, c, nl, t),
        TL2::CdlpEnd { c, labels } => lemma_cdlpend(s, c, labels, t),
        TL2::CdlpInit { c } => {
            let il = init_labels(s.nodes0, s.out, s.inn);
            assert forall|n: int| #[trigger] il.contains_key(n) <==> s.nodes0.contains(n) && endpoint0(s.out, s.inn, n) by {}
            assert(lab_ok(t.nodes0, t.out, t.inn, il));
            assert forall|d: int| #[trigger] t.cdlp.contains_key(d) implies lab_ok(t.nodes0, t.out, t.inn, t.cdlp[d]) by {
                if d != c { assert(s.cdlp.contains_key(d)); }
            }
        }
        TL2::AddEdge { g, a, b } => {
            assert forall|e: E| #[trigger] t.out.contains(e) && e.g == 0 implies t.nodes0.contains(e.a) && t.nodes0.contains(e.b) by {
                if e != (E { g, a, b }) { assert(s.out.contains(e)); }
            }
            assert forall|e: E| #[trigger] t.inn.contains(e) <==> t.out.contains(rev(e)) by {
                assert(s.inn.contains(e) <==> s.out.contains(rev(e)));
            }
        }
        TL2::DelEdge { g, a, b } => {
            assert forall|e: E| #[trigger] t.out.contains(e) && e.g == 0 implies t.nodes0.contains(e.a) && t.nodes0.contains(e.b) by {
                assert(s.out.contains(e));
            }
            assert forall|e: E| #[trigger] t.inn.contains(e) <==> t.out.contains(rev(e)) by {
                assert(s.inn.contains(e) <==> s.out.contains(rev(e)));
            }
        }
        TL2::AddNode { n } => {
            assert forall|e: E| #[trigger] t.out.contains(e) && e.g == 0 implies t.nodes0.contains(e.a) && t.nodes0.contains(e.b) by {
                assert(s.out.contains(e));
            }
        }
    }
}

impl Refines<TravL1> for TravL2 {
    open spec fn abs(s: TS2) -> TS1 { abst(s) }
    open spec fn lab(l: TL2) -> Option<TL1> { labt(l) }
    proof fn init_refines(s: TS2) {}
    proof fn step_refines(s: TS2, l: TL2, t: TS2) { lemma_step(s, l, t); }
}

impl SafeContract for TravL2 {
    open spec fn inv(s: TS2) -> bool { inv10t(s) }
    proof fn init_safe(s: TS2) {}
    proof fn step_safe(s: TS2, l: TL2, t: TS2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<TS2>, labels: Seq<TL2>, k: int)
    requires execution::<TravRaw>(states, labels), 0 <= k < states.len(),
    ensures inv10t(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<TS2>, labels: Seq<TL2>)
    requires execution::<TravRaw>(states, labels),
    ensures
        execution::<TravL2>(states, labels),
        abstract_execution::<TravL1>(Seq::new(states.len(), |i: int| abst(states[i])),
                                     Seq::new(labels.len(), |i: int| labt(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv10t(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv10t(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<TravL2>(states, labels));
    trace_refines::<TravL2, TravL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| abst(states[i])) =~= Seq::new(states.len(), |i: int| <TravL2 as Refines<TravL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labt(labels[i])) =~= Seq::new(labels.len(), |i: int| <TravL2 as Refines<TravL1>>::lab(labels[i])));
}

/// On the layout: a label kg_CDLP answers is a node of the default graph (graph scope of label propagation).
pub proof fn theorem_cdlp_answer_in_default_graph(s: TS2, c: int, labels: Map<int, int>, t: TS2, n: int)
    requires inv10t(s), step2(s, TL2::CdlpEnd { c, labels }, t), labels.contains_key(n),
    ensures s.nodes0.contains(n), s.nodes0.contains(labels[n]),
{
    lemma_cdlpend(s, c, labels, t);
}

} // verus!
