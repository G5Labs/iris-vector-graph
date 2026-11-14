//! Non-vacuity of the module 11 reviewed model (compiled without controls): a concrete run of the L2 step relation
//! from its initial state through genesis, an applied commit with a retry key and the head as expected head, a replay
//! of that key (answering the bound revision, changing nothing), a commit refused for a stale expected head, strict
//! mode turned on, and a governed write refused; each step is an L1 step or a stutter (`theorem_raw_executions_refine`).
//!
//! `witness_erase` (lane proofs-pa3): from the same commit, EraseGraph(0) under the head lock deletes the committed
//! edge's row, a ledger-bypassing engine write inserts a NEW row of graph 0 while the erasure is open (P-A3 is not
//! assumed: a bypass writer takes no head lock and a new row no row lock), EraseLedgerFor kills the edge's statement
//! entry and the erasure commits; the new row survives as an unrecorded write.
use vstd::prelude::*;
use crate::ledger_l1::*;
use crate::ledger_l2::*;

verus! {

pub open spec fn w_k1() -> K { K { id: 1, edge: true, gr: 0 } }
pub open spec fn w_init() -> LS2 {
    LS2 {
        meta: Meta { state: LState::Never, strict: false }, g: glob0(), stats: Stats { ok: 0, rej: 0 },
        rows: Map::empty(), txn: None, gcache: None, probe_fails: false, copies: Map::empty(), drift: Set::empty(), er: None,
    }
}
pub open spec fn w1() -> LS2 {
    LS2 { meta: Meta { state: LState::Enabled, strict: false }, g: commit_glob(glob0(), genesis_args(seq![], 1)),
          stats: Stats { ok: 1, rej: 0 }, drift: Set::empty(), ..w_init() }
}
pub open spec fn a_new() -> CArgs { CArgs { recs: seq![Op { k: w_k1(), v: Some(5) }], key: Some(7), fp: 3, exp: Some(1), id: 2 } }
pub open spec fn a_retry() -> CArgs { CArgs { recs: seq![Op { k: w_k1(), v: Some(5) }], key: Some(7), fp: 3, exp: Some(1), id: 3 } }
pub open spec fn a_stale() -> CArgs { CArgs { recs: seq![Op { k: w_k1(), v: None }], key: None, fp: 4, exp: Some(1), id: 4 } }
pub open spec fn w2() -> LS2 { applied(w1(), a_new()) }
pub open spec fn w3() -> LS2 { LS2 { meta: Meta { strict: true, ..w2().meta }, ..w2() } }

pub open spec fn k_new() -> K { K { id: 5, edge: false, gr: 0 } }
pub open spec fn rows2() -> Map<K, V> { Map::empty().insert(w_k1(), 5) }
pub open spec fn x1() -> LS2 {
    LS2 { er: Some(Er { gr: 0, ph: ErPh::Started, del: Set::empty(), pre: Map::empty(), pre_sx: w2().g.sx }), ..w2() }
}
pub open spec fn x2() -> LS2 {
    LS2 { rows: rows_minus(x1().rows, er_del(x1().rows, 0)),
          er: Some(Er { ph: ErPh::Deleted, del: er_del(x1().rows, 0), pre: Map::new(er_del(x1().rows, 0), |k: K| x1().rows[k]),
                        ..x1().er->0 }),
          ..x1() }
}
pub open spec fn x3() -> LS2 { engine_write(x2(), Wr::Api, k_new(), Some(4)) }
pub open spec fn x4() -> LS2 {
    LS2 { g: Glob { sx: clean_sx(x3().g.sx, 0), ..x3().g }, er: Some(Er { ph: ErPh::Cleaned, pre_sx: x3().g.sx, ..x3().er->0 }), ..x3() }
}
pub open spec fn x5() -> LS2 { LS2 { er: None, drift: x4().drift.union(Set::empty().insert(w_k1())), ..x4() } }

pub proof fn witness_erase()
    ensures
        step2(w2(), L2Label::EStart { gr: 0 }, x1()),
        step2(x1(), L2Label::ERows, x2()),
        x2().er->0.del == Set::<K>::empty().insert(w_k1()),
        // a writer of graph 0 lands between the erasure's DELETE and its commit
        k_new().gr == 0 && x2().er->0.gr == 0,
        step2(x2(), L2Label::EngineWrite { w: Wr::Api, k: k_new(), v: Some(4), landed: true }, x3()),
        step2(x3(), L2Label::EClean, x4()),
        step2(x4(), L2Label::ECommit { del: Set::<K>::empty().insert(w_k1()) }, x5()),
        x5().rows == Map::<K, V>::empty().insert(k_new(), 4),
        !x5().g.sx.tuple.contains_key(w_k1()) && x5().drift.contains(w_k1()) && x5().drift.contains(k_new()),
{
    witness_ledger();
    assert(a_new().recs.drop_last() =~= Seq::<Op>::empty());
    assert(w2().rows =~= rows2());
    assert(!refuses(w2(), Wr::Api));
    assert(step2(w2(), L2Label::EStart { gr: 0 }, x1()));
    let d = Set::<K>::empty().insert(w_k1());
    assert(er_del(x1().rows, 0) =~= d);
    assert(step2(x1(), L2Label::ERows, x2()));
    assert(x2().rows =~= Map::<K, V>::empty());
    assert(k_new() != w_k1());
    assert(write_ok(x2(), Wr::Api, k_new(), Some(4)));
    assert(!refuses(x2(), Wr::Api));
    assert(step2(x2(), L2Label::EngineWrite { w: Wr::Api, k: k_new(), v: Some(4), landed: true }, x3()));
    assert(step2(x3(), L2Label::EClean, x4()));
    assert(step2(x4(), L2Label::ECommit { del: d }, x5()));
    assert(x5().rows =~= Map::<K, V>::empty().insert(k_new(), 4));
    assert(!x5().g.sx.tuple.contains_key(w_k1()));
}

pub proof fn witness_ledger()
    ensures
        init2(w_init()),
        step2(w_init(), L2Label::Enable { strict: false, id: 1, recs: seq![], busy: false }, w1()),
        step2(w1(), L2Label::Commit { a: a_new(), out: COut::Applied(2) }, w2()),
        step2(w2(), L2Label::Commit { a: a_retry(), out: COut::Replayed(2) }, w2()),
        step2(w2(), L2Label::Commit { a: a_stale(), out: COut::Refused(Reason::StaleHead) }, w2()),
        step2(w2(), L2Label::SetStrict { on: true }, w3()),
        step2(w3(), L2Label::EngineWrite { w: Wr::Api, k: K { id: 9, edge: false, gr: 0 }, v: Some(1), landed: false }, w3()),
        w2().g.head == 2 && w2().rows.contains_key(w_k1()) && w2().g.sx.tuple.contains_key(w_k1()),
        w2().g.idem[7] == (2nat, 3int),
{
    assert(apply_recs(Map::<K, V>::empty(), Seq::<Op>::empty()) == Map::<K, V>::empty());
    let g1 = w1().g;
    assert(g1.head == 1);
    assert(g1.rev_by_id.contains_key(1) && !g1.rev_by_id.contains_key(2) && g1.id_by_seq[1] == 1);
    assert(!g1.idem.contains_key(7));
    assert(out2(w1().meta, g1, a_new()) == COut::Applied(2));
    assert(step2(w1(), L2Label::Commit { a: a_new(), out: COut::Applied(2) }, w2()));
    let g2 = w2().g;
    assert(g2.idem.contains_key(7) && g2.idem[7] == (2nat, 3int));
    assert(out2(w2().meta, g2, a_retry()) == COut::Replayed(2));
    assert(g2.rev_by_id.contains_key(1) && g2.id_by_seq[2] == 2);
    assert(out2(w2().meta, g2, a_stale()) == COut::Refused(Reason::StaleHead));
    let x = stmt_fold(g1.sx, 2, a_new().recs);
    assert(a_new().recs.drop_last() =~= Seq::<Op>::empty());
    assert(x.tuple.contains_key(w_k1()));
    assert(apply_recs(w1().rows, a_new().recs).contains_key(w_k1()));
    assert(refuses(w3(), Wr::Api));
}

} // verus!
