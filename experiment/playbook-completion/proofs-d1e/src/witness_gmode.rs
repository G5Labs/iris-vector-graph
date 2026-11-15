//! Non-vacuity of the reviewed multigraph-mode model (compiled without its controls): two parallel edges in
//! multigraph mode; turning the mode off is refused while they are parallel; after a per-edge delete it is accepted,
//! and while it holds the lock no writer reads the mode; afterwards the single-edge writer and a mode-off Cypher
//! CREATE are refused on the lone edge at ekey 1, so the graph keeps one edge of the triple.
use vstd::prelude::*;
use crate::gmode_l2::*;
use crate::gmode_runs::*;

verus! {

pub open spec fn w1() -> MS2 { p_on(m0(), 0) }
pub open spec fn w2() -> MS2 { p_cymode(w1(), 0) }
pub open spec fn w3() -> MS2 { p_par(w2(), 0, 0) }
pub open spec fn w4() -> MS2 { p_cymode(w3(), 0) }
pub open spec fn w5() -> MS2 { p_par(w4(), 0, 1) }
pub open spec fn w6() -> MS2 { p_del(w5(), 0) }
pub open spec fn w7() -> MS2 { p_count(w6(), 0) }
pub open spec fn w8() -> MS2 { p_kill(w7(), 0) }
pub open spec fn w9() -> MS2 { p_cymode(w8(), 1) }
pub open spec fn w10() -> MS2 { p_one(w9(), 1) }

pub proof fn witness_gmode()
    ensures
        init2(m0()),
        step2(m0(), ML2::SetOn { e: 0 }, w1()),
        step2(w1(), ML2::CyMode { e: 0 }, w2()),
        step2(w2(), ML2::CyInsertPar { e: 0, k: 0 }, w3()),
        step2(w3(), ML2::CyMode { e: 0 }, w4()),
        step2(w4(), ML2::CyInsertPar { e: 0, k: 1 }, w5()),
        w5().rows.len() == 2,
        step2(w5(), ML2::SetOffCount { e: 0, ok: false }, w5()),
        step2(w5(), ML2::Delete { k: 0 }, w6()),
        step2(w6(), ML2::SetOffCount { e: 0, ok: true }, w7()),
        forall|t: MS2| !#[trigger] step2(w7(), ML2::CyMode { e: 1 }, t),
        step2(w7(), ML2::SetOffKill { e: 0 }, w8()),
        step2(w8(), ML2::Single { e: 0, added: false }, w8()),
        step2(w8(), ML2::CyMode { e: 1 }, w9()),
        step2(w9(), ML2::CyInsertOne { e: 1, added: false }, w10()),
        !w10().gm && w10().rows.len() == 1,
{
    lemma_m_steps(m0(), 0, 0);
    lemma_m_steps(w1(), 0, 0);
    lemma_m_steps(w2(), 0, 0);
    assert(w3().rows =~= Set::empty().insert(0int));
    lemma_m_steps(w3(), 0, 1);
    lemma_m_steps(w4(), 0, 1);
    assert(w5().rows =~= Set::empty().insert(0int).insert(1int));
    assert(w5().shared =~= Set::<int>::empty());
    lemma_m_steps(w5(), 0, 0);
    assert(w6().rows =~= Set::empty().insert(1int));
    assert(w6().shared =~= Set::<int>::empty());
    lemma_m_steps(w6(), 0, 0);
    lemma_m_steps(w7(), 0, 0);
    lemma_m_steps(w8(), 0, 0);
    lemma_m_steps(w8(), 1, 0);
    assert(p_single(w8()) == w8());
    lemma_m_steps(w9(), 1, 0);
    assert(w10().rows =~= Set::empty().insert(1int));
}

} // verus!
