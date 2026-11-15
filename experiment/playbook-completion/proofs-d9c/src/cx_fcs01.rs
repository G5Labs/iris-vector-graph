//! Proved counterexample for control `control_fcs01_noop_unrecorded` (F-CS01, reproduced live `sim-fcs01-minimal`),
//! compiled only with that feature.
//!
//! As built a commit counts operations, not records (Ledger.cls:489-492), a no-op operation writes no record
//! (LedgerApply.cls:229-233, 252-263), and the revision row and the key binding are written regardless
//! (Ledger.cls:520-525). The composed participant contracts (`system::sys_step`, as the control changes them) run,
//! from the initial state, the live minimal schedule: commit A's node with key 1 (revision 0, one record); commit a
//! changeset whose only operation addresses A's node and changes nothing, with key 2 (revision 1, **no** record: its
//! row has free text and key 2, and key 2 is bound); erase A; redact A (open, start, three scan steps, final): the
//! run completes. Revision 0's metadata is cleared and key 1 is in idemRedacted, but revision 1, attributable to A, keeps
//! its free text and key 2, and key 2 is still bound: a same-key retry after the complete redaction is **replayed**
//! (spec 256 FR-004 spec.md:121-123, SC-001 spec.md:142-143 and plan.md:25 fail; `theorem_redaction_clears_metadata`
//! and INV-retry are violated), and the business invariants fail from the zero-record commit on (`attr_ok`).
use vstd::prelude::*;
use actors::protocol::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::protocol_rl::*;
use crate::biz::*;
use crate::system::*;
use crate::theorems::*;
use crate::witness::*;

verus! {

pub open spec fn nil() -> Seq<Content> { Seq::empty() }
pub open spec fn na() -> Seq<Key> { seq![ka()] }

pub open spec fn z1() -> BizS {
    BizS { rl: RLS { l: ledger_commit(w0().rl.l, seq![ca()], keys(seq![ca()]), Some(1)), r: w0().rl.r }, st: store_apply(w0().st, seq![ca()]), ..w0() }
}
/// The no-op changeset: one operation on A's node, no record (as built), key 2.
pub open spec fn z2() -> BizS { BizS { rl: RLS { l: ledger_commit(z1().rl.l, nil(), na(), Some(2)), r: z1().rl.r }, ..z1() } }
pub open spec fn z3() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: true, ..z2().rl.l }, r: z2().rl.r }, st: store_erase_rows(z2().st, dom_a()), ..z2() }
}
pub open spec fn z4() -> BizS { BizS { st: store_erase_index(z3().st), ..z3() } }
pub open spec fn z5() -> BizS {
    BizS { rl: RLS { l: LedgerS { locked: false, ..z4().rl.l }, r: z4().rl.r }, st: store_erase_commit(z4().st),
           pend: z4().pend.insert(dom_a()), ..z4() }
}
pub open spec fn z6() -> BizS { BizS { rl: RLS { l: z5().rl.l, r: red_step(z5().rl.r, RedL::Open { p: 0, t: t_a() }) }, ..z5() } }
pub open spec fn z7() -> BizS {
    BizS { rl: RLS { l: ledger_mark(z6().rl.l, t_a()), r: red_step(z6().rl.r, RedL::Attach { p: 0, i: 0, j: 0, end: 2 }) },
           pend: z6().pend.insert(dom_a()), ..z6() }
}
pub open spec fn z8() -> BizS {
    BizS { rl: RLS { l: ledger_batch(z7().rl.l, 0, 0, t_a(), true, 0, 1), r: red_step(z7().rl.r, RedL::Advance { p: 0, row_end: false }) }, ..z7() }
}
pub open spec fn z9() -> BizS {
    BizS { rl: RLS { l: ledger_batch(z8().rl.l, 0, 1, t_a(), false, 1, 0), r: red_step(z8().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..z8() }
}
/// Revision 1 has no record: the scan passes its end at once.
pub open spec fn z10() -> BizS {
    BizS { rl: RLS { l: ledger_batch(z9().rl.l, 1, 0, t_a(), false, 2, 0), r: red_step(z9().rl.r, RedL::Advance { p: 0, row_end: true }) }, ..z9() }
}
pub open spec fn z11() -> BizS { BizS { rl: RLS { l: z10().rl.l, r: red_step(z10().rl.r, RedL::ToFinal { p: 0 }) }, ..z10() } }
pub open spec fn z12() -> BizS {
    BizS {
        rl: RLS { l: ledger_audit(z11().rl.l, t_a()), r: red_step(z11().rl.r, RedL::Finish { p: 0 }) },
        st: store_drop(z11().st, t_a().sc),
        pend: z11().pend.filter(|d: Dom| !covers(t_a().rm, d)),
        wr: z11().wr,
    }
}

pub proof fn counterexample_fcs01()
    ensures
        Biz::init(w0()),
        sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: Some(1) }, z1()),
        sys_step(z1(), BizL::Commit { cs: nil(), named: na(), key: Some(2) }, z2()),
        sys_step(z2(), BizL::EraseRows { e: dom_a() }, z3()),
        sys_step(z3(), BizL::EraseIndex, z4()),
        sys_step(z4(), BizL::EraseCommit, z5()),
        sys_step(z5(), BizL::Open { p: 0, t: t_a() }, z6()),
        sys_step(z6(), BizL::Start { p: 0, fresh: true }, z7()),
        sys_step(z7(), BizL::Scan { p: 0 }, z8()),
        sys_step(z8(), BizL::Scan { p: 0 }, z9()),
        sys_step(z9(), BizL::Scan { p: 0 }, z10()),
        sys_step(z10(), BizL::ToFinal { p: 0 }, z11()),
        sys_step(z11(), BizL::Final { p: 0, ok: true }, z12()),
        // the redaction completed: no marker, nothing pending, A's record tombstoned, revision 0 redacted, key 1 moved
        z12().rl.l.marker is None && z12().pend =~= Set::<Dom>::empty() && z12().rl.l.hist[0][0] == Rec::Tomb(ca()),
        meta_redacted(z12().rl.l, 0) && z12().rl.l.idemr.contains(1),
        // ... but revision 1, attributable to A and with no record, keeps its free text and key 2, still bound ...
        z12().rl.l.hist[1].len() == 0 && attributed(z12().rl.l, 1, dom_a()),
        z12().rl.l.meta[1].txt && z12().rl.l.meta[1].key == Some(2int) && z12().rl.l.idem.contains_key(2),
        !meta_redacted(z12().rl.l, 1),
        // ... so a same-key retry after the complete redaction is replayed instead of refused.
        sys_step(z12(), BizL::Replay { key: 2, props: nil() }, z12()),
        !biz_inv(z2()), !biz_inv(z12()),
{
    lemma_one(w0().st.rows, w0().st.stmts, w0().st.unrec, ca());
    lemma_one(Map::<Key, int>::empty(), Set::<Key>::empty(), Set::<Key>::empty(), ca());
    assert(z1().st.rows =~= Map::<Key, int>::empty().insert(ka(), 5));
    assert(sys_step(w0(), BizL::Commit { cs: seq![ca()], named: keys(seq![ca()]), key: Some(1) }, z1()));

    // the zero-record commit: as built it passes the operation count and BlocksCommit, and writes row and binding
    assert(lives(nil()) =~= Seq::<Rec>::empty());
    assert(store_apply(z1().st, nil()) == z1().st);
    assert(z1().rl.l.idem =~= Map::<IKey, nat>::empty().insert(1, 0));
    assert(!z1().rl.l.idem.contains_key(2));
    assert(!touches(nil(), t_a().rm));
    assert(sys_step(z1(), BizL::Commit { cs: nil(), named: na(), key: Some(2) }, z2()));
    assert(z2().rl.l.hist.len() == 2 && z2().rl.l.hist[1].len() == 0);
    assert(z2().rl.l.meta[1] == commit_meta(na(), Some(2)));
    assert(!rev_names(z2().rl.l.hist[1], ka()));
    assert(z2().rl.l.meta[1].named[0] == ka());
    assert(!attr_ok(z2().rl.l));

    assert(sys_step(z2(), BizL::EraseRows { e: dom_a() }, z3()));
    assert(z3().st.rows =~= Map::<Key, int>::empty()) by {
        assert forall|k: Key| !#[trigger] z3().st.rows.contains_key(k) by {
            if z3().st.rows.contains_key(k) { assert(z2().st.rows.contains_key(k)); assert(k == ka()); }
        }
    }
    assert(sys_step(z3(), BizL::EraseIndex, z4()));
    assert(sys_step(z4(), BizL::EraseCommit, z5()));
    assert(sys_step(z5(), BizL::Open { p: 0, t: t_a() }, z6()));
    assert(z6().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(z6().st.rows, t_a().lv));
    assert(tgt_of(z6().rl.r, 0) == t_a());
    assert(aligned(t_a()));
    assert(sys_step(z6(), BizL::Start { p: 0, fresh: true }, z7()));

    let c7 = pcur(z7().rl.r, 0);
    assert(c7 == Cur { t: dom_a(), i: 0, j: 0, end: 2 });
    assert(z7().rl.l.hist[0][0] == Rec::Live(ca()));
    assert(hit(z7().rl.l, c7));
    assert(sys_step(z7(), BizL::Scan { p: 0 }, z8()));
    let c8 = pcur(z8().rl.r, 0);
    assert(c8 == Cur { t: dom_a(), i: 0, j: 1, end: 2 });
    assert(z8().rl.l.hist[0].len() == 1);
    assert(row_end(z8().rl.l, c8));
    assert(sys_step(z8(), BizL::Scan { p: 0 }, z9()));
    let c9 = pcur(z9().rl.r, 0);
    assert(c9 == Cur { t: dom_a(), i: 1, j: 0, end: 2 });
    assert(z9().rl.l.hist[1] == z2().rl.l.hist[1]);
    assert(row_end(z9().rl.l, c9));
    assert(sys_step(z9(), BizL::Scan { p: 0 }, z10()));
    assert(sys_step(z10(), BizL::ToFinal { p: 0 }, z11()));
    assert(tgt_of(z11().rl.r, 0) == t_a());
    assert(z11().st.rows =~= Map::<Key, int>::empty());
    assert(!live_in(z11().st.rows, t_a().lv));
    assert(sys_step(z11(), BizL::Final { p: 0, ok: true }, z12()));

    // what the complete redaction left
    assert(covers(t_a().rm, dom_a()));
    assert(z12().pend =~= Set::<Dom>::empty()) by {
        assert forall|d: Dom| !#[trigger] z12().pend.contains(d) by {
            if z11().pend.contains(d) { assert(d == dom_a()); }
        }
    }
    assert(z8().rl.l.meta[0] == cleared(z7().rl.l.meta[0]));
    assert(z7().rl.l.meta[0] == commit_meta(keys(seq![ca()]), Some(1)));
    assert(z12().rl.l.meta[0] == z8().rl.l.meta[0]);
    assert(z8().rl.l.idem =~= Map::<IKey, nat>::empty().insert(2, 1));
    assert(z12().rl.l.idem == z8().rl.l.idem);
    assert(z12().rl.l.idemr =~= Set::<IKey>::empty().insert(1));
    assert(meta_redacted(z12().rl.l, 0));
    assert(z12().rl.l.meta[1] == commit_meta(na(), Some(2)));
    assert(z12().rl.l.hist[1] == z2().rl.l.hist[1]);
    assert(member(dom_a(), z12().rl.l.meta[1].named[0]));
    assert(attributed(z12().rl.l, 1, dom_a()));
    assert(z12().rl.l.idem.contains_key(2));
    assert(sys_step(z12(), BizL::Replay { key: 2, props: nil() }, z12()));
    assert(z12().rl.l.hist[1].len() == 0 && z12().rl.l.meta[1].named[0] == ka());
    assert(!rev_names(z12().rl.l.hist[1], ka()));
    assert(!attr_ok(z12().rl.l));
}

} // verus!
