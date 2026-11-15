//! AX-14 (accepted work progresses), as the explorer checks it: AG EF final, i.e. from every reached state some run
//! finishes every process (Done or Refused) and releases the marker. Proved for every design whose redaction clears
//! its marker (obligation `obl_ax14`), constructively: the proof returns the schedule. It drains the head-lock
//! holder, then each process in turn (with no other process acting, every step of the running process is enabled);
//! if the redaction is then parked on live content, the operator re-runs the erasure and resumes the redaction
//! (premise PS-2 below: the operator actions are part of the model, as in the explorer), whose final section then
//! passes. Like the explorer's AG EF, this is "can finish", not "finishes under fairness".
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;
use crate::sys::*;
use crate::base::*;

verus! {

pub open spec fn others_same(s: SS, t: SS, i: nat) -> bool {
    forall|j: int| 0 <= j < 4 && j != i ==> t.pc[j] == s.pc[j]
}
pub open spec fn not_at(p: Pc) -> bool { !(p is At) }

pub proof fn lemma_cons<O: SysDesign>(s: SS, a: SA, l: Seq<SA>)
    ensures run::<SysM<O>>(s, seq![a] + l) == match sys_step::<O>(s, a) { Some(t) => run::<SysM<O>>(t, l), None => None },
{
    lemma_run_append::<SysM<O>>(s, seq![a], l);
    reveal_with_fuel(run, 2);
    let one = seq![a];
    assert(one.drop_first() =~= Seq::<SA>::empty());
}

/// Running `ls` then `a` (used to state counterexample runs step by step).
pub proof fn lemma_run_snoc<M: Machine>(s: M::S, ls: Seq<M::A>, a: M::A)
    ensures run::<M>(s, ls.push(a)) == match run::<M>(s, ls) { Some(t) => M::step(t, a), None => None },
{
    lemma_run_append::<M>(s, ls, seq![a]);
    assert(ls.push(a) =~= ls + seq![a]);
    reveal_with_fuel(run, 2);
    assert(seq![a].drop_first() =~= Seq::<M::A>::empty());
    match run::<M>(s, ls) {
        Some(t) => { assert(run::<M>(t, seq![a]) == match M::step(t, a) { Some(u) => run::<M>(u, Seq::<M::A>::empty()), None => None }); },
        None => {},
    }
}

/// The generic run of a design is the run for its parameters.
pub proof fn lemma_run_cfg<O: SysDesign>(s: SS, ls: Seq<SA>)
    ensures run::<SysM<O>>(s, ls) == run_cfg(O::cfg(), s, ls),
    decreases ls.len(),
{
    if ls.len() > 0 {
        match sys_step::<O>(s, ls[0]) {
            Some(t) => { lemma_run_cfg::<O>(t, ls.drop_first()); },
            None => {},
        }
    }
}

pub proof fn lemma_run_base<O: SysDesign>(s: SS, l: Seq<SA>)
    requires inv_base::<O>(s), run::<SysM<O>>(s, l) is Some,
    ensures inv_base::<O>(run::<SysM<O>>(s, l)->0),
{
    let inv = |x: SS| inv_base::<O>(x);
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_base_step::<O>(x, a);
    }
    lemma_run_inv::<SysM<O>>(inv, s, l);
}

/// One step of the only active process i (lock free or its own) is enabled and keeps the others still.
pub proof fn lemma_step_alone<O: SysDesign>(s: SS, i: nat)
    requires inv_base::<O>(s), i < 4, s.pc[i as int] is At, s.lock is None || s.lock == Some(i),
    ensures
        sys_step::<O>(s, SA::Run(i)) is Some,
        ({
            let t = sys_step::<O>(s, SA::Run(i))->0;
            let c = O::cfg();
            let k = pc_k(s.pc[i as int]);
            &&& inv_base::<O>(t) && others_same(s, t, i)
            &&& t.lock is None || t.lock == Some(i)
            &&& (t.pc[i as int] is At ==> t.pc[i as int] == Pc::At(k + 1))
            &&& (not_at(t.pc[i as int]) ==> t.lock is None)
            &&& t == after(c, s, i, k, step_at(c, i, k))
        }),
{
    let c = O::cfg();
    let k = pc_k(s.pc[i as int]);
    let st = step_at(c, i, k);
    assert(pc_ok(c, i, s.pc[i as int]));
    lemma_after(c, s, i, k, st);
    lemma_frame(c, s, i, st);
    lemma_base_step::<O>(s, SA::Run(i));
}

/// Drain process i alone: a run of its steps after which it is Done, Refused or Parked, the lock is free, and no
/// other process moved.
pub proof fn lemma_drain<O: SysDesign>(s: SS, i: nat) -> (ls: Seq<SA>)
    requires inv_base::<O>(s), i < 4, s.pc[i as int] is At, s.lock is None || s.lock == Some(i),
    ensures
        run::<SysM<O>>(s, ls) is Some,
        ({
            let t = run::<SysM<O>>(s, ls)->0;
            inv_base::<O>(t) && not_at(t.pc[i as int]) && t.lock is None && others_same(s, t, i)
        }),
    decreases len_of(O::cfg(), i) - pc_k(s.pc[i as int]),
{
    let c = O::cfg();
    assert(pc_ok(c, i, s.pc[i as int]));
    lemma_step_alone::<O>(s, i);
    let t = sys_step::<O>(s, SA::Run(i))->0;
    if t.pc[i as int] is At {
        assert(pc_ok(c, i, t.pc[i as int]));
        let rest = lemma_drain::<O>(t, i);
        lemma_cons::<O>(s, SA::Run(i), rest);
        seq![SA::Run(i)] + rest
    } else {
        lemma_cons::<O>(s, SA::Run(i), Seq::empty());
        assert(seq![SA::Run(i)] + Seq::<SA>::empty() =~= seq![SA::Run(i)]);
        reveal_with_fuel(run, 1);
        seq![SA::Run(i)]
    }
}

/// Drain process i if it is active (else the empty run).
pub proof fn lemma_drain_if<O: SysDesign>(s: SS, i: nat) -> (ls: Seq<SA>)
    requires inv_base::<O>(s), i < 4, s.lock is None,
    ensures
        run::<SysM<O>>(s, ls) is Some,
        ({
            let t = run::<SysM<O>>(s, ls)->0;
            inv_base::<O>(t) && not_at(t.pc[i as int]) && t.lock is None && others_same(s, t, i)
                && (not_at(s.pc[i as int]) ==> t == s)
        }),
{
    if s.pc[i as int] is At {
        lemma_drain::<O>(s, i)
    } else {
        reveal_with_fuel(run, 1);
        Seq::empty()
    }
}

/// The erasure re-run alone from its first step leaves tenant A not live.
pub proof fn lemma_drain_e<O: SysDesign>(s: SS) -> (ls: Seq<SA>)
    requires inv_base::<O>(s), s.pc[2] is At, s.lock is None || s.lock == Some(2nat),
        ({
            let c = O::cfg();
            let k = pc_k(s.pc[2]);
            (k > e_lk(c) ==> !s.content[0]) && (k > e_lk(c) + (if c.m10_erase_split { 1nat } else { 0 }) ==> !s.prop[0])
        }),
    ensures
        run::<SysM<O>>(s, ls) is Some,
        ({
            let t = run::<SysM<O>>(s, ls)->0;
            inv_base::<O>(t) && not_at(t.pc[2]) && t.lock is None && others_same(s, t, 2) && !live(t, 0)
        }),
    decreases len_of(O::cfg(), 2) - pc_k(s.pc[2]),
{
    let c = O::cfg();
    let k = pc_k(s.pc[2]);
    assert(pc_ok(c, 2, s.pc[2]));
    lemma_step_alone::<O>(s, 2);
    let t = sys_step::<O>(s, SA::Run(2))->0;
    lemma_effect_data(c, s, 2, step_at(c, 2, k));
    lemma_positions(c, 2, k);
    if t.pc[2] is At {
        let rest = lemma_drain_e::<O>(t);
        lemma_cons::<O>(s, SA::Run(2), rest);
        seq![SA::Run(2)] + rest
    } else {
        lemma_cons::<O>(s, SA::Run(2), Seq::empty());
        assert(seq![SA::Run(2)] + Seq::<SA>::empty() =~= seq![SA::Run(2)]);
        reveal_with_fuel(run, 1);
        seq![SA::Run(2)]
    }
}

/// The redaction alone in its final part, with tenant A not live: it finishes (Done).
pub proof fn lemma_drain_r_final<O: SysDesign>(s: SS) -> (ls: Seq<SA>)
    requires inv_base::<O>(s), s.pc[3] is At, r_lock2(O::cfg()) <= pc_k(s.pc[3]), s.lock is None || s.lock == Some(3nat), !live(s, 0),
    ensures
        run::<SysM<O>>(s, ls) is Some,
        ({
            let t = run::<SysM<O>>(s, ls)->0;
            inv_base::<O>(t) && t.pc[3] is Done && t.lock is None && others_same(s, t, 3)
        }),
    decreases len_of(O::cfg(), 3) - pc_k(s.pc[3]),
{
    let c = O::cfg();
    let k = pc_k(s.pc[3]);
    assert(pc_ok(c, 3, s.pc[3]));
    lemma_step_alone::<O>(s, 3);
    let t = sys_step::<O>(s, SA::Run(3))->0;
    lemma_effect_data(c, s, 3, step_at(c, 3, k));
    lemma_positions(c, 3, k);
    lemma_positions(c, 3, r_sm(c));
    if t.pc[3] is At {
        let rest = lemma_drain_r_final::<O>(t);
        lemma_cons::<O>(s, SA::Run(3), rest);
        seq![SA::Run(3)] + rest
    } else {
        lemma_cons::<O>(s, SA::Run(3), Seq::empty());
        assert(seq![SA::Run(3)] + Seq::<SA>::empty() =~= seq![SA::Run(3)]);
        reveal_with_fuel(run, 1);
        seq![SA::Run(3)]
    }
}

/// Every process stopped (Done, Refused or a parked redaction) and the lock free.
pub open spec fn quiescent(s: SS) -> bool {
    s.lock is None && not_at(s.pc[0]) && not_at(s.pc[1]) && not_at(s.pc[2]) && not_at(s.pc[3])
}

/// From any state of the base invariant, a run to a quiescent state.
pub proof fn lemma_quiesce<O: SysDesign>(s: SS) -> (ls: Seq<SA>)
    requires inv_base::<O>(s),
    ensures run::<SysM<O>>(s, ls) is Some, inv_base::<O>(run::<SysM<O>>(s, ls)->0), quiescent(run::<SysM<O>>(s, ls)->0),
{
    let c = O::cfg();
    let (l0, s0) = if s.lock is Some {
        let h = s.lock->0;
        assert(holding(c, s, h));
        let l = lemma_drain::<O>(s, h);
        (l, run::<SysM<O>>(s, l)->0)
    } else {
        reveal_with_fuel(run, 1);
        (Seq::<SA>::empty(), s)
    };
    let l1 = lemma_drain_if::<O>(s0, 0);
    let s1 = run::<SysM<O>>(s0, l1)->0;
    let l2 = lemma_drain_if::<O>(s1, 1);
    let s2 = run::<SysM<O>>(s1, l2)->0;
    let l3 = lemma_drain_if::<O>(s2, 2);
    let s3 = run::<SysM<O>>(s2, l3)->0;
    let l4 = lemma_drain_if::<O>(s3, 3);
    let s4 = run::<SysM<O>>(s3, l4)->0;
    lemma_run_append::<SysM<O>>(s, l0, l1);
    lemma_run_append::<SysM<O>>(s, l0 + l1, l2);
    lemma_run_append::<SysM<O>>(s, l0 + l1 + l2, l3);
    lemma_run_append::<SysM<O>>(s, l0 + l1 + l2 + l3, l4);
    assert(not_at(s4.pc[0]) && not_at(s4.pc[1]) && not_at(s4.pc[2]));
    l0 + l1 + l2 + l3 + l4
}

pub proof fn lemma_ef<O: SysDesign>(s: SS) -> (ls: Seq<SA>)
    requires obl_ax14::<O>(), inv_base::<O>(s),
    ensures run::<SysM<O>>(s, ls) is Some, final_state(run::<SysM<O>>(s, ls)->0),
{
    let c = O::cfg();
    let l0 = lemma_quiesce::<O>(s);
    let q = run::<SysM<O>>(s, l0)->0;
    assert(pc_ok(c, 0, q.pc[0]) && pc_ok(c, 1, q.pc[1]) && pc_ok(c, 2, q.pc[2]) && pc_ok(c, 3, q.pc[3]));
    lemma_positions(c, 3, r_sm(c));
    if q.pc[3] is Parked {
        let (l1, q1) = if live(q, 0) {
            // the operator re-runs the erasure, which then runs alone
            let e0 = sys_step::<O>(q, SA::ReErase)->0;
            lemma_base_step::<O>(q, SA::ReErase);
            let le = lemma_drain_e::<O>(e0);
            lemma_cons::<O>(q, SA::ReErase, le);
            (seq![SA::ReErase] + le, run::<SysM<O>>(e0, le)->0)
        } else {
            reveal_with_fuel(run, 1);
            (Seq::<SA>::empty(), q)
        };
        assert(pc_ok(c, 3, q1.pc[3]));
        // the operator resumes the parked redaction; its final section passes
        let r0 = sys_step::<O>(q1, SA::Resume)->0;
        lemma_base_step::<O>(q1, SA::Resume);
        let lr = lemma_drain_r_final::<O>(r0);
        lemma_cons::<O>(q1, SA::Resume, lr);
        let l2 = seq![SA::Resume] + lr;
        lemma_run_append::<SysM<O>>(s, l0, l1);
        lemma_run_append::<SysM<O>>(s, l0 + l1, l2);
        let f = run::<SysM<O>>(r0, lr)->0;
        assert(pc_ok(c, 0, f.pc[0]) && pc_ok(c, 1, f.pc[1]) && pc_ok(c, 2, f.pc[2]));
        assert forall|i: int| 0 <= i < 4 implies (#[trigger] f.pc[i] is Done || f.pc[i] is Refused) by {
            assert(pc_ok(c, i as nat, f.pc[i]));
        }
        l0 + l1 + l2
    } else {
        assert forall|i: int| 0 <= i < 4 implies (#[trigger] q.pc[i] is Done || q.pc[i] is Refused) by {
            assert(pc_ok(c, i as nat, q.pc[i]));
        }
        l0
    }
}

/// AX-14: every reached state of a design whose redaction clears its marker can finish.
pub proof fn theorem_ax14<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires obl_ax14::<O>(), reached::<SysM<O>>(s0, ls, t),
    ensures law_ax14::<O>(t),
{
    theorem_base::<O>(s0, ls, t);
    let w = lemma_ef::<O>(t);
    assert(run::<SysM<O>>(t, w) is Some && final_state(run::<SysM<O>>(t, w)->0));
}

} // verus!
