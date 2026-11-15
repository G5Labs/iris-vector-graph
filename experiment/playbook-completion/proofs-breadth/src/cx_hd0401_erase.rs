//! Proved counterexample for control `control_hd0401_erase_kills_gen` (F-0401 / HD-0401, erase), compiled only with it.
//!
//! The finding's trace: generation 0 (absent); a Degree call reads it and has its probe granted; Eraser.EraseGraph's
//! RemoveGraph takes the lock and kills out (Adjacency.cls:434-439); the reader counts 0, its check passes (the
//! generation is still 0) and it stores (0, 0); RemoveGraph kills gen and degc; the erase rolls back, restoring out
//! and the killed degc node (the reader's entry). With no transaction open the entry (0, 0) is current while the
//! committed degree is 1. The store is not an L1 step and L1's invariant fails.
use vstd::prelude::*;
use actors::protocol::*;
use crate::adj_l1::*;
use crate::adj_l2::*;
use crate::cx_adj_common::*;

verus! {

pub open spec fn c3() -> AS2 { r3(0) }
pub open spec fn c4() -> AS2 {
    sete(c3(), 1, EP { g: 0, ph: EPh::Locked, pre_out: Set::empty(), pre_degc: Map::empty(), pre_gen: c3().gen, pre_nolock: false })
}
pub open spec fn c5() -> AS2 {
    AS2 { out: out_minus(c4().out, 0), ..sete(c4(), 1, EP { ph: EPh::OutKilled, pre_out: out_in(c4().out, 0), ..c4().e[1] }) }
}
pub open spec fn c6() -> AS2 { setr(c5(), 0, RP { ph: RPh::Counted, n: deg(c5().out, k0()), ..c5().r[0] }) }
pub open spec fn c7() -> AS2 { setr(c6(), 0, RP { ph: RPh::Checked, ..c6().r[0] }) }
pub open spec fn c8() -> AS2 {
    AS2 { degc: c7().degc.insert(k0(), (c7().r[0].tgen, c7().r[0].n)), ..setr(c7(), 0, RP { ph: RPh::Stored, ..c7().r[0] }) }
}
pub open spec fn c9() -> AS2 { AS2 { degc: c8().degc, r: c8().r.remove(0), ..c8() } }
pub open spec fn c10() -> AS2 {
    AS2 { gen: gen_kill_graph(c9().gen, 0), degc: degc_minus(c9().degc, 0), nolock: c9().nolock.remove(0),
          ..sete(c9(), 1, EP { ph: EPh::Killed, pre_gen: c9().gen, pre_degc: degc_in(c9().degc, 0),
                               pre_nolock: c9().nolock.contains(0), ..c9().e[1] }) }
}
pub open spec fn c11() -> AS2 {
    AS2 { out: c10().out.union(c10().e[1].pre_out), degc: c10().degc.union_prefer_right(c10().e[1].pre_degc),
          nolock: c10().nolock, gen: gen_restore_graph(c10().gen, c10().e[1].pre_gen, 0), e: c10().e.remove(1), ..c10() }
}

pub proof fn counterexample_hd0401_erase()
    ensures
        init2(a_init(0)),
        step2(c3(), AL2::ELock { q: 1, g: 0 }, c4()),
        step2(c4(), AL2::EKillOut { q: 1 }, c5()),
        step2(c5(), AL2::RCount { p: 0 }, c6()),
        step2(c6(), AL2::RCheck { p: 0 }, c7()),
        step2(c7(), AL2::RStore { p: 0 }, c8()),
        step2(c8(), AL2::RRecheck { p: 0 }, c9()),
        step2(c9(), AL2::EKill { q: 1 }, c10()),
        step2(c10(), AL2::EAbort { q: 1 }, c11()),
        !step_or_stutter::<AdjL1>(abs04(c7()), lab04(AL2::RStore { p: 0 }), abs04(c8())),
        c11().w == Map::<nat, WP>::empty() && c11().r.dom() == Set::<nat>::empty() && c11().e.dom() == Set::<nat>::empty()
            && c11().b is None,
        cur2(c11().degc, c11().gen, k0()) && c11().degc[k0()] == (0nat, 0nat) && deg(c11().rows, k0()) == 1,
        !inv1(abs04(c11())),
{
    lemma_reader_opens(0);
    lemma_degs();
    assert(step2(c3(), AL2::ELock { q: 1, g: 0 }, c4())) by {
        assert forall|p: nat| !c3().w.contains_key(p) by {}
        assert forall|q: nat| !c3().e.contains_key(q) by {}
    }
    assert(step2(c4(), AL2::EKillOut { q: 1 }, c5()));
    assert(c5().out =~= Set::<X>::empty());
    assert(step2(c5(), AL2::RCount { p: 0 }, c6()));
    assert(c6().r[0].n == 0);
    assert(step2(c6(), AL2::RCheck { p: 0 }, c7()));
    assert(step2(c7(), AL2::RStore { p: 0 }, c8()));
    assert(step2(c8(), AL2::RRecheck { p: 0 }, c9()));
    assert(step2(c9(), AL2::EKill { q: 1 }, c10()));
    assert(c10().e[1].pre_degc.contains_key(k0()) && c10().e[1].pre_degc[k0()] == (0nat, 0nat));
    assert(step2(c10(), AL2::EAbort { q: 1 }, c11()));
    assert(c11().degc[k0()] == (0nat, 0nat));
    assert((c11().gen)(k0()) == 0);
    assert(c11().r.dom() =~= Set::<nat>::empty());
    assert(c11().e.dom() =~= Set::<nat>::empty());
    assert(!entry_ok(c7().rows, c7().gen, k0(), (0nat, 0nat)));
    assert(abs04(c11()).cache.contains_key(k0()));
}

} // verus!
