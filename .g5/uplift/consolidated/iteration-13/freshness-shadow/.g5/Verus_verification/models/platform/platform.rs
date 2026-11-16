// IVG platform obligations — Verus model (initial uplift, worker B-platform, 2026-11-13).
//
// Product baseline 3eaa79cf. Bindings (L3) are in NOTES.md and in the comments that name a product
// operation. This file is a model and a transcription; it does not verify the product's Python or
// ObjectScript bodies.
//
//   Part 1  O-SCHEMA        one IVG Schema per namespace (ADR-0016, spec 262 FR-005/006/009)
//   Part 2  O-WRITE-SURFACE strict ledger mode on every structural write path (spec 213, ADR-0004/0013)
//   Part 3  O2 (cypher)     compiled plan cache: a class runs only for its own plan (ADR-0014, spec 257)
//
// Layers: L1 rules are stated independently of the code; L2 is the as-built mechanism with its real
// commit and interruption boundaries; lemmas prove L2 steps preserve the L1 invariants under named
// premises, and witnesses (concrete traces proved in Verus) show where the as-built mechanism breaks L1.
//
// Run:  $VERUS_BIN platform.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;
use vstd::set_lib::*;

verus! {

// ################################################################################################
// Part 1 — O-SCHEMA: one recorded IVG Schema per namespace
// ################################################################################################
//
// L1 (ADR-0016:11,17; spec 262 FR-005, FR-006, FR-009):
//   (a) record stability: once ^IVG.Deploy("schema") names a schema R, it names R for good;
//   (b) after the record names R, nothing for another schema writes the namespace: no engine, setup,
//       deploy or migration of T != R creates objects or writes rows/globals (the globals ^KG, ^NKG,
//       ^IVG.* belong to the namespace, so a second schema would share them);
//   (c) a refusal changes nothing (FR-006 "before any write").
// Schema names are modelled in their canonical case (same_schema, schema_name.py:138-140); the
// case-variant spelling of the deploy rewrite (F-S6) is not represented.

pub type Sch = nat;
pub type Eid = nat;
pub type Pid = nat;

/// `how` of _record_and_initialize (_engine/schema.py:2232-2242); "new" and "inferred" both record.
pub enum How {
    Existing,
    Fresh,
    Explicit,
}

/// The setup's commit/interruption boundaries inside initialize_schema():
///   Read      after read_record (2222), the mismatch check (2224-2226) and `held` (2230-2242)
///   Ddl       after the table DDL and routines of _initialize_schema (committed, 2284 → 2572)
///   Deployed  after the class deploy (2578-2595, best-effort: an exception is kept as a warning)
pub enum Phase {
    Read,
    Ddl,
    Deployed,
}

/// One initialize_schema() call in flight.
pub struct Setup {
    pub e: Eid,
    pub sch: Sch,
    /// the record as read at 2222 (`recorded`); write_record runs at 2311-2312 iff this is None
    pub saw: Option<Sch>,
    pub how: How,
    pub phase: Phase,
}

/// An IRISGraphEngine: its schema (resolve_schema_name), whether it was named (`_schema_explicit`,
/// engine.py:297) and whether its first-access check has passed (FirstAccessCheck.pending == False).
pub struct Eng {
    pub sch: Sch,
    pub explicit: bool,
    pub accepted: bool,
}

pub struct SSt {
    /// ^IVG.Deploy("schema")
    pub record: Option<Sch>,
    /// schemas holding IVG base tables nodes + rdf_edges (INFORMATION_SCHEMA; _ivg_table_schemas)
    pub tables: Set<Sch>,
    /// schemas holding this release's objects: ^oddDEF(<pkg>.funcCYCMP) (schema_name.py:184-235)
    pub marker: Set<Sch>,
    /// schemas the class deploy compiled IVG's classes for (rewritten sources)
    pub classes_for: Set<Sch>,
    pub setups: Map<Pid, Setup>,
    pub engines: Map<Eid, Eng>,
    /// ghost: schemas that wrote objects, rows or globals while a record existed (L1 (b))
    pub post_writers: Set<Sch>,
}

pub enum SAction {
    /// IRISGraphEngine.__init__ → _check_namespace_schema (engine.py:375-378, 1847-1866).
    /// native_ok = false: the record cannot be read (no %Native_GlobalAccess); the check is skipped
    /// with a WARNING (engine.py:1862-1866, ADMIN_GUIDE:515-518).
    NewEngine { e: Eid, sch: Sch, explicit: bool, native_ok: bool },
    /// a pending engine's next database access re-runs the check (FirstAccessCheck.ensure,
    /// guarded_connection, schema_name.py:286-353)
    Access { e: Eid },
    /// an accepted engine writes its tables and the namespace's globals (any public write method)
    Write { e: Eid },
    /// engine._waive_schema_check() (engine.py:1887-1890) as called by the migrations
    /// (graph_scoped_embeddings.py:287-288, temporal_structural_rows.py:85-89)
    Waive { e: Eid },
    SetupRead { p: Pid, e: Eid },
    SetupDdl { p: Pid },
    /// deploy_objectscript_classes → refuse_other_record (schema.py:2878-2888, class_deploy.py:355-357):
    /// re-reads the record; its IVGSchemaError is caught by _initialize_schema's `except Exception`
    /// (_engine/schema.py:2591-2594) and kept as a warning
    SetupDeploy { p: Pid },
    /// grants, ledger-history copy, write_record iff nothing was read (2309-2312), conn.commit (2313);
    /// initialize_schema then releases the engine's guard (_schema_check_passed, 2159-2160)
    SetupRecord { p: Pid },
    /// the setup stops (process death, an exception): its committed effects stay
    SetupAbort { p: Pid },
}

/// `serial`: a setup starts only when no other is in flight (the premise under which the as-built
/// mechanism is correct; equivalently the proposed LOCK +^IVG.Deploy("schema") around read..record).
/// `refuse_explicit_over_marker`: the explicit path (FR-009) refuses while another schema holds this
/// release's marker (premise/proposal for F-S3). `deploy_refusal_aborts`: the deploy's IVGSchemaError
/// is re-raised instead of swallowed. `cas`: write_record becomes a compare-and-set (written only if no
/// record exists at write time), without a lock. `cas_raises`: a lost compare-and-set raises before
/// initialize_schema releases the engine (_schema_check_passed is then not reached).
pub struct SVariant {
    pub serial: bool,
    pub refuse_explicit_over_marker: bool,
    pub deploy_refusal_aborts: bool,
    pub cas: bool,
    pub cas_raises: bool,
}

pub open spec fn s_as_built() -> SVariant {
    SVariant { serial: false, refuse_explicit_over_marker: false, deploy_refusal_aborts: false, cas: false, cas_raises: false }
}

/// The variant the serial theorem is proved for (premises P-SERIAL and P-NO-EXPLICIT-OVER-MARKER).
pub open spec fn s_proved() -> SVariant {
    SVariant { serial: true, refuse_explicit_over_marker: true, deploy_refusal_aborts: false, cas: false, cas_raises: false }
}

/// check_first_access with a readable record (schema_name.py:220-235): a record must name the
/// engine's schema; without one, this release's marker must be there (never_set_up,
/// setup_unfinished and not_upgraded are all refusals).
pub open spec fn check_passes(s: SSt, sch: Sch) -> bool {
    match s.record {
        Some(r) => r == sch,
        None => s.marker.contains(sch),
    }
}

pub open spec fn no_others(s: SSt, sch: Sch) -> bool {
    forall|x: Sch| #[trigger] s.tables.contains(x) ==> x == sch
}

pub open spec fn marker_elsewhere(s: SSt, sch: Sch) -> bool {
    exists|x: Sch| #[trigger] s.marker.contains(x) && x != sch
}

/// _record_and_initialize's record transitions (2222-2242); None = IVGSchemaError (nothing written).
pub open spec fn how_of(s: SSt, sch: Sch, explicit: bool, v: SVariant) -> Option<How> {
    match s.record {
        Some(r) => if r == sch { Some(How::Existing) } else { None },
        None =>
            if no_others(s, sch) {
                Some(How::Fresh)
            } else if explicit && !(v.refuse_explicit_over_marker && marker_elsewhere(s, sch)) {
                Some(How::Explicit)
            } else {
                None
            },
    }
}

pub open spec fn busy_s(s: SSt) -> bool {
    exists|q: Pid| #[trigger] s.setups.contains_key(q)
}

pub open spec fn pw_if_recorded(s: SSt, sch: Sch) -> Set<Sch> {
    if s.record is Some { s.post_writers.insert(sch) } else { s.post_writers }
}

pub open spec fn s_step(s: SSt, a: SAction, v: SVariant) -> Option<SSt> {
    match a {
        SAction::NewEngine { e, sch, explicit, native_ok } =>
            if s.engines.contains_key(e) {
                None
            } else {
                Some(SSt { engines: s.engines.insert(e, Eng { sch, explicit, accepted: !native_ok || check_passes(s, sch) }), ..s })
            },
        SAction::Access { e } =>
            if !s.engines.contains_key(e) || s.engines[e].accepted || !check_passes(s, s.engines[e].sch) {
                None
            } else {
                Some(SSt { engines: s.engines.insert(e, Eng { accepted: true, ..s.engines[e] }), ..s })
            },
        SAction::Write { e } =>
            if !s.engines.contains_key(e) || !s.engines[e].accepted || !s.tables.contains(s.engines[e].sch) {
                None  // refused (IVGSchemaError at the method's entry) or no table to write
            } else {
                Some(SSt { post_writers: pw_if_recorded(s, s.engines[e].sch), ..s })
            },
        SAction::Waive { e } =>
            if !s.engines.contains_key(e) {
                None
            } else {
                Some(SSt { engines: s.engines.insert(e, Eng { accepted: true, ..s.engines[e] }), ..s })
            },
        SAction::SetupRead { p, e } =>
            if s.setups.contains_key(p) || !s.engines.contains_key(e) || (v.serial && busy_s(s)) {
                None
            } else {
                let en = s.engines[e];
                match how_of(s, en.sch, en.explicit, v) {
                    None => None,
                    Some(h) => Some(SSt {
                        setups: s.setups.insert(p, Setup { e, sch: en.sch, saw: s.record, how: h, phase: Phase::Read }),
                        ..s
                    }),
                }
            },
        SAction::SetupDdl { p } =>
            if !s.setups.contains_key(p) || s.setups[p].phase != Phase::Read {
                None
            } else {
                let st = s.setups[p];
                Some(SSt {
                    tables: s.tables.insert(st.sch),
                    marker: s.marker.insert(st.sch),
                    post_writers: pw_if_recorded(s, st.sch),
                    setups: s.setups.insert(p, Setup { phase: Phase::Ddl, ..st }),
                    ..s
                })
            },
        SAction::SetupDeploy { p } =>
            if !s.setups.contains_key(p) || s.setups[p].phase != Phase::Ddl {
                None
            } else {
                let st = s.setups[p];
                if s.record is Some && s.record != Some(st.sch) {
                    // refuse_other_record raised IVGSchemaError
                    if v.deploy_refusal_aborts {
                        Some(SSt { setups: s.setups.remove(p), ..s })
                    } else {
                        Some(SSt { setups: s.setups.insert(p, Setup { phase: Phase::Deployed, ..st }), ..s })
                    }
                } else {
                    Some(SSt {
                        classes_for: s.classes_for.insert(st.sch),
                        post_writers: pw_if_recorded(s, st.sch),
                        setups: s.setups.insert(p, Setup { phase: Phase::Deployed, ..st }),
                        ..s
                    })
                }
            },
        SAction::SetupRecord { p } =>
            if !s.setups.contains_key(p) || s.setups[p].phase != Phase::Deployed || !s.engines.contains_key(s.setups[p].e) {
                None
            } else {
                let st = s.setups[p];
                let released = s.engines.insert(st.e, Eng { accepted: true, ..s.engines[st.e] });
                if v.cas && s.record is Some && s.record != Some(st.sch) {
                    // the compare-and-set lost: another schema's record stays
                    if v.cas_raises {
                        Some(SSt { setups: s.setups.remove(p), ..s })
                    } else {
                        Some(SSt { post_writers: pw_if_recorded(s, st.sch), engines: released, setups: s.setups.remove(p), ..s })
                    }
                } else {
                    Some(SSt {
                        record: if st.saw is None { Some(st.sch) } else { s.record },
                        post_writers: pw_if_recorded(s, st.sch),
                        engines: released,
                        setups: s.setups.remove(p),
                        ..s
                    })
                }
            },
        SAction::SetupAbort { p } =>
            if !s.setups.contains_key(p) { None } else { Some(SSt { setups: s.setups.remove(p), ..s }) },
    }
}

// ---------------------------------------------------------------------------------------- L1

/// L1 (b): every schema that wrote while a record existed is the recorded one.
pub open spec fn post_writes_ok(s: SSt) -> bool {
    forall|x: Sch| #[trigger] s.post_writers.contains(x) ==> s.record == Some(x)
}

/// L1 (a) as a step property.
pub open spec fn record_stable(s: SSt, s2: SSt) -> bool {
    s.record is Some ==> s2.record == s.record
}

// ---------------------------------------------------------------------------------------- invariant

pub open spec fn setup_ok(s: SSt, st: Setup) -> bool {
    &&& st.saw == s.record
    &&& (s.record is Some ==> s.record->Some_0 == st.sch)
    &&& (forall|x: Sch| #[trigger] s.marker.contains(x) ==> x == st.sch)
    &&& (st.phase != Phase::Read ==> s.marker.contains(st.sch))
    &&& s.engines.contains_key(st.e)
    &&& s.engines[st.e].sch == st.sch
}

pub open spec fn s_inv(s: SSt) -> bool {
    &&& forall|x: Sch| #[trigger] s.marker.contains(x) ==> s.tables.contains(x)
    &&& (s.record is Some ==> s.marker.contains(s.record->Some_0))
    &&& forall|x: Sch| #[trigger] s.marker.contains(x) && s.record is Some ==> x == s.record->Some_0
    &&& forall|e: Eid| #[trigger] s.engines.contains_key(e) && s.engines[e].accepted ==> s.marker.contains(s.engines[e].sch)
    &&& forall|p: Pid, q: Pid| #[trigger] s.setups.contains_key(p) && #[trigger] s.setups.contains_key(q) ==> p == q
    &&& forall|p: Pid| #[trigger] s.setups.contains_key(p) ==> setup_ok(s, s.setups[p])
    &&& post_writes_ok(s)
}

/// Premises the serial theorem needs about the environment (named in NOTES.md):
///   P-NATIVE-READABLE  every engine's role can read ^IVG.Deploy (else the check is skipped by design)
///   P-WAIVE-HARMLESS   a migration's waiver is used only where the check would pass anyway
pub open spec fn s_premise(s: SSt, a: SAction) -> bool {
    match a {
        SAction::NewEngine { native_ok, .. } => native_ok,
        SAction::Waive { e } => s.engines.contains_key(e) ==> check_passes(s, s.engines[e].sch),
        _ => true,
    }
}

pub open spec fn s_init(s: SSt) -> bool {
    &&& s.record is None
    &&& s.marker == Set::<Sch>::empty()
    &&& s.classes_for == Set::<Sch>::empty()
    &&& s.setups == Map::<Pid, Setup>::empty()
    &&& s.engines == Map::<Eid, Eng>::empty()
    &&& s.post_writers == Set::<Sch>::empty()
}

/// A fresh namespace, or one holding only an earlier release's tables (any `tables`), satisfies the
/// invariant.
pub proof fn lemma_s_init(s: SSt)
    requires s_init(s),
    ensures s_inv(s),
{
}

/// Every in-scope step of the serial variant preserves the invariant and the record.
pub proof fn lemma_s_step_preserves_inv(s: SSt, a: SAction)
    requires
        s_inv(s),
        s_premise(s, a),
        s_step(s, a, s_proved()) is Some,
    ensures
        s_inv(s_step(s, a, s_proved())->Some_0),
        record_stable(s, s_step(s, a, s_proved())->Some_0),
{
    let v = s_proved();
    let s2 = s_step(s, a, v)->Some_0;
    match a {
        SAction::NewEngine { e, sch, explicit, native_ok } => {
            assert forall|p: Pid| #[trigger] s2.setups.contains_key(p) implies setup_ok(s2, s2.setups[p]) by {
                assert(s.setups.contains_key(p));
                assert(setup_ok(s, s.setups[p]));
                assert(s2.engines.contains_key(s.setups[p].e));
                assert(s.setups[p].e != e);
            }
            assert forall|x: Eid| #[trigger] s2.engines.contains_key(x) && s2.engines[x].accepted implies s2.marker.contains(s2.engines[x].sch) by {
                if x == e {
                    match s.record {
                        Some(r) => { assert(r == sch); }
                        None => {}
                    }
                } else {
                    assert(s.engines.contains_key(x));
                }
            }
        }
        SAction::Access { e } => {
            assert forall|p: Pid| #[trigger] s2.setups.contains_key(p) implies setup_ok(s2, s2.setups[p]) by {
                assert(setup_ok(s, s.setups[p]));
            }
            assert forall|x: Eid| #[trigger] s2.engines.contains_key(x) && s2.engines[x].accepted implies s2.marker.contains(s2.engines[x].sch) by {
                if x == e {
                    match s.record {
                        Some(r) => { assert(r == s.engines[e].sch); }
                        None => {}
                    }
                } else {
                    assert(s.engines.contains_key(x));
                }
            }
        }
        SAction::Write { e } => {
            let x0 = s.engines[e].sch;
            assert(s.marker.contains(x0));
            assert forall|x: Sch| #[trigger] s2.post_writers.contains(x) implies s2.record == Some(x) by {
                if x == x0 && s.record is Some {
                    let r = s.record->Some_0;
                    assert(s.record == Some(r) && s.marker.contains(x0));
                }
            }
            assert forall|p: Pid| #[trigger] s2.setups.contains_key(p) implies setup_ok(s2, s2.setups[p]) by {
                assert(setup_ok(s, s.setups[p]));
            }
        }
        SAction::Waive { e } => {
            assert forall|p: Pid| #[trigger] s2.setups.contains_key(p) implies setup_ok(s2, s2.setups[p]) by {
                assert(setup_ok(s, s.setups[p]));
            }
            assert forall|x: Eid| #[trigger] s2.engines.contains_key(x) && s2.engines[x].accepted implies s2.marker.contains(s2.engines[x].sch) by {
                if x == e {
                    match s.record {
                        Some(r) => { assert(r == s.engines[e].sch); }
                        None => {}
                    }
                } else {
                    assert(s.engines.contains_key(x));
                }
            }
        }
        SAction::SetupRead { p, e } => {
            let en = s.engines[e];
            let st = s2.setups[p];
            assert(!busy_s(s));
            assert forall|q: Pid| #[trigger] s2.setups.contains_key(q) implies q == p by {
                if q != p {
                    assert(s.setups.contains_key(q));
                    assert(busy_s(s));
                }
            }
            assert forall|x: Sch| #[trigger] s2.marker.contains(x) implies x == st.sch by {
                assert(s.tables.contains(x));
                match s.record {
                    Some(r) => {}
                    None => {
                        if !no_others(s, en.sch) {
                            assert(!marker_elsewhere(s, en.sch));
                        }
                    }
                }
            }
            assert(setup_ok(s2, st));
        }
        SAction::SetupDdl { p } => {
            let st = s.setups[p];
            assert(setup_ok(s, st));
            assert forall|q: Pid| #[trigger] s2.setups.contains_key(q) implies setup_ok(s2, s2.setups[q]) by {
                assert(q == p);
            }
            assert forall|x: Sch| #[trigger] s2.post_writers.contains(x) implies s2.record == Some(x) by {
                if x == st.sch && s.record is Some {
                    let r = s.record->Some_0;
                    assert(r == st.sch);
                }
            }
            assert forall|x: Sch| #[trigger] s2.marker.contains(x) && s2.record is Some implies x == s2.record->Some_0 by {
                if x != st.sch {
                    assert(s.marker.contains(x));
                }
            }
        }
        SAction::SetupDeploy { p } => {
            let st = s.setups[p];
            assert(setup_ok(s, st));
            assert(!(s.record is Some && s.record != Some(st.sch))) by {
                if s.record is Some {
                    let r = s.record->Some_0;
                    assert(r == st.sch);
                }
            }
            assert forall|q: Pid| #[trigger] s2.setups.contains_key(q) implies setup_ok(s2, s2.setups[q]) by {
                assert(q == p);
            }
            assert forall|x: Sch| #[trigger] s2.post_writers.contains(x) implies s2.record == Some(x) by {
                if x == st.sch && s.record is Some {
                    let r = s.record->Some_0;
                    assert(r == st.sch);
                }
            }
        }
        SAction::SetupRecord { p } => {
            let st = s.setups[p];
            assert(setup_ok(s, st));
            assert forall|q: Pid| #[trigger] s2.setups.contains_key(q) implies setup_ok(s2, s2.setups[q]) by {
                assert(s.setups.contains_key(q));
                assert(q == p);
            }
            assert forall|x: Eid| #[trigger] s2.engines.contains_key(x) && s2.engines[x].accepted implies s2.marker.contains(s2.engines[x].sch) by {
                if x != st.e {
                    assert(s.engines.contains_key(x));
                }
            }
            assert forall|x: Sch| #[trigger] s2.post_writers.contains(x) implies s2.record == Some(x) by {
                if s.record is Some {
                    let r = s.record->Some_0;
                    assert(r == st.sch);
                } else {
                    assert(!s.post_writers.contains(x));
                }
            }
            assert forall|x: Sch| #[trigger] s2.marker.contains(x) && s2.record is Some implies x == s2.record->Some_0 by {
                assert(setup_ok(s, st));
            }
        }
        SAction::SetupAbort { p } => {
            assert forall|q: Pid| #[trigger] s2.setups.contains_key(q) implies setup_ok(s2, s2.setups[q]) by {
                assert(setup_ok(s, s.setups[q]));
            }
        }
    }
}

/// L1 consequences of the invariant: once recorded, every accepted engine is on the record, every
/// write while recorded was the record's, and a setup on another schema is refused with nothing written.
pub proof fn theorem_schema_one_per_namespace(s: SSt, r: Sch, e: Eid, p: Pid, t: Sch)
    requires
        s_inv(s),
        s.record == Some(r),
        t != r,
    ensures
        s.engines.contains_key(e) && s.engines[e].accepted ==> s.engines[e].sch == r,
        post_writes_ok(s),
        s.engines.contains_key(e) && s.engines[e].sch == t ==> s_step(s, SAction::SetupRead { p, e }, s_proved()) is None,
        s.engines.contains_key(e) && s.engines[e].sch == t ==> s_step(s, SAction::Write { e }, s_proved()) is None
            || !s.engines[e].accepted,
{
    if s.engines.contains_key(e) && s.engines[e].accepted {
        assert(s.marker.contains(s.engines[e].sch));
    }
}

/// L1 (c): an engine on another schema is constructed refused and nothing in the namespace changes.
pub proof fn theorem_refusal_changes_nothing(s: SSt, r: Sch, e: Eid, t: Sch, explicit: bool)
    requires
        s.record == Some(r),
        t != r,
        !s.engines.contains_key(e),
    ensures
        ({
            let s2 = s_step(s, SAction::NewEngine { e, sch: t, explicit, native_ok: true }, s_as_built())->Some_0;
            &&& !s2.engines[e].accepted
            &&& s2.record == s.record && s2.tables == s.tables && s2.marker == s.marker
            &&& s2.classes_for == s.classes_for && s2.post_writers == s.post_writers
        }),
        s_step(s, SAction::NewEngine { e, sch: t, explicit, native_ok: true }, s_as_built()) is Some,
{
}

// ---------------------------------------------------------------------------------------- witnesses

pub open spec fn fresh_ns() -> SSt {
    SSt {
        record: None,
        tables: Set::empty(),
        marker: Set::empty(),
        classes_for: Set::empty(),
        setups: Map::empty(),
        engines: Map::empty(),
        post_writers: Set::empty(),
    }
}

/// A valid serial first setup: Graph_KG (1) is recorded, its engine is accepted and writes; an engine
/// on IVGALT (2) is refused at construction, its writes and its setup are refused, nothing changes.
pub proof fn witness_serial_first_setup_and_refusal() {
    let v = s_proved();
    let s0 = fresh_ns();
    let s1 = s_step(s0, SAction::NewEngine { e: 1, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    assert(!s1.engines[1].accepted);
    assert(no_others(s1, 1));
    let s2 = s_step(s1, SAction::SetupRead { p: 1, e: 1 }, v)->Some_0;
    assert(s_step(s1, SAction::SetupRead { p: 1, e: 1 }, v) is Some);
    let s3 = s_step(s2, SAction::SetupDdl { p: 1 }, v)->Some_0;
    let s4 = s_step(s3, SAction::SetupDeploy { p: 1 }, v)->Some_0;
    let s5 = s_step(s4, SAction::SetupRecord { p: 1 }, v)->Some_0;
    assert(s_step(s4, SAction::SetupRecord { p: 1 }, v) is Some);
    assert(s5.record == Some(1nat) && s5.engines[1].accepted);
    let s6 = s_step(s5, SAction::Write { e: 1 }, v)->Some_0;
    assert(s_step(s5, SAction::Write { e: 1 }, v) is Some);
    assert(s6.post_writers.contains(1));
    assert(post_writes_ok(s6));
    let s7 = s_step(s6, SAction::NewEngine { e: 2, sch: 2, explicit: true, native_ok: true }, v)->Some_0;
    assert(!s7.engines[2].accepted);
    assert(s_step(s7, SAction::Write { e: 2 }, v) is None);
    assert(s_step(s7, SAction::SetupRead { p: 2, e: 2 }, v) is None);
    assert(s7.record == s6.record && s7.tables == s6.tables && s7.post_writers == s6.post_writers);
}

/// W-S1 (F-S1) — two first setups at once, Graph_KG (1) and IVGALT (2), in a fresh namespace. Both
/// read "no record" at 2222, both run their DDL and deploy (the deploy's re-check also sees no record),
/// setup 1 records Graph_KG, then setup 2 records IVGALT over it (write_record is an unconditional
/// set, 2311-2312). Both engines are accepted; the Graph_KG engine keeps writing the shared globals
/// while the record names IVGALT.
pub proof fn witness_concurrent_first_setups_overwrite_the_record() {
    let v = s_as_built();
    let s0 = fresh_ns();
    let s1 = s_step(s0, SAction::NewEngine { e: 1, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    let s2 = s_step(s1, SAction::NewEngine { e: 2, sch: 2, explicit: true, native_ok: true }, v)->Some_0;
    assert(!s2.engines[1].accepted && !s2.engines[2].accepted);
    assert(no_others(s2, 1));
    let s3 = s_step(s2, SAction::SetupRead { p: 1, e: 1 }, v)->Some_0;
    assert(s_step(s2, SAction::SetupRead { p: 1, e: 1 }, v) is Some);
    assert(no_others(s3, 2));
    let s4 = s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v)->Some_0;
    assert(s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v) is Some);
    let s5 = s_step(s4, SAction::SetupDdl { p: 1 }, v)->Some_0;
    let s6 = s_step(s5, SAction::SetupDdl { p: 2 }, v)->Some_0;
    let s7 = s_step(s6, SAction::SetupDeploy { p: 1 }, v)->Some_0;
    let s8 = s_step(s7, SAction::SetupDeploy { p: 2 }, v)->Some_0;
    assert(s8.classes_for.contains(1) && s8.classes_for.contains(2));
    let s9 = s_step(s8, SAction::SetupRecord { p: 1 }, v)->Some_0;
    assert(s_step(s8, SAction::SetupRecord { p: 1 }, v) is Some);
    assert(s9.record == Some(1nat));
    let s10 = s_step(s9, SAction::SetupRecord { p: 2 }, v)->Some_0;
    assert(s_step(s9, SAction::SetupRecord { p: 2 }, v) is Some);
    // L1 (a) is broken: the record changed from Graph_KG to IVGALT
    assert(s10.record == Some(2nat));
    assert(!record_stable(s9, s10));
    assert(s10.engines[1].accepted && s10.engines[2].accepted);
    // L1 (b) is broken: the loser's engine writes while the record names the winner
    let s11 = s_step(s10, SAction::Write { e: 1 }, v)->Some_0;
    assert(s_step(s10, SAction::Write { e: 1 }, v) is Some);
    assert(s11.post_writers.contains(1));
    assert(!post_writes_ok(s11));
}

/// W-S1b — the deploy's re-check sees the other setup's record, raises IVGSchemaError, and
/// _initialize_schema keeps it as a warning: the setup goes on and write_record overwrites the record.
/// Its DDL already created IVGALT's objects in a namespace recorded as Graph_KG.
pub proof fn witness_deploy_refusal_is_swallowed() {
    let v = s_as_built();
    let s0 = fresh_ns();
    let s1 = s_step(s0, SAction::NewEngine { e: 1, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    let s2 = s_step(s1, SAction::NewEngine { e: 2, sch: 2, explicit: true, native_ok: true }, v)->Some_0;
    assert(no_others(s2, 1));
    let s3 = s_step(s2, SAction::SetupRead { p: 1, e: 1 }, v)->Some_0;
    assert(no_others(s3, 2));
    let s4 = s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v)->Some_0;
    assert(s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v) is Some);
    let s5 = s_step(s4, SAction::SetupDdl { p: 1 }, v)->Some_0;
    let s6 = s_step(s5, SAction::SetupDeploy { p: 1 }, v)->Some_0;
    let s7 = s_step(s6, SAction::SetupRecord { p: 1 }, v)->Some_0;
    assert(s_step(s6, SAction::SetupRecord { p: 1 }, v) is Some);
    assert(s7.record == Some(1nat) && s7.setups.contains_key(2));
    let s8 = s_step(s7, SAction::SetupDdl { p: 2 }, v)->Some_0;
    assert(s8.post_writers.contains(2) && s8.record == Some(1nat));
    assert(!post_writes_ok(s8));
    let s9 = s_step(s8, SAction::SetupDeploy { p: 2 }, v)->Some_0;
    assert(s_step(s8, SAction::SetupDeploy { p: 2 }, v) is Some);
    assert(!s9.classes_for.contains(2) && s9.setups.contains_key(2));
    let s10 = s_step(s9, SAction::SetupRecord { p: 2 }, v)->Some_0;
    assert(s_step(s9, SAction::SetupRecord { p: 2 }, v) is Some);
    assert(s10.record == Some(2nat));
    assert(!record_stable(s9, s10));
}

/// Re-raising the deploy's refusal stops the overwrite in W-S1b but not the DDL already done for
/// IVGALT, and not W-S1 (where both deploys ran before either record): only a lock (`serial`) does.
pub proof fn witness_reraise_alone_is_not_enough() {
    let v = SVariant { serial: false, refuse_explicit_over_marker: false, deploy_refusal_aborts: true, cas: false, cas_raises: false };
    let s0 = fresh_ns();
    let s1 = s_step(s0, SAction::NewEngine { e: 1, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    let s2 = s_step(s1, SAction::NewEngine { e: 2, sch: 2, explicit: true, native_ok: true }, v)->Some_0;
    assert(no_others(s2, 1));
    let s3 = s_step(s2, SAction::SetupRead { p: 1, e: 1 }, v)->Some_0;
    assert(no_others(s3, 2));
    let s4 = s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v)->Some_0;
    let s5 = s_step(s4, SAction::SetupDdl { p: 1 }, v)->Some_0;
    let s6 = s_step(s5, SAction::SetupDdl { p: 2 }, v)->Some_0;
    let s7 = s_step(s6, SAction::SetupDeploy { p: 1 }, v)->Some_0;
    let s8 = s_step(s7, SAction::SetupDeploy { p: 2 }, v)->Some_0;
    let s9 = s_step(s8, SAction::SetupRecord { p: 1 }, v)->Some_0;
    let s10 = s_step(s9, SAction::SetupRecord { p: 2 }, v)->Some_0;
    assert(s_step(s9, SAction::SetupRecord { p: 2 }, v) is Some);
    assert(s9.record == Some(1nat) && s10.record == Some(2nat));
}

/// With the lock (`serial`) the second setup cannot start while the first is in flight, and once
/// the first has recorded Graph_KG the IVGALT setup is refused at its read (FR-006).
pub proof fn witness_lock_refuses_the_second_setup() {
    let v = SVariant { serial: true, refuse_explicit_over_marker: false, deploy_refusal_aborts: false, cas: false, cas_raises: false };
    let s0 = fresh_ns();
    let s1 = s_step(s0, SAction::NewEngine { e: 1, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    let s2 = s_step(s1, SAction::NewEngine { e: 2, sch: 2, explicit: true, native_ok: true }, v)->Some_0;
    assert(no_others(s2, 1));
    let s3 = s_step(s2, SAction::SetupRead { p: 1, e: 1 }, v)->Some_0;
    assert(s3.setups.contains_key(1));
    assert(s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v) is None) by {
        assert(busy_s(s3));
    }
    let s4 = s_step(s3, SAction::SetupDdl { p: 1 }, v)->Some_0;
    let s5 = s_step(s4, SAction::SetupDeploy { p: 1 }, v)->Some_0;
    let s6 = s_step(s5, SAction::SetupRecord { p: 1 }, v)->Some_0;
    assert(s6.record == Some(1nat));
    assert(s_step(s6, SAction::SetupRead { p: 2, e: 2 }, v) is None);
}

/// R1-4: a compare-and-set record write alone (no lock) stops the overwrite of W-S1 but not the
/// violation: setup 2 still reaches _schema_check_passed (2159-2160), so its engine is released and
/// writes while the record names Graph_KG.
pub proof fn witness_cas_alone_still_releases_the_second_engine() {
    let v = SVariant { serial: false, refuse_explicit_over_marker: false, deploy_refusal_aborts: false, cas: true, cas_raises: false };
    let s0 = fresh_ns();
    let s1 = s_step(s0, SAction::NewEngine { e: 1, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    let s2 = s_step(s1, SAction::NewEngine { e: 2, sch: 2, explicit: true, native_ok: true }, v)->Some_0;
    assert(no_others(s2, 1));
    let s3 = s_step(s2, SAction::SetupRead { p: 1, e: 1 }, v)->Some_0;
    assert(no_others(s3, 2));
    let s4 = s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v)->Some_0;
    assert(s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v) is Some);
    let s5 = s_step(s4, SAction::SetupDdl { p: 1 }, v)->Some_0;
    let s6 = s_step(s5, SAction::SetupDdl { p: 2 }, v)->Some_0;
    let s7 = s_step(s6, SAction::SetupDeploy { p: 1 }, v)->Some_0;
    let s8 = s_step(s7, SAction::SetupDeploy { p: 2 }, v)->Some_0;
    let s9 = s_step(s8, SAction::SetupRecord { p: 1 }, v)->Some_0;
    assert(s_step(s8, SAction::SetupRecord { p: 1 }, v) is Some);
    let s10 = s_step(s9, SAction::SetupRecord { p: 2 }, v)->Some_0;
    assert(s_step(s9, SAction::SetupRecord { p: 2 }, v) is Some);
    assert(s10.record == Some(1nat) && record_stable(s9, s10));
    assert(s10.engines[2].accepted);
    let s11 = s_step(s10, SAction::Write { e: 2 }, v)->Some_0;
    assert(s_step(s10, SAction::Write { e: 2 }, v) is Some);
    assert(s11.post_writers.contains(2) && s11.record == Some(1nat));
    assert(!post_writes_ok(s11));
}

/// R1-4: compare-and-set plus a raise that does not release the engine closes W-S1's release, but the
/// second setup's DDL can still land after the first record (W-S1b's order): IVGALT's objects are
/// created in a namespace recorded as Graph_KG. Only the lock refuses the second setup before it writes
/// (witness_lock_refuses_the_second_setup, lemma_s_step_preserves_inv).
pub proof fn witness_cas_with_raise_still_admits_late_ddl() {
    let v = SVariant { serial: false, refuse_explicit_over_marker: false, deploy_refusal_aborts: false, cas: true, cas_raises: true };
    let s0 = fresh_ns();
    let s1 = s_step(s0, SAction::NewEngine { e: 1, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    let s2 = s_step(s1, SAction::NewEngine { e: 2, sch: 2, explicit: true, native_ok: true }, v)->Some_0;
    assert(no_others(s2, 1));
    let s3 = s_step(s2, SAction::SetupRead { p: 1, e: 1 }, v)->Some_0;
    assert(no_others(s3, 2));
    let s4 = s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v)->Some_0;
    assert(s_step(s3, SAction::SetupRead { p: 2, e: 2 }, v) is Some);
    let s5 = s_step(s4, SAction::SetupDdl { p: 1 }, v)->Some_0;
    let s6 = s_step(s5, SAction::SetupDeploy { p: 1 }, v)->Some_0;
    let s7 = s_step(s6, SAction::SetupRecord { p: 1 }, v)->Some_0;
    assert(s_step(s6, SAction::SetupRecord { p: 1 }, v) is Some);
    let s8 = s_step(s7, SAction::SetupDdl { p: 2 }, v)->Some_0;
    assert(s_step(s7, SAction::SetupDdl { p: 2 }, v) is Some);
    assert(s8.post_writers.contains(2) && s8.record == Some(1nat));
    assert(!post_writes_ok(s8));
    let s9 = s_step(s8, SAction::SetupDeploy { p: 2 }, v)->Some_0;
    let s10 = s_step(s9, SAction::SetupRecord { p: 2 }, v)->Some_0;
    assert(s_step(s9, SAction::SetupRecord { p: 2 }, v) is Some);
    assert(s10.record == Some(1nat) && !s10.engines[2].accepted && !s10.setups.contains_key(2));
}

/// W-S2 (F-S2) — a namespace recorded as RAG (3) that also holds Graph_KG (1) tables (FR-009's
/// two-schema case). A migration builds IRISGraphEngine(conn) on the default Graph_KG: refused
/// (mismatch). _waive_schema_check releases the mismatch too, and its create_edge writes Graph_KG
/// rows and the shared ^KG while the record names RAG.
pub proof fn witness_waiver_releases_a_mismatch() {
    let v = s_as_built();
    let s0 = SSt {
        record: Some(3nat),
        tables: Set::empty().insert(1nat).insert(3nat),
        marker: Set::empty().insert(3nat),
        ..fresh_ns()
    };
    let s1 = s_step(s0, SAction::NewEngine { e: 4, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    assert(!s1.engines[4].accepted);
    assert(s_step(s1, SAction::Write { e: 4 }, v) is None);
    let s2 = s_step(s1, SAction::Waive { e: 4 }, v)->Some_0;
    assert(s2.engines[4].accepted);
    let s3 = s_step(s2, SAction::Write { e: 4 }, v)->Some_0;
    assert(s_step(s2, SAction::Write { e: 4 }, v) is Some);
    assert(s3.post_writers.contains(1) && s3.record == Some(3nat));
    assert(!post_writes_ok(s3));
}

/// W-S3 (F-S3, open question) — setup on Graph_KG (1) stops after its DDL (no record). An engine on
/// Graph_KG is accepted (the marker is there: KNOWN_ISSUES:787-807) and writes. An engine named
/// IVGALT (2) runs setup: held = {Graph_KG}, named, so "explicit" records IVGALT. The Graph_KG engine is
/// never re-checked and keeps writing the shared globals under IVGALT's record. Holds even with
/// serial setups; refused where the explicit path refuses over another schema's marker.
pub proof fn witness_interrupted_setup_then_explicit_schema() {
    let v = SVariant { serial: true, refuse_explicit_over_marker: false, deploy_refusal_aborts: false, cas: false, cas_raises: false };
    let s0 = fresh_ns();
    let s1 = s_step(s0, SAction::NewEngine { e: 1, sch: 1, explicit: false, native_ok: true }, v)->Some_0;
    assert(no_others(s1, 1));
    let s2 = s_step(s1, SAction::SetupRead { p: 1, e: 1 }, v)->Some_0;
    let s3 = s_step(s2, SAction::SetupDdl { p: 1 }, v)->Some_0;
    let s4 = s_step(s3, SAction::SetupAbort { p: 1 }, v)->Some_0;
    assert(s4.record is None && s4.marker.contains(1));
    let s5 = s_step(s4, SAction::Access { e: 1 }, v)->Some_0;
    assert(s_step(s4, SAction::Access { e: 1 }, v) is Some);
    assert(s5.engines[1].accepted);
    let s6 = s_step(s5, SAction::Write { e: 1 }, v)->Some_0;
    assert(s_step(s5, SAction::Write { e: 1 }, v) is Some);
    let s7 = s_step(s6, SAction::NewEngine { e: 2, sch: 2, explicit: true, native_ok: true }, v)->Some_0;
    assert(!no_others(s7, 2)) by { assert(s7.tables.contains(1)); }
    assert(!busy_s(s7)) by {
        assert forall|q: Pid| !s7.setups.contains_key(q) by {}
    }
    let s8 = s_step(s7, SAction::SetupRead { p: 2, e: 2 }, v)->Some_0;
    assert(s_step(s7, SAction::SetupRead { p: 2, e: 2 }, v) is Some);
    assert(s8.setups[2].how == How::Explicit);
    let s9 = s_step(s8, SAction::SetupDdl { p: 2 }, v)->Some_0;
    let s10 = s_step(s9, SAction::SetupDeploy { p: 2 }, v)->Some_0;
    let s11 = s_step(s10, SAction::SetupRecord { p: 2 }, v)->Some_0;
    assert(s_step(s10, SAction::SetupRecord { p: 2 }, v) is Some);
    assert(s11.record == Some(2nat) && s11.engines[1].accepted);
    let s12 = s_step(s11, SAction::Write { e: 1 }, v)->Some_0;
    assert(s_step(s11, SAction::Write { e: 1 }, v) is Some);
    assert(s12.post_writers.contains(1) && s12.record == Some(2nat));
    assert(!post_writes_ok(s12));
    // the proposed refusal stops it at the read
    let w = s_proved();
    assert(marker_elsewhere(s7, 2)) by { assert(s7.marker.contains(1)); }
    assert(s_step(s7, SAction::SetupRead { p: 2, e: 2 }, w) is None);
}

/// W-S4 (F-S8, documented design gap) — a role that cannot read ^IVG.Deploy: the check is skipped and
/// an engine on another schema is accepted and writes.
pub proof fn witness_unreadable_record_skips_the_check() {
    let v = s_as_built();
    let s0 = SSt {
        record: Some(3nat),
        tables: Set::empty().insert(1nat).insert(3nat),
        marker: Set::empty().insert(3nat),
        ..fresh_ns()
    };
    let s1 = s_step(s0, SAction::NewEngine { e: 5, sch: 1, explicit: false, native_ok: false }, v)->Some_0;
    assert(s1.engines[5].accepted);
    let s2 = s_step(s1, SAction::Write { e: 5 }, v)->Some_0;
    assert(s_step(s1, SAction::Write { e: 5 }, v) is Some);
    assert(s2.post_writers.contains(1) && s2.record == Some(3nat));
    assert(!post_writes_ok(s2));
}

// ################################################################################################
// Part 2 — O-WRITE-SURFACE: strict ledger mode on every structural write path
// ################################################################################################
//
// L1 (spec 213 contracts/ledger-api.md:82-92; USER_GUIDE:1107-1120): with the ledger enabled in
// strict mode, a structural write that does not go through the ledger is refused and changes nothing.
// Documented exemptions: BulkLoader and raw SQL (ledger-api.md:92), and the derived row a temporal
// write asserts (USER_GUIDE:1085-1090, ADR-0009). Outside the ledger's scope by decision: embedding,
// vector-index and BM25 writes (ADR-0006:34; spec 213 governs structural writes). Temporal reading: a
// call that begins after set_strict(True) returned must be refused; a call that began before it
// overlaps it and may linearize before it.

pub enum Path {
    /// engine.create_node (nodes_edges.py:1005)
    CreateNode,
    /// engine.execute_cypher with an updating clause → _execute_parsed_sql (query.py:2299-2301). A
    /// transactional SQLQuery carries no var_length_paths (translator.py:6043-6049), so a write cannot take
    /// the var-length route (query.py:2290-2297) before the check.
    CypherDml,
    /// engine.erase_graph / drop_graph / delete_nodes_by_prefix / erase_all (nodes_edges.py:1513,1553,1581)
    EraseGraph,
    /// the rest of the contract list (store_node … load_networkx, the store writers; the temporal
    /// backfill migration writes through create_edge, temporal_structural_rows.py:110)
    OtherGuarded,
    /// engine.bulk_delete_adjacency (nodes_edges.py:2301-2338): Eraser.EraseEdges per graph, no check
    BulkDeleteAdjacency,
    /// api.main POST /api/cypher and GraphQL executeCypher (translator SQL on a raw cursor:
    /// api/routers/cypher.py:130-166, api/gql/schema.py:174-200), and the example updateProtein mutation
    /// (raw rdf_props writes: examples/domains/biomedical/resolver.py:263-275)
    ApiSample,
    /// engine.fhir_graph_sync → Graph.KG.FHIRGraph.SyncOnce (_engine/fhir_graph.py:255-258)
    FhirSync,
    /// Graph.KG.MCPTools.CypherQuery (MCPTools.cls:9-29, %AI builds)
    McpCypher,
    /// upgrade_to_4_0_0 and its steps (migrations/upgrade.py:130-292; rekey_kg_node_stores kills and
    /// rebuilds ^KG, kg_node_stores.py:175-180)
    Migration,
    /// engine.set_multigraph (_engine/admin.py:893)
    SetMultigraph,
    /// the SQL procedures Prop_Set (SqlProcs.cls:187) and Txn_* (168-178) called directly
    PropSetProc,
    /// iris_vector_graph.bulk_loader.BulkLoader (raw connection)
    BulkLoader,
    /// SQL or Native API outside IVG's Python API, MCP RunSQL included (ADMIN_GUIDE:631-636)
    RawSql,
    /// the marked rdf_edges row a temporal write asserts (ADR-0009)
    TemporalDerived,
    /// embedding, vector-index (IVF, VecIndex, PLAID) and BM25 writes
    IndexWrite,
}

/// The classification of each path, from its governing source (NOTES.md Part 2 table).
pub enum PathClass {
    /// the method calls ledger_check / check_structural_write first
    Guarded,
    /// exempt by an accepted source: spec 213 ledger-api.md:92, USER_GUIDE:1085-1090, ADMIN_GUIDE:631-636
    DocumentedExempt,
    /// not a structural write: ADR-0006:34
    OutsideScope,
    /// unguarded, and the 213 contract or USER_GUIDE "the other methods" covers it
    UndocumentedBypass,
    /// unguarded, and no source decides whether strict mode governs it
    Undecided,
}

pub open spec fn class_of(p: Path) -> PathClass {
    match p {
        Path::CreateNode | Path::CypherDml | Path::EraseGraph | Path::OtherGuarded => PathClass::Guarded,
        Path::BulkDeleteAdjacency | Path::ApiSample => PathClass::UndocumentedBypass,
        Path::FhirSync | Path::McpCypher | Path::Migration | Path::SetMultigraph | Path::PropSetProc => PathClass::Undecided,
        Path::BulkLoader | Path::RawSql | Path::TemporalDerived => PathClass::DocumentedExempt,
        Path::IndexWrite => PathClass::OutsideScope,
    }
}

/// L3 binding: the paths that call ledger_check / check_structural_write first.
pub open spec fn guarded(p: Path) -> bool {
    class_of(p) == PathClass::Guarded
}

/// Exempt from strict mode by an accepted source.
pub open spec fn exempt(p: Path) -> bool {
    class_of(p) == PathClass::DocumentedExempt || class_of(p) == PathClass::OutsideScope
}

/// The 213 contract (or USER_GUIDE's "the other methods") covers the path.
pub open spec fn contract_covered(p: Path) -> bool {
    class_of(p) == PathClass::Guarded || class_of(p) == PathClass::UndocumentedBypass
}

/// A call of this path can delete the tenant graph's node rows (its characteristic effect in the model).
pub open spec fn removes_g(p: Path) -> bool {
    match p {
        Path::EraseGraph | Path::ApiSample | Path::McpCypher | Path::RawSql => true,
        _ => false,
    }
}

/// LedgerGuard's cached probe (guard.py:27-28, 57-58).
pub struct Cache {
    pub strict: bool,
    pub at: nat,
}

pub struct Call {
    pub path: Path,
    /// ghost: the ledger was enabled and strict when the call began
    pub started_strict: bool,
}

pub struct GSt {
    /// ^IVG.Ledger("meta","state") = "enabled"
    pub enabled: bool,
    /// ^IVG.Ledger("meta","strict")
    pub strict: bool,
    /// time.monotonic(), seconds
    pub now: nat,
    /// each engine's LedgerGuard cache (one guard per engine object: _engine/ledger.py:30-38)
    pub cache: Map<Eid, Cache>,
    /// engines whose guard has computed _class_present (guard.py:45-49; kept for the guard's lifetime)
    pub known: Set<Eid>,
    /// engines whose guard found Graph.KG.Ledger absent on its first probe: they never read Meta() again
    pub blind: Set<Eid>,
    /// calls past their check, not yet committed
    pub calls: Map<nat, Call>,
    /// ghost: unrecorded structural writes committed, with their path and started_strict
    pub log: Seq<(Path, bool)>,
    /// rej_strict_block (count_rejection)
    pub refusals: nat,
    /// the tenant's named graph G: its node rows and edge rows (LedgerRedact.LiveRows counts these)
    pub g_nodes: nat,
    pub g_edges: nat,
    pub redacted: bool,
}

pub enum GAction {
    /// a write call's entry: guarded paths run LedgerGuard.check_structural_write first (guard.py:75-80).
    /// probe_ok = false: the Meta() probe raised (fail-open, guard.py:55-56). class_present: what
    /// compiled_class_exists answers if this is the guard's first probe (guard.py:45-49).
    Begin { c: nat, e: Eid, path: Path, probe_ok: bool, class_present: bool },
    /// the call's write commits
    Commit { c: nat },
    /// the call fails and rolls back
    Abort { c: nat },
    /// engine.ledger.set_strict(flag) through engine e (client.py:305-309 → Ledger.SetStrict, refresh e's guard)
    SetStrict { e: Eid, flag: bool },
    /// engine.ledger.enable(strict=flag) (client.py:281-297)
    Enable { e: Eid, flag: bool },
    /// engine.ledger.disable() (client.py:299-303)
    Disable { e: Eid },
    Tick { d: nat },
    /// a changeset create_relationship(..., graph=G): EnsureEndpoint writes both endpoints' node rows
    /// in G (LedgerApply.cls:97-110), the relationship row in G
    LedgerCreateRelInG,
    /// a changeset delete_relationship of one of G's relationships (LedgerApply.cls:643-648)
    LedgerDeleteRelInG,
    /// a changeset delete_node: default-graph rows only (OpDeleteNode, DeleteNodeRows: LedgerApply.cls:357-367, 374-385)
    LedgerDeleteNode,
    /// ledger.redact(G) (LedgerRedact.Redact: LiveRows must be 0, LedgerRedact.cls:203-210)
    Redact,
}

/// `ttl`: LedgerGuard.TTL_SECONDS (guard.py:20). `guard_all`: every non-exempt path checks (proposal).
pub struct GVariant {
    pub ttl: nat,
    pub guard_all: bool,
}

pub open spec fn g_as_built() -> GVariant {
    GVariant { ttl: 5, guard_all: false }
}

pub open spec fn guarded_v(p: Path, v: GVariant) -> bool {
    guarded(p) || (v.guard_all && !exempt(p))
}

/// Ledger.Meta(): state "enabled" and strict (guard.py:69-71)
pub open spec fn meta_strict(s: GSt) -> bool {
    s.enabled && s.strict
}

pub open spec fn cache_live(s: GSt, e: Eid, v: GVariant) -> bool {
    s.cache.contains_key(e) && s.now < s.cache[e].at + v.ttl
}

/// The guard's blind set after a probe: a first probe that finds the class absent caches False forever.
pub open spec fn blind_after(s: GSt, e: Eid, class_present: bool) -> Set<Eid> {
    if !s.known.contains(e) && !class_present { s.blind.insert(e) } else { s.blind }
}

/// LedgerGuard._probe then is_strict: the cached value inside the TTL, else a fresh probe; a guard that
/// cached "class absent" answers "never-enabled"; a failed probe answers "never-enabled". Both are cached.
pub open spec fn probe_value(s: GSt, e: Eid, probe_ok: bool, class_present: bool) -> bool {
    !blind_after(s, e, class_present).contains(e) && probe_ok && meta_strict(s)
}

pub open spec fn seen_strict(s: GSt, e: Eid, probe_ok: bool, class_present: bool, v: GVariant) -> bool {
    if cache_live(s, e, v) { s.cache[e].strict } else { probe_value(s, e, probe_ok, class_present) }
}

/// The guard state after the check of a call (the probe runs only outside the TTL).
pub open spec fn after_check(s: GSt, e: Eid, probe_ok: bool, class_present: bool, v: GVariant) -> GSt {
    if cache_live(s, e, v) {
        s
    } else {
        GSt {
            cache: s.cache.insert(e, Cache { strict: probe_value(s, e, probe_ok, class_present), at: s.now }),
            blind: blind_after(s, e, class_present),
            known: s.known.insert(e),
            ..s
        }
    }
}

pub open spec fn commit_effect(s: GSt, p: Path) -> GSt {
    match p {
        Path::EraseGraph | Path::ApiSample | Path::McpCypher | Path::RawSql => GSt { g_nodes: 0, g_edges: 0, ..s },
        Path::BulkDeleteAdjacency => GSt { g_edges: 0, ..s },
        _ => s,
    }
}

pub open spec fn g_step(s: GSt, a: GAction, v: GVariant) -> Option<GSt> {
    match a {
        GAction::Begin { c, e, path, probe_ok, class_present } =>
            if s.calls.contains_key(c) {
                None
            } else if guarded_v(path, v) {
                let s1 = after_check(s, e, probe_ok, class_present, v);
                if seen_strict(s, e, probe_ok, class_present, v) {
                    // LedgerStrictModeError: nothing written, the rejection counted
                    Some(GSt { refusals: s.refusals + 1, ..s1 })
                } else {
                    Some(GSt { calls: s.calls.insert(c, Call { path, started_strict: meta_strict(s) }), ..s1 })
                }
            } else {
                Some(GSt { calls: s.calls.insert(c, Call { path, started_strict: meta_strict(s) }), ..s })
            },
        GAction::Commit { c } =>
            if !s.calls.contains_key(c) {
                None
            } else {
                let call = s.calls[c];
                let s1 = commit_effect(s, call.path);
                Some(GSt { log: s.log.push((call.path, call.started_strict)), calls: s.calls.remove(c), ..s1 })
            },
        GAction::Abort { c } =>
            if !s.calls.contains_key(c) { None } else { Some(GSt { calls: s.calls.remove(c), ..s }) },
        GAction::SetStrict { e, flag } => Some(GSt { strict: flag, cache: s.cache.remove(e), ..s }),
        GAction::Enable { e, flag } => Some(GSt { enabled: true, strict: flag, cache: s.cache.remove(e), ..s }),
        GAction::Disable { e } => Some(GSt { enabled: false, cache: s.cache.remove(e), ..s }),
        GAction::Tick { d } => Some(GSt { now: s.now + d, ..s }),
        GAction::LedgerCreateRelInG =>
            if !s.enabled { None } else { Some(GSt { g_nodes: s.g_nodes + 2, g_edges: s.g_edges + 1, ..s }) },
        GAction::LedgerDeleteRelInG =>
            if !s.enabled || s.g_edges == 0 { None } else { Some(GSt { g_edges: (s.g_edges - 1) as nat, ..s }) },
        GAction::LedgerDeleteNode =>
            if !s.enabled { None } else { Some(s) },
        GAction::Redact =>
            if !s.enabled || s.g_nodes + s.g_edges > 0 { None } else { Some(GSt { redacted: true, ..s }) },
    }
}

// ---------------------------------------------------------------------------------------- L1

/// L1 as the 213 contract and USER_GUIDE state it: no unrecorded write from a call that began under
/// strict mode, on a path the contract covers (guarded or undocumented bypass).
pub open spec fn strict_ok(s: GSt) -> bool {
    forall|i: int| 0 <= i < s.log.len() && (#[trigger] s.log[i]).1 ==> !contract_covered(s.log[i].0)
}

/// L1 under the reading "strict mode governs every structural write path but the exempt ones": the
/// undecided paths count too.
pub open spec fn strict_ok_all(s: GSt) -> bool {
    forall|i: int| 0 <= i < s.log.len() && (#[trigger] s.log[i]).1 ==> exempt(s.log[i].0)
}

pub proof fn lemma_strict_ok_all_implies_strict_ok(s: GSt)
    requires strict_ok_all(s),
    ensures strict_ok(s),
{
    assert forall|i: int| 0 <= i < s.log.len() && (#[trigger] s.log[i]).1 implies !contract_covered(s.log[i].0) by {
        assert(exempt(s.log[i].0));
    }
}

pub open spec fn g_inv(s: GSt, v: GVariant) -> bool {
    &&& strict_ok_all(s)
    &&& forall|c: nat| #[trigger] s.calls.contains_key(c) && s.calls[c].started_strict ==> exempt(s.calls[c].path)
    &&& forall|e: Eid| #[trigger] s.cache.contains_key(e) && s.now < s.cache[e].at + v.ttl ==> s.cache[e].strict == meta_strict(s)
    &&& forall|e: Eid| !(#[trigger] s.blind.contains(e))
}

/// no engine other than e holds a live cache that disagrees with the new meta value m
pub open spec fn others_current(s: GSt, e: Eid, m: bool, v: GVariant) -> bool {
    forall|x: Eid| #[trigger] s.cache.contains_key(x) && x != e && s.now < s.cache[x].at + v.ttl ==> s.cache[x].strict == m
}

/// Premises (NOTES.md): P-PROBE-OK (the Meta probe answers and the ledger class is compiled when a guard
/// first probes), P-NO-STALE-CACHE (strict/enable/disable change while no other engine holds a live cache
/// of the old value; vacuous with ttl = 0 or one engine), P-PATHS (a call takes a checked path or an
/// exempt one; vacuous with guard_all).
pub open spec fn g_premise(s: GSt, a: GAction, v: GVariant) -> bool {
    match a {
        GAction::Begin { path, probe_ok, class_present, .. } => probe_ok && class_present && (guarded_v(path, v) || exempt(path)),
        GAction::SetStrict { e, flag } => others_current(s, e, s.enabled && flag, v),
        GAction::Enable { e, flag } => others_current(s, e, flag, v),
        GAction::Disable { e } => others_current(s, e, false, v),
        _ => true,
    }
}

pub proof fn lemma_g_step_preserves_inv(s: GSt, a: GAction, v: GVariant)
    requires
        g_inv(s, v),
        g_premise(s, a, v),
        g_step(s, a, v) is Some,
    ensures
        g_inv(g_step(s, a, v)->Some_0, v),
{
    let s2 = g_step(s, a, v)->Some_0;
    match a {
        GAction::Begin { c, e, path, probe_ok, class_present } => {
            if guarded_v(path, v) {
                assert(!blind_after(s, e, class_present).contains(e));
                assert(seen_strict(s, e, probe_ok, class_present, v) == meta_strict(s));
                assert forall|x: Eid| #[trigger] s2.cache.contains_key(x) && s2.now < s2.cache[x].at + v.ttl implies s2.cache[x].strict == meta_strict(s2) by {
                    if !cache_live(s, e, v) && x == e {
                    } else {
                        assert(s.cache.contains_key(x));
                    }
                }
                assert forall|x: Eid| !(#[trigger] s2.blind.contains(x)) by {
                    assert(!s.blind.contains(x));
                }
            }
            assert forall|k: nat| #[trigger] s2.calls.contains_key(k) && s2.calls[k].started_strict implies exempt(s2.calls[k].path) by {
                if k != c {
                    assert(s.calls.contains_key(k));
                }
            }
        }
        GAction::Commit { c } => {
            let call = s.calls[c];
            assert forall|i: int| 0 <= i < s2.log.len() && (#[trigger] s2.log[i]).1 implies exempt(s2.log[i].0) by {
                if i < s.log.len() {
                    assert(s2.log[i] == s.log[i]);
                } else {
                    assert(s2.log[i] == (call.path, call.started_strict));
                }
            }
            assert forall|k: nat| #[trigger] s2.calls.contains_key(k) && s2.calls[k].started_strict implies exempt(s2.calls[k].path) by {
                assert(s.calls.contains_key(k));
            }
        }
        GAction::Abort { c } => {
            assert forall|k: nat| #[trigger] s2.calls.contains_key(k) && s2.calls[k].started_strict implies exempt(s2.calls[k].path) by {
                assert(s.calls.contains_key(k));
            }
        }
        GAction::SetStrict { e, flag } => {
            assert forall|x: Eid| #[trigger] s2.cache.contains_key(x) && s2.now < s2.cache[x].at + v.ttl implies s2.cache[x].strict == meta_strict(s2) by {
                assert(s.cache.contains_key(x) && x != e);
            }
            assert forall|k: nat| #[trigger] s2.calls.contains_key(k) && s2.calls[k].started_strict implies exempt(s2.calls[k].path) by {
                assert(s.calls.contains_key(k));
            }
        }
        GAction::Enable { e, flag } => {
            assert forall|x: Eid| #[trigger] s2.cache.contains_key(x) && s2.now < s2.cache[x].at + v.ttl implies s2.cache[x].strict == meta_strict(s2) by {
                assert(s.cache.contains_key(x) && x != e);
            }
        }
        GAction::Disable { e } => {
            assert forall|x: Eid| #[trigger] s2.cache.contains_key(x) && s2.now < s2.cache[x].at + v.ttl implies s2.cache[x].strict == meta_strict(s2) by {
                assert(s.cache.contains_key(x) && x != e);
            }
        }
        GAction::Tick { d } => {
            assert forall|x: Eid| #[trigger] s2.cache.contains_key(x) && s2.now < s2.cache[x].at + v.ttl implies s2.cache[x].strict == meta_strict(s2) by {
                assert(s.cache.contains_key(x) && s.now < s.cache[x].at + v.ttl);
            }
        }
        _ => {}
    }
}

/// With the cache disabled (ttl = 0) the stale-cache premise holds of every state whose cache entries
/// were filled at or before now (every reachable state: entries are written with at = now, and now
/// only grows).
pub proof fn lemma_ttl0_needs_no_cache_premise(s: GSt, e: Eid, m: bool)
    requires forall|x: Eid| #[trigger] s.cache.contains_key(x) ==> s.cache[x].at <= s.now,
    ensures others_current(s, e, m, GVariant { ttl: 0, guard_all: false }),
{
}

/// The inventory theorem: under strict mode, with a fresh probe of a present class, a guarded path is
/// refused and writes nothing; an unguarded path is admitted, and its write breaks the contract's L1
/// exactly when it is an undocumented bypass, and the all-paths reading exactly when it is not exempt.
pub proof fn theorem_strict_paths(s: GSt, p: Path, c: nat, e: Eid)
    requires
        meta_strict(s),
        !s.calls.contains_key(c),
        !s.cache.contains_key(e),
        !s.blind.contains(e),
        strict_ok_all(s),
    ensures
        g_step(s, GAction::Begin { c, e, path: p, probe_ok: true, class_present: true }, g_as_built()) is Some,
        guarded(p) ==> ({
            let s1 = g_step(s, GAction::Begin { c, e, path: p, probe_ok: true, class_present: true }, g_as_built())->Some_0;
            &&& !s1.calls.contains_key(c)
            &&& s1.log == s.log && s1.g_nodes == s.g_nodes && s1.g_edges == s.g_edges
            &&& s1.refusals == s.refusals + 1
        }),
        !guarded(p) ==> ({
            let s1 = g_step(s, GAction::Begin { c, e, path: p, probe_ok: true, class_present: true }, g_as_built())->Some_0;
            let s2 = g_step(s1, GAction::Commit { c }, g_as_built())->Some_0;
            &&& g_step(s1, GAction::Commit { c }, g_as_built()) is Some
            &&& s2.log.last() == (p, true)
            &&& (strict_ok(s2) <==> class_of(p) != PathClass::UndocumentedBypass)
            &&& (strict_ok_all(s2) <==> exempt(p))
        }),
{
    let v = g_as_built();
    if guarded(p) {
        assert(!blind_after(s, e, true).contains(e));
    } else {
        let s1 = g_step(s, GAction::Begin { c, e, path: p, probe_ok: true, class_present: true }, v)->Some_0;
        let s2 = g_step(s1, GAction::Commit { c }, v)->Some_0;
        assert(s1.calls.contains_key(c) && s1.calls[c] == Call { path: p, started_strict: true });
        assert(s2.log == s.log.push((p, true)));
        lemma_strict_ok_all_implies_strict_ok(s);
        let i = s.log.len() as int;
        assert(s2.log[i] == (p, true));
        if exempt(p) {
            assert forall|k: int| 0 <= k < s2.log.len() && (#[trigger] s2.log[k]).1 implies exempt(s2.log[k].0) by {
                if k < s.log.len() { assert(s2.log[k] == s.log[k]); }
            }
        }
        if class_of(p) != PathClass::UndocumentedBypass {
            assert forall|k: int| 0 <= k < s2.log.len() && (#[trigger] s2.log[k]).1 implies !contract_covered(s2.log[k].0) by {
                if k < s.log.len() { assert(s2.log[k] == s.log[k]); }
            }
        }
    }
}

// ---------------------------------------------------------------------------------------- witnesses

pub open spec fn g_start() -> GSt {
    GSt {
        enabled: true,
        strict: false,
        now: 0,
        cache: Map::empty(),
        known: Set::empty(),
        blind: Set::empty(),
        calls: Map::empty(),
        log: Seq::empty(),
        refusals: 0,
        g_nodes: 0,
        g_edges: 0,
        redacted: false,
    }
}

/// A one-call write under strict mode by a fresh engine on path p.
pub open spec fn strict_write(p: Path) -> GSt {
    let v = g_as_built();
    let s0 = GSt { strict: true, ..g_start() };
    let s1 = g_step(s0, GAction::Begin { c: 1, e: 1, path: p, probe_ok: true, class_present: true }, v)->Some_0;
    g_step(s1, GAction::Commit { c: 1 }, v)->Some_0
}

/// The USER_GUIDE example (1112-1120), a valid outcome: the engine that turned strict on is refused
/// at once (set_strict refreshes its own guard) and nothing is written.
pub proof fn witness_user_guide_strict_example() {
    let v = g_as_built();
    let s0 = g_start();
    let s1 = g_step(s0, GAction::Begin { c: 1, e: 1, path: Path::CreateNode, probe_ok: true, class_present: true }, v)->Some_0;
    let s2 = g_step(s1, GAction::Commit { c: 1 }, v)->Some_0;
    assert(s1.cache.contains_key(1) && s1.calls.contains_key(1));
    let s3 = g_step(s2, GAction::SetStrict { e: 1, flag: true }, v)->Some_0;
    let s4 = g_step(s3, GAction::Begin { c: 2, e: 1, path: Path::CreateNode, probe_ok: true, class_present: true }, v)->Some_0;
    assert(!cache_live(s3, 1, v));
    assert(!blind_after(s3, 1, true).contains(1));
    assert(!s4.calls.contains_key(2) && s4.refusals == 1 && s4.log == s3.log);
}

/// W-TTL — two engines (two processes, or two engine objects in one). Engine 2 has probed "not strict"
/// at t=0. Engine 1 turns strict on at t=1; engine 2's guard answers from its cache until t=5, so its
/// create_node at t=2 is admitted and commits unrecorded. At t=6 the same call is refused.
/// Observed natively: receipts/native/platform_strict_ttl.json.
pub proof fn witness_ttl_window_admits_a_write_after_set_strict() {
    let v = g_as_built();
    let s0 = g_start();
    let s1 = g_step(s0, GAction::Begin { c: 1, e: 2, path: Path::CreateNode, probe_ok: true, class_present: true }, v)->Some_0;
    let s2 = g_step(s1, GAction::Commit { c: 1 }, v)->Some_0;
    assert(s1.calls.contains_key(1));
    assert(s2.cache.contains_key(2) && s2.cache[2] == Cache { strict: false, at: 0 });
    let s3 = g_step(s2, GAction::Tick { d: 1 }, v)->Some_0;
    let s4 = g_step(s3, GAction::SetStrict { e: 1, flag: true }, v)->Some_0;
    assert(meta_strict(s4));
    let s5 = g_step(s4, GAction::Tick { d: 1 }, v)->Some_0;
    assert(cache_live(s5, 2, v));
    let s6 = g_step(s5, GAction::Begin { c: 2, e: 2, path: Path::CreateNode, probe_ok: true, class_present: true }, v)->Some_0;
    assert(s6.calls.contains_key(2) && s6.calls[2].started_strict);
    let s7 = g_step(s6, GAction::Commit { c: 2 }, v)->Some_0;
    assert(s7.log[1] == (Path::CreateNode, true));
    assert(!strict_ok(s7));
    let s8 = g_step(s7, GAction::Tick { d: 4 }, v)->Some_0;
    assert(!cache_live(s8, 2, v));
    assert(!blind_after(s8, 2, true).contains(2));
    let s9 = g_step(s8, GAction::Begin { c: 3, e: 2, path: Path::CreateNode, probe_ok: true, class_present: true }, v)->Some_0;
    assert(!s9.calls.contains_key(3) && s9.refusals == s8.refusals + 1);
}

/// W-FAILOPEN — the probe cannot run (a role refused the Meta call): the guard answers "never-enabled"
/// and a guarded write is admitted under strict mode (retried after the TTL).
pub proof fn witness_failed_probe_admits_a_write() {
    let v = g_as_built();
    let s0 = GSt { strict: true, ..g_start() };
    let s1 = g_step(s0, GAction::Begin { c: 1, e: 1, path: Path::CreateNode, probe_ok: false, class_present: true }, v)->Some_0;
    assert(s1.calls.contains_key(1) && s1.calls[1].started_strict);
    let s2 = g_step(s1, GAction::Commit { c: 1 }, v)->Some_0;
    assert(s2.log[0] == (Path::CreateNode, true));
    assert(!strict_ok(s2));
}

/// W-CLASS — `_class_present` is computed once per guard and kept (guard.py:45-49). An engine whose
/// first guarded call ran while Graph.KG.Ledger was not compiled (a failed best-effort deploy, setup
/// with auto_deploy_objectscript=False) never reads Meta() again: after the class is deployed and strict
/// is on, its writes are admitted past every TTL. A new engine is refused.
pub proof fn witness_class_absent_cached_for_the_engines_lifetime() {
    let v = g_as_built();
    let s0 = g_start();
    let s1 = g_step(s0, GAction::Begin { c: 1, e: 3, path: Path::CreateNode, probe_ok: true, class_present: false }, v)->Some_0;
    assert(s1.blind.contains(3) && s1.known.contains(3));
    let s2 = g_step(s1, GAction::Commit { c: 1 }, v)->Some_0;
    let s3 = g_step(s2, GAction::SetStrict { e: 1, flag: true }, v)->Some_0;
    let s4 = g_step(s3, GAction::Tick { d: 10 }, v)->Some_0;
    assert(!cache_live(s4, 3, v) && s4.blind.contains(3) && meta_strict(s4));
    let s5 = g_step(s4, GAction::Begin { c: 2, e: 3, path: Path::CreateNode, probe_ok: true, class_present: true }, v)->Some_0;
    assert(s5.calls.contains_key(2) && s5.calls[2].started_strict);
    let s6 = g_step(s5, GAction::Commit { c: 2 }, v)->Some_0;
    assert(s6.log[1] == (Path::CreateNode, true));
    assert(!strict_ok(s6));
    // a fresh engine is refused
    assert(!blind_after(s6, 4, true).contains(4));
    let s7 = g_step(s6, GAction::Begin { c: 3, e: 4, path: Path::CreateNode, probe_ok: true, class_present: true }, v)->Some_0;
    assert(!s7.calls.contains_key(3) && s7.refusals == s6.refusals + 1);
}

/// A write that passed its check before set_strict(True) and commits after it: permitted (the call
/// overlapped the switch). The model keeps it apart from the TTL case.
pub proof fn witness_write_overlapping_set_strict_is_permitted() {
    let v = g_as_built();
    let s0 = g_start();
    let s1 = g_step(s0, GAction::Begin { c: 1, e: 1, path: Path::CypherDml, probe_ok: true, class_present: true }, v)->Some_0;
    let s2 = g_step(s1, GAction::SetStrict { e: 2, flag: true }, v)->Some_0;
    assert(s2.calls.contains_key(1));
    let s3 = g_step(s2, GAction::Commit { c: 1 }, v)->Some_0;
    assert(s3.log[0] == (Path::CypherDml, false));
    assert(strict_ok_all(s3)) by {
        assert forall|i: int| 0 <= i < s3.log.len() && (#[trigger] s3.log[i]).1 implies exempt(s3.log[i].0) by {
            assert(i == 0);
        }
    }
}

/// The undocumented bypasses: under strict mode bulk_delete_adjacency deletes the tenant graph's edges
/// unrecorded, and the api.main sample's Cypher write commits; both break the contract's L1.
/// Observed natively: receipts/native/platform_strict_{bulk_delete_adjacency,api_sample}.json.
pub proof fn witness_undocumented_bypasses_break_the_contract() {
    let v = g_as_built();
    let s0 = GSt { strict: true, g_nodes: 2, g_edges: 1, ..g_start() };
    let s1 = g_step(s0, GAction::Begin { c: 1, e: 1, path: Path::BulkDeleteAdjacency, probe_ok: true, class_present: true }, v)->Some_0;
    assert(s1.calls.contains_key(1));
    let s2 = g_step(s1, GAction::Commit { c: 1 }, v)->Some_0;
    assert(s2.g_edges == 0 && s2.log[0] == (Path::BulkDeleteAdjacency, true));
    assert(!strict_ok(s2));
    let w = strict_write(Path::ApiSample);
    assert(w.log[0] == (Path::ApiSample, true));
    assert(!strict_ok(w));
}

/// The undecided paths (FHIR sync, MCP CypherQuery, migrations, set_multigraph, Prop_Set/Txn_*): under
/// strict mode their writes commit. The contract as written is silent (strict_ok holds); the all-paths
/// reading is broken. Marking any of them exempt, or covered, makes this witness fail.
pub proof fn witness_undecided_paths_write_under_strict() {
    let f = strict_write(Path::FhirSync);
    assert(f.log[0] == (Path::FhirSync, true));
    assert(strict_ok(f)) by {
        assert forall|i: int| 0 <= i < f.log.len() && (#[trigger] f.log[i]).1 implies !contract_covered(f.log[i].0) by {
            assert(i == 0);
        }
    }
    assert(!strict_ok_all(f));
    let m = strict_write(Path::McpCypher);
    assert(m.log[0] == (Path::McpCypher, true));
    assert(!strict_ok_all(m));
    let g = strict_write(Path::Migration);
    assert(g.log[0] == (Path::Migration, true));
    assert(!strict_ok_all(g));
    let x = strict_write(Path::SetMultigraph);
    assert(x.log[0] == (Path::SetMultigraph, true));
    assert(!strict_ok_all(x));
    let y = strict_write(Path::PropSetProc);
    assert(y.log[0] == (Path::PropSetProc, true));
    assert(!strict_ok_all(y));
}

/// Writes outside the ledger's scope (embeddings, vector indexes, BM25) and the documented exemptions
/// (BulkLoader, raw SQL with MCP RunSQL, the derived temporal row) commit under strict mode without
/// breaking either reading of L1.
pub proof fn witness_exempt_and_out_of_scope_writes_are_permitted() {
    let i = strict_write(Path::IndexWrite);
    assert(i.log[0] == (Path::IndexWrite, true));
    assert(strict_ok_all(i)) by {
        assert forall|k: int| 0 <= k < i.log.len() && (#[trigger] i.log[k]).1 implies exempt(i.log[k].0) by { assert(k == 0); }
    }
    let r = strict_write(Path::RawSql);
    assert(r.log[0] == (Path::RawSql, true));
    assert(strict_ok_all(r)) by {
        assert forall|k: int| 0 <= k < r.log.len() && (#[trigger] r.log[k]).1 implies exempt(r.log[k].0) by { assert(k == 0); }
    }
    let b = strict_write(Path::BulkLoader);
    assert(b.log[0] == (Path::BulkLoader, true));
    assert(strict_ok_all(b)) by {
        assert forall|k: int| 0 <= k < b.log.len() && (#[trigger] b.log[k]).1 implies exempt(b.log[k].0) by { assert(k == 0); }
    }
}

// ---------------------------------------------------------------------------------------- erasure vs strict

/// While the ledger stays strict: the tenant graph has a node row and no call that could delete it is
/// in flight.
pub open spec fn locked(s: GSt) -> bool {
    &&& meta_strict(s)
    &&& s.g_nodes > 0
    &&& forall|c: nat| #[trigger] s.calls.contains_key(c) ==> !removes_g(s.calls[c].path)
}

/// Steps that keep strict on and use only engine methods and the ledger (no SQL or Native API
/// deletion, no api.main or MCP Cypher).
pub open spec fn keeps_strict(a: GAction) -> bool {
    match a {
        GAction::SetStrict { flag, .. } => flag,
        GAction::Enable { flag, .. } => flag,
        GAction::Disable { .. } => false,
        GAction::Begin { path, .. } => guarded(path) || !removes_g(path),
        _ => true,
    }
}

/// Consequence of ADR-0013's order (erase, then redact) under strict mode: erase_graph is refused, the
/// ledger deletes node rows of the default graph only, so a named graph that holds a node row stays
/// live and its redaction is refused (target_live) at every step until strict is turned off.
/// Observed natively: receipts/native/platform_strict_redaction.json.
pub proof fn theorem_strict_blocks_named_graph_redaction(s: GSt, a: GAction)
    requires
        g_inv(s, g_as_built()),
        g_premise(s, a, g_as_built()),
        locked(s),
        keeps_strict(a),
        g_step(s, a, g_as_built()) is Some,
    ensures
        locked(g_step(s, a, g_as_built())->Some_0),
        g_step(s, GAction::Redact, g_as_built()) is None,
{
    let v = g_as_built();
    let s2 = g_step(s, a, v)->Some_0;
    match a {
        GAction::Begin { c, e, path, probe_ok, class_present } => {
            if guarded(path) {
                assert(!blind_after(s, e, class_present).contains(e));
                assert(seen_strict(s, e, probe_ok, class_present, v) == meta_strict(s));
            }
            assert forall|k: nat| #[trigger] s2.calls.contains_key(k) implies !removes_g(s2.calls[k].path) by {
                if k != c { assert(s.calls.contains_key(k)); }
            }
        }
        GAction::Commit { c } => {
            assert(s.calls.contains_key(c));
            assert forall|k: nat| #[trigger] s2.calls.contains_key(k) implies !removes_g(s2.calls[k].path) by {
                assert(s.calls.contains_key(k));
            }
        }
        GAction::Abort { c } => {
            assert forall|k: nat| #[trigger] s2.calls.contains_key(k) implies !removes_g(s2.calls[k].path) by {
                assert(s.calls.contains_key(k));
            }
        }
        _ => {}
    }
}

/// The documented order needs strict off: under strict, erase_graph(G) is refused; the ledger can
/// delete G's relationships but not G's node rows, so redact(G) is refused. Turning strict off lets the
/// erase and the redaction run — and, in that window, another engine's unrecorded write is admitted.
pub proof fn witness_strict_erase_then_redact_needs_strict_off() {
    let v = g_as_built();
    let s0 = g_start();
    let s1 = g_step(s0, GAction::LedgerCreateRelInG, v)->Some_0;
    let s2 = g_step(s1, GAction::SetStrict { e: 1, flag: true }, v)->Some_0;
    assert(s2.g_nodes == 2 && s2.g_edges == 1 && meta_strict(s2));
    assert(!blind_after(s2, 1, true).contains(1));
    let s3 = g_step(s2, GAction::Begin { c: 1, e: 1, path: Path::EraseGraph, probe_ok: true, class_present: true }, v)->Some_0;
    assert(!s3.calls.contains_key(1) && s3.g_nodes == 2);
    let s4 = g_step(s3, GAction::LedgerDeleteRelInG, v)->Some_0;
    let s5 = g_step(s4, GAction::LedgerDeleteNode, v)->Some_0;
    assert(s5.g_edges == 0 && s5.g_nodes == 2);
    assert(g_step(s5, GAction::Redact, v) is None);
    // strict off: the erase runs, the redaction completes
    let s6 = g_step(s5, GAction::SetStrict { e: 1, flag: false }, v)->Some_0;
    let s7 = g_step(s6, GAction::Begin { c: 2, e: 1, path: Path::EraseGraph, probe_ok: true, class_present: true }, v)->Some_0;
    assert(s7.calls.contains_key(2));
    // the window: another engine's create_node is admitted and not recorded
    let s8 = g_step(s7, GAction::Begin { c: 3, e: 2, path: Path::CreateNode, probe_ok: true, class_present: true }, v)->Some_0;
    assert(s8.calls.contains_key(3));
    let s9 = g_step(s8, GAction::Commit { c: 2 }, v)->Some_0;
    let s10 = g_step(s9, GAction::Commit { c: 3 }, v)->Some_0;
    assert(s9.calls.contains_key(3));
    assert(s10.g_nodes == 0 && s10.g_edges == 0);
    let s11 = g_step(s10, GAction::Redact, v)->Some_0;
    assert(g_step(s10, GAction::Redact, v) is Some);
    assert(s11.redacted && s11.log[1] == (Path::CreateNode, false));
}

// ################################################################################################
// Part 3 — O2 (cypher): a compiled class runs only for its own plan
// ################################################################################################
//
// L1 (ADR-0014:16-23; CONTEXT "Compiled plan"; spec 257 US1): a compiled class answers exactly as
// the interpreter does, so it runs only for the shape and the build stamp it was written for; "a stale
// entry is never run; its shape is built again"; a deploy discards every compiled plan; a missing,
// pending, failed or unrecordable entry means the interpreter answers. As a run-level property: every
// Walk1 a run executes is the code written for that run's (shape, stamp).

pub type Shape = int;
pub type Stamp = nat;

/// $ZCRC(tShape, 7) (Gen.cls:69): a 32-bit checksum of the shape's $ListBuild text.
pub uninterp spec fn crc32(s: Shape) -> u32;
/// Gen.Lines: the Walk1 body For writes (Gen.cls:83). A function of the shape and of the rdf_props
/// layout baked into it (Gen.Check / Emission read ^||IVG.CypherProps("index"|"data"|"slot"),
/// Gen.cls:498, 545); the layout is a component of the stamp, so the model indexes lines by stamp.
pub uninterp spec fn lines_of(s: Shape, st: Stamp) -> int;
/// Gen.Digest: SHA-256 of the lines (Gen.cls:147-156).
pub uninterp spec fn digest(l: int) -> int;

/// the hash, and the name IVGC.P<h> (Gen.cls:69, 183): classes are keyed by it
pub open spec fn hash_of(s: Shape) -> int {
    crc32(s) as int
}

pub enum Status {
    Pending,
    Ok,
    /// a failed compile, a refused build (lines not the ones written), a shape not written
    Failed,
}

/// A compiled class's name: IVGC.P<h> as built (h = CRC-32 of the shape, Gen.cls:183), IVGC.D<n> under
/// the proposed repair (n = the SHA-256 of the lines For computes anyway, Gen.cls:91), or any other class.
pub enum CName {
    P(int),
    D(int),
    Other(int),
}

/// ^IVG.CypherCompiled(h) = $LB(class, shape, stamp, status, builtAt)
pub struct Entry {
    pub cls: Option<CName>,
    pub shape: Shape,
    pub stamp: Stamp,
    pub status: Status,
    pub at: nat,
}

/// A compiled class (keyed by its CName). Ghost: the shape and stamp its lines were written for.
pub struct Code {
    pub lines: int,
    pub shape: Shape,
    pub stamp: Stamp,
}

/// A run's progress through Exec.RunA's one call of Gen.For (Exec.cls:156-166):
///   Check (Gen.cls:69-77) → Write1 → [80] → Write2 → [81-91] → Write3 → [92-100 job | 101 sync]
///   → Inline → [Build] → ReadBack → [102-103] → Running (Walk1 per anchor: Exec.cls:199, 258)
pub enum RPhase {
    Check,
    Write1,
    Write2,
    Write3,
    Inline,
    ReadBack,
    Running,
}

pub struct Run {
    pub shape: Shape,
    /// Gen.Stamp(): the rdf_props layout this run's Props.Begin read | Exec.BuiltAt | Gen.BuiltAt
    pub stamp: Stamp,
    /// mode "sync" (else "job")
    pub sync: bool,
    pub phase: RPhase,
    /// tGen: the class this run walks with, None = interpreted
    pub gen: Option<CName>,
    /// tDigest
    pub digest: int,
    /// a Walk1 raised (<CLASS DOES NOT EXIST> after a drop): Run re-throws, the read goes to the SQL path
    pub failed: bool,
}

/// A jobbed Gen.Build(tH, tDigest); ghost: the shape and stamp of the For that spawned it.
pub struct Job {
    pub h: int,
    pub d: int,
    pub shape: Shape,
    pub stamp: Stamp,
}

pub struct PSt {
    pub entries: Map<int, Entry>,
    /// ^IVG.CypherCompiled(h, "src")
    pub src: Map<int, int>,
    pub classes: Map<CName, Code>,
    pub runs: Map<nat, Run>,
    pub jobs: Map<nat, Job>,
    /// the stamp a run beginning now reads
    pub stamp: Stamp,
    /// Gen.Now(), seconds
    pub now: nat,
    /// ghost: every shape a run has presented
    pub presented: Set<Shape>,
    /// ghost: each Walk1 executed: the run's shape and stamp and the lines that ran
    pub execs: Seq<(Shape, Stamp, int)>,
}

pub enum PAction {
    RunBegin { r: nat, shape: Shape, sync: bool },
    ForCheck { r: nat },
    ForEntry { r: nat },
    ForSrc { r: nat },
    ForSpawn { r: nat, j: nat },
    ForInlineBuild { r: nat },
    ForReadBack { r: nat },
    JobBuild { j: nat },
    /// the job did not start, or found the build lock held (Gen.cls:96, 166-167)
    JobQuit { j: nat },
    Walk { r: nat },
    RunEnd { r: nat },
    /// deploy_objectscript_classes: recompiles Exec/Gen (new BuiltAt: a new stamp) and, when the deploy
    /// succeeded (result.deployed), Gen.DropAll (schema.py:2935-2941, Gen.cls:225-230)
    Deploy { recompiled: bool, deployed: bool },
    /// rdf_props recompiled: TimeChanged, the stamp's first part, changes (Props.cls:104-108)
    LayoutChange,
    Tick { d: nat },
    /// a role with the database at RW sets the entry or the lines (the 4.6.0 R311 threat)
    PlantEntry { h: int, e: Entry },
    PlantSrc { h: int, lines: int },
}

pub open spec fn set_run(s: PSt, r: nat, rr: Run) -> PSt {
    PSt { runs: s.runs.insert(r, rr), ..s }
}

/// The variant: `build_checks` — Build also requires the entry's shape and stamp to be the ones its lines
/// were written for (proposal: pass them to Build); `unique_names` — the class is named by the lines'
/// SHA-256 (IVGC.D<digest>) instead of IVGC.P<CRC-32>; `readback_checks` — the sync read-back (Gen.cls:102-103)
/// makes the checks the hit path makes: its own shape and stamp, and its own class name.
pub struct PVariant {
    pub build_checks: bool,
    pub unique_names: bool,
    pub readback_checks: bool,
}

pub open spec fn p_as_built() -> PVariant {
    PVariant { build_checks: false, unique_names: false, readback_checks: false }
}

pub open spec fn p_repaired() -> PVariant {
    PVariant { build_checks: true, unique_names: true, readback_checks: true }
}

/// The class name Build gives entry h's lines with digest d.
pub open spec fn class_name(h: int, d: int, v: PVariant) -> CName {
    if v.unique_names { CName::D(d) } else { CName::P(h) }
}

/// Line 73's name check: the entry names one of the generated classes for this hash.
pub open spec fn name_ok(cls: Option<CName>, h: int, v: PVariant) -> bool {
    if v.unique_names {
        match cls { Some(CName::D(_)) => true, _ => false }
    } else {
        cls == Some(CName::P(h))
    }
}

/// Gen.Build(pH, pDigest) (Gen.cls:163-222), atomic under Lock +^IVG.CypherCompiled(pH):0.
pub open spec fn build(s: PSt, h: int, d: int, gs: Shape, gst: Stamp, v: PVariant) -> PSt {
    if !s.entries.contains_key(h) || s.entries[h].status != Status::Pending || !s.src.contains_key(h) {
        s
    } else if digest(s.src[h]) != d {
        // "refused: its lines are not the ones written for it" (177-181)
        PSt { entries: s.entries.insert(h, Entry { status: Status::Failed, ..s.entries[h] }), ..s }
    } else if v.build_checks && (s.entries[h].shape != gs || s.entries[h].stamp != gst) {
        // proposal: the entry no longer describes these lines
        PSt { entries: s.entries.insert(h, Entry { status: Status::Failed, ..s.entries[h] }), ..s }
    } else {
        // LoadStream + Compile; $List(entry, 1) = class, $List(entry, 4) = "ok" (204-207)
        PSt {
            classes: s.classes.insert(class_name(h, d, v), Code { lines: s.src[h], shape: gs, stamp: gst }),
            entries: s.entries.insert(h, Entry { cls: Some(class_name(h, d, v)), status: Status::Ok, ..s.entries[h] }),
            ..s
        }
    }
}

/// Gen.For's check (Gen.cls:69-77): the class to run, interpreted (Running with None), or go on writing.
pub open spec fn for_check(s: PSt, rr: Run, v: PVariant) -> Run {
    let h = hash_of(rr.shape);
    if s.entries.contains_key(h) && s.entries[h].shape == rr.shape && s.entries[h].stamp == rr.stamp {
        let e = s.entries[h];
        if e.status == Status::Ok {
            Run { phase: RPhase::Running, gen: if name_ok(e.cls, h, v) { e.cls } else { None }, ..rr }
        } else if e.status != Status::Pending {
            Run { phase: RPhase::Running, gen: None, ..rr }
        } else if s.now < e.at + 120 {
            Run { phase: RPhase::Running, gen: None, ..rr }
        } else {
            Run { phase: RPhase::Write1, gen: None, ..rr }
        }
    } else {
        Run { phase: RPhase::Write1, gen: None, ..rr }
    }
}

/// Gen.For's sync read-back (Gen.cls:102-103): as built, the entry's class when its status is ok.
pub open spec fn readback(s: PSt, rr: Run, v: PVariant) -> Option<CName> {
    let h = hash_of(rr.shape);
    if !s.entries.contains_key(h) || s.entries[h].status != Status::Ok {
        None
    } else if !v.readback_checks {
        s.entries[h].cls
    } else if s.entries[h].shape == rr.shape && s.entries[h].stamp == rr.stamp
        && s.entries[h].cls == Some(class_name(h, rr.digest, v)) {
        s.entries[h].cls
    } else {
        None
    }
}

/// The as-built system.
pub open spec fn p_step(s: PSt, a: PAction) -> Option<PSt> {
    p_step_v(s, a, p_as_built())
}

pub open spec fn p_step_v(s: PSt, a: PAction, v: PVariant) -> Option<PSt> {
    match a {
        PAction::RunBegin { r, shape, sync } =>
            if s.runs.contains_key(r) {
                None
            } else {
                Some(PSt {
                    runs: s.runs.insert(r, Run { shape, stamp: s.stamp, sync, phase: RPhase::Check, gen: None, digest: 0, failed: false }),
                    presented: s.presented.insert(shape),
                    ..s
                })
            },
        PAction::ForCheck { r } =>
            if !s.runs.contains_key(r) || s.runs[r].phase != RPhase::Check { None } else { Some(set_run(s, r, for_check(s, s.runs[r], v))) },
        PAction::ForEntry { r } =>
            if !s.runs.contains_key(r) || s.runs[r].phase != RPhase::Write1 {
                None
            } else {
                let rr = s.runs[r];
                let s1 = PSt {
                    entries: s.entries.insert(hash_of(rr.shape), Entry { cls: None, shape: rr.shape, stamp: rr.stamp, status: Status::Pending, at: s.now }),
                    ..s
                };
                Some(set_run(s1, r, Run { phase: RPhase::Write2, ..rr }))
            },
        PAction::ForSrc { r } =>
            if !s.runs.contains_key(r) || s.runs[r].phase != RPhase::Write2 {
                None
            } else {
                let rr = s.runs[r];
                let l = lines_of(rr.shape, rr.stamp);
                let s1 = PSt { src: s.src.insert(hash_of(rr.shape), l), ..s };
                Some(set_run(s1, r, Run { phase: RPhase::Write3, digest: digest(l), ..rr }))
            },
        PAction::ForSpawn { r, j } =>
            if !s.runs.contains_key(r) || s.runs[r].phase != RPhase::Write3 {
                None
            } else {
                let rr = s.runs[r];
                if rr.sync {
                    Some(set_run(s, r, Run { phase: RPhase::Inline, ..rr }))
                } else if s.jobs.contains_key(j) {
                    None
                } else {
                    let s1 = PSt { jobs: s.jobs.insert(j, Job { h: hash_of(rr.shape), d: rr.digest, shape: rr.shape, stamp: rr.stamp }), ..s };
                    Some(set_run(s1, r, Run { phase: RPhase::Running, gen: None, ..rr }))
                }
            },
        PAction::ForInlineBuild { r } =>
            if !s.runs.contains_key(r) || s.runs[r].phase != RPhase::Inline {
                None
            } else {
                let rr = s.runs[r];
                let s1 = build(s, hash_of(rr.shape), rr.digest, rr.shape, rr.stamp, v);
                Some(set_run(s1, r, Run { phase: RPhase::ReadBack, ..rr }))
            },
        PAction::ForReadBack { r } =>
            if !s.runs.contains_key(r) || s.runs[r].phase != RPhase::ReadBack {
                None
            } else {
                let rr = s.runs[r];
                Some(set_run(s, r, Run { phase: RPhase::Running, gen: readback(s, rr, v), ..rr }))
            },
        PAction::JobBuild { j } =>
            if !s.jobs.contains_key(j) {
                None
            } else {
                let jb = s.jobs[j];
                let s1 = build(s, jb.h, jb.d, jb.shape, jb.stamp, v);
                Some(PSt { jobs: s.jobs.remove(j), ..s1 })
            },
        PAction::JobQuit { j } =>
            if !s.jobs.contains_key(j) { None } else { Some(PSt { jobs: s.jobs.remove(j), ..s }) },
        PAction::Walk { r } =>
            if !s.runs.contains_key(r) || s.runs[r].phase != RPhase::Running || s.runs[r].failed {
                None
            } else {
                let rr = s.runs[r];
                match rr.gen {
                    None => Some(s),
                    Some(c) =>
                        if s.classes.contains_key(c) {
                            Some(PSt { execs: s.execs.push((rr.shape, rr.stamp, s.classes[c].lines)), ..s })
                        } else {
                            Some(set_run(s, r, Run { failed: true, ..rr }))
                        },
                }
            },
        PAction::RunEnd { r } =>
            if !s.runs.contains_key(r) { None } else { Some(PSt { runs: s.runs.remove(r), ..s }) },
        PAction::Deploy { recompiled, deployed } =>
            if deployed && !recompiled {
                None
            } else {
                let st = if recompiled { s.stamp + 1 } else { s.stamp };
                if deployed {
                    // Gen.DropAll: DeletePackage("IVGC"), Kill ^IVG.CypherCompiled
                    Some(PSt {
                        stamp: st,
                        classes: s.classes.restrict(s.classes.dom().filter(|k: CName| k is Other)),
                        entries: Map::empty(),
                        src: Map::empty(),
                        ..s
                    })
                } else {
                    Some(PSt { stamp: st, ..s })
                }
            },
        PAction::LayoutChange => Some(PSt { stamp: s.stamp + 1, ..s }),
        PAction::Tick { d } => Some(PSt { now: s.now + d, ..s }),
        PAction::PlantEntry { h, e } => Some(PSt { entries: s.entries.insert(h, e), ..s }),
        PAction::PlantSrc { h, lines } => Some(PSt { src: s.src.insert(h, lines), ..s }),
    }
}

// ---------------------------------------------------------------------------------------- L1

/// L1: every Walk1 executed ran the code written for its run's shape and stamp.
pub open spec fn execs_ok(s: PSt) -> bool {
    forall|i: int| 0 <= i < s.execs.len() ==> (#[trigger] s.execs[i]).2 == lines_of(s.execs[i].0, s.execs[i].1)
}

// ---------------------------------------------------------------------------------------- the check itself

/// The check Gen.For makes (Gen.cls:70-73), for any state (planted entries included): a run is given a
/// class only when the entry under its hash holds its own shape and its own stamp, says "ok", and
/// names the class IVGC.P<hash>. Every other answer interprets the run or rewrites the entry.
pub proof fn lemma_for_hit_checks(s: PSt, rr: Run)
    requires rr.phase == RPhase::Check,
    ensures
        ({
            let out = for_check(s, rr, p_as_built());
            let h = hash_of(rr.shape);
            out.gen is Some ==> {
                &&& out.gen == Some(CName::P(h))
                &&& s.entries.contains_key(h)
                &&& s.entries[h].shape == rr.shape
                &&& s.entries[h].stamp == rr.stamp
                &&& s.entries[h].status == Status::Ok
                &&& s.entries[h].cls == Some(CName::P(h))
            }
        }),
{
}

/// Absent, pending (younger than 120 s) and failed entries interpret the run.
pub proof fn lemma_for_interprets_otherwise(s: PSt, rr: Run)
    requires
        rr.phase == RPhase::Check,
        s.entries.contains_key(hash_of(rr.shape)),
        s.entries[hash_of(rr.shape)].shape == rr.shape,
        s.entries[hash_of(rr.shape)].stamp == rr.stamp,
        s.entries[hash_of(rr.shape)].status != Status::Ok,
    ensures
        for_check(s, rr, p_as_built()).gen is None,
{
}

/// A deploy that succeeded discards every compiled class and entry; a run holding a class from before
/// fails over (its next Walk1 raises) instead of running it.
pub proof fn lemma_deploy_discards(s: PSt, r: nat)
    ensures
        ({
            let s2 = p_step(s, PAction::Deploy { recompiled: true, deployed: true })->Some_0;
            &&& p_step(s, PAction::Deploy { recompiled: true, deployed: true }) is Some
            &&& forall|k: CName| #[trigger] s2.classes.contains_key(k) ==> k is Other
            &&& s2.entries == Map::<int, Entry>::empty()
            &&& s2.src == Map::<int, int>::empty()
            &&& (s2.runs.contains_key(r) && s2.runs[r].phase == RPhase::Running && !s2.runs[r].failed
                 && s2.runs[r].gen is Some && !(s2.runs[r].gen->Some_0 is Other) ==> {
                    let s3 = p_step(s2, PAction::Walk { r })->Some_0;
                    &&& s3.runs[r].failed
                    &&& s3.execs == s2.execs
                })
        }),
{
}

// ---------------------------------------------------------------------------------------- invariant

pub open spec fn writing(ph: RPhase) -> bool {
    ph == RPhase::Write2 || ph == RPhase::Write3 || ph == RPhase::Inline || ph == RPhase::ReadBack
}

pub open spec fn digested(ph: RPhase) -> bool {
    ph == RPhase::Write3 || ph == RPhase::Inline || ph == RPhase::ReadBack
}

pub open spec fn no_collision(s: PSt) -> bool {
    forall|x: Shape, y: Shape| #[trigger] s.presented.contains(x) && #[trigger] s.presented.contains(y) && hash_of(x) == hash_of(y) ==> x == y
}

pub open spec fn run_ok(s: PSt, rr: Run) -> bool {
    let h = hash_of(rr.shape);
    &&& rr.stamp == s.stamp
    &&& s.presented.contains(rr.shape)
    &&& (writing(rr.phase) ==> s.entries.contains_key(h) && s.entries[h].shape == rr.shape && s.entries[h].stamp == rr.stamp)
    &&& (digested(rr.phase) ==> rr.digest == digest(lines_of(rr.shape, rr.stamp)))
    &&& (rr.phase != RPhase::Running ==> rr.gen is None)
    &&& (rr.gen is Some ==> rr.gen == Some(CName::P(h)))
    &&& (rr.gen is Some && s.classes.contains_key(CName::P(h)) ==> s.classes[CName::P(h)].lines == lines_of(rr.shape, rr.stamp))
}

pub open spec fn entry_ok(s: PSt, h: int, e: Entry) -> bool {
    &&& hash_of(e.shape) == h
    &&& s.presented.contains(e.shape)
    &&& (e.cls is None || e.cls == Some(CName::P(h)))
    &&& (e.status == Status::Ok ==> e.cls == Some(CName::P(h)) && s.classes.contains_key(CName::P(h))
            && s.classes[CName::P(h)].shape == e.shape && s.classes[CName::P(h)].stamp == e.stamp)
}

pub open spec fn job_ok(s: PSt, jb: Job) -> bool {
    &&& jb.stamp == s.stamp
    &&& s.presented.contains(jb.shape)
    &&& hash_of(jb.shape) == jb.h
    &&& jb.d == digest(lines_of(jb.shape, jb.stamp))
    &&& (s.entries.contains_key(jb.h) ==> s.entries[jb.h].stamp == jb.stamp)
}

pub open spec fn p_inv(s: PSt) -> bool {
    &&& no_collision(s)
    &&& forall|r: nat| #[trigger] s.runs.contains_key(r) ==> run_ok(s, s.runs[r])
    &&& forall|c: CName| #[trigger] s.classes.contains_key(c) && c is P ==> {
            &&& hash_of(s.classes[c].shape) == c->P_0
            &&& s.presented.contains(s.classes[c].shape)
            &&& s.classes[c].lines == lines_of(s.classes[c].shape, s.classes[c].stamp)
        }
    &&& forall|h: int| #[trigger] s.entries.contains_key(h) ==> entry_ok(s, h, s.entries[h])
    &&& forall|j: nat| #[trigger] s.jobs.contains_key(j) ==> job_ok(s, s.jobs[j])
    &&& execs_ok(s)
}

/// Premises (NOTES.md):
///   P-NO-COLLISION  no two shapes presented share a CRC-32 (the witnesses drop it)
///   P-QUIESCENT     a deploy or an rdf_props recompile happens with no run and no build job in flight
///   P-NO-PLANT-ENTRY no role writes ^IVG.CypherCompiled(h) itself (planted lines are allowed)
pub open spec fn p_premise(s: PSt, a: PAction) -> bool {
    match a {
        PAction::RunBegin { shape, .. } => forall|x: Shape| #[trigger] s.presented.contains(x) && hash_of(x) == hash_of(shape) ==> x == shape,
        PAction::Deploy { .. } => s.runs == Map::<nat, Run>::empty() && s.jobs == Map::<nat, Job>::empty(),
        PAction::LayoutChange => s.runs == Map::<nat, Run>::empty() && s.jobs == Map::<nat, Job>::empty(),
        PAction::PlantEntry { .. } => false,
        _ => true,
    }
}

/// P-SHA: SHA-256 has no collision among the lines involved.
pub open spec fn digest_injective() -> bool {
    forall|a: int, b: int| #![trigger digest(a), digest(b)] digest(a) == digest(b) ==> a == b
}

pub proof fn lemma_build_preserves(s: PSt, h: int, d: int, gs: Shape, gst: Stamp)
    requires
        p_inv(s),
        digest_injective(),
        hash_of(gs) == h,
        s.presented.contains(gs),
        gst == s.stamp,
        d == digest(lines_of(gs, gst)),
        s.entries.contains_key(h) ==> s.entries[h].stamp == gst,
    ensures
        p_inv(build(s, h, d, gs, gst, p_as_built())),
        build(s, h, d, gs, gst, p_as_built()).runs == s.runs,
        build(s, h, d, gs, gst, p_as_built()).jobs == s.jobs,
        build(s, h, d, gs, gst, p_as_built()).presented == s.presented,
        build(s, h, d, gs, gst, p_as_built()).execs == s.execs,
        build(s, h, d, gs, gst, p_as_built()).stamp == s.stamp,
{
    let s2 = build(s, h, d, gs, gst, p_as_built());
    if !s.entries.contains_key(h) || s.entries[h].status != Status::Pending || !s.src.contains_key(h) {
    } else if digest(s.src[h]) != d {
        assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
            assert(entry_ok(s, k, s.entries[k]));
        }
        assert forall|r: nat| #[trigger] s2.runs.contains_key(r) implies run_ok(s2, s2.runs[r]) by {
            assert(run_ok(s, s.runs[r]));
        }
        assert forall|j: nat| #[trigger] s2.jobs.contains_key(j) implies job_ok(s2, s2.jobs[j]) by {
            assert(job_ok(s, s.jobs[j]));
        }
    } else {
        let e = s.entries[h];
        assert(entry_ok(s, h, e));
        assert(s.src[h] == lines_of(gs, gst));
        assert(e.shape == gs);
        assert forall|c: CName| #[trigger] s2.classes.contains_key(c) && c is P implies {
            &&& hash_of(s2.classes[c].shape) == c->P_0
            &&& s2.presented.contains(s2.classes[c].shape)
            &&& s2.classes[c].lines == lines_of(s2.classes[c].shape, s2.classes[c].stamp)
        } by {
            if c != CName::P(h) { assert(s.classes.contains_key(c)); }
        }
        assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
            assert(entry_ok(s, k, s.entries[k]));
            if k != h && s.entries[k].status == Status::Ok {
                assert(s.classes.contains_key(CName::P(k)));
            }
        }
        assert forall|r: nat| #[trigger] s2.runs.contains_key(r) implies run_ok(s2, s2.runs[r]) by {
            let rr = s.runs[r];
            assert(run_ok(s, rr));
            if rr.gen is Some && hash_of(rr.shape) == h {
                assert(s.presented.contains(rr.shape) && s.presented.contains(gs));
                assert(rr.shape == gs);
            }
        }
        assert forall|j: nat| #[trigger] s2.jobs.contains_key(j) implies job_ok(s2, s2.jobs[j]) by {
            assert(job_ok(s, s.jobs[j]));
        }
    }
}

pub proof fn lemma_p_step_preserves_inv(s: PSt, a: PAction)
    requires
        p_inv(s),
        digest_injective(),
        p_premise(s, a),
        p_step(s, a) is Some,
    ensures
        p_inv(p_step(s, a)->Some_0),
{
    let s2 = p_step(s, a)->Some_0;
    match a {
        PAction::RunBegin { r, shape, sync } => {
            assert forall|x: Shape, y: Shape| #[trigger] s2.presented.contains(x) && #[trigger] s2.presented.contains(y) && hash_of(x) == hash_of(y) implies x == y by {
                if x != shape && y != shape {
                    assert(s.presented.contains(x) && s.presented.contains(y));
                } else if x == shape && y != shape {
                    assert(s.presented.contains(y));
                } else if y == shape && x != shape {
                    assert(s.presented.contains(x));
                }
            }
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                if k != r { assert(run_ok(s, s.runs[k])); }
            }
            assert forall|h: int| #[trigger] s2.entries.contains_key(h) implies entry_ok(s2, h, s2.entries[h]) by {
                assert(entry_ok(s, h, s.entries[h]));
            }
            assert forall|j: nat| #[trigger] s2.jobs.contains_key(j) implies job_ok(s2, s2.jobs[j]) by {
                assert(job_ok(s, s.jobs[j]));
            }
            assert forall|c: CName| #[trigger] s2.classes.contains_key(c) && c is P implies {
                &&& hash_of(s2.classes[c].shape) == c->P_0
                &&& s2.presented.contains(s2.classes[c].shape)
                &&& s2.classes[c].lines == lines_of(s2.classes[c].shape, s2.classes[c].stamp)
            } by {
                assert(s.classes.contains_key(c));
            }
        }
        PAction::ForCheck { r } => {
            let rr = s.runs[r];
            let h = hash_of(rr.shape);
            assert(run_ok(s, rr));
            let out = for_check(s, rr, p_as_built());
            if out.gen is Some {
                assert(entry_ok(s, h, s.entries[h]));
            }
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                if k != r { assert(run_ok(s, s.runs[k])); }
            }
        }
        PAction::ForEntry { r } => {
            let rr = s.runs[r];
            let h = hash_of(rr.shape);
            assert(run_ok(s, rr));
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                if k != r {
                    let q = s.runs[k];
                    assert(run_ok(s, q));
                    if hash_of(q.shape) == h {
                        assert(s.presented.contains(q.shape) && s.presented.contains(rr.shape));
                        assert(q.shape == rr.shape);
                    }
                }
            }
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
                if k != h { assert(entry_ok(s, k, s.entries[k])); }
            }
            assert forall|j: nat| #[trigger] s2.jobs.contains_key(j) implies job_ok(s2, s2.jobs[j]) by {
                assert(job_ok(s, s.jobs[j]));
            }
        }
        PAction::ForSrc { r } => {
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                assert(run_ok(s, s.runs[k]));
            }
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
                assert(entry_ok(s, k, s.entries[k]));
            }
            assert forall|j: nat| #[trigger] s2.jobs.contains_key(j) implies job_ok(s2, s2.jobs[j]) by {
                assert(job_ok(s, s.jobs[j]));
            }
        }
        PAction::ForSpawn { r, j } => {
            let rr = s.runs[r];
            assert(run_ok(s, rr));
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                assert(run_ok(s, s.runs[k]));
            }
            assert forall|k: nat| #[trigger] s2.jobs.contains_key(k) implies job_ok(s2, s2.jobs[k]) by {
                if k != j || rr.sync { assert(job_ok(s, s.jobs[k])); }
            }
        }
        PAction::ForInlineBuild { r } => {
            let rr = s.runs[r];
            assert(run_ok(s, rr));
            lemma_build_preserves(s, hash_of(rr.shape), rr.digest, rr.shape, rr.stamp);
            let s1 = build(s, hash_of(rr.shape), rr.digest, rr.shape, rr.stamp, p_as_built());
            assert(run_ok(s1, s1.runs[r]));
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                if k != r { assert(run_ok(s1, s1.runs[k])); }
            }
        }
        PAction::ForReadBack { r } => {
            let rr = s.runs[r];
            let h = hash_of(rr.shape);
            assert(run_ok(s, rr));
            assert(entry_ok(s, h, s.entries[h]));
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                if k != r { assert(run_ok(s, s.runs[k])); }
            }
        }
        PAction::JobBuild { j } => {
            let jb = s.jobs[j];
            assert(job_ok(s, jb));
            lemma_build_preserves(s, jb.h, jb.d, jb.shape, jb.stamp);
            let s1 = build(s, jb.h, jb.d, jb.shape, jb.stamp, p_as_built());
            assert forall|k: nat| #[trigger] s2.jobs.contains_key(k) implies job_ok(s2, s2.jobs[k]) by {
                assert(job_ok(s1, s1.jobs[k]));
            }
        }
        PAction::JobQuit { j } => {
            assert forall|k: nat| #[trigger] s2.jobs.contains_key(k) implies job_ok(s2, s2.jobs[k]) by {
                assert(job_ok(s, s.jobs[k]));
            }
        }
        PAction::Walk { r } => {
            let rr = s.runs[r];
            assert(run_ok(s, rr));
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                assert(run_ok(s, s.runs[k]));
            }
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
                assert(entry_ok(s, k, s.entries[k]));
            }
            assert forall|j: nat| #[trigger] s2.jobs.contains_key(j) implies job_ok(s2, s2.jobs[j]) by {
                assert(job_ok(s, s.jobs[j]));
            }
            assert forall|i: int| 0 <= i < s2.execs.len() implies (#[trigger] s2.execs[i]).2 == lines_of(s2.execs[i].0, s2.execs[i].1) by {
                if i < s.execs.len() {
                    assert(s2.execs[i] == s.execs[i]);
                }
            }
        }
        PAction::RunEnd { r } => {
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                assert(run_ok(s, s.runs[k]));
            }
        }
        PAction::Deploy { recompiled, deployed } => {
            assert forall|k: nat| !s2.runs.contains_key(k) by {
                assert(!s.runs.contains_key(k));
            }
            assert forall|k: nat| !s2.jobs.contains_key(k) by {
                assert(!s.jobs.contains_key(k));
            }
            if !deployed {
                assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
                    assert(entry_ok(s, k, s.entries[k]));
                }
            }
            assert forall|c: CName| #[trigger] s2.classes.contains_key(c) && c is P implies {
                &&& hash_of(s2.classes[c].shape) == c->P_0
                &&& s2.presented.contains(s2.classes[c].shape)
                &&& s2.classes[c].lines == lines_of(s2.classes[c].shape, s2.classes[c].stamp)
            } by {
                assert(s.classes.contains_key(c));
            }
        }
        PAction::LayoutChange => {
            assert forall|k: nat| !s2.runs.contains_key(k) by {
                assert(!s.runs.contains_key(k));
            }
            assert forall|k: nat| !s2.jobs.contains_key(k) by {
                assert(!s.jobs.contains_key(k));
            }
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
                assert(entry_ok(s, k, s.entries[k]));
            }
        }
        PAction::Tick { d } => {
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                assert(run_ok(s, s.runs[k]));
            }
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
                assert(entry_ok(s, k, s.entries[k]));
            }
            assert forall|j: nat| #[trigger] s2.jobs.contains_key(j) implies job_ok(s2, s2.jobs[j]) by {
                assert(job_ok(s, s.jobs[j]));
            }
        }
        PAction::PlantEntry { h, e } => {}
        PAction::PlantSrc { h, lines } => {
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies run_ok(s2, s2.runs[k]) by {
                assert(run_ok(s, s.runs[k]));
            }
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies entry_ok(s2, k, s2.entries[k]) by {
                assert(entry_ok(s, k, s.entries[k]));
            }
            assert forall|j: nat| #[trigger] s2.jobs.contains_key(j) implies job_ok(s2, s2.jobs[j]) by {
                assert(job_ok(s, s.jobs[j]));
            }
        }
    }
}

pub open spec fn p_start(st: Stamp) -> PSt {
    PSt {
        entries: Map::empty(),
        src: Map::empty(),
        classes: Map::empty(),
        runs: Map::empty(),
        jobs: Map::empty(),
        stamp: st,
        now: 0,
        presented: Set::empty(),
        execs: Seq::empty(),
    }
}

/// A namespace after a deploy (no compiled plan) satisfies the invariant.
pub proof fn lemma_p_init(st: Stamp)
    ensures p_inv(p_start(st)),
{
}

// ---------------------------------------------------------------------------------------- collisions exist

/// Any 32-bit naming of more than 2^32 shapes has a collision (pigeonhole). Shapes hold node labels and
/// property keys, which are free text, so the planner accepts unboundedly many (P-SHAPES-UNBOUNDED).
pub proof fn lemma_crc_collision_exists()
    ensures
        exists|a: Shape, b: Shape| 0 <= a < 0x1_0000_0001 && 0 <= b < 0x1_0000_0001 && a != b && crc32(a) == crc32(b),
{
    let n: int = 0x1_0000_0000;
    let x = set_int_range(0, n + 1);
    let f = |a: int| crc32(a) as int;
    let y = x.map(f);
    lemma_int_range(0, n + 1);
    lemma_int_range(0, n);
    if !(exists|a: Shape, b: Shape| 0 <= a < 0x1_0000_0001 && 0 <= b < 0x1_0000_0001 && a != b && crc32(a) == crc32(b)) {
        assert(x.injective_on(f)) by {
            assert forall|a: int, b: int| x.contains(a) && x.contains(b) && #[trigger] f(a) == #[trigger] f(b) implies a == b by {
                if a != b {
                    assert(crc32(a) == crc32(b));
                }
            }
        }
        lemma_map_size(x, y, f);
        assert(y.subset_of(set_int_range(0, n))) by {
            assert forall|b: int| #[trigger] y.contains(b) implies set_int_range(0, n).contains(b) by {
                x.lemma_map_contains(f, b);
                let a = choose|a: int| x.contains(a) && b == f(a);
                assert(0 <= crc32(a) as int && (crc32(a) as int) < n);
            }
        }
        lemma_len_subset(y, set_int_range(0, n));
        assert(false);
    }
}

/// With P-CODE-VARIETY (2^32 + 1 shapes whose generated code differs pairwise: labels and property keys
/// are baked into the lines as literals, Gen.Check), two shapes with one CRC-32 and different code exist.
pub proof fn lemma_colliding_shapes_with_different_code(st: Stamp)
    requires
        forall|a: Shape, b: Shape| #![trigger lines_of(a, st), lines_of(b, st)]
            0 <= a < 0x1_0000_0001 && 0 <= b < 0x1_0000_0001 && a != b ==> lines_of(a, st) != lines_of(b, st),
    ensures
        exists|a: Shape, b: Shape| a != b && crc32(a) == crc32(b) && lines_of(a, st) != lines_of(b, st),
{
    lemma_crc_collision_exists();
    let (a, b) = choose|a: Shape, b: Shape| 0 <= a < 0x1_0000_0001 && 0 <= b < 0x1_0000_0001 && a != b && crc32(a) == crc32(b);
    assert(lines_of(a, st) != lines_of(b, st));
}

// ---------------------------------------------------------------------------------------- witnesses

/// A valid outcome: in job mode the first run of a shape is interpreted and builds its class; the next
/// run of the same shape walks the class, which is its own code.
pub proof fn witness_compiled_plan_is_used(a: Shape, st: Stamp) {
    let s0 = p_start(st);
    let h = hash_of(a);
    let s1 = p_step(s0, PAction::RunBegin { r: 1, shape: a, sync: false })->Some_0;
    let s2 = p_step(s1, PAction::ForCheck { r: 1 })->Some_0;
    assert(s2.runs[1].phase == RPhase::Write1);
    let s3 = p_step(s2, PAction::ForEntry { r: 1 })->Some_0;
    let s4 = p_step(s3, PAction::ForSrc { r: 1 })->Some_0;
    let s5 = p_step(s4, PAction::ForSpawn { r: 1, j: 1 })->Some_0;
    assert(s5.runs[1].gen is None && s5.jobs.contains_key(1));
    let s6 = p_step(s5, PAction::JobBuild { j: 1 })->Some_0;
    assert(s5.entries[h].status == Status::Pending && s5.src[h] == lines_of(a, st));
    assert(s6.classes.contains_key(CName::P(h)) && s6.entries[h].status == Status::Ok);
    let s7 = p_step(s6, PAction::RunEnd { r: 1 })->Some_0;
    let s8 = p_step(s7, PAction::RunBegin { r: 2, shape: a, sync: false })->Some_0;
    let s9 = p_step(s8, PAction::ForCheck { r: 2 })->Some_0;
    assert(s9.runs[2].gen == Some(CName::P(h)));
    let s10 = p_step(s9, PAction::Walk { r: 2 })->Some_0;
    assert(s10.execs.len() == 1 && s10.execs[0] == (a, st, lines_of(a, st)));
    assert(execs_ok(s10));
}

/// W-O2a (F2, mid-run) — shapes a != b with one CRC-32. A sync run of a holds IVGC.P<h> after its check;
/// a sync run of b misses (its shape differs), rewrites the same entry and recompiles the same class
/// name with b's code; the run of a's next Walk1 executes b's code.
pub proof fn witness_collision_swaps_the_class_mid_run(a: Shape, b: Shape, st: Stamp)
    requires
        a != b,
        crc32(a) == crc32(b),
        lines_of(a, st) != lines_of(b, st),
{
    let h = hash_of(a);
    let s0 = p_start(st);
    let s1 = p_step(s0, PAction::RunBegin { r: 1, shape: a, sync: true })->Some_0;
    let s2 = p_step(s1, PAction::ForCheck { r: 1 })->Some_0;
    let s3 = p_step(s2, PAction::ForEntry { r: 1 })->Some_0;
    let s4 = p_step(s3, PAction::ForSrc { r: 1 })->Some_0;
    let s5 = p_step(s4, PAction::ForSpawn { r: 1, j: 0 })->Some_0;
    let s6 = p_step(s5, PAction::ForInlineBuild { r: 1 })->Some_0;
    assert(s5.entries[h].status == Status::Pending && s5.src[h] == lines_of(a, st) && s5.runs[1].digest == digest(lines_of(a, st)));
    let s7 = p_step(s6, PAction::ForReadBack { r: 1 })->Some_0;
    assert(s7.runs[1].gen == Some(CName::P(h)));
    let s8 = p_step(s7, PAction::Walk { r: 1 })->Some_0;
    assert(s8.execs[0] == (a, st, lines_of(a, st)));
    // the run of b
    let s9 = p_step(s8, PAction::RunBegin { r: 2, shape: b, sync: true })->Some_0;
    let s10 = p_step(s9, PAction::ForCheck { r: 2 })->Some_0;
    assert(s9.entries[h].shape == a);
    assert(s10.runs[2].phase == RPhase::Write1);
    let s11 = p_step(s10, PAction::ForEntry { r: 2 })->Some_0;
    let s12 = p_step(s11, PAction::ForSrc { r: 2 })->Some_0;
    let s13 = p_step(s12, PAction::ForSpawn { r: 2, j: 0 })->Some_0;
    let s14 = p_step(s13, PAction::ForInlineBuild { r: 2 })->Some_0;
    assert(s13.entries[h].status == Status::Pending && s13.src[h] == lines_of(b, st) && s13.runs[2].digest == digest(lines_of(b, st)));
    assert(s14.classes[CName::P(h)].lines == lines_of(b, st));
    // the run of a walks its next anchor with b's code
    let s15 = p_step(s14, PAction::Walk { r: 1 })->Some_0;
    assert(s14.runs[1].gen == Some(CName::P(h)) && s14.runs[1].phase == RPhase::Running && !s14.runs[1].failed);
    assert(s15.execs[1] == (a, st, lines_of(b, st)));
    assert(!execs_ok(s15));
}

/// W-O2b (F2, persistent) — two job-mode runs of a and b (one CRC-32) interleave inside For: the entry
/// ends written by b (line 80) while the lines are a's (81-89), and a's job compiles them: the digest
/// check passes because they are the lines a's For wrote. The entry now says (b, ok, IVGC.P<h>) over a's
/// code, so every later run of b walks a's code (until a stamp change or a deploy).
pub proof fn witness_collision_leaves_another_shapes_code_under_an_ok_entry(a: Shape, b: Shape, st: Stamp)
    requires
        a != b,
        crc32(a) == crc32(b),
        lines_of(a, st) != lines_of(b, st),
{
    let h = hash_of(a);
    let s0 = p_start(st);
    let s1 = p_step(s0, PAction::RunBegin { r: 1, shape: a, sync: false })->Some_0;
    let s2 = p_step(s1, PAction::RunBegin { r: 2, shape: b, sync: false })->Some_0;
    let s3 = p_step(s2, PAction::ForCheck { r: 1 })->Some_0;
    let s4 = p_step(s3, PAction::ForCheck { r: 2 })->Some_0;
    let s5 = p_step(s4, PAction::ForEntry { r: 1 })->Some_0;
    let s6 = p_step(s5, PAction::ForEntry { r: 2 })->Some_0;
    assert(s6.entries[h].shape == b);
    let s7 = p_step(s6, PAction::ForSrc { r: 2 })->Some_0;
    let s8 = p_step(s7, PAction::ForSrc { r: 1 })->Some_0;
    assert(s8.src[h] == lines_of(a, st));
    let s9 = p_step(s8, PAction::ForSpawn { r: 1, j: 1 })->Some_0;
    let s10 = p_step(s9, PAction::ForSpawn { r: 2, j: 2 })->Some_0;
    assert(s10.jobs[1].d == digest(lines_of(a, st)));
    let s11 = p_step(s10, PAction::JobBuild { j: 1 })->Some_0;
    assert(s10.entries[h].status == Status::Pending && s10.src[h] == lines_of(a, st));
    assert(s11.entries[h].shape == b && s11.entries[h].status == Status::Ok && s11.entries[h].cls == Some(CName::P(h)));
    assert(s11.classes[CName::P(h)].lines == lines_of(a, st));
    let s12 = p_step(s11, PAction::JobBuild { j: 2 })->Some_0;
    assert(s12.entries[h].status == Status::Ok && s12.classes[CName::P(h)].lines == lines_of(a, st));
    let s13 = p_step(s12, PAction::RunEnd { r: 1 })->Some_0;
    let s14 = p_step(s13, PAction::RunEnd { r: 2 })->Some_0;
    // a later run of b: the check passes (shape b, stamp, ok, IVGC.P<h>) and walks a's code
    let s15 = p_step(s14, PAction::RunBegin { r: 3, shape: b, sync: false })->Some_0;
    let s16 = p_step(s15, PAction::ForCheck { r: 3 })->Some_0;
    assert(hash_of(b) == h);
    assert(s16.runs[3].gen == Some(CName::P(h)));
    let s17 = p_step(s16, PAction::Walk { r: 3 })->Some_0;
    assert(s17.execs[0] == (b, st, lines_of(a, st)));
    assert(!execs_ok(s17));
}

/// W-O2c (no collision) — the check is once per run. A run that began before an rdf_props recompile
/// (its layout is the old one) reaches For after a run under the new layout compiled the shape; its
/// stamp differs, so it rewrites the entry and recompiles the same class name with code for the old
/// layout, which the newer run's next Walk1 executes. Excluded by P-QUIESCENT.
pub proof fn witness_straggler_recompiles_for_an_old_layout(a: Shape, st: Stamp)
    requires lines_of(a, st) != lines_of(a, st + 1),
{
    let h = hash_of(a);
    let s0 = p_start(st);
    let s1 = p_step(s0, PAction::RunBegin { r: 1, shape: a, sync: true })->Some_0;
    let s2 = p_step(s1, PAction::LayoutChange)->Some_0;
    let s3 = p_step(s2, PAction::RunBegin { r: 2, shape: a, sync: true })->Some_0;
    assert(s3.runs[1].stamp == st && s3.runs[2].stamp == st + 1);
    let s4 = p_step(s3, PAction::ForCheck { r: 2 })->Some_0;
    let s5 = p_step(s4, PAction::ForEntry { r: 2 })->Some_0;
    let s6 = p_step(s5, PAction::ForSrc { r: 2 })->Some_0;
    let s7 = p_step(s6, PAction::ForSpawn { r: 2, j: 0 })->Some_0;
    let s8 = p_step(s7, PAction::ForInlineBuild { r: 2 })->Some_0;
    assert(s7.entries[h].status == Status::Pending && s7.src[h] == lines_of(a, (st + 1) as nat));
    let s9 = p_step(s8, PAction::ForReadBack { r: 2 })->Some_0;
    assert(s9.runs[2].gen == Some(CName::P(h)));
    let s10 = p_step(s9, PAction::Walk { r: 2 })->Some_0;
    assert(s10.execs[0] == (a, (st + 1) as nat, lines_of(a, (st + 1) as nat)));
    // the straggler
    let s11 = p_step(s10, PAction::ForCheck { r: 1 })->Some_0;
    assert(s11.runs[1].phase == RPhase::Write1);
    let s12 = p_step(s11, PAction::ForEntry { r: 1 })->Some_0;
    let s13 = p_step(s12, PAction::ForSrc { r: 1 })->Some_0;
    let s14 = p_step(s13, PAction::ForSpawn { r: 1, j: 0 })->Some_0;
    let s15 = p_step(s14, PAction::ForInlineBuild { r: 1 })->Some_0;
    assert(s14.entries[h].status == Status::Pending && s14.src[h] == lines_of(a, st));
    assert(s15.classes[CName::P(h)].lines == lines_of(a, st));
    let s16 = p_step(s15, PAction::Walk { r: 2 })->Some_0;
    assert(s15.runs[2].gen == Some(CName::P(h)) && s15.runs[2].phase == RPhase::Running && !s15.runs[2].failed);
    assert(s16.execs[1] == (a, (st + 1) as nat, lines_of(a, st)));
    assert(!execs_ok(s16));
}

/// W-O2d (R311 gap) — after a sync build, For reads the entry again and returns its class name without
/// the IVGC.P<h> check line 73 makes (Gen.cls:102-103). A role that sets the entry in that window to
/// another shape's compiled class makes the run walk that class. The same planted entry is harmless on
/// the check path: line 73 refuses the foreign name and the run is interpreted.
pub proof fn witness_readback_trusts_the_entrys_class(a: Shape, b: Shape, st: Stamp)
    requires
        hash_of(a) != hash_of(b),
        lines_of(a, st) != lines_of(b, st),
{
    let ha = hash_of(a);
    let hb = hash_of(b);
    let s0 = PSt { classes: Map::empty().insert(CName::P(hb), Code { lines: lines_of(b, st), shape: b, stamp: st }), ..p_start(st) };
    let s1 = p_step(s0, PAction::RunBegin { r: 1, shape: a, sync: true })->Some_0;
    let s2 = p_step(s1, PAction::ForCheck { r: 1 })->Some_0;
    let s3 = p_step(s2, PAction::ForEntry { r: 1 })->Some_0;
    let s4 = p_step(s3, PAction::ForSrc { r: 1 })->Some_0;
    let s5 = p_step(s4, PAction::ForSpawn { r: 1, j: 0 })->Some_0;
    let s6 = p_step(s5, PAction::ForInlineBuild { r: 1 })->Some_0;
    assert(s5.entries[ha].status == Status::Pending && s5.src[ha] == lines_of(a, st));
    let planted = Entry { cls: Some(CName::P(hb)), shape: a, stamp: st, status: Status::Ok, at: 0 };
    let s7 = p_step(s6, PAction::PlantEntry { h: ha, e: planted })->Some_0;
    let s8 = p_step(s7, PAction::ForReadBack { r: 1 })->Some_0;
    assert(s8.runs[1].gen == Some(CName::P(hb)));
    let s9 = p_step(s8, PAction::Walk { r: 1 })->Some_0;
    assert(s8.classes.contains_key(CName::P(hb)) && s8.classes[CName::P(hb)].lines == lines_of(b, st));
    assert(s9.execs[0] == (a, st, lines_of(b, st)));
    assert(!execs_ok(s9));
    // the check path with the same entry: interpreted
    let s10 = p_step(s9, PAction::RunBegin { r: 2, shape: a, sync: true })->Some_0;
    let s11 = p_step(s10, PAction::ForCheck { r: 2 })->Some_0;
    assert(s11.runs[2].phase == RPhase::Running && s11.runs[2].gen is None);
}

// ---------------------------------------------------------------------------------------- forging a collision (R1-3)

/// The shape a caller writes whose chosen label (or property key) is `base` followed by four free bytes
/// `suffix`. Labels and keys are free text and Gen.Shape carries them in the $ListBuild it hashes.
pub uninterp spec fn forged(base: int, suffix: int) -> Shape;

/// P-CRC-AFFINE(base): CRC-32 is affine over GF(2), and feeding four more bytes is a bijection of its 32-bit
/// state, so distinct suffixes of one prefix give distinct checksums.
pub open spec fn crc_suffix_bijective(base: int) -> bool {
    forall|x1: int, x2: int| #![trigger crc32(forged(base, x1)), crc32(forged(base, x2))]
        0 <= x1 < 0x1_0000_0000 && 0 <= x2 < 0x1_0000_0000 && x1 != x2 ==> crc32(forged(base, x1)) != crc32(forged(base, x2))
}

/// Under P-CRC-AFFINE every target checksum is hit by some suffix: a caller can choose a shape colliding
/// with any target shape (2^32 suffixes map onto the 2^32 checksums).
pub proof fn lemma_forge_collision(base: int, target: Shape)
    requires crc_suffix_bijective(base),
    ensures exists|x: int| 0 <= x < 0x1_0000_0000 && crc32(forged(base, x)) == crc32(target),
{
    let n: int = 0x1_0000_0000;
    let xs = set_int_range(0, n);
    let f = |x: int| crc32(forged(base, x)) as int;
    let ys = xs.map(f);
    lemma_int_range(0, n);
    assert(xs.injective_on(f)) by {
        assert forall|x1: int, x2: int| xs.contains(x1) && xs.contains(x2) && #[trigger] f(x1) == #[trigger] f(x2) implies x1 == x2 by {
            if x1 != x2 {
                assert(crc32(forged(base, x1)) != crc32(forged(base, x2)));
            }
        }
    }
    lemma_map_size(xs, ys, f);
    assert(ys.subset_of(xs)) by {
        assert forall|y: int| #[trigger] ys.contains(y) implies xs.contains(y) by {
            xs.lemma_map_contains(f, y);
            let x = choose|x: int| xs.contains(x) && y == f(x);
            assert(0 <= crc32(forged(base, x)) as int && (crc32(forged(base, x)) as int) < n);
        }
    }
    lemma_subset_equality(ys, xs);
    let t = crc32(target) as int;
    assert(xs.contains(t));
    assert(ys.contains(t));
    xs.lemma_map_contains(f, t);
    let x = choose|x: int| xs.contains(x) && t == f(x);
    assert(0 <= x < n && crc32(forged(base, x)) == crc32(target));
}

/// R1-3 — a caller with Cypher read access only (every action below is an ordinary read; nothing is
/// planted) chooses a shape colliding with a victim's shape `target`, runs both in job mode until a's
/// build job runs first (W-O2b's order), and from then on every run of `target` — the victim's — walks
/// the attacker's code: a label that matches nothing makes the victim's read answer no rows. The login
/// the reads run under must be able to write ^IVG.CypherCompiled (Gen.For writes it; the default
/// _SYSTEM login can, including under IVG_READ_ONLY, which does not cover caches).
pub proof fn witness_reader_forges_a_collision_and_poisons_a_shape(base: int, target: Shape, st: Stamp)
    requires
        crc_suffix_bijective(base),
        forall|x: int| #[trigger] forged(base, x) != target,
        forall|x: int| #[trigger] lines_of(forged(base, x), st) != lines_of(target, st),
{
    lemma_forge_collision(base, target);
    let x = choose|x: int| 0 <= x < 0x1_0000_0000 && crc32(forged(base, x)) == crc32(target);
    let a = forged(base, x);
    let b = target;
    assert(a != b && lines_of(a, st) != lines_of(b, st));
    let h = hash_of(a);
    assert(hash_of(b) == h);
    let s0 = p_start(st);
    // the attacker's two reads
    let s1 = p_step(s0, PAction::RunBegin { r: 1, shape: a, sync: false })->Some_0;
    let s2 = p_step(s1, PAction::RunBegin { r: 2, shape: b, sync: false })->Some_0;
    let s3 = p_step(s2, PAction::ForCheck { r: 1 })->Some_0;
    let s4 = p_step(s3, PAction::ForCheck { r: 2 })->Some_0;
    let s5 = p_step(s4, PAction::ForEntry { r: 1 })->Some_0;
    let s6 = p_step(s5, PAction::ForEntry { r: 2 })->Some_0;
    let s7 = p_step(s6, PAction::ForSrc { r: 2 })->Some_0;
    let s8 = p_step(s7, PAction::ForSrc { r: 1 })->Some_0;
    let s9 = p_step(s8, PAction::ForSpawn { r: 1, j: 1 })->Some_0;
    let s10 = p_step(s9, PAction::ForSpawn { r: 2, j: 2 })->Some_0;
    let s11 = p_step(s10, PAction::JobBuild { j: 1 })->Some_0;
    assert(s10.entries[h].status == Status::Pending && s10.entries[h].shape == b && s10.src[h] == lines_of(a, st));
    assert(s10.jobs[1].d == digest(lines_of(a, st)));
    assert(s11.entries[h].shape == b && s11.entries[h].status == Status::Ok && s11.classes[CName::P(h)].lines == lines_of(a, st));
    let s12 = p_step(s11, PAction::JobBuild { j: 2 })->Some_0;
    let s13 = p_step(s12, PAction::RunEnd { r: 1 })->Some_0;
    let s14 = p_step(s13, PAction::RunEnd { r: 2 })->Some_0;
    // the victim's read
    let s15 = p_step(s14, PAction::RunBegin { r: 3, shape: b, sync: false })->Some_0;
    let s16 = p_step(s15, PAction::ForCheck { r: 3 })->Some_0;
    assert(s16.runs[3].gen == Some(CName::P(h)));
    let s17 = p_step(s16, PAction::Walk { r: 3 })->Some_0;
    assert(s17.execs[0] == (b, st, lines_of(a, st)));
    assert(!execs_ok(s17));
}

// ---------------------------------------------------------------------------------------- which repair closes what

/// The persistent case (W-O2b) is closed by Build's shape/stamp check alone: a's job finds the entry
/// written for b and refuses; the shape stays interpreted, and no class of a's code is ever under b's entry.
pub proof fn witness_build_check_closes_the_persistent_case(a: Shape, b: Shape, st: Stamp)
    requires
        a != b,
        crc32(a) == crc32(b),
{
    let v = PVariant { build_checks: true, unique_names: false, readback_checks: false };
    let h = hash_of(a);
    let s0 = p_start(st);
    let s1 = p_step_v(s0, PAction::RunBegin { r: 1, shape: a, sync: false }, v)->Some_0;
    let s2 = p_step_v(s1, PAction::RunBegin { r: 2, shape: b, sync: false }, v)->Some_0;
    let s3 = p_step_v(s2, PAction::ForCheck { r: 1 }, v)->Some_0;
    let s4 = p_step_v(s3, PAction::ForCheck { r: 2 }, v)->Some_0;
    let s5 = p_step_v(s4, PAction::ForEntry { r: 1 }, v)->Some_0;
    let s6 = p_step_v(s5, PAction::ForEntry { r: 2 }, v)->Some_0;
    let s7 = p_step_v(s6, PAction::ForSrc { r: 2 }, v)->Some_0;
    let s8 = p_step_v(s7, PAction::ForSrc { r: 1 }, v)->Some_0;
    let s9 = p_step_v(s8, PAction::ForSpawn { r: 1, j: 1 }, v)->Some_0;
    let s10 = p_step_v(s9, PAction::ForSpawn { r: 2, j: 2 }, v)->Some_0;
    assert(s10.entries[h].status == Status::Pending && s10.entries[h].shape == b && s10.src[h] == lines_of(a, st));
    assert(s10.jobs[1].d == digest(lines_of(a, st)) && s10.jobs[1].shape == a);
    let s11 = p_step_v(s10, PAction::JobBuild { j: 1 }, v)->Some_0;
    assert(s11.entries[h].status == Status::Failed && !s11.classes.contains_key(CName::P(h)));
    let s12 = p_step_v(s11, PAction::JobBuild { j: 2 }, v)->Some_0;
    assert(s12.entries[h].status == Status::Failed && !s12.classes.contains_key(CName::P(h)));
    let s13 = p_step_v(s12, PAction::RunEnd { r: 1 }, v)->Some_0;
    let s14 = p_step_v(s13, PAction::RunEnd { r: 2 }, v)->Some_0;
    let s15 = p_step_v(s14, PAction::RunBegin { r: 3, shape: b, sync: false }, v)->Some_0;
    let s16 = p_step_v(s15, PAction::ForCheck { r: 3 }, v)->Some_0;
    assert(s16.runs[3].phase == RPhase::Running && s16.runs[3].gen is None);
}

/// Unique class names alone do not close the persistent case: without Build's shape/stamp check, a's job
/// compiles a's lines under b's entry, the entry names a's digest-named class, and every later run of b
/// passes the check and walks a's code.
pub proof fn witness_unique_names_alone_leave_the_persistent_case(a: Shape, b: Shape, st: Stamp)
    requires
        a != b,
        crc32(a) == crc32(b),
        lines_of(a, st) != lines_of(b, st),
{
    let v = PVariant { build_checks: false, unique_names: true, readback_checks: true };
    let h = hash_of(a);
    let da = digest(lines_of(a, st));
    let s0 = p_start(st);
    let s1 = p_step_v(s0, PAction::RunBegin { r: 1, shape: a, sync: false }, v)->Some_0;
    let s2 = p_step_v(s1, PAction::RunBegin { r: 2, shape: b, sync: false }, v)->Some_0;
    let s3 = p_step_v(s2, PAction::ForCheck { r: 1 }, v)->Some_0;
    let s4 = p_step_v(s3, PAction::ForCheck { r: 2 }, v)->Some_0;
    let s5 = p_step_v(s4, PAction::ForEntry { r: 1 }, v)->Some_0;
    let s6 = p_step_v(s5, PAction::ForEntry { r: 2 }, v)->Some_0;
    let s7 = p_step_v(s6, PAction::ForSrc { r: 2 }, v)->Some_0;
    let s8 = p_step_v(s7, PAction::ForSrc { r: 1 }, v)->Some_0;
    let s9 = p_step_v(s8, PAction::ForSpawn { r: 1, j: 1 }, v)->Some_0;
    let s10 = p_step_v(s9, PAction::ForSpawn { r: 2, j: 2 }, v)->Some_0;
    assert(s10.entries[h].status == Status::Pending && s10.entries[h].shape == b && s10.src[h] == lines_of(a, st));
    assert(s10.jobs[1].d == da);
    let s11 = p_step_v(s10, PAction::JobBuild { j: 1 }, v)->Some_0;
    assert(s11.entries[h].shape == b && s11.entries[h].status == Status::Ok && s11.entries[h].cls == Some(CName::D(da)));
    assert(s11.classes[CName::D(da)].lines == lines_of(a, st));
    let s12 = p_step_v(s11, PAction::JobBuild { j: 2 }, v)->Some_0;
    let s13 = p_step_v(s12, PAction::RunEnd { r: 1 }, v)->Some_0;
    let s14 = p_step_v(s13, PAction::RunEnd { r: 2 }, v)->Some_0;
    let s15 = p_step_v(s14, PAction::RunBegin { r: 3, shape: b, sync: false }, v)->Some_0;
    let s16 = p_step_v(s15, PAction::ForCheck { r: 3 }, v)->Some_0;
    assert(hash_of(b) == h);
    assert(s16.runs[3].gen == Some(CName::D(da)));
    let s17 = p_step_v(s16, PAction::Walk { r: 3 }, v)->Some_0;
    assert(s17.execs[0] == (b, st, lines_of(a, st)));
    assert(!execs_ok(s17));
}

/// The mid-run swap (W-O2a) survives Build's check and the read-back check: b's entry and lines are b's
/// own, so b's build is legitimate, but it recompiles the class name a's run is walking.
pub proof fn witness_build_check_leaves_the_mid_run_swap(a: Shape, b: Shape, st: Stamp)
    requires
        a != b,
        crc32(a) == crc32(b),
        lines_of(a, st) != lines_of(b, st),
{
    let v = PVariant { build_checks: true, unique_names: false, readback_checks: true };
    let h = hash_of(a);
    let s0 = p_start(st);
    let s1 = p_step_v(s0, PAction::RunBegin { r: 1, shape: a, sync: true }, v)->Some_0;
    let s2 = p_step_v(s1, PAction::ForCheck { r: 1 }, v)->Some_0;
    let s3 = p_step_v(s2, PAction::ForEntry { r: 1 }, v)->Some_0;
    let s4 = p_step_v(s3, PAction::ForSrc { r: 1 }, v)->Some_0;
    let s5 = p_step_v(s4, PAction::ForSpawn { r: 1, j: 0 }, v)->Some_0;
    let s6 = p_step_v(s5, PAction::ForInlineBuild { r: 1 }, v)->Some_0;
    assert(s5.entries[h].status == Status::Pending && s5.entries[h].shape == a && s5.src[h] == lines_of(a, st));
    assert(s5.runs[1].digest == digest(lines_of(a, st)));
    let s7 = p_step_v(s6, PAction::ForReadBack { r: 1 }, v)->Some_0;
    assert(s7.runs[1].gen == Some(CName::P(h)));
    let s8 = p_step_v(s7, PAction::Walk { r: 1 }, v)->Some_0;
    let s9 = p_step_v(s8, PAction::RunBegin { r: 2, shape: b, sync: true }, v)->Some_0;
    let s10 = p_step_v(s9, PAction::ForCheck { r: 2 }, v)->Some_0;
    assert(s10.runs[2].phase == RPhase::Write1);
    let s11 = p_step_v(s10, PAction::ForEntry { r: 2 }, v)->Some_0;
    let s12 = p_step_v(s11, PAction::ForSrc { r: 2 }, v)->Some_0;
    let s13 = p_step_v(s12, PAction::ForSpawn { r: 2, j: 0 }, v)->Some_0;
    let s14 = p_step_v(s13, PAction::ForInlineBuild { r: 2 }, v)->Some_0;
    assert(s13.entries[h].status == Status::Pending && s13.entries[h].shape == b && s13.src[h] == lines_of(b, st));
    assert(s13.runs[2].digest == digest(lines_of(b, st)));
    assert(s14.classes[CName::P(h)].lines == lines_of(b, st));
    let s15 = p_step_v(s14, PAction::Walk { r: 1 }, v)->Some_0;
    assert(s14.runs[1].gen == Some(CName::P(h)) && s14.runs[1].phase == RPhase::Running && !s14.runs[1].failed);
    assert(s15.execs[1] == (a, st, lines_of(b, st)));
    assert(!execs_ok(s15));
}

/// With unique names and Build's check but the read-back as built, a sync run of a whose read-back
/// comes after b's build is given b's class (the entry now names it): the read-back needs the checks too.
/// The repaired read-back refuses it on the same state.
pub proof fn witness_unique_names_need_the_readback_check(a: Shape, b: Shape, st: Stamp)
    requires
        a != b,
        crc32(a) == crc32(b),
        lines_of(a, st) != lines_of(b, st),
{
    let v = PVariant { build_checks: true, unique_names: true, readback_checks: false };
    let h = hash_of(a);
    let da = digest(lines_of(a, st));
    let db = digest(lines_of(b, st));
    let s0 = p_start(st);
    let s1 = p_step_v(s0, PAction::RunBegin { r: 1, shape: a, sync: true }, v)->Some_0;
    let s2 = p_step_v(s1, PAction::ForCheck { r: 1 }, v)->Some_0;
    let s3 = p_step_v(s2, PAction::ForEntry { r: 1 }, v)->Some_0;
    let s4 = p_step_v(s3, PAction::ForSrc { r: 1 }, v)->Some_0;
    let s5 = p_step_v(s4, PAction::ForSpawn { r: 1, j: 0 }, v)->Some_0;
    let s6 = p_step_v(s5, PAction::ForInlineBuild { r: 1 }, v)->Some_0;
    assert(s5.entries[h].status == Status::Pending && s5.entries[h].shape == a && s5.src[h] == lines_of(a, st));
    assert(s5.runs[1].digest == da);
    assert(s6.entries[h].cls == Some(CName::D(da)) && s6.runs[1].phase == RPhase::ReadBack);
    // b's sync run completes its build before a's read-back
    let s7 = p_step_v(s6, PAction::RunBegin { r: 2, shape: b, sync: true }, v)->Some_0;
    let s8 = p_step_v(s7, PAction::ForCheck { r: 2 }, v)->Some_0;
    assert(s8.runs[2].phase == RPhase::Write1);
    let s9 = p_step_v(s8, PAction::ForEntry { r: 2 }, v)->Some_0;
    let s10 = p_step_v(s9, PAction::ForSrc { r: 2 }, v)->Some_0;
    let s11 = p_step_v(s10, PAction::ForSpawn { r: 2, j: 0 }, v)->Some_0;
    let s12 = p_step_v(s11, PAction::ForInlineBuild { r: 2 }, v)->Some_0;
    assert(s11.entries[h].status == Status::Pending && s11.entries[h].shape == b && s11.src[h] == lines_of(b, st));
    assert(s11.runs[2].digest == db);
    assert(s12.entries[h].cls == Some(CName::D(db)) && s12.classes[CName::D(db)].lines == lines_of(b, st));
    // the repaired read-back refuses on this state
    assert(readback(s12, s12.runs[1], p_repaired()) is None);
    let s13 = p_step_v(s12, PAction::ForReadBack { r: 1 }, v)->Some_0;
    assert(s13.runs[1].gen == Some(CName::D(db)));
    let s14 = p_step_v(s13, PAction::Walk { r: 1 }, v)->Some_0;
    assert(s14.execs[0] == (a, st, lines_of(b, st)));
    assert(!execs_ok(s14));
}

/// A valid outcome under the full repair, with a collision: two colliding shapes each compile their own
/// class (named by the digest of their lines) and each run walks its own code, before and after the
/// other's build.
pub proof fn witness_repair_keeps_both_colliding_plans(a: Shape, b: Shape, st: Stamp)
    requires
        a != b,
        crc32(a) == crc32(b),
        digest(lines_of(a, st)) != digest(lines_of(b, st)),
{
    let v = p_repaired();
    let h = hash_of(a);
    let da = digest(lines_of(a, st));
    let db = digest(lines_of(b, st));
    let s0 = p_start(st);
    let s1 = p_step_v(s0, PAction::RunBegin { r: 1, shape: a, sync: true }, v)->Some_0;
    let s2 = p_step_v(s1, PAction::ForCheck { r: 1 }, v)->Some_0;
    let s3 = p_step_v(s2, PAction::ForEntry { r: 1 }, v)->Some_0;
    let s4 = p_step_v(s3, PAction::ForSrc { r: 1 }, v)->Some_0;
    let s5 = p_step_v(s4, PAction::ForSpawn { r: 1, j: 0 }, v)->Some_0;
    let s6 = p_step_v(s5, PAction::ForInlineBuild { r: 1 }, v)->Some_0;
    assert(s5.entries[h].status == Status::Pending && s5.entries[h].shape == a && s5.src[h] == lines_of(a, st));
    assert(s5.runs[1].digest == da);
    let s7 = p_step_v(s6, PAction::ForReadBack { r: 1 }, v)->Some_0;
    assert(s7.runs[1].gen == Some(CName::D(da)));
    let s8 = p_step_v(s7, PAction::Walk { r: 1 }, v)->Some_0;
    let s9 = p_step_v(s8, PAction::RunBegin { r: 2, shape: b, sync: true }, v)->Some_0;
    let s10 = p_step_v(s9, PAction::ForCheck { r: 2 }, v)->Some_0;
    let s11 = p_step_v(s10, PAction::ForEntry { r: 2 }, v)->Some_0;
    let s12 = p_step_v(s11, PAction::ForSrc { r: 2 }, v)->Some_0;
    let s13 = p_step_v(s12, PAction::ForSpawn { r: 2, j: 0 }, v)->Some_0;
    let s14 = p_step_v(s13, PAction::ForInlineBuild { r: 2 }, v)->Some_0;
    assert(s13.entries[h].status == Status::Pending && s13.entries[h].shape == b && s13.src[h] == lines_of(b, st));
    assert(s13.runs[2].digest == db);
    let s15 = p_step_v(s14, PAction::ForReadBack { r: 2 }, v)->Some_0;
    assert(s15.runs[2].gen == Some(CName::D(db)));
    let s16 = p_step_v(s15, PAction::Walk { r: 1 }, v)->Some_0;
    let s17 = p_step_v(s16, PAction::Walk { r: 2 }, v)->Some_0;
    assert(s15.classes[CName::D(da)].lines == lines_of(a, st));
    assert(s17.execs.len() == 3);
    assert(s17.execs[0] == (a, st, lines_of(a, st)));
    assert(s17.execs[1] == (a, st, lines_of(a, st)));
    assert(s17.execs[2] == (b, st, lines_of(b, st)));
    assert(execs_ok(s17)) by {
        assert forall|i: int| 0 <= i < s17.execs.len() implies (#[trigger] s17.execs[i]).2 == lines_of(s17.execs[i].0, s17.execs[i].1) by {}
    }
}

// ---------------------------------------------------------------------------------------- the repaired system

pub open spec fn q_run_ok(rr: Run) -> bool {
    &&& (rr.phase != RPhase::Running ==> rr.gen is None)
    &&& (digested(rr.phase) ==> rr.digest == digest(lines_of(rr.shape, rr.stamp)))
    &&& (rr.gen is Some ==> rr.gen == Some(CName::D(digest(lines_of(rr.shape, rr.stamp)))))
}

pub open spec fn q_entry_ok(e: Entry) -> bool {
    &&& (e.cls is None || e.cls->Some_0 is D)
    &&& (e.status == Status::Ok ==> e.cls == Some(CName::D(digest(lines_of(e.shape, e.stamp)))))
}

pub open spec fn q_inv(s: PSt) -> bool {
    &&& forall|r: nat| #[trigger] s.runs.contains_key(r) ==> q_run_ok(s.runs[r])
    &&& forall|c: CName| #[trigger] s.classes.contains_key(c) && c is D ==> digest(s.classes[c].lines) == c->D_0
    &&& forall|h: int| #[trigger] s.entries.contains_key(h) ==> q_entry_ok(s.entries[h])
    &&& forall|j: nat| #[trigger] s.jobs.contains_key(j) ==> s.jobs[j].d == digest(lines_of(s.jobs[j].shape, s.jobs[j].stamp))
    &&& execs_ok(s)
}

/// The repaired system's only premise besides P-SHA: no role writes ^IVG.CypherCompiled(h) itself.
pub open spec fn q_premise(a: PAction) -> bool {
    match a {
        PAction::PlantEntry { .. } => false,
        _ => true,
    }
}

pub proof fn lemma_q_build_preserves(s: PSt, h: int, d: int, gs: Shape, gst: Stamp)
    requires
        q_inv(s),
        digest_injective(),
        d == digest(lines_of(gs, gst)),
    ensures
        q_inv(build(s, h, d, gs, gst, p_repaired())),
        build(s, h, d, gs, gst, p_repaired()).runs == s.runs,
        build(s, h, d, gs, gst, p_repaired()).jobs == s.jobs,
        build(s, h, d, gs, gst, p_repaired()).execs == s.execs,
{
    let v = p_repaired();
    let s2 = build(s, h, d, gs, gst, v);
    if !s.entries.contains_key(h) || s.entries[h].status != Status::Pending || !s.src.contains_key(h) {
    } else if digest(s.src[h]) != d || s.entries[h].shape != gs || s.entries[h].stamp != gst {
        assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies q_entry_ok(s2.entries[k]) by {
            assert(q_entry_ok(s.entries[k]));
        }
    } else {
        assert forall|c: CName| #[trigger] s2.classes.contains_key(c) && c is D implies digest(s2.classes[c].lines) == c->D_0 by {
            if c != CName::D(d) { assert(s.classes.contains_key(c)); }
        }
        assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies q_entry_ok(s2.entries[k]) by {
            assert(q_entry_ok(s.entries[k]));
        }
    }
}

/// The repair (unique class names, Build's shape/stamp check, the read-back's checks) satisfies L1 for
/// every interleaving, colliding shapes, concurrent deploys and rdf_props recompiles, and planted lines
/// included: the premises P-NO-COLLISION and P-QUIESCENT are no longer needed.
pub proof fn lemma_q_step_preserves_inv(s: PSt, a: PAction)
    requires
        q_inv(s),
        digest_injective(),
        q_premise(a),
        p_step_v(s, a, p_repaired()) is Some,
    ensures
        q_inv(p_step_v(s, a, p_repaired())->Some_0),
{
    let v = p_repaired();
    let s2 = p_step_v(s, a, v)->Some_0;
    match a {
        PAction::RunBegin { r, shape, sync } => {
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                if k != r { assert(q_run_ok(s.runs[k])); }
            }
        }
        PAction::ForCheck { r } => {
            let rr = s.runs[r];
            let h = hash_of(rr.shape);
            assert(q_run_ok(rr));
            let out = for_check(s, rr, v);
            if out.gen is Some {
                assert(q_entry_ok(s.entries[h]));
            }
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                if k != r { assert(q_run_ok(s.runs[k])); }
            }
        }
        PAction::ForEntry { r } => {
            let h = hash_of(s.runs[r].shape);
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                assert(q_run_ok(s.runs[k]));
            }
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies q_entry_ok(s2.entries[k]) by {
                if k != h { assert(q_entry_ok(s.entries[k])); }
            }
        }
        PAction::ForSrc { r } => {
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                assert(q_run_ok(s.runs[k]));
            }
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies q_entry_ok(s2.entries[k]) by {
                assert(q_entry_ok(s.entries[k]));
            }
        }
        PAction::ForSpawn { r, j } => {
            let rr = s.runs[r];
            assert(q_run_ok(rr));
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                assert(q_run_ok(s.runs[k]));
            }
        }
        PAction::ForInlineBuild { r } => {
            let rr = s.runs[r];
            assert(q_run_ok(rr));
            lemma_q_build_preserves(s, hash_of(rr.shape), rr.digest, rr.shape, rr.stamp);
            let s1 = build(s, hash_of(rr.shape), rr.digest, rr.shape, rr.stamp, v);
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                assert(q_run_ok(s1.runs[k]));
            }
        }
        PAction::ForReadBack { r } => {
            let rr = s.runs[r];
            let h = hash_of(rr.shape);
            assert(q_run_ok(rr));
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                if k != r { assert(q_run_ok(s.runs[k])); }
            }
        }
        PAction::JobBuild { j } => {
            let jb = s.jobs[j];
            lemma_q_build_preserves(s, jb.h, jb.d, jb.shape, jb.stamp);
        }
        PAction::Walk { r } => {
            let rr = s.runs[r];
            assert(q_run_ok(rr));
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                assert(q_run_ok(s.runs[k]));
            }
            if rr.gen is Some && s.classes.contains_key(rr.gen->Some_0) {
                let c = rr.gen->Some_0;
                assert(digest(s.classes[c].lines) == digest(lines_of(rr.shape, rr.stamp)));
                assert(s.classes[c].lines == lines_of(rr.shape, rr.stamp));
            }
            assert forall|i: int| 0 <= i < s2.execs.len() implies (#[trigger] s2.execs[i]).2 == lines_of(s2.execs[i].0, s2.execs[i].1) by {
                if i < s.execs.len() {
                    assert(s2.execs[i] == s.execs[i]);
                }
            }
        }
        PAction::RunEnd { r } => {
            assert forall|k: nat| #[trigger] s2.runs.contains_key(k) implies q_run_ok(s2.runs[k]) by {
                assert(q_run_ok(s.runs[k]));
            }
        }
        PAction::Deploy { recompiled, deployed } => {
            assert forall|c: CName| #[trigger] s2.classes.contains_key(c) && c is D implies digest(s2.classes[c].lines) == c->D_0 by {
                assert(s.classes.contains_key(c));
            }
            if !deployed {
                assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies q_entry_ok(s2.entries[k]) by {
                    assert(q_entry_ok(s.entries[k]));
                }
            }
        }
        PAction::LayoutChange => {
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies q_entry_ok(s2.entries[k]) by {
                assert(q_entry_ok(s.entries[k]));
            }
        }
        PAction::Tick { d } => {
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies q_entry_ok(s2.entries[k]) by {
                assert(q_entry_ok(s.entries[k]));
            }
        }
        PAction::PlantEntry { h, e } => {}
        PAction::PlantSrc { h, lines } => {
            assert forall|k: int| #[trigger] s2.entries.contains_key(k) implies q_entry_ok(s2.entries[k]) by {
                assert(q_entry_ok(s.entries[k]));
            }
        }
        PAction::JobQuit { j } => {}
    }
}

/// The repaired system starts in its invariant.
pub proof fn lemma_q_init(st: Stamp)
    ensures q_inv(p_start(st)),
{
}

} // verus!
