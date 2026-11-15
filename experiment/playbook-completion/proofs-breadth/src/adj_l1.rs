//! Module 04 (adjacency), L1: the abstract machine of the committed adjacency and its generation-validated degree
//! cache (ADR-0012, spec 248, Adj.cls:1-48 at pin 3eaa79cf).
//!
//! State: the committed adjacency `adj` (one entry per committed edge row, keyed (graph, source, entry)), one
//! generation per source `ep`, and the cache `cache[(graph, source)] = (generation, count)`.
//!
//! Business rules (transition rules; `inv1` is their consequence):
//! - **a cached degree is valid only for its source generation**: an entry is used (`Hit`) only when it carries the
//!   source's current generation, and a current entry holds the committed out-degree (ADJ-I5.9);
//! - **no stale degree becomes valid again after erase or rebuild**: generations never go back (`Advance` only
//!   raises them; no step lowers one), so an entry whose generation is behind stays behind (HD-0401 working answer);
//! - a committed write or erase changes the adjacency of a source only when no current entry exists for it (the
//!   writer and eraser move the generation first, ADR-0012:31);
//! - an entry is stored, restored or killed freely, but a stored or restored entry that carries the current
//!   generation must hold the committed degree (Adj.cls:34-39: stored only when no writer was in flight).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

/// `^KG("out", g, s, p, o)`: graph, source, out entry ((p, o) as one int).
pub type X = (int, int, int);
/// A source `(g, s)`: the subscripts of `^KG("gen", g, s)` and `^KG("degc", g, s, $c(1))`.
pub type KS = (int, int);

pub open spec fn ks(x: X) -> KS { (x.0, x.1) }

pub open spec fn of_src(k: KS) -> spec_fn(X) -> bool { |x: X| x.0 == k.0 && x.1 == k.1 }

/// The out-degree of source k in an adjacency (Adj.Count without parallel-edge multiplicity).
pub open spec fn deg(m: Set<X>, k: KS) -> nat { m.filter(of_src(k)).len() }

pub struct AS1 {
    pub adj: Set<X>,
    pub ep: spec_fn(KS) -> nat,
    pub cache: Map<KS, (nat, nat)>,
}

pub enum AL1 {
    /// A committed single-edge write (Adjacency.Put: add, Adjacency.Remove: remove).
    Commit { x: X, add: bool },
    /// A committed erase of one graph's adjacency (Eraser.EraseGraph -> Adjacency.RemoveGraph).
    EraseGraph { g: int },
    /// Generations move forward.
    Advance,
    /// Cache entries are stored, killed or restored.
    Cache,
    /// A Degree call answers a cached entry that carries the current generation.
    Hit { k: KS, n: nat },
}

pub open spec fn cur1(s: AS1, k: KS) -> bool { s.cache.contains_key(k) && s.cache[k].0 == (s.ep)(k) }

pub open spec fn entry_ok(adj: Set<X>, ep: spec_fn(KS) -> nat, k: KS, en: (nat, nat)) -> bool {
    en.0 <= ep(k) && (en.0 == ep(k) ==> en.1 == deg(adj, k))
}

pub struct AdjL1;

impl Contract for AdjL1 {
    type S = AS1;
    type L = AL1;

    open spec fn init(s: AS1) -> bool { s.cache == Map::<KS, (nat, nat)>::empty() }

    open spec fn next(s: AS1, l: AL1, t: AS1) -> bool {
        match l {
            AL1::Commit { x, add } =>
                !cur1(s, ks(x)) && t == AS1 { adj: if add { s.adj.insert(x) } else { s.adj.remove(x) }, ..s },
            AL1::EraseGraph { g } =>
                (forall|src: int| !#[trigger] cur1(s, (g, src)))
                && t == AS1 { adj: s.adj.filter(|y: X| y.0 != g), ..s },
            AL1::Advance =>
                (forall|k: KS| #[trigger] (t.ep)(k) >= (s.ep)(k)) && t == AS1 { ep: t.ep, ..s },
            AL1::Cache =>
                t == AS1 { cache: t.cache, ..s }
                && forall|k: KS| #[trigger] t.cache.contains_key(k) && !(s.cache.contains_key(k) && s.cache[k] == t.cache[k])
                    ==> entry_ok(s.adj, s.ep, k, t.cache[k]),
            AL1::Hit { k, n } => s.cache.contains_key(k) && s.cache[k] == ((s.ep)(k), n) && t == s,
        }
    }
}

/// Every cache entry is no newer than its source's generation, and a current entry holds the committed degree.
pub open spec fn inv1(s: AS1) -> bool {
    forall|k: KS| #[trigger] s.cache.contains_key(k) ==> entry_ok(s.adj, s.ep, k, s.cache[k])
}

pub proof fn lemma_deg_other(m: Set<X>, x: X, k: KS)
    requires ks(x) != k,
    ensures deg(m.insert(x), k) == deg(m, k), deg(m.remove(x), k) == deg(m, k),
{
    assert(m.insert(x).filter(of_src(k)) =~= m.filter(of_src(k)));
    assert(m.remove(x).filter(of_src(k)) =~= m.filter(of_src(k)));
}

pub proof fn lemma_deg_graph(m: Set<X>, g: int, k: KS)
    requires k.0 != g,
    ensures deg(m.filter(|y: X| y.0 != g), k) == deg(m, k),
{
    assert(m.filter(|y: X| y.0 != g).filter(of_src(k)) =~= m.filter(of_src(k)));
}

impl SafeContract for AdjL1 {
    open spec fn inv(s: AS1) -> bool { inv1(s) }

    proof fn init_safe(s: AS1) {}

    proof fn step_safe(s: AS1, l: AL1, t: AS1) {
        match l {
            AL1::Commit { x, add } => {
                assert forall|k: KS| #[trigger] t.cache.contains_key(k) implies entry_ok(t.adj, t.ep, k, t.cache[k]) by {
                    if k != ks(x) { lemma_deg_other(s.adj, x, k); }
                }
            }
            AL1::EraseGraph { g } => {
                assert forall|k: KS| #[trigger] t.cache.contains_key(k) implies entry_ok(t.adj, t.ep, k, t.cache[k]) by {
                    if k.0 != g { lemma_deg_graph(s.adj, g, k); } else { assert(!cur1(s, (g, k.1))); }
                }
            }
            AL1::Advance => {
                assert forall|k: KS| #[trigger] t.cache.contains_key(k) implies entry_ok(t.adj, t.ep, k, t.cache[k]) by {
                    assert((t.ep)(k) >= (s.ep)(k));
                    assert(entry_ok(s.adj, s.ep, k, s.cache[k]));
                }
            }
            AL1::Cache => {
                assert forall|k: KS| #[trigger] t.cache.contains_key(k) implies entry_ok(t.adj, t.ep, k, t.cache[k]) by {
                    if s.cache.contains_key(k) && s.cache[k] == t.cache[k] { assert(entry_ok(s.adj, s.ep, k, s.cache[k])); }
                }
            }
            AL1::Hit { k, n } => {}
        }
    }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// A cached degree is valid only for its source generation: a hit answers the committed out-degree.
pub proof fn theorem_hit_answers_committed_degree(s: AS1, k: KS, n: nat, t: AS1)
    requires inv1(s), AdjL1::next(s, AL1::Hit { k, n }, t),
    ensures n == deg(s.adj, k),
{
    assert(entry_ok(s.adj, s.ep, k, s.cache[k]));
}

/// A current entry holds the committed out-degree.
pub proof fn theorem_current_entry_is_committed_degree(s: AS1, k: KS)
    requires inv1(s), cur1(s, k),
    ensures s.cache[k].1 == deg(s.adj, k),
{
    assert(entry_ok(s.adj, s.ep, k, s.cache[k]));
}

/// Generations never go back.
pub proof fn theorem_generations_monotone(s: AS1, l: AL1, t: AS1)
    requires AdjL1::next(s, l, t),
    ensures forall|k: KS| #[trigger] (t.ep)(k) >= (s.ep)(k),
{
}

/// No stale degree becomes valid again: along any execution, a generation value behind a source's generation at
/// step i stays behind it at every later step, so an entry carrying it is never current again (whatever erase,
/// rebuild or restore happens in between).
pub proof fn theorem_stale_never_valid_again(states: Seq<AS1>, labels: Seq<AL1>, i: int, j: int, k: KS, e: nat)
    requires segment::<AdjL1>(states, labels), 0 <= i <= j < states.len(), e < (states[i].ep)(k),
    ensures e < (states[j].ep)(k), !(states[j].cache.contains_key(k) && states[j].cache[k].0 == e && cur1(states[j], k)),
    decreases j - i,
{
    if j > i {
        theorem_stale_never_valid_again(states, labels, i, j - 1, k, e);
        theorem_generations_monotone(states[j - 1], labels[j - 1], states[j]);
    }
}

} // verus!
