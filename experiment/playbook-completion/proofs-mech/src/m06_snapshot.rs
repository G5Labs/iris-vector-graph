//! M-06 Snapshot save and restore (AX-12, AX-05, AX-10), generic over `SnapshotPolicy` / `SnapshotObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/snapshot.rs` (read at commit b0433157, working tree of
//! 2026-11-14) restated in Verus without its bounds (any number of writes, saves and restores; the explorer's counters
//! `n` are kept as unbounded ghost counters, used only by the sharpness witnesses): four live stores (0 rows, 1 routed
//! node vectors, 2 routed edge vectors, 3 temporal aggregates), the ledger head (a write of store 0 is a commit and
//! moves it), at most one archive (the values of the stores it carries, `None` for an uncarried store instead of the
//! explorer's byte 255, and the head it saw), the live state at the save (`saved`, ghost) and whether anything was
//! written since. Save copies the carried stores (snapshot.py:299-344, 960-1025). A replacing restore replaces the
//! live stores wholesale (uncarried stores end empty) and, as built, lays the archived head over the live one
//! (snapshot.py:1554-1588, F-1801). A merge restore combines rows and, as built, overwrites the temporal aggregates
//! (snapshot.py:1679, F-1805). The instance parameters: which stores the archive carries, the head policy of a
//! replacing restore, the aggregate policy of a merge restore.
//!
//! Laws (MECHANISMS.md M-06): M06-L1 (invariant) a replacing restore with nothing written since the save gives the
//! saved state on every store (`rt_ok`); M06-L2 (action) a restore never lowers the head; M06-L3 (action) a merge
//! restore that restores the aggregates adds the archived aggregates to the live ones (capped at 9 as in the explorer).
//!
//! Obligations (design rules, one per law): L1 the archive carries every store; L2 a replacing restore refuses when
//! the live head is ahead of the archive's; L3 a merge restore that carries the aggregates combines them.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum Head { Lays, Refuses }
pub enum Agg { Overwrite, Combine }

/// Four store values (0 rows, 1 routed node vectors, 2 routed edge vectors, 3 temporal aggregates).
pub struct V4 { pub r: nat, pub nv: nat, pub ev: nat, pub agg: nat }
/// An archive's copy of the four stores (`None`: not carried).
pub struct A4 { pub r: Option<nat>, pub nv: Option<nat>, pub ev: Option<nat>, pub agg: Option<nat> }

pub struct SS {
    pub live: V4,
    pub head: nat,
    pub archive: Option<(A4, nat)>,
    pub saved: V4,
    pub wrote_since: bool,
    pub rt_ok: bool,
    pub refused: nat,
    pub writes: nat,
    pub saves: nat,
    pub restores: nat,
}

pub enum SA { Write(nat), Save, RestoreReplace, RestoreMerge }

/// The instance parameters.
pub trait SnapshotPolicy: Sized {
    /// whether the archive carries store k (0..3)
    spec fn carried(k: nat) -> bool;
    spec fn head_policy() -> Head;
    spec fn agg_policy() -> Agg;
}

pub open spec fn snapshot_s0() -> SS {
    SS {
        live: V4 { r: 1, nv: 1, ev: 1, agg: 1 }, head: 1, archive: None, saved: V4 { r: 0, nv: 0, ev: 0, agg: 0 },
        wrote_since: false, rt_ok: true, refused: 0, writes: 0, saves: 0, restores: 0,
    }
}

pub open spec fn bump(x: nat) -> nat { ((x + 1) % 3) as nat }

pub open spec fn write_store(v: V4, k: nat) -> V4 {
    if k == 0 { V4 { r: bump(v.r), ..v } }
    else if k == 1 { V4 { nv: bump(v.nv), ..v } }
    else if k == 2 { V4 { ev: bump(v.ev), ..v } }
    else { V4 { agg: bump(v.agg), ..v } }
}

pub open spec fn keep_if(c: bool, x: nat) -> Option<nat> { if c { Some(x) } else { None } }

pub open spec fn archive_of<O: SnapshotPolicy>(v: V4) -> A4 {
    A4 { r: keep_if(O::carried(0), v.r), nv: keep_if(O::carried(1), v.nv), ev: keep_if(O::carried(2), v.ev),
         agg: keep_if(O::carried(3), v.agg) }
}

pub open spec fn or0(x: Option<nat>) -> nat { match x { Some(v) => v, None => 0 } }

pub open spec fn replaced(a: A4) -> V4 { V4 { r: or0(a.r), nv: or0(a.nv), ev: or0(a.ev), agg: or0(a.agg) } }

pub open spec fn maxn(a: nat, b: nat) -> nat { if a >= b { a } else { b } }
pub open spec fn minn(a: nat, b: nat) -> nat { if a <= b { a } else { b } }
pub open spec fn merge1(live: nat, a: Option<nat>) -> nat { match a { Some(x) => maxn(live, x), None => live } }
pub open spec fn merge_agg<O: SnapshotPolicy>(live: nat, a: Option<nat>) -> nat {
    match a {
        Some(x) => match O::agg_policy() { Agg::Overwrite => x, Agg::Combine => minn(live + x, 9) },
        None => live,
    }
}

/// The mechanism's step, generic over the instance (explorer `Machine::next`).
pub open spec fn snapshot_step<O: SnapshotPolicy>(s: SS, a: SA) -> Option<SS> {
    match a {
        SA::Write(k) => {
            if k > 3 { None }
            else {
                Some(SS { live: write_store(s.live, k), head: if k == 0 { s.head + 1 } else { s.head },
                          wrote_since: true, writes: s.writes + 1, ..s })
            }
        },
        SA::Save => Some(SS { archive: Some((archive_of::<O>(s.live), s.head)), saved: s.live, wrote_since: false,
                              saves: s.saves + 1, ..s }),
        SA::RestoreReplace => match s.archive {
            None => None,
            Some((arch, ah)) => {
                if O::head_policy() is Refuses && s.head > ah {
                    Some(SS { refused: s.refused + 1, restores: s.restores + 1, ..s })
                } else {
                    let live = replaced(arch);
                    Some(SS { live, head: if O::head_policy() is Lays { ah } else { s.head },
                              rt_ok: if !s.wrote_since { live == s.saved } else { s.rt_ok },
                              restores: s.restores + 1, ..s })
                }
            },
        },
        SA::RestoreMerge => match s.archive {
            None => None,
            Some((arch, _ah)) => Some(SS {
                live: V4 { r: merge1(s.live.r, arch.r), nv: merge1(s.live.nv, arch.nv), ev: merge1(s.live.ev, arch.ev),
                           agg: merge_agg::<O>(s.live.agg, arch.agg) },
                wrote_since: true, restores: s.restores + 1, ..s }),
        },
    }
}

pub struct SnapshotM<O> { pub o: O }

impl<O: SnapshotPolicy> Machine for SnapshotM<O> {
    type S = SS;
    type A = SA;
    open spec fn init(s: SS) -> bool { s == snapshot_s0() }
    open spec fn step(s: SS, a: SA) -> Option<SS> { snapshot_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M06-L1 (invariant): every replacing restore with nothing written since its save gave the saved state.
pub open spec fn law_l1(s: SS) -> bool { s.rt_ok }

/// M06-L2 (action): a restore never lowers the head.
pub open spec fn law_l2(s: SS, a: SA, t: SS) -> bool {
    !(a is RestoreReplace || a is RestoreMerge) || t.head >= s.head
}

/// M06-L3 (action): a merge restore that restores the aggregates adds them to the live ones.
pub open spec fn law_l3(s: SS, a: SA, t: SS) -> bool {
    match (a, s.archive) {
        (SA::RestoreMerge, Some((arch, _))) => arch.agg is Some ==> t.live.agg == minn(s.live.agg + arch.agg->0, 9),
        _ => true,
    }
}

// ------------------------------------------------------------------------------------------------ obligations

/// L1: the archive carries every store.
pub open spec fn obl_l1<O: SnapshotPolicy>() -> bool {
    O::carried(0) && O::carried(1) && O::carried(2) && O::carried(3)
}
/// L2: a replacing restore refuses when the live head is ahead of the archive's (never lays the archived head over it).
pub open spec fn obl_l2<O: SnapshotPolicy>() -> bool { O::head_policy() is Refuses }
/// L3: a merge restore that carries the aggregates combines them.
pub open spec fn obl_l3<O: SnapshotPolicy>() -> bool { O::agg_policy() is Combine || !O::carried(3) }

/// An object that uses the mechanism: its parameters and the obligations it discharges.
pub trait SnapshotObject: SnapshotPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

/// The inductive form of M06-L1: the archive holds exactly the saved state.
pub open spec fn ind_l1(s: SS) -> bool {
    &&& s.rt_ok
    &&& s.archive is Some ==> (s.archive->0).0 == (A4 { r: Some(s.saved.r), nv: Some(s.saved.nv), ev: Some(s.saved.ev), agg: Some(s.saved.agg) })
}

pub proof fn lemma_l1_step<O: SnapshotPolicy>(s: SS, a: SA)
    requires obl_l1::<O>(), ind_l1(s), snapshot_step::<O>(s, a) is Some,
    ensures ind_l1(snapshot_step::<O>(s, a)->0),
{
    let t = snapshot_step::<O>(s, a)->0;
    match a {
        SA::RestoreReplace => {
            let arch = (s.archive->0).0;
            assert(replaced(arch) == s.saved);
        },
        _ => {},
    }
}

pub proof fn lemma_l2_step<O: SnapshotPolicy>(s: SS, a: SA)
    requires obl_l2::<O>(), snapshot_step::<O>(s, a) is Some,
    ensures law_l2(s, a, snapshot_step::<O>(s, a)->0),
{
}

/// The archive carries the aggregates exactly when the policy carries them (needed by L3 when it does not).
pub open spec fn ind_carried<O: SnapshotPolicy>(s: SS) -> bool {
    s.archive is Some ==> ((s.archive->0).0.agg is Some <==> O::carried(3))
}

pub proof fn lemma_carried_step<O: SnapshotPolicy>(s: SS, a: SA)
    requires ind_carried::<O>(s), snapshot_step::<O>(s, a) is Some,
    ensures ind_carried::<O>(snapshot_step::<O>(s, a)->0),
{
}

pub proof fn lemma_l3_step<O: SnapshotPolicy>(s: SS, a: SA)
    requires obl_l3::<O>(), ind_carried::<O>(s), snapshot_step::<O>(s, a) is Some,
    ensures law_l3(s, a, snapshot_step::<O>(s, a)->0),
{
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_l1<O: SnapshotPolicy>(s0: SS, ls: Seq<SA>, t: SS)
    requires obl_l1::<O>(), reached::<SnapshotM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    let inv = |s: SS| ind_l1(s);
    assert forall|x: SS, a: SA| inv(x) && (#[trigger] SnapshotM::<O>::step(x, a)) is Some implies inv(SnapshotM::<O>::step(x, a)->0) by {
        lemma_l1_step::<O>(x, a);
    }
    lemma_reached_inv::<SnapshotM<O>>(inv, s0, ls, t);
}

/// Every step keeps M06-L2 when its obligation holds (no invariant needed).
pub proof fn theorem_l2<O: SnapshotPolicy>(s: SS, a: SA)
    requires obl_l2::<O>(), snapshot_step::<O>(s, a) is Some,
    ensures law_l2(s, a, snapshot_step::<O>(s, a)->0),
{
    lemma_l2_step::<O>(s, a);
}

/// Every step from a reached state keeps M06-L3 when its obligation holds.
pub proof fn theorem_l3<O: SnapshotPolicy>(s0: SS, ls: Seq<SA>, t: SS, a: SA)
    requires obl_l3::<O>(), reached::<SnapshotM<O>>(s0, ls, t), snapshot_step::<O>(t, a) is Some,
    ensures law_l3(t, a, snapshot_step::<O>(t, a)->0),
{
    let inv = |s: SS| ind_carried::<O>(s);
    assert forall|x: SS, b: SA| inv(x) && (#[trigger] SnapshotM::<O>::step(x, b)) is Some implies inv(SnapshotM::<O>::step(x, b)->0) by {
        lemma_carried_step::<O>(x, b);
    }
    lemma_reached_inv::<SnapshotM<O>>(inv, s0, ls, t);
    lemma_l3_step::<O>(t, a);
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_snapshot<O: SnapshotObject>(s0: SS, ls: Seq<SA>, t: SS, a: SA)
    requires reached::<SnapshotM<O>>(s0, ls, t),
    ensures
        law_l1(t),
        snapshot_step::<O>(t, a) is Some ==> law_l2(t, a, snapshot_step::<O>(t, a)->0) && law_l3(t, a, snapshot_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    theorem_l1::<O>(s0, ls, t);
    if snapshot_step::<O>(t, a) is Some {
        theorem_l2::<O>(t, a);
        theorem_l3::<O>(s0, ls, t, a);
    }
}

} // verus!
