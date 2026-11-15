//! What the redaction has checked or done still holds while it holds the head lock or its marker (every design;
//! each fact is an implication whose premise names the design choices it needs):
//! - `f_content`: inside its first section after its liveness check (checked inside the lock), A has no content;
//! - `f_prop`: the same for A's properties, when post-commit properties are written in the commit;
//! - `f_final`: inside its final section after its final check, A is not live (properties: when written in commit);
//! - `f_bind`: from its MoveBinding to its receipt (receipt at Final), A's retry key is not bound;
//! - `f_recs`: from its tombstones to its receipt (receipt at Final), A has no live record.
//! The argument is the same for all: only the A committer W writes A's content, properties, records or binding, and
//! it does so only at positions where it holds the head lock (its apply steps, its refusing check) and, for its
//! apply steps, only having seen no marker; while the redaction holds the lock or its marker, W is at none of them.
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;
use crate::sys::*;
use crate::base::*;

verus! {

pub open spec fn r_in(p: Pc, lo: nat, hi: nat) -> bool { match p { Pc::At(k) => lo < k && k <= hi, _ => false } }

pub open spec fn f_content(c: SysCfg, s: SS) -> bool {
    check_in_lock(c) && r_in(s.pc[3], r_check(c), r_unlock1(c)) ==> !s.content[0]
}
pub open spec fn f_prop(c: SysCfg, s: SS) -> bool {
    check_in_lock(c) && c.m02_post is InCommit && r_in(s.pc[3], r_check(c), r_unlock1(c)) ==> !s.prop[0]
}
pub open spec fn f_final(c: SysCfg, s: SS) -> bool {
    r_in(s.pc[3], r_cnlf(c), r_unlock2(c)) ==> !s.content[0] && (c.m02_post is InCommit ==> !s.prop[0])
}
pub open spec fn r_until_receipt(c: SysCfg, p: Pc, from: nat) -> bool {
    !early(c) && (r_in(p, from, r_rcpt(c)) || p is Parked)
}
pub open spec fn f_bind(c: SysCfg, s: SS) -> bool {
    c.m05_move_binding && r_until_receipt(c, s.pc[3], r_move(c)) ==> !(s.bind is Bound)
}
pub open spec fn f_recs(c: SysCfg, s: SS) -> bool {
    r_until_receipt(c, s.pc[3], r_tomb(c)) ==> !has_live_record(s.recs[0])
}

pub open spec fn inv_facts<O: SysDesign>(s: SS) -> bool {
    let c = O::cfg();
    inv_base::<O>(s) && f_content(c, s) && f_prop(c, s) && f_final(c, s) && f_bind(c, s) && f_recs(c, s)
}

/// While the redaction holds the lock or its marker (and has not passed its receipt), W is at no apply step.
pub proof fn lemma_w_blocked<O: SysDesign>(s: SS)
    requires inv_base::<O>(s), r_until_receipt(O::cfg(), s.pc[3], r_sm(O::cfg())) || r_in(s.pc[3], r_lock1(O::cfg()), r_unlock1(O::cfg()))
        || r_in(s.pc[3], r_lock2(O::cfg()), r_unlock2(O::cfg())),
    ensures !w_at_apply(O::cfg(), s),
        r_in(s.pc[3], r_lock1(O::cfg()), r_unlock1(O::cfg())) || r_in(s.pc[3], r_lock2(O::cfg()), r_unlock2(O::cfg()))
            ==> !holding(O::cfg(), s, 0),
{
    let c = O::cfg();
    lemma_positions(c, 3, r_sm(c));
    assert(pc_ok(c, 3, s.pc[3]) && pc_ok(c, 0, s.pc[0]));
    assert(holding(c, s, 3) == (s.lock == Some(3nat)));
    assert(holding(c, s, 0) == (s.lock == Some(0nat)));
    if w_at_apply(c, s) {
        lemma_positions(c, 0, pc_k(s.pc[0]));
    }
}

pub proof fn lemma_facts_step<O: SysDesign>(s: SS, a: SA)
    requires inv_facts::<O>(s), sys_step::<O>(s, a) is Some,
    ensures inv_facts::<O>(sys_step::<O>(s, a)->0),
{
    lemma_base_step::<O>(s, a);
    let c = O::cfg();
    let t = sys_step::<O>(s, a)->0;
    match a {
        SA::Run(i) => {
            lemma_run_shape::<O>(s, i);
            let k = pc_k(s.pc[i as int]);
            let st = step_at(c, i, k);
            assert(t == after(c, s, i, k, st));
            if i == 0 { lemma_facts_w::<O>(s, k, st, t); }
            else if i == 3 { lemma_facts_r::<O>(s, k, st, t); }
            else { lemma_facts_ce::<O>(s, i, k, st, t); }
        },
        _ => { lemma_facts_env::<O>(s, a, t); },
    }
}

proof fn lemma_facts_ce<O: SysDesign>(s: SS, i: nat, k: nat, st: Step, t: SS)
    requires inv_facts::<O>(s), inv_base::<O>(t), i == 1 || i == 2, s.pc[i as int] == Pc::At(k), k < len_of(O::cfg(), i),
        st == step_at(O::cfg(), i, k), t == after(O::cfg(), s, i, k, st), wf_shape(s),
    ensures inv_facts::<O>(t),
{
    let c = O::cfg();
    lemma_after(c, s, i, k, st);
    lemma_effect_data(c, s, i, st);
    lemma_effect_binding(c, s, i, st);
    lemma_positions(c, i, k);
    assert(t.pc[3] == s.pc[3]);
    assert(t.bind == s.bind);
    assert(t.recs[0] == s.recs[0]);
}

proof fn lemma_facts_env<O: SysDesign>(s: SS, a: SA, t: SS)
    requires inv_facts::<O>(s), inv_base::<O>(t), !(a is Run), sys_step::<O>(s, a) == Some(t),
    ensures inv_facts::<O>(t),
{
    let c = O::cfg();
    lemma_positions(c, 3, r_sm(c));
    assert(pc_ok(c, 3, s.pc[3]));
    assert(t.content == s.content && t.prop == s.prop && t.bind == s.bind && t.recs == s.recs);
}

proof fn lemma_facts_w<O: SysDesign>(s: SS, k: nat, st: Step, t: SS)
    requires inv_facts::<O>(s), inv_base::<O>(t), s.pc[0] == Pc::At(k), k < len_of(O::cfg(), 0),
        st == step_at(O::cfg(), 0, k), t == after(O::cfg(), s, 0, k, st), wf_shape(s),
        !(st is Lock && s.lock is Some && s.lock != Some(0nat)),
    ensures inv_facts::<O>(t),
{
    let c = O::cfg();
    lemma_after(c, s, 0, k, st);
    lemma_effect_data(c, s, 0, st);
    lemma_effect_binding(c, s, 0, st);
    lemma_positions(c, 0, k);
    lemma_positions(c, 3, r_sm(c));
    assert(t.pc[3] == s.pc[3]);
    assert(holding(c, s, 0) == (s.lock == Some(0nat)));
    assert(holding(c, s, 3) == (s.lock == Some(3nat)));
    assert(pc_ok(c, 3, s.pc[3]));
    let writes_a = st is Apply || st is ApplyProp || st is ApplyUnrecorded || st is CheckMarkerBad;
    if writes_a && (r_in(s.pc[3], r_lock1(c), r_unlock1(c)) || r_in(s.pc[3], r_lock2(c), r_unlock2(c))
        || r_until_receipt(c, s.pc[3], r_sm(c))) {
        if st is CheckMarkerBad { assert(holding(c, s, 0)); }
        lemma_w_blocked::<O>(s);
    }
}

proof fn lemma_facts_r<O: SysDesign>(s: SS, k: nat, st: Step, t: SS)
    requires inv_facts::<O>(s), inv_base::<O>(t), s.pc[3] == Pc::At(k), k < len_of(O::cfg(), 3),
        st == step_at(O::cfg(), 3, k), t == after(O::cfg(), s, 3, k, st), wf_shape(s),
    ensures inv_facts::<O>(t),
{
    let c = O::cfg();
    lemma_after(c, s, 3, k, st);
    lemma_effect_data(c, s, 3, st);
    lemma_effect_binding(c, s, 3, st);
    lemma_positions(c, 3, k);
    lemma_positions(c, 3, r_sm(c));
    if st is TombAll || st is TombAllAny || st is DeleteRecords {
        assert(!has_live_record(t.recs[0]));
    }
}

pub proof fn theorem_facts<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires reached::<SysM<O>>(s0, ls, t),
    ensures inv_facts::<O>(t),
{
    lemma_init::<O>();
    let inv = |s: SS| inv_facts::<O>(s);
    assert(inv(sys_s0())) by {
        let c = O::cfg();
        assert(sys_s0().pc[3] == Pc::At(0));
        lemma_positions(c, 3, r_sm(c));
    }
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_facts_step::<O>(x, a);
    }
    lemma_reached_inv::<SysM<O>>(inv, s0, ls, t);
}

} // verus!
