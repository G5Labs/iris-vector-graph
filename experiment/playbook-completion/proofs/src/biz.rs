//! The outer business contract `Biz` of erase -> redact -> replay, and its safety invariants.
//!
//! `Biz` is the level-2 protocol's outer contract (`protocol_sys`). Its state is the redaction ledger (`RL`: the
//! ledger and the redaction runs), the store, and `pend`: the targets whose erasure or redaction is under way (an
//! erasure of t, or a run of t, adds t; the run's successful final step removes it). Its steps are the reviewed
//! design's transactions, with the store's part decided in the same step: the eraser holds the ledger head lock
//! from its row deletes to its statement cleanup (HD-1201); Start checks liveness and writes its marker in one
//! locked step (HD-1301); Final runs under its own marker and re-checks liveness; a replayed retry changes nothing
//! (HD-1305).
//!
//! Business invariants (`biz_inv`), each proved inductive here (`impl SafeContract for Biz`):
//! - **No tombstone of live content**: while a marker names t, nothing of t is live (`mark_ok`), and a tombstone is
//!   written only for a live record of the marker's target, so the record's key is never live when it is
//!   tombstoned (`theorem_no_tombstone_of_live`).
//! - **Per-target audit counts**: the counter counts exactly the tally of records tombstoned under the current
//!   marker, all of the marker's target; the audit names its target and that count
//!   (`theorem_audit_counts_own_target`).
//! - **Marker owned by one target**: only a process of the marker's target scans (from the marker's cursor) or
//!   finishes, and no step hands a set marker to another target (`theorem_marker_owned`).
//! - **Statement entries match live edges** outside an open erasure (`theorem_statements_match`).
//! - **Replay equals store once settled**: outside the pending targets the replay of the history equals the store;
//!   with nothing pending they are equal (`theorem_replay_settled`).
//!
//! Premise named here: P-C02 every content write goes through a ledger commit (no ledger-bypassing writes to the
//! modelled tables; the post-commit properties of a first commit are outside the model, HD-1105).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::protocol_rl::*;

verus! {

pub struct BizS { pub rl: RLS, pub st: StoreS, pub pend: Set<Tgt> }

pub enum BizL {
    /// A ledger commit; its records are applied to the store in the same transaction.
    Commit { cs: Seq<Content>, key: Option<IKey> },
    /// A retry with a bound key, carrying the client's post-commit properties.
    Replay { key: IKey, props: Seq<Content> },
    /// An erasure's row deletes (it takes the head lock and keeps it).
    EraseRows { t: Tgt },
    /// The erasure's statement cleanup and commit (it releases the head lock).
    EraseIndex { t: Tgt },
    SetEnabled { on: bool },
    Open { p: nat, t: Tgt },
    Start { p: nat, fresh: bool },
    Scan { p: nat },
    ToFinal { p: nat },
    Final { p: nat, ok: bool },
    Stop { p: nat },
}

pub open spec fn rl_label(l: BizL) -> RLL {
    match l {
        BizL::Commit { cs, key } => RLL::Commit { cs, key },
        BizL::Replay { key, props } => RLL::Replay { key },
        BizL::EraseRows { t } => RLL::Lock,
        BizL::EraseIndex { t } => RLL::Unlock,
        BizL::SetEnabled { on } => RLL::SetEnabled { on },
        BizL::Open { p, t } => RLL::Open { p, t },
        BizL::Start { p, fresh } => RLL::Start { p, fresh },
        BizL::Scan { p } => RLL::Scan { p },
        BizL::ToFinal { p } => RLL::ToFinal { p },
        BizL::Final { p, ok } => RLL::Final { p, ok },
        BizL::Stop { p } => RLL::Stop { p },
    }
}

pub open spec fn pend_after(rl: RLS, pend: Set<Tgt>, l: BizL) -> Set<Tgt> {
    match l {
        BizL::EraseRows { t } => pend.insert(t),
        BizL::Start { p, fresh } => if fresh { pend.insert(tgt_of(rl.r, p)) } else { pend },
        BizL::Final { p, ok } => if ok { pend.remove(tgt_of(rl.r, p)) } else { pend },
        _ => pend,
    }
}

/// The store's part of each step, and the liveness reads made in the same step.
pub open spec fn store_next(x: BizS, l: BizL, st2: StoreS) -> bool {
    match l {
        BizL::Commit { cs, key } => st2 == store_apply(x.st, cs),
        BizL::EraseRows { t } => x.st.erasing is None && st2 == store_erase_rows(x.st, t),
        BizL::EraseIndex { t } => x.st.erasing == Some(t) && st2 == store_erase_index(x.st, t),
        BizL::Start { p, fresh } => !live_in(x.st.rows, tgt_of(x.rl.r, p)) && st2 == x.st,
        BizL::Final { p, ok } => ok == !live_in(x.st.rows, tgt_of(x.rl.r, p)) && st2 == x.st,
        _ => st2 == x.st,
    }
}

pub open spec fn biz_next(x: BizS, l: BizL, y: BizS) -> bool {
    &&& rl_next(x.rl, rl_label(l), y.rl)
    &&& store_next(x, l, y.st)
    &&& y.pend == pend_after(x.rl, x.pend, l)
}

pub struct Biz;

impl Contract for Biz {
    type S = BizS;
    type L = BizL;

    open spec fn init(x: BizS) -> bool {
        RL::init(x.rl) && Store::init(x.st) && x.pend == Set::<Tgt>::empty()
    }

    open spec fn next(x: BizS, l: BizL, y: BizS) -> bool { biz_next(x, l, y) }
}

// ------------------------------------------------------------------------------------------------ the invariants

pub open spec fn in_pend(pend: Set<Tgt>) -> spec_fn(Key) -> bool {
    |k: Key| exists|t: Tgt| #[trigger] pend.contains(t) && member(t, k)
}

/// Everything before the cursor, and everything from the scan bound on, holds no live record of the run's target.
pub open spec fn cursor_ok(h: Seq<Seq<Rec>>, c: Cur) -> bool {
    &&& c.i <= c.end && c.end <= h.len()
    &&& c.i < c.end ==> c.j <= h[c.i as int].len()
    &&& c.i == c.end ==> c.j == 0
    &&& forall|i: int, j: int| 0 <= i < h.len() && 0 <= j < h[i].len() && (i < c.i || (i == c.i && j < c.j) || i >= c.end)
            ==> !live_member(#[trigger] h[i][j], c.t)
}

pub open spec fn tally_ok(tally: Seq<Content>, t: Tgt) -> bool {
    forall|i: int| 0 <= i < tally.len() ==> member(t, #[trigger] tally[i].k)
}

pub open spec fn inv_parts(x: BizS) -> bool { ledger_inv(x.rl.l) && red_inv(x.rl.r) && store_inv(x.st) }

/// The head lock is held across steps exactly while an erasure is open.
pub open spec fn inv_lock(x: BizS) -> bool { x.rl.l.locked == (x.st.erasing is Some) }

pub open spec fn inv_erase(x: BizS) -> bool {
    x.st.erasing is Some ==> x.pend.contains(x.st.erasing->0) && !live_in(x.st.rows, x.st.erasing->0)
}

pub open spec fn mark_ok(x: BizS) -> bool {
    let t = x.rl.l.marker->0;
    let c = dcur(x.rl.l);
    &&& x.pend.contains(t)
    &&& !live_in(x.st.rows, t)
    &&& cursor_ok(x.rl.l.hist, c)
    &&& tally_ok(x.rl.l.tally, t)
}

pub open spec fn inv_mark(x: BizS) -> bool {
    x.rl.l.marker is Some ==> mark_ok(x)
}

pub open spec fn inv_stmts(x: BizS) -> bool { edges_ok(x.st.rows, x.st.stmts, in_erasing(x.st.erasing)) }

pub open spec fn inv_replay(x: BizS) -> bool { agree(replay(x.rl.l.hist), x.st.rows, in_pend(x.pend)) }

pub open spec fn biz_inv(x: BizS) -> bool {
    &&& inv_parts(x)
    &&& inv_lock(x)
    &&& inv_erase(x)
    &&& inv_mark(x)
    &&& inv_stmts(x)
    &&& inv_replay(x)
}

// ------------------------------------------------------------------------------------------------ helper lemmas

pub proof fn lemma_pend_mono(p1: Set<Tgt>, p2: Set<Tgt>)
    requires forall|t: Tgt| #[trigger] p1.contains(t) ==> p2.contains(t),
    ensures forall|k: Key| #[trigger] in_pend(p1)(k) ==> in_pend(p2)(k),
{
    assert forall|k: Key| #[trigger] in_pend(p1)(k) implies in_pend(p2)(k) by {
        let t = choose|t: Tgt| #[trigger] p1.contains(t) && member(t, k);
        assert(p2.contains(t));
    }
}

pub proof fn lemma_outside_agree(rows: Map<Key, int>, t: Tgt, d: spec_fn(Key) -> bool)
    requires forall|k: Key| #[trigger] member(t, k) ==> d(k),
    ensures agree(rows, outside(rows, t), d),
{
    let o = outside(rows, t);
    assert forall|k: Key| #![trigger rows.contains_key(k)] #![trigger o.contains_key(k)]
        !d(k) implies (rows.contains_key(k) <==> o.contains_key(k)) && (rows.contains_key(k) ==> rows[k] == o[k]) by {
        assert(!member(t, k));
    }
}

pub proof fn lemma_outside_not_live(rows: Map<Key, int>, t: Tgt, m: Tgt)
    requires !live_in(rows, m) || m == t,
    ensures !live_in(outside(rows, t), m),
{
    let o = outside(rows, t);
    if live_in(o, m) {
        let k = choose|k: Key| #[trigger] o.contains_key(k) && member(m, k);
        assert(rows.contains_key(k) && !member(t, k));
    }
}

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

/// At the bound, no live record of the target is left anywhere.
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

// ------------------------------------------------------------------------------------------------ step lemmas

proof fn lemma_commit(x: BizS, cs: Seq<Content>, key: Option<IKey>, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Commit { cs, key }, y),
    ensures biz_inv(y),
{
    let l = x.rl.l;
    lemma_rl_safe(x.rl, RLL::Commit { cs, key }, y.rl);
    lemma_store_safe(x.st, StoreL::Apply { cs });
    assert(y.rl.l == ledger_commit(l, cs, key));
    assert(x.st.erasing is None);
    lemma_stmts_recs(x.st.rows, x.st.stmts, lives(cs), in_erasing(x.st.erasing));
    lemma_replay_push(l.hist, lives(cs));
    lemma_agree_recs(replay(l.hist), x.st.rows, lives(cs), lives(cs), in_pend(x.pend));
    if l.marker is Some {
        let t = l.marker->0;
        let c = dcur(l);
        assert(!touches(cs, t));
        lemma_lives_no_member(cs, t);
        lemma_recs_no_member(x.st.rows, lives(cs), t);
        lemma_cursor_push(l.hist, c, lives(cs));
    }
}

proof fn lemma_erase_rows(x: BizS, t: Tgt, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseRows { t }, y),
    ensures biz_inv(y),
{
    lemma_rl_safe(x.rl, RLL::Lock, y.rl);
    lemma_store_safe(x.st, StoreL::EraseRows { t });
    let rows2 = outside(x.st.rows, t);
    assert(y.st.rows == rows2);
    lemma_outside_not_live(x.st.rows, t, t);
    if x.rl.l.marker is Some { lemma_outside_not_live(x.st.rows, t, x.rl.l.marker->0); }
    assert forall|k: Key| #[trigger] rows2.contains_key(k) && k.edge && !in_erasing(y.st.erasing)(k) implies y.st.stmts.contains(k) by {
        assert(x.st.rows.contains_key(k));
    }
    let d = in_pend(x.pend);
    let d2 = in_pend(y.pend);
    lemma_pend_mono(x.pend, y.pend);
    assert forall|k: Key| #[trigger] member(t, k) implies d2(k) by { assert(y.pend.contains(t)); }
    lemma_agree_mono(replay(x.rl.l.hist), x.st.rows, d, d2);
    lemma_outside_agree(x.st.rows, t, d2);
    lemma_agree_trans(replay(x.rl.l.hist), x.st.rows, rows2, d2);
}

proof fn lemma_erase_index(x: BizS, t: Tgt, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseIndex { t }, y),
    ensures biz_inv(y),
{
    lemma_rl_safe(x.rl, RLL::Unlock, y.rl);
    lemma_store_safe(x.st, StoreL::EraseIndex { t });
    assert forall|k: Key| #[trigger] y.st.rows.contains_key(k) && k.edge && !in_erasing(y.st.erasing)(k) implies y.st.stmts.contains(k) by {
        if member(t, k) {
            assert(live_in(x.st.rows, t));
        } else {
            assert(x.st.stmts.contains(k));
        }
    }
}

proof fn lemma_start(x: BizS, p: nat, fresh: bool, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Start { p, fresh }, y),
    ensures biz_inv(y),
{
    let l = x.rl.l;
    let r = x.rl.r;
    let t = tgt_of(r, p);
    lemma_rl_safe(x.rl, RLL::Start { p, fresh }, y.rl);
    lemma_pend_mono(x.pend, y.pend);
    lemma_agree_mono(replay(l.hist), x.st.rows, in_pend(x.pend), in_pend(y.pend));
    if fresh {
        let c = Cur { t, i: 0, j: 0, end: l.hist.len() };
        assert(dcur(y.rl.l) == c);
        assert(l.tally.len() == 0);
        assert(cursor_ok(l.hist, c));
        assert(y.pend.contains(t));
    } else {
        lemma_cursor_resume(l.hist, dcur(l));
        assert(dcur(y.rl.l) == resume_cursor(dcur(l)));
    }
}

proof fn lemma_scan(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Scan { p }, y),
    ensures biz_inv(y),
{
    let l = x.rl.l;
    let r = x.rl.r;
    let c = pcur(r, p);
    let t = c.t;
    assert(c == dcur(l));
    lemma_rl_safe(x.rl, RLL::Scan { p }, y.rl);
    lemma_cursor_scan(l.hist, c);
    assert(dcur(y.rl.l) == (if row_end(l, c) { Cur { i: c.i + 1, j: 0, ..c } } else { Cur { j: c.j + 1, ..c } }));
    if hit(l, c) {
        let c0 = l.hist[c.i as int][c.j as int]->Live_0;
        assert(y.rl.l.hist == tomb_hist(l.hist, c.i, c.j));
        assert(y.rl.l.tally == l.tally.push(c0));
        assert(member(t, c0.k));
        assert(x.pend.contains(t));
        assert(in_pend(x.pend)(c0.k));
        lemma_tomb_replay(l.hist, c.i, c.j, in_pend(x.pend));
        lemma_agree_trans(replay(y.rl.l.hist), replay(l.hist), x.st.rows, in_pend(x.pend));
        assert(tally_ok(y.rl.l.tally, t)) by {
            assert forall|i: int| 0 <= i < y.rl.l.tally.len() implies member(t, #[trigger] y.rl.l.tally[i].k) by {
                if i < l.tally.len() { assert(y.rl.l.tally[i] == l.tally[i]); }
            }
        }
    }
}

proof fn lemma_final(x: BizS, p: nat, ok: bool, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Final { p, ok }, y),
    ensures biz_inv(y),
{
    let l = x.rl.l;
    let r = x.rl.r;
    let t = tgt_of(r, p);
    let c = dcur(l);
    lemma_rl_safe(x.rl, RLL::Final { p, ok }, y.rl);
    if ok {
        assert(!live_in(x.st.rows, t));
        lemma_cursor_done(l.hist, c);
        lemma_replay_no_member(l.hist, t);
        if l.count > 0 { lemma_replay_audit(l.hist, t, l.count); }
        assert(replay(y.rl.l.hist) == replay(l.hist));
        let h = replay(l.hist);
        let rows = x.st.rows;
        let d = in_pend(x.pend);
        let d2 = in_pend(y.pend);
        assert forall|k: Key| #![trigger h.contains_key(k)] #![trigger rows.contains_key(k)]
            !d2(k) implies (h.contains_key(k) <==> rows.contains_key(k)) && (h.contains_key(k) ==> h[k] == rows[k]) by {
            if d(k) {
                let t2 = choose|t2: Tgt| #[trigger] x.pend.contains(t2) && member(t2, k);
                if t2 != t { assert(y.pend.contains(t2)); }
                assert(member(t, k));
                if h.contains_key(k) { assert(live_in(h, t)); }
                if rows.contains_key(k) { assert(live_in(rows, t)); }
            }
        }
    } else {
        assert(live_in(x.st.rows, t));
    }
}

/// Each step keeps the business invariants.
pub proof fn lemma_biz_safe(x: BizS, l: BizL, y: BizS)
    requires biz_inv(x), biz_next(x, l, y),
    ensures biz_inv(y),
{
    match l {
        BizL::Commit { cs, key } => lemma_commit(x, cs, key, y),
        BizL::EraseRows { t } => lemma_erase_rows(x, t, y),
        BizL::EraseIndex { t } => lemma_erase_index(x, t, y),
        BizL::Start { p, fresh } => lemma_start(x, p, fresh, y),
        BizL::Scan { p } => lemma_scan(x, p, y),
        BizL::Final { p, ok } => lemma_final(x, p, ok, y),
        _ => { lemma_rl_safe(x.rl, rl_label(l), y.rl); }
    }
}

impl SafeContract for Biz {
    open spec fn inv(x: BizS) -> bool { biz_inv(x) }

    proof fn init_safe(x: BizS) {
        assert(replay(x.rl.l.hist) == Map::<Key, int>::empty());
    }

    proof fn step_safe(x: BizS, l: BizL, y: BizS) { lemma_biz_safe(x, l, y); }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// **No tombstone of live content.** No step turns a record into a tombstone while its key is live, before or after
/// the step (spec 256 FR-005, ADR-0013 "Redaction only follows erasure"; F-1302 is the pin's violation).
pub proof fn theorem_no_tombstone_of_live(x: BizS, l: BizL, y: BizS, i: int, j: int)
    requires
        biz_inv(x), biz_next(x, l, y),
        0 <= i < x.rl.l.hist.len(), 0 <= j < x.rl.l.hist[i].len(),
        x.rl.l.hist[i][j] is Live, y.rl.l.hist[i][j] is Tomb,
    ensures
        !x.st.rows.contains_key(x.rl.l.hist[i][j]->Live_0.k),
        !y.st.rows.contains_key(x.rl.l.hist[i][j]->Live_0.k),
{
    let h = x.rl.l.hist;
    match l {
        BizL::Commit { cs, key } => { assert(y.rl.l.hist[i] == h[i]); }
        BizL::Final { p, ok } => {
            if ok && x.rl.l.count > 0 { assert(y.rl.l.hist[i] == h[i]); }
        }
        BizL::Scan { p } => {
            let c = pcur(x.rl.r, p);
            if hit(x.rl.l, c) {
                if i != c.i || j != c.j { assert(y.rl.l.hist[i][j] == h[i][j]); }
                let k = h[i][j]->Live_0.k;
                assert(member(c.t, k));
                if x.st.rows.contains_key(k) { assert(live_in(x.st.rows, c.t)); }
            }
        }
        _ => {}
    }
}

/// **Per-target audit counts.** A successful final step runs under its own target's marker; when it writes an audit
/// revision, that revision names its target and counts exactly the tally of records tombstoned since the target was
/// marked, every one of them a record of that target; it writes none when nothing was tombstoned (Decision 1,
/// HD-1301; F-1303 is the pin's violation).
pub proof fn theorem_audit_counts_own_target(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Final { p, ok: true }, y),
    ensures ({
        let t = tgt_of(x.rl.r, p);
        let l = x.rl.l;
        &&& l.marker == Some(t)
        &&& tally_ok(l.tally, t)
        &&& l.count == l.tally.len()
        &&& l.count > 0 ==> y.rl.l.hist == l.hist.push(seq![Rec::Audit { t, n: l.tally.len() }])
        &&& l.count == 0 ==> y.rl.l.hist == l.hist
        &&& y.rl.l.marker is None && y.rl.l.count == 0 && y.rl.l.tally.len() == 0
    }),
{
}

/// Every tombstone the redaction writes joins the tally of the target that owns the marker, and is a record of it.
pub proof fn theorem_tally_counts_own_target(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Scan { p }, y), hit(x.rl.l, pcur(x.rl.r, p)),
    ensures ({
        let c = pcur(x.rl.r, p);
        let c0 = x.rl.l.hist[c.i as int][c.j as int]->Live_0;
        &&& x.rl.l.marker == Some(tgt_of(x.rl.r, p))
        &&& member(tgt_of(x.rl.r, p), c0.k)
        &&& y.rl.l.tally == x.rl.l.tally.push(c0)
        &&& y.rl.l.count == x.rl.l.count + 1
    }),
{
}

/// **Marker owned by one target.** Only a step of a process of the marker's target scans (from the marker's cursor)
/// or finishes; a fresh start needs no marker, a resume its own; and no step hands a set marker to another target.
pub proof fn theorem_marker_owned(x: BizS, l: BizL, y: BizS)
    requires biz_inv(x), biz_next(x, l, y),
    ensures
        x.rl.l.marker is Some && y.rl.l.marker is Some ==> y.rl.l.marker == x.rl.l.marker,
        match l {
            BizL::Scan { p } => x.rl.l.marker == Some(tgt_of(x.rl.r, p)) && pcur(x.rl.r, p) == dcur(x.rl.l),
            BizL::Final { p, ok } => x.rl.l.marker == Some(tgt_of(x.rl.r, p)) && pcur(x.rl.r, p) == dcur(x.rl.l),
            BizL::Start { p, fresh } => fresh == (x.rl.l.marker is None) && (!fresh ==> x.rl.l.marker == Some(tgt_of(x.rl.r, p))),
            _ => true,
        },
{
}

/// **Statement entries match live edges** outside an open erasure (ADR-0004 in both directions; F-1201 is the pin's
/// violation).
pub proof fn theorem_statements_match(x: BizS, k: Key)
    requires biz_inv(x), k.edge, !in_erasing(x.st.erasing)(k),
    ensures x.st.stmts.contains(k) <==> x.st.rows.contains_key(k),
{
}

/// No erasure and no redaction is under way.
pub open spec fn settled(x: BizS) -> bool { x.pend == Set::<Tgt>::empty() }

/// **Replay equals store once settled** (spec 256 FR-007, `verify()` reports `equal`).
pub proof fn theorem_replay_settled(x: BizS)
    requires biz_inv(x), settled(x),
    ensures
        replay(x.rl.l.hist) =~= x.st.rows,
        x.rl.l.marker is None,
        x.st.erasing is None,
{
    let h = replay(x.rl.l.hist);
    assert forall|k: Key| #[trigger] h.contains_key(k) <==> x.st.rows.contains_key(k) by {
        if in_pend(x.pend)(k) {
            let t = choose|t: Tgt| #[trigger] x.pend.contains(t) && member(t, k);
        }
    }
    assert forall|k: Key| #[trigger] h.contains_key(k) implies h[k] == x.st.rows[k] by {
        if in_pend(x.pend)(k) {
            let t = choose|t: Tgt| #[trigger] x.pend.contains(t) && member(t, k);
        }
    }
    if x.rl.l.marker is Some { assert(x.pend.contains(x.rl.l.marker->0)); }
    if x.st.erasing is Some { assert(x.pend.contains(x.st.erasing->0)); }
}

} // verus!
