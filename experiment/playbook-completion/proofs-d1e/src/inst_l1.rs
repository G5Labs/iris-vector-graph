//! Module 01 (install / schema), L1: the namespace's IVG Schema binding (the deploy record), capability readiness,
//! the 4.0.0 upgrade and legacy removal, as a business contract.
//!
//! State: `unreadable` (environment: the engine's login cannot read the record, HD-0101; any value at init, no step
//! changes it), `bound` (the IVG Schema the namespace is bound to), `classes` (the ObjectScript layer is deployed:
//! readiness), `held` / `shaped` (schemas holding IVG tables, and those in the 4.0.0 shape), `views` / `lcls` (legacy
//! views and legacy shipped classes present; a class projects SqlProc items), `run` (a setup in progress: its schema
//! and whether one of its steps failed). Business rules:
//!
//! - **an engine is admitted only by the binding** (spec 262 FR-006/FR-006a, specs/262-ivg-owned-sql-schema/
//!   spec.md:243-245; INS-I3.4): accepted exactly when the namespace is bound to its schema; a record it cannot read
//!   is the separate, warned `Unchecked` outcome (HD-0101 working assumption);
//! - **setup of schema T never runs on a namespace bound to another schema, and the binding never changes**
//!   (FR-006: refused before any write; ADR-0016 docs/adr/0016-one-ivg-schema-per-namespace.md:10-12);
//! - **a quiet reply means every step succeeded** (docs/ADMIN_GUIDE.md:428: `warnings` lists what you must act on;
//!   INS-B1.12);
//! - **the binding is not readiness** (HD-0102 working assumption: the record is a namespace binding only; readiness
//!   is reported separately, and a feature call on a namespace without the classes is a named failure);
//! - **the upgrade follows the binding** (ADR-0016; FR-009: other schemas' tables are left untouched);
//! - **legacy removal says an object was removed only when it is gone** (specs/262-ivg-owned-sql-schema/
//!   data-model.md:50-60; INS-I7.6).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub enum Adm { Accepted, Unchecked, Refused }
pub enum Ready { Done, NotDeployed }
pub enum Obj { View(int), Item(int) }

pub struct Run1 { pub schema: int, pub failed: bool }

pub struct IS1 {
    pub unreadable: bool,
    pub bound: Option<int>,
    pub classes: bool,
    pub held: Set<int>,
    pub shaped: Set<int>,
    pub views: Set<int>,
    pub lcls: Set<int>,
    pub run: Option<Run1>,
}

pub enum IL1 {
    Begin { schema: int },
    Refuse { schema: int },
    Ddl { ok: bool },
    StepFailed,
    Deploy { ok: bool },
    Bind,
    Reply { warned: bool, ready: bool },
    Stop,
    Access { schema: int, adm: Adm },
    Feature { rdy: Ready },
    Upgrade,
    Remove { obj: Obj, reported: bool },
}

pub open spec fn access1(s: IS1, schema: int) -> Adm {
    if s.unreadable { Adm::Unchecked } else if s.bound == Some(schema) { Adm::Accepted } else { Adm::Refused }
}

pub open spec fn up1(s: IS1) -> Set<int> {
    if s.bound is Some && s.held.contains(s.bound->Some_0) { s.shaped.insert(s.bound->Some_0) } else { s.shaped }
}

pub open spec fn removed1(s: IS1, o: Obj) -> IS1 {
    match o { Obj::View(v) => IS1 { views: s.views.remove(v), ..s }, Obj::Item(c) => IS1 { lcls: s.lcls.remove(c), ..s } }
}

pub open spec fn gone1(s: IS1, o: Obj) -> bool {
    match o { Obj::View(v) => !s.views.contains(v), Obj::Item(c) => !s.lcls.contains(c) }
}

pub open spec fn next1(s: IS1, l: IL1, t: IS1) -> bool {
    match l {
        IL1::Begin { schema } => s.run is None && (s.bound is None || s.bound == Some(schema))
            && t == (IS1 { run: Some(Run1 { schema, failed: false }), ..s }),
        IL1::Refuse { schema } => s.bound is Some && s.bound->Some_0 != schema && t == s,
        IL1::Ddl { ok } => s.run is Some && t == (if ok {
                IS1 { held: s.held.insert(s.run->Some_0.schema), shaped: s.shaped.insert(s.run->Some_0.schema), ..s }
            } else { IS1 { run: Some(Run1 { failed: true, ..s.run->Some_0 }), ..s } }),
        IL1::StepFailed => s.run is Some && t == (IS1 { run: Some(Run1 { failed: true, ..s.run->Some_0 }), ..s }),
        IL1::Deploy { ok } => s.run is Some && t == (if ok { IS1 { classes: true, ..s } } else { s }),
        IL1::Bind => s.run is Some && t == (IS1 { bound: Some(s.run->Some_0.schema), ..s }),
        IL1::Reply { warned, ready } => s.run is Some && (s.run->Some_0.failed ==> warned) && ready == s.classes
            && t == (IS1 { run: None, ..s }),
        IL1::Stop => s.run is Some && t == (IS1 { run: None, ..s }),
        IL1::Access { schema, adm } => adm == access1(s, schema) && t == s,
        IL1::Feature { rdy } => rdy == (if s.classes { Ready::Done } else { Ready::NotDeployed }) && t == s,
        IL1::Upgrade => t == s || (s.bound is Some && t == (IS1 { shaped: up1(s), ..s })),
        IL1::Remove { obj, reported } => (t == s || t == removed1(s, obj)) && (reported ==> gone1(t, obj)),
    }
}

pub struct InstL1;

impl Contract for InstL1 {
    type S = IS1;
    type L = IL1;
    open spec fn init(s: IS1) -> bool { s.bound is None && !s.classes && s.run is None }
    open spec fn next(s: IS1, l: IL1, t: IS1) -> bool { next1(s, l, t) }
}

/// A setup in progress runs on an unbound namespace or on one bound to its own schema.
pub open spec fn inv1(s: IS1) -> bool {
    s.run is Some ==> (s.bound is None || s.bound == Some(s.run->Some_0.schema))
}

pub proof fn lemma_l1_safe(s: IS1, l: IL1, t: IS1)
    requires inv1(s), next1(s, l, t),
    ensures inv1(t),
{
}

impl SafeContract for InstL1 {
    open spec fn inv(s: IS1) -> bool { inv1(s) }
    proof fn init_safe(s: IS1) {}
    proof fn step_safe(s: IS1, l: IL1, t: IS1) { lemma_l1_safe(s, l, t); }
}

/// FR-006 / FR-006a (INS-I3.4): an engine is accepted only on a namespace bound to its schema whose record it reads.
pub proof fn theorem_admitted_only_by_binding(s: IS1, schema: int, adm: Adm, t: IS1)
    requires next1(s, IL1::Access { schema, adm }, t), adm is Accepted,
    ensures s.bound == Some(schema), !s.unreadable,
{
}

/// ADR-0016: once bound, a namespace's IVG Schema never changes.
pub proof fn theorem_binding_never_changes(s: IS1, l: IL1, t: IS1)
    requires inv1(s), next1(s, l, t), s.bound is Some,
    ensures t.bound == s.bound,
{
}

/// docs/ADMIN_GUIDE.md:428 (INS-B1.12): a reply with no warning comes from a setup none of whose steps failed.
pub proof fn theorem_quiet_reply_means_success(s: IS1, ready: bool, t: IS1)
    requires next1(s, IL1::Reply { warned: false, ready }, t),
    ensures !s.run->Some_0.failed, ready == s.classes,
{
}

/// HD-0102 (working assumption): readiness is not the binding; a feature call answers or names the missing layer.
pub proof fn theorem_readiness_is_named(s: IS1, rdy: Ready, t: IS1)
    requires next1(s, IL1::Feature { rdy }, t),
    ensures (rdy is Done) == s.classes, rdy is NotDeployed ==> !s.classes,
{
}

/// ADR-0016 / FR-009: the upgrade touches the bound schema's tables only.
pub proof fn theorem_upgrade_follows_binding(s: IS1, t: IS1, x: int)
    requires next1(s, IL1::Upgrade, t), s.bound != Some(x),
    ensures t.shaped.contains(x) == s.shaped.contains(x), t.held == s.held, t.bound == s.bound,
{
}

/// INS-I7.6: a reported removal is a removal.
pub proof fn theorem_removed_means_gone(s: IS1, obj: Obj, t: IS1)
    requires next1(s, IL1::Remove { obj, reported: true }, t),
    ensures gone1(t, obj),
{
}

} // verus!
