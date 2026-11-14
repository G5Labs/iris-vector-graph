//! M-11 Capability gate (AX-13, AX-03), generic over `CapPolicy` / `CapObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/cap.rs` (read at commit b0433157) restated in Verus
//! without its bound of two calls (the laws are action laws, so any number of calls). State: the store's value
//! (incremented mod 3 by a write, as in the explorer), whether a server file was read or written (or caller text
//! run as code), the number of calls, and whether a caller without a valid credential got an answer. A call names a
//! caller (credential `key`: 2 is the valid one, any other value none or wrong; role read-only or read-write) and a
//! route of the object's entry point. The instance parameter is the object's route list: each route has a kind
//! (`Read`, `Write`, `File`) and whether it checks the credential (key or privilege) and the read-only role before its
//! effect (docs/ADMIN_GUIDE.md:824-840; spec 253 FR-011).
//!
//! Laws (MECHANISMS.md M-11): M11-L1 (action) a read-only caller changes nothing; M11-L2 (action) with credentials
//! on, a caller without a valid credential is refused before any effect or answer; M11-L3 (action) no route touches
//! server files or runs caller text.
//!
//! Obligations (one per law, on the routes; each is a trait proof function of `CapObject`):
//! L1 every route that is not a read checks the read-only role; L2 every route checks the credential before its
//! effect; L3 no route has a server-file or code capability.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum Kind { Read, Write, File }

pub struct Route { pub kind: Kind, pub key_check: bool, pub ro_check: bool }

pub struct CS { pub store: nat, pub files: bool, pub calls: nat, pub unauth_answer: bool }

/// A call: the caller's credential (2 = valid), its read-only role, the route.
pub struct CA { pub key: nat, pub ro: bool, pub route: nat }

/// The instance parameters: the entry point's routes.
pub trait CapPolicy: Sized {
    spec fn routes() -> Seq<Route>;
}

pub open spec fn r_read() -> Route { Route { kind: Kind::Read, key_check: true, ro_check: true } }
pub open spec fn r_write() -> Route { Route { kind: Kind::Write, key_check: true, ro_check: true } }

pub open spec fn cap_s0() -> CS { CS { store: 0, files: false, calls: 0, unauth_answer: false } }

/// The mechanism's step, generic over the instance (explorer `Machine::next`, without the bound on calls).
pub open spec fn cap_step<O: CapPolicy>(s: CS, a: CA) -> Option<CS> {
    if a.route >= O::routes().len() { None }
    else {
        let r = O::routes()[a.route as int];
        let u = CS { calls: s.calls + 1, ..s };
        if r.key_check && a.key != 2 { Some(u) }
        else if r.ro_check && a.ro && !(r.kind is Read) { Some(u) }
        else {
            let v = if a.key != 2 { CS { unauth_answer: true, ..u } } else { u };
            match r.kind {
                Kind::Read => Some(v),
                Kind::Write => Some(CS { store: (s.store + 1) % 3, ..v }),
                Kind::File => Some(CS { files: true, ..v }),
            }
        }
    }
}

pub struct CapM<O> { pub o: O }

impl<O: CapPolicy> Machine for CapM<O> {
    type S = CS;
    type A = CA;
    open spec fn init(s: CS) -> bool { s == cap_s0() }
    open spec fn step(s: CS, a: CA) -> Option<CS> { cap_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M11-L1 (action): a read-only caller changes nothing.
pub open spec fn law_l1(s: CS, a: CA, t: CS) -> bool { !a.ro || (t.store == s.store && t.files == s.files) }

/// M11-L2 (action): no valid credential, no effect and no answer.
pub open spec fn law_l2(s: CS, a: CA, t: CS) -> bool {
    a.key == 2 || (t.store == s.store && t.files == s.files && t.unauth_answer == s.unauth_answer)
}

/// M11-L3 (action): no server-file or code capability.
pub open spec fn law_l3(s: CS, a: CA, t: CS) -> bool { t.files == s.files }

// ------------------------------------------------------------------------------------------------ obligations

pub open spec fn route_checks_role(r: Route) -> bool { r.kind is Read || r.ro_check }
pub open spec fn route_checks_credential(r: Route) -> bool { r.key_check }
pub open spec fn route_no_file(r: Route) -> bool { !(r.kind is File) }

pub open spec fn obl_l1<O: CapPolicy>() -> bool {
    forall|i: int| 0 <= i < O::routes().len() ==> route_checks_role(#[trigger] O::routes()[i])
}
pub open spec fn obl_l2<O: CapPolicy>() -> bool {
    forall|i: int| 0 <= i < O::routes().len() ==> route_checks_credential(#[trigger] O::routes()[i])
}
pub open spec fn obl_l3<O: CapPolicy>() -> bool {
    forall|i: int| 0 <= i < O::routes().len() ==> route_no_file(#[trigger] O::routes()[i])
}

/// An object that uses the mechanism: its routes and the obligations it discharges.
pub trait CapObject: CapPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

pub proof fn lemma_l1_step<O: CapPolicy>(s: CS, a: CA)
    requires obl_l1::<O>(), cap_step::<O>(s, a) is Some,
    ensures law_l1(s, a, cap_step::<O>(s, a)->0),
{
    assert(route_checks_role(O::routes()[a.route as int]));
}

pub proof fn lemma_l2_step<O: CapPolicy>(s: CS, a: CA)
    requires obl_l2::<O>(), cap_step::<O>(s, a) is Some,
    ensures law_l2(s, a, cap_step::<O>(s, a)->0),
{
    assert(route_checks_credential(O::routes()[a.route as int]));
}

pub proof fn lemma_l3_step<O: CapPolicy>(s: CS, a: CA)
    requires obl_l3::<O>(), cap_step::<O>(s, a) is Some,
    ensures law_l3(s, a, cap_step::<O>(s, a)->0),
{
    assert(route_no_file(O::routes()[a.route as int]));
}

// ------------------------------------------------------------------------------------------------ theorems

/// Every step of every execution keeps the action laws whose obligations hold (no invariant is needed).
pub proof fn theorem_action_laws<O: CapPolicy>(s: CS, a: CA)
    requires cap_step::<O>(s, a) is Some,
    ensures
        obl_l1::<O>() ==> law_l1(s, a, cap_step::<O>(s, a)->0),
        obl_l2::<O>() ==> law_l2(s, a, cap_step::<O>(s, a)->0),
        obl_l3::<O>() ==> law_l3(s, a, cap_step::<O>(s, a)->0),
{
    if obl_l1::<O>() { lemma_l1_step::<O>(s, a); }
    if obl_l2::<O>() { lemma_l2_step::<O>(s, a); }
    if obl_l3::<O>() { lemma_l3_step::<O>(s, a); }
}

/// The mechanism's theorem, once for every object: every step from every reached state keeps the three laws.
pub proof fn theorem_cap<O: CapObject>(s0: CS, ls: Seq<CA>, t: CS, a: CA)
    requires reached::<CapM<O>>(s0, ls, t),
    ensures
        cap_step::<O>(t, a) is Some ==> law_l1(t, a, cap_step::<O>(t, a)->0) && law_l2(t, a, cap_step::<O>(t, a)->0)
            && law_l3(t, a, cap_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    if cap_step::<O>(t, a) is Some { theorem_action_laws::<O>(t, a); }
}

} // verus!
