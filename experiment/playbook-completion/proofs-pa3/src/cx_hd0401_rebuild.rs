//! Proved counterexample for control `control_hd0401_rebuild_kills_gen` (HD-0401, rebuild), compiled only with it.
//!
//! A Degree call reads generation 2 and has its probe granted; a rebuild (BuildKG) runs RemoveAll, which kills out
//! and gen (Adjacency.cls:452-462); the reader counts 0; the rebuild fills from the rows without stepping a generation
//! (FillEdge, Adjacency.cls:824-830) and commits; a later Put of x1 steps the restarted generation back to 2 and
//! commits; the reader's check passes (the generation equals the one it read) and it stores (2, 0). With no
//! transaction open the stale count is valid again while the committed degree is 2. RemoveAll's kill is not an L1
//! step (a generation goes back) and L1's invariant fails at the end.
use vstd::prelude::*;
use actors::protocol::*;
use crate::adj_l1::*;
use crate::adj_l2::*;
use crate::cx_adj_common::*;

verus! {

pub open spec fn wp1() -> WP { WP { x: x1(), kind: WKind::Put, got: true, ph: WPh::Locked, had: false } }
pub open spec fn c3() -> AS2 { r3(2) }
pub open spec fn c4() -> AS2 {
    setb(c3(), BP { ph: BPh::Begun, pre_out: Set::empty(), pre_degc: Map::empty(), pre_gen: c3().gen, pre_nolock: Set::empty() })
}
pub open spec fn c5() -> AS2 {
    AS2 { out: Set::empty(), degc: Map::empty(), nolock: Set::empty(), gen: gen_zero(),
          ..setb(c4(), BP { ph: BPh::Killed, pre_out: c4().out, pre_degc: c4().degc, pre_gen: c4().gen,
                            pre_nolock: c4().nolock, ..c4().b->0 }) }
}
pub open spec fn c6() -> AS2 { setr(c5(), 0, RP { ph: RPh::Counted, n: deg(c5().out, k0()), ..c5().r[0] }) }
pub open spec fn c7() -> AS2 { AS2 { out: c6().rows, ..setb(c6(), BP { ph: BPh::Filled, ..c6().b->0 }) } }
pub open spec fn c8() -> AS2 { AS2 { b: None, ..c7() } }
pub open spec fn c9() -> AS2 { AS2 { w: c8().w.insert(1, wp1()), nolock: c8().nolock, ..c8() } }
pub open spec fn c10() -> AS2 { AS2 { gen: gen_bump(c9().gen, k0()), ..setw(c9(), 1, WP { ph: WPh::Pre, ..c9().w[1] }) } }
pub open spec fn c11() -> AS2 {
    AS2 { out: c10().out.insert(x1()), ..setw(c10(), 1, WP { ph: WPh::Wrote, had: c10().out.contains(x1()), ..c10().w[1] }) }
}
pub open spec fn c12() -> AS2 { AS2 { gen: gen_bump(c11().gen, k0()), ..setw(c11(), 1, WP { ph: WPh::Post, ..c11().w[1] }) } }
pub open spec fn c13() -> AS2 { AS2 { rows: c12().rows.insert(x1()), w: c12().w.remove(1), ..c12() } }
pub open spec fn c14() -> AS2 { setr(c13(), 0, RP { ph: RPh::Checked, ..c13().r[0] }) }
pub open spec fn c15() -> AS2 {
    AS2 { degc: c14().degc.insert(k0(), (c14().r[0].tgen, c14().r[0].n)), ..setr(c14(), 0, RP { ph: RPh::Stored, ..c14().r[0] }) }
}
pub open spec fn c16() -> AS2 { AS2 { degc: c15().degc, r: c15().r.remove(0), ..c15() } }

pub proof fn counterexample_hd0401_rebuild()
    ensures
        init2(a_init(2)),
        step2(c3(), AL2::BBegin, c4()),
        step2(c4(), AL2::BKill, c5()),
        step2(c5(), AL2::RCount { p: 0 }, c6()),
        step2(c6(), AL2::BFill, c7()),
        step2(c7(), AL2::BCommit, c8()),
        step2(c8(), AL2::WLock { p: 1, x: x1(), kind: WKind::Put, got: true }, c9()),
        step2(c9(), AL2::WPre { p: 1 }, c10()),
        step2(c10(), AL2::WOut { p: 1 }, c11()),
        step2(c11(), AL2::WPost { p: 1 }, c12()),
        step2(c12(), AL2::WCommit { p: 1, x: x1(), add: true }, c13()),
        step2(c13(), AL2::RCheck { p: 0 }, c14()),
        step2(c14(), AL2::RStore { p: 0 }, c15()),
        step2(c15(), AL2::RRecheck { p: 0 }, c16()),
        !step_or_stutter::<AdjL1>(abs04(c4()), lab04(AL2::BKill), abs04(c5())),
        c16().w.dom() == Set::<nat>::empty() && c16().r.dom() == Set::<nat>::empty() && c16().e == Map::<nat, EP>::empty()
            && c16().b is None,
        cur2(c16().degc, c16().gen, k0()) && c16().degc[k0()] == (2nat, 0nat) && deg(c16().rows, k0()) == 2,
        !inv1(abs04(c16())),
{
    lemma_reader_opens(2);
    lemma_degs();
    assert(step2(c3(), AL2::BBegin, c4())) by {
        assert forall|p: nat| !c3().w.contains_key(p) by {}
        assert forall|q: nat| !c3().e.contains_key(q) by {}
    }
    assert(step2(c4(), AL2::BKill, c5()));
    assert((c4().gen)(k0()) == 2 && (c5().gen)(k0()) == 0);
    assert(abs04(c5()).ep != abs04(c4()).ep);
    assert(step2(c5(), AL2::RCount { p: 0 }, c6()));
    assert(c6().r[0].n == 0);
    assert(step2(c6(), AL2::BFill, c7()));
    assert(step2(c7(), AL2::BCommit, c8()));
    assert(step2(c8(), AL2::WLock { p: 1, x: x1(), kind: WKind::Put, got: true }, c9())) by {
        assert(c8().w =~= Map::<nat, WP>::empty());
        assert forall|p2: nat| !c8().w.contains_key(p2) by {}
        assert forall|q: nat| !c8().e.contains_key(q) by {}
    }
    assert(step2(c9(), AL2::WPre { p: 1 }, c10()));
    assert(step2(c10(), AL2::WOut { p: 1 }, c11()));
    assert(!c11().w[1].had);
    assert(step2(c11(), AL2::WPost { p: 1 }, c12()));
    assert((c12().gen)(k0()) == 2);
    assert(step2(c12(), AL2::WCommit { p: 1, x: x1(), add: true }, c13()));
    assert(c13().rows == s01());
    assert(!c13().nolock.contains(0));
    assert(step2(c13(), AL2::RCheck { p: 0 }, c14()));
    assert(step2(c14(), AL2::RStore { p: 0 }, c15()));
    assert(c15().degc[k0()] == (2nat, 0nat));
    assert(step2(c15(), AL2::RRecheck { p: 0 }, c16()));
    assert(c16().w.dom() =~= Set::<nat>::empty());
    assert(c16().r.dom() =~= Set::<nat>::empty());
    assert(abs04(c16()).cache.contains_key(k0()));
}

} // verus!
