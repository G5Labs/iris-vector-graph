//! Proved counterexample for control `control_fc0401_write_before_gen` (F-C0401), compiled only with it.
//!
//! A Degree call reads generation 0 and has its probe granted; a writer then takes the lock and writes edge x1
//! (Adjacency.Put writes out before its $Increment, Adjacency.cls:87-89); the reader counts 2 (the uncommitted edge
//! is visible), its check passes (the generation has not moved) and it stores (0, 2); the writer is stopped before
//! its generation step and rolled back. With no transaction open, the entry carries the current generation and holds
//! 2 while the committed degree is 1. The store is not an L1 step and L1's invariant fails.
use vstd::prelude::*;
use actors::protocol::*;
use crate::adj_l1::*;
use crate::adj_l2::*;
use crate::cx_adj_common::*;

verus! {

pub open spec fn wp1() -> WP { WP { x: x1(), kind: WKind::Put, got: true, ph: WPh::Locked, had: false } }
pub open spec fn c3() -> AS2 { r3(0) }
pub open spec fn c4() -> AS2 { AS2 { w: c3().w.insert(1, wp1()), nolock: c3().nolock, ..c3() } }
pub open spec fn c5() -> AS2 {
    AS2 { out: c4().out.insert(x1()), ..setw(c4(), 1, WP { ph: WPh::Wrote, had: c4().out.contains(x1()), ..c4().w[1] }) }
}
pub open spec fn c6() -> AS2 { setr(c5(), 0, RP { ph: RPh::Counted, n: deg(c5().out, k0()), ..c5().r[0] }) }
pub open spec fn c7() -> AS2 { setr(c6(), 0, RP { ph: RPh::Checked, ..c6().r[0] }) }
pub open spec fn c8() -> AS2 {
    AS2 { degc: c7().degc.insert(k0(), (c7().r[0].tgen, c7().r[0].n)), ..setr(c7(), 0, RP { ph: RPh::Stored, ..c7().r[0] }) }
}
pub open spec fn c9() -> AS2 { AS2 { degc: c8().degc, r: c8().r.remove(0), ..c8() } }
pub open spec fn c10() -> AS2 { AS2 { out: c9().out.remove(x1()), w: c9().w.remove(1), ..c9() } }

pub proof fn counterexample_fc0401()
    ensures
        init2(a_init(0)),
        step2(c3(), AL2::WLock { p: 1, x: x1(), kind: WKind::Put, got: true }, c4()),
        step2(c4(), AL2::WOut { p: 1 }, c5()),
        step2(c5(), AL2::RCount { p: 0 }, c6()),
        step2(c6(), AL2::RCheck { p: 0 }, c7()),
        step2(c7(), AL2::RStore { p: 0 }, c8()),
        step2(c8(), AL2::RRecheck { p: 0 }, c9()),
        step2(c9(), AL2::WAbort { p: 1 }, c10()),
        !step_or_stutter::<AdjL1>(abs04(c7()), lab04(AL2::RStore { p: 0 }), abs04(c8())),
        c10().w.dom() == Set::<nat>::empty() && c10().r.dom() == Set::<nat>::empty() && c10().e == Map::<nat, EP>::empty()
            && c10().b is None,
        cur2(c10().degc, c10().gen, k0()) && c10().degc[k0()] == (0nat, 2nat) && deg(c10().rows, k0()) == 1,
        !inv1(abs04(c10())),
{
    lemma_reader_opens(0);
    lemma_degs();
    assert(step2(c3(), AL2::WLock { p: 1, x: x1(), kind: WKind::Put, got: true }, c4())) by {
        assert forall|p2: nat| !c3().w.contains_key(p2) by {}
        assert forall|q: nat| !c3().e.contains_key(q) by {}
    }
    assert(step2(c4(), AL2::WOut { p: 1 }, c5()));
    assert(c5().out == s01());
    assert(step2(c5(), AL2::RCount { p: 0 }, c6()));
    assert(c6().r[0].n == 2);
    assert((c6().gen)(k0()) == 0);
    assert(step2(c6(), AL2::RCheck { p: 0 }, c7()));
    assert(step2(c7(), AL2::RStore { p: 0 }, c8()));
    assert(c8().degc[k0()] == (0nat, 2nat));
    assert(step2(c8(), AL2::RRecheck { p: 0 }, c9()));
    assert(wrote(c9().w[1]) && !c9().w[1].had);
    assert(step2(c9(), AL2::WAbort { p: 1 }, c10()));
    assert(c10().w.dom() =~= Set::<nat>::empty());
    assert(c10().r.dom() =~= Set::<nat>::empty());
    assert(!entry_ok(c7().rows, c7().gen, k0(), (0nat, 2nat)));
    assert(abs04(c10()).cache.contains_key(k0()));
}

} // verus!
