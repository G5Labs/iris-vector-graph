//! Proved counterexample for control `control_f1201_erase_no_head_lock` (F-1201), compiled only with it. Lane
//! proofs-pa3 (proof debt D-13): P-A3 removed, the pin's EraseGraph (no ledger head lock, Eraser.cls:47-261) put back.
//!
//! The live reproduction `live-f1201-reproduced` (8/8): graph 7 is empty; EraseGraph(7) starts (the guard lets it,
//! strict mode is off) and its DELETEs remove nothing; a ledger commit of a new edge e of graph 7 takes the free head
//! lock, writes the row, the revision and the statement entry ("stmt", 1) / ("tuple", e), and commits; EraseLedgerFor
//! then kills every statement entry of graph 7, the new one included, and the erasure commits. Final state: e's row is
//! live, its revision is recorded (head 2, ("rec", 2, 1) = create e), no erasure or transaction is open, and e has no
//! statement entry: ERS-I3 / `theorem_statements_match_records` fails, so the L2 invariant does not hold.
use vstd::prelude::*;
use crate::ledger_l1::*;
use crate::ledger_l2::*;
use crate::cx_ledger_common::*;

verus! {

pub open spec fn e() -> K { K { id: 1, edge: true, gr: 7 } }
pub open spec fn a() -> CArgs { CArgs { recs: seq![Op { k: e(), v: Some(1) }], key: None, fp: 0, exp: None, id: 2 } }
pub open spec fn c1() -> LS2 { c_genesis(false) }
pub open spec fn c2() -> LS2 {
    LS2 { er: Some(Er { gr: 7, ph: ErPh::Started, del: Set::empty(), pre: Map::empty(), pre_sx: c1().g.sx }), ..c1() }
}
pub open spec fn c3() -> LS2 {
    LS2 { rows: rows_minus(c2().rows, er_del(c2().rows, 7)),
          er: Some(Er { ph: ErPh::Deleted, del: er_del(c2().rows, 7), pre: Map::new(er_del(c2().rows, 7), |k: K| c2().rows[k]),
                        ..c2().er->0 }),
          ..c2() }
}
pub open spec fn c4() -> LS2 { applied(c3(), a()) }
pub open spec fn c5() -> LS2 {
    LS2 { g: Glob { sx: clean_sx(c4().g.sx, 7), ..c4().g }, er: Some(Er { ph: ErPh::Cleaned, pre_sx: c4().g.sx, ..c4().er->0 }), ..c4() }
}
pub open spec fn c6() -> LS2 { LS2 { er: None, drift: c5().drift.union(Set::empty()), ..c5() } }

pub proof fn counterexample_f1201()
    ensures
        init2(c_init()),
        step2(c_init(), L2Label::Enable { strict: false, id: 1, recs: seq![], busy: false }, c1()),
        step2(c1(), L2Label::EStart { gr: 7 }, c2()),
        step2(c2(), L2Label::ERows, c3()),
        c3().er->0.del == Set::<K>::empty(),
        // as built: the commit does not wait for the open erasure (EraseGraph holds no head lock)
        step2(c3(), L2Label::Commit { a: a(), out: COut::Applied(2) }, c4()),
        c4().g.sx.tuple.contains_key(e()),
        step2(c4(), L2Label::EClean, c5()),
        step2(c5(), L2Label::ECommit { del: Set::<K>::empty() }, c6()),
        c6().er is None && c6().txn is None,
        c6().rows.contains_key(e()) && c6().rows[e()] == 1 && e().edge && !c6().drift.contains(e()),
        c6().g.head == 2 && c6().g.rec[(2nat, 1nat)] == (Op { k: e(), v: Some(1) }),
        !c6().g.sx.tuple.contains_key(e()),
        !inv2(c6()),
{
    lemma_genesis_step(false);
    let g1 = c1().g;
    assert(g1.head == 1);
    assert(!refuses(c1(), Wr::Api));
    assert(step2(c1(), L2Label::EStart { gr: 7 }, c2()));
    assert(er_del(c2().rows, 7) =~= Set::<K>::empty());
    assert(step2(c2(), L2Label::ERows, c3()));
    assert(c3().rows =~= Map::<K, V>::empty());
    assert(c3().g == g1);
    assert(!g1.rev_by_id.contains_key(2));
    assert(g1.idem == Map::<IKey, (nat, Fp)>::empty());
    assert(out2(c3().meta, c3().g, a()) == COut::Applied(2));
    assert(c3().er->0.del == Set::<K>::empty());
    assert forall|k: K| #[trigger] touches(a().recs, k) implies er_row_free(c3(), k) by {}
    assert(step2(c3(), L2Label::Commit { a: a(), out: COut::Applied(2) }, c4()));
    assert(a().recs.drop_last() =~= Seq::<Op>::empty());
    assert(!g1.sx.tuple.contains_key(e()));
    assert(c4().g.sx.tuple.contains_key(e()));
    assert(c4().rows.contains_key(e()) && c4().rows[e()] == 1);
    assert(step2(c4(), L2Label::EClean, c5()));
    assert(step2(c5(), L2Label::ECommit { del: Set::<K>::empty() }, c6()));
    assert(c6().drift =~= Set::<K>::empty());
    assert(!c6().g.sx.tuple.contains_key(e()));
    assert(c6().g.rec[(2nat, 1nat)] == (Op { k: e(), v: Some(1) })) by {
        lemma_rec_put_all(g1.rec, 2, a().recs);
    }
    // the L2 invariant would give the live statement entry: rows agree with the replay outside drift (L1's invariant on
    // the abstraction) and, outside drift, an edge has a tuple entry iff it is live in the replay
    if inv2(c6()) {
        assert(eg(c6()) == c6().g);
        assert(crows(c6()) == c6().rows);
        assert(cg(c6()) == c6().g);
        assert(val(c6().rows, e()) == val(replay(lay_hist(c6().g)), e()));
        assert(live_ok(c6().g.sx, replay(lay_hist(c6().g)), c6().drift));
        assert(c6().g.sx.tuple.contains_key(e()) <==> val(replay(lay_hist(c6().g)), e()) is Some);
        assert(false);
    }
}

} // verus!
