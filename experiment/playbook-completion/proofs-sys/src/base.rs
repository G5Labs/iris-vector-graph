//! The composed machine's base invariant, for every design (no obligation): shapes, program counters in range, the
//! head lock held exactly by the process inside a locked section of its program, the marker set exactly while the
//! redaction is in its marked phase (only the redaction sets or clears it), the receipt written exactly once the
//! redaction passed its receipt step, and a commit about to apply has seen no marker. Proved once for all designs.
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;
use crate::sys::*;

verus! {

pub open spec fn pc_k(p: Pc) -> nat { match p { Pc::At(k) => k, _ => 0 } }

pub open spec fn pc_ok(c: SysCfg, i: nat, p: Pc) -> bool {
    match p {
        Pc::At(k) => k < len_of(c, i),
        Pc::Parked(b) => i == 3 && b == r_lock2(c),
        Pc::Refused => i != 2,
        Pc::Done => true,
    }
}

pub open spec fn holding(c: SysCfg, s: SS, i: nat) -> bool { s.pc[i as int] is At && holds_at(c, i, pc_k(s.pc[i as int])) }

/// The redaction is in its marked phase: past its SetMarker and not past its clear (parked runs are marked).
pub open spec fn r_marked(c: SysCfg, p: Pc) -> bool {
    match p {
        Pc::At(k) => r_sm(c) < k && (!has_clear(c) || k <= r_clear(c)),
        Pc::Parked(_) => true,
        Pc::Done => !has_clear(c),
        Pc::Refused => false,
    }
}

/// The redaction passed its receipt step.
pub open spec fn r_past_receipt(c: SysCfg, p: Pc) -> bool {
    match p {
        Pc::At(k) => r_rcpt(c) < k,
        Pc::Parked(_) => early(c),
        Pc::Done => true,
        Pc::Refused => false,
    }
}

/// W is at one of its apply positions (inside its locked section, past its marker check).
pub open spec fn w_at_apply(c: SysCfg, s: SS) -> bool {
    s.pc[0] == Pc::At(w_apply1(c)) || s.pc[0] == Pc::At(w_apply2(c))
}

pub open spec fn inv_base<O: SysDesign>(s: SS) -> bool {
    let c = O::cfg();
    &&& wf_shape(s)
    &&& forall|i: nat| i < 4 ==> #[trigger] pc_ok(c, i, s.pc[i as int])
    &&& forall|i: nat| i < 4 ==> ((s.lock == Some(i)) == #[trigger] holding(c, s, i))
    &&& s.lock is Some ==> s.lock->0 < 4
    &&& s.marker == (if r_marked(c, s.pc[3]) { Some((0nat, 3nat)) } else { None })
    &&& s.receipt == r_past_receipt(c, s.pc[3])
    &&& w_at_apply(c, s) ==> s.marker is None
}

/// Facts about each program, by position (decided by the solver over every design).
pub proof fn lemma_positions(c: SysCfg, i: nat, k: nat)
    requires i < 4, k < len_of(c, i),
    ensures
        step_at(c, i, k) is Lock ==> !holds_at(c, i, k) && (k + 1 < len_of(c, i) ==> holds_at(c, i, k + 1)),
        step_at(c, i, k) is Unlock ==> holds_at(c, i, k) && (k + 1 < len_of(c, i) ==> !holds_at(c, i, k + 1)),
        !(step_at(c, i, k) is Lock) && !(step_at(c, i, k) is Unlock) && k + 1 < len_of(c, i)
            ==> holds_at(c, i, k + 1) == holds_at(c, i, k),
        !(step_at(c, i, k) is Unlock) && k + 1 == len_of(c, i) ==> !holds_at(c, i, k),
        // only the redaction marks, clears, writes the receipt or checks liveness
        step_at(c, i, k) is SetMarker || step_at(c, i, k) is ClearOwn || step_at(c, i, k) is ClearAny
            || step_at(c, i, k) is Receipt || step_at(c, i, k) is CheckNotLive || step_at(c, i, k) is CheckNotLiveFinal
            || step_at(c, i, k) is TombAll || step_at(c, i, k) is TombAllAny || step_at(c, i, k) is DeleteRecords
            || step_at(c, i, k) is MoveBinding ==> i == 3,
        step_at(c, i, k) is SetMarker ==> k == r_sm(c) && step_at(c, i, k) == Step::SetMarker(0) && holds_at(c, i, k),
        step_at(c, i, k) is ClearOwn || step_at(c, i, k) is ClearAny ==> has_clear(c) && k == r_clear(c) && holds_at(c, i, k),
        step_at(c, i, k) is Receipt ==> k == r_rcpt(c),
        step_at(c, i, k) is CheckNotLiveFinal ==> k == r_cnlf(c) && step_at(c, i, k) == Step::CheckNotLiveFinal(0, r_lock2(c)) && holds_at(c, i, k),
        step_at(c, i, k) is CheckNotLive ==> k == r_check(c) && step_at(c, i, k) == Step::CheckNotLive(0),
        // the erasure and the B committer touch only their tenant; W only tenant A
        step_at(c, i, k) is EraseBoth || step_at(c, i, k) is EraseContent || step_at(c, i, k) is EraseProp ==> i == 2,
        i == 2 ==> (step_at(c, i, k) matches Step::EraseBoth(t, _) ==> t == 0)
            && (step_at(c, i, k) matches Step::EraseContent(t) ==> t == 0)
            && (step_at(c, i, k) matches Step::EraseProp(t) ==> t == 0),
        step_at(c, i, k) matches Step::Apply(t, keyed) ==> (i == 0 && t == 0 && keyed && (k == w_apply1(c) || k == w_apply2(c)))
            || (i == 1 && t == 1 && !keyed && k == 2),
        step_at(c, i, k) matches Step::ApplyProp(t, keyed) ==> i == 0 && t == 0 && keyed && (k == w_apply1(c) || k == w_apply2(c)),
        step_at(c, i, k) is ApplyUnrecorded ==> i == 0 && k == w_apply1(c) && step_at(c, i, k) == Step::ApplyUnrecorded(0),
        step_at(c, i, k) is Post ==> i == 0 && step_at(c, i, k) == Step::Post(0) && !holds_at(c, i, k) && c.m02_post is SeparateAlways,
        step_at(c, i, k) matches Step::CheckMarker(t) ==> (i == 0 && t == 0 && (k + 1 == w_apply1(c) || k + 1 == w_apply2(c)) && holds_at(c, i, k))
            || (i == 1 && t == 1 && k == 1),
        step_at(c, i, k) is CheckMarkerBad ==> i == 0 && k == 1 && step_at(c, i, k) == Step::CheckMarkerBad(0) && holds_at(c, i, k)
            && c.m10_refusal is Writes,
        (i == 0 && (k == w_apply1(c) || k == w_apply2(c))) ==> holds_at(c, i, k),
        step_at(c, i, k) matches Step::TombAll(t) ==> t == 0 && k == r_tomb(c),
        step_at(c, i, k) is TombAllAny || step_at(c, i, k) is DeleteRecords ==> k == r_tomb(c),
        step_at(c, i, k) matches Step::DeleteRecords(t) ==> t == 0,
        step_at(c, i, k) is MoveBinding ==> k == r_move(c) && c.m05_move_binding,
        i == 3 ==> r_tomb(c) < r_unlock1(c) && r_sm(c) < r_tomb(c) && r_check(c) < r_sm(c) && r_lock1(c) < r_sm(c)
            && r_unlock1(c) < r_lock2(c) && r_lock2(c) < r_cnlf(c) && r_cnlf(c) < r_unlock2(c) && r_unlock2(c) + 1 == r_len(c)
            && (has_clear(c) ==> r_cnlf(c) < r_clear(c) && r_clear(c) < r_unlock2(c))
            && (!early(c) ==> r_cnlf(c) < r_rcpt(c) && r_rcpt(c) < r_unlock2(c) && (has_clear(c) ==> r_clear(c) < r_rcpt(c)))
            && (early(c) ==> r_sm(c) < r_rcpt(c) && r_rcpt(c) < r_tomb(c))
            && (c.m05_move_binding ==> r_tomb(c) < r_move(c) && r_move(c) < r_unlock1(c)),
{
}

pub proof fn lemma_init<O: SysDesign>()
    ensures inv_base::<O>(sys_s0()),
{
    let c = O::cfg();
    let s = sys_s0();
    assert forall|i: nat| i < 4 implies #[trigger] pc_ok(c, i, s.pc[i as int]) by {
        assert(s.pc[i as int] == Pc::At(0));
    }
    assert forall|i: nat| i < 4 implies ((s.lock == Some(i)) == #[trigger] holding(c, s, i)) by {
        assert(s.pc[i as int] == Pc::At(0));
    }
    assert(s.pc[3] == Pc::At(0));
    assert(s.pc[0] == Pc::At(0));
}

/// The step of process i in state s (when enabled), unfolded.
pub proof fn lemma_run_shape<O: SysDesign>(s: SS, i: nat)
    requires inv_base::<O>(s), sys_step::<O>(s, SA::Run(i)) is Some,
    ensures ({
        let c = O::cfg();
        let k = pc_k(s.pc[i as int]);
        let st = step_at(c, i, k);
        let u = effect(c, s, i, st);
        let t = sys_step::<O>(s, SA::Run(i))->0;
        &&& i < 4 && s.pc[i as int] == Pc::At(k) && k < len_of(c, i)
        &&& !(st is Lock && s.lock is Some && s.lock != Some(i))
        &&& t == match next_pc(s, i, k, st) {
                Pc::At(n) => if n >= len_of(c, i) { finish(u, i, Pc::Done) } else { SS { pc: u.pc.update(i as int, Pc::At(n)), ..u } },
                other => finish(u, i, other),
            }
    }),
{
}

/// What a step of process i does to the program counters, the lock, the marker and the receipt.
pub proof fn lemma_frame(c: SysCfg, s: SS, i: nat, st: Step)
    ensures ({
        let u = effect(c, s, i, st);
        &&& u.pc == s.pc
        &&& u.lock == (if st is Lock { Some(i) } else if st is Unlock { if s.lock == Some(i) { None } else { s.lock } } else { s.lock })
        &&& u.marker == (match st {
                Step::SetMarker(t) => if s.marker is None { Some((t, i)) } else { s.marker },
                Step::ClearOwn => match s.marker { Some((_, o)) => if o == i { None } else { s.marker }, None => None },
                Step::ClearAny => None,
                _ => s.marker,
            })
        &&& u.receipt == (st is Receipt || s.receipt)
        &&& u.partial == s.partial && u.reply == (match st {
                Step::CheckMarker(t) => if marked_other(s, t, i) && i == 0 { Reply::Refused } else { s.reply },
                Step::Apply(_, keyed) | Step::ApplyProp(_, keyed) =>
                    if keyed && s.bind is Bound { Reply::Replay } else if keyed && s.bind is Redacted { Reply::Refused } else { Reply::First },
                _ => s.reply,
            })
    }),
{
    reveal(effect);
}

/// A commit applies (it is not answered by a replay or a refusal of its key).
pub open spec fn applies(s: SS, keyed: bool) -> bool { !(keyed && (s.bind is Bound || s.bind is Redacted)) }
pub open spec fn post_runs(c: SysCfg, s: SS) -> bool { s.reply is First || (s.reply is Replay && post_always(c)) }

/// The step's effect on the tenants' stores and records.
pub proof fn lemma_effect_data(c: SysCfg, s: SS, i: nat, st: Step)
    ensures ({
        let u = effect(c, s, i, st);
        &&& u.content == (match st {
                Step::CheckMarkerBad(t) => if marked_other(s, t, i) { s.content.update(t as int, true) } else { s.content },
                Step::Apply(t, keyed) | Step::ApplyProp(t, keyed) => if applies(s, keyed) { s.content.update(t as int, true) } else { s.content },
                Step::ApplyUnrecorded(t) => s.content.update(t as int, true),
                Step::EraseBoth(t, _) | Step::EraseContent(t) => s.content.update(t as int, false),
                _ => s.content,
            })
        &&& u.prop == (match st {
                Step::ApplyProp(t, keyed) => if applies(s, keyed) { s.prop.update(t as int, true) } else { s.prop },
                Step::ApplyUnrecorded(t) => s.prop.update(t as int, true),
                Step::Post(t) => if post_runs(c, s) { s.prop.update(t as int, true) } else { s.prop },
                Step::EraseBoth(t, _) | Step::EraseProp(t) => s.prop.update(t as int, false),
                _ => s.prop,
            })
        &&& u.der == (match st {
                Step::Apply(t, keyed) | Step::ApplyProp(t, keyed) => if applies(s, keyed) { s.der.update(t as int, true) } else { s.der },
                Step::ApplyUnrecorded(t) => s.der.update(t as int, true),
                Step::EraseBoth(t, maint) => if maint { s.der.update(t as int, false) } else { s.der },
                Step::EraseContent(t) => s.der.update(t as int, false),
                _ => s.der,
            })
        &&& u.recs == (match st {
                Step::Apply(t, keyed) | Step::ApplyProp(t, keyed) =>
                    if applies(s, keyed) { s.recs.update(t as int, s.recs[t as int].push(true)) } else { s.recs },
                Step::TombAll(t) => s.recs.update(t as int, tomb_seq(s.recs[t as int])),
                Step::TombAllAny => s.recs.update(0, tomb_seq(s.recs[0])).update(1, tomb_seq(s.recs[1])),
                Step::DeleteRecords(t) => s.recs.update(t as int, Seq::<bool>::empty()),
                _ => s.recs,
            })
    }),
{
    reveal(effect);
}

/// The step's effect on the retry binding, the effect counters and the receipt flags.
pub proof fn lemma_effect_binding(c: SysCfg, s: SS, i: nat, st: Step)
    ensures ({
        let u = effect(c, s, i, st);
        &&& u.bind == (match st {
                Step::Apply(_, keyed) | Step::ApplyProp(_, keyed) => if applies(s, keyed) && keyed { Bind::Bound } else { s.bind },
                Step::MoveBinding => if s.bind is Bound { Bind::Redacted } else { s.bind },
                _ => s.bind,
            })
        &&& u.effects == (match st {
                Step::Apply(_, keyed) | Step::ApplyProp(_, keyed) => if applies(s, keyed) && keyed { s.effects + 1 } else { s.effects },
                _ => s.effects,
            })
        &&& u.posts == (match st {
                Step::ApplyProp(_, keyed) => if applies(s, keyed) { s.posts + 1 } else { s.posts },
                Step::Post(_) => if post_runs(c, s) { s.posts + 1 } else { s.posts },
                _ => s.posts,
            })
        &&& u.after_receipt == (match st {
                Step::Apply(t, keyed) | Step::ApplyProp(t, keyed) => if applies(s, keyed) && t == 0 && s.receipt { true } else { s.after_receipt },
                Step::ApplyUnrecorded(t) => if t == 0 && s.receipt { true } else { s.after_receipt },
                Step::Receipt => false,
                _ => s.after_receipt,
            })
        &&& u.revived == (match st {
                Step::Post(_) => if post_runs(c, s) && s.reply is Replay && s.e_done && !s.fresh_a { true } else { s.revived },
                _ => s.revived,
            })
        &&& u.e_done == (st is EraseBoth || st is EraseProp || s.e_done)
        &&& u.fresh_a == (match st {
                Step::Apply(t, keyed) | Step::ApplyProp(t, keyed) => if applies(s, keyed) && t == 0 { true } else { s.fresh_a },
                Step::ApplyUnrecorded(t) => if t == 0 { true } else { s.fresh_a },
                Step::EraseBoth(t, _) | Step::EraseProp(t) => if t == 0 { false } else { s.fresh_a },
                _ => s.fresh_a,
            })
    }),
{
    reveal(effect);
}

/// A final liveness check parks its process at the check's back position.
pub open spec fn parked_by(st: Step, np: Pc) -> bool {
    match st { Step::CheckNotLiveFinal(_, b) => np == Pc::Parked(b), _ => false }
}

/// The successor of a Run step, by the next program counter.
pub open spec fn after(c: SysCfg, s: SS, i: nat, k: nat, st: Step) -> SS {
    let u = effect(c, s, i, st);
    match next_pc(s, i, k, st) {
        Pc::At(n) => if n >= len_of(c, i) { finish(u, i, Pc::Done) } else { SS { pc: u.pc.update(i as int, Pc::At(n)), ..u } },
        other => finish(u, i, other),
    }
}

/// The new program counter of the stepping process.
pub open spec fn new_pc(c: SysCfg, s: SS, i: nat, k: nat, st: Step) -> Pc {
    match next_pc(s, i, k, st) { Pc::At(n) => if n >= len_of(c, i) { Pc::Done } else { Pc::At(n) }, other => other }
}

pub proof fn lemma_after(c: SysCfg, s: SS, i: nat, k: nat, st: Step)
    requires wf_shape(s), i < 4,
    ensures ({
        let u = effect(c, s, i, st);
        let t = after(c, s, i, k, st);
        let np = new_pc(c, s, i, k, st);
        &&& t.pc == s.pc.update(i as int, np)
        &&& t.lock == (if np is At { u.lock } else if u.lock == Some(i) { None } else { u.lock })
        &&& t.marker == u.marker && t.receipt == u.receipt
        &&& (np is At ==> np == Pc::At(k + 1))
        &&& (np is Parked ==> parked_by(st, np))
        &&& (np is Refused ==> st is CheckMarker || st is CheckMarkerBad || st is CheckNotLive)
    }),
{
    lemma_frame(c, s, i, st);
}

pub proof fn lemma_base_run<O: SysDesign>(s: SS, i: nat)
    requires inv_base::<O>(s), sys_step::<O>(s, SA::Run(i)) is Some,
    ensures inv_base::<O>(sys_step::<O>(s, SA::Run(i))->0),
{
    let c = O::cfg();
    lemma_run_shape::<O>(s, i);
    let k = pc_k(s.pc[i as int]);
    let st = step_at(c, i, k);
    let t = sys_step::<O>(s, SA::Run(i))->0;
    assert(t == after(c, s, i, k, st));
    lemma_after(c, s, i, k, st);
    lemma_effect_data(c, s, i, st);
    lemma_effect_binding(c, s, i, st);
    lemma_frame(c, s, i, st);
    lemma_positions(c, i, k);
    let np = new_pc(c, s, i, k, st);
    assert(pc_ok(c, i, s.pc[i as int]));
    assert(holding(c, s, i) == (s.lock == Some(i)));
    lemma_base_run_pcs::<O>(s, i, k, st, t, np);
    lemma_base_run_lock::<O>(s, i, k, st, t, np);
    lemma_base_run_marker::<O>(s, i, k, st, t, np);
}

proof fn lemma_base_run_pcs<O: SysDesign>(s: SS, i: nat, k: nat, st: Step, t: SS, np: Pc)
    requires
        inv_base::<O>(s), i < 4, s.pc[i as int] == Pc::At(k), k < len_of(O::cfg(), i), st == step_at(O::cfg(), i, k),
        t.pc == s.pc.update(i as int, np), np == new_pc(O::cfg(), s, i, k, st),
        np is At ==> np == Pc::At(k + 1),
        np is Parked ==> parked_by(st, np),
        np is Refused ==> st is CheckMarker || st is CheckMarkerBad || st is CheckNotLive,
    ensures forall|j: nat| j < 4 ==> #[trigger] pc_ok(O::cfg(), j, t.pc[j as int]),
{
    let c = O::cfg();
    lemma_positions(c, i, k);
    assert forall|j: nat| j < 4 implies #[trigger] pc_ok(c, j, t.pc[j as int]) by {
        if j != i { assert(pc_ok(c, j, s.pc[j as int])); }
    }
}

proof fn lemma_base_run_lock<O: SysDesign>(s: SS, i: nat, k: nat, st: Step, t: SS, np: Pc)
    requires
        inv_base::<O>(s), i < 4, s.pc[i as int] == Pc::At(k), k < len_of(O::cfg(), i), st == step_at(O::cfg(), i, k),
        !(st is Lock && s.lock is Some && s.lock != Some(i)),
        t.pc == s.pc.update(i as int, np), np == new_pc(O::cfg(), s, i, k, st),
        t.lock == (if np is At { effect(O::cfg(), s, i, st).lock } else if effect(O::cfg(), s, i, st).lock == Some(i) { None }
                   else { effect(O::cfg(), s, i, st).lock }),
        effect(O::cfg(), s, i, st).lock == (if st is Lock { Some(i) } else if st is Unlock { if s.lock == Some(i) { None } else { s.lock } } else { s.lock }),
        np is At ==> np == Pc::At(k + 1),
    ensures
        forall|j: nat| j < 4 ==> ((t.lock == Some(j)) == #[trigger] holding(O::cfg(), t, j)),
        t.lock is Some ==> t.lock->0 < 4,
{
    let c = O::cfg();
    lemma_positions(c, i, k);
    assert(holding(c, s, i) == (s.lock == Some(i)));
    if st is Lock {
        // the process holds nothing at a Lock step, so the lock is free
        assert(s.lock == None::<nat>);
    }
    assert forall|j: nat| j < 4 implies ((t.lock == Some(j)) == #[trigger] holding(c, t, j)) by {
        if j != i {
            assert(t.pc[j as int] == s.pc[j as int]);
            assert(holding(c, s, j) == (s.lock == Some(j)));
        }
    }
}

proof fn lemma_base_run_marker<O: SysDesign>(s: SS, i: nat, k: nat, st: Step, t: SS, np: Pc)
    requires
        inv_base::<O>(s), i < 4, s.pc[i as int] == Pc::At(k), k < len_of(O::cfg(), i), st == step_at(O::cfg(), i, k),
        !(st is Lock && s.lock is Some && s.lock != Some(i)),
        t.pc == s.pc.update(i as int, np), np == new_pc(O::cfg(), s, i, k, st),
        t.marker == effect(O::cfg(), s, i, st).marker, t.receipt == effect(O::cfg(), s, i, st).receipt,
        effect(O::cfg(), s, i, st).marker == (match st {
            Step::SetMarker(x) => if s.marker is None { Some((x, i)) } else { s.marker },
            Step::ClearOwn => match s.marker { Some((_, o)) => if o == i { None } else { s.marker }, None => None },
            Step::ClearAny => None,
            _ => s.marker,
        }),
        effect(O::cfg(), s, i, st).receipt == (st is Receipt || s.receipt),
        np is At ==> np == Pc::At(k + 1),
        np is Parked ==> parked_by(st, np),
        np is Refused ==> st is CheckMarker || st is CheckMarkerBad || st is CheckNotLive,
        forall|j: nat| j < 4 ==> ((t.lock == Some(j)) == #[trigger] holding(O::cfg(), t, j)),
    ensures
        t.marker == (if r_marked(O::cfg(), t.pc[3]) { Some((0nat, 3nat)) } else { None }),
        t.receipt == r_past_receipt(O::cfg(), t.pc[3]),
        w_at_apply(O::cfg(), t) ==> t.marker is None,
{
    let c = O::cfg();
    lemma_positions(c, i, k);
    lemma_positions(c, 3, r_sm(c));
    assert(pc_ok(c, 3, s.pc[3]));
    if i != 3 {
        assert(t.pc[3] == s.pc[3]);
    }
    if i == 0 && w_at_apply(c, t) {
        // W just passed its marker check (or was there already: then it held the lock, so no SetMarker ran)
        assert(t.pc[0] == np);
    }
    if i != 0 && w_at_apply(c, t) {
        assert(t.pc[0] == s.pc[0]);
        assert(holding(c, s, 0));
        if st is SetMarker { assert(s.lock == Some(0nat)); assert(holding(c, s, i)); }
    }
}

pub proof fn lemma_base_step<O: SysDesign>(s: SS, a: SA)
    requires inv_base::<O>(s), sys_step::<O>(s, a) is Some,
    ensures inv_base::<O>(sys_step::<O>(s, a)->0),
{
    let c = O::cfg();
    let t = sys_step::<O>(s, a)->0;
    match a {
        SA::Run(i) => { lemma_base_run::<O>(s, i); },
        SA::StopE => {
            let k = pc_k(s.pc[2]);
            lemma_positions(c, 2, k);
            assert(pc_ok(c, 2, s.pc[2]));
            assert forall|j: nat| j < 4 implies #[trigger] pc_ok(c, j, t.pc[j as int]) by {
                if j != 2 { assert(pc_ok(c, j, s.pc[j as int])); }
            }
            assert forall|j: nat| j < 4 implies ((t.lock == Some(j)) == #[trigger] holding(c, t, j)) by {
                assert(holding(c, s, j) == (s.lock == Some(j)));
            }
            assert(t.pc[3] == s.pc[3] && t.pc[0] == s.pc[0]);
        },
        SA::ReErase => {
            assert forall|j: nat| j < 4 implies #[trigger] pc_ok(c, j, t.pc[j as int]) by {
                if j != 2 { assert(pc_ok(c, j, s.pc[j as int])); }
            }
            assert forall|j: nat| j < 4 implies ((t.lock == Some(j)) == #[trigger] holding(c, t, j)) by {
                assert(holding(c, s, j) == (s.lock == Some(j)));
            }
            assert(t.pc[3] == s.pc[3] && t.pc[0] == s.pc[0]);
        },
        SA::Resume => {
            lemma_positions(c, 3, r_lock2(c));
            assert(pc_ok(c, 3, s.pc[3]));
            assert forall|j: nat| j < 4 implies #[trigger] pc_ok(c, j, t.pc[j as int]) by {
                if j != 3 { assert(pc_ok(c, j, s.pc[j as int])); }
            }
            assert forall|j: nat| j < 4 implies ((t.lock == Some(j)) == #[trigger] holding(c, t, j)) by {
                assert(holding(c, s, j) == (s.lock == Some(j)));
            }
            assert(t.pc[0] == s.pc[0]);
        },
    }
}

pub proof fn theorem_base<O: SysDesign>(s0: SS, ls: Seq<SA>, t: SS)
    requires reached::<SysM<O>>(s0, ls, t),
    ensures inv_base::<O>(t),
{
    lemma_init::<O>();
    let inv = |s: SS| inv_base::<O>(s);
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SysM::<O>::step(x, a)) is Some implies inv(SysM::<O>::step(x, a)->0) by {
        lemma_base_step::<O>(x, a);
    }
    lemma_reached_inv::<SysM<O>>(inv, s0, ls, t);
}

} // verus!
