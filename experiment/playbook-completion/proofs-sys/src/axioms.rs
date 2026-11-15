//! The axioms of module 00, each proved once over the design trait from its own obligation (on the composed
//! mechanisms' instance choices) and the invariants of src/base.rs and src/facts.rs.
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;
use crate::sys::*;
use crate::base::*;
use crate::facts::*;

verus! {

/// Unfold one Run step: the stepping process, its position and step, and the successor.
pub proof fn lemma_run<O: SysDesign>(s: SS, i: nat)
    requires inv_base::<O>(s), sys_step::<O>(s, SA::Run(i)) is Some,
    ensures ({
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        let st = step_at(c, i, k);
        &&& sys_step::<O>(s, SA::Run(i))->0 == after(c, s, i, k, st)
        &&& cur_step::<O>(s, i) == Some(st)
        &&& i < 4 && s.pc[i as int] == Pc::At(k) && k < len_of(c, i)
    }),
{
    lemma_run_shape::<O>(s, i);
    let c = O::cfg();
    let k = pc_k(s.pc[i as int]);
    let st = step_at(c, i, k);
    lemma_after(c, s, i, k, st);
    lemma_effect_data(c, s, i, st);
    lemma_effect_binding(c, s, i, st);
    lemma_positions(c, i, k);
}

// ------------------------------------------------------------------------------------------------ per-step axioms

pub proof fn lemma_ax02<O: SysDesign>(s: SS, a: SA)
    requires obl_ax02::<O>(), inv_base::<O>(s), sys_step::<O>(s, a) is Some,
    ensures law_ax02(s, a, sys_step::<O>(s, a)->0),
{
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        lemma_positions(c, i, k);
        lemma_after(c, s, i, k, step_at(c, i, k));
        lemma_effect_data(c, s, i, step_at(c, i, k));
        lemma_effect_binding(c, s, i, step_at(c, i, k));
    }
}

pub proof fn lemma_ax03<O: SysDesign>(s: SS, a: SA)
    requires obl_ax03::<O>(), inv_base::<O>(s), sys_step::<O>(s, a) is Some,
    ensures law_ax03(s, a, sys_step::<O>(s, a)->0),
{
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        lemma_positions(c, i, k);
        lemma_after(c, s, i, k, step_at(c, i, k));
        lemma_effect_data(c, s, i, step_at(c, i, k));
        lemma_effect_binding(c, s, i, step_at(c, i, k));
        lemma_frame(c, s, i, step_at(c, i, k));
    }
}

pub proof fn lemma_ax05<O: SysDesign>(s: SS, a: SA)
    requires obl_ax05::<O>(), inv_base::<O>(s), sys_step::<O>(s, a) is Some,
    ensures law_ax05(s, sys_step::<O>(s, a)->0),
{
    let t = sys_step::<O>(s, a)->0;
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        lemma_positions(c, i, k);
        lemma_after(c, s, i, k, step_at(c, i, k));
        lemma_effect_data(c, s, i, step_at(c, i, k));
        lemma_effect_binding(c, s, i, step_at(c, i, k));
        assert forall|x: int| 0 <= x < 2 implies #[trigger] t.recs[x].len() >= s.recs[x].len()
            && forall|j: int| 0 <= j < s.recs[x].len() ==> (#[trigger] t.recs[x][j] == s.recs[x][j] || !t.recs[x][j]) by {}
    } else {
        assert(t.recs == s.recs);
    }
}

pub proof fn theorem_ax02<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS, a: SA)
    requires obl_ax02::<O>(), reached::<SysM<O>>(s0, ls, t), sys_step::<O>(t, a) is Some,
    ensures law_ax02(t, a, sys_step::<O>(t, a)->0),
{
    theorem_base::<O>(s0, ls, t);
    lemma_ax02::<O>(t, a);
}

pub proof fn theorem_ax03<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS, a: SA)
    requires obl_ax03::<O>(), reached::<SysM<O>>(s0, ls, t), sys_step::<O>(t, a) is Some,
    ensures law_ax03(t, a, sys_step::<O>(t, a)->0),
{
    theorem_base::<O>(s0, ls, t);
    lemma_ax03::<O>(t, a);
}

pub proof fn theorem_ax05<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS, a: SA)
    requires obl_ax05::<O>(), reached::<SysM<O>>(s0, ls, t), sys_step::<O>(t, a) is Some,
    ensures law_ax05(t, sys_step::<O>(t, a)->0),
{
    theorem_base::<O>(s0, ls, t);
    lemma_ax05::<O>(t, a);
}

// ------------------------------------------------------------------------------------------------ simple invariants

pub open spec fn inv_ax04<O: SysDesign>(s: SS) -> bool { inv_base::<O>(s) && law_ax04(s) }
pub open spec fn inv_ax06<O: SysDesign>(s: SS) -> bool {
    inv_base::<O>(s) && s.effects == (if s.bind is Free { 0nat } else { 1nat }) && s.posts <= s.effects
}
pub open spec fn inv_ax08<O: SysDesign>(s: SS) -> bool { inv_base::<O>(s) && law_ax08(s) }

pub proof fn lemma_ax04_step<O: SysDesign>(s: SS, a: SA)
    requires obl_ax04::<O>(), inv_ax04::<O>(s), sys_step::<O>(s, a) is Some,
    ensures inv_ax04::<O>(sys_step::<O>(s, a)->0),
{
    lemma_base_step::<O>(s, a);
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        lemma_after(c, s, i, pc_k(s.pc[i as int]), step_at(c, i, pc_k(s.pc[i as int])));
        lemma_effect_data(c, s, i, step_at(c, i, pc_k(s.pc[i as int])));
        lemma_effect_binding(c, s, i, step_at(c, i, pc_k(s.pc[i as int])));
        lemma_frame(c, s, i, step_at(c, i, pc_k(s.pc[i as int])));
    }
}

pub proof fn lemma_ax06_step<O: SysDesign>(s: SS, a: SA)
    requires obl_ax06::<O>(), inv_ax06::<O>(s), sys_step::<O>(s, a) is Some,
    ensures inv_ax06::<O>(sys_step::<O>(s, a)->0),
{
    lemma_base_step::<O>(s, a);
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        lemma_positions(c, i, k);
        lemma_after(c, s, i, k, step_at(c, i, k));
        lemma_effect_data(c, s, i, step_at(c, i, k));
        lemma_effect_binding(c, s, i, step_at(c, i, k));
    }
}

pub proof fn lemma_ax08_step<O: SysDesign>(s: SS, a: SA)
    requires obl_ax08::<O>(), inv_ax08::<O>(s), sys_step::<O>(s, a) is Some,
    ensures inv_ax08::<O>(sys_step::<O>(s, a)->0),
{
    lemma_base_step::<O>(s, a);
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        lemma_positions(c, i, k);
        lemma_after(c, s, i, k, step_at(c, i, k));
        lemma_effect_data(c, s, i, step_at(c, i, k));
        lemma_effect_binding(c, s, i, step_at(c, i, k));
    }
}

pub proof fn theorem_ax04<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires obl_ax04::<O>(), reached::<SysM<O>>(s0, ls, t),
    ensures law_ax04(t),
{
    lemma_init::<O>();
    let inv = |s: SS| inv_ax04::<O>(s);
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_ax04_step::<O>(x, a);
    }
    lemma_reached_inv::<SysM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_ax06<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires obl_ax06::<O>(), reached::<SysM<O>>(s0, ls, t),
    ensures law_ax06(t),
{
    lemma_init::<O>();
    let inv = |s: SS| inv_ax06::<O>(s);
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_ax06_step::<O>(x, a);
    }
    lemma_reached_inv::<SysM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_ax08<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires obl_ax08::<O>(), reached::<SysM<O>>(s0, ls, t),
    ensures law_ax08(t),
{
    lemma_init::<O>();
    let inv = |s: SS| inv_ax08::<O>(s);
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_ax08_step::<O>(x, a);
    }
    lemma_reached_inv::<SysM<O>>(inv, s0, ls, t);
}

// ------------------------------------------------------------------------------------------------ invariants on the facts

pub open spec fn inv_ax07<O: SysDesign>(s: SS) -> bool { inv_facts::<O>(s) && law_ax07(s) }
pub open spec fn inv_ax11m<O: SysDesign>(s: SS) -> bool { inv_facts::<O>(s) && law_ax11m(s) }
pub open spec fn inv_ax10<O: SysDesign>(s: SS) -> bool {
    &&& inv_facts::<O>(s)
    &&& !s.revived
    &&& (s.der[0] ==> s.content[0]) && (s.der[1] ==> s.content[1])
    &&& (s.receipt ==> s.after_receipt || (!s.content[0] && !s.prop[0] && !s.der[0] && !(s.bind is Bound)))
}

pub proof fn lemma_ax07_step<O: SysDesign>(s: SS, a: SA)
    requires obl_ax07::<O>(), inv_ax07::<O>(s), sys_step::<O>(s, a) is Some,
    ensures inv_ax07::<O>(sys_step::<O>(s, a)->0),
{
    lemma_facts_step::<O>(s, a);
    let t = sys_step::<O>(s, a)->0;
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        let st = step_at(c, i, k);
        lemma_positions(c, i, k);
        lemma_after(c, s, i, k, st);
        lemma_effect_data(c, s, i, st);
        lemma_effect_binding(c, s, i, st);
        assert forall|x: int| 0 <= x < 2 && #[trigger] t.content[x] implies has_live_record(t.recs[x]) by {
            if (st is Apply || st is ApplyProp) && t.recs[x] != s.recs[x] {
                assert(t.recs[x][t.recs[x].len() - 1]);
            } else if t.content[x] && s.content[x] && t.recs[x] == s.recs[x] {
            } else if st is TombAll || st is DeleteRecords {
                assert(f_content(c, s));
            } else {
                let w = choose|j: int| 0 <= j < s.recs[x].len() && s.recs[x][j];
                assert(t.recs[x][w]);
            }
        }
    } else {
        assert(t.content == s.content && t.recs == s.recs);
    }
}

pub proof fn lemma_ax11m_step<O: SysDesign>(s: SS, a: SA)
    requires obl_ax11m::<O>(), inv_ax11m::<O>(s), sys_step::<O>(s, a) is Some,
    ensures inv_ax11m::<O>(sys_step::<O>(s, a)->0),
{
    lemma_facts_step::<O>(s, a);
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        let st = step_at(c, i, k);
        lemma_positions(c, i, k);
        lemma_positions(c, 3, r_sm(c));
        lemma_after(c, s, i, k, st);
        lemma_effect_data(c, s, i, st);
        lemma_effect_binding(c, s, i, st);
        assert(pc_ok(c, 3, s.pc[3]));
    }
}

pub proof fn lemma_ax10_step<O: SysDesign>(s: SS, a: SA)
    requires obl_ax10::<O>(), inv_ax10::<O>(s), sys_step::<O>(s, a) is Some,
    ensures inv_ax10::<O>(sys_step::<O>(s, a)->0),
{
    lemma_facts_step::<O>(s, a);
    if let SA::Run(i) = a {
        lemma_run::<O>(s, i);
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        let st = step_at(c, i, k);
        lemma_positions(c, i, k);
        lemma_positions(c, 3, r_sm(c));
        lemma_after(c, s, i, k, st);
        lemma_effect_data(c, s, i, st);
        lemma_effect_binding(c, s, i, st);
        assert(pc_ok(c, 3, s.pc[3]));
    }
}

pub proof fn theorem_ax07<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires obl_ax07::<O>(), reached::<SysM<O>>(s0, ls, t),
    ensures law_ax07(t),
{
    let inv = |s: SS| inv_ax07::<O>(s);
    assert(inv_facts::<O>(sys_s0())) by { theorem_facts::<O>(sys_s0(), Seq::empty(), sys_s0()); }
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_ax07_step::<O>(x, a);
    }
    lemma_reached_inv::<SysM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_ax11m<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires obl_ax11m::<O>(), reached::<SysM<O>>(s0, ls, t),
    ensures law_ax11m(t),
{
    let inv = |s: SS| inv_ax11m::<O>(s);
    assert(inv_facts::<O>(sys_s0())) by { theorem_facts::<O>(sys_s0(), Seq::empty(), sys_s0()); }
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_ax11m_step::<O>(x, a);
    }
    lemma_reached_inv::<SysM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_ax10<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires obl_ax10::<O>(), reached::<SysM<O>>(s0, ls, t),
    ensures law_ax10(t),
{
    let inv = |s: SS| inv_ax10::<O>(s);
    assert(inv_facts::<O>(sys_s0())) by { theorem_facts::<O>(sys_s0(), Seq::empty(), sys_s0()); }
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_ax10_step::<O>(x, a);
    }
    lemma_reached_inv::<SysM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_ax11<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS, i: nat)
    requires obl_ax11::<O>(), reached::<SysM<O>>(s0, ls, t), sys_step::<O>(t, SA::Run(i)) is Some,
    ensures law_ax11::<O>(t, i),
{
    theorem_facts::<O>(s0, ls, t);
    lemma_run::<O>(t, i);
    let c = O::cfg();
    lemma_positions(c, i, pc_k(t.pc[i as int]));
}

pub proof fn theorem_ax12<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS, i: nat)
    requires obl_ax12::<O>(), reached::<SysM<O>>(s0, ls, t), sys_step::<O>(t, SA::Run(i)) is Some,
    ensures law_ax12::<O>(t, i),
{
    theorem_facts::<O>(s0, ls, t);
    lemma_run::<O>(t, i);
    let c = O::cfg();
    lemma_positions(c, i, pc_k(t.pc[i as int]));
    lemma_positions(c, 3, r_sm(c));
}

} // verus!
