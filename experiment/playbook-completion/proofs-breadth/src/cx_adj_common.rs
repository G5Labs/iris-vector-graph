//! Concrete states shared by the module 04 counterexamples (compiled only with a module 04 control): graph 0,
//! source 0 with one committed edge x0, a second edge x1, and a Degree call that reads the generation, misses the
//! cache and gets its probe granted.
use vstd::prelude::*;
use crate::adj_l1::*;
use crate::adj_l2::*;

verus! {

pub open spec fn k0() -> KS { (0, 0) }
pub open spec fn x0() -> X { (0, 0, 0) }
pub open spec fn x1() -> X { (0, 0, 1) }
pub open spec fn s0() -> Set<X> { Set::empty().insert(x0()) }
pub open spec fn s01() -> Set<X> { s0().insert(x1()) }
pub open spec fn gconst(v: nat) -> spec_fn(KS) -> nat { |k: KS| v }

pub open spec fn a_init(v: nat) -> AS2 {
    AS2 { out: s0(), gen: gconst(v), degc: Map::empty(), nolock: Set::empty(), w: Map::empty(), r: Map::empty(),
          e: Map::empty(), b: None, rows: s0() }
}
pub open spec fn rp0(v: nat) -> RP { RP { k: k0(), tgen: v, got: false, n: 0, ph: RPh::Gen } }
pub open spec fn r1(v: nat) -> AS2 { setr(a_init(v), 0, rp0(v)) }
pub open spec fn r2(v: nat) -> AS2 { setr(r1(v), 0, RP { ph: RPh::Looked, ..r1(v).r[0] }) }
pub open spec fn r3(v: nat) -> AS2 { setr(r2(v), 0, RP { ph: RPh::Probed, got: !held(r2(v), 0), ..r2(v).r[0] }) }

pub proof fn lemma_degs()
    ensures deg(Set::<X>::empty(), k0()) == 0, deg(s0(), k0()) == 1, deg(s01(), k0()) == 2,
{
    let f = of_src(k0());
    assert(Set::<X>::empty().filter(f) =~= Set::<X>::empty());
    assert(s0().filter(f) =~= s0());
    assert(s01().filter(f) =~= s01());
    assert(!Set::<X>::empty().contains(x0()));
    assert(!s0().contains(x1()));
}

/// A Degree call starts, misses the cache and has its probe granted (nothing holds ^IVG.AdjW(0)).
pub proof fn lemma_reader_opens(v: nat)
    ensures
        init2(a_init(v)),
        step2(a_init(v), AL2::RStart { p: 0, k: k0() }, r1(v)),
        step2(r1(v), AL2::RLookup { p: 0, k: k0(), hit: None }, r2(v)),
        step2(r2(v), AL2::RProbe { p: 0 }, r3(v)),
        r3(v).r[0] == (RP { k: k0(), tgen: v, got: true, n: 0, ph: RPh::Probed }),
        r3(v).w == Map::<nat, WP>::empty(), r3(v).e == Map::<nat, EP>::empty(), r3(v).b is None,
        r3(v).out == s0(), r3(v).rows == s0(), r3(v).degc == Map::<KS, (nat, nat)>::empty(),
        r3(v).nolock == Set::<int>::empty(), r3(v).gen == gconst(v),
        r3(v).r.dom() == set![0nat],
{
    assert((a_init(v).gen)(k0()) == v);
    assert(!a_init(v).r.contains_key(0));
    assert(step2(a_init(v), AL2::RStart { p: 0, k: k0() }, r1(v)));
    assert(!r1(v).degc.contains_key(k0()));
    assert(step2(r1(v), AL2::RLookup { p: 0, k: k0(), hit: None }, r2(v)));
    assert(!held(r2(v), 0)) by {
        assert forall|p: nat| !r2(v).w.contains_key(p) by {}
        assert forall|q: nat| !r2(v).e.contains_key(q) by {}
    }
    assert(step2(r2(v), AL2::RProbe { p: 0 }, r3(v)));
    assert(r3(v).r.dom() =~= set![0nat]);
}

} // verus!
