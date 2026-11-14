//! M-01 Ledger commit with record (AX-05, AX-07, AX-04), generic over `LedgerPolicy` / `LedgerObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/ledger.rs` (read at commit b0433157) restated in Verus
//! without its bounds (any number of records, writes and values): one governed item's content (0 = absent), the
//! ledger's records for it (each the value it sets, 0 = a delete), the head, the strict flag, an engine's cached copy
//! of it (`Refresh` = the 5 s TTL of guard.py:20-59), the `unrecorded` flag (a write outside the ledger was allowed
//! while not strict), and `mid` (a two-step commit's pending record; controls only). The instance parameter is the
//! object's list of write paths (`paths`); the canonical commit is Ledger.Commit (Ledger.cls:397-528).
//!
//! Laws (MECHANISMS.md M-01): M01-L1 (action) records are a prefix-preserving append and the head never falls;
//! M01-L2 (invariant) no commit in flight => content = replay(records) or an allowed unrecorded write is flagged;
//! M01-L3 (action) a stale expected head changes nothing; M01-L4 (action) while strict, no bypass changes the content.
//!
//! Obligations (one per law, on the instance's paths; each is a trait proof function of `LedgerObject`):
//! L1 no path rewrites a record in place; L2 every path records exactly the changes it makes (no two-step record,
//! no record of an insert that collided, no record of a delete that removed nothing); L3 every commit path checks the
//! expected head; L4 every bypass path's guard reads the authoritative strict flag (the server's).
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum Guard { Server, CachedClient, NoGuard }

pub enum Path {
    Commit,
    InsertIfAbsent { record_on_collision: bool },
    DeleteAbsent { record_anyway: bool },
    Bypass(Guard),
    CommitTwoStep,
    CommitOverwrite,
    CommitIgnoreHead,
}

pub struct LS {
    pub content: nat,
    pub records: Seq<nat>,
    pub head: nat,
    pub strict: bool,
    pub cache: bool,
    pub unrecorded: bool,
    pub mid: Option<nat>,
    pub refusals: nat,
}

pub enum LA { Write(nat, nat), CommitStale(nat, nat), Finish, Stop, SetStrict(bool), Refresh }

/// The instance parameters: the object's write paths.
pub trait LedgerPolicy: Sized {
    spec fn paths() -> Seq<Path>;
}

pub open spec fn replay(r: Seq<nat>) -> nat {
    if r.len() == 0 { 0 } else { r.last() }
}

pub open spec fn ledger_s0() -> LS {
    LS { content: 0, records: Seq::empty(), head: 0, strict: false, cache: false, unrecorded: false, mid: None, refusals: 0 }
}

pub open spec fn guard_refuses(g: Guard, s: LS) -> bool {
    match g { Guard::Server => s.strict, Guard::CachedClient => s.cache, Guard::NoGuard => false }
}

pub open spec fn commit_v(s: LS, v: nat) -> LS {
    LS { content: v, records: s.records.push(v), head: s.head + 1, ..s }
}

/// The effect of one write through path `p` (explorer `A::Write`).
pub open spec fn write_path(p: Path, s: LS, v: nat) -> Option<LS> {
    match p {
        Path::Commit | Path::CommitIgnoreHead => if v == 0 && s.content == 0 { None } else { Some(commit_v(s, v)) },
        Path::CommitTwoStep => if v == 0 && s.content == 0 { None } else { Some(LS { content: v, mid: Some(v), ..s }) },
        Path::CommitOverwrite => {
            if v == 0 { None }
            else if s.records.len() == 0 { Some(commit_v(s, v)) }
            else { Some(LS { content: v, records: s.records.update(s.records.len() - 1, v), ..s }) }
        },
        Path::InsertIfAbsent { record_on_collision } => {
            if v == 0 { None }
            else if s.content == 0 { Some(commit_v(s, v)) }
            else if record_on_collision { Some(LS { records: s.records.push(v), head: s.head + 1, ..s }) }
            else { Some(s) }
        },
        Path::DeleteAbsent { record_anyway } => {
            // a delete aimed at another scope: the item stays; as built a graph-blind record is written anyway
            if v != 0 || s.content == 0 { None }
            else if record_anyway { Some(LS { records: s.records.push(0), head: s.head + 1, ..s }) }
            else { Some(s) }
        },
        Path::Bypass(g) => {
            if v == 0 && s.content == 0 { None }
            else if guard_refuses(g, s) { Some(LS { refusals: s.refusals + 1, ..s }) }
            else { Some(LS { content: v, unrecorded: true, ..s }) }
        },
    }
}

/// The mechanism's step, generic over the instance (explorer `Machine::next`).
pub open spec fn ledger_step<O: LedgerPolicy>(s: LS, a: LA) -> Option<LS> {
    match a {
        LA::SetStrict(b) => if s.strict == b || s.mid is Some { None } else { Some(LS { strict: b, ..s }) },
        LA::Refresh => if s.cache == s.strict { None } else { Some(LS { cache: s.strict, ..s }) },
        LA::Finish => match s.mid {
            Some(v) => Some(LS { records: s.records.push(v), head: s.head + 1, mid: None, ..s }),
            None => None,
        },
        LA::Stop => match s.mid { Some(_) => Some(LS { mid: None, ..s }), None => None },
        LA::CommitStale(i, v) => {
            if i >= O::paths().len() || s.mid is Some || s.head == 0 { None }
            else {
                match O::paths()[i as int] {
                    Path::CommitIgnoreHead => Some(commit_v(s, v)),
                    Path::Commit | Path::CommitTwoStep | Path::CommitOverwrite => Some(LS { refusals: s.refusals + 1, ..s }),
                    _ => None,
                }
            }
        },
        LA::Write(i, v) => {
            if i >= O::paths().len() || s.mid is Some { None } else { write_path(O::paths()[i as int], s, v) }
        },
    }
}

pub struct LedgerM<O> { pub o: O }

impl<O: LedgerPolicy> Machine for LedgerM<O> {
    type S = LS;
    type A = LA;
    open spec fn init(s: LS) -> bool { s == ledger_s0() }
    open spec fn step(s: LS, a: LA) -> Option<LS> { ledger_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M01-L1 (action): history only grows.
pub open spec fn law_l1(s: LS, t: LS) -> bool {
    t.records.len() >= s.records.len() && t.records.subrange(0, s.records.len() as int) == s.records && t.head >= s.head
}

/// M01-L2 (invariant): record and change together.
pub open spec fn law_l2(s: LS) -> bool {
    s.mid is Some || s.unrecorded || s.content == replay(s.records)
}

/// M01-L3 (action): a stale expected head changes nothing.
pub open spec fn law_l3(s: LS, a: LA, t: LS) -> bool {
    !(a is CommitStale) || (t.content == s.content && t.records == s.records)
}

/// M01-L4 (action): while strict, no bypass changes the content.
pub open spec fn law_l4<O: LedgerPolicy>(s: LS, a: LA, t: LS) -> bool {
    match a {
        LA::Write(i, _) => !(i < O::paths().len() && O::paths()[i as int] is Bypass) || !(s.strict && t.content != s.content),
        _ => true,
    }
}

// ------------------------------------------------------------------------------------------------ obligations

pub open spec fn path_appends(p: Path) -> bool { !(p is CommitOverwrite) }
pub open spec fn path_records_its_change(p: Path) -> bool {
    match p {
        Path::CommitTwoStep => false,
        Path::InsertIfAbsent { record_on_collision } => !record_on_collision,
        Path::DeleteAbsent { record_anyway } => !record_anyway,
        _ => true,
    }
}
pub open spec fn path_checks_head(p: Path) -> bool { !(p is CommitIgnoreHead) }
pub open spec fn path_guard_authoritative(p: Path) -> bool {
    match p { Path::Bypass(g) => g is Server, _ => true }
}

pub open spec fn obl_l1<O: LedgerPolicy>() -> bool {
    forall|i: int| 0 <= i < O::paths().len() ==> path_appends(#[trigger] O::paths()[i])
}
pub open spec fn obl_l2<O: LedgerPolicy>() -> bool {
    forall|i: int| 0 <= i < O::paths().len() ==> path_records_its_change(#[trigger] O::paths()[i])
}
pub open spec fn obl_l3<O: LedgerPolicy>() -> bool {
    forall|i: int| 0 <= i < O::paths().len() ==> path_checks_head(#[trigger] O::paths()[i])
}
pub open spec fn obl_l4<O: LedgerPolicy>() -> bool {
    forall|i: int| 0 <= i < O::paths().len() ==> path_guard_authoritative(#[trigger] O::paths()[i])
}

/// An object that uses the mechanism: its parameters and the obligations it discharges.
pub trait LedgerObject: LedgerPolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
    proof fn discharge_l4() ensures obl_l4::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

pub proof fn lemma_l1_step<O: LedgerPolicy>(s: LS, a: LA)
    requires obl_l1::<O>(), ledger_step::<O>(s, a) is Some,
    ensures law_l1(s, ledger_step::<O>(s, a)->0),
{
    let t = ledger_step::<O>(s, a)->0;
    if let LA::Write(i, v) = a {
        assert(path_appends(O::paths()[i as int]));
    }
    assert(t.records.subrange(0, s.records.len() as int) =~= s.records);
}

/// The inductive form of M01-L2 (no two-step commit is ever in flight).
pub open spec fn ind_l2(s: LS) -> bool { law_l2(s) && s.mid is None }

pub proof fn lemma_l2_step<O: LedgerPolicy>(s: LS, a: LA)
    requires obl_l2::<O>(), ind_l2(s), ledger_step::<O>(s, a) is Some,
    ensures ind_l2(ledger_step::<O>(s, a)->0),
{
    let t = ledger_step::<O>(s, a)->0;
    match a {
        LA::Write(i, v) => {
            let p = O::paths()[i as int];
            assert(path_records_its_change(p));
            match p {
                Path::CommitOverwrite => {
                    if s.records.len() > 0 { assert(t.records.last() == v); }
                },
                _ => {},
            }
        },
        _ => {},
    }
}

pub proof fn lemma_l3_step<O: LedgerPolicy>(s: LS, a: LA)
    requires obl_l3::<O>(), ledger_step::<O>(s, a) is Some,
    ensures law_l3(s, a, ledger_step::<O>(s, a)->0),
{
    if let LA::CommitStale(i, v) = a {
        assert(path_checks_head(O::paths()[i as int]));
    }
}

pub proof fn lemma_l4_step<O: LedgerPolicy>(s: LS, a: LA)
    requires obl_l4::<O>(), ledger_step::<O>(s, a) is Some,
    ensures law_l4::<O>(s, a, ledger_step::<O>(s, a)->0),
{
    if let LA::Write(i, v) = a {
        assert(path_guard_authoritative(O::paths()[i as int]));
    }
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_l2<O: LedgerPolicy>(s0: LS, ls: Seq<LA>, t: LS)
    requires obl_l2::<O>(), reached::<LedgerM<O>>(s0, ls, t),
    ensures law_l2(t),
{
    let inv = |s: LS| ind_l2(s);
    assert forall|x: LS, a: LA| inv(x) && (#[trigger] LedgerM::<O>::step(x, a)) is Some implies inv(LedgerM::<O>::step(x, a)->0) by {
        lemma_l2_step::<O>(x, a);
    }
    lemma_reached_inv::<LedgerM<O>>(inv, s0, ls, t);
}

/// Every step of every execution keeps the action laws whose obligations hold (L1, L3, L4 need no invariant).
pub proof fn theorem_action_laws<O: LedgerPolicy>(s: LS, a: LA)
    requires ledger_step::<O>(s, a) is Some,
    ensures
        obl_l1::<O>() ==> law_l1(s, ledger_step::<O>(s, a)->0),
        obl_l3::<O>() ==> law_l3(s, a, ledger_step::<O>(s, a)->0),
        obl_l4::<O>() ==> law_l4::<O>(s, a, ledger_step::<O>(s, a)->0),
{
    if obl_l1::<O>() { lemma_l1_step::<O>(s, a); }
    if obl_l3::<O>() { lemma_l3_step::<O>(s, a); }
    if obl_l4::<O>() { lemma_l4_step::<O>(s, a); }
}

/// The mechanism's theorem, once for every object: in every reached state the invariant law holds and every step
/// from it keeps the action laws.
pub proof fn theorem_ledger<O: LedgerObject>(s0: LS, ls: Seq<LA>, t: LS, a: LA)
    requires reached::<LedgerM<O>>(s0, ls, t),
    ensures
        law_l2(t),
        ledger_step::<O>(t, a) is Some ==> law_l1(t, ledger_step::<O>(t, a)->0)
            && law_l3(t, a, ledger_step::<O>(t, a)->0) && law_l4::<O>(t, a, ledger_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    O::discharge_l4();
    theorem_l2::<O>(s0, ls, t);
    if ledger_step::<O>(t, a) is Some { theorem_action_laws::<O>(t, a); }
}

} // verus!
