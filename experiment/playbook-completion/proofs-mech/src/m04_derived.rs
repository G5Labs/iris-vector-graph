//! M-04 Derived store with staleness (AX-08), generic over `DerivedPolicy` / `DerivedObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/derived.rs` (read at commit b0433157, working tree of
//! the semantics lane at the time of reading) restated without its bounds (the counters `n[0..4]`: writes, fills,
//! rebuilds, clears, answers are unbounded here) and with the stamp as `Option<nat>` (`None` = invalidated, the
//! explorer's 255, which could collide with a token here) and the token as `nat`. Abstract state: the committed
//! source `src` and an open writer's uncommitted value `dirty` (visible to other processes, E-VIS); the derived value
//! `der` (`None` = cleared, read as 0, the warm-stamp reading of F-0406); the sync path's pending derived value
//! `sync_der`; the `stamp` and the live `token` (monotone, not undone by rollback, E-INCR). `f` is the identity; a
//! `wrong` path computes v + 1 (a maintenance function that counts twice, F-0501). The writer runs one write path per
//! transaction: optional shared writer lock (held to the end), an optional token step before the write, the write (a
//! `sync` path updates the derived value in the same transaction, as a functional index does, X-FX; `survives` makes
//! that update an $Increment a rollback keeps, F-C0801), an optional token step after, then commit or roll back. A
//! reader fill stores a value with the token it read: `Plain` (token, compute, store), `Probe` (token, probe the
//! writer lock with no wait, compute, store only if granted and the token unchanged: ADR-0012, Adj.cls:34-39), and
//! the controls `ProbeLate` and `TokenAfter`. A rebuild (no writer open) recomputes and stamps. A clear removes the
//! value and keeps (as built) or invalidates the stamp. An answer reads through the gate.
//!
//! Laws (MECHANISMS.md M-04): M04-L1 (invariant) no writer open => (stamp = token => value(der) = src); M04-L2
//! (action) a commit that changes the source is sync or moved the token; M04-L3 (action) a rebuild leaves der = src
//! with the current stamp; M04-L4 (action) an answer with no writer open equals src.
//!
//! Obligations (design rules on the instance's configuration): L1 rebuilds recompute; a clear never keeps a current
//! stamp; every write path maintains the derived value correctly in its own transaction (sync, not counted twice, no
//! update that survives a rollback) or moves the token; and either no reader fills the derived store, or every fill
//! probes the writer lock after reading the token and stores only if granted and the token is unchanged, with every
//! write path taking the writer lock and moving the token before it writes. L2 every write path is sync or moves the
//! token. L3 rebuilds recompute. L4 the gate checks the stamp, and L1's rule holds.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub struct WPath { pub lock: bool, pub pre: bool, pub post: bool, pub sync: bool, pub wrong: bool, pub survives: bool }
pub enum Fill { Off, Plain, Probe, ProbeLate, TokenAfter }
pub enum Clear { NoClear, KeepStamp, Restamp }
pub enum Gate { Checked, Unchecked }
pub enum Rebuild { Correct, StampOnly }

pub struct DCfg { pub paths: Seq<WPath>, pub fill: Fill, pub clear: Clear, pub gate: Gate, pub rebuild: Rebuild }

pub enum W { Idle, Begun(nat), Pre(nat), Written(nat, nat), Post(nat, nat) }
pub enum R { Idle, Token(nat), Probed(nat, bool), Computed(nat, bool, nat), Early(nat), LateProbed(nat, bool, nat) }

pub struct DS {
    pub src: nat,
    pub dirty: Option<nat>,
    pub der: Option<nat>,
    pub sync_der: Option<nat>,
    pub stamp: Option<nat>,
    pub token: nat,
    pub w: W,
    pub bumped: bool,
    pub r: R,
    pub last_ok: bool,
}

pub enum DA { Begin(nat), PreBump, Write(nat), PostBump, Commit, Rollback, RToken, RProbe, RCompute, RStore, Rebuild, Clear, Answer }

pub trait DerivedPolicy: Sized {
    spec fn cfg() -> DCfg;
}

pub open spec fn derived_s0() -> DS {
    DS { src: 1, dirty: None, der: Some(1), sync_der: None, stamp: Some(0), token: 0, w: W::Idle, bumped: false, r: R::Idle, last_ok: true }
}

pub open spec fn val(d: Option<nat>) -> nat { match d { Some(v) => v, None => 0 } }

pub open spec fn w_ix(w: W) -> nat {
    match w { W::Idle => 0, W::Begun(p) => p, W::Pre(p) => p, W::Written(p, _) => p, W::Post(p, _) => p }
}

pub open spec fn w_ok<O: DerivedPolicy>(w: W) -> bool { w is Idle || w_ix(w) < O::cfg().paths.len() }

pub open spec fn writer_locked<O: DerivedPolicy>(s: DS) -> bool {
    !(s.w is Idle) && O::cfg().paths[w_ix(s.w) as int].lock
}

/// The write of `v` through path `p` (explorer `A::Write`).
pub open spec fn write_eff(c: DCfg, s: DS, p: nat, v: nat) -> DS {
    let wp = c.paths[p as int];
    let fv = if wp.wrong { v + 1 } else { v };
    DS {
        dirty: Some(v),
        der: if wp.sync && wp.survives { Some(fv) } else { s.der },
        sync_der: if wp.sync && !wp.survives { Some(fv) } else { s.sync_der },
        w: W::Written(p, v),
        ..s
    }
}

pub open spec fn commit_eff(c: DCfg, s: DS, p: nat, v: nat) -> DS {
    let wp = c.paths[p as int];
    DS {
        src: v,
        dirty: None,
        der: if wp.sync && !wp.survives { s.sync_der } else { s.der },
        stamp: if wp.sync { Some(s.token) } else { s.stamp },
        sync_der: None,
        w: W::Idle,
        ..s
    }
}

pub open spec fn derived_step<O: DerivedPolicy>(s: DS, a: DA) -> Option<DS> {
    let c = O::cfg();
    match a {
        DA::Begin(p) => {
            if !(s.w is Idle) || p >= c.paths.len() { None } else { Some(DS { w: W::Begun(p), bumped: false, ..s }) }
        },
        DA::PreBump => match s.w {
            W::Begun(p) => if p < c.paths.len() && c.paths[p as int].pre {
                Some(DS { token: s.token + 1, bumped: true, w: W::Pre(p), ..s })
            } else { None },
            _ => None,
        },
        DA::Write(v) => {
            let pp: Option<nat> = match s.w {
                W::Begun(p) => if p < c.paths.len() && !c.paths[p as int].pre { Some(p) } else { None },
                W::Pre(p) => if p < c.paths.len() { Some(p) } else { None },
                _ => None,
            };
            match pp { Some(p) => if v == s.src { None } else { Some(write_eff(c, s, p, v)) }, None => None }
        },
        DA::PostBump => match s.w {
            W::Written(p, v) => if p < c.paths.len() && c.paths[p as int].post {
                Some(DS { token: s.token + 1, bumped: true, w: W::Post(p, v), ..s })
            } else { None },
            _ => None,
        },
        DA::Commit => match s.w {
            W::Written(p, v) => if p < c.paths.len() && !c.paths[p as int].post { Some(commit_eff(c, s, p, v)) } else { None },
            W::Post(p, v) => if p < c.paths.len() { Some(commit_eff(c, s, p, v)) } else { None },
            _ => None,
        },
        DA::Rollback => if s.w is Idle { None } else { Some(DS { dirty: None, sync_der: None, w: W::Idle, ..s }) },
        DA::RToken => {
            if c.fill is Off { None } else {
                match (s.r, c.fill) {
                    (R::Idle, Fill::TokenAfter) => None,
                    (R::Idle, _) => Some(DS { r: R::Token(s.token), ..s }),
                    (R::Early(v), Fill::TokenAfter) => Some(DS { r: R::Computed(s.token, true, v), ..s }),
                    _ => None,
                }
            }
        },
        DA::RProbe => {
            let granted = !writer_locked::<O>(s);
            match (s.r, c.fill) {
                (R::Token(t), Fill::Probe) => Some(DS { r: R::Probed(t, granted), ..s }),
                (R::Computed(t, _, v), Fill::ProbeLate) => Some(DS { r: R::LateProbed(t, granted, v), ..s }),
                _ => None,
            }
        },
        DA::RCompute => {
            let seen = match s.dirty { Some(d) => d, None => s.src };
            match (s.r, c.fill) {
                (R::Token(t), Fill::Plain) => Some(DS { r: R::Computed(t, true, seen), ..s }),
                (R::Probed(t, g), Fill::Probe) => Some(DS { r: R::Computed(t, g, seen), ..s }),
                (R::Token(t), Fill::ProbeLate) => Some(DS { r: R::Computed(t, true, seen), ..s }),
                (R::Idle, Fill::TokenAfter) => Some(DS { r: R::Early(seen), ..s }),
                _ => None,
            }
        },
        DA::RStore => {
            let tgv: Option<(nat, bool, nat)> = match (s.r, c.fill) {
                (R::Computed(t, g, v), Fill::Plain) => Some((t, g, v)),
                (R::Computed(t, g, v), Fill::TokenAfter) => Some((t, g, v)),
                (R::Computed(t, g, v), Fill::Probe) => Some((t, g && s.token == t, v)),
                (R::LateProbed(t, g, v), Fill::ProbeLate) => Some((t, g && s.token == t, v)),
                _ => None,
            };
            match tgv {
                Some((t, g, v)) => if g { Some(DS { der: Some(v), stamp: Some(t), r: R::Idle, ..s }) } else { Some(DS { r: R::Idle, ..s }) },
                None => None,
            }
        },
        DA::Rebuild => {
            if !(s.w is Idle) { None }
            else { Some(DS { der: if c.rebuild is Correct { Some(s.src) } else { s.der }, stamp: Some(s.token), ..s }) }
        },
        DA::Clear => {
            if c.clear is NoClear || s.der is None { None }
            else { Some(DS { der: None, stamp: if c.clear is Restamp { None } else { s.stamp }, ..s }) }
        },
        DA::Answer => {
            if !(s.w is Idle) { None } else {
                let ans = match c.gate {
                    Gate::Checked => if s.stamp == Some(s.token) { val(s.der) } else { s.src },
                    Gate::Unchecked => val(s.der),
                };
                Some(DS { last_ok: ans == s.src, ..s })
            }
        },
    }
}

pub struct DerivedM<O> { pub o: O }

impl<O: DerivedPolicy> Machine for DerivedM<O> {
    type S = DS;
    type A = DA;
    open spec fn init(s: DS) -> bool { s == derived_s0() }
    open spec fn step(s: DS, a: DA) -> Option<DS> { derived_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M04-L1 (invariant): current or stale.
pub open spec fn law_l1(s: DS) -> bool { !(s.w is Idle) || s.stamp != Some(s.token) || val(s.der) == s.src }

/// M04-L2 (action): a commit that changes the source is sync or moved the token.
pub open spec fn law_l2<O: DerivedPolicy>(s: DS, a: DA, t: DS) -> bool {
    !(a is Commit) || t.src == s.src || !(s.w is Written || s.w is Post) || O::cfg().paths[w_ix(s.w) as int].sync || s.bumped
}

/// M04-L3 (action): a rebuild is current and correct.
pub open spec fn law_l3(a: DA, t: DS) -> bool { !(a is Rebuild) || (t.der == Some(t.src) && t.stamp == Some(t.token)) }

/// M04-L4 (action): a gated read answers the source.
pub open spec fn law_l4(a: DA, t: DS) -> bool { !(a is Answer) || t.last_ok }

// ------------------------------------------------------------------------------------------------ obligations

pub open spec fn path_maintains(p: WPath) -> bool { !p.wrong && !p.survives && (p.sync || p.pre || p.post) }
pub open spec fn path_signals(p: WPath) -> bool { p.sync || p.pre || p.post }
pub open spec fn path_probe_safe(p: WPath) -> bool { p.pre && p.lock }

pub open spec fn obl_l1<O: DerivedPolicy>() -> bool {
    let c = O::cfg();
    &&& c.rebuild is Correct
    &&& !(c.clear is KeepStamp)
    &&& forall|i: int| 0 <= i < c.paths.len() ==> path_maintains(#[trigger] c.paths[i])
    &&& (c.fill is Off || (c.fill is Probe && forall|i: int| 0 <= i < c.paths.len() ==> path_probe_safe(#[trigger] c.paths[i])))
}
pub open spec fn obl_l2<O: DerivedPolicy>() -> bool {
    forall|i: int| 0 <= i < O::cfg().paths.len() ==> path_signals(#[trigger] O::cfg().paths[i])
}
pub open spec fn obl_l3<O: DerivedPolicy>() -> bool { O::cfg().rebuild is Correct }
pub open spec fn obl_l4<O: DerivedPolicy>() -> bool { O::cfg().gate is Checked && obl_l1::<O>() }

pub trait DerivedObject: DerivedPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
    proof fn discharge_l4() ensures obl_l4::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

/// Every policy: the writer's path index is valid; a begun writer has not bumped; a writer past its pre-step or in
/// its post-step has.
pub open spec fn bump_shape<O: DerivedPolicy>(s: DS) -> bool {
    &&& w_ok::<O>(s.w)
    &&& match s.w {
        W::Idle => true,
        W::Begun(_) => !s.bumped,
        W::Pre(_) => s.bumped,
        W::Written(p, _) => O::cfg().paths[p as int].pre ==> s.bumped,
        W::Post(_, _) => s.bumped,
    }
}

pub proof fn lemma_bump_step<O: DerivedPolicy>(s: DS, a: DA)
    requires bump_shape::<O>(s), derived_step::<O>(s, a) is Some,
    ensures bump_shape::<O>(derived_step::<O>(s, a)->0),
{
}

pub open spec fn w_quiet(w: W) -> bool { w is Idle || w is Begun }

pub open spec fn stamp_le(s: DS) -> bool { match s.stamp { Some(x) => x <= s.token, None => true } }

pub open spec fn dirty_shape<O: DerivedPolicy>(s: DS) -> bool {
    match s.w {
        W::Written(p, v) => s.dirty == Some(v) && s.sync_der == (if O::cfg().paths[p as int].sync { Some(v) } else { None }),
        W::Post(p, v) => s.dirty == Some(v) && s.sync_der == (if O::cfg().paths[p as int].sync { Some(v) } else { None }),
        _ => s.dirty is None && s.sync_der is None,
    }
}

/// A reader holds a token no later than the current one; a granted probe (or a computation after it) whose token is
/// still current saw no writer that has moved the token, and its computed value is the committed source.
pub open spec fn reader_ok<O: DerivedPolicy>(s: DS) -> bool {
    match s.r {
        R::Idle => true,
        R::Token(t) => O::cfg().fill is Probe && t <= s.token,
        R::Probed(t, g) => O::cfg().fill is Probe && t <= s.token && (g && t == s.token ==> w_quiet(s.w)),
        R::Computed(t, g, v) => O::cfg().fill is Probe && t <= s.token && (g && t == s.token ==> w_quiet(s.w) && v == s.src),
        _ => false,
    }
}

/// The inductive form of M04-L1 under its obligation: the law holds in every state, not only with no writer open.
pub open spec fn ind_l1<O: DerivedPolicy>(s: DS) -> bool {
    &&& bump_shape::<O>(s)
    &&& stamp_le(s)
    &&& (s.stamp == Some(s.token) ==> val(s.der) == s.src)
    &&& (!(s.w is Idle) && s.bumped ==> s.stamp != Some(s.token))
    &&& dirty_shape::<O>(s)
    &&& reader_ok::<O>(s)
}

pub proof fn lemma_l1_step<O: DerivedPolicy>(s: DS, a: DA)
    requires obl_l1::<O>(), ind_l1::<O>(s), derived_step::<O>(s, a) is Some,
    ensures ind_l1::<O>(derived_step::<O>(s, a)->0),
{
    let c = O::cfg();
    let t = derived_step::<O>(s, a)->0;
    lemma_bump_step::<O>(s, a);
    if !(s.w is Idle) {
        assert(path_maintains(c.paths[w_ix(s.w) as int]));
        if c.fill is Probe { assert(path_probe_safe(c.paths[w_ix(s.w) as int])); }
    }
    match a {
        DA::Begin(p) => {
            if c.fill is Probe { assert(path_probe_safe(c.paths[p as int])); }
        },
        DA::RProbe => {
            if !(s.w is Idle) && c.fill is Probe { assert(writer_locked::<O>(s)); }
        },
        _ => {},
    }
}

pub proof fn lemma_l2_step<O: DerivedPolicy>(s: DS, a: DA)
    requires obl_l2::<O>(), bump_shape::<O>(s), derived_step::<O>(s, a) is Some,
    ensures law_l2::<O>(s, a, derived_step::<O>(s, a)->0),
{
    if a is Commit {
        assert(path_signals(O::cfg().paths[w_ix(s.w) as int]));
    }
}

pub proof fn lemma_l3_step<O: DerivedPolicy>(s: DS, a: DA)
    requires obl_l3::<O>(), derived_step::<O>(s, a) is Some,
    ensures law_l3(a, derived_step::<O>(s, a)->0),
{
}

pub proof fn lemma_l4_step<O: DerivedPolicy>(s: DS, a: DA)
    requires obl_l4::<O>(), ind_l1::<O>(s), derived_step::<O>(s, a) is Some,
    ensures law_l4(a, derived_step::<O>(s, a)->0),
{
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_bump<O: DerivedPolicy>(s0: DS, ls: Seq<DA>, t: DS)
    requires reached::<DerivedM<O>>(s0, ls, t),
    ensures bump_shape::<O>(t),
{
    let inv = |s: DS| bump_shape::<O>(s);
    assert forall|x: DS, a: DA| inv(x) && (#[trigger] DerivedM::<O>::step(x, a)) is Some implies inv(DerivedM::<O>::step(x, a)->0) by {
        lemma_bump_step::<O>(x, a);
    }
    lemma_reached_inv::<DerivedM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_ind_l1<O: DerivedPolicy>(s0: DS, ls: Seq<DA>, t: DS)
    requires obl_l1::<O>(), reached::<DerivedM<O>>(s0, ls, t),
    ensures ind_l1::<O>(t),
{
    let inv = |s: DS| ind_l1::<O>(s);
    assert forall|x: DS, a: DA| inv(x) && (#[trigger] DerivedM::<O>::step(x, a)) is Some implies inv(DerivedM::<O>::step(x, a)->0) by {
        lemma_l1_step::<O>(x, a);
    }
    lemma_reached_inv::<DerivedM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l1<O: DerivedPolicy>(s0: DS, ls: Seq<DA>, t: DS)
    requires obl_l1::<O>(), reached::<DerivedM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    theorem_ind_l1::<O>(s0, ls, t);
}

pub proof fn theorem_l2<O: DerivedPolicy>(s0: DS, ls: Seq<DA>, t: DS, a: DA)
    requires obl_l2::<O>(), reached::<DerivedM<O>>(s0, ls, t), derived_step::<O>(t, a) is Some,
    ensures law_l2::<O>(t, a, derived_step::<O>(t, a)->0),
{
    theorem_bump::<O>(s0, ls, t);
    lemma_l2_step::<O>(t, a);
}

pub proof fn theorem_l3<O: DerivedPolicy>(t: DS, a: DA)
    requires obl_l3::<O>(), derived_step::<O>(t, a) is Some,
    ensures law_l3(a, derived_step::<O>(t, a)->0),
{
    lemma_l3_step::<O>(t, a);
}

pub proof fn theorem_l4<O: DerivedPolicy>(s0: DS, ls: Seq<DA>, t: DS, a: DA)
    requires obl_l4::<O>(), reached::<DerivedM<O>>(s0, ls, t), derived_step::<O>(t, a) is Some,
    ensures law_l4(a, derived_step::<O>(t, a)->0),
{
    theorem_ind_l1::<O>(s0, ls, t);
    lemma_l4_step::<O>(t, a);
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_derived<O: DerivedObject>(s0: DS, ls: Seq<DA>, t: DS, a: DA)
    requires reached::<DerivedM<O>>(s0, ls, t),
    ensures
        law_l1(t),
        derived_step::<O>(t, a) is Some ==> law_l2::<O>(t, a, derived_step::<O>(t, a)->0)
            && law_l3(a, derived_step::<O>(t, a)->0) && law_l4(a, derived_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    O::discharge_l4();
    theorem_l1::<O>(s0, ls, t);
    if derived_step::<O>(t, a) is Some {
        theorem_l2::<O>(s0, ls, t, a);
        theorem_l3::<O>(t, a);
        theorem_l4::<O>(s0, ls, t, a);
    }
}

} // verus!
