//! Module 08, L2 part 1: a Cypher write query on the SQL path at pin 3eaa79cf, over Graph_KG.nodes, rdf_edges (with
//! qualifiers), rdf_props, ^IVG.Ledger("meta") and the engine's LedgerGuard; refinement of `cyw_l1` for every step, the
//! invariant, and the controls F-0801 (two), F-0805, F-C0803 and F-0810.
//!
//! The query runs as one IVG transaction (`_execute_cypher_write`, query.py:1946-1966; a raised error rolls back IVG's
//! level), after `_ledger_check(self, "cypher_dml")` on the transactional route (query.py:2299-2301). The guard
//! (iris_vector_graph/ledger/guard.py:20-80) answers from its cached Meta while it is younger than TTL_SECONDS = 5.0
//! (:38-41) and otherwise probes Graph.KG.Ledger.Meta(), reading any probe failure as never-enabled (:42-56). Steps:
//! `Meta` (another process's Ledger.Enable/SetStrict, Ledger.cls:360-375), `Tick` (the cache gets older than the TTL),
//! `Exec` (the guard passes and the translation commits), `Refuse` (the guard or the translation raises: nothing of the
//! query stays). `pok` is whether the probe can run; `top` is the row SELECT TOP 1 with no ORDER BY happens to return
//! (storage order).
//!
//! **Reviewed design** (remedies): the guard reads Meta at each write and refuses when it cannot (HD-0801 options b/c,
//! fail-closed); CREATE between literal endpoints is guarded by NOT EXISTS as the matched-endpoint path is
//! (translator.py:10306-10365; F-0805 remedy); `SET r = a` copies the node correlated with each relationship's own
//! source (F-C0803 remedy); a literal null deletes the row as a computed null does (translator.py:13648-13654; F-0810
//! remedy). **As built**: the TTL cache (`control_f0801_ttl_window`), the fail-open probe (`control_f0801_fail_open`),
//! a bare `INSERT ... VALUES` (translator.py:10212-10248), `(SELECT TOP 1 a.node_id FROM <preceding rows>)` applied to
//! every merged relationship (translator.py:12362-12395), `UPDATE rdf_props SET val = ?` with a null (translator.py:
//! 13655-13665).
//!
//! Premises: P-C1 a query is one atomic step (its transaction); P-C2 the caller opens no transaction around it; P-C3 no
//! multigraph mode (one relationship per (s, p, o, graph)); P-C4 one graph, one relationship type; P-C5 the guard is
//! the only strict-mode check (raw SQL and other clients are not guarded at all, HD-0801; not modelled).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::cyw_l1::*;

verus! {

pub struct CW2 {
    pub nodes: Set<int>,
    pub edges: Set<(int, int)>,
    pub qual: Map<(int, int), Map<int, Val>>,
    pub props: Map<int, Map<int, Val>>,
    pub en: bool,
    pub strict: bool,
    /// the guard's cached Meta (enabled, strict) and whether it is younger than the TTL
    pub cache: Option<(bool, bool)>,
    pub fresh: bool,
}

pub enum CWL2 {
    Meta { en: bool, strict: bool },
    Tick,
    Exec { q: Q, pok: bool, top: (int, int) },
    Refuse { q: Q, pok: bool, why: Why },
}

pub open spec fn ttl() -> bool { cfg!(feature = "control_f0801_ttl_window") }
pub open spec fn failopen() -> bool { cfg!(feature = "control_f0801_fail_open") }
pub open spec fn f0805() -> bool { cfg!(feature = "control_f0805_literal_insert_unguarded") }
pub open spec fn fc0803() -> bool { cfg!(feature = "control_fc0803_top1_copy") }
pub open spec fn f0810() -> bool { cfg!(feature = "control_f0810_null_keeps_key") }

/// What the guard reads (enabled, strict), or None when it cannot tell (the write is refused, fail-closed).
pub open spec fn guard_meta(s: CW2, pok: bool) -> Option<(bool, bool)> {
    if ttl() && s.cache is Some && s.fresh { s.cache }
    else if pok { Some((s.en, s.strict)) }
    else if failopen() { Some((false, false)) }
    else { None }
}
/// The guard's own state after the check: the as-built cache keeps what it read, for the TTL.
pub open spec fn guarded(s: CW2, pok: bool) -> CW2 {
    if ttl() { CW2 { cache: guard_meta(s, pok), fresh: true, ..s } } else { s }
}
pub open spec fn passes(s: CW2, pok: bool) -> bool {
    guard_meta(s, pok) is Some && !strict_on(guard_meta(s, pok)->Some_0.0, guard_meta(s, pok)->Some_0.1)
}
/// The translation's own preconditions: an unguarded INSERT raises on an existing relationship; TOP 1 picks a row.
pub open spec fn pre2(s: CW2, q: Q, top: (int, int)) -> bool {
    match q {
        Q::CreateLit { ns, es } => !f0805() || es.disjoint(s.edges),
        Q::MergeCopy { rows } => rows.disjoint(s.edges) && (rows.contains(top) || rows == Set::<(int, int)>::empty()),
        Q::SetProp { n, k, v } => true,
    }
}
/// Whether the translation raises SQLCODE -119 (u_spo_graph_ekey) for a relationship that exists.
pub open spec fn dup_raises(s: CW2, q: Q) -> bool {
    f0805() && match q { Q::CreateLit { ns, es } => !es.disjoint(s.edges), _ => false }
}
/// The translation's effect.
pub open spec fn apply2(s: CW2, q: Q, top: (int, int)) -> CW2 {
    match q {
        Q::CreateLit { ns, es } => CW2 { nodes: s.nodes.union(ns), edges: s.edges.union(es),
                                         qual: quals_after(s.edges, s.qual, es, |e: (int, int)| Map::<int, Val>::empty()), ..s },
        Q::MergeCopy { rows } => CW2 { edges: s.edges.union(rows),
                                       qual: quals_after(s.edges, s.qual, rows,
                                                         |e: (int, int)| if fc0803() { pm(s.props, top.0) } else { pm(s.props, e.0) }), ..s },
        Q::SetProp { n, k, v } =>
            if s.nodes.contains(n) {
                CW2 { props: s.props.insert(n, if f0810() && v is None { pm(s.props, n).insert(k, Val::Empty) }
                                               else { set_prop(pm(s.props, n), k, v) }), ..s }
            } else { s },
    }
}

pub open spec fn init2(s: CW2) -> bool {
    s.nodes == Set::<int>::empty() && s.edges == Set::<(int, int)>::empty() && s.qual == Map::<(int, int), Map<int, Val>>::empty()
        && s.props == Map::<int, Map<int, Val>>::empty() && !s.en && !s.strict && s.cache is None && !s.fresh
}

pub open spec fn step2(s: CW2, l: CWL2, t: CW2) -> bool {
    match l {
        CWL2::Meta { en, strict } => t == (CW2 { en, strict, ..s }),
        CWL2::Tick => t == (CW2 { fresh: false, ..s }),
        CWL2::Exec { q, pok, top } => passes(s, pok) && pre2(s, q, top) && t == apply2(guarded(s, pok), q, top),
        CWL2::Refuse { q, pok, why } =>
            t == guarded(s, pok) && match why {
                Why::Strict => guard_meta(s, pok) is Some && strict_on(guard_meta(s, pok)->Some_0.0, guard_meta(s, pok)->Some_0.1),
                Why::Unavailable => guard_meta(s, pok) is None,
                Why::Env => true,
                Why::Dup => dup_raises(s, q),
            },
    }
}

pub open spec fn absc(s: CW2) -> CW1 {
    CW1 { nodes: s.nodes, edges: s.edges, qual: s.qual, props: s.props, en: s.en, strict: s.strict }
}
pub open spec fn labc(l: CWL2) -> Option<CWL1> {
    match l {
        CWL2::Meta { en, strict } => Some(CWL1::Meta { en, strict }),
        CWL2::Tick => None,
        CWL2::Exec { q, pok, top } => Some(CWL1::Write { q }),
        CWL2::Refuse { q, pok, why } => Some(CWL1::Refuse { q, why }),
    }
}

pub open spec fn inv08w(s: CW2) -> bool { inv1(absc(s)) }

pub struct CwL2;
impl Contract for CwL2 {
    type S = CW2;
    type L = CWL2;
    open spec fn init(s: CW2) -> bool { init2(s) }
    open spec fn next(s: CW2, l: CWL2, t: CW2) -> bool { inv08w(s) && step2(s, l, t) }
}
pub struct CwRaw;
impl Contract for CwRaw {
    type S = CW2;
    type L = CWL2;
    open spec fn init(s: CW2) -> bool { init2(s) }
    open spec fn next(s: CW2, l: CWL2, t: CW2) -> bool { step2(s, l, t) }
}

proof fn lemma_exec(s: CW2, q: Q, pok: bool, top: (int, int), t: CW2)
    requires inv08w(s), step2(s, CWL2::Exec { q, pok, top }, t),
    ensures inv08w(t), step_or_stutter::<CwL1>(absc(s), labc(CWL2::Exec { q, pok, top }), absc(t)),
{
    // the guard read the ledger's Meta now: a strict ledger refuses (controls F-0801 TTL and fail-open fail here)
    assert(!strict_on(s.en, s.strict));
    let g = guarded(s, pok);
    assert(absc(g) == absc(s));
    match q {
        Q::MergeCopy { rows } => {
            // each merged relationship gets its own row's node (control F-C0803 fails here)
            assert(apply2(g, q, top).qual =~= apply(absc(s), q).qual);
        }
        Q::SetProp { n, k, v } => {
            // a literal null deletes the row (control F-0810 fails here)
            assert(absc(apply2(g, q, top)) == apply(absc(s), q));
        }
        Q::CreateLit { ns, es } => {}
    }
    assert(absc(apply2(g, q, top)) == apply(absc(s), q));
    lemma_apply_safe(absc(s), q);
}

proof fn lemma_refuse(s: CW2, q: Q, pok: bool, why: Why, t: CW2)
    requires inv08w(s), step2(s, CWL2::Refuse { q, pok, why }, t),
    ensures inv08w(t), step_or_stutter::<CwL1>(absc(s), labc(CWL2::Refuse { q, pok, why }), absc(t)),
{
    // a relationship that exists never fails the query (control F-0805 fails here)
    assert(!(why is Dup));
    assert(absc(t) == absc(s));
}

proof fn lemma_step(s: CW2, l: CWL2, t: CW2)
    requires inv08w(s), step2(s, l, t),
    ensures inv08w(t), step_or_stutter::<CwL1>(absc(s), labc(l), absc(t)),
{
    match l {
        CWL2::Exec { q, pok, top } => lemma_exec(s, q, pok, top, t),
        CWL2::Refuse { q, pok, why } => lemma_refuse(s, q, pok, why, t),
        CWL2::Meta { en, strict } => {
            assert(absc(t).qual == absc(s).qual && absc(t).props == absc(s).props && absc(t).edges == absc(s).edges);
        }
        CWL2::Tick => { assert(absc(t) == absc(s)); }
    }
}

impl Refines<CwL1> for CwL2 {
    open spec fn abs(s: CW2) -> CW1 { absc(s) }
    open spec fn lab(l: CWL2) -> Option<CWL1> { labc(l) }
    proof fn init_refines(s: CW2) {}
    proof fn step_refines(s: CW2, l: CWL2, t: CW2) { lemma_step(s, l, t); }
}

impl SafeContract for CwL2 {
    open spec fn inv(s: CW2) -> bool { inv08w(s) }
    proof fn init_safe(s: CW2) { assert(s.qual.dom() =~= s.edges); }
    proof fn step_safe(s: CW2, l: CWL2, t: CW2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<CW2>, labels: Seq<CWL2>, k: int)
    requires execution::<CwRaw>(states, labels), 0 <= k < states.len(),
    ensures inv08w(states[k]),
    decreases k,
{
    if k == 0 { assert(states[0].qual.dom() =~= states[0].edges); }
    else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<CW2>, labels: Seq<CWL2>)
    requires execution::<CwRaw>(states, labels),
    ensures
        execution::<CwL2>(states, labels),
        abstract_execution::<CwL1>(Seq::new(states.len(), |i: int| absc(states[i])),
                                   Seq::new(labels.len(), |i: int| labc(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv08w(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv08w(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<CwL2>(states, labels));
    trace_refines::<CwL2, CwL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absc(states[i])) =~= Seq::new(states.len(), |i: int| <CwL2 as Refines<CwL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labc(labels[i])) =~= Seq::new(labels.len(), |i: int| <CwL2 as Refines<CwL1>>::lab(labels[i])));
}

/// CYP-X7.2 on the layout: from a state whose ^IVG.Ledger("meta") says enabled and strict, no Exec step is enabled,
/// whatever the guard's cache and whether its probe can run.
pub proof fn theorem_strict_meta_admits_no_write(s: CW2, q: Q, pok: bool, top: (int, int), t: CW2)
    requires inv08w(s), strict_on(s.en, s.strict),
    ensures !step2(s, CWL2::Exec { q, pok, top }, t),
{
    if step2(s, CWL2::Exec { q, pok, top }, t) { lemma_exec(s, q, pok, top, t); }
}

} // verus!
