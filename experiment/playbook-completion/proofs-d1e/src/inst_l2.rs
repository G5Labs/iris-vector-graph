//! Module 01, L2: setup, the schema record, the first-access check, the 4.0.0 upgrade and legacy removal over the
//! stored layout at pin 3eaa79cf; refinement of `inst_l1` for every step, the invariant, and controls F-0103,
//! F-0102, F-0109 and F-0101.
//!
//! Layout: `rec` = ^IVG.Deploy("schema") (write_record, iris_vector_graph/schema_name.py:194-198); `tables` the
//! schemas holding the base tables (the base DDL, iris_vector_graph/_engine/schema.py:2440-2512), `shaped` those in
//! the 4.0.0 shape; `funcs` the schemas holding IVG's SQL functions, among them the class `<package>.funcCYCMP` that
//! check_first_access probes in ^oddDEF (schema_name.py:203-209, 233-235); `cls` the Graph.KG classes compiled
//! (deploy_objectscript_classes, _engine/schema.py:2578-2594); `kg` the ^KG bootstrap (:2674-2681); `views`/`lcls`
//! the legacy views and shipped classes present, `done` remove_legacy_objects' classes_done with each class delete's
//! result (_engine/legacy.py:654-686); `run` a setup in progress with its ghost `failed` and its reply's `warnings`.
//!
//! Setup (`initialize_schema` -> `_record_and_initialize` -> `_initialize_schema`): `Begin` reads the record and
//! refuses another schema's (`Refuse`, _engine/schema.py:2224-2226); `Ddl` the base tables; `Funcs` the IVG Schema's
//! SQL functions (the marker); `Deploy` the classes (R299: a deploy that raises is in the reply's warnings,
//! :2591-2593; auto_deploy_objectscript=False skips it); `Kg` the ^KG bootstrap; `Record` write_record when none is
//! recorded (:2309-2312); `Reply`. The process can stop between any two steps (`Stop`). `Access` is an engine's first
//! access (engine.py:1847-1868 -> check_first_access, schema_name.py:220-235); `Feature` a call needing the classes;
//! `Upgrade` upgrade_to_4_0_0 (migrations/upgrade.py:130-200); `RmView`/`RmFirst`/`RmLater` the removal of a legacy
//! view, of the first item of a shipped class (the class delete) and of a later item of that class.
//!
//! **Reviewed design** (the findings' remedies and the working answers): with no record the first access refuses
//! whatever the marker says (F-0103 remedy; setup is exempt); every passed-over failure is put in `warnings`
//! (F-0102 remedy); the upgrade reads the record and refuses a schema other than the bound one (F-0109 remedy);
//! `removed` comes from the drop's or the class delete's result (F-0101 remedy); the record is a binding only and a
//! feature call on a namespace without the classes is a named failure (HD-0102); an unreadable record is the warned
//! `Unchecked` outcome (HD-0101, as built).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::inst_l1::*;

verus! {

pub enum Ph { Ddl, Funcs, Deploy, Kg, Record, Replied }
pub struct Run2 { pub schema: int, pub failed: bool, pub warnings: bool, pub ph: Ph }

pub struct IS2 {
    pub unreadable: bool,
    pub rec: Option<int>,
    pub tables: Set<int>,
    pub shaped: Set<int>,
    pub funcs: Set<int>,
    pub cls: bool,
    pub kg: bool,
    pub views: Set<int>,
    pub lcls: Set<int>,
    pub done: Map<int, bool>,
    pub run: Option<Run2>,
}

pub enum IL2 {
    Begin { schema: int },
    Refuse { schema: int },
    Ddl { ok: bool },
    Funcs,
    Deploy { on: bool, ok: bool },
    Kg { ok: bool },
    Record,
    Reply { warned: bool, ready: bool },
    Stop,
    Access { schema: int, adm: Adm },
    Feature { rdy: Ready },
    Upgrade { arg: int },
    RmView { v: int, ok: bool, reported: bool },
    RmFirst { c: int, ok: bool, reported: bool },
    RmLater { c: int, reported: bool },
}

pub open spec fn f0103() -> bool { cfg!(feature = "control_f0103_marker_admits") }
pub open spec fn f0102() -> bool { cfg!(feature = "control_f0102_failure_only_logged") }
pub open spec fn f0109() -> bool { cfg!(feature = "control_f0109_upgrade_default_schema") }
pub open spec fn f0101() -> bool { cfg!(feature = "control_f0101_removed_unchecked") }

pub open spec fn at(s: IS2, p: Ph) -> bool { s.run is Some && s.run->Some_0.ph == p }
pub open spec fn adv(s: IS2, p: Ph) -> Option<Run2> { Some(Run2 { ph: p, ..s.run->Some_0 }) }

/// check_first_access (schema_name.py:220-235) as the engine runs it (engine.py:1847-1868).
pub open spec fn access2(s: IS2, schema: int) -> Adm {
    if s.unreadable { Adm::Unchecked }                       // engine.py:1863-1867: logged at WARNING, not checked
    else if s.rec is Some { if s.rec == Some(schema) { Adm::Accepted } else { Adm::Refused } }   // FR-006
    else if f0103() && s.funcs.contains(schema) { Adm::Accepted }   // as built: the marker class admits (F-0103)
    else { Adm::Refused }                                     // FR-006a
}

/// upgrade_to_4_0_0's placements over `schema=` (default DEFAULT_SCHEMA "Graph_KG", upgrade.py:58, :140).
pub open spec fn up2(s: IS2, arg: int) -> Set<int> {
    if f0109() { if s.tables.contains(arg) { s.shaped.insert(arg) } else { s.shaped } }   // as built: never reads the record
    else if s.rec == Some(arg) && s.tables.contains(arg) { s.shaped.insert(arg) } else { s.shaped }
}

pub open spec fn step2(s: IS2, l: IL2, t: IS2) -> bool {
    match l {
        IL2::Begin { schema } => s.run is None && (s.rec is None || s.rec == Some(schema))
            && t == (IS2 { run: Some(Run2 { schema, failed: false, warnings: false, ph: Ph::Ddl }), ..s }),
        IL2::Refuse { schema } => s.rec is Some && s.rec->Some_0 != schema && t == s,
        IL2::Ddl { ok } => at(s, Ph::Ddl) && t == (if ok {
                IS2 { tables: s.tables.insert(s.run->Some_0.schema), shaped: s.shaped.insert(s.run->Some_0.schema),
                      run: adv(s, Ph::Funcs), ..s }
            } else {
                // a statement failing for a reason other than "exists" or a privilege: as built a WARNING log line
                // only (_engine/schema.py:2508-2511), reviewed also in the reply's warnings
                IS2 { run: Some(Run2 { failed: true, warnings: s.run->Some_0.warnings || !f0102(), ph: Ph::Funcs,
                                       ..s.run->Some_0 }), ..s }
            }),
        IL2::Funcs => at(s, Ph::Funcs)
            && t == (IS2 { funcs: s.funcs.insert(s.run->Some_0.schema), run: adv(s, Ph::Deploy), ..s }),
        IL2::Deploy { on, ok } => at(s, Ph::Deploy)
            && t == (IS2 { cls: s.cls || (on && ok),
                           run: Some(Run2 { warnings: s.run->Some_0.warnings || (on && !ok), ph: Ph::Kg, ..s.run->Some_0 }),
                           ..s }),
        IL2::Kg { ok } => at(s, Ph::Kg) && (!ok ==> s.cls && !s.kg) && t == (if ok {
                IS2 { kg: s.kg || s.cls, run: adv(s, Ph::Record), ..s }
            } else {
                // as built a log line only (_engine/schema.py:2680-2681)
                IS2 { run: Some(Run2 { failed: true, warnings: s.run->Some_0.warnings || !f0102(), ph: Ph::Record,
                                       ..s.run->Some_0 }), ..s }
            }),
        IL2::Record => at(s, Ph::Record)
            && t == (IS2 { rec: if s.rec is None { Some(s.run->Some_0.schema) } else { s.rec }, run: adv(s, Ph::Replied), ..s }),
        IL2::Reply { warned, ready } => at(s, Ph::Replied) && warned == s.run->Some_0.warnings && ready == s.cls
            && t == (IS2 { run: None, ..s }),
        IL2::Stop => s.run is Some && t == (IS2 { run: None, ..s }),
        IL2::Access { schema, adm } => adm == access2(s, schema) && t == s,
        IL2::Feature { rdy } => rdy == (if s.cls { Ready::Done } else { Ready::NotDeployed }) && t == s,
        IL2::Upgrade { arg } => t == (IS2 { shaped: up2(s, arg), ..s }),
        IL2::RmView { v, ok, reported } => s.views.contains(v)
            && t == (IS2 { views: if ok { s.views.remove(v) } else { s.views }, ..s })
            && reported == (if f0101() { true } else { ok }),     // as built: removed = True after DROP VIEW (legacy.py:670-672)
        IL2::RmFirst { c, ok, reported } => s.lcls.contains(c) && !s.done.contains_key(c)
            && t == (IS2 { lcls: if ok { s.lcls.remove(c) } else { s.lcls }, done: s.done.insert(c, ok), ..s })
            && reported == ok,                                      // legacy.py:680-682
        IL2::RmLater { c, reported } => s.done.contains_key(c) && t == s
            && reported == (if f0101() { true } else { s.done[c] }),   // as built: removed = True (legacy.py:683-684)
    }
}

pub open spec fn init2(s: IS2) -> bool {
    s.rec is None && s.funcs == Set::<int>::empty() && !s.cls && !s.kg && s.done == Map::<int, bool>::empty() && s.run is None
}

pub open spec fn absi(s: IS2) -> IS1 {
    IS1 { unreadable: s.unreadable, bound: s.rec, classes: s.cls, held: s.tables, shaped: s.shaped, views: s.views,
          lcls: s.lcls,
          run: match s.run { None => None, Some(r) => Some(Run1 { schema: r.schema, failed: r.failed }) } }
}

pub open spec fn labi(l: IL2) -> Option<IL1> {
    match l {
        IL2::Begin { schema } => Some(IL1::Begin { schema }),
        IL2::Refuse { schema } => Some(IL1::Refuse { schema }),
        IL2::Ddl { ok } => Some(IL1::Ddl { ok }),
        IL2::Funcs => None,
        IL2::Deploy { on, ok } => Some(IL1::Deploy { ok: on && ok }),
        IL2::Kg { ok } => if ok { None } else { Some(IL1::StepFailed) },
        IL2::Record => Some(IL1::Bind),
        IL2::Reply { warned, ready } => Some(IL1::Reply { warned, ready }),
        IL2::Stop => Some(IL1::Stop),
        IL2::Access { schema, adm } => Some(IL1::Access { schema, adm }),
        IL2::Feature { rdy } => Some(IL1::Feature { rdy }),
        IL2::Upgrade { .. } => Some(IL1::Upgrade),
        IL2::RmView { v, ok, reported } => Some(IL1::Remove { obj: Obj::View(v), reported }),
        IL2::RmFirst { c, ok, reported } => Some(IL1::Remove { obj: Obj::Item(c), reported }),
        IL2::RmLater { c, reported } => Some(IL1::Remove { obj: Obj::Item(c), reported }),
    }
}

/// L1's invariant through the abstraction; a failed step is in the reply's warnings; each recorded class delete's
/// result says whether the class is gone.
pub open spec fn inv01(s: IS2) -> bool {
    &&& inv1(absi(s))
    &&& (s.run is Some ==> (s.run->Some_0.failed ==> s.run->Some_0.warnings))
    &&& forall|c: int| #[trigger] s.done.contains_key(c) ==> (s.done[c] == !s.lcls.contains(c))
}

pub struct InstL2;

impl Contract for InstL2 {
    type S = IS2;
    type L = IL2;
    open spec fn init(s: IS2) -> bool { init2(s) }
    open spec fn next(s: IS2, l: IL2, t: IS2) -> bool { inv01(s) && step2(s, l, t) }
}

pub struct InstRaw;

impl Contract for InstRaw {
    type S = IS2;
    type L = IL2;
    open spec fn init(s: IS2) -> bool { init2(s) }
    open spec fn next(s: IS2, l: IL2, t: IS2) -> bool { step2(s, l, t) }
}

proof fn lemma_ddl(s: IS2, ok: bool, t: IS2)
    requires inv01(s), step2(s, IL2::Ddl { ok }, t),
    ensures inv01(t), step_or_stutter::<InstL1>(absi(s), labi(IL2::Ddl { ok }), absi(t)),
{
    // a failed DDL statement is in the reply's warnings (control F-0102 fails here)
    assert(t.run->Some_0.failed ==> t.run->Some_0.warnings);
    assert(forall|c: int| #[trigger] t.done.contains_key(c) ==> (t.done[c] == !t.lcls.contains(c)));
}

proof fn lemma_kg(s: IS2, ok: bool, t: IS2)
    requires inv01(s), step2(s, IL2::Kg { ok }, t),
    ensures inv01(t), step_or_stutter::<InstL1>(absi(s), labi(IL2::Kg { ok }), absi(t)),
{
    // a failed ^KG bootstrap is in the reply's warnings (control F-0102 fails here)
    assert(t.run->Some_0.failed ==> t.run->Some_0.warnings);
    assert(forall|c: int| #[trigger] t.done.contains_key(c) ==> (t.done[c] == !t.lcls.contains(c)));
}

proof fn lemma_access(s: IS2, schema: int, adm: Adm, t: IS2)
    requires inv01(s), step2(s, IL2::Access { schema, adm }, t),
    ensures inv01(t), step_or_stutter::<InstL1>(absi(s), labi(IL2::Access { schema, adm }), absi(t)),
{
    // the first access admits by the record alone: no record, no admission (control F-0103 fails here)
    assert(access2(s, schema) == access1(absi(s), schema));
}

proof fn lemma_upgrade(s: IS2, arg: int, t: IS2)
    requires inv01(s), step2(s, IL2::Upgrade { arg }, t),
    ensures inv01(t), step_or_stutter::<InstL1>(absi(s), labi(IL2::Upgrade { arg }), absi(t)),
{
    // the upgrade migrates the bound schema's tables or nothing (control F-0109 fails here)
    assert(t.shaped == s.shaped || (s.rec is Some && t.shaped == up1(absi(s))));
    if t.shaped == s.shaped { assert(absi(t) == absi(s)); }
}

proof fn lemma_rmview(s: IS2, v: int, ok: bool, reported: bool, t: IS2)
    requires inv01(s), step2(s, IL2::RmView { v, ok, reported }, t),
    ensures inv01(t), step_or_stutter::<InstL1>(absi(s), labi(IL2::RmView { v, ok, reported }), absi(t)),
{
    // a view is reported removed only when its DROP VIEW succeeded (control F-0101 fails here)
    assert(reported ==> !t.views.contains(v));
    if ok { assert(absi(t) == removed1(absi(s), Obj::View(v))); } else { assert(absi(t) == absi(s)); }
}

proof fn lemma_rmfirst(s: IS2, c: int, ok: bool, reported: bool, t: IS2)
    requires inv01(s), step2(s, IL2::RmFirst { c, ok, reported }, t),
    ensures inv01(t), step_or_stutter::<InstL1>(absi(s), labi(IL2::RmFirst { c, ok, reported }), absi(t)),
{
    assert forall|x: int| #[trigger] t.done.contains_key(x) implies (t.done[x] == !t.lcls.contains(x)) by {
        if x != c { assert(s.done.contains_key(x)); }
    }
    if ok { assert(absi(t) == removed1(absi(s), Obj::Item(c))); } else { assert(absi(t) == absi(s)); }
}

proof fn lemma_rmlater(s: IS2, c: int, reported: bool, t: IS2)
    requires inv01(s), step2(s, IL2::RmLater { c, reported }, t),
    ensures inv01(t), step_or_stutter::<InstL1>(absi(s), labi(IL2::RmLater { c, reported }), absi(t)),
{
    // a later item of a class reports that class's delete (control F-0101 fails here)
    assert(reported ==> !t.lcls.contains(c));
}

proof fn lemma_step(s: IS2, l: IL2, t: IS2)
    requires inv01(s), step2(s, l, t),
    ensures inv01(t), step_or_stutter::<InstL1>(absi(s), labi(l), absi(t)),
{
    match l {
        IL2::Ddl { ok } => lemma_ddl(s, ok, t),
        IL2::Kg { ok } => lemma_kg(s, ok, t),
        IL2::Access { schema, adm } => lemma_access(s, schema, adm, t),
        IL2::Upgrade { arg } => lemma_upgrade(s, arg, t),
        IL2::RmView { v, ok, reported } => lemma_rmview(s, v, ok, reported, t),
        IL2::RmFirst { c, ok, reported } => lemma_rmfirst(s, c, ok, reported, t),
        IL2::RmLater { c, reported } => lemma_rmlater(s, c, reported, t),
        IL2::Funcs => { assert(absi(t) == absi(s)); }
        IL2::Deploy { on, ok } => { if !(on && ok) { assert(absi(t) == absi(s)); } }
        IL2::Record => { assert(absi(t) == IS1 { bound: Some(s.run->Some_0.schema), ..absi(s) }); }
        _ => {}
    }
}

impl Refines<InstL1> for InstL2 {
    open spec fn abs(s: IS2) -> IS1 { absi(s) }
    open spec fn lab(l: IL2) -> Option<IL1> { labi(l) }
    proof fn init_refines(s: IS2) {}
    proof fn step_refines(s: IS2, l: IL2, t: IS2) { lemma_step(s, l, t); }
}

impl SafeContract for InstL2 {
    open spec fn inv(s: IS2) -> bool { inv01(s) }
    proof fn init_safe(s: IS2) {}
    proof fn step_safe(s: IS2, l: IL2, t: IS2) { lemma_step(s, l, t); }
}

proof fn lemma_raw_inv_at(states: Seq<IS2>, labels: Seq<IL2>, k: int)
    requires execution::<InstRaw>(states, labels), 0 <= k < states.len(),
    ensures inv01(states[k]),
    decreases k,
{
    if k > 0 {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution.
pub proof fn theorem_raw_executions_refine(states: Seq<IS2>, labels: Seq<IL2>)
    requires execution::<InstRaw>(states, labels),
    ensures
        execution::<InstL2>(states, labels),
        abstract_execution::<InstL1>(Seq::new(states.len(), |i: int| absi(states[i])),
                                     Seq::new(labels.len(), |i: int| labi(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv01(#[trigger] states[i]),
{
    assert forall|i: int| 0 <= i < states.len() implies inv01(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<InstL2>(states, labels));
    trace_refines::<InstL2, InstL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| absi(states[i])) =~= Seq::new(states.len(), |i: int| <InstL2 as Refines<InstL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| labi(labels[i])) =~= Seq::new(labels.len(), |i: int| <InstL2 as Refines<InstL1>>::lab(labels[i])));
}

/// On the layout: an engine is admitted only by a record naming its schema that it can read (spec 262 FR-006a).
pub proof fn theorem_no_record_no_admission(s: IS2, schema: int, adm: Adm, t: IS2)
    requires inv01(s), step2(s, IL2::Access { schema, adm }, t), adm is Accepted,
    ensures s.rec == Some(schema), !s.unreadable,
{
    lemma_access(s, schema, adm, t);
}

} // verus!
