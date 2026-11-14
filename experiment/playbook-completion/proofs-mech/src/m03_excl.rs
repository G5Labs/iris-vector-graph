//! M-03 Exclusive section: lock and marker (AX-11, AX-12), generic over `ExclPolicy` / `ExclObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/excl.rs` (read at commit b0433157): an interpreter of
//! the step programs the object's processes run, interleaved in every order. State: each process's program counter
//! (`At(k)`, `Done`, `Refused`); the lock (exclusive holders, shared holders: sets of process ids instead of the
//! explorer's bitmasks); the marker (target, owner) or none; per target (0 = tenant A, 1 = tenant B): live?, history
//! tombstoned?; the no-lock mark (Adjacency.cls:55-75: a writer that waited 5 s writes without the lock and marks the
//! graph). Steps as in the explorer: `LockX`, `LockS` (block until available), `LockSOrMark`, `Unlock`, the refusing
//! checks `CheckNotLive(t)`, `CheckNoMarker(t)`, `CheckNoMarkerAny` (a refused process stops and releases its lock),
//! `SetMarker(t)` (only if none), `ClearAny`, `ClearOwn`, the guarded effects `MakeLive(t)` (a commit into t),
//! `Erase(t)`, `Tomb(t)`, `Write`, and the control's broken lock `LockXBad`. The instance parameters are the programs
//! and the targets' initial liveness. Differences from the explorer: a step naming a target other than 0 or 1 is
//! disabled (the explorer has no such step), and an empty program starts `Done` (the explorer has none).
//!
//! Laws (MECHANISMS.md M-03): M03-L1 (invariant) mutual exclusion; M03-L2 (action) every guarded effect is made by a
//! process holding the lock or with the no-lock mark set; M03-L3 (invariant) a marked target is not live; M03-L4
//! (action) only the marker's owner clears it; M03-L5 (action) no history of live content is tombstoned.
//!
//! Obligations: structural rules on the programs (`Rule`), each decided by computation over the instance's
//! programs (`holds_all`). A *section* is the run of steps after a lock step up to the next `Unlock`; an *X section*
//! is one opened by `LockX`. L1 (lock discipline): no broken lock, and no lock step inside a section. L2: every
//! guarded effect is inside a section. L3: a marker is set only in an X section after the section checked the target
//! not live; content is made live only in an X section after the section checked that no other process marks the
//! target, by a program that never sets a marker; and, if any program sets markers or makes content live, the lock
//! discipline. L4: no program clears a marker it may not own (no `ClearAny`). L5: if any program tombstones, the lock
//! discipline holds, every tombstone is in an X section after the section checked the target not live, and content
//! is made live only in X sections.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum Step {
    LockX, LockXBad, LockS, LockSOrMark, Unlock,
    CheckNotLive(nat), CheckNoMarker(nat), CheckNoMarkerAny,
    SetMarker(nat), ClearAny, ClearOwn,
    MakeLive(nat), Erase(nat), Tomb(nat), Write,
}

pub enum Pc { At(nat), Done, Refused }

pub struct XS {
    pub pc: Seq<Pc>,
    pub excl: Set<nat>,
    pub shared: Set<nat>,
    pub marker: Option<(nat, nat)>,
    pub live: Seq<bool>,
    pub tomb: Seq<bool>,
    pub nolock: bool,
}

pub trait ExclPolicy: Sized {
    spec fn progs() -> Seq<Seq<Step>>;
    spec fn init_live() -> Seq<bool>;
}

pub open spec fn guarded(st: Step) -> bool { st is MakeLive || st is Erase || st is Tomb || st is Write }
pub open spec fn is_lock(st: Step) -> bool { st is LockX || st is LockXBad || st is LockS || st is LockSOrMark }
pub open spec fn step_ok(st: Step) -> bool {
    match st {
        Step::CheckNotLive(t) | Step::CheckNoMarker(t) | Step::SetMarker(t) | Step::MakeLive(t) | Step::Erase(t) | Step::Tomb(t) => t < 2,
        _ => true,
    }
}

pub open spec fn holds(s: XS, i: nat) -> bool { s.excl.contains(i) || s.shared.contains(i) }
pub open spec fn other_holds(s: XS, i: nat) -> bool { exists|j: nat| j != i && #[trigger] holds(s, j) }
pub open spec fn other_excl(s: XS, i: nat) -> bool { exists|j: nat| j != i && #[trigger] s.excl.contains(j) }
pub open spec fn release(s: XS, i: nat) -> XS { XS { excl: s.excl.remove(i), shared: s.shared.remove(i), ..s } }

/// The marker is set, by a process other than `i`, on target `t` (or on any target when `t` is None).
pub open spec fn marked_by_other(s: XS, t: Option<nat>, i: nat) -> bool {
    match s.marker {
        Some((m, o)) => o != i && match t { Some(x) => m == x, None => true },
        None => false,
    }
}
pub open spec fn owns_marker(s: XS, i: nat) -> bool {
    match s.marker { Some((_, o)) => o == i, None => false }
}

pub open spec fn refuses(st: Step, s: XS, i: nat) -> bool {
    match st {
        Step::CheckNotLive(t) => s.live[t as int],
        Step::CheckNoMarker(t) => marked_by_other(s, Some(t), i),
        Step::CheckNoMarkerAny => marked_by_other(s, None, i),
        _ => false,
    }
}

/// The effect of a step that does not refuse (None: blocked).
pub open spec fn effect(st: Step, s: XS, i: nat) -> Option<XS> {
    match st {
        Step::LockX => if other_holds(s, i) { None } else { Some(XS { excl: s.excl.insert(i), ..s }) },
        Step::LockXBad => Some(XS { excl: s.excl.insert(i), ..s }),
        Step::LockS => if other_excl(s, i) { None } else { Some(XS { shared: s.shared.insert(i), ..s }) },
        Step::LockSOrMark => if other_excl(s, i) { Some(XS { nolock: true, ..s }) } else { Some(XS { shared: s.shared.insert(i), ..s }) },
        Step::Unlock => Some(release(s, i)),
        Step::SetMarker(t) => if s.marker is None { Some(XS { marker: Some((t, i)), ..s }) } else { Some(s) },
        Step::ClearAny => Some(XS { marker: None, ..s }),
        Step::ClearOwn => if owns_marker(s, i) { Some(XS { marker: None, ..s }) } else { Some(s) },
        Step::MakeLive(t) => Some(XS { live: s.live.update(t as int, true), ..s }),
        Step::Erase(t) => Some(XS { live: s.live.update(t as int, false), ..s }),
        Step::Tomb(t) => Some(XS { tomb: s.tomb.update(t as int, true), ..s }),
        _ => Some(s),
    }
}

pub open spec fn pc_k(p: Pc) -> nat { match p { Pc::At(k) => k, _ => 0 } }

/// The step process `i` would take now, if any.
pub open spec fn cur_step<O: ExclPolicy>(s: XS, i: nat) -> Option<Step> {
    let ps = O::progs();
    if i < ps.len() && i < s.pc.len() && s.pc[i as int] is At && pc_k(s.pc[i as int]) < ps[i as int].len() {
        Some(ps[i as int][pc_k(s.pc[i as int]) as int])
    } else { None }
}

pub open spec fn x_step<O: ExclPolicy>(s: XS, i: nat) -> Option<XS> {
    let ps = O::progs();
    if i >= ps.len() || s.pc.len() != ps.len() || s.live.len() != 2 || s.tomb.len() != 2 || !(s.pc[i as int] is At) { None }
    else {
        let k = pc_k(s.pc[i as int]);
        if k >= ps[i as int].len() || !step_ok(ps[i as int][k as int]) { None }
        else {
            let st = ps[i as int][k as int];
            if refuses(st, s, i) {
                Some(XS { pc: s.pc.update(i as int, Pc::Refused), ..release(s, i) })
            } else {
                match effect(st, s, i) {
                    None => None,
                    Some(u) => if k + 1 >= ps[i as int].len() {
                        Some(XS { pc: u.pc.update(i as int, Pc::Done), ..release(u, i) })
                    } else {
                        Some(XS { pc: u.pc.update(i as int, Pc::At(k + 1)), ..u })
                    },
                }
            }
        }
    }
}

pub open spec fn x_s0<O: ExclPolicy>() -> XS {
    XS {
        pc: Seq::new(O::progs().len(), |i: int| if O::progs()[i].len() > 0 { Pc::At(0) } else { Pc::Done }),
        excl: Set::empty(),
        shared: Set::empty(),
        marker: None,
        live: O::init_live(),
        tomb: seq![false, false],
        nolock: false,
    }
}

pub struct ExclM<O> { pub o: O }

impl<O: ExclPolicy> Machine for ExclM<O> {
    type S = XS;
    type A = nat;
    open spec fn init(s: XS) -> bool { s == x_s0::<O>() }
    open spec fn step(s: XS, a: nat) -> Option<XS> { x_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M03-L1 (invariant): mutual exclusion (at most one exclusive holder, and none while any shared holder).
pub open spec fn law_l1(s: XS) -> bool {
    &&& forall|a: nat, b: nat| s.excl.contains(a) && s.excl.contains(b) ==> a == b
    &&& forall|a: nat, b: nat| s.excl.contains(a) ==> !s.shared.contains(b)
}

/// M03-L2 (action): every guarded effect is made by a process that holds the lock (or with the no-lock mark set).
pub open spec fn law_l2<O: ExclPolicy>(s: XS, i: nat) -> bool {
    match cur_step::<O>(s, i) { Some(st) => guarded(st) ==> holds(s, i) || s.nolock, None => true }
}

/// M03-L3 (invariant): while target t is marked, t is not live.
pub open spec fn law_l3(s: XS) -> bool {
    match s.marker { Some((t, _)) => !s.live[t as int], None => true }
}

/// M03-L4 (action): only the marker's owner clears it.
pub open spec fn law_l4(s: XS, i: nat, t: XS) -> bool {
    !(s.marker is Some && t.marker is None) || owns_marker(s, i)
}

/// M03-L5 (action): no history of live content is tombstoned.
pub open spec fn law_l5<O: ExclPolicy>(s: XS, i: nat) -> bool {
    match cur_step::<O>(s, i) { Some(Step::Tomb(t)) => !s.live[t as int], _ => true }
}

// ------------------------------------------------------------------------------------------------ program structure

/// The position of the lock step that opened the section step k runs in, if any.
pub open spec fn sec(p: Seq<Step>, k: int) -> Option<int>
    decreases k,
{
    if k <= 0 { None }
    else if p[k - 1] is Unlock { None }
    else if is_lock(p[k - 1]) { Some(k - 1) }
    else { sec(p, k - 1) }
}

pub open spec fn in_x(p: Seq<Step>, k: int) -> bool {
    match sec(p, k) { Some(j) => p[j] is LockX, None => false }
}

/// The current section checked that t is not live, and did not make it live since.
pub open spec fn checked_not_live(p: Seq<Step>, k: int, t: nat) -> bool
    decreases k,
{
    if k <= 0 { false }
    else if p[k - 1] is Unlock || is_lock(p[k - 1]) { false }
    else if p[k - 1] == Step::CheckNotLive(t) { true }
    else if p[k - 1] == Step::MakeLive(t) { false }
    else { checked_not_live(p, k - 1, t) }
}

/// The current section checked that no other process marks t.
pub open spec fn checked_no_marker(p: Seq<Step>, k: int, t: nat) -> bool
    decreases k,
{
    if k <= 0 { false }
    else if p[k - 1] is Unlock || is_lock(p[k - 1]) { false }
    else if p[k - 1] == Step::CheckNoMarker(t) || p[k - 1] is CheckNoMarkerAny { true }
    else { checked_no_marker(p, k - 1, t) }
}

pub open spec fn has_set(p: Seq<Step>, k: nat) -> bool
    decreases p.len() - k,
{
    if k >= p.len() { false } else { p[k as int] is SetMarker || has_set(p, k + 1) }
}

pub enum Rule { Discipline, GuardedLocked, MarkerSet, MakeLiveChecked, NoClearAny, TombChecked, MakeLiveInX, NoMarkerUse, NoTomb }

pub open spec fn rule(r: Rule, p: Seq<Step>, k: int) -> bool {
    let st = p[k];
    match r {
        Rule::Discipline => !(st is LockXBad) && (is_lock(st) ==> sec(p, k) is None),
        Rule::GuardedLocked => guarded(st) ==> sec(p, k) is Some,
        Rule::MarkerSet => match st { Step::SetMarker(t) => in_x(p, k) && checked_not_live(p, k, t), _ => true },
        Rule::MakeLiveChecked => match st {
            Step::MakeLive(t) => in_x(p, k) && checked_no_marker(p, k, t) && !has_set(p, 0),
            _ => true,
        },
        Rule::NoClearAny => !(st is ClearAny),
        Rule::TombChecked => match st { Step::Tomb(t) => in_x(p, k) && checked_not_live(p, k, t), _ => true },
        Rule::MakeLiveInX => st is MakeLive ==> in_x(p, k),
        Rule::NoMarkerUse => !(st is SetMarker || st is MakeLive),
        Rule::NoTomb => !(st is Tomb),
    }
}

pub open spec fn all_steps(r: Rule, p: Seq<Step>, k: nat) -> bool
    decreases p.len() - k,
{
    if k >= p.len() { true } else { rule(r, p, k as int) && all_steps(r, p, k + 1) }
}

pub open spec fn all_progs(r: Rule, ps: Seq<Seq<Step>>, i: nat) -> bool
    decreases ps.len() - i,
{
    if i >= ps.len() { true } else { all_steps(r, ps[i as int], 0) && all_progs(r, ps, i + 1) }
}

/// Rule `r` holds at every step of every program (decided by computation for an instance).
pub open spec fn holds_all(r: Rule, ps: Seq<Seq<Step>>) -> bool { all_progs(r, ps, 0) }

// ------------------------------------------------------------------------------------------------ obligations

pub open spec fn obl_l1<O: ExclPolicy>() -> bool { holds_all(Rule::Discipline, O::progs()) }
pub open spec fn obl_l2<O: ExclPolicy>() -> bool { holds_all(Rule::GuardedLocked, O::progs()) }
pub open spec fn obl_l3<O: ExclPolicy>() -> bool {
    holds_all(Rule::MarkerSet, O::progs()) && holds_all(Rule::MakeLiveChecked, O::progs())
        && (holds_all(Rule::NoMarkerUse, O::progs()) || holds_all(Rule::Discipline, O::progs()))
}
pub open spec fn obl_l4<O: ExclPolicy>() -> bool { holds_all(Rule::NoClearAny, O::progs()) }
pub open spec fn obl_l5<O: ExclPolicy>() -> bool {
    holds_all(Rule::NoTomb, O::progs()) || (holds_all(Rule::Discipline, O::progs())
        && holds_all(Rule::TombChecked, O::progs()) && holds_all(Rule::MakeLiveInX, O::progs()))
}

pub trait ExclObject: ExclPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
    proof fn discharge_l4() ensures obl_l4::<Self>();
    proof fn discharge_l5() ensures obl_l5::<Self>();
}

// ------------------------------------------------------------------------------------------------ structure lemmas

pub proof fn lemma_all_steps(r: Rule, p: Seq<Step>, k: nat, m: int)
    requires all_steps(r, p, k), k <= m < p.len(),
    ensures rule(r, p, m),
    decreases m - k,
{
    if m > k { lemma_all_steps(r, p, k + 1, m); }
}

pub proof fn lemma_all_progs(r: Rule, ps: Seq<Seq<Step>>, i: nat, n: int, m: int)
    requires all_progs(r, ps, i), i <= n < ps.len(), 0 <= m < ps[n].len(),
    ensures rule(r, ps[n], m),
    decreases n - i,
{
    if n > i { lemma_all_progs(r, ps, i + 1, n, m); } else { lemma_all_steps(r, ps[n], 0, m); }
}

/// The rule at one step of one program.
pub proof fn lemma_rule(r: Rule, ps: Seq<Seq<Step>>, n: int, m: int)
    requires holds_all(r, ps), 0 <= n < ps.len(), 0 <= m < ps[n].len(),
    ensures rule(r, ps[n], m),
{
    lemma_all_progs(r, ps, 0, n, m);
}

pub proof fn lemma_sec_range(p: Seq<Step>, k: int)
    ensures sec(p, k) matches Some(j) ==> 0 <= j < k && is_lock(p[j]),
    decreases k,
{
    if k > 0 { lemma_sec_range(p, k - 1); }
}

pub proof fn lemma_has_set(p: Seq<Step>, k: nat, m: int)
    requires k <= m < p.len(), p[m] is SetMarker,
    ensures has_set(p, k),
    decreases m - k,
{
    if m > k { lemma_has_set(p, k + 1, m); }
}

// ------------------------------------------------------------------------------------------------ invariants

pub open spec fn wf<O: ExclPolicy>(s: XS) -> bool {
    &&& s.pc.len() == O::progs().len()
    &&& s.tomb.len() == 2
    &&& s.live.len() == O::init_live().len()
    &&& forall|i: int| 0 <= i < s.pc.len() && #[trigger] s.pc[i] is At ==> pc_k(s.pc[i]) < O::progs()[i].len()
}

/// A process inside a section holds what its opening step took (every policy).
pub open spec fn held_ok<O: ExclPolicy>(s: XS, i: nat) -> bool {
    s.pc[i as int] is At ==> match sec(O::progs()[i as int], pc_k(s.pc[i as int]) as int) {
        Some(j) => {
            let st = O::progs()[i as int][j];
            &&& (st is LockX || st is LockXBad ==> s.excl.contains(i))
            &&& (st is LockS ==> s.shared.contains(i))
            &&& (st is LockSOrMark ==> s.shared.contains(i) || s.nolock)
        },
        None => true,
    }
}

pub open spec fn inv_held<O: ExclPolicy>(s: XS) -> bool {
    wf::<O>(s) && forall|i: nat| i < s.pc.len() ==> #[trigger] held_ok::<O>(s, i)
}

/// Under the lock discipline: a holder is inside a section opened by the matching kind of step.
pub open spec fn in_section_of<O: ExclPolicy>(s: XS, i: nat, exclusive: bool) -> bool {
    i < s.pc.len() && s.pc[i as int] is At && match sec(O::progs()[i as int], pc_k(s.pc[i as int]) as int) {
        Some(j) => {
            let st = O::progs()[i as int][j];
            if exclusive { st is LockX || st is LockXBad } else { st is LockS || st is LockSOrMark }
        },
        None => false,
    }
}

pub open spec fn inv_disc<O: ExclPolicy>(s: XS) -> bool {
    &&& inv_held::<O>(s)
    &&& law_l1(s)
    &&& forall|i: nat| #[trigger] s.excl.contains(i) ==> in_section_of::<O>(s, i, true)
    &&& forall|i: nat| #[trigger] s.shared.contains(i) ==> in_section_of::<O>(s, i, false)
}

pub proof fn lemma_init<O: ExclPolicy>()
    ensures inv_held::<O>(x_s0::<O>()),
        law_l1(x_s0::<O>()),
        forall|i: nat| !(#[trigger] x_s0::<O>().excl.contains(i)),
        forall|i: nat| !(#[trigger] x_s0::<O>().shared.contains(i)),
{
    let s = x_s0::<O>();
    assert forall|i: nat| i < s.pc.len() implies #[trigger] held_ok::<O>(s, i) by {
        if s.pc[i as int] is At { assert(pc_k(s.pc[i as int]) == 0); }
    }
}

pub proof fn lemma_held_step<O: ExclPolicy>(s: XS, q: nat)
    requires inv_held::<O>(s), x_step::<O>(s, q) is Some,
    ensures inv_held::<O>(x_step::<O>(s, q)->0),
{
    let u = x_step::<O>(s, q)->0;
    let ps = O::progs();
    let k = pc_k(s.pc[q as int]);
    let p = ps[q as int];
    assert(wf::<O>(u)) by {
        assert forall|i: int| 0 <= i < u.pc.len() && #[trigger] u.pc[i] is At implies pc_k(u.pc[i]) < ps[i].len() by {
            if i != q as int { assert(u.pc[i] == s.pc[i]); }
        }
    }
    assert forall|i: nat| i < u.pc.len() implies #[trigger] held_ok::<O>(u, i) by {
        assert(held_ok::<O>(s, i));
        if i != q {
            assert(u.pc[i as int] == s.pc[i as int]);
            assert(s.excl.contains(i) ==> u.excl.contains(i));
            assert(s.shared.contains(i) ==> u.shared.contains(i));
        } else if u.pc[i as int] is At {
            assert(u.pc[i as int] == Pc::At(k + 1));
            lemma_sec_range(p, k as int);
        }
    }
}

/// A step changes the lock sets only at the stepping process.
pub proof fn lemma_step_sets<O: ExclPolicy>(s: XS, q: nat)
    requires x_step::<O>(s, q) is Some,
    ensures
        forall|a: nat| a != q ==> ((x_step::<O>(s, q)->0).excl.contains(a) == s.excl.contains(a)),
        forall|a: nat| a != q ==> ((x_step::<O>(s, q)->0).shared.contains(a) == s.shared.contains(a)),
        (x_step::<O>(s, q)->0).nolock == s.nolock || (x_step::<O>(s, q)->0).nolock,
{
    let ps = O::progs();
    let k = pc_k(s.pc[q as int]);
    let st = ps[q as int][k as int];
    let u = x_step::<O>(s, q)->0;
    if !refuses(st, s, q) {
        let e = effect(st, s, q)->0;
        assert forall|a: nat| a != q implies (e.excl.contains(a) == s.excl.contains(a) && e.shared.contains(a) == s.shared.contains(a)) by {}
        assert forall|a: nat| a != q implies (u.excl.contains(a) == e.excl.contains(a) && u.shared.contains(a) == e.shared.contains(a)) by {}
    }
}

pub proof fn lemma_disc_step<O: ExclPolicy>(s: XS, q: nat)
    requires obl_l1::<O>(), inv_disc::<O>(s), x_step::<O>(s, q) is Some,
    ensures inv_disc::<O>(x_step::<O>(s, q)->0),
{
    lemma_held_step::<O>(s, q);
    let u = x_step::<O>(s, q)->0;
    let ps = O::progs();
    let k = pc_k(s.pc[q as int]);
    let p = ps[q as int];
    let st = p[k as int];
    lemma_rule(Rule::Discipline, ps, q as int, k as int);
    lemma_sec_range(p, k as int);
    if is_lock(st) {
        // the process held nothing before its lock step
        assert(!s.excl.contains(q));
        assert(!s.shared.contains(q));
    }
    assert(law_l1(u)) by {
        if !refuses(st, s, q) && (st is LockX || st is LockS || st is LockSOrMark) {
            if st is LockX {
                assert forall|a: nat| a != q implies !s.excl.contains(a) && !s.shared.contains(a) by {
                    if s.excl.contains(a) || s.shared.contains(a) { assert(holds(s, a)); }
                }
            } else {
                assert forall|a: nat| a != q && !other_excl(s, q) implies !s.excl.contains(a) by {
                    if s.excl.contains(a) { assert(other_excl(s, q)); }
                }
            }
            lemma_step_sets::<O>(s, q);
            assert(!u.shared.contains(q) || !(st is LockX));
            assert forall|a: nat, b: nat| u.excl.contains(a) && u.excl.contains(b) implies a == b by {
                if a != q { assert(s.excl.contains(a)); }
                if b != q { assert(s.excl.contains(b)); }
            }
            assert forall|a: nat, b: nat| u.excl.contains(a) implies !u.shared.contains(b) by {
                if a != q { assert(s.excl.contains(a)); }
                if b != q && u.shared.contains(b) { assert(s.shared.contains(b)); }
            }
        } else {
            lemma_step_sets::<O>(s, q);
            assert(u.excl.contains(q) ==> s.excl.contains(q));
            assert(u.shared.contains(q) ==> s.shared.contains(q));
            assert forall|a: nat| u.excl.contains(a) implies s.excl.contains(a) by {}
            assert forall|a: nat| u.shared.contains(a) implies s.shared.contains(a) by {}
        }
    }
    assert forall|i: nat| #[trigger] u.excl.contains(i) implies in_section_of::<O>(u, i, true) by {
        if i != q { assert(s.excl.contains(i)); assert(u.pc[i as int] == s.pc[i as int]); }
        else if !s.excl.contains(q) { assert(u.pc[i as int] == Pc::At(k + 1)); }
        else { assert(in_section_of::<O>(s, q, true)); assert(u.pc[i as int] == Pc::At(k + 1)); }
    }
    assert forall|i: nat| #[trigger] u.shared.contains(i) implies in_section_of::<O>(u, i, false) by {
        if i != q { assert(s.shared.contains(i)); assert(u.pc[i as int] == s.pc[i as int]); }
        else if !s.shared.contains(q) { assert(u.pc[i as int] == Pc::At(k + 1)); }
        else { assert(in_section_of::<O>(s, q, false)); assert(u.pc[i as int] == Pc::At(k + 1)); }
    }
}

/// The facts an X section has checked still hold: checked not live; checked no other process's marker.
pub open spec fn facts_nl<O: ExclPolicy>(s: XS, i: nat) -> bool {
    s.pc[i as int] is At && in_x(O::progs()[i as int], pc_k(s.pc[i as int]) as int) ==>
        forall|t: nat| t < 2 && #[trigger] checked_not_live(O::progs()[i as int], pc_k(s.pc[i as int]) as int, t) ==> !s.live[t as int]
}
pub open spec fn facts_nm<O: ExclPolicy>(s: XS, i: nat) -> bool {
    s.pc[i as int] is At && in_x(O::progs()[i as int], pc_k(s.pc[i as int]) as int) ==>
        forall|t: nat| #[trigger] checked_no_marker(O::progs()[i as int], pc_k(s.pc[i as int]) as int, t) ==> !marked_by_other(s, Some(t), i)
}

pub open spec fn inv_nl<O: ExclPolicy>(s: XS) -> bool {
    inv_disc::<O>(s) && forall|i: nat| i < s.pc.len() ==> #[trigger] facts_nl::<O>(s, i)
}

/// A process inside an X section holds the lock exclusively, so no other process holds anything.
pub proof fn lemma_x_alone<O: ExclPolicy>(s: XS, i: nat, q: nat)
    requires inv_disc::<O>(s), i < s.pc.len(), s.pc[i as int] is At, in_x(O::progs()[i as int], pc_k(s.pc[i as int]) as int), q != i,
    ensures s.excl.contains(i), !holds(s, q),
{
    assert(held_ok::<O>(s, i));
    lemma_sec_range(O::progs()[i as int], pc_k(s.pc[i as int]) as int);
}

pub proof fn lemma_nl_step<O: ExclPolicy>(s: XS, q: nat)
    requires obl_l1::<O>(), holds_all(Rule::MakeLiveInX, O::progs()), inv_nl::<O>(s), x_step::<O>(s, q) is Some,
    ensures inv_nl::<O>(x_step::<O>(s, q)->0),
{
    lemma_disc_step::<O>(s, q);
    let u = x_step::<O>(s, q)->0;
    let ps = O::progs();
    let k = pc_k(s.pc[q as int]);
    let p = ps[q as int];
    let st = p[k as int];
    lemma_rule(Rule::MakeLiveInX, ps, q as int, k as int);
    lemma_sec_range(p, k as int);
    assert forall|i: nat| i < u.pc.len() implies #[trigger] facts_nl::<O>(u, i) by {
        assert(facts_nl::<O>(s, i));
        if i != q {
            assert(u.pc[i as int] == s.pc[i as int]);
            if u.pc[i as int] is At && in_x(ps[i as int], pc_k(u.pc[i as int]) as int) {
                lemma_x_alone::<O>(s, i, q);
                if st is MakeLive && !refuses(st, s, q) {
                    assert(held_ok::<O>(s, q));
                }
            }
        } else if u.pc[i as int] is At {
            assert(u.pc[i as int] == Pc::At(k + 1));
            let kk = (k + 1) as int;
            if in_x(p, kk) {
                assert forall|t: nat| t < 2 && #[trigger] checked_not_live(p, kk, t) implies !u.live[t as int] by {
                    if st != Step::CheckNotLive(t) {
                        assert(checked_not_live(p, k as int, t));
                        assert(sec(p, kk) == sec(p, k as int));
                    }
                }
            }
        }
    }
}

pub open spec fn inv_nm<O: ExclPolicy>(s: XS) -> bool {
    inv_disc::<O>(s) && forall|i: nat| i < s.pc.len() ==> #[trigger] facts_nm::<O>(s, i)
}

pub proof fn lemma_nm_step<O: ExclPolicy>(s: XS, q: nat)
    requires obl_l1::<O>(), holds_all(Rule::MarkerSet, O::progs()), inv_nm::<O>(s), x_step::<O>(s, q) is Some,
    ensures inv_nm::<O>(x_step::<O>(s, q)->0),
{
    lemma_disc_step::<O>(s, q);
    let u = x_step::<O>(s, q)->0;
    let ps = O::progs();
    let k = pc_k(s.pc[q as int]);
    let p = ps[q as int];
    let st = p[k as int];
    lemma_rule(Rule::MarkerSet, ps, q as int, k as int);
    lemma_sec_range(p, k as int);
    assert forall|i: nat| i < u.pc.len() implies #[trigger] facts_nm::<O>(u, i) by {
        assert(facts_nm::<O>(s, i));
        if i != q {
            assert(u.pc[i as int] == s.pc[i as int]);
            if u.pc[i as int] is At && in_x(ps[i as int], pc_k(u.pc[i as int]) as int) {
                lemma_x_alone::<O>(s, i, q);
                if st is SetMarker && !refuses(st, s, q) {
                    assert(held_ok::<O>(s, q));
                }
            }
        } else if u.pc[i as int] is At {
            assert(u.pc[i as int] == Pc::At(k + 1));
            let kk = (k + 1) as int;
            if in_x(p, kk) {
                assert forall|t: nat| #[trigger] checked_no_marker(p, kk, t) implies !marked_by_other(u, Some(t), i) by {
                    if !(st == Step::CheckNoMarker(t) || st is CheckNoMarkerAny) {
                        assert(checked_no_marker(p, k as int, t));
                        assert(sec(p, kk) == sec(p, k as int));
                    }
                }
            }
        }
    }
}

/// M03-L3's inductive form: a marked target is not live, and the marker's owner runs a program that sets markers.
pub open spec fn inv_l3<O: ExclPolicy>(s: XS) -> bool {
    &&& inv_nl::<O>(s)
    &&& inv_nm::<O>(s)
    &&& law_l3(s)
    &&& s.marker matches Some((t, o)) ==> t < 2 && o < O::progs().len() && has_set(O::progs()[o as int], 0)
}

pub proof fn lemma_l3_step<O: ExclPolicy>(s: XS, q: nat)
    requires obl_l1::<O>(), obl_l3::<O>(), inv_l3::<O>(s), x_step::<O>(s, q) is Some,
    ensures inv_l3::<O>(x_step::<O>(s, q)->0),
{
    let ps = O::progs();
    let k = pc_k(s.pc[q as int]);
    let p = ps[q as int];
    let st = p[k as int];
    assert(holds_all(Rule::MakeLiveInX, ps)) by {
        assert forall|n: int, m: int| 0 <= n < ps.len() && 0 <= m < ps[n].len() implies rule(Rule::MakeLiveInX, ps[n], m) by {
            lemma_rule(Rule::MakeLiveChecked, ps, n, m);
        }
        lemma_all_of_pointwise(Rule::MakeLiveInX, ps);
    }
    lemma_nl_step::<O>(s, q);
    lemma_nm_step::<O>(s, q);
    lemma_rule(Rule::MarkerSet, ps, q as int, k as int);
    lemma_rule(Rule::MakeLiveChecked, ps, q as int, k as int);
    let u = x_step::<O>(s, q)->0;
    if !refuses(st, s, q) {
        if let Step::SetMarker(t) = st {
            if s.marker is None {
                assert(facts_nl::<O>(s, q));
                lemma_has_set(p, 0, k as int);
            }
        }
        if let Step::MakeLive(t) = st {
            assert(facts_nm::<O>(s, q));
            if let Some((m, o)) = s.marker {
                if o == q { assert(has_set(p, 0)); }
            }
        }
    }
}

/// A rule that holds at every step holds for the program list (the converse of `lemma_rule`).
pub proof fn lemma_all_of_pointwise(r: Rule, ps: Seq<Seq<Step>>)
    requires forall|n: int, m: int| 0 <= n < ps.len() && 0 <= m < ps[n].len() ==> rule(r, ps[n], m),
    ensures holds_all(r, ps),
{
    lemma_all_progs_pointwise(r, ps, 0);
}

proof fn lemma_all_progs_pointwise(r: Rule, ps: Seq<Seq<Step>>, i: nat)
    requires forall|n: int, m: int| 0 <= n < ps.len() && 0 <= m < ps[n].len() ==> rule(r, ps[n], m),
    ensures all_progs(r, ps, i),
    decreases ps.len() - i,
{
    if i < ps.len() {
        lemma_all_steps_pointwise(r, ps[i as int], 0);
        lemma_all_progs_pointwise(r, ps, i + 1);
    }
}

proof fn lemma_all_steps_pointwise(r: Rule, p: Seq<Step>, k: nat)
    requires forall|m: int| 0 <= m < p.len() ==> rule(r, p, m),
    ensures all_steps(r, p, k),
    decreases p.len() - k,
{
    if k < p.len() { lemma_all_steps_pointwise(r, p, k + 1); }
}

/// No program sets a marker or makes content live: the marker is never set.
pub proof fn lemma_no_marker_step<O: ExclPolicy>(s: XS, q: nat)
    requires holds_all(Rule::NoMarkerUse, O::progs()), wf::<O>(s), s.marker is None, x_step::<O>(s, q) is Some,
    ensures wf::<O>(x_step::<O>(s, q)->0), (x_step::<O>(s, q)->0).marker is None,
{
    let ps = O::progs();
    let k = pc_k(s.pc[q as int]);
    lemma_rule(Rule::NoMarkerUse, ps, q as int, k as int);
    let u = x_step::<O>(s, q)->0;
    assert forall|i: int| 0 <= i < u.pc.len() && #[trigger] u.pc[i] is At implies pc_k(u.pc[i]) < ps[i].len() by {
        if i != q as int { assert(u.pc[i] == s.pc[i]); }
    }
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_held<O: ExclPolicy>(s0: XS, ls: Seq<nat>, t: XS)
    requires reached::<ExclM<O>>(s0, ls, t),
    ensures inv_held::<O>(t),
{
    lemma_init::<O>();
    let inv = |s: XS| inv_held::<O>(s);
    assert forall|x: XS, a: nat| inv(x) && (#[trigger] ExclM::<O>::step(x, a)) is Some implies inv(ExclM::<O>::step(x, a)->0) by {
        lemma_held_step::<O>(x, a);
    }
    lemma_reached_inv::<ExclM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_disc<O: ExclPolicy>(s0: XS, ls: Seq<nat>, t: XS)
    requires obl_l1::<O>(), reached::<ExclM<O>>(s0, ls, t),
    ensures inv_disc::<O>(t),
{
    lemma_init::<O>();
    let inv = |s: XS| inv_disc::<O>(s);
    assert forall|x: XS, a: nat| inv(x) && (#[trigger] ExclM::<O>::step(x, a)) is Some implies inv(ExclM::<O>::step(x, a)->0) by {
        lemma_disc_step::<O>(x, a);
    }
    lemma_reached_inv::<ExclM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l1<O: ExclPolicy>(s0: XS, ls: Seq<nat>, t: XS)
    requires obl_l1::<O>(), reached::<ExclM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    theorem_disc::<O>(s0, ls, t);
}

pub proof fn theorem_l2<O: ExclPolicy>(s0: XS, ls: Seq<nat>, t: XS, q: nat)
    requires obl_l2::<O>(), reached::<ExclM<O>>(s0, ls, t), x_step::<O>(t, q) is Some,
    ensures law_l2::<O>(t, q),
{
    theorem_held::<O>(s0, ls, t);
    let ps = O::progs();
    let k = pc_k(t.pc[q as int]);
    lemma_rule(Rule::GuardedLocked, ps, q as int, k as int);
    lemma_sec_range(ps[q as int], k as int);
    assert(held_ok::<O>(t, q));
}

pub proof fn theorem_l3<O: ExclPolicy>(s0: XS, ls: Seq<nat>, t: XS)
    requires obl_l3::<O>(), reached::<ExclM<O>>(s0, ls, t),
    ensures law_l3(t),
{
    lemma_init::<O>();
    if holds_all(Rule::NoMarkerUse, O::progs()) {
        let inv = |s: XS| wf::<O>(s) && s.marker is None;
        assert forall|x: XS, a: nat| inv(x) && (#[trigger] ExclM::<O>::step(x, a)) is Some implies inv(ExclM::<O>::step(x, a)->0) by {
            lemma_no_marker_step::<O>(x, a);
        }
        lemma_reached_inv::<ExclM<O>>(inv, s0, ls, t);
    } else {
        let inv = |s: XS| inv_l3::<O>(s);
        assert(inv(x_s0::<O>())) by {
            let s = x_s0::<O>();
            assert forall|i: nat| i < s.pc.len() implies #[trigger] facts_nl::<O>(s, i) by {
                if s.pc[i as int] is At { assert(pc_k(s.pc[i as int]) == 0); }
            }
            assert forall|i: nat| i < s.pc.len() implies #[trigger] facts_nm::<O>(s, i) by {
                if s.pc[i as int] is At { assert(pc_k(s.pc[i as int]) == 0); }
            }
        }
        assert forall|x: XS, a: nat| inv(x) && (#[trigger] ExclM::<O>::step(x, a)) is Some implies inv(ExclM::<O>::step(x, a)->0) by {
            lemma_l3_step::<O>(x, a);
        }
        lemma_reached_inv::<ExclM<O>>(inv, s0, ls, t);
    }
}

pub proof fn theorem_l4<O: ExclPolicy>(s: XS, q: nat)
    requires obl_l4::<O>(), x_step::<O>(s, q) is Some,
    ensures law_l4(s, q, x_step::<O>(s, q)->0),
{
    let ps = O::progs();
    let k = pc_k(s.pc[q as int]);
    lemma_rule(Rule::NoClearAny, ps, q as int, k as int);
}

pub proof fn theorem_l5<O: ExclPolicy>(s0: XS, ls: Seq<nat>, t: XS, q: nat)
    requires obl_l5::<O>(), reached::<ExclM<O>>(s0, ls, t), x_step::<O>(t, q) is Some,
    ensures law_l5::<O>(t, q),
{
    let ps = O::progs();
    let k = pc_k(t.pc[q as int]);
    if holds_all(Rule::NoTomb, ps) {
        lemma_rule(Rule::NoTomb, ps, q as int, k as int);
    } else {
        lemma_init::<O>();
        let inv = |s: XS| inv_nl::<O>(s);
        assert(inv(x_s0::<O>())) by {
            let s = x_s0::<O>();
            assert forall|i: nat| i < s.pc.len() implies #[trigger] facts_nl::<O>(s, i) by {
                if s.pc[i as int] is At { assert(pc_k(s.pc[i as int]) == 0); }
            }
        }
        assert forall|x: XS, a: nat| inv(x) && (#[trigger] ExclM::<O>::step(x, a)) is Some implies inv(ExclM::<O>::step(x, a)->0) by {
            lemma_nl_step::<O>(x, a);
        }
        lemma_reached_inv::<ExclM<O>>(inv, s0, ls, t);
        lemma_rule(Rule::TombChecked, ps, q as int, k as int);
        assert(facts_nl::<O>(t, q));
    }
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_excl<O: ExclObject>(s0: XS, ls: Seq<nat>, t: XS, q: nat)
    requires reached::<ExclM<O>>(s0, ls, t),
    ensures
        law_l1(t),
        law_l3(t),
        x_step::<O>(t, q) is Some ==> law_l2::<O>(t, q) && law_l4(t, q, x_step::<O>(t, q)->0) && law_l5::<O>(t, q),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    O::discharge_l4();
    O::discharge_l5();
    theorem_l1::<O>(s0, ls, t);
    theorem_l3::<O>(s0, ls, t);
    if x_step::<O>(t, q) is Some {
        theorem_l2::<O>(s0, ls, t, q);
        theorem_l4::<O>(t, q);
        theorem_l5::<O>(s0, ls, t, q);
    }
}

} // verus!
