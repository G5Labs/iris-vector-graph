//! The cyw L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::cyw_l1::*;
use crate::cyw_l2::*;

verus! {

pub open spec fn c0() -> CW2 {
    CW2 { nodes: Set::empty(), edges: Set::empty(), qual: Map::empty(), props: Map::empty(), en: false, strict: false,
          cache: None, fresh: false }
}
pub open spec fn p_meta(s: CW2, en: bool, strict: bool) -> CW2 { CW2 { en, strict, ..s } }
pub open spec fn p_exec(s: CW2, q: Q, pok: bool, top: (int, int)) -> CW2 { apply2(guarded(s, pok), q, top) }

pub proof fn lemma_c_steps(s: CW2, q: Q, pok: bool, top: (int, int), en: bool, strict: bool, why: Why)
    ensures
        init2(c0()),
        step2(s, CWL2::Meta { en, strict }, p_meta(s, en, strict)),
        step2(s, CWL2::Tick, CW2 { fresh: false, ..s }),
        passes(s, pok) && pre2(s, q, top) ==> step2(s, CWL2::Exec { q, pok, top }, p_exec(s, q, pok, top)),
        why is Env ==> step2(s, CWL2::Refuse { q, pok, why }, guarded(s, pok)),
        why is Dup && dup_raises(s, q) ==> step2(s, CWL2::Refuse { q, pok, why }, guarded(s, pok)),
        why is Strict && guard_meta(s, pok) is Some && strict_on(guard_meta(s, pok)->Some_0.0, guard_meta(s, pok)->Some_0.1)
            ==> step2(s, CWL2::Refuse { q, pok, why }, guarded(s, pok)),
        why is Unavailable && guard_meta(s, pok) is None ==> step2(s, CWL2::Refuse { q, pok, why }, guarded(s, pok)),
{
}

} // verus!
