//! M-08 Install, settings and version gate (AX-09, AX-03), generic over `InstallPolicy` / `InstallObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/install.rs` (read at commit b0433157, working tree of
//! 2026-11-14) restated in Verus without its bounds (any number of setups, first uses and settings; any schema id and
//! any setting value instead of the explorer's 0/1 schemas and values 1..3): the namespace's recorded schema (none or
//! one schema id, Graph_KG being one of them), the set of schemas engines use, a foreign object that shares an
//! unqualified name with one of the product's, the effective value of one setting (0 job, 1 sync, 2 off; any value
//! above 2 is outside the domain), the ledger state, and processes that may enable the ledger for the first time at
//! once (each checks the state, then takes the head lock and creates the genesis revision, Ledger.cls:252-329; the
//! explorer's two processes are the initial `en` sequence). The instance parameters are the four as-built flags.
//!
//! Laws (MECHANISMS.md M-08): M08-L1 (invariant) at most one schema is recorded or used; M08-L2 (action) repeating
//! setup on a current install changes nothing and answers ok, and an enable on an enabled ledger answers ok;
//! M08-L3 (action) setup leaves foreign objects; M08-L4 (action) a setting outside its domain changes nothing.
//!
//! Obligations (design rules, one per law): L1 first use refuses a namespace with no schema record; L2 an enable that
//! finds the ledger enabled returns the genesis (no error for a lost first-enable race); L3 setup drops only qualified
//! names; L4 a setting value outside its domain is refused.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum En { Idle, Checked(bool), Done(bool) }

pub struct IS {
    pub recorded: Option<nat>,
    pub used: Set<nat>,
    pub foreign: bool,
    pub mode: nat,
    pub enabled: bool,
    pub en: Seq<En>,
    pub last_ok: bool,
}

pub enum IA { Setup(nat), FirstUse(nat), SetMode(nat), Check(nat), Create(nat) }

/// The instance parameters (the explorer's `Cfg`).
pub trait InstallPolicy: Sized {
    spec fn first_use_accepts_unrecorded() -> bool;
    spec fn drop_unqualified() -> bool;
    spec fn invalid_setting_accepted() -> bool;
    spec fn enable_race_errors() -> bool;
}

pub open spec fn install_s0() -> IS {
    IS { recorded: None, used: Set::empty(), foreign: true, mode: 0, enabled: false, en: seq![En::Idle, En::Idle], last_ok: true }
}

/// The largest value in the setting's domain (0 job, 1 sync, 2 off).
pub open spec fn mode_max() -> nat { 2 }

/// The mechanism's step, generic over the instance (explorer `Machine::next`).
pub open spec fn install_step<O: InstallPolicy>(s: IS, a: IA) -> Option<IS> {
    match a {
        IA::Setup(x) => match s.recorded {
            None => Some(IS { recorded: Some(x), used: s.used.insert(x),
                              foreign: if O::drop_unqualified() { false } else { s.foreign }, last_ok: true, ..s }),
            Some(r) => {
                if r == x { Some(IS { foreign: if O::drop_unqualified() { false } else { s.foreign }, last_ok: true, ..s }) }
                else { Some(IS { last_ok: false, ..s }) }
            },
        },
        IA::FirstUse(x) => match s.recorded {
            Some(r) => if r == x { Some(IS { used: s.used.insert(x), ..s }) } else { Some(s) },
            None => if O::first_use_accepts_unrecorded() { Some(IS { used: s.used.insert(x), ..s }) } else { Some(s) },
        },
        IA::SetMode(v) => {
            if v <= mode_max() { Some(IS { mode: v, ..s }) }
            else if O::invalid_setting_accepted() { Some(IS { mode: 1, ..s }) }
            else { Some(s) }
        },
        IA::Check(i) => {
            if i >= s.en.len() || !(s.en[i as int] is Idle) { None }
            else { Some(IS { en: s.en.update(i as int, En::Checked(!s.enabled)), ..s }) }
        },
        IA::Create(i) => {
            if i >= s.en.len() { None }
            else {
                match s.en[i as int] {
                    En::Checked(saw_never) => {
                        if !s.enabled { Some(IS { enabled: true, en: s.en.update(i as int, En::Done(true)), ..s }) }
                        else { Some(IS { en: s.en.update(i as int, En::Done(!(O::enable_race_errors() && saw_never))), ..s }) }
                    },
                    _ => None,
                }
            }
        },
    }
}

pub struct InstallM<O> { pub o: O }

impl<O: InstallPolicy> Machine for InstallM<O> {
    type S = IS;
    type A = IA;
    open spec fn init(s: IS) -> bool { s == install_s0() }
    open spec fn step(s: IS, a: IA) -> Option<IS> { install_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// A schema the namespace records or an engine uses.
pub open spec fn in_schemas(s: IS, x: nat) -> bool { s.used.contains(x) || s.recorded == Some(x) }

/// M08-L1 (invariant): at most one schema is recorded or used.
pub open spec fn law_l1(s: IS) -> bool {
    forall|x: nat, y: nat| in_schemas(s, x) && in_schemas(s, y) ==> x == y
}

/// M08-L2 (action): setup on a current install changes nothing and answers ok; an enable on an enabled ledger is ok.
pub open spec fn law_l2(s: IS, a: IA, t: IS) -> bool {
    match a {
        IA::Setup(x) => s.recorded == Some(x) ==> (t.recorded == s.recorded && t.used == s.used && t.last_ok),
        IA::Create(i) => s.enabled ==> (i < t.en.len() && t.en[i as int] == En::Done(true)),
        _ => true,
    }
}

/// M08-L3 (action): setup leaves foreign objects.
pub open spec fn law_l3(s: IS, a: IA, t: IS) -> bool { !(a is Setup) || t.foreign == s.foreign }

/// M08-L4 (action): a setting outside its domain changes nothing.
pub open spec fn law_l4(s: IS, a: IA, t: IS) -> bool {
    match a { IA::SetMode(v) => v > mode_max() ==> t.mode == s.mode, _ => true }
}

// ------------------------------------------------------------------------------------------------ obligations

/// L1: first use refuses a namespace with no schema record.
pub open spec fn obl_l1<O: InstallPolicy>() -> bool { !O::first_use_accepts_unrecorded() }
/// L2: an enable that finds the ledger enabled returns the genesis (a lost first-enable race is not an error).
pub open spec fn obl_l2<O: InstallPolicy>() -> bool { !O::enable_race_errors() }
/// L3: setup drops only names qualified with its own schema.
pub open spec fn obl_l3<O: InstallPolicy>() -> bool { !O::drop_unqualified() }
/// L4: a setting value outside its domain is refused.
pub open spec fn obl_l4<O: InstallPolicy>() -> bool { !O::invalid_setting_accepted() }

/// An object that uses the mechanism: its parameters and the obligations it discharges.
pub trait InstallObject: InstallPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
    proof fn discharge_l4() ensures obl_l4::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

/// The inductive form of M08-L1: every used schema is the recorded one.
pub open spec fn ind_l1(s: IS) -> bool {
    forall|x: nat| #[trigger] s.used.contains(x) ==> s.recorded == Some(x)
}

pub proof fn lemma_ind_l1_law(s: IS)
    requires ind_l1(s),
    ensures law_l1(s),
{
}

pub proof fn lemma_l1_step<O: InstallPolicy>(s: IS, a: IA)
    requires obl_l1::<O>(), ind_l1(s), install_step::<O>(s, a) is Some,
    ensures ind_l1(install_step::<O>(s, a)->0),
{
    let t = install_step::<O>(s, a)->0;
    match a {
        IA::Setup(x) => {
            if s.recorded is None {
                assert forall|y: nat| #[trigger] t.used.contains(y) implies t.recorded == Some(y) by {
                    if y != x { assert(s.used.contains(y)); }
                }
            }
        },
        IA::FirstUse(x) => {
            assert forall|y: nat| #[trigger] t.used.contains(y) implies t.recorded == Some(y) by {
                if y != x { assert(s.used.contains(y)); }
            }
        },
        _ => {},
    }
}

pub proof fn lemma_l2_step<O: InstallPolicy>(s: IS, a: IA)
    requires obl_l2::<O>(), install_step::<O>(s, a) is Some,
    ensures law_l2(s, a, install_step::<O>(s, a)->0),
{
}

pub proof fn lemma_l3_step<O: InstallPolicy>(s: IS, a: IA)
    requires obl_l3::<O>(), install_step::<O>(s, a) is Some,
    ensures law_l3(s, a, install_step::<O>(s, a)->0),
{
}

pub proof fn lemma_l4_step<O: InstallPolicy>(s: IS, a: IA)
    requires obl_l4::<O>(), install_step::<O>(s, a) is Some,
    ensures law_l4(s, a, install_step::<O>(s, a)->0),
{
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_l1<O: InstallPolicy>(s0: IS, ls: Seq<IA>, t: IS)
    requires obl_l1::<O>(), reached::<InstallM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    let inv = |s: IS| ind_l1(s);
    assert forall|x: IS, a: IA| inv(x) && (#[trigger] InstallM::<O>::step(x, a)) is Some implies inv(InstallM::<O>::step(x, a)->0) by {
        lemma_l1_step::<O>(x, a);
    }
    assert(inv(install_s0()));
    lemma_reached_inv::<InstallM<O>>(inv, s0, ls, t);
    lemma_ind_l1_law(t);
}

/// Every step keeps the action laws whose obligations hold (L2, L3, L4 need no invariant).
pub proof fn theorem_action_laws<O: InstallPolicy>(s: IS, a: IA)
    requires install_step::<O>(s, a) is Some,
    ensures
        obl_l2::<O>() ==> law_l2(s, a, install_step::<O>(s, a)->0),
        obl_l3::<O>() ==> law_l3(s, a, install_step::<O>(s, a)->0),
        obl_l4::<O>() ==> law_l4(s, a, install_step::<O>(s, a)->0),
{
    if obl_l2::<O>() { lemma_l2_step::<O>(s, a); }
    if obl_l3::<O>() { lemma_l3_step::<O>(s, a); }
    if obl_l4::<O>() { lemma_l4_step::<O>(s, a); }
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_install<O: InstallObject>(s0: IS, ls: Seq<IA>, t: IS, a: IA)
    requires reached::<InstallM<O>>(s0, ls, t),
    ensures
        law_l1(t),
        install_step::<O>(t, a) is Some ==> law_l2(t, a, install_step::<O>(t, a)->0)
            && law_l3(t, a, install_step::<O>(t, a)->0) && law_l4(t, a, install_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    O::discharge_l4();
    theorem_l1::<O>(s0, ls, t);
    if install_step::<O>(t, a) is Some { theorem_action_laws::<O>(t, a); }
}

} // verus!
