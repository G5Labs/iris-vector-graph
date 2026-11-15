//! M-05 Store inventory and removal (AX-10, AX-02, AX-04), generic over `RemovalPolicy` / `RemovalObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/removal.rs` (read at commit b0433157) restated with sets
//! of store ids instead of bitmasks (store k here is bit 2^k there) and without the bound on writes: for two targets
//! (0 the tenant being removed, 1 another tenant), the stores holding each target's content; per target erased? and
//! redacted?. A write path puts the target's content into the stores it reaches; erasure removes the target from the
//! stores in its inventory (Graph.KG.GraphStores, GraphStores.cls:26-133, and the eraser's own list); redaction
//! removes it from the history stores it reaches; the receipt names stores that keep content (spec 256 FR-008);
//! `cross` is a store in which removing one target also removes the other's content.
//!
//! Laws (MECHANISMS.md M-05): M05-L1 (invariant) after erasure and redaction of t, no store outside the receipt
//! holds t; M05-L2 (action) removing t leaves the other target's content; M05-L3 (invariant) every store holding
//! content is reached by erasure, redaction or the receipt (the inventory is complete).
//!
//! Obligations (design rules on the instance's store lists): L1 and L3 every store a write path reaches is in the
//! erasure inventory, the redaction's reach or the receipt (one rule serves both laws: in this machine they fail
//! together, as the explorer's `violates` lists show); L2 no store a write path reaches is shared across targets.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub struct RmCfg {
    pub paths: Seq<Set<nat>>,
    pub inventory: Set<nat>,
    pub redact: Set<nat>,
    pub receipt: Set<nat>,
    pub cross: Set<nat>,
}

pub struct RmS { pub content: Seq<Set<nat>>, pub erased: Seq<bool>, pub redacted: Seq<bool> }

pub enum RmA { Write(nat, nat), Erase(nat), Redact(nat) }

pub trait RemovalPolicy: Sized {
    spec fn cfg() -> RmCfg;
}

pub open spec fn removal_s0() -> RmS {
    RmS { content: seq![Set::empty(), Set::empty()], erased: seq![false, false], redacted: seq![false, false] }
}

pub open spec fn other(t: nat) -> nat { if t == 0 { 1 } else { 0 } }

pub open spec fn removal_step<O: RemovalPolicy>(s: RmS, a: RmA) -> Option<RmS> {
    let c = O::cfg();
    if s.content.len() != 2 || s.erased.len() != 2 || s.redacted.len() != 2 { None } else {
    match a {
        RmA::Write(t, p) => {
            if t >= 2 || p >= c.paths.len() || s.erased[t as int] || c.paths[p as int].subset_of(s.content[t as int]) { None }
            else { Some(RmS { content: s.content.update(t as int, s.content[t as int] + c.paths[p as int]), ..s }) }
        },
        RmA::Erase(t) => {
            if t >= 2 || s.erased[t as int] || s.content[t as int] == Set::<nat>::empty() { None }
            else {
                Some(RmS {
                    content: s.content.update(t as int, s.content[t as int] - c.inventory)
                                      .update(other(t) as int, s.content[other(t) as int] - c.cross),
                    erased: s.erased.update(t as int, true),
                    ..s
                })
            }
        },
        RmA::Redact(t) => {
            if t >= 2 || !s.erased[t as int] || s.redacted[t as int] { None }
            else {
                Some(RmS {
                    content: s.content.update(t as int, s.content[t as int] - c.redact)
                                      .update(other(t) as int, s.content[other(t) as int] - c.cross.intersect(c.redact)),
                    redacted: s.redacted.update(t as int, true),
                    ..s
                })
            }
        },
    }
    }
}

pub struct RemovalM<O> { pub o: O }

impl<O: RemovalPolicy> Machine for RemovalM<O> {
    type S = RmS;
    type A = RmA;
    open spec fn init(s: RmS) -> bool { s == removal_s0() }
    open spec fn step(s: RmS, a: RmA) -> Option<RmS> { removal_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M05-L1 (invariant): a redacted target's content is only in stores the receipt names.
pub open spec fn law_l1<O: RemovalPolicy>(s: RmS) -> bool {
    forall|t: int, x: nat| 0 <= t < 2 && s.redacted[t] && #[trigger] s.content[t].contains(x) ==> O::cfg().receipt.contains(x)
}

/// M05-L2 (action): removing t leaves the other target's content.
pub open spec fn law_l2(s: RmS, a: RmA, t: RmS) -> bool {
    match a {
        RmA::Erase(x) | RmA::Redact(x) => t.content[other(x) as int] == s.content[other(x) as int],
        _ => true,
    }
}

/// M05-L3 (invariant): every store that holds content is reached by erasure, redaction or the receipt.
pub open spec fn law_l3<O: RemovalPolicy>(s: RmS) -> bool {
    forall|t: int, x: nat| 0 <= t < 2 && #[trigger] s.content[t].contains(x) ==> reached_by_removal::<O>(x)
}

pub open spec fn reached_by_removal<O: RemovalPolicy>(x: nat) -> bool {
    O::cfg().inventory.contains(x) || O::cfg().redact.contains(x) || O::cfg().receipt.contains(x)
}

/// Store `x` is reached by some write path of the instance.
pub open spec fn written<O: RemovalPolicy>(x: nat) -> bool {
    exists|p: int| 0 <= p < O::cfg().paths.len() && #[trigger] O::cfg().paths[p].contains(x)
}

// ------------------------------------------------------------------------------------------------ obligations

pub open spec fn covered<O: RemovalPolicy>() -> bool {
    forall|p: int, x: nat| 0 <= p < O::cfg().paths.len() && #[trigger] O::cfg().paths[p].contains(x) ==> reached_by_removal::<O>(x)
}
pub open spec fn obl_l1<O: RemovalPolicy>() -> bool { covered::<O>() }
pub open spec fn obl_l2<O: RemovalPolicy>() -> bool {
    forall|p: int, x: nat| 0 <= p < O::cfg().paths.len() && #[trigger] O::cfg().paths[p].contains(x) ==> !O::cfg().cross.contains(x)
}
pub open spec fn obl_l3<O: RemovalPolicy>() -> bool { covered::<O>() }

pub trait RemovalObject: RemovalPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

/// Every policy: content comes only from write paths; an erased target holds nothing in the inventory and is never
/// written again; a redacted target was erased and holds nothing in the redaction's reach.
pub open spec fn inv_rm<O: RemovalPolicy>(s: RmS) -> bool {
    &&& s.content.len() == 2 && s.erased.len() == 2 && s.redacted.len() == 2
    &&& forall|t: int, x: nat| 0 <= t < 2 && #[trigger] s.content[t].contains(x) ==> written::<O>(x)
    &&& forall|t: int, x: nat| 0 <= t < 2 && s.erased[t] && #[trigger] s.content[t].contains(x) ==> !O::cfg().inventory.contains(x)
    &&& forall|t: int, x: nat| 0 <= t < 2 && s.redacted[t] && #[trigger] s.content[t].contains(x) ==> !O::cfg().redact.contains(x)
    &&& forall|t: int| 0 <= t < 2 && #[trigger] s.redacted[t] ==> s.erased[t]
}

pub proof fn lemma_inv_step<O: RemovalPolicy>(s: RmS, a: RmA)
    requires inv_rm::<O>(s), removal_step::<O>(s, a) is Some,
    ensures inv_rm::<O>(removal_step::<O>(s, a)->0),
{
    let c = O::cfg();
    let u = removal_step::<O>(s, a)->0;
    match a {
        RmA::Write(t, p) => {
            assert forall|i: int, x: nat| 0 <= i < 2 && #[trigger] u.content[i].contains(x) implies written::<O>(x) by {
                if i == t as int && c.paths[p as int].contains(x) { assert(c.paths[p as int].contains(x)); }
            }
        },
        RmA::Erase(t) => {},
        RmA::Redact(t) => {},
    }
}

pub proof fn lemma_l2_step<O: RemovalPolicy>(s: RmS, a: RmA)
    requires obl_l2::<O>(), inv_rm::<O>(s), removal_step::<O>(s, a) is Some,
    ensures law_l2(s, a, removal_step::<O>(s, a)->0),
{
    let c = O::cfg();
    let u = removal_step::<O>(s, a)->0;
    match a {
        RmA::Erase(t) => {
            let o = other(t) as int;
            assert forall|x: nat| s.content[o].contains(x) implies !c.cross.contains(x) by {
                assert(written::<O>(x));
                let p = choose|p: int| 0 <= p < c.paths.len() && #[trigger] c.paths[p].contains(x);
            }
            assert(u.content[o] =~= s.content[o]);
        },
        RmA::Redact(t) => {
            let o = other(t) as int;
            assert forall|x: nat| s.content[o].contains(x) implies !c.cross.contains(x) by {
                assert(written::<O>(x));
                let p = choose|p: int| 0 <= p < c.paths.len() && #[trigger] c.paths[p].contains(x);
            }
            assert(u.content[o] =~= s.content[o]);
        },
        _ => {},
    }
}

pub proof fn lemma_l1_of_inv<O: RemovalPolicy>(s: RmS)
    requires obl_l1::<O>(), inv_rm::<O>(s),
    ensures law_l1::<O>(s),
{
    assert forall|t: int, x: nat| 0 <= t < 2 && s.redacted[t] && #[trigger] s.content[t].contains(x) implies O::cfg().receipt.contains(x) by {
        assert(written::<O>(x));
        let p = choose|p: int| 0 <= p < O::cfg().paths.len() && #[trigger] O::cfg().paths[p].contains(x);
        assert(reached_by_removal::<O>(x));
    }
}

pub proof fn lemma_l3_of_inv<O: RemovalPolicy>(s: RmS)
    requires obl_l3::<O>(), inv_rm::<O>(s),
    ensures law_l3::<O>(s),
{
    assert forall|t: int, x: nat| 0 <= t < 2 && #[trigger] s.content[t].contains(x) implies reached_by_removal::<O>(x) by {
        assert(written::<O>(x));
        let p = choose|p: int| 0 <= p < O::cfg().paths.len() && #[trigger] O::cfg().paths[p].contains(x);
    }
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_inv<O: RemovalPolicy>(s0: RmS, ls: Seq<RmA>, t: RmS)
    requires reached::<RemovalM<O>>(s0, ls, t),
    ensures inv_rm::<O>(t),
{
    let inv = |s: RmS| inv_rm::<O>(s);
    assert forall|x: RmS, a: RmA| inv(x) && (#[trigger] RemovalM::<O>::step(x, a)) is Some implies inv(RemovalM::<O>::step(x, a)->0) by {
        lemma_inv_step::<O>(x, a);
    }
    assert(inv(removal_s0()));
    lemma_reached_inv::<RemovalM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l1<O: RemovalPolicy>(s0: RmS, ls: Seq<RmA>, t: RmS)
    requires obl_l1::<O>(), reached::<RemovalM<O>>(s0, ls, t),
    ensures law_l1::<O>(t),
{
    theorem_inv::<O>(s0, ls, t);
    lemma_l1_of_inv::<O>(t);
}

pub proof fn theorem_l2<O: RemovalPolicy>(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA)
    requires obl_l2::<O>(), reached::<RemovalM<O>>(s0, ls, t), removal_step::<O>(t, a) is Some,
    ensures law_l2(t, a, removal_step::<O>(t, a)->0),
{
    theorem_inv::<O>(s0, ls, t);
    lemma_l2_step::<O>(t, a);
}

pub proof fn theorem_l3<O: RemovalPolicy>(s0: RmS, ls: Seq<RmA>, t: RmS)
    requires obl_l3::<O>(), reached::<RemovalM<O>>(s0, ls, t),
    ensures law_l3::<O>(t),
{
    theorem_inv::<O>(s0, ls, t);
    lemma_l3_of_inv::<O>(t);
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_removal<O: RemovalObject>(s0: RmS, ls: Seq<RmA>, t: RmS, a: RmA)
    requires reached::<RemovalM<O>>(s0, ls, t),
    ensures
        law_l1::<O>(t),
        law_l3::<O>(t),
        removal_step::<O>(t, a) is Some ==> law_l2(t, a, removal_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    theorem_l1::<O>(s0, ls, t);
    theorem_l3::<O>(s0, ls, t);
    if removal_step::<O>(t, a) is Some { theorem_l2::<O>(s0, ls, t, a); }
}

} // verus!
