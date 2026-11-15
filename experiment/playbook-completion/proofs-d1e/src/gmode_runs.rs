//! The multigraph-mode L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::gmode_l2::*;

verus! {

pub open spec fn m0() -> MS2 {
    MS2 { rows: Set::empty(), gm: false, cache: Map::empty(), cy: Map::empty(), excl: false, shared: Set::empty(), counted: None }
}
pub open spec fn p_on(s: MS2, e: int) -> MS2 { MS2 { gm: true, cache: s.cache.remove(e), ..s } }
pub open spec fn p_count(s: MS2, e: int) -> MS2 { MS2 { counted: Some(e), excl: locked(), ..s } }
pub open spec fn p_kill(s: MS2, e: int) -> MS2 { MS2 { gm: false, counted: None, excl: false, cache: s.cache.remove(e), ..s } }
pub open spec fn p_cymode(s: MS2, e: int) -> MS2 {
    MS2 { cy: s.cy.insert(e, mode_read(s, e)), cache: if s.cache.contains_key(e) { s.cache } else { s.cache.insert(e, s.gm) },
          shared: if locked() { s.shared.insert(e) } else { s.shared }, ..s }
}
pub open spec fn p_par(s: MS2, e: int, k: int) -> MS2 { MS2 { rows: s.rows.insert(k), cy: s.cy.remove(e), shared: s.shared.remove(e), ..s } }
pub open spec fn p_one(s: MS2, e: int) -> MS2 {
    MS2 { rows: if guard_ok(s) { s.rows.insert(0) } else { s.rows }, cy: s.cy.remove(e), shared: s.shared.remove(e), ..s }
}
pub open spec fn p_single(s: MS2) -> MS2 { MS2 { rows: if guard_ok(s) { s.rows.insert(0) } else { s.rows }, ..s } }
pub open spec fn p_del(s: MS2, k: int) -> MS2 { MS2 { rows: s.rows.remove(k), ..s } }

pub proof fn lemma_m_steps(s: MS2, e: int, k: int)
    ensures
        step2(s, ML2::SetOn { e }, p_on(s, e)),
        s.counted is None && s.gm && (locked() ==> !s.excl && s.shared == Set::<int>::empty()) && s.rows.len() <= 1
            ==> step2(s, ML2::SetOffCount { e, ok: true }, p_count(s, e)),
        s.counted is None && s.gm && (locked() ==> !s.excl && s.shared == Set::<int>::empty()) && s.rows.len() > 1
            ==> step2(s, ML2::SetOffCount { e, ok: false }, s),
        s.counted == Some(e) ==> step2(s, ML2::SetOffKill { e }, p_kill(s, e)),
        !s.cy.contains_key(e) && (locked() ==> !s.excl) ==> step2(s, ML2::CyMode { e }, p_cymode(s, e)),
        s.cy.contains_key(e) && s.cy[e] && !s.rows.contains(k) ==> step2(s, ML2::CyInsertPar { e, k }, p_par(s, e, k)),
        s.cy.contains_key(e) && !s.cy[e] ==> step2(s, ML2::CyInsertOne { e, added: guard_ok(s) }, p_one(s, e)),
        step2(s, ML2::Single { e, added: guard_ok(s) }, p_single(s)),
        s.rows.contains(k) ==> step2(s, ML2::Delete { k }, p_del(s, k)),
{
}

} // verus!
