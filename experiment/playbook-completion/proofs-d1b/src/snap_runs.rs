//! Module 18: generic runs of the L2 step relation used by the witness and the counterexamples (valid under every
//! feature): a whole `save_snapshot` (start, four store reads, the ledger globals, the ZIP) and a whole replacing
//! `restore_snapshot` (erase_all, rows and globals, ledger globals, answer), as the active design defines them.
use vstd::prelude::*;
use crate::snap_l1::*;
use crate::snap_l2::*;

verus! {

pub open spec fn sv(s: SS2, id: nat, k: nat) -> SS2 {
    SS2 { x: Some(XP { id, stage: k, part: read_upto(s.cur, k), g: None }), ..s }
}
pub open spec fn svl(s: SS2, id: nat) -> SS2 {
    SS2 { x: Some(XP { id, stage: 4, part: read_upto(s.cur, 4), g: Some(s.g) }), ..s }
}
pub open spec fn sve(s: SS2, id: nat) -> SS2 {
    SS2 { files: s.files.insert(id, AF { lines: read_upto(s.cur, 4), g: s.g }), x: None, ..s }
}

proof fn lemma_read_step(c: Set<Item>, k: nat)
    ensures read_upto(c, k + 1) == (if planned(k as int) { read_upto(c, k).union(store_of(c, k as int)) } else { read_upto(c, k) }),
{
    if planned(k as int) {
        assert(read_upto(c, k + 1) =~= read_upto(c, k).union(store_of(c, k as int)));
    } else {
        assert(read_upto(c, k + 1) =~= read_upto(c, k));
    }
}

/// A whole save of archive `id` with nothing else running.
pub proof fn lemma_save_run(s: SS2, id: nat)
    requires s.x is None, s.r is None, fc1801() || s.w is None, !s.files.contains_key(id),
    ensures
        step2(s, SL2::XStart { id }, sv(s, id, 0)),
        step2(sv(s, id, 0), SL2::XRead, sv(s, id, 1)),
        step2(sv(s, id, 1), SL2::XRead, sv(s, id, 2)),
        step2(sv(s, id, 2), SL2::XRead, sv(s, id, 3)),
        step2(sv(s, id, 3), SL2::XRead, sv(s, id, 4)),
        step2(sv(s, id, 4), SL2::XLedger, svl(s, id)),
        step2(svl(s, id), SL2::XEnd { id, lines: read_upto(s.cur, 4), g: s.g }, sve(s, id)),
{
    assert(read_upto(s.cur, 0) =~= Set::<Item>::empty());
    lemma_read_step(s.cur, 0);
    lemma_read_step(s.cur, 1);
    lemma_read_step(s.cur, 2);
    lemma_read_step(s.cur, 3);
}

pub open spec fn fail_of(bad: Set<Item>) -> Set<Item> { if fc1802() { Set::empty() } else { bad } }

pub open spec fn rb(s: SS2, id: nat) -> SS2 {
    SS2 { rows: Set::empty(), cur: Set::empty(),
          r: Some(RP { id, ph: RPh::Erased, failed: Set::empty(), pre_rows: s.rows, pre_g: s.g }), ..s }
}
pub open spec fn rl(s: SS2, id: nat, bad: Set<Item>) -> SS2 {
    let l = loaded(s.files[id].lines, bad, s.scope);
    SS2 { rows: l, cur: l,
          r: Some(RP { id, ph: RPh::Loaded, failed: fail_of(bad), pre_rows: s.rows, pre_g: s.g }), ..s }
}
pub open spec fn rg(s: SS2, id: nat, bad: Set<Item>) -> SS2 {
    SS2 { g: overlay(s.g, s.files[id].g, s.scope),
          r: Some(RP { id, ph: RPh::LedgerSet, failed: fail_of(bad), pre_rows: s.rows, pre_g: s.g }), ..rl(s, id, bad) }
}
pub open spec fn re(s: SS2, id: nat, bad: Set<Item>) -> SS2 { SS2 { r: None, ..rg(s, id, bad) } }

/// A whole replacing restore of archive `id` with nothing else running, IRIS refusing the global lines `bad`.
pub proof fn lemma_restore_run(s: SS2, id: nat, bad: Set<Item>)
    requires
        s.files.contains_key(id), s.r is None, s.x is None, s.w is None,
        f1801p() || prefix(s.g.led, s.files[id].g.led), bad.subset_of(store_of(s.files[id].lines, 3)),
    ensures
        step2(s, SL2::RBegin { id }, rb(s, id)),
        step2(rb(s, id), SL2::RLoad { bad }, rl(s, id, bad)),
        step2(rl(s, id, bad), SL2::RLedger, rg(s, id, bad)),
        step2(rg(s, id, bad), SL2::REnd { id, failed: fail_of(bad) }, re(s, id, bad)),
{
}

// ------------------------------------------------------------------------------------------------ concrete states

/// The initial state: an empty namespace, a never-committed ledger, no archive.
pub open spec fn c0() -> SS2 {
    SS2 { rows: Set::empty(), cur: Set::empty(), g: G2 { led: led0(), rev: Set::empty() }, scope: Set::empty(),
          w: None, x: None, r: None, files: Map::empty() }
}

pub proof fn lemma_c0()
    ensures init2(c0()),
{
}

pub open spec fn c_commit(s: SS2, items: Set<Item>, id: int) -> SS2 {
    SS2 { rows: s.rows.union(items), cur: s.cur.union(items), g: commit_g(s.g, items, id), ..s }
}

pub proof fn lemma_commit_run(s: SS2, items: Set<Item>, id: int)
    requires writer_may(s), new_items(s, items), !s.g.rev.contains(s.g.led.head + 1),
    ensures step2(s, SL2::Commit { items, id }, c_commit(s, items, id)),
{
}

/// Tenant 7's content `(0, 7, 1)` (a table row).
pub open spec fn i7() -> Item { (0, 7, 1) }
/// Tenant 7 commits its row (revision 1, id 1).
pub open spec fn t1() -> SS2 { c_commit(c0(), set![i7()], 1) }
/// Archive 0 is saved: it holds the row and revision 1's record.
pub open spec fn t2() -> SS2 { sve(t1(), 0) }
/// The tenant is erased: its row leaves the namespace, its record stays in the history.
pub open spec fn t3() -> SS2 { SS2 { rows: not_ten(t2().rows, 7), cur: not_ten(t2().cur, 7), ..t2() } }

pub open spec fn g1_of(items: Set<Item>) -> G2 { commit_g(G2 { led: led0(), rev: Set::empty() }, items, 1) }

/// Commit, save of archive 0, erase of tenant 7: steps of the L2 relation under every feature.
pub proof fn lemma_tenant_run()
    ensures
        init2(c0()),
        step2(c0(), SL2::Commit { items: set![i7()], id: 1 }, t1()),
        t1().rows == set![i7()] && t1().cur == set![i7()] && t1().g == g1_of(set![i7()]),
        read_upto(t1().cur, 4) == set![i7()],
        t2().files == Map::<nat, AF>::empty().insert(0, AF { lines: set![i7()], g: g1_of(set![i7()]) }),
        step2(t2(), SL2::Erase { ten: 7 }, t3()),
        t3().rows == Set::<Item>::empty() && t3().cur == Set::<Item>::empty(),
        t3().g == g1_of(set![i7()]) && t3().scope == Set::<int>::empty() && t3().w is None && t3().x is None && t3().r is None,
{
    lemma_commit_run(c0(), set![i7()], 1);
    assert(t1().rows =~= set![i7()]);
    assert(t1().cur =~= set![i7()]);
    assert(read_upto(t1().cur, 4) =~= set![i7()]) by { assert(planned(0)); }
    lemma_save_run(t1(), 0);
    assert(not_ten(t2().rows, 7) =~= Set::<Item>::empty());
    assert(not_ten(t2().cur, 7) =~= Set::<Item>::empty());
}

} // verus!
