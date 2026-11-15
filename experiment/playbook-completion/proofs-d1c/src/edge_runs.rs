//! The edge L2 machine's steps as functions (valid under every feature: each mirrors its `step2` arm), used by the
//! witness and the counterexamples.
use vstd::prelude::*;
use crate::edge_l1::*;
use crate::edge_l2::*;

verus! {

pub open spec fn e0(reg: Set<GP>) -> ES2 {
    ES2 { rows: Map::empty(), out: Set::empty(), tout: Set::empty(), tin: Set::empty(), nodes: Set::empty(), reg, pend: Map::empty() }
}

pub open spec fn p_node(s: ES2, nk: NK) -> ES2 { ES2 { nodes: s.nodes.insert(nk), ..s } }

pub open spec fn r_cinsert(s: ES2, k: K) -> Option<bool> {
    if !s.rows.contains_key(k) { Some(true) } else if fc0301() { None } else if s.rows[k] is Marked { Some(true) } else { Some(false) }
}
pub open spec fn p_cinsert(s: ES2, c: nat, k: K, q: Q) -> ES2 {
    if !s.rows.contains_key(k) {
        ES2 { rows: s.rows.insert(k, q), out: s.out.insert(k), nodes: add_ends(s.nodes, k), ..s }
    } else if fc0301() {
        ES2 { nodes: add_ends(s.nodes, k), pend: s.pend.insert(c, PA { k, q }), ..s }
    } else if s.rows[k] is Marked {
        ES2 { rows: s.rows.insert(k, q), nodes: add_ends(s.nodes, k), ..s }
    } else {
        ES2 { nodes: add_ends(s.nodes, k), ..s }
    }
}

pub open spec fn a_cadopt(s: ES2, c: nat) -> bool { s.rows.contains_key(s.pend[c].k) && s.rows[s.pend[c].k] is Marked }
pub open spec fn p_cadopt(s: ES2, c: nat) -> ES2 {
    if a_cadopt(s, c) { ES2 { rows: s.rows.insert(s.pend[c].k, s.pend[c].q), pend: s.pend.remove(c), ..s } }
    else { ES2 { pend: s.pend.remove(c), ..s } }
}

pub open spec fn p_sstore(s: ES2, k: K, q: Q) -> ES2 {
    if !s.rows.contains_key(k) {
        ES2 { rows: s.rows.insert(k, q), out: s.out.insert(k), nodes: add_ends(s.nodes, k), ..s }
    } else if !f0304() && s.rows[k] is Marked {
        ES2 { rows: s.rows.insert(k, q), nodes: add_ends(s.nodes, k), ..s }
    } else {
        ES2 { nodes: add_ends(s.nodes, k), ..s }
    }
}

pub open spec fn p_ddelete(s: ES2, k: K) -> ES2 {
    if !hd0302() && has_ts(s.tout, k) && structural(s.reg, k) { ES2 { rows: s.rows.insert(k, Q::Marked), out: s.out.insert(k), ..s } }
    else { ES2 { rows: s.rows.remove(k), out: s.out.remove(k), ..s } }
}

pub open spec fn p_tinsert(s: ES2, k: K, ts: int) -> ES2 {
    if s.tout.contains(Ev { k, ts }) {
        s
    } else if structural(s.reg, k) && !s.out.contains(k) {
        ES2 { tout: s.tout.insert(Ev { k, ts }), tin: s.tin.insert(Ev { k, ts }), rows: s.rows.insert(k, Q::Marked),
              out: s.out.insert(k), nodes: add_ends(s.nodes, k), ..s }
    } else {
        ES2 { tout: s.tout.insert(Ev { k, ts }), tin: s.tin.insert(Ev { k, ts }), ..s }
    }
}

pub open spec fn p_trefuse(s: ES2, k: K, ts: int) -> ES2 {
    if fc0501() { ES2 { tout: s.tout.insert(Ev { k, ts }), tin: s.tin.insert(Ev { k, ts }), nodes: add_ends(s.nodes, k), ..s } }
    else { s }
}

pub open spec fn p_tdelete(s: ES2, k: K, ts: int) -> ES2 {
    if !has_ts(s.tout.remove(Ev { k, ts }), k) && s.rows.contains_key(k) && marked(s.rows[k]) {
        ES2 { tout: s.tout.remove(Ev { k, ts }), tin: s.tin.remove(Ev { k, ts }), rows: s.rows.remove(k), out: s.out.remove(k), ..s }
    } else {
        ES2 { tout: s.tout.remove(Ev { k, ts }), tin: s.tin.remove(Ev { k, ts }), ..s }
    }
}

pub open spec fn p_purgeraw(s: ES2, g: int, end: int) -> ES2 {
    ES2 { tout: purge_ts(s.tout, g, end), tin: purge_ts(s.tin, g, end), rows: purge_rows(s, g, purge_ts(s.tout, g, end)),
          out: s.out.filter(|k: K| !retired(s, g, purge_ts(s.tout, g, end), k)), ..s }
}

pub open spec fn p_tpurge(s: ES2) -> ES2 {
    ES2 { tout: Set::empty(), tin: Set::empty(),
          rows: if f0507() { s.rows } else { unmarked_rows(s.rows) },
          out: if f0507() { s.out } else { s.out.filter(|k: K| !(s.rows.contains_key(k) && marked(s.rows[k]))) }, ..s }
}

pub open spec fn p_enodes(s: ES2, g: int, sel: Set<int>) -> ES2 {
    ES2 { nodes: erase_nodes(s.nodes, g, ids_of(s, g, sel)), rows: erase_rows(s.rows, g, ids_of(s, g, sel)),
          out: s.out.filter(|k: K| !hit(g, ids_of(s, g, sel), k)),
          tout: erase_ts(s.tout, g, ids_of(s, g, sel)), tin: erase_ts(s.tin, g, ids_of(s, g, sel)), ..s }
}

pub proof fn lemma_p_node(s: ES2, nk: NK) ensures step2(s, EL2::CreateNode { nk }, p_node(s, nk)) {}
pub proof fn lemma_p_cinsert(s: ES2, c: nat, k: K, q: Q)
    requires !(q is Marked), !s.pend.contains_key(c),
    ensures step2(s, EL2::CInsert { c, k, q, res: r_cinsert(s, k) }, p_cinsert(s, c, k, q)) {}
pub proof fn lemma_p_cadopt(s: ES2, c: nat)
    requires s.pend.contains_key(c),
    ensures step2(s, EL2::CAdopt { c, k: s.pend[c].k, ans: a_cadopt(s, c) }, p_cadopt(s, c)) {}
pub proof fn lemma_p_sstore(s: ES2, k: K, q: Q) requires !(q is Marked) ensures step2(s, EL2::SStore { k, q }, p_sstore(s, k, q)) {}
pub proof fn lemma_p_ddelete(s: ES2, k: K) ensures step2(s, EL2::DDelete { k }, p_ddelete(s, k)) {}
pub proof fn lemma_p_tinsert(s: ES2, k: K, ts: int) ensures step2(s, EL2::TInsert { k, ts }, p_tinsert(s, k, ts)) {}
pub proof fn lemma_p_trefuse(s: ES2, k: K, ts: int)
    requires !s.tout.contains(Ev { k, ts }), structural(s.reg, k), !s.out.contains(k),
    ensures step2(s, EL2::TRefuse { k, ts }, p_trefuse(s, k, ts)) {}
pub proof fn lemma_p_tdelete(s: ES2, k: K, ts: int)
    requires s.tout.contains(Ev { k, ts }),
    ensures step2(s, EL2::TDelete { k, ts }, p_tdelete(s, k, ts)) {}
pub proof fn lemma_p_purgeraw(s: ES2, g: int, end: int) ensures step2(s, EL2::PurgeRaw { g, end }, p_purgeraw(s, g, end)) {}
pub proof fn lemma_p_tpurge(s: ES2) ensures step2(s, EL2::TPurge, p_tpurge(s)) {}
pub proof fn lemma_p_enodes(s: ES2, g: int, sel: Set<int>) ensures step2(s, EL2::ENodes { g, sel }, p_enodes(s, g, sel)) {}

/// The triples of the runs: k1 = (graph 0, 1 -2-> 3), structural; k2 = (graph 0, 1 -9-> 4), with predicate 9
/// registered temporal-only in graph 0 by `reg9`.
pub open spec fn k1() -> K { K { g: 0, s: 1, p: 2, o: 3 } }
pub open spec fn k2() -> K { K { g: 0, s: 1, p: 9, o: 4 } }
pub open spec fn reg9() -> Set<GP> { Set::empty().insert(GP { g: 0, p: 9 }) }

} // verus!
