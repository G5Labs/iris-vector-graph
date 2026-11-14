//! Non-vacuity of the module 04 reviewed model (compiled without controls): a concrete run of the L2 step relation
//! from its initial state in which a writer commits edge x1 (stepping the generation before and after its write), a
//! Degree call counts and stores the current entry (2, 2), a second Degree call hits it (an L1 `Hit` answering the
//! committed degree 2), and EraseGraph deletes the rows, RemoveGraph steps the generation, kills out and degc and
//! commits; each step is an L1 step or a stutter (`theorem_raw_executions_refine`).
//!
//! `witness_overlap` (lane proofs-pa3): the reviewed model admits a writer and an eraser of the same graph open
//! together (P-A3 is not assumed): a lock-less writer of graph 0 is in flight when EraseGraph(0) takes its lock; the
//! writer commits, the eraser's DELETE then removes its row, and the erase commits with graph 0 empty.
use vstd::prelude::*;
use crate::adj_l1::*;
use crate::adj_l2::*;

verus! {

pub open spec fn k0() -> KS { (0, 0) }
pub open spec fn x0() -> X { (0, 0, 0) }
pub open spec fn x1() -> X { (0, 0, 1) }
pub open spec fn s0() -> Set<X> { Set::empty().insert(x0()) }
pub open spec fn g0() -> spec_fn(KS) -> nat { |k: KS| 0nat }
pub open spec fn wp1() -> WP { WP { x: x1(), kind: WKind::Put, got: true, ph: WPh::Locked, had: false } }

pub open spec fn v0() -> AS2 {
    AS2 { out: s0(), gen: g0(), degc: Map::empty(), nolock: Set::empty(), w: Map::empty(), r: Map::empty(),
          e: Map::empty(), b: None, rows: s0() }
}
pub open spec fn v1() -> AS2 { AS2 { w: v0().w.insert(1, wp1()), nolock: v0().nolock, ..v0() } }
pub open spec fn v2() -> AS2 { AS2 { gen: gen_bump(v1().gen, k0()), ..setw(v1(), 1, WP { ph: WPh::Pre, ..v1().w[1] }) } }
pub open spec fn v3() -> AS2 {
    AS2 { out: v2().out.insert(x1()), ..setw(v2(), 1, WP { ph: WPh::Wrote, had: v2().out.contains(x1()), ..v2().w[1] }) }
}
pub open spec fn v4() -> AS2 { AS2 { gen: gen_bump(v3().gen, k0()), ..setw(v3(), 1, WP { ph: WPh::Post, ..v3().w[1] }) } }
pub open spec fn v5() -> AS2 { AS2 { rows: v4().rows.insert(x1()), w: v4().w.remove(1), ..v4() } }
pub open spec fn v6() -> AS2 { setr(v5(), 0, RP { k: k0(), tgen: (v5().gen)(k0()), got: false, n: 0, ph: RPh::Gen }) }
pub open spec fn v7() -> AS2 { setr(v6(), 0, RP { ph: RPh::Looked, ..v6().r[0] }) }
pub open spec fn v8() -> AS2 { setr(v7(), 0, RP { ph: RPh::Probed, got: !held(v7(), 0), ..v7().r[0] }) }
pub open spec fn v9() -> AS2 { setr(v8(), 0, RP { ph: RPh::Counted, n: deg(v8().out, k0()), ..v8().r[0] }) }
pub open spec fn v10() -> AS2 { setr(v9(), 0, RP { ph: RPh::Checked, ..v9().r[0] }) }
pub open spec fn v11() -> AS2 {
    AS2 { degc: v10().degc.insert(k0(), (v10().r[0].tgen, v10().r[0].n)), ..setr(v10(), 0, RP { ph: RPh::Stored, ..v10().r[0] }) }
}
pub open spec fn v12() -> AS2 { AS2 { degc: v11().degc, r: v11().r.remove(0), ..v11() } }
pub open spec fn v13() -> AS2 { setr(v12(), 2, RP { k: k0(), tgen: (v12().gen)(k0()), got: false, n: 0, ph: RPh::Gen }) }
pub open spec fn v14() -> AS2 { AS2 { r: v13().r.remove(2), ..v13() } }
pub open spec fn v15() -> AS2 {
    sete(v14(), 3, EP { g: 0, ph: EPh::Locked, del: Set::empty(), pre_out: Set::empty(), pre_degc: Map::empty(),
                        pre_gen: v14().gen, pre_nolock: false })
}
pub open spec fn v15d() -> AS2 { sete(v15(), 3, EP { ph: EPh::Deleted, del: out_in(v15().rows, 0), ..v15().e[3] }) }
pub open spec fn v16() -> AS2 { AS2 { gen: gen_step_graph(v15d().gen, 0), ..sete(v15d(), 3, EP { ph: EPh::Stepped, ..v15d().e[3] }) } }
pub open spec fn v17() -> AS2 {
    AS2 { out: out_minus(v16().out, 0), degc: degc_minus(v16().degc, 0), nolock: v16().nolock.remove(0),
          ..sete(v16(), 3, EP { ph: EPh::Killed, pre_out: out_in(v16().out, 0), pre_degc: degc_in(v16().degc, 0),
                                pre_nolock: v16().nolock.contains(0), ..v16().e[3] }) }
}
pub open spec fn v18() -> AS2 { AS2 { rows: v17().rows.difference(v17().e[3].del), e: v17().e.remove(3), ..v17() } }

pub proof fn witness_adj()
    ensures
        init2(v0()),
        step2(v0(), AL2::WLock { p: 1, x: x1(), kind: WKind::Put, got: true }, v1()),
        step2(v1(), AL2::WPre { p: 1 }, v2()),
        step2(v2(), AL2::WOut { p: 1 }, v3()),
        step2(v3(), AL2::WPost { p: 1 }, v4()),
        step2(v4(), AL2::WCommit { p: 1, x: x1(), add: true }, v5()),
        step2(v5(), AL2::RStart { p: 0, k: k0() }, v6()),
        step2(v6(), AL2::RLookup { p: 0, k: k0(), hit: None }, v7()),
        step2(v7(), AL2::RProbe { p: 0 }, v8()),
        step2(v8(), AL2::RCount { p: 0 }, v9()),
        step2(v9(), AL2::RCheck { p: 0 }, v10()),
        step2(v10(), AL2::RStore { p: 0 }, v11()),
        step2(v11(), AL2::RRecheck { p: 0 }, v12()),
        step2(v12(), AL2::RStart { p: 2, k: k0() }, v13()),
        step2(v13(), AL2::RLookup { p: 2, k: k0(), hit: Some((2nat, true)) }, v14()),
        lab04(AL2::RLookup { p: 2, k: k0(), hit: Some((2nat, true)) }) == Some(AL1::Hit { k: k0(), n: 2 }),
        deg(v13().rows, k0()) == 2,
        step2(v14(), AL2::ELock { q: 3, g: 0 }, v15()),
        step2(v15(), AL2::ERows { q: 3 }, v15d()),
        step2(v15d(), AL2::EStep { q: 3 }, v16()),
        step2(v16(), AL2::EKill { q: 3 }, v17()),
        step2(v17(), AL2::ECommit { q: 3, g: 0, del: s0().insert(x1()) }, v18()),
        !v18().degc.contains_key(k0()) && !v18().rows.contains(x0()),
{
    let f = of_src(k0());
    let s01 = s0().insert(x1());
    assert(s01.filter(f) =~= s01);
    assert(!s0().contains(x1()));
    assert(deg(s01, k0()) == 2);
    assert(step2(v0(), AL2::WLock { p: 1, x: x1(), kind: WKind::Put, got: true }, v1())) by {
        assert forall|p2: nat| !v0().w.contains_key(p2) by {}
        assert forall|q: nat| !v0().e.contains_key(q) by {}
    }
    assert(step2(v1(), AL2::WPre { p: 1 }, v2()));
    assert(step2(v2(), AL2::WOut { p: 1 }, v3()));
    assert(step2(v3(), AL2::WPost { p: 1 }, v4()));
    assert(step2(v4(), AL2::WCommit { p: 1, x: x1(), add: true }, v5()));
    assert((v5().gen)(k0()) == 2);
    assert(v5().w =~= Map::<nat, WP>::empty());
    assert(step2(v5(), AL2::RStart { p: 0, k: k0() }, v6()));
    assert(step2(v6(), AL2::RLookup { p: 0, k: k0(), hit: None }, v7()));
    assert(!held(v7(), 0)) by {
        assert forall|p: nat| !v7().w.contains_key(p) by {}
        assert forall|q: nat| !v7().e.contains_key(q) by {}
    }
    assert(step2(v7(), AL2::RProbe { p: 0 }, v8()));
    assert(v8().out == s01);
    assert(step2(v8(), AL2::RCount { p: 0 }, v9()));
    assert(step2(v9(), AL2::RCheck { p: 0 }, v10()));
    assert(step2(v10(), AL2::RStore { p: 0 }, v11()));
    assert(step2(v11(), AL2::RRecheck { p: 0 }, v12()));
    assert(v12().degc[k0()] == (2nat, 2nat));
    assert(step2(v12(), AL2::RStart { p: 2, k: k0() }, v13()));
    assert(step2(v13(), AL2::RLookup { p: 2, k: k0(), hit: Some((2nat, true)) }, v14()));
    assert(v14().r =~= Map::<nat, RP>::empty());
    assert(step2(v14(), AL2::ELock { q: 3, g: 0 }, v15())) by {
        assert forall|p: nat| !v14().w.contains_key(p) by {}
        assert forall|q: nat| !v14().e.contains_key(q) by {}
    }
    assert(step2(v15(), AL2::ERows { q: 3 }, v15d())) by {
        assert forall|p: nat| !v15().w.contains_key(p) by {}
    }
    assert(out_in(v15().rows, 0) =~= s01);
    assert(step2(v15d(), AL2::EStep { q: 3 }, v16()));
    assert(step2(v16(), AL2::EKill { q: 3 }, v17()));
    assert(v17().e[3].del == s01);
    assert(step2(v17(), AL2::ECommit { q: 3, g: 0, del: s01 }, v18()));
    assert(v18().rows =~= Set::<X>::empty());
}

// ---- witness_overlap: a writer and an eraser of graph 0 open together in the reviewed model

pub open spec fn u0() -> AS2 {
    AS2 { out: Set::empty(), gen: g0(), degc: Map::empty(), nolock: Set::empty(), w: Map::empty(), r: Map::empty(),
          e: Map::empty(), b: None, rows: Set::empty() }
}
pub open spec fn wlockless() -> WP { WP { x: x1(), kind: WKind::Put, got: false, ph: WPh::Locked, had: false } }
pub open spec fn u1() -> AS2 { AS2 { w: u0().w.insert(1, wlockless()), nolock: u0().nolock.insert(0), ..u0() } }
pub open spec fn u2() -> AS2 { AS2 { gen: gen_bump(u1().gen, k0()), ..setw(u1(), 1, WP { ph: WPh::Pre, ..u1().w[1] }) } }
pub open spec fn u3() -> AS2 {
    AS2 { out: u2().out.insert(x1()), ..setw(u2(), 1, WP { ph: WPh::Wrote, had: u2().out.contains(x1()), ..u2().w[1] }) }
}
pub open spec fn u4() -> AS2 { AS2 { gen: gen_bump(u3().gen, k0()), ..setw(u3(), 1, WP { ph: WPh::Post, ..u3().w[1] }) } }
pub open spec fn u5() -> AS2 {
    sete(u4(), 3, EP { g: 0, ph: EPh::Locked, del: Set::empty(), pre_out: Set::empty(), pre_degc: Map::empty(),
                       pre_gen: u4().gen, pre_nolock: false })
}
pub open spec fn u6() -> AS2 { AS2 { rows: u5().rows.insert(x1()), w: u5().w.remove(1), ..u5() } }
pub open spec fn u7() -> AS2 { sete(u6(), 3, EP { ph: EPh::Deleted, del: out_in(u6().rows, 0), ..u6().e[3] }) }
pub open spec fn u8() -> AS2 { AS2 { gen: gen_step_graph(u7().gen, 0), ..sete(u7(), 3, EP { ph: EPh::Stepped, ..u7().e[3] }) } }
pub open spec fn u9() -> AS2 {
    AS2 { out: out_minus(u8().out, 0), degc: degc_minus(u8().degc, 0), nolock: u8().nolock.remove(0),
          ..sete(u8(), 3, EP { ph: EPh::Killed, pre_out: out_in(u8().out, 0), pre_degc: degc_in(u8().degc, 0),
                               pre_nolock: u8().nolock.contains(0), ..u8().e[3] }) }
}
pub open spec fn u10() -> AS2 { AS2 { rows: u9().rows.difference(u9().e[3].del), e: u9().e.remove(3), ..u9() } }

pub proof fn witness_overlap()
    ensures
        init2(u0()),
        step2(u0(), AL2::WLock { p: 1, x: x1(), kind: WKind::Put, got: false }, u1()),
        step2(u1(), AL2::WPre { p: 1 }, u2()),
        step2(u2(), AL2::WOut { p: 1 }, u3()),
        step2(u3(), AL2::WPost { p: 1 }, u4()),
        step2(u4(), AL2::ELock { q: 3, g: 0 }, u5()),
        u5().w.contains_key(1) && u5().e.contains_key(3) && u5().w[1].x.0 == u5().e[3].g,
        step2(u5(), AL2::WCommit { p: 1, x: x1(), add: true }, u6()),
        step2(u6(), AL2::ERows { q: 3 }, u7()),
        u7().e[3].del == Set::<X>::empty().insert(x1()),
        step2(u7(), AL2::EStep { q: 3 }, u8()),
        step2(u8(), AL2::EKill { q: 3 }, u9()),
        step2(u9(), AL2::ECommit { q: 3, g: 0, del: Set::<X>::empty().insert(x1()) }, u10()),
        u10().rows == Set::<X>::empty() && u10().out == Set::<X>::empty() && !u10().nolock.contains(0),
{
    let sx1 = Set::<X>::empty().insert(x1());
    assert(step2(u0(), AL2::WLock { p: 1, x: x1(), kind: WKind::Put, got: false }, u1())) by {
        assert forall|p2: nat| !u0().w.contains_key(p2) by {}
        assert forall|q: nat| !u0().e.contains_key(q) by {}
    }
    assert(step2(u1(), AL2::WPre { p: 1 }, u2()));
    assert(step2(u2(), AL2::WOut { p: 1 }, u3()));
    assert(step2(u3(), AL2::WPost { p: 1 }, u4()));
    assert(step2(u4(), AL2::ELock { q: 3, g: 0 }, u5())) by {
        assert forall|q: nat| !u4().e.contains_key(q) by {}
        assert forall|p: nat| #[trigger] u4().w.contains_key(p) && u4().w[p].got implies u4().w[p].x.0 != 0 by {
            assert(p == 1);
        }
    }
    assert(step2(u5(), AL2::WCommit { p: 1, x: x1(), add: true }, u6()));
    assert(u6().w =~= Map::<nat, WP>::empty());
    assert(step2(u6(), AL2::ERows { q: 3 }, u7())) by {
        assert forall|p: nat| !u6().w.contains_key(p) by {}
    }
    assert(out_in(u6().rows, 0) =~= sx1);
    assert(step2(u7(), AL2::EStep { q: 3 }, u8()));
    assert(step2(u8(), AL2::EKill { q: 3 }, u9()));
    assert(step2(u9(), AL2::ECommit { q: 3, g: 0, del: sx1 }, u10()));
    assert(u10().rows =~= Set::<X>::empty());
    assert(u9().out =~= Set::<X>::empty());
    assert(u10().nolock =~= Set::<int>::empty());
}

} // verus!
