//! Business theorems of the reviewed model (D-9), each proved from `biz_inv` and one `biz_next` step (no other
//! reachability assumption). All are statements about the **model**; none is a property of the product at the pin.
//!
//! Compared with `proofs/src/biz.rs`, the premises dropped are P-C02 (no ledger-bypassing writer), P-C03 (one target
//! predicate) and P-C04 (no erasure rollback). What a bypass writer can do is excluded from a conclusion only where the
//! conclusion is about recorded content: a row last written outside the ledger is not the content of any ledger
//! record (`unrec`, M2's "new incarnation"); with no bypass write, every conclusion is the original one.
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
use crate::safety::*;

verus! {

/// **No tombstone of live content.** A record becomes a tombstone only while its key holds no recorded content: not
/// in the rows other processes see, and not in the rows a rollback of every open transaction (an erasure's, a bypass
/// writer's) would leave; before and after the step (RED-B1.1, FR-005; F-1302, F-1304, F-C1201, F-C1301 are the
/// pin's violations).
pub proof fn theorem_no_tombstone_of_live(x: BizS, l: BizL, y: BizS, i: int, j: int)
    requires
        biz_inv(x), biz_next(x, l, y),
        0 <= i < x.rl.l.hist.len(), 0 <= j < x.rl.l.hist[i].len(),
        x.rl.l.hist[i][j] is Live, y.rl.l.hist[i][j] is Tomb,
    ensures
        !rec_content(x, x.rl.l.hist[i][j]->Live_0.k),
        !rec_content(y, x.rl.l.hist[i][j]->Live_0.k),
{
    let h = x.rl.l.hist;
    let k = h[i][j]->Live_0.k;
    match l {
        BizL::Commit { cs, key } => { assert(y.rl.l.hist[i] == h[i]); }
        BizL::Final { p, ok } => {
            if ok && x.rl.l.count > 0 { assert(y.rl.l.hist[i] == h[i]); }
        }
        BizL::Scan { p } => {
            let c = pcur(x.rl.r, p);
            assert(rl_next(x.rl, RLL::Scan { p }, y.rl));
            assert(y.st == x.st && y.wr == x.wr);
            if hit(x.rl.l, c) {
                if i != c.i || j != c.j { assert(y.rl.l.hist[i][j] == h[i][j]); }
                assert(member(c.t, k));
                assert(x.rl.l.marker == Some(tgt_of(x.rl.r, p)));
                assert(key_ok(x, k));
                assert(x.st.erasing is None);
                if x.wr.open.contains_key(k) { assert(x.st.unrec.contains(k)); }
                assert(crow(y, k) == crow(x, k) && cunrec(y, k) == cunrec(x, k));
            } else {
                assert(y.rl.l.hist == h);
            }
        }
        BizL::Start { p, fresh } => { assert(y.rl.l.hist == h); }
        BizL::EraseRows { e } => { assert(y.rl.l.hist == h); }
        BizL::EraseCommit => { assert(y.rl.l.hist == h); }
        BizL::EraseAbort => { assert(y.rl.l.hist == h); }
        BizL::Replay { key } => { assert(y.rl.l.hist == h); }
        BizL::SetEnabled { on } => { assert(y.rl.l.hist == h); }
        BizL::Open { p, t } => { assert(y.rl.l.hist == h); }
        BizL::ToFinal { p } => { assert(y.rl.l.hist == h); }
        BizL::Stop { p } => { assert(y.rl.l.hist == h); }
        _ => { assert(mid_of(y).rl == x.rl); }
    }
}

/// **Per-target audit counts.** A successful final step runs under its own target's marker; its audit revision names
/// its target and counts exactly the tally of records tombstoned since the target was marked, each one a record its
/// record match selects; none when nothing was tombstoned (Decision 1, HD-1301; F-1303 is the pin's violation).
pub proof fn theorem_audit_counts_own_target(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Final { p, ok: true }, y),
    ensures ({
        let t = tgt_of(x.rl.r, p);
        let l = x.rl.l;
        &&& l.marker == Some(t)
        &&& tally_ok(l.tally, t.rm)
        &&& l.count == l.tally.len()
        &&& l.count > 0 ==> y.rl.l.hist == l.hist.push(seq![Rec::Audit { t, n: l.tally.len() }])
        &&& l.count == 0 ==> y.rl.l.hist == l.hist
        &&& y.rl.l.marker is None && y.rl.l.count == 0 && y.rl.l.tally.len() == 0
    }),
{
    assert(rl_next(x.rl, RLL::Final { p, ok: true }, y.rl));
}

/// Every tombstone joins the tally of the target that owns the marker, and is a record its record match selects.
pub proof fn theorem_tally_counts_own_target(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Scan { p }, y), hit(x.rl.l, pcur(x.rl.r, p)),
    ensures ({
        let c = pcur(x.rl.r, p);
        let c0 = x.rl.l.hist[c.i as int][c.j as int]->Live_0;
        &&& x.rl.l.marker == Some(tgt_of(x.rl.r, p))
        &&& member(tgt_of(x.rl.r, p).rm, c0.k)
        &&& y.rl.l.tally == x.rl.l.tally.push(c0)
        &&& y.rl.l.count == x.rl.l.count + 1
    }),
{
    assert(rl_next(x.rl, RLL::Scan { p }, y.rl));
}

/// **Marker owned by one target.** Only a process of the marker's target scans (from the marker's cursor) or
/// finishes; a fresh start needs no marker, a resume its own; no step hands a set marker to another target.
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
    match l {
        BizL::Scan { p } => { assert(rl_next(x.rl, RLL::Scan { p }, y.rl)); }
        BizL::Final { p, ok } => { assert(rl_next(x.rl, RLL::Final { p, ok }, y.rl)); }
        BizL::Start { p, fresh } => { assert(rl_next(x.rl, RLL::Start { p, fresh }, y.rl)); }
        BizL::Commit { cs, key } => { assert(rl_next(x.rl, RLL::Commit { cs, key }, y.rl)); }
        BizL::EraseRows { e } => { assert(rl_next(x.rl, RLL::Lock, y.rl)); }
        BizL::EraseCommit => { assert(rl_next(x.rl, RLL::Unlock, y.rl)); }
        BizL::EraseAbort => { assert(rl_next(x.rl, RLL::Unlock, y.rl)); }
        BizL::Replay { key } => { assert(rl_next(x.rl, RLL::Replay { key }, y.rl)); }
        BizL::SetEnabled { on } => { assert(rl_next(x.rl, RLL::SetEnabled { on }, y.rl)); }
        BizL::Open { p, t } => { assert(rl_next(x.rl, RLL::Open { p, t }, y.rl)); }
        BizL::ToFinal { p } => { assert(rl_next(x.rl, RLL::ToFinal { p }, y.rl)); }
        BizL::Stop { p } => { assert(rl_next(x.rl, RLL::Stop { p }, y.rl)); }
        _ => { assert(mid_of(y).rl == x.rl); }
    }
}

/// **Statement entries match live edges** (ADR-0004, both directions) at every key outside the open erasure whose row
/// was last written through the ledger (F-1201, F-C1202 are the pin's violations; a bypass edge write is F-0303's class
/// and is excluded by `unrec`).
pub proof fn theorem_statements_match(x: BizS, k: Key)
    requires biz_inv(x), k.edge, !in_erasing(x.st.erasing)(k), !x.st.unrec.contains(k),
    ensures x.st.stmts.contains(k) <==> x.st.rows.contains_key(k),
{
    assert(key_ok(x, k));
    assert(!x.wr.open.contains_key(k));
    if x.st.erasing is Some {
        assert(store_inv(x.st));
        assert(!x.st.erasing->0.saved.contains_key(k));
        assert(!x.st.erasing->0.sst.contains(k));
    }
}

/// ... and the same in the committed view (what every rollback of the open transactions would leave).
pub proof fn theorem_statements_match_committed(x: BizS, k: Key)
    requires biz_inv(x), k.edge, !cunrec(x, k),
    ensures cstmt(x, k) <==> crow(x, k) is Some,
{
    assert(key_ok(x, k));
}

/// **Replay equals store once settled** (FR-007, `verify()` reports `equal`) at every key whose row was last written
/// through the ledger; with no bypass write ever, they are equal.
pub proof fn theorem_replay_settled(x: BizS)
    requires biz_inv(x), settled(x),
    ensures
        forall|k: Key| !x.st.unrec.contains(k) ==> #[trigger] oget(replay(x.rl.l.hist), k) == oget(x.st.rows, k),
        x.st.unrec == Set::<Key>::empty() ==> replay(x.rl.l.hist) =~= x.st.rows,
        x.rl.l.marker is None,
{
    assert forall|k: Key| !x.st.unrec.contains(k) implies #[trigger] oget(replay(x.rl.l.hist), k) == oget(x.st.rows, k) by {
        assert(key_ok(x, k));
        assert(!x.wr.open.contains_key(k));
        assert(!in_pend(x.pend)(k));
    }
    if x.st.unrec == Set::<Key>::empty() {
        let h = replay(x.rl.l.hist);
        assert forall|k: Key| #[trigger] h.contains_key(k) <==> x.st.rows.contains_key(k) by {
            assert(oget(h, k) == oget(x.st.rows, k));
        }
        assert forall|k: Key| #[trigger] h.contains_key(k) implies h[k] == x.st.rows[k] by {
            assert(oget(h, k) == oget(x.st.rows, k));
        }
    }
    if x.rl.l.marker is Some { assert(x.pend.contains(x.rl.l.marker->0.rm)); }
}

/// **The reviewed Start reads committed state.** Whenever the reviewed Start may run (no erasure open: it holds the
/// head lock; no bypass transaction open: G-B), the rows its liveness check reads are the committed rows at every
/// key. So the reviewed design satisfies the alternative "liveness on committed state" too.
pub proof fn theorem_start_reads_committed(x: BizS, p: nat, fresh: bool, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Start { p, fresh }, y),
    ensures forall|k: Key| #[trigger] crow(x, k) == oget(x.st.rows, k) && cunrec(x, k) == x.st.unrec.contains(k),
{
    assert(rl_next(x.rl, RLL::Start { p, fresh }, y.rl));
    assert(x.st.erasing is None);
    assert(no_open(x.wr));
    assert forall|k: Key| #[trigger] crow(x, k) == oget(x.st.rows, k) && cunrec(x, k) == x.st.unrec.contains(k) by {
        assert(!x.wr.open.contains_key(k));
    }
}

/// **A pending domain leaves only through a redaction that covers it.** An erasure's domain (or a run's record match)
/// is no longer pending only after a successful Final whose record match covers it. With F-1305's targets (an erasure
/// of a graph whose node records the graph target does not match) the erasure's domain stays pending, so the model
/// never calls that state settled.
pub proof fn theorem_pending_needs_cover(x: BizS, l: BizL, y: BizS, d: Dom)
    requires biz_inv(x), biz_next(x, l, y), x.pend.contains(d), !y.pend.contains(d),
    ensures l is Final && l->Final_ok && covers(tgt_of(x.rl.r, l->Final_p).rm, d),
{
    match l {
        BizL::Final { p, ok } => {
            if ok {
                assert(y.pend == x.pend.filter(|d2: Dom| !covers(tgt_of(x.rl.r, p).rm, d2)));
            } else {
                assert(y.pend == x.pend);
            }
        }
        BizL::Start { p, fresh } => { assert(y.pend.contains(d)); }
        BizL::EraseCommit => { assert(y.pend.contains(d)); }
        BizL::BCommit { k } => { assert(mid_of(y) == mid_of(x)); }
        _ => { assert(y.pend == x.pend); }
    }
}

/// Every marked target satisfies the predicates' side condition (the reviewed Start refused it otherwise).
pub proof fn theorem_marked_target_aligned(x: BizS)
    requires biz_inv(x), x.rl.l.marker is Some,
    ensures aligned(x.rl.l.marker->0), x.pend.contains(x.rl.l.marker->0.rm),
{
}

} // verus!
