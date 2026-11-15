//! Proved counterexample for control `control_fc1202_erase_unguarded` (F-C1202, the adjacency half of F-1201),
//! compiled only with it. Lane proofs-pa3 (proof debt D-13): P-A3 removed, the pin's unguarded EraseGraph put back.
//!
//! Graph 0 is empty (as in the live reproduction `live-f1201-reproduced`). Eraser.EraseGraph(0) starts (TSTART takes
//! no lock) and its rdf_edges DELETE removes nothing; a writer inserts the NEW edge x1 of graph 0 (no row lock stops
//! an insert of a row that DELETE never saw), steps the generation before and after its write (reviewed R04-1) and
//! commits; RemoveGraph steps the graph's generation (reviewed R04-2), kills out and degc (its shared lock excludes no
//! writer) and the erase commits. The committed edge x1 has no adjacency entry. A Degree call then reads the current
//! generation, misses, has its probe granted, counts 0, passes its check and stores (gen, 0): the store is not an L1
//! step (a current entry must hold the committed degree, 1), and with nothing open L1's invariant fails (ADJ-I5.9).
use vstd::prelude::*;
use actors::protocol::*;
use crate::adj_l1::*;
use crate::adj_l2::*;
use crate::cx_adj_common::*;

verus! {

pub open spec fn z0() -> AS2 {
    AS2 { out: Set::empty(), gen: gconst(0), degc: Map::empty(), nolock: Set::empty(), w: Map::empty(), r: Map::empty(),
          e: Map::empty(), b: None, rows: Set::empty() }
}
pub open spec fn z1() -> AS2 {
    sete(z0(), 1, EP { g: 0, ph: EPh::Locked, del: Set::empty(), pre_out: Set::empty(), pre_degc: Map::empty(),
                       pre_gen: z0().gen, pre_nolock: false })
}
pub open spec fn z2() -> AS2 { sete(z1(), 1, EP { ph: EPh::Deleted, del: out_in(z1().rows, 0), ..z1().e[1] }) }
pub open spec fn wp() -> WP { WP { x: x1(), kind: WKind::Put, got: true, ph: WPh::Locked, had: false } }
pub open spec fn z3() -> AS2 { AS2 { w: z2().w.insert(0, wp()), nolock: z2().nolock, ..z2() } }
pub open spec fn z4() -> AS2 { AS2 { gen: gen_bump(z3().gen, k0()), ..setw(z3(), 0, WP { ph: WPh::Pre, ..z3().w[0] }) } }
pub open spec fn z5() -> AS2 {
    AS2 { out: z4().out.insert(x1()), ..setw(z4(), 0, WP { ph: WPh::Wrote, had: z4().out.contains(x1()), ..z4().w[0] }) }
}
pub open spec fn z6() -> AS2 { AS2 { gen: gen_bump(z5().gen, k0()), ..setw(z5(), 0, WP { ph: WPh::Post, ..z5().w[0] }) } }
pub open spec fn z7() -> AS2 { AS2 { rows: z6().rows.insert(x1()), w: z6().w.remove(0), ..z6() } }
pub open spec fn z8() -> AS2 { AS2 { gen: gen_step_graph(z7().gen, 0), ..sete(z7(), 1, EP { ph: EPh::Stepped, ..z7().e[1] }) } }
pub open spec fn z9() -> AS2 {
    AS2 { out: out_minus(z8().out, 0), degc: degc_minus(z8().degc, 0), nolock: z8().nolock.remove(0),
          ..sete(z8(), 1, EP { ph: EPh::Killed, pre_out: out_in(z8().out, 0), pre_degc: degc_in(z8().degc, 0),
                               pre_nolock: z8().nolock.contains(0), ..z8().e[1] }) }
}
pub open spec fn z10() -> AS2 { AS2 { rows: z9().rows.difference(z9().e[1].del), e: z9().e.remove(1), ..z9() } }
pub open spec fn z11() -> AS2 { setr(z10(), 2, RP { k: k0(), tgen: (z10().gen)(k0()), got: false, n: 0, ph: RPh::Gen }) }
pub open spec fn z12() -> AS2 { setr(z11(), 2, RP { ph: RPh::Looked, ..z11().r[2] }) }
pub open spec fn z13() -> AS2 { setr(z12(), 2, RP { ph: RPh::Probed, got: !held(z12(), 0), ..z12().r[2] }) }
pub open spec fn z14() -> AS2 { setr(z13(), 2, RP { ph: RPh::Counted, n: deg(z13().out, k0()), ..z13().r[2] }) }
pub open spec fn z15() -> AS2 { setr(z14(), 2, RP { ph: RPh::Checked, ..z14().r[2] }) }
pub open spec fn z16() -> AS2 {
    AS2 { degc: z15().degc.insert(k0(), (z15().r[2].tgen, z15().r[2].n)), ..setr(z15(), 2, RP { ph: RPh::Stored, ..z15().r[2] }) }
}
pub open spec fn z17() -> AS2 { AS2 { degc: z16().degc, r: z16().r.remove(2), ..z16() } }

pub proof fn counterexample_fc1202()
    ensures
        init2(z0()),
        step2(z0(), AL2::ELock { q: 1, g: 0 }, z1()),
        step2(z1(), AL2::ERows { q: 1 }, z2()),
        z2().e[1].del == Set::<X>::empty(),
        step2(z2(), AL2::WLock { p: 0, x: x1(), kind: WKind::Put, got: true }, z3()),
        step2(z3(), AL2::WPre { p: 0 }, z4()),
        step2(z4(), AL2::WOut { p: 0 }, z5()),
        step2(z5(), AL2::WPost { p: 0 }, z6()),
        step2(z6(), AL2::WCommit { p: 0, x: x1(), add: true }, z7()),
        step2(z7(), AL2::EStep { q: 1 }, z8()),
        step2(z8(), AL2::EKill { q: 1 }, z9()),
        step2(z9(), AL2::ECommit { q: 1, g: 0, del: Set::<X>::empty() }, z10()),
        // the erase committed: a committed edge of graph 0 with no adjacency entry, nothing open
        z10().rows.contains(x1()) && !z10().out.contains(x1()),
        z10().w.dom() == Set::<nat>::empty() && z10().e.dom() == Set::<nat>::empty() && z10().b is None,
        step2(z10(), AL2::RStart { p: 2, k: k0() }, z11()),
        step2(z11(), AL2::RLookup { p: 2, k: k0(), hit: None }, z12()),
        step2(z12(), AL2::RProbe { p: 2 }, z13()),
        step2(z13(), AL2::RCount { p: 2 }, z14()),
        step2(z14(), AL2::RCheck { p: 2 }, z15()),
        step2(z15(), AL2::RStore { p: 2 }, z16()),
        step2(z16(), AL2::RRecheck { p: 2 }, z17()),
        !step_or_stutter::<AdjL1>(abs04(z15()), lab04(AL2::RStore { p: 2 }), abs04(z16())),
        z17().w.dom() == Set::<nat>::empty() && z17().r.dom() == Set::<nat>::empty()
            && z17().e.dom() == Set::<nat>::empty() && z17().b is None,
        cur2(z17().degc, z17().gen, k0()) && z17().degc[k0()] == (3nat, 0nat) && deg(z17().rows, k0()) == 1,
        !inv1(abs04(z17())),
{
    lemma_degs();
    let sx1 = Set::<X>::empty().insert(x1());
    assert(deg(sx1, k0()) == 1) by {
        assert(sx1.filter(of_src(k0())) =~= sx1);
    }
    assert(step2(z0(), AL2::ELock { q: 1, g: 0 }, z1())) by {
        assert forall|q: nat| !z0().e.contains_key(q) by {}
        assert forall|p: nat| !z0().w.contains_key(p) by {}
    }
    assert(step2(z1(), AL2::ERows { q: 1 }, z2())) by {
        assert forall|p: nat| !z1().w.contains_key(p) by {}
    }
    assert(out_in(z1().rows, 0) =~= Set::<X>::empty());
    // as built: the writer waits only for row locks, and the DELETE removed no row
    assert(step2(z2(), AL2::WLock { p: 0, x: x1(), kind: WKind::Put, got: true }, z3())) by {
        assert forall|q: nat| #[trigger] z2().e.contains_key(q) implies !z2().e[q].del.contains(x1()) by {}
        assert forall|p2: nat| !z2().w.contains_key(p2) by {}
    }
    assert(step2(z3(), AL2::WPre { p: 0 }, z4()));
    assert(step2(z4(), AL2::WOut { p: 0 }, z5()));
    assert(step2(z5(), AL2::WPost { p: 0 }, z6()));
    assert(step2(z6(), AL2::WCommit { p: 0, x: x1(), add: true }, z7()));
    assert(z7().w =~= Map::<nat, WP>::empty());
    assert((z7().gen)(k0()) == 2);
    assert(step2(z7(), AL2::EStep { q: 1 }, z8()));
    assert((z8().gen)(k0()) == 3);
    assert(step2(z8(), AL2::EKill { q: 1 }, z9()));
    assert(z9().out =~= Set::<X>::empty());
    assert(z9().e[1].del == Set::<X>::empty());
    assert(step2(z9(), AL2::ECommit { q: 1, g: 0, del: Set::<X>::empty() }, z10()));
    assert(z10().rows =~= sx1);
    assert(z10().w.dom() =~= Set::<nat>::empty());
    assert(z10().e.dom() =~= Set::<nat>::empty());
    assert(step2(z10(), AL2::RStart { p: 2, k: k0() }, z11()));
    assert(z11().r[2].tgen == 3);
    assert(!z11().degc.contains_key(k0()));
    assert(step2(z11(), AL2::RLookup { p: 2, k: k0(), hit: None }, z12()));
    assert(!held(z12(), 0)) by {
        assert forall|p: nat| !z12().w.contains_key(p) by {}
        assert forall|q: nat| !z12().e.contains_key(q) by {}
    }
    assert(step2(z12(), AL2::RProbe { p: 2 }, z13()));
    assert(z13().out =~= Set::<X>::empty());
    assert(step2(z13(), AL2::RCount { p: 2 }, z14()));
    assert(z14().r[2].n == 0);
    assert(!z14().nolock.contains(0));
    assert(step2(z14(), AL2::RCheck { p: 2 }, z15()));
    assert(step2(z15(), AL2::RStore { p: 2 }, z16()));
    assert(z16().degc[k0()] == (3nat, 0nat));
    assert(step2(z16(), AL2::RRecheck { p: 2 }, z17()));
    assert(!entry_ok(z15().rows, z15().gen, k0(), (3nat, 0nat)));
    assert(z17().r.dom() =~= Set::<nat>::empty());
    assert(z17().w.dom() =~= Set::<nat>::empty());
    assert(z17().e.dom() =~= Set::<nat>::empty());
    assert(abs04(z17()).cache.contains_key(k0()));
    assert(!entry_ok(z17().rows, z17().gen, k0(), z17().degc[k0()]));
}

} // verus!
