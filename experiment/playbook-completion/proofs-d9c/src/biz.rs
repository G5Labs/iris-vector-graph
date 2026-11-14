//! The outer business contract `Biz` (level 3: Mid x Writer, `protocol_top`) and the definitions of its invariants.
//! Proofs of the invariants are in `safety`, the business theorems in `theorems`.
//!
//! State: the redaction ledger, the store (rows as other processes see them, provenance, statement index, the open
//! erasure), `pend`, and the writers' open transactions. Labels: Mid's, with the non-ledger write split into a
//! writer transaction's begin, commit and abort.
//!
//! The reviewed decisions at this level (`top_ok`):
//! - **G-B (bypass writers serialized with redaction start)**: Start runs only when no ledger-bypassing transaction is
//!   open (the writers hold a lock that the redaction's opening step takes exclusively; F-C1301 remedy, HD-1201
//!   extended to "every same-target writer"). Writers need not serialize with commits, batches, Final, or each other.
//! - **G-BE (the eraser waits for open bypass transactions on its target)**: EraseRows runs only when no open
//!   bypass transaction wrote a key of its target.
//! - **G-BM (D-9c, review R4-01; bypass writers honour the marker)**: while a target is marked, a ledger-bypassing
//!   write of a row its liveness predicate selects is refused (the writer reads `^IVG.Ledger("redacting")` and answers
//!   busy, as a ledger commit into the target is refused by BlocksCommit). Intent: Ledger.cls:514 ("Spec 256 Decision
//!   3: while a redaction runs, nothing may be written into its target"), ADR-0013:17-18. At the pin no non-ledger
//!   writer reads the marker (F-C1350, live).
//! - Row locks (as built, IRIS E-ROWLOCK / E-UNIQUE; the undecided cases modelled as waits, as core model M2 does):
//!   a ledger commit waits for rows an open bypass transaction wrote; a bypass write waits for a row the open erasure
//!   deleted. Premise P-D9-2.
//!
//! **Committed view.** `crow(x, k)`, `cunrec(x, k)`, `cstmt(x, k)`: the row, provenance and statement entry at k that
//! rolling back every open transaction (the erasure and the writers') would leave. The invariants are stated on the
//! committed view, plus overlay facts relating the visible rows to it; so every invariant also holds in every state a
//! rollback can produce (E-ROLLBACK-OTHER, E-STOP), which is what "an erasure rolls back after a liveness check saw
//! it" and "a bypass delete rolls back" require.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::writer::*;
use crate::protocol_rl::*;
use crate::mid::*;

verus! {

pub struct BizS { pub rl: RLS, pub st: StoreS, pub pend: Set<Dom>, pub wr: WrS }

pub enum BizL {
    Commit { cs: Seq<Content>, named: Seq<Key>, key: Option<IKey> },
    Replay { key: IKey, props: Seq<Content> },
    EraseRows { e: Dom },
    EraseIndex,
    EraseCommit,
    EraseAbort,
    SetEnabled { on: bool },
    Open { p: nat, t: Tgt },
    Start { p: nat, fresh: bool },
    Scan { p: nat },
    ToFinal { p: nat },
    Final { p: nat, ok: bool },
    Stop { p: nat },
    /// A ledger-bypassing transaction writes row k (`Some(v)` insert/update, `None` delete); visible at once.
    BBegin { k: Key, v: Option<int> },
    BCommit { k: Key },
    BAbort { k: Key },
}

pub open spec fn mid_of(x: BizS) -> MidS { MidS { rl: x.rl, st: x.st, pend: x.pend } }

pub open spec fn no_open(w: WrS) -> bool { forall|k: Key| #![trigger w.open.contains_key(k)] !w.open.contains_key(k) }

pub open spec fn saved_in(st: StoreS, k: Key) -> bool { st.erasing is Some && st.erasing->0.saved.contains_key(k) }

/// The reviewed level-3 decision.
pub open spec fn top_ok(m: MidS, w: WrS, l: BizL) -> bool {
    match l {
        BizL::Start { p, fresh } => no_open(w),
        BizL::EraseRows { e } => forall|k: Key| #[trigger] w.open.contains_key(k) ==> !member(e, k),
        BizL::Commit { cs, named, key } => forall|i: int| 0 <= i < cs.len() ==> !w.open.contains_key(#[trigger] cs[i].k),
        BizL::BBegin { k, v } => !saved_in(m.st, k) && bypass_honours_marker(m, k),
        _ => true,
    }
}

/// G-BM: no bypass write of a row the marked target's liveness predicate selects.
pub open spec fn bypass_honours_marker(m: MidS, k: Key) -> bool {
    m.rl.l.marker is Some ==> !member(m.rl.l.marker->0.lv, k)
}

/// The Mid operation of each step.
pub open spec fn top_lab_m(m: MidS, w: WrS, l: BizL) -> Option<MidL> {
    match l {
        BizL::Commit { cs, named, key } => Some(MidL::Commit { cs, named, key }),
        BizL::Replay { key, props } => Some(MidL::Replay { key, props }),
        BizL::EraseRows { e } => Some(MidL::EraseRows { e }),
        BizL::EraseIndex => Some(MidL::EraseIndex),
        BizL::EraseCommit => Some(MidL::EraseCommit),
        BizL::EraseAbort => Some(MidL::EraseAbort),
        BizL::SetEnabled { on } => Some(MidL::SetEnabled { on }),
        BizL::Open { p, t } => Some(MidL::Open { p, t }),
        BizL::Start { p, fresh } => Some(MidL::Start { p, fresh }),
        BizL::Scan { p } => Some(MidL::Scan { p }),
        BizL::ToFinal { p } => Some(MidL::ToFinal { p }),
        BizL::Final { p, ok } => Some(MidL::Final { p, ok }),
        BizL::Stop { p } => Some(MidL::Stop { p }),
        BizL::BBegin { k, v } => Some(MidL::Write { k, v }),
        BizL::BCommit { k } => None,
        BizL::BAbort { k } => Some(MidL::Undo { k, before: w.open[k].before, was: w.open[k].was }),
    }
}

/// The writer operation of each step: a write records the before-image the store had.
pub open spec fn top_lab_w(m: MidS, w: WrS, l: BizL) -> Option<WrL> {
    match l {
        BizL::BBegin { k, v } => Some(WrL::Begin { k, before: oget(m.st.rows, k), was: m.st.unrec.contains(k) }),
        BizL::BCommit { k } => Some(WrL::Commit { k }),
        BizL::BAbort { k } => Some(WrL::Abort { k }),
        _ => None,
    }
}

pub open spec fn biz_next(x: BizS, l: BizL, y: BizS) -> bool {
    &&& top_ok(mid_of(x), x.wr, l)
    &&& step_or_stutter::<Mid>(mid_of(x), top_lab_m(mid_of(x), x.wr, l), mid_of(y))
    &&& step_or_stutter::<Writer>(x.wr, top_lab_w(mid_of(x), x.wr, l), y.wr)
}

pub struct Biz;

impl Contract for Biz {
    type S = BizS;
    type L = BizL;

    open spec fn init(x: BizS) -> bool { Mid::init(mid_of(x)) && Writer::init(x.wr) }

    open spec fn next(x: BizS, l: BizL, y: BizS) -> bool { biz_next(x, l, y) }
}

// ------------------------------------------------------------------------------------------------ committed view

pub open spec fn crow(x: BizS, k: Key) -> Option<int> {
    if x.wr.open.contains_key(k) { x.wr.open[k].before }
    else if saved_in(x.st, k) { Some(x.st.erasing->0.saved[k]) }
    else { oget(x.st.rows, k) }
}

pub open spec fn cunrec(x: BizS, k: Key) -> bool {
    if x.wr.open.contains_key(k) { x.wr.open[k].was } else { x.st.unrec.contains(k) }
}

pub open spec fn cstmt(x: BizS, k: Key) -> bool {
    x.st.stmts.contains(k) || (x.st.erasing is Some && x.st.erasing->0.sst.contains(k))
}

/// k holds **recorded content** (content a ledger record wrote): in the rows other processes see now, or in the rows a
/// rollback of the open transactions would leave.
pub open spec fn rec_content(x: BizS, k: Key) -> bool {
    (x.st.rows.contains_key(k) && !x.st.unrec.contains(k)) || (crow(x, k) is Some && !cunrec(x, k))
}

pub open spec fn in_pend(pend: Set<Dom>) -> spec_fn(Key) -> bool {
    |k: Key| exists|d: Dom| #[trigger] pend.contains(d) && member(d, k)
}

pub open spec fn in_erasing(e: Option<Ers>) -> spec_fn(Key) -> bool {
    |k: Key| e is Some && member(e->0.e, k)
}

// ------------------------------------------------------------------------------------------------ invariants

/// C1: in the committed view, every recorded edge has its statement entry and every statement entry of a key with
/// recorded provenance names a live edge.
pub open spec fn c_stmt_ok(x: BizS, k: Key) -> bool {
    k.edge && !cunrec(x, k) ==> (cstmt(x, k) <==> crow(x, k) is Some)
}

/// C2: outside the pending domains, at every key with recorded provenance, replay equals the committed rows.
pub open spec fn c_replay_ok(x: BizS, k: Key) -> bool {
    !in_pend(x.pend)(k) && !cunrec(x, k) ==> oget(replay(x.rl.l.hist), k) == crow(x, k)
}

/// The open erasure's overlay at k.
pub open spec fn ers_key_ok(x: BizS, r: Ers, k: Key) -> bool {
    &&& (r.saved.contains_key(k) ==> member(r.e, k) && !x.st.rows.contains_key(k) && !x.wr.open.contains_key(k))
    &&& (member(r.e, k) && x.st.rows.contains_key(k) ==> x.st.unrec.contains(k))
    &&& (member(r.e, k) && !r.saved.contains_key(k) && crow(x, k) is Some ==> cunrec(x, k))
    &&& (r.idx && x.st.stmts.contains(k) ==> !member(r.e, k))
    &&& (r.idx && x.st.shist.contains(k) ==> !member(r.e, k))
}

/// Overlay: what the visible state adds to the committed view at k.
pub open spec fn overlay_ok(x: BizS, k: Key) -> bool {
    &&& (x.wr.open.contains_key(k) ==> x.st.unrec.contains(k))
    &&& (cstmt(x, k) ==> k.edge)
    &&& (x.st.erasing is Some ==> ers_key_ok(x, x.st.erasing->0, k))
}

/// C3: while a target is marked, no key its record match selects holds recorded content in the committed view.
pub open spec fn mark_key_ok(x: BizS, k: Key) -> bool {
    x.rl.l.marker is Some && member(x.rl.l.marker->0.rm, k) && crow(x, k) is Some ==> cunrec(x, k)
}

/// k holds content of **any** provenance (recorded or written outside the ledger): visible now, or left by a rollback
/// of the open transactions.
pub open spec fn any_content(x: BizS, k: Key) -> bool { x.st.rows.contains_key(k) || crow(x, k) is Some }

/// C4 (D-9c, G-BM): while a target is marked, no key its record match selects holds content of any provenance —
/// no visible row, no open transaction on it, nothing an open erasure would restore.
pub open spec fn mark_key_all(x: BizS, k: Key) -> bool {
    x.rl.l.marker is Some && member(x.rl.l.marker->0.rm, k)
        ==> !x.st.rows.contains_key(k) && !x.wr.open.contains_key(k) && !saved_in(x.st, k)
}

pub open spec fn key_ok(x: BizS, k: Key) -> bool {
    &&& c_stmt_ok(x, k)
    &&& c_replay_ok(x, k)
    &&& overlay_ok(x, k)
    &&& mark_key_ok(x, k)
    &&& mark_key_all(x, k)
}

/// Everything before the cursor, and everything from the scan bound on, holds no live record the target matches.
pub open spec fn cursor_ok(h: Seq<Seq<Rec>>, c: Cur) -> bool {
    &&& c.i <= c.end && c.end <= h.len()
    &&& c.i < c.end ==> c.j <= h[c.i as int].len()
    &&& c.i == c.end ==> c.j == 0
    &&& forall|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].len() && (i < c.i || (i == c.i && j < c.j) || i >= c.end)
            ==> !live_member(#[trigger] h[i][j], c.t)
}

pub open spec fn tally_ok(tally: Seq<Content>, d: Dom) -> bool {
    forall|i: int| 0 <= i < tally.len() ==> member(d, #[trigger] tally[i].k)
}

pub open spec fn mark_ok(x: BizS) -> bool {
    let t = x.rl.l.marker->0;
    &&& x.pend.contains(t.rm)
    &&& aligned(t)
    &&& cursor_ok(x.rl.l.hist, dcur(x.rl.l))
    &&& tally_ok(x.rl.l.tally, t.rm)
}

pub open spec fn inv_parts(x: BizS) -> bool {
    ledger_inv(x.rl.l) && red_inv(x.rl.r) && attr_ok(x.rl.l) && store_inv(x.st) && wr_inv(x.wr)
}

pub open spec fn biz_inv(x: BizS) -> bool {
    &&& inv_parts(x)
    &&& x.rl.l.locked == (x.st.erasing is Some)
    &&& (x.rl.l.marker is Some ==> mark_ok(x))
    &&& forall|k: Key| #[trigger] key_ok(x, k)
}

/// No erasure, no redaction run, no bypass transaction under way.
pub open spec fn settled(x: BizS) -> bool {
    x.pend == Set::<Dom>::empty() && x.st.erasing is None && no_open(x.wr)
}

// ------------------------------------------------------------------------------------------------ helper lemmas

pub proof fn lemma_cursor_push(h: Seq<Seq<Rec>>, c: Cur, rs: Seq<Rec>)
    requires cursor_ok(h, c), forall|j: int| 0 <= j < rs.len() ==> !live_member(#[trigger] rs[j], c.t),
    ensures cursor_ok(h.push(rs), c),
{
    let h2 = h.push(rs);
    assert forall|i: int, j: int| 0 <= i < h2.len() && 0 <= j < h2[i].len() && (i < c.i || (i == c.i && j < c.j) || i >= c.end)
        implies !live_member(#[trigger] h2[i][j], c.t) by {
        if i < h.len() { assert(h2[i] == h[i]); } else { assert(h2[i] == rs); }
    }
    if c.i < c.end { assert(h2[c.i as int] == h[c.i as int]); }
}

/// A commit keeps the cursor facts whether the run's bound stays (D-2, reviewed) or moves to the new head (the
/// progress-only control `control_bound_follows_tail`): widening the scan window never breaks them.
pub proof fn lemma_cursor_commit(h: Seq<Seq<Rec>>, c: Cur, rs: Seq<Rec>, e2: nat)
    requires
        cursor_ok(h, c), forall|j: int| 0 <= j < rs.len() ==> !live_member(#[trigger] rs[j], c.t),
        e2 == c.end || e2 == h.len() + 1,
    ensures cursor_ok(h.push(rs), Cur { end: e2, ..c }),
{
    if e2 == c.end {
        lemma_cursor_push(h, c, rs);
        assert(Cur { end: e2, ..c } == c);
    } else {
        let h2 = h.push(rs);
        let c2 = Cur { end: e2, ..c };
        assert forall|i: int, j: int| 0 <= i < h2.len() && 0 <= j < h2[i].len() && (i < c2.i || (i == c2.i && j < c2.j) || i >= c2.end)
            implies !live_member(#[trigger] h2[i][j], c2.t) by {
            assert(i < h.len());
            assert(h2[i] == h[i]);
        }
        if c.i < c.end { assert(h2[c.i as int] == h[c.i as int]); }
    }
}

pub open spec fn tomb_hist(h: Seq<Seq<Rec>>, i: nat, j: nat) -> Seq<Seq<Rec>> {
    h.update(i as int, h[i as int].update(j as int, Rec::Tomb(h[i as int][j as int]->Live_0)))
}

pub proof fn lemma_cursor_scan(h: Seq<Seq<Rec>>, c: Cur)
    requires cursor_ok(h, c), c.i < c.end, c.i < h.len(),
    ensures ({
        let re = c.j >= h[c.i as int].len();
        let hit = !re && live_member(h[c.i as int][c.j as int], c.t);
        let h2 = if hit { tomb_hist(h, c.i, c.j) } else { h };
        let c2 = if re { Cur { i: c.i + 1, j: 0, ..c } } else { Cur { j: c.j + 1, ..c } };
        cursor_ok(h2, c2)
    }),
{
    let re = c.j >= h[c.i as int].len();
    let hit = !re && live_member(h[c.i as int][c.j as int], c.t);
    let h2 = if hit { tomb_hist(h, c.i, c.j) } else { h };
    let c2 = if re { Cur { i: c.i + 1, j: 0, ..c } } else { Cur { j: c.j + 1, ..c } };
    assert(h2.len() == h.len());
    assert forall|i: int| 0 <= i < h.len() implies (#[trigger] h2[i]).len() == h[i].len() by {}
    assert forall|i: int, j: int| 0 <= i < h2.len() && 0 <= j < h2[i].len() && (i < c2.i || (i == c2.i && j < c2.j) || i >= c2.end)
        implies !live_member(#[trigger] h2[i][j], c2.t) by {
        if hit && i == c.i && j == c.j {
        } else {
            assert(h2[i][j] == h[i][j]);
            if re { assert(i < c.i || (i == c.i && j < c.j) || i >= c.end); }
        }
    }
    if c2.i < c2.end { assert(h2[c2.i as int].len() == h[c2.i as int].len()); }
}

/// Where a resumed run continues: the marker's cursor, or (progress-only control) the first record.
pub open spec fn resume_cursor(c: Cur) -> Cur { if resume_rewinds() { Cur { i: 0, j: 0, ..c } } else { c } }

pub proof fn lemma_cursor_resume(h: Seq<Seq<Rec>>, c: Cur)
    requires cursor_ok(h, c),
    ensures cursor_ok(h, resume_cursor(c)),
{
}

/// At the bound, no live record the target matches is left anywhere.
pub proof fn lemma_cursor_done(h: Seq<Seq<Rec>>, c: Cur)
    requires cursor_ok(h, c), c.i == c.end,
    ensures no_member(h, c.t),
{
    assert forall|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].len() implies !live_member(#[trigger] h[i][j], c.t) by {
        assert(i < c.i || i >= c.end);
    }
}

pub proof fn lemma_tomb_replay(h: Seq<Seq<Rec>>, i: nat, j: nat, d: spec_fn(Key) -> bool)
    requires i < h.len(), j < h[i as int].len(), h[i as int][j as int] is Live, d(h[i as int][j as int]->Live_0.k),
    ensures agree(replay(tomb_hist(h, i, j)), replay(h), d),
{
    let h2 = tomb_hist(h, i, j);
    assert forall|a: int| 0 <= a < h2.len() implies (#[trigger] h2[a]).len() == h[a].len() by {}
    assert forall|a: int, b: int| 0 <= a < h2.len() && 0 <= b < h2[a].len() implies rec_eqv(#[trigger] h2[a][b], h[a][b], d) by {
        if a == i && b == j {
        } else {
            assert(h2[a][b] == h[a][b]);
        }
    }
    lemma_agree_hist(h2, h, d);
}

pub proof fn lemma_pend_insert(pend: Set<Dom>, d: Dom, k: Key)
    ensures in_pend(pend)(k) ==> in_pend(pend.insert(d))(k), member(d, k) ==> in_pend(pend.insert(d))(k),
{
    if in_pend(pend)(k) {
        let d2 = choose|d2: Dom| #[trigger] pend.contains(d2) && member(d2, k);
        assert(pend.insert(d).contains(d2));
    }
    if member(d, k) { assert(pend.insert(d).contains(d)); }
}

} // verus!
