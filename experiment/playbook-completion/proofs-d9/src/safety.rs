//! The business invariants of `Biz` are inductive (`impl SafeContract for Biz`): one lemma per operation, over the
//! named conjuncts of `biz::biz_inv`, with the per-key part (`key_ok`) proved key by key.
//!
//! "View" lemmas state what each step does to the committed view: opening a transaction (EraseRows, EraseIndex,
//! BBegin) and rolling one back (EraseAbort, BAbort) leave it unchanged; only commits (ledger Commit, EraseCommit,
//! BCommit) and the redaction's own transactions change it. That is the model's form of "a rollback after a liveness
//! check saw the transaction cannot hurt": the reviewed design never lets a check see what the view does not hold.
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
use crate::biz::*;

verus! {

/// The committed view at every key is the same in x and y.
pub open spec fn same_view(x: BizS, y: BizS) -> bool {
    forall|k: Key| #![trigger crow(y, k)] #![trigger cunrec(y, k)] #![trigger cstmt(y, k)]
        crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k)
}

// ------------------------------------------------------------------------------------------------ ledger commit

proof fn lemma_commit(x: BizS, cs: Seq<Content>, key: Option<IKey>, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Commit { cs, key }, y),
    ensures biz_inv(y),
{
    let l = x.rl.l;
    let rs = lives(cs);
    assert(rl_next(x.rl, RLL::Commit { cs, key }, y.rl));
    assert(y.rl.l == ledger_commit(l, cs, key) && y.rl.r == x.rl.r);
    assert(y.st == store_apply(x.st, cs));
    assert(y.wr == x.wr && y.pend == x.pend);
    assert(x.st.erasing is None);
    lemma_rl_safe(x.rl, RLL::Commit { cs, key }, y.rl);
    lemma_store_safe(x.st, StoreL::Apply { cs });
    lemma_replay_push(l.hist, rs);
    if l.marker is Some {
        let t = l.marker->0;
        assert(!touches(cs, t.rm));
        lemma_lives_no_member(cs, t.rm);
        lemma_cursor_push(l.hist, dcur(l), rs);
        assert(dcur(y.rl.l) == dcur(l));
    }
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        lemma_recs_at(replay(l.hist), x.st.rows, x.st.stmts, x.st.unrec, rs, k);
        lemma_recs_at(x.st.rows, x.st.rows, x.st.stmts, x.st.unrec, rs, k);
        lemma_lives_touch(cs, k);
        if recs_touch(rs, k) {
            let i = choose|i: int| 0 <= i < cs.len() && #[trigger] cs[i].k == k;
            assert(!x.wr.open.contains_key(cs[i].k));
            if l.marker is Some && member(l.marker->0.rm, k) { assert(member(l.marker->0.rm, cs[i].k)); }
            assert(crow(y, k) == oget(y.st.rows, k));
            assert(!cunrec(y, k));
        } else {
            assert(crow(y, k) == crow(x, k));
            assert(cunrec(y, k) == cunrec(x, k));
            assert(cstmt(y, k) == cstmt(x, k));
        }
    }
}

// ------------------------------------------------------------------------------------------------ erasure

proof fn lemma_erase_rows_view(x: BizS, e: Dom, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseRows { e }, y),
    ensures same_view(x, y), y.st == store_erase_rows(x.st, e), y.wr == x.wr, y.pend == x.pend,
        y.rl == (RLS { l: LedgerS { locked: true, ..x.rl.l }, r: x.rl.r }), x.st.erasing is None,
{
    assert(rl_next(x.rl, RLL::Lock, y.rl));
    assert(y.st == store_erase_rows(x.st, e));
    assert forall|k: Key| #![trigger crow(y, k)] #![trigger cunrec(y, k)] #![trigger cstmt(y, k)]
        crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k) by {
        if x.wr.open.contains_key(k) {
        } else if x.st.rows.contains_key(k) && member(e, k) {
            assert(saved_in(y.st, k));
        } else {
            assert(!saved_in(y.st, k));
        }
    }
}

proof fn lemma_erase_rows(x: BizS, e: Dom, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseRows { e }, y),
    ensures biz_inv(y),
{
    lemma_erase_rows_view(x, e, y);
    lemma_rl_safe(x.rl, RLL::Lock, y.rl);
    lemma_store_safe(x.st, StoreL::EraseRows { e });
    let r = y.st.erasing->0;
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
        if x.wr.open.contains_key(k) { assert(!member(e, k)); }
        assert(ers_key_ok(y, r, k));
    }
}

proof fn lemma_erase_index_view(x: BizS, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseIndex, y),
    ensures same_view(x, y), y.st == store_erase_index(x.st), y.wr == x.wr, y.pend == x.pend, y.rl == x.rl,
{
    assert(y.st == store_erase_index(x.st));
    let r = x.st.erasing->0;
    assert forall|k: Key| #![trigger crow(y, k)] #![trigger cunrec(y, k)] #![trigger cstmt(y, k)]
        crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k) by {
        assert(!r.sst.contains(k));
        assert(saved_in(y.st, k) == saved_in(x.st, k));
    }
}

proof fn lemma_erase_index(x: BizS, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseIndex, y),
    ensures biz_inv(y),
{
    lemma_erase_index_view(x, y);
    lemma_store_safe(x.st, StoreL::EraseIndex);
    let r = x.st.erasing->0;
    let r2 = y.st.erasing->0;
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
        assert(ers_key_ok(x, r, k));
        assert(ers_key_ok(y, r2, k));
    }
}

proof fn lemma_erase_commit(x: BizS, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseCommit, y),
    ensures biz_inv(y),
{
    let r = x.st.erasing->0;
    assert(rl_next(x.rl, RLL::Unlock, y.rl));
    assert(y.st == store_erase_commit(x.st));
    assert(y.wr == x.wr && y.pend == x.pend.insert(r.e));
    lemma_rl_safe(x.rl, RLL::Unlock, y.rl);
    lemma_store_safe(x.st, StoreL::EraseCommit);
    if x.rl.l.marker is Some { assert(y.pend.contains(x.rl.l.marker->0.rm)); }
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        assert(ers_key_ok(x, r, k));
        lemma_pend_insert(x.pend, r.e, k);
        assert(cunrec(y, k) == cunrec(x, k));
        assert(cstmt(y, k) == x.st.stmts.contains(k));
        if member(r.e, k) {
            if r.saved.contains_key(k) {
                assert(crow(y, k) is None);
            } else {
                assert(crow(y, k) == crow(x, k));
            }
        } else {
            assert(!r.saved.contains_key(k) && !r.sst.contains(k));
            assert(crow(y, k) == crow(x, k));
            assert(cstmt(y, k) == cstmt(x, k));
        }
    }
}

proof fn lemma_erase_abort_view(x: BizS, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseAbort, y),
    ensures same_view(x, y), y.st == store_erase_abort(x.st), y.wr == x.wr, y.pend == x.pend,
        y.rl == (RLS { l: LedgerS { locked: false, ..x.rl.l }, r: x.rl.r }),
{
    let r = x.st.erasing->0;
    assert(rl_next(x.rl, RLL::Unlock, y.rl));
    assert(y.st == store_erase_abort(x.st));
    assert forall|k: Key| #![trigger crow(y, k)] #![trigger cunrec(y, k)] #![trigger cstmt(y, k)]
        crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k) by {
        assert(key_ok(x, k));
        assert(ers_key_ok(x, r, k));
        if x.wr.open.contains_key(k) {
        } else if r.saved.contains_key(k) {
            assert(!x.st.rows.contains_key(k));
            assert(y.st.rows.contains_key(k) && y.st.rows[k] == r.saved[k]);
        } else {
            assert(y.st.rows.contains_key(k) == x.st.rows.contains_key(k));
            if x.st.rows.contains_key(k) { assert(y.st.rows[k] == x.st.rows[k]); }
        }
    }
}

proof fn lemma_erase_abort(x: BizS, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::EraseAbort, y),
    ensures biz_inv(y),
{
    lemma_erase_abort_view(x, y);
    lemma_rl_safe(x.rl, RLL::Unlock, y.rl);
    lemma_store_safe(x.st, StoreL::EraseAbort);
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
    }
}

// ------------------------------------------------------------------------------------------------ bypass writers

proof fn lemma_bbegin_view(x: BizS, k0: Key, v: Option<int>, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::BBegin { k: k0, v }, y),
    ensures same_view(x, y), y.st == store_write(x.st, k0, v), y.rl == x.rl, y.pend == x.pend,
        y.wr == (WrS { open: x.wr.open.insert(k0, BTx { before: oget(x.st.rows, k0), was: x.st.unrec.contains(k0) }) }),
        !x.wr.open.contains_key(k0), !saved_in(x.st, k0),
{
    assert(y.st == store_write(x.st, k0, v));
    assert forall|k: Key| #![trigger crow(y, k)] #![trigger cunrec(y, k)] #![trigger cstmt(y, k)]
        crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k) by {
        if k != k0 {
            assert(y.st.rows.contains_key(k) == x.st.rows.contains_key(k));
            if x.st.rows.contains_key(k) { assert(y.st.rows[k] == x.st.rows[k]); }
        }
    }
}

proof fn lemma_bbegin(x: BizS, k0: Key, v: Option<int>, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::BBegin { k: k0, v }, y),
    ensures biz_inv(y),
{
    lemma_bbegin_view(x, k0, v, y);
    lemma_store_safe(x.st, StoreL::Write { k: k0, v });
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
        if k != k0 {
            assert(y.st.rows.contains_key(k) == x.st.rows.contains_key(k));
        }
    }
}

proof fn lemma_bcommit(x: BizS, k0: Key, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::BCommit { k: k0 }, y),
    ensures biz_inv(y),
{
    assert(mid_of(y) == mid_of(x));
    assert(y.rl == x.rl && y.st == x.st && y.pend == x.pend);
    assert(y.wr.open == x.wr.open.remove(k0));
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        if k == k0 {
            assert(x.st.unrec.contains(k0));
            assert(cunrec(y, k0));
            if x.st.erasing is Some { assert(!x.st.erasing->0.saved.contains_key(k0)); }
        } else {
            assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k));
        }
    }
}

proof fn lemma_babort_view(x: BizS, k0: Key, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::BAbort { k: k0 }, y),
    ensures same_view(x, y), y.rl == x.rl, y.pend == x.pend,
        y.st == store_undo(x.st, k0, x.wr.open[k0].before, x.wr.open[k0].was), y.wr.open == x.wr.open.remove(k0),
{
    let b = x.wr.open[k0];
    assert(y.st == store_undo(x.st, k0, b.before, b.was));
    assert forall|k: Key| #![trigger crow(y, k)] #![trigger cunrec(y, k)] #![trigger cstmt(y, k)]
        crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k) by {
        assert(key_ok(x, k));
        if k == k0 {
            if x.st.erasing is Some { assert(!x.st.erasing->0.saved.contains_key(k0)); }
            assert(!saved_in(y.st, k0));
        } else {
            assert(y.st.rows.contains_key(k) == x.st.rows.contains_key(k));
            if x.st.rows.contains_key(k) { assert(y.st.rows[k] == x.st.rows[k]); }
        }
    }
}

proof fn lemma_babort(x: BizS, k0: Key, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::BAbort { k: k0 }, y),
    ensures biz_inv(y),
{
    lemma_babort_view(x, k0, y);
    let b = x.wr.open[k0];
    lemma_store_safe(x.st, StoreL::Undo { k: k0, before: b.before, was: b.was });
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
        if k != k0 {
            assert(y.st.rows.contains_key(k) == x.st.rows.contains_key(k));
        } else if x.st.erasing is Some {
            assert(ers_key_ok(x, x.st.erasing->0, k0));
        }
    }
}

// ------------------------------------------------------------------------------------------------ redaction

proof fn lemma_start(x: BizS, p: nat, fresh: bool, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Start { p, fresh }, y),
    ensures biz_inv(y),
{
    let l = x.rl.l;
    let r = x.rl.r;
    let t = tgt_of(r, p);
    assert(rl_next(x.rl, RLL::Start { p, fresh }, y.rl));
    assert(y.st == x.st && y.wr == x.wr);
    assert(y.pend == if fresh { x.pend.insert(t.rm) } else { x.pend });
    assert(no_open(x.wr));
    assert(x.st.erasing is None);
    assert(aligned(t) && !live_in(x.st.rows, t.lv));
    lemma_rl_safe(x.rl, RLL::Start { p, fresh }, y.rl);
    if fresh {
        let c = Cur { t: t.rm, i: 0, j: 0, end: l.hist.len() };
        assert(y.rl.l.marker == Some(t));
        assert(dcur(y.rl.l) == c);
        assert(l.tally.len() == 0);
        assert(cursor_ok(l.hist, c));
        assert(y.pend.contains(t.rm));
    } else {
        lemma_cursor_resume(l.hist, dcur(l));
        assert(dcur(y.rl.l) == resume_cursor(dcur(l)));
    }
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        lemma_pend_insert(x.pend, t.rm, k);
        assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
        if fresh && member(t.rm, k) {
            assert(!x.wr.open.contains_key(k));
            assert(member(t.lv, k));
            if x.st.rows.contains_key(k) { assert(live_in(x.st.rows, t.lv)); }
            assert(crow(x, k) is None);
        }
    }
}

proof fn lemma_scan(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Scan { p }, y),
    ensures biz_inv(y),
{
    let l = x.rl.l;
    let r = x.rl.r;
    let c = pcur(r, p);
    let t = tgt_of(r, p);
    assert(rl_next(x.rl, RLL::Scan { p }, y.rl));
    assert(y.st == x.st && y.wr == x.wr && y.pend == x.pend);
    assert(c == dcur(l));
    lemma_rl_safe(x.rl, RLL::Scan { p }, y.rl);
    lemma_cursor_scan(l.hist, c);
    assert(y.rl.l.marker == l.marker);
    assert(dcur(y.rl.l) == (if row_end(l, c) { Cur { i: c.i + 1, j: 0, ..c } } else { Cur { j: c.j + 1, ..c } }));
    if hit(l, c) {
        let c0 = l.hist[c.i as int][c.j as int]->Live_0;
        assert(y.rl.l.hist == tomb_hist(l.hist, c.i, c.j));
        assert(y.rl.l.tally == l.tally.push(c0));
        assert(member(t.rm, c0.k));
        assert(x.pend.contains(t.rm));
        assert(in_pend(x.pend)(c0.k));
        lemma_tomb_replay(l.hist, c.i, c.j, in_pend(x.pend));
        assert(tally_ok(y.rl.l.tally, t.rm)) by {
            assert forall|i: int| 0 <= i < y.rl.l.tally.len() implies member(t.rm, #[trigger] y.rl.l.tally[i].k) by {
                if i < l.tally.len() { assert(y.rl.l.tally[i] == l.tally[i]); }
            }
        }
    }
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
        if hit(l, c) && !in_pend(x.pend)(k) {
            let h1 = replay(y.rl.l.hist);
            let h0 = replay(l.hist);
            assert(h1.contains_key(k) == h0.contains_key(k));
            if h1.contains_key(k) { assert(h1[k] == h0[k]); }
            assert(oget(h1, k) == oget(h0, k));
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
    assert(rl_next(x.rl, RLL::Final { p, ok }, y.rl));
    assert(y.wr == x.wr);
    lemma_rl_safe(x.rl, RLL::Final { p, ok }, y.rl);
    assert(x.st.erasing is None);
    if ok {
        assert(y.rl.l == ledger_audit(l, t));
        assert(y.st == store_drop(x.st, t.sc));
        assert(y.pend == x.pend.filter(|d: Dom| !covers(t.rm, d)));
        lemma_store_safe(x.st, StoreL::Drop { sc: t.sc });
        assert(mark_ok(x));
        assert(c.t == t.rm);
        lemma_cursor_done(l.hist, c);
        lemma_replay_no_member(l.hist, t.rm);
        if l.count > 0 { lemma_replay_audit(l.hist, t, l.count); }
        assert(replay(y.rl.l.hist) == replay(l.hist));
        assert forall|k: Key| #[trigger] key_ok(y, k) by {
            assert(key_ok(x, k));
            assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k));
            assert(cstmt(y, k) == (x.st.stmts.contains(k) && !member(t.sc, k)));
            if member(t.sc, k) && k.edge { assert(member(t.rm, k)); }
            if in_pend(x.pend)(k) && !in_pend(y.pend)(k) {
                let d = choose|d: Dom| #[trigger] x.pend.contains(d) && member(d, k);
                if !covers(t.rm, d) { assert(y.pend.contains(d)); }
                assert(member(t.rm, k));
                let h = replay(l.hist);
                if h.contains_key(k) { assert(live_in(h, t.rm)); }
                assert(oget(replay(y.rl.l.hist), k) is None);
            }
        }
    } else {
        assert(y.rl.l == l && y.st == x.st && y.pend == x.pend);
        assert forall|k: Key| #[trigger] key_ok(y, k) by {
            assert(key_ok(x, k));
            assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
        }
    }
}

/// Steps that change only the redactor's or the ledger's flags (Replay, SetEnabled, Open, ToFinal, Stop).
proof fn lemma_quiet(x: BizS, lb: BizL, y: BizS)
    requires
        biz_inv(x), biz_next(x, lb, y),
        lb is Replay || lb is SetEnabled || lb is Open || lb is ToFinal || lb is Stop,
    ensures biz_inv(y),
{
    let m = top_lab_m(mid_of(x), x.wr, lb)->0;
    let a = mid_rl(m)->0;
    assert(rl_next(x.rl, a, y.rl));
    assert(y.st == x.st && y.wr == x.wr && y.pend == x.pend);
    lemma_rl_safe(x.rl, a, y.rl);
    assert(y.rl.l.hist == x.rl.l.hist && y.rl.l.marker == x.rl.l.marker);
    assert(dcur(y.rl.l) == dcur(x.rl.l) && y.rl.l.tally == x.rl.l.tally);
    assert forall|k: Key| #[trigger] key_ok(y, k) by {
        assert(key_ok(x, k));
        assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k) && cstmt(y, k) == cstmt(x, k));
    }
}

/// Each step keeps the business invariants.
pub proof fn lemma_biz_safe(x: BizS, l: BizL, y: BizS)
    requires biz_inv(x), biz_next(x, l, y),
    ensures biz_inv(y),
{
    match l {
        BizL::Commit { cs, key } => lemma_commit(x, cs, key, y),
        BizL::EraseRows { e } => lemma_erase_rows(x, e, y),
        BizL::EraseIndex => lemma_erase_index(x, y),
        BizL::EraseCommit => lemma_erase_commit(x, y),
        BizL::EraseAbort => lemma_erase_abort(x, y),
        BizL::BBegin { k, v } => lemma_bbegin(x, k, v, y),
        BizL::BCommit { k } => lemma_bcommit(x, k, y),
        BizL::BAbort { k } => lemma_babort(x, k, y),
        BizL::Start { p, fresh } => lemma_start(x, p, fresh, y),
        BizL::Scan { p } => lemma_scan(x, p, y),
        BizL::Final { p, ok } => lemma_final(x, p, ok, y),
        _ => lemma_quiet(x, l, y),
    }
}

impl SafeContract for Biz {
    open spec fn inv(x: BizS) -> bool { biz_inv(x) }

    proof fn init_safe(x: BizS) {
        assert(replay(x.rl.l.hist) == Map::<Key, int>::empty());
        assert forall|k: Key| #[trigger] key_ok(x, k) by {
            assert(!x.wr.open.contains_key(k));
        }
    }

    proof fn step_safe(x: BizS, l: BizL, y: BizS) { lemma_biz_safe(x, l, y); }
}

// ------------------------------------------------------------------------------------------------ view theorems

/// **Open and rollback steps do not change the committed view.** An erasure's row deletes and statement cleanup, a
/// bypass transaction's write, and the rollback of either leave, at every key, the row, provenance and statement
/// entry that rolling back every open transaction would leave. (Only commits change it.)
pub proof fn theorem_open_and_rollback_keep_view(x: BizS, l: BizL, y: BizS)
    requires biz_inv(x), biz_next(x, l, y),
        l is EraseRows || l is EraseIndex || l is EraseAbort || l is BBegin || l is BAbort,
    ensures same_view(x, y),
{
    match l {
        BizL::EraseRows { e } => lemma_erase_rows_view(x, e, y),
        BizL::EraseIndex => lemma_erase_index_view(x, y),
        BizL::EraseAbort => lemma_erase_abort_view(x, y),
        BizL::BBegin { k, v } => lemma_bbegin_view(x, k, v, y),
        BizL::BAbort { k } => lemma_babort_view(x, k, y),
        _ => {}
    }
}

} // verus!
