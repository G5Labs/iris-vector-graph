//! Business theorems of the reviewed model (D-9, D-9b), each proved from `biz_inv` and one `biz_next` step, or over a
//! `biz_run` (no other reachability assumption). All are statements about the **model**; none is a property of the
//! product at the pin. D-9b adds: revision metadata redacted for every revision attributable to a completed target
//! (F-CS01), Decision 2 "any", INV-retry (step and executions), the statement history after Final and after an
//! erasure, and "a replayed retry changes nothing" (F-1306).
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

/// **No tombstone of live content** (RED-B1.1, FR-005, ADR-0013:17). A record becomes a tombstone only while its key
/// holds no content: in D-9 no *recorded* content (not in the rows other processes see, not in the rows a rollback of
/// every open transaction would leave); in D-9c, with G-BM, no content of **any** provenance, recorded or written
/// outside the ledger — before and after the step. F-1302, F-1304, F-C1201, F-C1301 and F-C1350 are the pin's
/// violations.
pub proof fn theorem_no_tombstone_of_live(x: BizS, l: BizL, y: BizS, i: int, j: int)
    requires
        biz_inv(x), biz_next(x, l, y),
        0 <= i < x.rl.l.hist.len(), 0 <= j < x.rl.l.hist[i].len(),
        x.rl.l.hist[i][j] is Live, y.rl.l.hist[i][j] is Tomb,
    ensures
        !rec_content(x, x.rl.l.hist[i][j]->Live_0.k),
        !rec_content(y, x.rl.l.hist[i][j]->Live_0.k),
        // D-9c (G-BM, review R4-01): no content of any provenance either — not recorded, not written outside the
        // ledger, visible or left by a rollback (F-C1350 is the pin's violation).
        !any_content(x, x.rl.l.hist[i][j]->Live_0.k),
        !any_content(y, x.rl.l.hist[i][j]->Live_0.k),
{
    let h = x.rl.l.hist;
    let k = h[i][j]->Live_0.k;
    match l {
        BizL::Commit { cs, named, key } => { assert(y.rl.l.hist[i] == h[i]); }
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
        BizL::Replay { key, props } => { assert(y.rl.l.hist == h); }
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
        BizL::Commit { cs, named, key } => { assert(rl_next(x.rl, RLL::Commit { cs, named, key }, y.rl)); }
        BizL::EraseRows { e } => { assert(rl_next(x.rl, RLL::Lock, y.rl)); }
        BizL::EraseCommit => { assert(rl_next(x.rl, RLL::Unlock, y.rl)); }
        BizL::EraseAbort => { assert(rl_next(x.rl, RLL::Unlock, y.rl)); }
        BizL::Replay { key, props } => { assert(rl_next(x.rl, RLL::Replay { key }, y.rl)); }
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

// ------------------------------------------------------------------------------------------------ D-9b: metadata, retry keys

/// A record (live or tombstoned) whose content key d selects.
pub open spec fn rec_in(r: Rec, d: Dom) -> bool {
    match r {
        Rec::Live(c) => member(d, c.k),
        Rec::Tomb(c) => member(d, c.k),
        _ => false,
    }
}

/// Revision i is **attributable** to the domain d: one of its records describes a key of d, or (ghost) one of the
/// keys its changeset's operations addressed is in d — the tenant its free text and key may name (premise P-D9b-1;
/// spec 256 US1 spec.md:42-44, SC-001 spec.md:142-143).
pub open spec fn attributed(l: LedgerS, i: int, d: Dom) -> bool {
    (exists|j: int| 0 <= j < l.hist[i].len() && #[trigger] rec_in(l.hist[i][j], d))
    || (exists|j: int| 0 <= j < l.meta[i].named.len() && member(d, #[trigger] l.meta[i].named[j]))
}

/// Revision i's metadata is redacted: no free text (message, source, correlation id), no idempotency_key, and the key
/// it was committed with, if any, is in idemRedacted and no longer bound (FR-004 spec.md:121-123, plan.md:25).
pub open spec fn meta_redacted(l: LedgerS, i: int) -> bool {
    &&& !l.meta[i].txt && l.meta[i].key is None
    &&& l.meta[i].okey is Some ==> l.idemr.contains(l.meta[i].okey->0) && !l.idem.contains_key(l.meta[i].okey->0)
}

/// **Decision 2 ("any", HD-1302).** In every invariant state, a revision with a tombstone has its metadata redacted
/// and its key moved to idemRedacted; the other records of the revision are not touched by the tombstone (a Scan
/// changes only the record under the cursor, `theorem_no_tombstone_of_live`'s case analysis).
pub proof fn theorem_decision2_any(x: BizS, i: int, j: int)
    requires biz_inv(x), 0 <= i < x.rl.l.hist.len(), 0 <= j < x.rl.l.hist[i].len(), x.rl.l.hist[i][j] is Tomb,
    ensures meta_redacted(x.rl.l, i),
{
    let l = x.rl.l;
    assert(meta_ok(l));
    assert(!l.meta[i].txt);
    if l.meta[i].okey is Some { assert(l.idemr.contains(l.meta[i].okey->0)); }
}

/// Every record a target's record match selects is a tombstone once its run reaches Final.
proof fn lemma_final_no_live(x: BizS, p: nat, y: BizS)
    requires biz_inv(x), biz_next(x, BizL::Final { p, ok: true }, y),
    ensures
        no_member(x.rl.l.hist, tgt_of(x.rl.r, p).rm),
        x.rl.l.marker == Some(tgt_of(x.rl.r, p)),
        y.rl.l == ledger_audit(x.rl.l, tgt_of(x.rl.r, p)),
        y.st == store_drop(x.st, tgt_of(x.rl.r, p).sc),
{
    assert(rl_next(x.rl, RLL::Final { p, ok: true }, y.rl));
    assert(mark_ok(x));
    lemma_cursor_done(x.rl.l.hist, dcur(x.rl.l));
}

/// **F-CS01's invariant (SC-001 / FR-004 for revision metadata, plan.md:25 for the key).** A successful Final of t
/// leaves every revision attributable to t's record match with its metadata redacted and its key moved to
/// idemRedacted — including revisions whose operations recorded no change (reviewed design R-1: their no-op records
/// are tombstoned like any other). At the pin a zero-record revision keeps both (`control_fcs01_noop_unrecorded`).
pub proof fn theorem_redaction_clears_metadata(x: BizS, p: nat, y: BizS, i: int)
    requires biz_inv(x), biz_next(x, BizL::Final { p, ok: true }, y), 0 <= i < x.rl.l.hist.len(),
        attributed(x.rl.l, i, tgt_of(x.rl.r, p).rm),
    ensures meta_redacted(y.rl.l, i), y.rl.l.meta[i] == x.rl.l.meta[i],
{
    let l = x.rl.l;
    let t = tgt_of(x.rl.r, p);
    lemma_final_no_live(x, p, y);
    assert(attr_ok(l) && meta_ok(l));
    let rs = l.hist[i];
    let a: int = if exists|j: int| 0 <= j < rs.len() && #[trigger] rec_in(rs[j], t.rm) {
        choose|j: int| 0 <= j < rs.len() && #[trigger] rec_in(rs[j], t.rm)
    } else {
        let j = choose|j: int| 0 <= j < l.meta[i].named.len() && member(t.rm, #[trigger] l.meta[i].named[j]);
        let k = l.meta[i].named[j];
        assert(rev_names(rs, k));
        let a = choose|a: int| 0 <= a < rs.len() && #[trigger] rec_names(rs[a], k);
        assert(rec_in(rs[a], t.rm));
        a
    };
    assert(0 <= a < rs.len() && rec_in(rs[a], t.rm));
    assert(!live_member(l.hist[i][a], t.rm));
    assert(l.hist[i][a] is Tomb);
    theorem_decision2_any(x, i, a);
    assert(y.rl.l.meta.len() >= l.meta.len());
    assert(y.rl.l.meta[i] == l.meta[i]);
}

/// **INV-retry (step).** A key in idemRedacted is never replayed (Ledger.cls:457-465 needs a binding) and never bound
/// again (Ledger.cls:468-473 refuses it), and it stays in idemRedacted.
pub proof fn theorem_retry_refused(x: BizS, k: IKey, l: BizL, y: BizS)
    requires biz_inv(x), x.rl.l.idemr.contains(k), biz_next(x, l, y),
    ensures
        match l {
            BizL::Replay { key, props } => key != k,
            BizL::Commit { cs, named, key } => key != Some(k),
            _ => true,
        },
        y.rl.l.idemr.contains(k),
{
    let lg = x.rl.l;
    assert(meta_ok(lg));
    assert(!lg.idem.contains_key(k));
    match l {
        BizL::Commit { cs, named, key } => { assert(rl_next(x.rl, RLL::Commit { cs, named, key }, y.rl)); }
        BizL::Replay { key, props } => { assert(rl_next(x.rl, RLL::Replay { key }, y.rl)); }
        BizL::Scan { p } => { assert(rl_next(x.rl, RLL::Scan { p }, y.rl)); }
        BizL::Final { p, ok } => { assert(rl_next(x.rl, RLL::Final { p, ok }, y.rl)); }
        BizL::Start { p, fresh } => { assert(rl_next(x.rl, RLL::Start { p, fresh }, y.rl)); }
        BizL::EraseRows { e } => { assert(rl_next(x.rl, RLL::Lock, y.rl)); }
        BizL::EraseCommit => { assert(rl_next(x.rl, RLL::Unlock, y.rl)); }
        BizL::EraseAbort => { assert(rl_next(x.rl, RLL::Unlock, y.rl)); }
        BizL::SetEnabled { on } => { assert(rl_next(x.rl, RLL::SetEnabled { on }, y.rl)); }
        BizL::Open { p, t } => { assert(rl_next(x.rl, RLL::Open { p, t }, y.rl)); }
        BizL::ToFinal { p } => { assert(rl_next(x.rl, RLL::ToFinal { p }, y.rl)); }
        BizL::Stop { p } => { assert(rl_next(x.rl, RLL::Stop { p }, y.rl)); }
        _ => { assert(mid_of(y).rl == x.rl); }
    }
}

/// An execution of the outer business contract from its initial state.
pub open spec fn biz_run(xs: Seq<BizS>, ls: Seq<BizL>) -> bool {
    &&& xs.len() == ls.len() + 1
    &&& Biz::init(xs[0])
    &&& forall|i: int| 0 <= i < ls.len() ==> #[trigger] biz_next(xs[i], ls[i], xs[i + 1])
}

pub proof fn lemma_biz_run_safe(xs: Seq<BizS>, ls: Seq<BizL>, m: int)
    requires biz_run(xs, ls), 0 <= m < xs.len(),
    ensures biz_inv(xs[m]),
    decreases m,
{
    if m == 0 { <Biz as SafeContract>::init_safe(xs[0]); } else {
        let j = m - 1;
        lemma_biz_run_safe(xs, ls, j);
        assert(biz_next(xs[j], ls[j], xs[j + 1]));
        lemma_biz_safe(xs[j], ls[j], xs[j + 1]);
    }
}

/// **INV-retry (executions).** Once a key is in idemRedacted, no later step of the execution replays it or binds it.
pub proof fn theorem_retry_refused_forever(xs: Seq<BizS>, ls: Seq<BizL>, n: int, k: IKey, m: int)
    requires biz_run(xs, ls), 0 <= n <= m < ls.len(), xs[n].rl.l.idemr.contains(k),
    ensures
        xs[m].rl.l.idemr.contains(k),
        match ls[m] {
            BizL::Replay { key, props } => key != k,
            BizL::Commit { cs, named, key } => key != Some(k),
            _ => true,
        },
    decreases m - n,
{
    if m > n {
        let j = m - 1;
        theorem_retry_refused_forever(xs, ls, n, k, j);
        lemma_biz_run_safe(xs, ls, j);
        assert(biz_next(xs[j], ls[j], xs[j + 1]));
        theorem_retry_refused(xs[j], k, ls[j], xs[j + 1]);
    }
    lemma_biz_run_safe(xs, ls, m);
    assert(biz_next(xs[m], ls[m], xs[m + 1]));
    theorem_retry_refused(xs[m], k, ls[m], xs[m + 1]);
}

/// **INV-retry after a complete redaction.** If step n is a successful Final of t, then for every revision
/// attributable to t that was committed with a key, no later step replays that key or binds it again: a same-key
/// retry is refused (`idempotency_redacted`), never replayed and never re-created (ADR-0013:15, spec.md:104-105).
pub proof fn theorem_redaction_retry_refused(xs: Seq<BizS>, ls: Seq<BizL>, n: int, p: nat, i: int, m: int)
    requires
        biz_run(xs, ls), 0 <= n < m < ls.len(), ls[n] == (BizL::Final { p, ok: true }),
        0 <= i < xs[n].rl.l.hist.len(), attributed(xs[n].rl.l, i, tgt_of(xs[n].rl.r, p).rm),
        xs[n].rl.l.meta[i].okey is Some,
    ensures
        match ls[m] {
            BizL::Replay { key, props } => key != xs[n].rl.l.meta[i].okey->0,
            BizL::Commit { cs, named, key } => key != xs[n].rl.l.meta[i].okey,
            _ => true,
        },
{
    lemma_biz_run_safe(xs, ls, n);
    assert(biz_next(xs[n], ls[n], xs[n + 1]));
    theorem_redaction_clears_metadata(xs[n], p, xs[n + 1], i);
    let k = xs[n].rl.l.meta[i].okey->0;
    assert(xs[n + 1].rl.l.idemr.contains(k));
    theorem_retry_refused_forever(xs, ls, n + 1, k, m);
}

// ------------------------------------------------------------------------------------------------ D-9b: statement history

/// **Statement history (SC-001 for `^IVG.Ledger("stmt")`).** A successful Final of t leaves no statement entry, live
/// or closed, of an edge t's record match selects (DropStatements removes closed entries too, LedgerRedact.cls:444-471;
/// it needs `rm ⊆ sc` on edges, part of the side condition; `control_sc_narrow`).
pub proof fn theorem_final_clears_statement_history(x: BizS, p: nat, y: BizS, k: Key)
    requires biz_inv(x), biz_next(x, BizL::Final { p, ok: true }, y), member(tgt_of(x.rl.r, p).rm, k), k.edge,
    ensures !y.st.shist.contains(k), !y.st.stmts.contains(k),
{
    lemma_final_no_live(x, p, y);
    assert(mark_ok(x));
    assert(aligned(tgt_of(x.rl.r, p)));
    assert(member(tgt_of(x.rl.r, p).sc, k));
}

/// An erasure's commit leaves no statement entry, live or closed, of its target (EraseLedgerFor, Eraser.cls:1117-1144).
pub proof fn theorem_erasure_clears_statement_history(x: BizS, y: BizS, k: Key)
    requires biz_inv(x), biz_next(x, BizL::EraseCommit, y), member(x.st.erasing->0.e, k),
    ensures !y.st.shist.contains(k), !y.st.stmts.contains(k),
{
    assert(y.st == store_erase_commit(x.st));
    let r = x.st.erasing->0;
    // cleanup ran (EraseCommit needs it); nothing wrote statement globals since: the head lock is held.
    assert(key_ok(x, k));
    assert(ers_key_ok(x, r, k));
    assert(r.idx);
}

// ------------------------------------------------------------------------------------------------ D-9b: replay (F-1306)

/// **A replayed retry changes nothing** (HD-1305; spec 213 ledger-api.md:26 "original outcome"; F-1306 is the pin's
/// violation: its client writes the post-commit properties by direct SQL, `control_f1306_replay_direct_sql`).
pub proof fn theorem_replay_changes_nothing(x: BizS, key: IKey, props: Seq<Content>, y: BizS)
    requires biz_next(x, BizL::Replay { key, props }, y),
    ensures y == x,
{
    assert(rl_next(x.rl, RLL::Replay { key }, y.rl));
    assert(mid_of(y) == mid_of(x));
}

} // verus!
