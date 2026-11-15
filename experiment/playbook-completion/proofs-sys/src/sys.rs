//! Module 00: the composed mechanisms (the semantics lane's `models/semantics/src/sys00.rs`, read at its commit
//! 50911c4a, SHA-256 ca7c21e7...), restated in Verus and made generic over the composed mechanisms' instances.
//!
//! One machine composes M-01 (ledger commit with record), M-02 (retry binding and post-commit step), M-03 (head lock
//! and redaction marker), M-04 (a derived store kept with the content), M-05 (erasure and redaction reach) and M-10
//! (all-or-none steps and inert refusals) over two tenants, A (0) and B (1). Four processes run their step programs,
//! interleaved in every order (W 0: a client committing A's content with a retry key, then retrying once; C 1: a
//! commit of B's content; E 2: erasure of A; R 3: redaction of A), plus the operator's actions (stop the erasure
//! between its two steps, re-run the erasure, resume a parked redaction). The stores are shared as the semantics
//! lane's objects declare them: content, properties and derived entries per tenant, the ledger's records per tenant,
//! the retry binding, the head lock, the marker and the receipt.
//!
//! **The design trait.** The explorer fixes 13 designs (reviewed, as built, one mutant per axiom), each a set of four
//! programs. Here a design is the choice of one instance per composed mechanism (`SysCfg`): M-01 whether the first
//! commit records its change; M-02 whether post-commit properties are written in the commit or by a separate step that
//! also runs on a replay; M-03 how the redaction section is locked and its marker cleared, and whether the eraser takes
//! the head lock; M-04 whether erasure maintains the derived store; M-05 which records the redaction tombstones,
//! whether it moves the retry binding, and when it writes the receipt; M-10 whether a refusal writes, and whether the
//! erasure is one step or two stoppable steps. The programs are computed from the choices (`step_at`, `len_of`), and
//! each explorer design is exactly one choice vector (src/inst.rs). The laws are the explorer's axiom checks.
//!
//! Representation (an exact abstraction for every law): the ledger's records are kept per tenant (`recs[t]`, in commit
//! order) instead of one list of (tenant, live) pairs; every operation (append, tombstone, delete) acts on one
//! tenant's records, and every law reads one tenant's records, so AX-05's global form and its per-tenant form agree.
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;

verus! {

pub enum Step {
    Lock, Unlock,
    CheckMarker(nat), CheckMarkerBad(nat), CheckNotLive(nat), CheckNotLiveFinal(nat, nat),
    SetMarker(nat), ClearOwn, ClearAny,
    Apply(nat, bool), ApplyProp(nat, bool), ApplyUnrecorded(nat), Post(nat),
    EraseBoth(nat, bool), EraseContent(nat), EraseProp(nat),
    TombAll(nat), TombAllAny, DeleteRecords(nat), MoveBinding, Receipt,
}

pub enum Pc { At(nat), Done, Refused, Parked(nat) }
pub enum Bind { Free, Bound, Redacted }
pub enum Reply { NoReply, First, Replay, Refused }

pub struct SS {
    pub pc: Seq<Pc>,
    pub lock: Option<nat>,
    pub marker: Option<(nat, nat)>,
    pub content: Seq<bool>,
    pub prop: Seq<bool>,
    pub der: Seq<bool>,
    pub recs: Seq<Seq<bool>>,
    pub bind: Bind,
    pub effects: nat,
    pub posts: nat,
    pub reply: Reply,
    pub receipt: bool,
    pub partial: bool,
    pub e_done: bool,
    pub fresh_a: bool,
    /// a fresh commit into tenant A after the receipt (re-onboarding)
    pub after_receipt: bool,
    /// a replayed answer's post-commit write re-created erased content (no fresh commit since the erasure)
    pub revived: bool,
}

pub enum SA { Run(nat), StopE, ReErase, Resume }

// ------------------------------------------------------------------------------------------------ the design trait

/// M-02 instance: post-commit properties written in the commit (reviewed), or by a separate step after each ok
/// answer that also runs on a replay (ledger-key as built, client.py:418-487).
pub enum M02Post { InCommit, SeparateAlways }
/// M-03 instance of the redaction section: reviewed (check, marker and tombstones in one locked section, Final clears
/// its own marker); as built (unlocked liveness check, Final clears any marker, LedgerRedact.cls:185-430); the
/// check-before-lock mutant (own marker); the never-cleared mutant.
pub enum M03Redact { Reviewed, AsBuilt, CheckBeforeLock, NeverCleared }
/// M-05 instance: what the redaction does to the target's records.
pub enum M05Tomb { Own, Any, Delete }
pub enum M05Receipt { Final, Early }
/// M-10 instance: a refusal is inert (reviewed) or writes content (mutant).
pub enum M10Refusal { Inert, Writes }

pub struct SysCfg {
    /// M-01: the first commit records its change (false: the unrecorded-apply mutant)
    pub m01_recorded: bool,
    pub m02_post: M02Post,
    pub m03_redact: M03Redact,
    /// M-03: the eraser takes the head lock (false as built, Eraser.cls:665-678)
    pub m03_erase_locked: bool,
    /// M-04: erasure maintains the derived store (false as built: F-0702, F-0606 family)
    pub m04_erase_maintains: bool,
    pub m05_tomb: M05Tomb,
    /// M-05: redaction moves the retry binding to redacted
    pub m05_move_binding: bool,
    pub m05_receipt: M05Receipt,
    pub m10_refusal: M10Refusal,
    /// M-10: erasure in two stoppable steps (content, then properties) instead of one
    pub m10_erase_split: bool,
}

pub trait SysDesign: Sized {
    spec fn cfg() -> SysCfg;
}

// ------------------------------------------------------------------------------------------------ the programs

pub open spec fn sep(c: SysCfg) -> nat { if c.m02_post is SeparateAlways { 1 } else { 0 } }
pub open spec fn post_always(c: SysCfg) -> bool { c.m02_post is SeparateAlways }
pub open spec fn stoppable_e(c: SysCfg) -> bool { c.m10_erase_split }

/// W: [Lock, check, apply, Unlock] (Post) [Lock, CheckMarker, apply, Unlock] (Post)
pub open spec fn w_len(c: SysCfg) -> nat { 8 + 2 * sep(c) }
pub open spec fn w_apply1(c: SysCfg) -> nat { 2 }
pub open spec fn w_apply2(c: SysCfg) -> nat { 6 + sep(c) }
pub open spec fn w_step(c: SysCfg, k: nat) -> Step {
    let s = sep(c);
    if k == 0 { Step::Lock }
    else if k == 1 { if c.m10_refusal is Writes { Step::CheckMarkerBad(0) } else { Step::CheckMarker(0) } }
    else if k == 2 {
        if !c.m01_recorded { Step::ApplyUnrecorded(0) }
        else if c.m02_post is InCommit { Step::ApplyProp(0, true) } else { Step::Apply(0, true) }
    }
    else if k == 3 { Step::Unlock }
    else if s == 1 && k == 4 { Step::Post(0) }
    else if k == 4 + s { Step::Lock }
    else if k == 5 + s { Step::CheckMarker(0) }
    else if k == 6 + s { if c.m02_post is InCommit { Step::ApplyProp(0, true) } else { Step::Apply(0, true) } }
    else if k == 7 + s { Step::Unlock }
    else { Step::Post(0) }
}
pub open spec fn w_holds(c: SysCfg, k: nat) -> bool { (1 <= k <= 3) || (5 + sep(c) <= k && k <= 7 + sep(c)) }

pub open spec fn c_step(k: nat) -> Step {
    if k == 0 { Step::Lock } else if k == 1 { Step::CheckMarker(1) } else if k == 2 { Step::Apply(1, false) } else { Step::Unlock }
}
pub open spec fn c_holds(k: nat) -> bool { 1 <= k <= 3 }

/// E: (Lock) EraseBoth | EraseContent EraseProp (Unlock)
pub open spec fn e_lk(c: SysCfg) -> nat { if c.m03_erase_locked { 1 } else { 0 } }
pub open spec fn e_body(c: SysCfg) -> nat { if c.m10_erase_split { 2 } else { 1 } }
pub open spec fn e_len(c: SysCfg) -> nat { e_body(c) + 2 * e_lk(c) }
pub open spec fn e_step(c: SysCfg, k: nat) -> Step {
    let l = e_lk(c);
    if l == 1 && k == 0 { Step::Lock }
    else if l == 1 && k == e_len(c) - 1 { Step::Unlock }
    else if c.m10_erase_split { if k == l { Step::EraseContent(0) } else { Step::EraseProp(0) } }
    else { Step::EraseBoth(0, c.m04_erase_maintains) }
}
pub open spec fn e_holds(c: SysCfg, k: nat) -> bool { c.m03_erase_locked && 1 <= k && k + 1 <= e_len(c) }

/// R: positions of its steps (the check before or after the first lock; an early receipt; no MoveBinding; no clear).
pub open spec fn check_first(c: SysCfg) -> bool { c.m03_redact is AsBuilt || c.m03_redact is CheckBeforeLock }
pub open spec fn has_clear(c: SysCfg) -> bool { !(c.m03_redact is NeverCleared) }
pub open spec fn early(c: SysCfg) -> bool { c.m05_receipt is Early }
pub open spec fn mv(c: SysCfg) -> nat { if c.m05_move_binding { 1 } else { 0 } }
pub open spec fn r_check(c: SysCfg) -> nat { if check_first(c) { 0 } else { 1 } }
pub open spec fn r_lock1(c: SysCfg) -> nat { if check_first(c) { 1 } else { 0 } }
pub open spec fn r_sm(c: SysCfg) -> nat { 2 }
pub open spec fn r_tomb(c: SysCfg) -> nat { if early(c) { 4 } else { 3 } }
pub open spec fn r_move(c: SysCfg) -> nat { r_tomb(c) + 1 }
pub open spec fn r_unlock1(c: SysCfg) -> nat { r_tomb(c) + 1 + mv(c) }
pub open spec fn r_lock2(c: SysCfg) -> nat { r_unlock1(c) + 1 }
pub open spec fn r_cnlf(c: SysCfg) -> nat { r_lock2(c) + 1 }
pub open spec fn r_clear(c: SysCfg) -> nat { r_cnlf(c) + 1 }
pub open spec fn r_rcpt(c: SysCfg) -> nat { if early(c) { 3 } else { r_cnlf(c) + 1 + (if has_clear(c) { 1nat } else { 0 }) } }
pub open spec fn r_unlock2(c: SysCfg) -> nat { r_cnlf(c) + 1 + (if has_clear(c) { 1nat } else { 0 }) + (if early(c) { 0nat } else { 1 }) }
pub open spec fn r_len(c: SysCfg) -> nat { r_unlock2(c) + 1 }
pub open spec fn r_step(c: SysCfg, k: nat) -> Step {
    if k == r_check(c) { Step::CheckNotLive(0) }
    else if k == r_lock1(c) || k == r_lock2(c) { Step::Lock }
    else if k == r_sm(c) { Step::SetMarker(0) }
    else if early(c) && k == 3 { Step::Receipt }
    else if k == r_tomb(c) {
        match c.m05_tomb { M05Tomb::Own => Step::TombAll(0), M05Tomb::Any => Step::TombAllAny, M05Tomb::Delete => Step::DeleteRecords(0) }
    }
    else if c.m05_move_binding && k == r_move(c) { Step::MoveBinding }
    else if k == r_unlock1(c) || k == r_unlock2(c) { Step::Unlock }
    else if k == r_cnlf(c) { Step::CheckNotLiveFinal(0, r_lock2(c)) }
    else if has_clear(c) && k == r_clear(c) { if c.m03_redact is AsBuilt { Step::ClearAny } else { Step::ClearOwn } }
    else { Step::Receipt }
}
pub open spec fn r_holds(c: SysCfg, k: nat) -> bool {
    (r_lock1(c) < k && k <= r_unlock1(c)) || (r_lock2(c) < k && k <= r_unlock2(c))
}

pub open spec fn len_of(c: SysCfg, i: nat) -> nat {
    if i == 0 { w_len(c) } else if i == 1 { 4 } else if i == 2 { e_len(c) } else { r_len(c) }
}
pub open spec fn step_at(c: SysCfg, i: nat, k: nat) -> Step {
    if i == 0 { w_step(c, k) } else if i == 1 { c_step(k) } else if i == 2 { e_step(c, k) } else { r_step(c, k) }
}
/// Process i at position k is inside one of its locked sections (it holds the head lock there).
pub open spec fn holds_at(c: SysCfg, i: nat, k: nat) -> bool {
    if i == 0 { w_holds(c, k) } else if i == 1 { c_holds(k) } else if i == 2 { e_holds(c, k) } else { r_holds(c, k) }
}

// ------------------------------------------------------------------------------------------------ the machine

pub open spec fn sys_s0() -> SS {
    SS {
        pc: seq![Pc::At(0), Pc::At(0), Pc::At(0), Pc::At(0)],
        lock: None, marker: None,
        content: seq![false, false], prop: seq![false, false], der: seq![false, false],
        recs: seq![Seq::<bool>::empty(), Seq::<bool>::empty()],
        bind: Bind::Free, effects: 0, posts: 0, reply: Reply::NoReply,
        receipt: false, partial: false, e_done: false, fresh_a: false, after_receipt: false, revived: false,
    }
}

pub open spec fn finish(u: SS, i: nat, p: Pc) -> SS {
    SS { pc: u.pc.update(i as int, p), lock: if u.lock == Some(i) { None } else { u.lock }, ..u }
}

pub open spec fn marked_other(s: SS, t: nat, i: nat) -> bool {
    match s.marker { Some((m, o)) => m == t && o != i, None => false }
}
pub open spec fn live(s: SS, t: nat) -> bool { s.content[t as int] || s.prop[t as int] }
pub open spec fn tomb_seq(r: Seq<bool>) -> Seq<bool> { Seq::new(r.len(), |k: int| false) }

/// The effect of process i's step `st` (the explorer's `match step`), before the program counter moves. Opaque: the
/// proofs use its closed forms (src/base.rs `lemma_frame`, `lemma_effect_data`, `lemma_effect_binding`).
#[verifier::opaque]
pub open spec fn effect(c: SysCfg, s: SS, i: nat, st: Step) -> SS {
    match st {
        Step::Lock => SS { lock: Some(i), ..s },
        Step::Unlock => SS { lock: if s.lock == Some(i) { None } else { s.lock }, ..s },
        Step::CheckMarker(t) => if marked_other(s, t, i) && i == 0 { SS { reply: Reply::Refused, ..s } } else { s },
        Step::CheckMarkerBad(t) => if marked_other(s, t, i) { SS { content: s.content.update(t as int, true), ..s } } else { s },
        Step::SetMarker(t) => if s.marker is None { SS { marker: Some((t, i)), ..s } } else { s },
        Step::ClearOwn => match s.marker { Some((_, o)) => if o == i { SS { marker: None, ..s } } else { s }, None => s },
        Step::ClearAny => SS { marker: None, ..s },
        Step::Apply(t, keyed) | Step::ApplyProp(t, keyed) => {
            let with_prop = st is ApplyProp;
            if keyed && s.bind is Bound { SS { reply: Reply::Replay, ..s } }
            else if keyed && s.bind is Redacted { SS { reply: Reply::Refused, ..s } }
            else {
                SS {
                    content: s.content.update(t as int, true),
                    der: s.der.update(t as int, true),
                    recs: s.recs.update(t as int, s.recs[t as int].push(true)),
                    prop: if with_prop { s.prop.update(t as int, true) } else { s.prop },
                    posts: if with_prop { s.posts + 1 } else { s.posts },
                    bind: if keyed { Bind::Bound } else { s.bind },
                    effects: if keyed { s.effects + 1 } else { s.effects },
                    reply: Reply::First,
                    fresh_a: if t == 0 { true } else { s.fresh_a },
                    after_receipt: if t == 0 && s.receipt { true } else { s.after_receipt },
                    ..s
                }
            }
        },
        Step::ApplyUnrecorded(t) => SS {
            content: s.content.update(t as int, true),
            der: s.der.update(t as int, true),
            prop: s.prop.update(t as int, true),
            fresh_a: if t == 0 { true } else { s.fresh_a },
            after_receipt: if t == 0 && s.receipt { true } else { s.after_receipt },
            ..s
        },
        Step::Post(t) => {
            let runs = s.reply is First || (s.reply is Replay && post_always(c));
            if runs {
                SS {
                    prop: s.prop.update(t as int, true),
                    posts: s.posts + 1,
                    revived: if s.reply is Replay && s.e_done && !s.fresh_a { true } else { s.revived },
                    ..s
                }
            } else { s }
        },
        Step::EraseBoth(t, maint) => SS {
            content: s.content.update(t as int, false),
            prop: s.prop.update(t as int, false),
            der: if maint { s.der.update(t as int, false) } else { s.der },
            e_done: true,
            fresh_a: if t == 0 { false } else { s.fresh_a },
            ..s
        },
        Step::EraseContent(t) => SS { content: s.content.update(t as int, false), der: s.der.update(t as int, false), ..s },
        Step::EraseProp(t) => SS {
            prop: s.prop.update(t as int, false), e_done: true, fresh_a: if t == 0 { false } else { s.fresh_a }, ..s
        },
        Step::TombAll(t) => SS { recs: s.recs.update(t as int, tomb_seq(s.recs[t as int])), ..s },
        Step::TombAllAny => SS { recs: s.recs.update(0, tomb_seq(s.recs[0])).update(1, tomb_seq(s.recs[1])), ..s },
        Step::DeleteRecords(t) => SS { recs: s.recs.update(t as int, Seq::<bool>::empty()), ..s },
        Step::MoveBinding => if s.bind is Bound { SS { bind: Bind::Redacted, ..s } } else { s },
        Step::Receipt => SS { receipt: true, after_receipt: false, ..s },
        _ => s,
    }
}

/// Where the process goes after the step: on, refused, or parked (back to an earlier position).
pub open spec fn next_pc(s: SS, i: nat, k: nat, st: Step) -> Pc {
    match st {
        Step::CheckMarker(t) | Step::CheckMarkerBad(t) => if marked_other(s, t, i) { Pc::Refused } else { Pc::At(k + 1) },
        Step::CheckNotLive(t) => if live(s, t) { Pc::Refused } else { Pc::At(k + 1) },
        Step::CheckNotLiveFinal(t, back) => if live(s, t) { Pc::Parked(back) } else { Pc::At(k + 1) },
        _ => Pc::At(k + 1),
    }
}

pub open spec fn wf_shape(s: SS) -> bool {
    s.pc.len() == 4 && s.content.len() == 2 && s.prop.len() == 2 && s.der.len() == 2 && s.recs.len() == 2
}

/// The composed step for design parameters `c` (non-generic, so concrete runs can be evaluated).
pub open spec fn step_cfg(c: SysCfg, s: SS, a: SA) -> Option<SS> {
    if !wf_shape(s) { None } else {
    match a {
        SA::StopE => {
            match s.pc[2] {
                Pc::At(k) => if stoppable_e(c) && k < e_len(c) && e_step(c, k) is EraseProp {
                    Some(finish(SS { partial: true, ..s }, 2, Pc::Done))
                } else { None },
                _ => None,
            }
        },
        SA::ReErase => if s.pc[2] is Done && live(s, 0) { Some(SS { pc: s.pc.update(2, Pc::At(0)), ..s }) } else { None },
        SA::Resume => match s.pc[3] { Pc::Parked(k) => Some(SS { pc: s.pc.update(3, Pc::At(k)), ..s }), _ => None },
        SA::Run(i) => {
            if i >= 4 { None } else {
                match s.pc[i as int] {
                    Pc::At(k) => {
                        if k >= len_of(c, i) { None } else {
                            let st = step_at(c, i, k);
                            if st is Lock && s.lock is Some && s.lock != Some(i) { None } else {
                                let u = effect(c, s, i, st);
                                match next_pc(s, i, k, st) {
                                    Pc::At(n) => if n >= len_of(c, i) { Some(finish(u, i, Pc::Done)) }
                                                 else { Some(SS { pc: u.pc.update(i as int, Pc::At(n)), ..u }) },
                                    other => Some(finish(u, i, other)),
                                }
                            }
                        }
                    },
                    _ => None,
                }
            }
        },
    }
    }
}

pub open spec fn sys_step<O: SysDesign>(s: SS, a: SA) -> Option<SS> { step_cfg(O::cfg(), s, a) }

/// A run of the composed machine for design parameters `c`.
pub open spec fn run_cfg(c: SysCfg, s: SS, ls: Seq<SA>) -> Option<SS>
    decreases ls.len(),
{
    if ls.len() == 0 { Some(s) } else {
        match step_cfg(c, s, ls[0]) { Some(t) => run_cfg(c, t, ls.drop_first()), None => None }
    }
}

pub struct SysM<O> { pub o: O }

impl<O: SysDesign> Machine for SysM<O> {
    type S = SS;
    type A = SA;
    open spec fn init(s: SS) -> bool { s == sys_s0() }
    open spec fn step(s: SS, a: SA) -> Option<SS> { sys_step::<O>(s, a) }
}

/// The step process i would take now, if any.
pub open spec fn cur_step_cfg(c: SysCfg, s: SS, i: nat) -> Option<Step> {
    if i < 4 && s.pc.len() == 4 && s.pc[i as int] is At && (s.pc[i as int]->At_0) < len_of(c, i) {
        Some(step_at(c, i, s.pc[i as int]->At_0))
    } else { None }
}
pub open spec fn cur_step<O: SysDesign>(s: SS, i: nat) -> Option<Step> { cur_step_cfg(O::cfg(), s, i) }

// ------------------------------------------------------------------------------------------------ the axioms

pub open spec fn has_live_record(r: Seq<bool>) -> bool { exists|k: int| 0 <= k < r.len() && r[k] }

pub open spec fn same_tenant(o: SS, n: SS, t: int) -> bool {
    n.content[t] == o.content[t] && n.prop[t] == o.prop[t] && n.der[t] == o.der[t] && n.recs[t] == o.recs[t]
}
pub open spec fn same_shared(o: SS, n: SS) -> bool {
    &&& n.marker == o.marker && n.content == o.content && n.prop == o.prop && n.der == o.der && n.recs == o.recs
    &&& n.bind == o.bind && n.effects == o.effects && n.posts == o.posts && n.receipt == o.receipt
    &&& n.partial == o.partial && n.e_done == o.e_done
}
pub open spec fn stopped(p: Pc) -> bool { p is Refused || p is Parked }

/// AX-02 (action): a step of the B committer leaves tenant A; every other step leaves tenant B.
pub open spec fn law_ax02(o: SS, a: SA, n: SS) -> bool {
    match a { SA::Run(i) => if i == 1 { same_tenant(o, n, 0) } else { same_tenant(o, n, 1) }, _ => same_tenant(o, n, 1) }
}
/// AX-03 (action): a step that refuses (or parks) its process changes no shared store.
pub open spec fn law_ax03(o: SS, a: SA, n: SS) -> bool {
    match a { SA::Run(i) => !(stopped(n.pc[i as int]) && !stopped(o.pc[i as int])) || same_shared(o, n), _ => true }
}
/// AX-04 (invariant): no erasure is left half done.
pub open spec fn law_ax04(s: SS) -> bool { !s.partial }
/// AX-05 (action): each tenant's records are only appended or turned into tombstones.
pub open spec fn law_ax05(o: SS, n: SS) -> bool {
    forall|t: int| 0 <= t < 2 ==> #[trigger] n.recs[t].len() >= o.recs[t].len()
        && forall|k: int| 0 <= k < o.recs[t].len() ==> (#[trigger] n.recs[t][k] == o.recs[t][k] || !n.recs[t][k])
}
/// AX-06 (invariant): one effect and one post-commit write per key.
pub open spec fn law_ax06(s: SS) -> bool { s.effects <= 1 && s.posts <= 1 }
/// AX-07 (invariant): live governed content has a live record.
pub open spec fn law_ax07(s: SS) -> bool {
    forall|t: int| 0 <= t < 2 && #[trigger] s.content[t] ==> has_live_record(s.recs[t])
}
/// AX-08 (invariant): the derived store equals the content.
pub open spec fn law_ax08(s: SS) -> bool { s.der[0] == s.content[0] && s.der[1] == s.content[1] }
/// AX-10 (invariant): after a receipt with no fresh commit into A since, A holds nothing and its key is not bound;
/// no replayed answer's post-commit write re-created erased content.
pub open spec fn law_ax10(s: SS) -> bool {
    (!s.receipt || s.after_receipt || (!s.content[0] && !s.prop[0] && !s.der[0] && !(s.bind is Bound))) && !s.revived
}
/// AX-11 (action): no tombstone of live content.
pub open spec fn law_ax11<O: SysDesign>(s: SS, i: nat) -> bool { law_ax11_cfg(O::cfg(), s, i) }
pub open spec fn law_ax11_cfg(c: SysCfg, s: SS, i: nat) -> bool {
    match cur_step_cfg(c, s, i) { Some(Step::TombAll(t)) => !s.content[t as int], _ => true }
}
/// AX-11 (invariant, the marker part): a marked target is not live.
pub open spec fn law_ax11m(s: SS) -> bool {
    match s.marker { Some((t, _)) => !s.content[t as int] && !s.prop[t as int], None => true }
}
/// AX-12 (action): a receipt is written only when no live record of the target remains.
pub open spec fn law_ax12<O: SysDesign>(s: SS, i: nat) -> bool { law_ax12_cfg(O::cfg(), s, i) }
pub open spec fn law_ax12_cfg(c: SysCfg, s: SS, i: nat) -> bool {
    match cur_step_cfg(c, s, i) { Some(Step::Receipt) => !has_live_record(s.recs[0]), _ => true }
}
/// AX-14 (AG EF): every process can finish and the marker be released.
pub open spec fn final_state(s: SS) -> bool {
    s.marker is None && forall|i: int| 0 <= i < 4 ==> (#[trigger] s.pc[i] is Done || s.pc[i] is Refused)
}
pub open spec fn law_ax14<O: SysDesign>(s: SS) -> bool {
    exists|ls: Seq<SA>| #[trigger] run::<SysM<O>>(s, ls) is Some && final_state(run::<SysM<O>>(s, ls)->0)
}

// ------------------------------------------------------------------------------------------------ obligations

/// The redaction checks liveness inside its locked section (M-03).
pub open spec fn check_in_lock(c: SysCfg) -> bool { !check_first(c) }
/// Every erasure step maintains the derived store (M-04).
pub open spec fn erase_maintains(c: SysCfg) -> bool { c.m10_erase_split || c.m04_erase_maintains }

pub open spec fn obl_ax02<O: SysDesign>() -> bool { !(O::cfg().m05_tomb is Any) }
pub open spec fn obl_ax03<O: SysDesign>() -> bool { O::cfg().m10_refusal is Inert }
pub open spec fn obl_ax04<O: SysDesign>() -> bool { !O::cfg().m10_erase_split }
pub open spec fn obl_ax05<O: SysDesign>() -> bool { !(O::cfg().m05_tomb is Delete) }
pub open spec fn obl_ax06<O: SysDesign>() -> bool { O::cfg().m02_post is InCommit }
pub open spec fn obl_ax07<O: SysDesign>() -> bool {
    let c = O::cfg();
    c.m01_recorded && c.m10_refusal is Inert && !(c.m05_tomb is Any) && check_in_lock(c)
}
pub open spec fn obl_ax08<O: SysDesign>() -> bool { erase_maintains(O::cfg()) && O::cfg().m10_refusal is Inert }
pub open spec fn obl_ax10<O: SysDesign>() -> bool {
    let c = O::cfg();
    erase_maintains(c) && c.m02_post is InCommit && c.m05_move_binding && c.m05_receipt is Final
        && (c.m10_refusal is Inert || has_clear(c))
}
pub open spec fn obl_ax11<O: SysDesign>() -> bool { check_in_lock(O::cfg()) }
pub open spec fn obl_ax11m<O: SysDesign>() -> bool {
    let c = O::cfg();
    check_in_lock(c) && c.m10_refusal is Inert && c.m02_post is InCommit
}
pub open spec fn obl_ax12<O: SysDesign>() -> bool { O::cfg().m05_receipt is Final }
pub open spec fn obl_ax14<O: SysDesign>() -> bool { has_clear(O::cfg()) }

/// A composed design whose instances keep every axiom: the obligations are proof functions it must discharge.
pub trait SysObject: SysDesign {
    proof fn discharge_ax02() ensures obl_ax02::<Self>();
    proof fn discharge_ax03() ensures obl_ax03::<Self>();
    proof fn discharge_ax04() ensures obl_ax04::<Self>();
    proof fn discharge_ax05() ensures obl_ax05::<Self>();
    proof fn discharge_ax06() ensures obl_ax06::<Self>();
    proof fn discharge_ax07() ensures obl_ax07::<Self>();
    proof fn discharge_ax08() ensures obl_ax08::<Self>();
    proof fn discharge_ax10() ensures obl_ax10::<Self>();
    proof fn discharge_ax11() ensures obl_ax11::<Self>();
    proof fn discharge_ax11m() ensures obl_ax11m::<Self>();
    proof fn discharge_ax12() ensures obl_ax12::<Self>();
    proof fn discharge_ax14() ensures obl_ax14::<Self>();
}

} // verus!
