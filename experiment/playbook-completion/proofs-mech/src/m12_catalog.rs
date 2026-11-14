//! M-12 Catalog binding of artifacts to graph and identity (AX-02, AX-01, AX-08), generic over `CatalogPolicy` /
//! `CatalogObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/catalog.rs` (read at commit b0433157, working tree of
//! 2026-11-14) restated in Verus without its bound (the explorer stops after 4 actions, `n >= 4`; the laws hold for
//! runs of any length, so the bound is dropped). Three (graph, identity) pairs 0 = (0,0), 1 = (1,0), 2 = (0,1); three
//! artifact slots named by the object's naming function; each artifact records the pair that created it and the
//! binding it recorded (none when the artifact records nothing); ghosts: a read or write used another pair's artifact
//! (`misused`), a create overwrote another pair's artifact (`clobbered`).
//! Instance parameters (`cfg`): naming `Full` (distinct pairs, distinct names: the registry row names the table,
//! VEC-I2.3) or `ShortHash` (pairs 0 and 2 share slot 0: two plan shapes with one 32-bit checksum, Gen.cls:69-80,
//! F-0901); `records` (the artifact records its binding; BM25Index.cls:608-612 records none, F-0705, and an
//! unrecorded artifact is read as pair 0's); `read_checked` (a read uses only an artifact bound to the asked pair;
//! F-0707, F-0609 read unchecked); `fail_open` (a write whose registry read fails goes through unchecked,
//! schema.py:1033-1061, F-0601).
//!
//! Laws (MECHANISMS.md M-12): M12-L1 (invariant) every artifact records its binding; M12-L2 (action) a read or write
//! uses only an artifact bound to its pair, and a failed check refuses; M12-L3 (invariant) no create overwrites
//! another pair's artifact.
//!
//! Obligations (one per law, on `cfg`; trait proof functions of `CatalogObject`): L1 every artifact records its
//! binding; L2 artifacts record their binding, reads check it, and a failed check refuses (never passes through);
//! L3 distinct pairs are given distinct names.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum Naming { Full, ShortHash }

pub struct CatCfg { pub naming: Naming, pub records: bool, pub read_checked: bool, pub fail_open: bool }

/// An artifact: the pair that created it and the binding it recorded.
pub struct Art { pub creator: nat, pub rec: Option<nat> }

pub struct CS { pub slots: Seq<Option<Art>>, pub misused: bool, pub clobbered: bool }

/// Create(pair); Read(pair, slot); Write(pair, slot, registry read fails).
pub enum CA { Create(nat), Read(nat, nat), Write(nat, nat, bool) }

/// The instance parameters.
pub trait CatalogPolicy: Sized {
    spec fn cfg() -> CatCfg;
}

pub open spec fn catalog_s0() -> CS {
    CS { slots: seq![None, None, None], misused: false, clobbered: false }
}

/// The slot an artifact for pair `p` is named into.
pub open spec fn slot_of(c: CatCfg, p: nat) -> nat {
    match c.naming { Naming::ShortHash => if p == 2 { 0 } else { p }, Naming::Full => p }
}

/// Whether an access by pair `p` to slot `k` proceeds, and whether it then uses another pair's artifact.
pub open spec fn access(c: CatCfg, s: CS, p: nat, k: nat, check_fails: bool) -> Option<(bool, bool)> {
    if k >= s.slots.len() || s.slots[k as int] is None { None }
    else {
        let art = s.slots[k as int]->0;
        // an artifact with no recorded binding is taken as pair 0's (the default graph's identity-0 artifact)
        let seen = match art.rec { Some(r) => r, None => 0 };
        let go = if check_fails { c.fail_open } else if c.read_checked { seen == p } else { true };
        Some((go, go && art.creator != p))
    }
}

pub open spec fn catalog_step<O: CatalogPolicy>(s: CS, a: CA) -> Option<CS> {
    let c = O::cfg();
    match a {
        CA::Create(p) => {
            if p >= 3 { None }
            else {
                let k = slot_of(c, p);
                let art = Art { creator: p, rec: if c.records { Some(p) } else { None } };
                if k >= s.slots.len() { None }
                else if s.slots[k as int] is Some && s.slots[k as int]->0.creator == p { None }
                else if s.slots[k as int] is Some { Some(CS { slots: s.slots.update(k as int, Some(art)), clobbered: true, ..s }) }
                else { Some(CS { slots: s.slots.update(k as int, Some(art)), ..s }) }
            }
        },
        CA::Read(p, k) => {
            if p >= 3 { None }
            else {
                match access(c, s, p, k, false) {
                    Some(r) => if r.1 { Some(CS { misused: true, ..s }) } else { Some(s) },
                    None => None,
                }
            }
        },
        CA::Write(p, k, fails) => {
            if p >= 3 { None }
            else {
                match access(c, s, p, k, fails) {
                    Some(r) => if r.1 { Some(CS { misused: true, ..s }) } else { Some(s) },
                    None => None,
                }
            }
        },
    }
}

pub struct CatalogM<O> { pub o: O }

impl<O: CatalogPolicy> Machine for CatalogM<O> {
    type S = CS;
    type A = CA;
    open spec fn init(s: CS) -> bool { s == catalog_s0() }
    open spec fn step(s: CS, a: CA) -> Option<CS> { catalog_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M12-L1 (invariant): every artifact records its binding.
pub open spec fn law_l1(s: CS) -> bool {
    forall|k: int| 0 <= k < s.slots.len() && (#[trigger] s.slots[k]) is Some ==> s.slots[k]->0.rec is Some
}

/// M12-L2 (action): no read or write uses another pair's artifact.
pub open spec fn law_l2(s: CS, t: CS) -> bool { t.misused == s.misused }

/// M12-L3 (invariant): no create overwrote another pair's artifact.
pub open spec fn law_l3(s: CS) -> bool { !s.clobbered }

// ------------------------------------------------------------------------------------------------ obligations

/// L1: every artifact records the binding it was built for.
pub open spec fn obl_l1<O: CatalogPolicy>() -> bool { O::cfg().records }
/// L2: artifacts record their binding, every read checks it, and a failed check refuses.
pub open spec fn obl_l2<O: CatalogPolicy>() -> bool { O::cfg().records && O::cfg().read_checked && !O::cfg().fail_open }
/// L3: distinct pairs get distinct names.
pub open spec fn obl_l3<O: CatalogPolicy>() -> bool { O::cfg().naming is Full }

pub trait CatalogObject: CatalogPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

pub open spec fn slots3(s: CS) -> bool { s.slots.len() == 3 }

pub open spec fn ind_l1(s: CS) -> bool { slots3(s) && law_l1(s) }

pub proof fn lemma_l1_step<O: CatalogPolicy>(s: CS, a: CA)
    requires obl_l1::<O>(), ind_l1(s), catalog_step::<O>(s, a) is Some,
    ensures ind_l1(catalog_step::<O>(s, a)->0),
{
    let t = catalog_step::<O>(s, a)->0;
    if let CA::Create(p) = a {
        let k = slot_of(O::cfg(), p);
        assert forall|j: int| 0 <= j < t.slots.len() && (#[trigger] t.slots[j]) is Some implies t.slots[j]->0.rec is Some by {
            if j != k { assert(t.slots[j] == s.slots[j]); }
        }
    }
}

/// Every artifact's recorded binding is its creator.
pub open spec fn rec_is_creator(s: CS) -> bool {
    forall|k: int| 0 <= k < s.slots.len() && (#[trigger] s.slots[k]) is Some ==> s.slots[k]->0.rec == Some(s.slots[k]->0.creator)
}

pub open spec fn ind_l2(s: CS) -> bool { slots3(s) && rec_is_creator(s) }

pub proof fn lemma_l2_step<O: CatalogPolicy>(s: CS, a: CA)
    requires obl_l2::<O>(), ind_l2(s), catalog_step::<O>(s, a) is Some,
    ensures ind_l2(catalog_step::<O>(s, a)->0), law_l2(s, catalog_step::<O>(s, a)->0),
{
    let t = catalog_step::<O>(s, a)->0;
    match a {
        CA::Create(p) => {
            let k = slot_of(O::cfg(), p);
            assert forall|j: int| 0 <= j < t.slots.len() && (#[trigger] t.slots[j]) is Some
                implies t.slots[j]->0.rec == Some(t.slots[j]->0.creator) by {
                if j != k { assert(t.slots[j] == s.slots[j]); }
            }
        },
        CA::Read(p, k) => { assert(s.slots[k as int]->0.rec == Some(s.slots[k as int]->0.creator)); },
        CA::Write(p, k, fails) => { assert(s.slots[k as int]->0.rec == Some(s.slots[k as int]->0.creator)); },
    }
}

/// Every artifact sits in its creator's own slot.
pub open spec fn in_own_slot(s: CS) -> bool {
    forall|k: int| 0 <= k < s.slots.len() && (#[trigger] s.slots[k]) is Some ==> s.slots[k]->0.creator == k
}

pub open spec fn ind_l3(s: CS) -> bool { slots3(s) && in_own_slot(s) && law_l3(s) }

pub proof fn lemma_l3_step<O: CatalogPolicy>(s: CS, a: CA)
    requires obl_l3::<O>(), ind_l3(s), catalog_step::<O>(s, a) is Some,
    ensures ind_l3(catalog_step::<O>(s, a)->0),
{
    let t = catalog_step::<O>(s, a)->0;
    if let CA::Create(p) = a {
        let k = slot_of(O::cfg(), p);
        assert(k == p);
        assert forall|j: int| 0 <= j < t.slots.len() && (#[trigger] t.slots[j]) is Some implies t.slots[j]->0.creator == j by {
            if j != k { assert(t.slots[j] == s.slots[j]); }
        }
    }
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_l1<O: CatalogPolicy>(s0: CS, ls: Seq<CA>, t: CS)
    requires obl_l1::<O>(), reached::<CatalogM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    let inv = |s: CS| ind_l1(s);
    assert forall|x: CS, a: CA| inv(x) && (#[trigger] CatalogM::<O>::step(x, a)) is Some implies inv(CatalogM::<O>::step(x, a)->0) by {
        lemma_l1_step::<O>(x, a);
    }
    lemma_reached_inv::<CatalogM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l2<O: CatalogPolicy>(s0: CS, ls: Seq<CA>, t: CS, a: CA)
    requires obl_l2::<O>(), reached::<CatalogM<O>>(s0, ls, t), catalog_step::<O>(t, a) is Some,
    ensures law_l2(t, catalog_step::<O>(t, a)->0),
{
    let inv = |s: CS| ind_l2(s);
    assert forall|x: CS, b: CA| inv(x) && (#[trigger] CatalogM::<O>::step(x, b)) is Some implies inv(CatalogM::<O>::step(x, b)->0) by {
        lemma_l2_step::<O>(x, b);
    }
    lemma_reached_inv::<CatalogM<O>>(inv, s0, ls, t);
    lemma_l2_step::<O>(t, a);
}

pub proof fn theorem_l3<O: CatalogPolicy>(s0: CS, ls: Seq<CA>, t: CS)
    requires obl_l3::<O>(), reached::<CatalogM<O>>(s0, ls, t),
    ensures law_l3(t),
{
    let inv = |s: CS| ind_l3(s);
    assert forall|x: CS, a: CA| inv(x) && (#[trigger] CatalogM::<O>::step(x, a)) is Some implies inv(CatalogM::<O>::step(x, a)->0) by {
        lemma_l3_step::<O>(x, a);
    }
    lemma_reached_inv::<CatalogM<O>>(inv, s0, ls, t);
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_catalog<O: CatalogObject>(s0: CS, ls: Seq<CA>, t: CS, a: CA)
    requires reached::<CatalogM<O>>(s0, ls, t),
    ensures
        law_l1(t),
        law_l3(t),
        catalog_step::<O>(t, a) is Some ==> law_l2(t, catalog_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    theorem_l1::<O>(s0, ls, t);
    theorem_l3::<O>(s0, ls, t);
    if catalog_step::<O>(t, a) is Some { theorem_l2::<O>(s0, ls, t, a); }
}

} // verus!
