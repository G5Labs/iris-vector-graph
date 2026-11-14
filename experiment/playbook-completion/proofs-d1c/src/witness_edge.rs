//! Non-vacuity of the reviewed edge model (compiled without the edge controls). Predicate 9 is temporal-only in graph
//! 0. A temporal edge of k1 asserts a marked row; create_edge adopts it (answer True); the triple's last temporal
//! delete keeps the explicit edge; a new timestamp; delete_edge reverts the row to marked (the triple keeps a
//! timestamp); purge_raw_before retracts it with its last timestamp; a refused temporal write writes nothing; a
//! temporal-only edge of k2 writes no row; the prefix erase of id 1 removes that edge too.
use vstd::prelude::*;
use crate::edge_l1::*;
use crate::edge_l2::*;
use crate::edge_runs::*;

verus! {

pub open spec fn e10() -> Ev { Ev { k: k1(), ts: 10 } }
pub open spec fn e20() -> Ev { Ev { k: k1(), ts: 20 } }
pub open spec fn e50() -> Ev { Ev { k: k2(), ts: 50 } }
pub open spec fn one() -> Set<int> { Set::empty().insert(1int) }
pub open spec fn w0() -> ES2 { e0(reg9()) }
pub open spec fn w1() -> ES2 { p_tinsert(w0(), k1(), 10) }
pub open spec fn w2() -> ES2 { p_cinsert(w1(), 0, k1(), Q::Plain) }
pub open spec fn w3() -> ES2 { p_tdelete(w2(), k1(), 10) }
pub open spec fn w4() -> ES2 { p_tinsert(w3(), k1(), 20) }
pub open spec fn w5() -> ES2 { p_ddelete(w4(), k1()) }
pub open spec fn w6() -> ES2 { p_purgeraw(w5(), 0, 30) }
pub open spec fn w7() -> ES2 { p_trefuse(w6(), k1(), 40) }
pub open spec fn w8() -> ES2 { p_tinsert(w7(), k2(), 50) }
pub open spec fn w9() -> ES2 { p_enodes(w8(), 0, one()) }

pub proof fn witness_edge()
    ensures
        init2(w0()),
        step2(w0(), EL2::TInsert { k: k1(), ts: 10 }, w1()),
        w1().rows[k1()] is Marked && w1().out.contains(k1()),
        step2(w1(), EL2::CInsert { c: 0, k: k1(), q: Q::Plain, res: Some(true) }, w2()),
        w2().rows[k1()] is Plain,
        step2(w2(), EL2::TDelete { k: k1(), ts: 10 }, w3()),
        w3().rows[k1()] is Plain && !w3().tout.contains(e10()),
        step2(w3(), EL2::TInsert { k: k1(), ts: 20 }, w4()),
        step2(w4(), EL2::DDelete { k: k1() }, w5()),
        w5().rows[k1()] is Marked && w5().out.contains(k1()),
        step2(w5(), EL2::PurgeRaw { g: 0, end: 30 }, w6()),
        !w6().rows.contains_key(k1()) && !w6().out.contains(k1()) && !w6().tout.contains(e20()),
        step2(w6(), EL2::TRefuse { k: k1(), ts: 40 }, w7()),
        w7() == w6(),
        step2(w7(), EL2::TInsert { k: k2(), ts: 50 }, w8()),
        w8().tout.contains(e50()) && !w8().rows.contains_key(k2()),
        step2(w8(), EL2::ENodes { g: 0, sel: one() }, w9()),
        !w9().tout.contains(e50()),
{
    lemma_p_tinsert(w0(), k1(), 10);
    assert(structural(w0().reg, k1()));
    assert(w1().rows.contains_key(k1()) && w1().rows[k1()] is Marked);
    assert(r_cinsert(w1(), k1()) == Some(true));
    lemma_p_cinsert(w1(), 0, k1(), Q::Plain);
    assert(w2().tout.contains(e10()));
    lemma_p_tdelete(w2(), k1(), 10);
    assert(w2().rows[k1()] is Plain);
    assert(!marked(w2().rows[k1()]));
    assert(w3().rows.contains_key(k1()) && w3().rows[k1()] is Plain);
    assert(w3().out.contains(k1()));
    lemma_p_tinsert(w3(), k1(), 20);
    assert(w4().tout.contains(e20()));
    assert(has_ts(w4().tout, k1()));
    lemma_p_ddelete(w4(), k1());
    assert(w5().tout.contains(e20()));
    assert(w5().tout =~= Set::<Ev>::empty().insert(e20()));
    lemma_p_purgeraw(w5(), 0, 30);
    assert(purge_ts(w5().tout, 0, 30) =~= Set::<Ev>::empty());
    assert(has_ts(w5().tout, k1()));
    assert(!has_ts(purge_ts(w5().tout, 0, 30), k1()));
    assert(retired(w5(), 0, purge_ts(w5().tout, 0, 30), k1()));
    assert(!w6().rows.contains_key(k1()));
    assert(!w6().out.contains(k1()));
    assert(w6().out =~= Set::<K>::empty());
    assert(w6().tout =~= Set::<Ev>::empty());
    lemma_p_trefuse(w6(), k1(), 40);
    lemma_p_tinsert(w7(), k2(), 50);
    assert(!structural(w7().reg, k2()));
    assert(w8().tout.contains(e50()));
    assert(!w8().rows.contains_key(k2())) by { assert(w6().rows =~= purge_rows(w5(), 0, purge_ts(w5().tout, 0, 30))); }
    lemma_p_enodes(w8(), 0, one());
    assert(endpoint(w8().tout, 0, 1));
    assert(ids_of(w8(), 0, one()).contains(1));
    assert(hit(0, ids_of(w8(), 0, one()), k2()));
}

} // verus!
