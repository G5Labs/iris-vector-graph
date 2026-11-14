//! Proved counterexample for control `control_fc1101_stats_whole_row` (F-C1101, root cause shared with F-1102),
//! compiled only with it. The live trace of b-11-live-f1102-txn:
//!
//! process A commits inside its caller's transaction (the stats row saved with CommitsOk 2); process B's Bump opens
//! the row (a dirty copy, %OpenId takes no lock); A's caller rolls back (CommitsOk 1 again, head 1); B's %Save
//! writes its whole copy: CommitsOk 2 while one revision past genesis was never kept. The save is not an L1 step
//! (nothing visible may change), and the L2 invariant `stats.ok == head` fails.
use vstd::prelude::*;
use actors::protocol::*;
use crate::ledger_l1::*;
use crate::ledger_l2::*;
use crate::cx_ledger_common::*;

verus! {

pub open spec fn k1() -> K { K { id: 1, edge: false, gr: 0 } }
pub open spec fn a() -> CArgs { CArgs { recs: seq![Op { k: k1(), v: Some(5) }], key: None, fp: 0, exp: None, id: 2 } }
pub open spec fn c1() -> LS2 { c_genesis(false) }
pub open spec fn c2() -> LS2 {
    LS2 { txn: Some(Txn { pre: c1().g, pre_ok: 1, pre_rows: c1().rows, a: a() }), ..applied(c1(), a()) }
}
pub open spec fn c3() -> LS2 { LS2 { copies: c2().copies.insert(0, c2().stats), ..c2() } }
pub open spec fn c4() -> LS2 {
    LS2 { g: c1().g, stats: Stats { ok: 1, ..c3().stats }, rows: restore(c3().rows, c1().rows, a().recs), txn: None, ..c3() }
}
pub open spec fn c5() -> LS2 { LS2 { stats: bump_save(c4().stats, c4().copies[0]), copies: c4().copies.remove(0), ..c4() } }

pub proof fn counterexample_fc1101()
    ensures
        init2(c_init()),
        step2(c_init(), L2Label::Enable { strict: false, id: 1, recs: seq![], busy: false }, c1()),
        step2(c1(), L2Label::CommitNested { a: a() }, c2()),
        step2(c2(), L2Label::BumpRead { p: 0 }, c3()),
        step2(c3(), L2Label::CallerEnd { keep: false, a: a(), seq: 2 }, c4()),
        step2(c4(), L2Label::BumpSave { p: 0 }, c5()),
        c5().txn is None && c5().stats.ok == 2 && c5().g.head == 1,
        !inv2(c5()),
        !step_or_stutter::<L1>(abs11(c4()), lab11(L2Label::BumpSave { p: 0 }), abs11(c5())),
{
    lemma_genesis_step(false);
    let g1 = c1().g;
    assert(g1.head == 1);
    assert(!g1.rev_by_id.contains_key(2));
    assert(g1.idem == Map::<IKey, (nat, Fp)>::empty());
    assert(out2(c1().meta, g1, a()) == COut::Applied(2));
    assert(step2(c1(), L2Label::CommitNested { a: a() }, c2()));
    assert(c2().stats.ok == 2);
    assert(step2(c2(), L2Label::BumpRead { p: 0 }, c3()));
    assert(c3().copies[0].ok == 2);
    assert(step2(c3(), L2Label::CallerEnd { keep: false, a: a(), seq: 2 }, c4()));
    assert(c4().copies.contains_key(0));
    assert(step2(c4(), L2Label::BumpSave { p: 0 }, c5()));
    assert(c5().stats.ok == 2);
    assert(cok(c4()) == 1 && cok(c5()) == 2);
    assert(abs11(c4()).ok != abs11(c5()).ok);
}

} // verus!
