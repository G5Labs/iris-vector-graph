//! The system theorem, once for every composed design that discharges the system trait: in every reached state the
//! invariant axioms hold, every step from it keeps the action axioms, and the work can finish (AG EF).
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;
use crate::sys::*;
use crate::axioms::*;
use crate::progress::*;

verus! {

pub open spec fn all_invariant_axioms(t: SS) -> bool {
    law_ax04(t) && law_ax06(t) && law_ax07(t) && law_ax08(t) && law_ax10(t) && law_ax11m(t)
}

pub proof fn theorem_sys<O: SysObject>(s0: SS, ls: Seq<SA>, t: SS)
    requires reached::<SysM<O>>(s0, ls, t),
    ensures
        all_invariant_axioms(t),
        law_ax14::<O>(t),
        forall|a: SA| #[trigger] sys_step::<O>(t, a) is Some ==> law_ax02(t, a, sys_step::<O>(t, a)->0)
            && law_ax03(t, a, sys_step::<O>(t, a)->0) && law_ax05(t, sys_step::<O>(t, a)->0),
        forall|i: nat| #[trigger] sys_step::<O>(t, SA::Run(i)) is Some ==> law_ax11::<O>(t, i) && law_ax12::<O>(t, i),
{
    O::discharge_ax02(); O::discharge_ax03(); O::discharge_ax04(); O::discharge_ax05(); O::discharge_ax06();
    O::discharge_ax07(); O::discharge_ax08(); O::discharge_ax10(); O::discharge_ax11(); O::discharge_ax11m();
    O::discharge_ax12(); O::discharge_ax14();
    theorem_ax04::<O>(s0, ls, t);
    theorem_ax06::<O>(s0, ls, t);
    theorem_ax07::<O>(s0, ls, t);
    theorem_ax08::<O>(s0, ls, t);
    theorem_ax10::<O>(s0, ls, t);
    theorem_ax11m::<O>(s0, ls, t);
    theorem_ax14::<O>(s0, ls, t);
    assert forall|a: SA| #[trigger] sys_step::<O>(t, a) is Some implies law_ax02(t, a, sys_step::<O>(t, a)->0)
        && law_ax03(t, a, sys_step::<O>(t, a)->0) && law_ax05(t, sys_step::<O>(t, a)->0) by {
        theorem_ax02::<O>(s0, ls, t, a);
        theorem_ax03::<O>(s0, ls, t, a);
        theorem_ax05::<O>(s0, ls, t, a);
    }
    assert forall|i: nat| #[trigger] sys_step::<O>(t, SA::Run(i)) is Some implies law_ax11::<O>(t, i) && law_ax12::<O>(t, i) by {
        theorem_ax11::<O>(s0, ls, t, i);
        theorem_ax12::<O>(s0, ls, t, i);
    }
}

} // verus!
