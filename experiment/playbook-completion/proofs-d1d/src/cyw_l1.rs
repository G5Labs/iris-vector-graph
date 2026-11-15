//! Module 08, L1 part 1: Cypher write queries on the SQL path, under the ledger's strict mode.
//!
//! Sources: specs/213-graph-revision-ledger/contracts/ledger-api.md:82-92 and CYP-X7.2 (with the ledger enabled in
//! strict mode, `execute_cypher` with any updating clause raises LedgerStrictModeError and changes nothing; HD-0801:
//! the intended refusal applies with no window and no fail-open case); CYP-I6.4 / query.py:1946-1966 (a write query is
//! one transaction: a failed query writes nothing); KNOWN_ISSUES.md:25-31 and CYP-B6.7.6/7 (outside multigraph mode a
//! CREATE of a relationship that exists returns no error and writes nothing for it); openCypher's per-row MERGE (CYP-B6.8:
//! `ON CREATE SET r = a` copies that row's node a onto that row's relationship); openCypher's SET to null (CYP-B6.9,
//! tests/e2e/test_470_set_null_e2e.py docstring: `SET n.p = null` removes the property).
//!
//! Abstraction (explicit): the Cypher text and its translation are not modelled; a write query is one of three shapes,
//! each given by its effect on the graph: `CreateLit` (CREATE of nodes and of relationships between literal endpoints,
//! one relationship type, no properties on them), `MergeCopy` (MATCH (a), (t) MERGE (a)-[r]->(t) ON CREATE SET r = a,
//! over the rows the MATCH binds, given as their (a, t) pairs; modelled only for rows whose relationship does not exist
//! yet and whose pairs are distinct, as in the live check), `SetProp` (MATCH (n {id}) SET n.k = v, v a value or a
//! literal null). Property values are integers; `Val::Empty` is the stored '' that stands for no value. The ledger's
//! state is `en` (enabled) and `strict`; recording of ledger changesets is not modelled (a strict ledger refuses the
//! write; a non-strict one lets it through unrecorded, as built and as documented).
//!
//! Labels: `Meta` (another process enables, disables or sets strict: Ledger.Enable/SetStrict), `Write{q}` (the query
//! commits), `Refuse{q, why}` (the query raises and writes nothing: strict mode, the guard unavailable, a SQL error of
//! the environment, or because a relationship it creates exists: `Dup`).
//!
//! Business rules: **in strict mode no write query commits**; **a refused query changes nothing**; **a query is never
//! refused because a relationship it creates exists** (no `Dup`); **each merged relationship gets its own row's node's
//! properties**; **a null SET removes the key**. `inv1` (proved inductive): every relationship has its qualifiers, and
//! no stored property or qualifier holds the empty value (openCypher has no null-valued property).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub enum Val { Int(int), Empty }
pub struct CW1 {
    pub nodes: Set<int>,
    pub edges: Set<(int, int)>,
    pub qual: Map<(int, int), Map<int, Val>>,
    pub props: Map<int, Map<int, Val>>,
    pub en: bool,
    pub strict: bool,
}
pub enum Q {
    CreateLit { ns: Set<int>, es: Set<(int, int)> },
    MergeCopy { rows: Set<(int, int)> },
    SetProp { n: int, k: int, v: Option<int> },
}
pub enum Why { Strict, Unavailable, Env, Dup }
pub enum CWL1 {
    Meta { en: bool, strict: bool },
    Write { q: Q },
    Refuse { q: Q, why: Why },
}

/// A node's properties (its rdf_props rows).
pub open spec fn pm(props: Map<int, Map<int, Val>>, a: int) -> Map<int, Val> {
    if props.contains_key(a) { props[a] } else { Map::<int, Val>::empty() }
}
pub open spec fn strict_on(en: bool, strict: bool) -> bool { en && strict }
/// The relationships' qualifiers after edges `es` are added with `f` giving a new one's qualifiers.
pub open spec fn quals_after(edges: Set<(int, int)>, qual: Map<(int, int), Map<int, Val>>, es: Set<(int, int)>,
                             f: spec_fn((int, int)) -> Map<int, Val>) -> Map<(int, int), Map<int, Val>> {
    Map::new(edges.union(es), |e: (int, int)| if edges.contains(e) { qual[e] } else { f(e) })
}
pub open spec fn set_prop(m: Map<int, Val>, k: int, v: Option<int>) -> Map<int, Val> {
    match v { Some(x) => m.insert(k, Val::Int(x)), None => m.remove(k) }
}
/// What the query may assume: a MERGE's rows name relationships that do not exist (the modelled case).
pub open spec fn pre(s: CW1, q: Q) -> bool {
    match q { Q::MergeCopy { rows } => rows.disjoint(s.edges), _ => true }
}
/// openCypher semantics of the three shapes.
pub open spec fn apply(s: CW1, q: Q) -> CW1 {
    match q {
        Q::CreateLit { ns, es } => CW1 { nodes: s.nodes.union(ns), edges: s.edges.union(es),
                                         qual: quals_after(s.edges, s.qual, es, |e: (int, int)| Map::<int, Val>::empty()), ..s },
        Q::MergeCopy { rows } => CW1 { edges: s.edges.union(rows),
                                       qual: quals_after(s.edges, s.qual, rows, |e: (int, int)| pm(s.props, e.0)), ..s },
        Q::SetProp { n, k, v } =>
            if s.nodes.contains(n) { CW1 { props: s.props.insert(n, set_prop(pm(s.props, n), k, v)), ..s } } else { s },
    }
}

pub struct CwL1;

impl Contract for CwL1 {
    type S = CW1;
    type L = CWL1;

    open spec fn init(s: CW1) -> bool {
        s.nodes == Set::<int>::empty() && s.edges == Set::<(int, int)>::empty() && s.qual == Map::<(int, int), Map<int, Val>>::empty()
            && s.props == Map::<int, Map<int, Val>>::empty() && !s.en && !s.strict
    }

    open spec fn next(s: CW1, l: CWL1, t: CW1) -> bool {
        match l {
            CWL1::Meta { en, strict } => t == (CW1 { en, strict, ..s }),
            CWL1::Write { q } => !strict_on(s.en, s.strict) && pre(s, q) && t == apply(s, q),
            CWL1::Refuse { q, why } => !(why is Dup) && t == s,
        }
    }
}

pub open spec fn noempty(m: Map<int, Val>) -> bool { forall|k: int| #[trigger] m.contains_key(k) ==> m[k] != Val::Empty }
pub open spec fn inv1(s: CW1) -> bool {
    &&& s.qual.dom() == s.edges
    &&& forall|e: (int, int)| #[trigger] s.qual.contains_key(e) ==> noempty(s.qual[e])
    &&& forall|n: int| #[trigger] s.props.contains_key(n) ==> noempty(s.props[n])
}

pub proof fn lemma_apply_safe(s: CW1, q: Q)
    requires inv1(s),
    ensures inv1(apply(s, q)),
{
    let t = apply(s, q);
    match q {
        Q::CreateLit { ns, es } => {
            assert(t.qual.dom() =~= t.edges);
            assert forall|e: (int, int)| #[trigger] t.qual.contains_key(e) implies noempty(t.qual[e]) by {
                if s.edges.contains(e) { assert(s.qual.contains_key(e)); }
            }
        }
        Q::MergeCopy { rows } => {
            assert(t.qual.dom() =~= t.edges);
            assert forall|e: (int, int)| #[trigger] t.qual.contains_key(e) implies noempty(t.qual[e]) by {
                if s.edges.contains(e) { assert(s.qual.contains_key(e)); }
                else if s.props.contains_key(e.0) { assert(noempty(s.props[e.0])); }
            }
        }
        Q::SetProp { n, k, v } => {
            if s.nodes.contains(n) {
                assert forall|m: int| #[trigger] t.props.contains_key(m) implies noempty(t.props[m]) by {
                    if m != n { assert(s.props.contains_key(m)); }
                    else {
                        let p = set_prop(pm(s.props, n), k, v);
                        assert forall|j: int| #[trigger] p.contains_key(j) implies p[j] != Val::Empty by {
                            if j != k { assert(pm(s.props, n).contains_key(j)); if s.props.contains_key(n) { assert(noempty(s.props[n])); } }
                        }
                    }
                }
            }
        }
    }
}

proof fn lemma_l1_safe(s: CW1, l: CWL1, t: CW1)
    requires inv1(s), CwL1::next(s, l, t),
    ensures inv1(t),
{
    match l { CWL1::Write { q } => lemma_apply_safe(s, q), _ => {} }
}

impl SafeContract for CwL1 {
    open spec fn inv(s: CW1) -> bool { inv1(s) }
    proof fn init_safe(s: CW1) { assert(s.qual.dom() =~= s.edges); }
    proof fn step_safe(s: CW1, l: CWL1, t: CW1) { lemma_l1_safe(s, l, t); }
}

/// CYP-X7.2 / ledger-api.md:82-92: while the ledger is enabled in strict mode, no step but a ledger change by its owner
/// changes the graph.
pub proof fn theorem_strict_mode_refuses_every_write(s: CW1, l: CWL1, t: CW1)
    requires strict_on(s.en, s.strict), CwL1::next(s, l, t), !(l is Meta),
    ensures t == s,
{
}

/// CYP-I6.4: a refused query writes nothing; and it is never refused because a relationship it creates exists.
pub proof fn theorem_refused_query_writes_nothing(s: CW1, q: Q, why: Why, t: CW1)
    requires CwL1::next(s, CWL1::Refuse { q, why }, t),
    ensures t == s, !(why is Dup),
{
}

/// KNOWN_ISSUES.md:25-31: creating relationships that all exist (between literal endpoints) adds no relationship.
pub proof fn theorem_existing_relationship_create_adds_nothing(s: CW1, ns: Set<int>, es: Set<(int, int)>, t: CW1)
    requires inv1(s), CwL1::next(s, CWL1::Write { q: Q::CreateLit { ns, es } }, t), es.subset_of(s.edges),
    ensures t.edges == s.edges, t.qual == s.qual,
{
    assert(t.edges =~= s.edges);
    assert(t.qual =~= s.qual);
}

/// CYP-B6.8: each relationship the MERGE creates carries its own row's node's properties.
pub proof fn theorem_merge_copies_each_rows_node(s: CW1, rows: Set<(int, int)>, t: CW1, e: (int, int))
    requires CwL1::next(s, CWL1::Write { q: Q::MergeCopy { rows } }, t), rows.contains(e),
    ensures t.edges.contains(e), t.qual[e] == pm(s.props, e.0),
{
}

/// CYP-B6.9: SET n.k = null leaves k out of keys(n).
pub proof fn theorem_null_set_removes_the_key(s: CW1, n: int, k: int, t: CW1)
    requires CwL1::next(s, CWL1::Write { q: Q::SetProp { n, k, v: None } }, t), s.nodes.contains(n),
    ensures !t.props[n].contains_key(k),
{
}

} // verus!
