//! Readers racing a redaction (D-9b; F-1402, HD-1401). Protocol `ReadP` composes the redaction ledger **RL** (level
//! 1's outer contract) and the **Reader** into the contract `RdOuter`.
//!
//! **Partition.** Readers write nothing and read only ledger globals (records, marker, epoch), so they compose with RL
//! rather than with the full `Biz`: every Biz step's ledger part is an RL step or leaves RL unchanged
//! (`theorem_biz_ledger_step`), so every interleaving of a Biz execution with reader steps is an RdOuter execution
//! (`theorem_biz_step_is_rd_step`), and what is proved here of readers holds while every other participant
//! (store, erasures, bypass writers) runs. verify()'s **table** read and its coherence with its record read are not
//! modelled (open; core model M3-readers also read records and tables as one cut).
//!
//! Reviewed reader protocol (HD-1401 working answer (b2)): a reader begins only when no marker exists and records
//! the redaction epoch; it reads revisions one at a time as they are; it may return its view only if, after reading,
//! there is still no marker **and** the epoch is unchanged; otherwise it refuses (or retries). The epoch is advanced by
//! every redaction start and finish (`ledger::ledger_mark`, `ledger::ledger_audit`) — a reviewed-design element; the
//! pin has none.
//!
//! Controls (each must fail `lemma_rd_binds` in this file; one proved counterexample serves both, `cx_reader`):
//! - `control_f1402_reader_no_recheck` (F-1402, as built: client.py:720-728 then replay.py:231-269): a reader returns
//!   its view with no check after reading;
//! - `control_reader_marker_recheck_only` (HD-1401 alternative (b1), the original review's remedy): a reader
//!   re-checks the marker after reading but compares no epoch; a whole redaction inside one read passes it
//!   (live `ib-HD1401-reader-full-race`).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::redactor::*;
use crate::reader::*;
use crate::protocol_rl::*;
use crate::mid::*;
use crate::biz::*;
use crate::compose::*;

verus! {

pub struct RdS { pub rl: RLS, pub rd: ReaderS }

pub enum RdL {
    /// Any step of the redaction ledger (commits, replays, locks, the redaction's steps).
    Ledger { x: RLL },
    Begin { q: nat },
    Page { q: nat },
    Accept { q: nat },
    Refuse { q: nat },
}

/// The reviewed acceptance condition: no marker and the epoch unchanged since the read began.
pub open spec fn accept_ok(l: LedgerS, r: ReaderS, q: nat) -> bool { l.marker is None && l.epoch == r.rd[q].e0 }

pub open spec fn rd_next(s: RdS, x: RdL, u: RdS) -> bool {
    let l = s.rl.l;
    let r = s.rd;
    match x {
        RdL::Ledger { x } => rl_next(s.rl, x, u.rl) && u.rd == r,
        RdL::Begin { q } => l.marker is None && reader_pre(r, ReaderL::Begin { q, e0: l.epoch })
            && u == RdS { rl: s.rl, rd: reader_step(r, ReaderL::Begin { q, e0: l.epoch }) },
        RdL::Page { q } => r.rd.contains_key(q) && r.rd[q].view.len() < l.hist.len()
            && u == RdS { rl: s.rl, rd: reader_step(r, ReaderL::Page { q, rs: l.hist[r.rd[q].view.len() as int] }) },
        RdL::Accept { q } => r.rd.contains_key(q) && accept_ok(l, r, q)
            && u == RdS { rl: s.rl, rd: reader_step(r, ReaderL::Accept { q }) },
        RdL::Refuse { q } => r.rd.contains_key(q) && !accept_ok(l, r, q)
            && u == RdS { rl: s.rl, rd: reader_step(r, ReaderL::Refuse { q }) },
    }
}

pub struct RdOuter;

impl Contract for RdOuter {
    type S = RdS;
    type L = RdL;

    open spec fn init(s: RdS) -> bool { RL::init(s.rl) && Reader::init(s.rd) }

    open spec fn next(s: RdS, x: RdL, u: RdS) -> bool { rd_next(s, x, u) }
}

// ------------------------------------------------------------------------------------------------ invariant

/// What a read in progress has seen: while the epoch is the one it began with, there is no marker and its view is a
/// prefix of the current history (no tombstone was written since it began: tombstones need a marker, and a marker needs
/// a redaction start, which advances the epoch).
pub open spec fn view_ok(l: LedgerS, p: RdProc) -> bool {
    &&& p.e0 <= l.epoch
    &&& l.epoch == p.e0 ==> l.marker is None && p.view.len() <= l.hist.len()
            && forall|i: int| 0 <= i < p.view.len() ==> #[trigger] p.view[i] == l.hist[i]
}

pub open spec fn rd_inv(s: RdS) -> bool {
    &&& rl_inv(s.rl)
    &&& forall|q: nat| #[trigger] s.rd.rd.contains_key(q) ==> view_ok(s.rl.l, s.rd.rd[q])
}

/// Every step of the redaction ledger keeps every reader's view facts.
pub proof fn lemma_view_rl(s: RLS, x: RLL, u: RLS, p: RdProc)
    requires rl_next(s, x, u), view_ok(s.l, p),
    ensures view_ok(u.l, p),
{
    let l = s.l;
    match x {
        RLL::Commit { cs, named, key } => {
            assert(u.l == ledger_commit(l, cs, named, key));
            if l.epoch == p.e0 {
                assert forall|i: int| 0 <= i < p.view.len() implies #[trigger] p.view[i] == u.l.hist[i] by {
                    assert(u.l.hist[i] == l.hist[i]);
                }
            }
        }
        RLL::Start { p: pr, fresh } => {
            if !fresh { assert(l.marker is Some); }
        }
        RLL::Scan { p: pr } => {
            assert(l.marker is Some);
        }
        RLL::Final { p: pr, ok } => {}
        _ => {}
    }
}

pub proof fn lemma_rd_safe(s: RdS, x: RdL, u: RdS)
    requires rd_inv(s), rd_next(s, x, u),
    ensures rd_inv(u),
{
    match x {
        RdL::Ledger { x: a } => {
            lemma_rl_safe(s.rl, a, u.rl);
            assert forall|q: nat| #[trigger] u.rd.rd.contains_key(q) implies view_ok(u.rl.l, u.rd.rd[q]) by {
                lemma_view_rl(s.rl, a, u.rl, s.rd.rd[q]);
            }
        }
        RdL::Page { q } => {
            let l = s.rl.l;
            let p = s.rd.rd[q];
            let p2 = u.rd.rd[q];
            assert(p2.view == p.view.push(l.hist[p.view.len() as int]) && p2.e0 == p.e0);
            assert forall|q2: nat| #[trigger] u.rd.rd.contains_key(q2) implies view_ok(u.rl.l, u.rd.rd[q2]) by {
                if q2 == q {
                    if l.epoch == p.e0 {
                        assert forall|i: int| 0 <= i < p2.view.len() implies #[trigger] p2.view[i] == l.hist[i] by {
                            if i < p.view.len() { assert(p2.view[i] == p.view[i]); }
                        }
                    }
                } else {
                    assert(u.rd.rd[q2] == s.rd.rd[q2]);
                }
            }
        }
        RdL::Begin { q } => {
            assert forall|q2: nat| #[trigger] u.rd.rd.contains_key(q2) implies view_ok(u.rl.l, u.rd.rd[q2]) by {
                if q2 != q { assert(u.rd.rd[q2] == s.rd.rd[q2]); }
            }
        }
        RdL::Accept { q } => {
            assert forall|q2: nat| #[trigger] u.rd.rd.contains_key(q2) implies view_ok(u.rl.l, u.rd.rd[q2]) by {
                assert(u.rd.rd[q2] == s.rd.rd[q2]);
            }
        }
        RdL::Refuse { q } => {
            assert forall|q2: nat| #[trigger] u.rd.rd.contains_key(q2) implies view_ok(u.rl.l, u.rd.rd[q2]) by {
                assert(u.rd.rd[q2] == s.rd.rd[q2]);
            }
        }
    }
}

impl SafeContract for RdOuter {
    open spec fn inv(s: RdS) -> bool { rd_inv(s) }
    proof fn init_safe(s: RdS) {}
    proof fn step_safe(s: RdS, x: RdL, u: RdS) { lemma_rd_safe(s, x, u); }
}

// ------------------------------------------------------------------------------------------------ business theorem

/// **RPL-I1 (no half-done view; spec 256 Decision 3, client.py:691-692; F-1402 is the pin's violation).** A view a
/// reader returns is a prefix of the current history, no redaction is in progress, and no redaction started or
/// finished while it was read (the epoch is the one it began with): it is a cut of one history in which no
/// tombstone was written during the read — never a redaction half done.
pub proof fn theorem_accepted_view_consistent(s: RdS, q: nat, u: RdS)
    requires rd_inv(s), rd_next(s, RdL::Accept { q }, u),
    ensures ({
        let l = s.rl.l;
        let p = s.rd.rd[q];
        &&& l.marker is None && l.epoch == p.e0
        &&& p.view.len() <= l.hist.len()
        &&& forall|i: int| 0 <= i < p.view.len() ==> #[trigger] p.view[i] == l.hist[i]
    }),
{
    assert(view_ok(s.rl.l, s.rd.rd[q]));
}

// ------------------------------------------------------------------------------------------------ the protocol

pub open spec fn rd_guard(a: RLS, b: ReaderS, x: RdL) -> bool {
    match x {
        RdL::Ledger { x } => true,
        // client.py:720-728: refuse while a marker exists (as built and reviewed).
        RdL::Begin { q } => a.l.marker is None,
        RdL::Page { q } => b.rd.contains_key(q) && b.rd[q].view.len() < a.l.hist.len(),
        RdL::Accept { q } =>
            if cfg!(feature = "control_f1402_reader_no_recheck") {
                // As built: no check after the read.
                true
            } else if cfg!(feature = "control_reader_marker_recheck_only") {
                // HD-1401 (b1): the marker re-checked, no epoch.
                a.l.marker is None
            } else {
                accept_ok(a.l, b, q)
            },
        RdL::Refuse { q } => !accept_ok(a.l, b, q),
    }
}

pub open spec fn rd_lab_a(a: RLS, b: ReaderS, x: RdL) -> Option<RLL> {
    match x {
        RdL::Ledger { x } => Some(x),
        _ => None,
    }
}

pub open spec fn rd_lab_b(a: RLS, b: ReaderS, x: RdL) -> Option<ReaderL> {
    match x {
        RdL::Ledger { x } => None,
        RdL::Begin { q } => Some(ReaderL::Begin { q, e0: a.l.epoch }),
        RdL::Page { q } => Some(ReaderL::Page { q, rs: a.l.hist[b.rd[q].view.len() as int] }),
        RdL::Accept { q } => Some(ReaderL::Accept { q }),
        RdL::Refuse { q } => Some(ReaderL::Refuse { q }),
    }
}

pub struct ReadP;

impl Protocol2 for ReadP {
    type Outer = RdOuter;
    type A = RL;
    type B = Reader;
    type Own = ();

    open spec fn abs(a: RLS, b: ReaderS, o: ()) -> RdS { RdS { rl: a, rd: b } }
    open spec fn guard(a: RLS, b: ReaderS, o: (), x: RdL) -> bool { rd_guard(a, b, x) }
    open spec fn lab_a(a: RLS, b: ReaderS, o: (), x: RdL) -> Option<RLL> { rd_lab_a(a, b, x) }
    open spec fn lab_b(a: RLS, b: ReaderS, o: (), x: RdL) -> Option<ReaderL> { rd_lab_b(a, b, x) }
    open spec fn own_next(a: RLS, b: ReaderS, o: (), x: RdL, o2: ()) -> bool { true }

    proof fn step_binds(a: RLS, b: ReaderS, o: (), x: RdL, a2: RLS, b2: ReaderS, o2: ()) {
        lemma_rd_binds(a, b, x, a2, b2);
    }

    proof fn step_enabled(a: RLS, b: ReaderS, o: (), x: RdL, t: RdS) {
        lemma_rd_enabled(a, b, x, t);
        assert(Self::abs(t.rl, t.rd, ()) == t);
    }
}

impl ProtocolInit for ReadP {
    open spec fn own_init(o: ()) -> bool { true }
    proof fn init_binds(a: RLS, b: ReaderS, o: ()) {}
}

/// REFINES: every synchronized step of the redaction ledger and the readers is one RdOuter step.
pub proof fn lemma_rd_binds(a: RLS, b: ReaderS, x: RdL, a2: RLS, b2: ReaderS)
    requires
        rd_guard(a, b, x),
        step_or_stutter::<RL>(a, rd_lab_a(a, b, x), a2),
        step_or_stutter::<Reader>(b, rd_lab_b(a, b, x), b2),
    ensures rd_next(RdS { rl: a, rd: b }, x, RdS { rl: a2, rd: b2 }),
{
}

/// Non-vacuity: every RdOuter step from a represented state is realized by the redaction ledger and the readers.
pub proof fn lemma_rd_enabled(a: RLS, b: ReaderS, x: RdL, t: RdS)
    requires rd_next(RdS { rl: a, rd: b }, x, t),
    ensures
        rd_guard(a, b, x),
        step_or_stutter::<RL>(a, rd_lab_a(a, b, x), t.rl),
        step_or_stutter::<Reader>(b, rd_lab_b(a, b, x), t.rd),
{
}

/// One step of the composed participant contracts (the controls change it; `cx_reader`).
pub open spec fn rd_sys_step(s: RdS, x: RdL, u: RdS) -> bool {
    &&& rd_guard(s.rl, s.rd, x)
    &&& step_or_stutter::<RL>(s.rl, rd_lab_a(s.rl, s.rd, x), u.rl)
    &&& step_or_stutter::<Reader>(s.rd, rd_lab_b(s.rl, s.rd, x), u.rd)
}

pub proof fn theorem_rd_sys_step_refines(s: RdS, x: RdL, u: RdS)
    requires rd_sys_step(s, x, u),
    ensures rd_next(s, x, u),
{
    lemma_rd_binds(s.rl, s.rd, x, u.rl, u.rd);
}

// ------------------------------------------------------------------------------------------------ composition

pub type RdTop<IRL, IRd> = Sys<ReadP, IRL, IRd>;

/// **Readers' composition.** Any implementations of the redaction ledger and of the readers, run in ReadP's steps,
/// refine RdOuter, and every state of every execution satisfies `rd_inv`.
pub proof fn theorem_rd_implementations_refine<IRL: Refines<RL>, IRd: Refines<Reader>>(
    s: <RdTop<IRL, IRd> as Contract>::S, x: <RdTop<IRL, IRd> as Contract>::L, u: <RdTop<IRL, IRd> as Contract>::S)
    requires <RdTop<IRL, IRd> as Contract>::next(s, x, u),
    ensures step_or_stutter::<RdOuter>(<RdTop<IRL, IRd> as Refines<RdOuter>>::abs(s), <RdTop<IRL, IRd> as Refines<RdOuter>>::lab(x),
        <RdTop<IRL, IRd> as Refines<RdOuter>>::abs(u)),
{
    <RdTop<IRL, IRd> as Refines<RdOuter>>::step_refines(s, x, u);
}

pub proof fn theorem_rd_implementations_safe<IRL: Refines<RL>, IRd: Refines<Reader>>(
    states: Seq<<RdTop<IRL, IRd> as Contract>::S>, labels: Seq<<RdTop<IRL, IRd> as Contract>::L>)
    requires execution::<RdTop<IRL, IRd>>(states, labels),
    ensures forall|i: int| 0 <= i < states.len() ==> rd_inv(#[trigger] <RdTop<IRL, IRd> as Refines<RdOuter>>::abs(states[i])),
{
    refinement_preserves_safety::<RdTop<IRL, IRd>, RdOuter>(states, labels);
}

/// **The partition is sound.** The ledger part of every business step is a step of RL, or RL does not move.
pub proof fn theorem_biz_ledger_step(x: BizS, l: BizL, y: BizS)
    requires biz_next(x, l, y),
    ensures
        match top_lab_m(mid_of(x), x.wr, l) {
            Some(m) => match mid_rl(m) { Some(a) => rl_next(x.rl, a, y.rl), None => y.rl == x.rl },
            None => y.rl == x.rl,
        },
{
    match top_lab_m(mid_of(x), x.wr, l) {
        Some(m) => { assert(mid_next(mid_of(x), m, mid_of(y))); }
        None => { assert(mid_of(y) == mid_of(x)); }
    }
}

/// ... so each business step, seen by readers in any state r, is an RdOuter step (or changes nothing they see).
pub proof fn theorem_biz_step_is_rd_step(x: BizS, l: BizL, y: BizS, r: ReaderS)
    requires biz_next(x, l, y),
    ensures
        y.rl == x.rl || exists|a: RLL| #[trigger] rd_next(RdS { rl: x.rl, rd: r }, RdL::Ledger { x: a }, RdS { rl: y.rl, rd: r }),
{
    theorem_biz_ledger_step(x, l, y);
    match top_lab_m(mid_of(x), x.wr, l) {
        Some(m) => {
            match mid_rl(m) {
                Some(a) => { assert(rd_next(RdS { rl: x.rl, rd: r }, RdL::Ledger { x: a }, RdS { rl: y.rl, rd: r })); }
                None => {}
            }
        }
        None => {}
    }
}

} // verus!
