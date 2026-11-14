//! The nread L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::nread_l1::*;
use crate::nread_l2::*;

verus! {

pub open spec fn r0(held: Set<int>, idx_e: bool, idx_l: bool, crc: Map<int, int>) -> NR2 {
    NR2 { rels: Set::empty(), snap: None, held, chk: Set::empty(), labs: Set::empty(), kg: Set::empty(), idx_e, idx_l, crc }
}
pub open spec fn p_tbegin(s: NR2) -> NR2 { NR2 { snap: Some(s.rels), ..s } }
pub open spec fn p_tadd(s: NR2, e: int) -> NR2 { NR2 { rels: s.rels.insert(e), ..s } }
pub open spec fn p_tcommit(s: NR2) -> NR2 { NR2 { snap: None, ..s } }
pub open spec fn p_trollback(s: NR2) -> NR2 { NR2 { rels: s.snap->Some_0, snap: None, ..s } }
pub open spec fn p_revoke(s: NR2, u: int) -> NR2 { NR2 { held: s.held.remove(u), ..s } }
pub open spec fn p_lwrite(s: NR2, n: int, l: int) -> NR2 {
    NR2 { labs: s.labs.insert((n, l)), kg: if s.idx_l || !s.idx_e { s.kg.insert((n, l)) } else { s.kg }, ..s }
}

pub proof fn lemma_r_steps(s: NR2, e: int, u: int, p: int, n: int, l: int)
    ensures
        forall|h: Set<int>, a: bool, b: bool, c: Map<int, int>| #[trigger] init2(r0(h, a, b, c)),
        s.snap is None ==> step2(s, NRL2::TBegin, p_tbegin(s)),
        s.snap is Some ==> step2(s, NRL2::TAdd { e }, p_tadd(s, e)),
        s.snap is Some ==> step2(s, NRL2::TCommit, p_tcommit(s)),
        s.snap is Some ==> step2(s, NRL2::TRollback, p_trollback(s)),
        step2(s, NRL2::Revoke { u }, p_revoke(s, u)),
        step2(s, NRL2::LWrite { n, l }, p_lwrite(s, n, l)),
        run_ok(s, p, u) ==> step2(s, NRL2::Run { p, u, ans: interp2(s) }, after_run(s, p, u)),
        gate(s) && run_ok(s, p, u) ==> step2(s, NRL2::RunLabels { p, u, ans: s.kg }, after_run(s, p, u)),
        step2(s, NRL2::SqlRead { u, ans: if s.held.contains(u) { Some(pairs(s.rels)) } else { None } }, s),
{
}

} // verus!
