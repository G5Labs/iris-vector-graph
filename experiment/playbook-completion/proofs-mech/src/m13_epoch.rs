//! M-13 Read epoch: consistent multi-step read (AX-12), generic over `EpochPolicy` / `EpochObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/epoch.rs` (read at commit b0433157, working tree of
//! 2026-11-14) restated in Verus. It has no finiteness bound to drop (the writer runs one change, the reader one read).
//! A multi-step change of two parts (a redaction over two batches, or a writer's transaction over two tables) sets a
//! marker and moves the epoch when it starts (`Start`), changes part 1 then part 2, then clears the marker and moves
//! the epoch again (`Finish`); a reader reads part 1 and part 2 in two steps (record readers page by page,
//! save_snapshot table by table). The two parts are fields `p1`, `p2` (the explorer's `parts[0]`, `parts[1]`).
//! Instance parameter (`reader`): `NoCheck` (save_snapshot reads with no barrier, snapshot.py:864-1034, F-C1801),
//! `CheckStart` (record readers check the redaction marker before reading only, F-1402), `CheckStartEnd` (the working
//! answer of HD-1401: an epoch compared before and after; a change seen means the read reports itself interrupted).
//!
//! Law (MECHANISMS.md M-13): M13-L1 (invariant) a finished, uninterrupted read returns both parts from one state.
//! Obligation (trait proof function of `EpochObject`): L1 the reader checks the marker before reading and compares
//! the epoch and the marker after reading, reporting a change as an interrupted read.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum Reader { NoCheck, CheckStart, CheckStartEnd }

pub enum Rd { Idle, Begun(nat), Read1(nat, nat), Read2(nat, nat, nat), Done { consistent: bool, interrupted: bool } }

pub struct ES { pub wpc: nat, pub marker: bool, pub epoch: nat, pub p1: nat, pub p2: nat, pub r: Rd }

pub enum EA { Start, Change1, Change2, Finish, RBegin, RRead1, RRead2, REnd }

/// The instance parameter: the reader's barrier.
pub trait EpochPolicy: Sized {
    spec fn reader() -> Reader;
}

pub open spec fn epoch_s0() -> ES { ES { wpc: 0, marker: false, epoch: 0, p1: 0, p2: 0, r: Rd::Idle } }

pub open spec fn epoch_step<O: EpochPolicy>(s: ES, a: EA) -> Option<ES> {
    match a {
        EA::Start => if s.wpc == 0 { Some(ES { wpc: 1, marker: true, epoch: s.epoch + 1, ..s }) } else { None },
        EA::Change1 => if s.wpc == 1 { Some(ES { wpc: 2, p1: 1, ..s }) } else { None },
        EA::Change2 => if s.wpc == 2 { Some(ES { wpc: 3, p2: 1, ..s }) } else { None },
        EA::Finish => if s.wpc == 3 { Some(ES { wpc: 4, marker: false, epoch: s.epoch + 1, ..s }) } else { None },
        EA::RBegin => match s.r {
            Rd::Idle => if !(O::reader() is NoCheck) && s.marker {
                Some(ES { r: Rd::Done { consistent: true, interrupted: true }, ..s })
            } else {
                Some(ES { r: Rd::Begun(s.epoch), ..s })
            },
            _ => None,
        },
        EA::RRead1 => match s.r { Rd::Begun(e) => Some(ES { r: Rd::Read1(e, s.p1), ..s }), _ => None },
        EA::RRead2 => match s.r { Rd::Read1(e, v1) => Some(ES { r: Rd::Read2(e, v1, s.p2), ..s }), _ => None },
        EA::REnd => match s.r {
            Rd::Read2(e, v1, v2) => {
                let interrupted = O::reader() is CheckStartEnd && (s.epoch != e || s.marker);
                Some(ES { r: Rd::Done { consistent: v1 == v2, interrupted }, ..s })
            },
            _ => None,
        },
    }
}

pub struct EpochM<O> { pub o: O }

impl<O: EpochPolicy> Machine for EpochM<O> {
    type S = ES;
    type A = EA;
    open spec fn init(s: ES) -> bool { s == epoch_s0() }
    open spec fn step(s: ES, a: EA) -> Option<ES> { epoch_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ law

/// M13-L1 (invariant): no finished read is inconsistent without saying it was interrupted.
pub open spec fn law_l1(s: ES) -> bool {
    !(s.r == Rd::Done { consistent: false, interrupted: false })
}

// ------------------------------------------------------------------------------------------------ obligation

/// L1: the reader checks before and compares the epoch and marker after reading.
pub open spec fn obl_l1<O: EpochPolicy>() -> bool { O::reader() is CheckStartEnd }

pub trait EpochObject: EpochPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemma

/// The writer's phases: epoch 0 before the change, 1 while it runs (marker set), 2 after it.
pub open spec fn writer_phase(s: ES) -> bool {
    ||| s.wpc == 0 && !s.marker && s.epoch == 0 && s.p1 == 0 && s.p2 == 0
    ||| s.wpc == 1 && s.marker && s.epoch == 1 && s.p1 == 0 && s.p2 == 0
    ||| s.wpc == 2 && s.marker && s.epoch == 1 && s.p1 == 1 && s.p2 == 0
    ||| s.wpc == 3 && s.marker && s.epoch == 1 && s.p1 == 1 && s.p2 == 1
    ||| s.wpc == 4 && !s.marker && s.epoch == 2 && s.p1 == 1 && s.p2 == 1
}

/// A read that began with the marker off began at epoch 0 or 2; while the epoch is unchanged, every part it read
/// is that epoch's value.
pub open spec fn reader_ok(s: ES) -> bool {
    match s.r {
        Rd::Idle => true,
        Rd::Begun(e) => e == 0 || (e == 2 && s.epoch == 2),
        Rd::Read1(e, v1) => (e == 0 && (s.epoch == 0 ==> v1 == 0)) || (e == 2 && s.epoch == 2 && v1 == 1),
        Rd::Read2(e, v1, v2) => (e == 0 && (s.epoch == 0 ==> v1 == 0 && v2 == 0)) || (e == 2 && s.epoch == 2 && v1 == 1 && v2 == 1),
        Rd::Done { consistent, interrupted } => consistent || interrupted,
    }
}

pub open spec fn ind_l1(s: ES) -> bool { writer_phase(s) && reader_ok(s) }

pub proof fn lemma_l1_step<O: EpochPolicy>(s: ES, a: EA)
    requires obl_l1::<O>(), ind_l1(s), epoch_step::<O>(s, a) is Some,
    ensures ind_l1(epoch_step::<O>(s, a)->0),
{
}

pub proof fn theorem_l1<O: EpochPolicy>(s0: ES, ls: Seq<EA>, t: ES)
    requires obl_l1::<O>(), reached::<EpochM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    let inv = |s: ES| ind_l1(s);
    assert forall|x: ES, a: EA| inv(x) && (#[trigger] EpochM::<O>::step(x, a)) is Some implies inv(EpochM::<O>::step(x, a)->0) by {
        lemma_l1_step::<O>(x, a);
    }
    lemma_reached_inv::<EpochM<O>>(inv, s0, ls, t);
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_epoch<O: EpochObject>(s0: ES, ls: Seq<EA>, t: ES)
    requires reached::<EpochM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    O::discharge_l1();
    theorem_l1::<O>(s0, ls, t);
}

} // verus!
