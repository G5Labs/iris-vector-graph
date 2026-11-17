// product 3eaa79cf: materialize_inference and retract_inference (iris_vector_graph/_engine/schema.py) over one graph's
//   rdf_edges, with create_edge as the competing writer. A row is (s, p, o) with a marker: asserted, or the qualifier
//   {"inferred":true}. Materialize reads asserted rows only (qualifiers NOT LIKE '%"inferred":%'), derives, and inserts
//   each derived triple that has no row yet, marked inferred. create_edge leaves an existing triple alone and answers
//   False (multigraph off). Retract deletes every inferred row of the graph.
//   Domain of the derivation: subclass and subproperty chains of at most two links (tc composes once); the product's
//   closure is a fixpoint, equal on that domain.
use vstd::prelude::*;
verus! {

pub type T = (int, int, int);
pub open spec fn SUB() -> int { 1 }
pub open spec fn SUBP() -> int { 2 }
pub open spec fn TYPE() -> int { 3 }
pub open spec fn DOM() -> int { 4 }
pub open spec fn RNG() -> int { 5 }
pub open spec fn reserved(p: int) -> bool { 1 <= p <= 5 }

/// rows: triple -> None (no row), Some(false) (asserted), Some(true) (qualifier {"inferred":true})
pub struct Rows { pub f: spec_fn(T) -> Option<bool> }

pub open spec fn present(e: Rows, t: T) -> bool { (e.f)(t) is Some }
/// An asserted row.
pub open spec fn arow(e: Rows, t: T) -> bool { (e.f)(t) == Some(false) }
pub open spec fn rel(e: Rows, p: int, x: int, y: int) -> bool { arow(e, (x, p, y)) }
pub open spec fn tc(e: Rows, p: int, x: int, y: int) -> bool {
    rel(e, p, x, y) || exists|b: int| rel(e, p, x, b) && rel(e, p, b, y) && x != y
}

/// As-built rules over asserted rows: subclass and subproperty closures; rdf:type from an asserted type and the subclass
/// closure; rdf:type from domain and range over asserted non-schema edges. No rule propagates an edge along a
/// subproperty (rdfs7), and a type derived from domain or range is not lifted along the subclass closure.
pub open spec fn derives(e: Rows, t: T) -> bool {
    (t.1 == SUB() && tc(e, SUB(), t.0, t.2))
    || (t.1 == SUBP() && tc(e, SUBP(), t.0, t.2))
    || (t.1 == TYPE() && exists|c: int| arow(e, (t.0, TYPE(), c)) && tc(e, SUB(), c, t.2))
    || (t.1 == TYPE() && exists|p: int, o: int| !reserved(p) && arow(e, (p, DOM(), t.2)) && arow(e, (t.0, p, o)))
    || (t.1 == TYPE() && exists|p: int, s: int| !reserved(p) && arow(e, (p, RNG(), t.2)) && arow(e, (s, p, t.0)))
}

pub open spec fn materialize(e: Rows) -> Rows {
    Rows { f: |t: T| if present(e, t) { (e.f)(t) } else if derives(e, t) { Some(true) } else { None } }
}
pub open spec fn create_edge(e: Rows, t: T) -> Rows {
    Rows { f: |u: T| if u == t && !present(e, t) { Some(false) } else { (e.f)(u) } }
}
pub open spec fn retract(e: Rows) -> Rows { Rows { f: |t: T| if arow(e, t) { Some(false) } else { None } } }
pub open spec fn rows2(a: T, b: T) -> Rows { Rows { f: |t: T| if t == a || t == b { Some(false) } else { None } } }
pub open spec fn rows3(a: T, b: T, c: T) -> Rows { Rows { f: |t: T| if t == a || t == b || t == c { Some(false) } else { None } } }

/// I9: retract keeps every asserted row and removes every inferred one.
pub proof fn theorem_retract_keeps_asserted(e: Rows, t: T)
    ensures present(retract(e), t) == arow(e, t),
{}

/// Derivation depends only on the asserted rows.
pub proof fn lemma_same_asserted(m: Rows, e: Rows, t: T)
    requires forall|u: T| #[trigger] arow(m, u) == arow(e, u),
    ensures derives(m, t) == derives(e, t),
{
    assert forall|p: int, x: int, y: int| #[trigger] tc(m, p, x, y) == tc(e, p, x, y) by {
        assert(arow(m, (x, p, y)) == arow(e, (x, p, y)));
        if tc(m, p, x, y) && !rel(m, p, x, y) {
            let b = choose|b: int| rel(m, p, x, b) && rel(m, p, b, y) && x != y;
            assert(arow(m, (x, p, b)) == arow(e, (x, p, b)) && arow(m, (b, p, y)) == arow(e, (b, p, y)));
            assert(rel(e, p, x, b) && rel(e, p, b, y) && x != y);
        }
        if tc(e, p, x, y) && !rel(e, p, x, y) {
            let b = choose|b: int| rel(e, p, x, b) && rel(e, p, b, y) && x != y;
            assert(arow(m, (x, p, b)) == arow(e, (x, p, b)) && arow(m, (b, p, y)) == arow(e, (b, p, y)));
            assert(rel(m, p, x, b) && rel(m, p, b, y) && x != y);
        }
    }
    if exists|c: int| arow(m, (t.0, TYPE(), c)) && tc(m, SUB(), c, t.2) {
        let c = choose|c: int| arow(m, (t.0, TYPE(), c)) && tc(m, SUB(), c, t.2);
        assert(arow(e, (t.0, TYPE(), c)) && tc(e, SUB(), c, t.2));
    }
    if exists|c: int| arow(e, (t.0, TYPE(), c)) && tc(e, SUB(), c, t.2) {
        let c = choose|c: int| arow(e, (t.0, TYPE(), c)) && tc(e, SUB(), c, t.2);
        assert(arow(m, (t.0, TYPE(), c)) && tc(m, SUB(), c, t.2));
    }
    if exists|p: int, o: int| !reserved(p) && arow(m, (p, DOM(), t.2)) && arow(m, (t.0, p, o)) {
        let (p, o) = choose|p: int, o: int| !reserved(p) && arow(m, (p, DOM(), t.2)) && arow(m, (t.0, p, o));
        assert(arow(e, (p, DOM(), t.2)) && arow(e, (t.0, p, o)));
    }
    if exists|p: int, o: int| !reserved(p) && arow(e, (p, DOM(), t.2)) && arow(e, (t.0, p, o)) {
        let (p, o) = choose|p: int, o: int| !reserved(p) && arow(e, (p, DOM(), t.2)) && arow(e, (t.0, p, o));
        assert(arow(m, (p, DOM(), t.2)) && arow(m, (t.0, p, o)));
    }
    if exists|p: int, s: int| !reserved(p) && arow(m, (p, RNG(), t.2)) && arow(m, (s, p, t.0)) {
        let (p, s) = choose|p: int, s: int| !reserved(p) && arow(m, (p, RNG(), t.2)) && arow(m, (s, p, t.0));
        assert(arow(e, (p, RNG(), t.2)) && arow(e, (s, p, t.0)));
    }
    if exists|p: int, s: int| !reserved(p) && arow(e, (p, RNG(), t.2)) && arow(e, (s, p, t.0)) {
        let (p, s) = choose|p: int, s: int| !reserved(p) && arow(e, (p, RNG(), t.2)) && arow(e, (s, p, t.0));
        assert(arow(m, (p, RNG(), t.2)) && arow(m, (s, p, t.0)));
    }
}

/// I2: a second materialize adds nothing (derivation reads asserted rows only, and materialize adds none).
pub proof fn theorem_rerun_adds_nothing(e: Rows, t: T)
    ensures (materialize(materialize(e)).f)(t) == (materialize(e).f)(t),
{
    let m = materialize(e);
    assert forall|u: T| #[trigger] arow(m, u) == arow(e, u) by {}
    lemma_same_asserted(m, e, t);
}

/// I3: a triple the user asserted before materializing survives retract.
pub proof fn theorem_asserted_first_survives(x: int, a: int, b: int)
    requires !reserved(x), !reserved(a), !reserved(b), a != b,
    ensures present(retract(materialize(create_edge(rows2((a, SUB(), b), (x, TYPE(), a)), (x, TYPE(), b)))), (x, TYPE(), b)),
{}

/// I4 (bug-str-105): the same triple asserted after materializing is a no-op on an inferred row, and retract deletes
/// it, although the user asserted it.
pub proof fn theorem_asserted_after_is_retracted(x: int, a: int, b: int)
    requires !reserved(x), !reserved(a), !reserved(b), a != b, x != a, x != b,
    ensures ({
        let e1 = materialize(rows2((a, SUB(), b), (x, TYPE(), a)));
        let t = (x, TYPE(), b);
        (e1.f)(t) == Some(true) && present(e1, t) && !present(retract(create_edge(e1, t)), t)
    }),
{
    let e0 = rows2((a, SUB(), b), (x, TYPE(), a));
    let t = (x, TYPE(), b);
    assert(arow(e0, (x, TYPE(), a)));
    assert(rel(e0, SUB(), a, b));
    assert(tc(e0, SUB(), a, b));
    assert(derives(e0, t));
    assert(!present(e0, t));
}

/// Every derived triple has a schema predicate: a user predicate is never derived (no rdfs7).
pub proof fn lemma_derived_predicates(e: Rows, t: T)
    requires derives(e, t),
    ensures t.1 == SUB() || t.1 == SUBP() || t.1 == TYPE(),
{}

/// I7 (bug-str-106): p subPropertyOf q and x p y never yield x q y.
pub proof fn theorem_no_subproperty_propagation(e: Rows, x: int, q: int, y: int)
    requires !reserved(q), !present(e, (x, q, y)),
    ensures !present(materialize(e), (x, q, y)),
{
    if derives(e, (x, q, y)) { lemma_derived_predicates(e, (x, q, y)); }
}

/// I10 (bug-str-106): a type derived from a domain is not lifted to the domain's superclass.
pub proof fn theorem_domain_type_not_lifted(p: int, d: int, f: int, x: int, y: int)
    requires !reserved(p), !reserved(d), !reserved(f), !reserved(x), !reserved(y), d != f, x != p, x != d,
    ensures derives(rows3((p, DOM(), d), (d, SUB(), f), (x, p, y)), (x, TYPE(), d)),
        !derives(rows3((p, DOM(), d), (d, SUB(), f), (x, p, y)), (x, TYPE(), f)),
{
    let e0 = rows3((p, DOM(), d), (d, SUB(), f), (x, p, y));
    assert(arow(e0, (p, DOM(), d)) && arow(e0, (x, p, y)));
    assert(forall|c: int| !arow(e0, (x, TYPE(), c)));
    assert(forall|q: int| !arow(e0, (q, DOM(), f)));
    assert(forall|q: int| !arow(e0, (q, RNG(), f)));
}

}
