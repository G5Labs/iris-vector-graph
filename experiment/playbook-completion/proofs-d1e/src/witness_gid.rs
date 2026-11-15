//! Non-vacuity of the reviewed names-and-readers model (compiled without its controls): one id in two graphs; the
//! reserved name is refused; the default-graph label reader answers the default graph's node with its own labels and
//! not the named graph's; the all-graph id helper answers the id once; the property keys of a label are the keys of
//! its own graph's nodes; a named graph is erased and leaves the default graph's node.
use vstd::prelude::*;
use crate::gid_l1::*;
use crate::gid_l2::*;
use crate::gid_runs::*;

verus! {

pub open spec fn w1() -> GS2 { add2(g0(), 1, 1, 10, 20) }
pub open spec fn w2() -> GS2 { add2(w1(), 0, 1, 11, 21) }
pub open spec fn w3() -> GS2 { erase2(w2(), 1) }
pub open spec fn hd() -> Hyd { Hyd { labels: Set::empty().insert(11int), props: Set::empty().insert(21int) } }

pub proof fn witness_gid()
    ensures
        init2(g0()),
        step2(g0(), GL2::CreateNode { g: 1, n: 1, l: 10, k: 20, ok: true }, w1()),
        step2(w1(), GL2::CreateNode { g: 0, n: 1, l: 11, k: 21, ok: true }, w2()),
        forall|t: GS2| !#[trigger] step2(w2(), GL2::CreateNode { g: -1, n: 2, l: 10, k: 20, ok: true }, t),
        step2(w2(), GL2::NodesByLabel { l: 10, ans: Map::empty() }, w2()),
        step2(w2(), GL2::NodesByLabel { l: 11, ans: Map::empty().insert(1int, hd()) }, w2()),
        step2(w2(), GL2::IdsByLabel { l: 10, ids: Set::empty().insert(1int) }, w2()),
        step2(w2(), GL2::PropertyKeys { l: 11, keys: Set::empty().insert(21int) }, w2()),
        step2(w2(), GL2::EraseGraph { g: 1 }, w3()),
        w3().nodes_t.contains(NK { g: 0, n: 1 }) && !w3().nodes_t.contains(NK { g: 1, n: 1 }),
{
    lemma_g_steps(g0(), 1, 1, 10, 20);
    lemma_g_steps(w1(), 0, 1, 11, 21);
    lemma_g_steps(w2(), 1, 1, 10, 20);
    let s = w2();
    assert(s.labels_t.contains(LK { g: 1, n: 1, l: 10 }));
    assert(s.labels_t.contains(LK { g: 0, n: 1, l: 11 }));
    assert(s.props_t.contains(PK { g: 0, n: 1, k: 21 }));
    assert forall|n: int| !(Map::<int, Hyd>::empty().contains_key(n) <==> ids_of(s, 10, n) && kept(s, n)) == false by {
        assert(!s.labels_t.contains(LK { g: 0, n, l: 10 }));
    }
    assert(bylabel2(s, 10, Map::empty()));
    let m = Map::<int, Hyd>::empty().insert(1int, hd());
    assert forall|n: int| m.contains_key(n) <==> ids_of(s, 11, n) && kept(s, n) by {
        if n == 1 { assert(kept(s, 1)); }
    }
    assert forall|x: int| hd().labels.contains(x) <==> s.labels_t.contains(LK { g: 0, n: 1, l: x }) by {}
    assert forall|k: int| hd().props.contains(k) <==> s.props_t.contains(PK { g: 0, n: 1, k }) by {}
    assert(hyd2(s, 1, m[1]));
    assert(bylabel2(s, 11, m));
    assert forall|n: int| Set::empty().insert(1int).contains(n) <==> (exists|g: int| s.labels_t.contains(LK { g, n, l: 10 })) by {
        if n == 1 { assert(s.labels_t.contains(LK { g: 1, n: 1, l: 10 })); }
    }
    assert forall|k: int| Set::empty().insert(21int).contains(k) <==>
        (exists|g: int, n: int| s.labels_t.contains(LK { g, n, l: 11 }) && s.props_t.contains(PK { g, n, k })) by {
        if k == 21 { assert(s.labels_t.contains(LK { g: 0, n: 1, l: 11 }) && s.props_t.contains(PK { g: 0, n: 1, k: 21 })); }
    }
    assert(w3().nodes_t.contains(NK { g: 0, n: 1 }));
}

} // verus!
