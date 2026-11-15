//! Family ins_setup (module 01; findings F-0103, F-0102; statements INS-I3.4, INS-B1.12; decisions HD-0101
//! (supported) and HD-0102 (assumption)).
//!
//! Setup = `initialize_schema()` -> `_record_and_initialize` -> `_initialize_schema` (iris_vector_graph/_engine/
//! schema.py:2097-2320, 2410-2720), in order: `Tables` the base DDL (2440-2512; a statement failing for a reason
//! other than "exists" or a privilege is logged at WARNING and setup goes on, 2508-2511), `Marker` the IVG
//! Schema's SQL functions, among them CY_CMP whose class `<package>.funcCYCMP` is the first-use marker
//! (schema_name.py:207-213), `Classes` the ObjectScript deploy (failures are reported in objectscript_failed),
//! `KG` the ^KG bootstrap (a failure is a log line only, 2675-2681), and `Record` write_record (2310-2312). The
//! process can stop between any two steps (an error that escapes, a killed process). A run that reaches the end
//! returns its reply; `warnings` is "what you must act on, each also logged at WARNING" (docs/ADMIN_GUIDE.md:428).
//!
//! First use = `check_first_access` (schema_name.py:218-235) through `FirstAccessCheck` (engine.py:1850-1866): a
//! readable record naming this schema passes; one naming another schema refuses (FR-006); no record passes when the
//! marker class exists (F-0103), else refuses; a record that cannot be read at all is logged at WARNING and the
//! check is skipped (engine.py:1861-1865; HD-0101 permits this documented warning/skip).
//!
//! Environment: the engine's login may be unable to read the record (`unreadable`, chosen initially).
//!
//! Designs: `AsBuilt`; `Reviewed` — no record refuses whatever the marker says (FR-006a; setup is exempt, so the
//! way out stays open), and every passed-over failure is put in `warnings` (the finding's fix); HD-0102: the record
//! is a namespace binding only, written even when the class deploy failed, with each capability's readiness
//! reported separately (here: the deploy failure in the reply). `SilentSkip` (negative control): the reviewed design
//! whose unreadable-record skip is not logged as a warning.
//!
//! Properties:
//! - `INS-I3.4` (spec 262 FR-006a, specs/262-ivg-owned-sql-schema/spec.md:245): an engine is accepted only on a
//!   namespace whose record names its schema, or with a warning when the record cannot be read (HD-0101).
//! - `INS-B1.12`: a reply with no warning and no reported deploy failure means every setup step succeeded.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, SilentSkip }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Step { Tables, Marker, Classes, Kg, Record, Replied, Stopped }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Engine { NotChecked, Accepted { warned: bool }, Refused }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub unreadable: bool,
    pub step: Step,
    pub marker: bool,
    pub record: bool,
    pub failed: bool,
    pub warned: bool,
    pub deploy_failed: bool,
    pub engine: Engine,
}

#[derive(Clone, Debug)]
pub enum A { Ok, Fail, Stop, EngineFirstUse }

pub struct M { pub design: Design }

pub const I34: &str = "INS-I3.4: an engine is accepted only on a namespace whose record names its schema (or with a warning when unreadable)";
pub const B112: &str = "INS-B1.12: a reply with no warning means every setup step succeeded";

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        [false, true].into_iter().map(|unreadable| S { unreadable, step: Step::Tables, marker: false, record: false,
            failed: false, warned: false, deploy_failed: false, engine: Engine::NotChecked }).collect()
    }
    fn actions(&self, _: &S) -> Vec<A> { vec![A::Ok, A::Fail, A::Stop, A::EngineFirstUse] }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let reviewed = self.design != Design::AsBuilt;
        let running = !matches!(s.step, Step::Replied | Step::Stopped);
        match a {
            A::Ok | A::Fail => {
                if !running { return None; }
                let fail = matches!(a, A::Fail);
                match s.step {
                    Step::Tables => {
                        if fail { u.failed = true; if reviewed { u.warned = true; } }
                        u.step = Step::Marker;
                    }
                    Step::Marker => { if fail { return None; } u.marker = true; u.step = Step::Classes; }
                    Step::Classes => { if fail { u.failed = true; u.deploy_failed = true; } u.step = Step::Kg; }
                    Step::Kg => {
                        if fail { u.failed = true; if reviewed { u.warned = true; } }
                        u.step = Step::Record;
                    }
                    Step::Record => { if fail { return None; } u.record = true; u.step = Step::Replied; }
                    Step::Replied | Step::Stopped => return None,
                }
            }
            A::Stop => { if !running { return None; } u.step = Step::Stopped; }
            A::EngineFirstUse => {
                if s.engine != Engine::NotChecked { return None; }
                u.engine = if s.unreadable {
                    Engine::Accepted { warned: self.design != Design::SilentSkip }
                } else if s.record {
                    Engine::Accepted { warned: false }
                } else if s.marker && !reviewed {
                    Engine::Accepted { warned: false }
                } else {
                    Engine::Refused
                };
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(I34, |s: &S| match s.engine {
                Engine::Accepted { warned } => s.record || (s.unreadable && warned),
                _ => true,
            }),
            invariant(B112, |s: &S| s.step != Step::Replied || s.warned || s.deploy_failed || !s.failed),
        ]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("01", "ins_setup");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::SilentSkip };
    vec![
        check("ins_setup-as-built-F0103", md, fam, "as-built", "safety", Expect::Violation(I34), &Keep::invariants(&ab, &[I34])),
        check("ins_setup-as-built-F0102", md, fam, "as-built", "safety", Expect::Violation(B112), &Keep::invariants(&ab, &[B112])),
        check("ins_setup-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rv),
        check("ins_setup-control-silent-skip", md, fam, "control", "safety", Expect::Violation(I34), &ct),
        reach("ins_setup-reviewed-reach-accepted", md, fam, "reviewed", &rv,
              "never: an engine is accepted after a complete setup", |s: &S| s.step == Step::Replied && s.engine == Engine::Accepted { warned: false }),
        reach("ins_setup-reviewed-reach-refused-half-setup", md, fam, "reviewed", &rv,
              "never: an engine is refused on a half set-up namespace", |s: &S| s.step == Step::Stopped && s.marker && s.engine == Engine::Refused),
        reach("ins_setup-reviewed-reach-deploy-failed-bound", md, fam, "reviewed", &rv,
              "never: the record binds a namespace whose class deploy failed (HD-0102)", |s: &S| s.record && s.deploy_failed),
    ]
}
