//! M-10 Unit of work: all or none, inert refusal (AX-04, AX-03, AX-12), generic over `UnitPolicy` / `UnitObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/unit.rs` (read at commit b0433157) restated in Verus. It
//! has no finiteness bounds to drop (the unit runs once, pc 0..4). Two initial states, as in the explorer: the caller
//! has a transaction open with an earlier write `w` of its own, or not. The unit begins (a nested level when the
//! caller's transaction is open: Ledger.Commit, Ledger.cls:390-415; `_write_txn`), writes A, then writes B or fails.
//! The instance parameter is the object's configuration: commit mode (`Txn` one level; `PerStatement` each write
//! commits on its own; `NoTxn` A is written before or outside the transaction), refusal handling (`OwnLevel`
//! TROLLBACK 1; `AllLevels` the caller's transaction too; `NoRollback`) and reply (`Code`; `WrongClass` a refusal
//! outside the product's error family; `OkOnFailure`).
//!
//! Laws (MECHANISMS.md M-10): M10-L1 (invariant) a finished unit kept both writes or neither; M10-L2 (invariant) a
//! refused unit left the caller's earlier write; M10-L3 (invariant) a refused unit replied refused with a code of its
//! family, and an ok reply means both writes are kept.
//!
//! Obligations (one per law, on the configuration; each is a trait proof function of `UnitObject`):
//! L1 the unit's writes commit together in one level and a refusal rolls its own level back (commit = Txn, undo is a
//! rollback); L2 a refusal rolls back only its own level (undo != AllLevels); L3 a refusal replies with a code of the
//! product's family (reply = Code).
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum Commit { Txn, PerStatement, NoTxn }
pub enum Undo { OwnLevel, AllLevels, NoRollback }
pub enum Reply { Code, WrongClass, OkOnFailure }

pub struct UnitCfg { pub commit: Commit, pub undo: Undo, pub reply: Reply }

/// The reply: pending, ok, or refused (with a code of the product's family, or not).
pub enum UR { Pending, Ok, Refused(bool) }

pub struct US {
    pub caller_open: bool,
    pub w: bool,
    pub a: bool,
    pub a_committed: bool,
    pub b: bool,
    pub pc: nat,
    pub reply: UR,
}

pub enum UA { Begin, WriteA, WriteB, Fail, End }

/// The instance parameters: the object's configuration.
pub trait UnitPolicy: Sized {
    spec fn cfg() -> UnitCfg;
}

pub open spec fn canon() -> UnitCfg { UnitCfg { commit: Commit::Txn, undo: Undo::OwnLevel, reply: Reply::Code } }

/// The initial state with the caller's transaction open (and its earlier write made) or not.
pub open spec fn unit_s0(caller_open: bool) -> US {
    US { caller_open, w: caller_open, a: false, a_committed: false, b: false, pc: 0, reply: UR::Pending }
}

/// The mechanism's step, generic over the instance (explorer `Machine::next`).
pub open spec fn unit_step<O: UnitPolicy>(s: US, a: UA) -> Option<US> {
    let c = O::cfg();
    match a {
        UA::Begin => if s.pc == 0 { Some(US { pc: 1, ..s }) } else { None },
        UA::WriteA => if s.pc == 1 {
            Some(US { a: true, a_committed: c.commit is PerStatement || c.commit is NoTxn, pc: 2, ..s })
        } else { None },
        UA::WriteB => if s.pc == 2 { Some(US { b: true, pc: 3, ..s }) } else { None },
        UA::End => if s.pc == 3 { Some(US { pc: 4, reply: UR::Ok, ..s }) } else { None },
        UA::Fail => if s.pc == 2 {
            let a2 = match c.undo { Undo::OwnLevel | Undo::AllLevels => if !s.a_committed { false } else { s.a }, Undo::NoRollback => s.a };
            let w2 = match c.undo { Undo::AllLevels => false, _ => s.w };
            let r = match c.reply { Reply::Code => UR::Refused(true), Reply::WrongClass => UR::Refused(false), Reply::OkOnFailure => UR::Ok };
            Some(US { a: a2, w: w2, reply: r, pc: 4, ..s })
        } else { None },
    }
}

pub struct UnitM<O> { pub o: O }

impl<O: UnitPolicy> Machine for UnitM<O> {
    type S = US;
    type A = UA;
    open spec fn init(s: US) -> bool { s == unit_s0(true) || s == unit_s0(false) }
    open spec fn step(s: US, a: UA) -> Option<US> { unit_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M10-L1 (invariant): all or none.
pub open spec fn law_l1(s: US) -> bool { s.pc != 4 || s.a == s.b }

/// M10-L2 (invariant): a refusal leaves the caller's writes.
pub open spec fn law_l2(s: US) -> bool { s.pc != 4 || s.b || s.w == s.caller_open }

/// M10-L3 (invariant): the reply matches the outcome.
pub open spec fn law_l3(s: US) -> bool {
    s.pc != 4 || match s.reply { UR::Refused(code) => code && !s.b, UR::Ok => s.a && s.b, UR::Pending => false }
}

// ------------------------------------------------------------------------------------------------ obligations

pub open spec fn obl_l1<O: UnitPolicy>() -> bool { O::cfg().commit is Txn && !(O::cfg().undo is NoRollback) }
pub open spec fn obl_l2<O: UnitPolicy>() -> bool { !(O::cfg().undo is AllLevels) }
pub open spec fn obl_l3<O: UnitPolicy>() -> bool { O::cfg().reply is Code }

/// An object that uses the mechanism: its configuration and the obligations it discharges.
pub trait UnitObject: UnitPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

/// The unit's program shape (independent of the obligations): which writes exist at each program counter.
pub open spec fn shape<O: UnitPolicy>(s: US) -> bool {
    &&& s.pc <= 4
    &&& s.pc <= 1 ==> !s.a && !s.b && !s.a_committed && s.w == s.caller_open
    &&& s.pc == 2 ==> s.a && !s.b && s.a_committed == (O::cfg().commit is PerStatement || O::cfg().commit is NoTxn)
          && s.w == s.caller_open
    &&& s.pc == 3 ==> s.a && s.b && s.w == s.caller_open
    &&& (s.pc < 4) == (s.reply is Pending)
}

pub proof fn lemma_shape_step<O: UnitPolicy>(s: US, a: UA)
    requires shape::<O>(s), unit_step::<O>(s, a) is Some,
    ensures shape::<O>(unit_step::<O>(s, a)->0),
{
}

pub open spec fn ind_l1<O: UnitPolicy>(s: US) -> bool { shape::<O>(s) && law_l1(s) }
pub open spec fn ind_l2<O: UnitPolicy>(s: US) -> bool { shape::<O>(s) && s.w == s.caller_open }
pub open spec fn ind_l3<O: UnitPolicy>(s: US) -> bool { shape::<O>(s) && law_l3(s) }

pub proof fn lemma_l1_step<O: UnitPolicy>(s: US, a: UA)
    requires obl_l1::<O>(), ind_l1::<O>(s), unit_step::<O>(s, a) is Some,
    ensures ind_l1::<O>(unit_step::<O>(s, a)->0),
{
    lemma_shape_step::<O>(s, a);
}

pub proof fn lemma_l2_step<O: UnitPolicy>(s: US, a: UA)
    requires obl_l2::<O>(), ind_l2::<O>(s), unit_step::<O>(s, a) is Some,
    ensures ind_l2::<O>(unit_step::<O>(s, a)->0),
{
    lemma_shape_step::<O>(s, a);
}

pub proof fn lemma_l3_step<O: UnitPolicy>(s: US, a: UA)
    requires obl_l3::<O>(), ind_l3::<O>(s), unit_step::<O>(s, a) is Some,
    ensures ind_l3::<O>(unit_step::<O>(s, a)->0),
{
    lemma_shape_step::<O>(s, a);
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_l1<O: UnitPolicy>(s0: US, ls: Seq<UA>, t: US)
    requires obl_l1::<O>(), reached::<UnitM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    let inv = |s: US| ind_l1::<O>(s);
    assert forall|x: US, a: UA| inv(x) && (#[trigger] UnitM::<O>::step(x, a)) is Some implies inv(UnitM::<O>::step(x, a)->0) by {
        lemma_l1_step::<O>(x, a);
    }
    lemma_reached_inv::<UnitM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l2<O: UnitPolicy>(s0: US, ls: Seq<UA>, t: US)
    requires obl_l2::<O>(), reached::<UnitM<O>>(s0, ls, t),
    ensures law_l2(t),
{
    let inv = |s: US| ind_l2::<O>(s);
    assert forall|x: US, a: UA| inv(x) && (#[trigger] UnitM::<O>::step(x, a)) is Some implies inv(UnitM::<O>::step(x, a)->0) by {
        lemma_l2_step::<O>(x, a);
    }
    lemma_reached_inv::<UnitM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l3<O: UnitPolicy>(s0: US, ls: Seq<UA>, t: US)
    requires obl_l3::<O>(), reached::<UnitM<O>>(s0, ls, t),
    ensures law_l3(t),
{
    let inv = |s: US| ind_l3::<O>(s);
    assert forall|x: US, a: UA| inv(x) && (#[trigger] UnitM::<O>::step(x, a)) is Some implies inv(UnitM::<O>::step(x, a)->0) by {
        lemma_l3_step::<O>(x, a);
    }
    lemma_reached_inv::<UnitM<O>>(inv, s0, ls, t);
}

/// The mechanism's theorem, once for every object: every reached state satisfies the three laws.
pub proof fn theorem_unit<O: UnitObject>(s0: US, ls: Seq<UA>, t: US)
    requires reached::<UnitM<O>>(s0, ls, t),
    ensures law_l1(t), law_l2(t), law_l3(t),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    theorem_l1::<O>(s0, ls, t);
    theorem_l2::<O>(s0, ls, t);
    theorem_l3::<O>(s0, ls, t);
}

} // verus!
