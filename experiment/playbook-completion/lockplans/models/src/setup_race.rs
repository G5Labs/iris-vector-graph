//! Family setup_race (module 01; gate 3.5-lockplans): two initialize_schema runs at once. Setup takes no lock of its
//! own (iris_vector_graph/_engine/schema.py, schema.py, schema_name.py: no LOCK, no Python lock; footprints/01.json
//! review "none: two concurrent setups are not serialized"); CHANGELOG.md:187-191 treats two processes setting up one
//! namespace as a supported case.
//!
//! `Gate` (LP-01-2a, INS-B1.10, docs/ADMIN_GUIDE.md:370-374: "The first setup that finds edges ... builds the
//! adjacency index from them. It does this once"). bootstrap_kg_global (schema.py:3329-3357): IsSet("kg_built"), then
//! BuildKG (whose BuildNKG tail waits for ^IVG.NKGBuild, TraversalBuild.cls:150, 293), then Set("kg_built"), all
//! unlocked. Property: at most one run builds (and reports kg_built True).
//!
//! `Record` (LP-01-1, INS-I2.8 "Once saved, the schema record is never changed by setup", specs/262 spec.md:333-336;
//! INS-X2.12 refuse when the record names another schema, spec.md:243). The record is read once
//! (_engine/schema.py:2222), the decision taken (:2230-2242), and written at the end by an unconditional Native set
//! (:2309-2312, schema_name.py:194-198). Two setups with different schema names on a namespace with no record.
//! Property: once a run's record is saved and reported, no other run changes it; a run whose schema differs from the
//! saved record is refused.
//!
//! Designs: `AsBuilt`; `Reviewed`: a namespace setup lock (e.g. LOCK +^IVG.Deploy("setup")) held from the check to the
//! set, with a re-check under it (Record: set-if-absent, refuse on mismatch); `Control`: the lock released right after
//! the check (before the work and the set).
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, Control }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum P { Start, Checked(bool), Built, Done, Refused }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    /// Gate: the kg_built mark; Record: the saved record (0 none, 1 or 2 = schema of setup 1 or 2)
    pub mark: u8,
    pub p: [P; 2],
    pub lock: Option<u8>,
    pub builds: u8,
    /// Record: the record each run reported as saved (0 none)
    pub reported: [u8; 2],
}

#[derive(Clone, Debug)]
pub enum A { Check(u8), Work(u8), Set(u8) }

pub struct M { pub design: Design, pub record: bool }

pub const ONCE: &str = "INS-B1.10: the adjacency index is built by one setup run";
pub const KEEP: &str = "INS-I2.8: a saved schema record a run reported is never changed by another run";

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { mark: 0, p: [P::Start; 2], lock: None, builds: 0, reported: [0; 2] }] }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::Check(0), A::Check(1), A::Work(0), A::Work(1), A::Set(0), A::Set(1)]
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        let locking = self.design != Design::AsBuilt;
        match *a {
            A::Check(i) => {
                let k = i as usize;
                if s.p[k] != P::Start { return None; }
                if locking { if s.lock.is_some() { return None; } u.lock = Some(i); }
                if self.record && s.mark != 0 && s.mark != i + 1 {
                    // another schema is recorded: refused (INS-X2.12)
                    u.p[k] = P::Refused;
                    if u.lock == Some(i) { u.lock = None; }
                    return Some(u);
                }
                u.p[k] = P::Checked(s.mark != 0);
                if self.design == Design::Control { u.lock = None; }
            }
            A::Work(i) => {
                let k = i as usize;
                let P::Checked(seen) = s.p[k] else { return None };
                if !self.record && !seen { u.builds += 1; }
                u.p[k] = P::Built;
            }
            A::Set(i) => {
                let k = i as usize;
                if s.p[k] != P::Built { return None; }
                if self.record {
                    if self.design == Design::Reviewed && s.mark != 0 && s.mark != i + 1 {
                        u.p[k] = P::Refused;
                    } else {
                        u.mark = i + 1; // as built: unconditional set (schema_name.py:194-198)
                        u.reported[k] = i + 1;
                        u.p[k] = P::Done;
                    }
                } else {
                    u.mark = 1;
                    u.p[k] = P::Done;
                }
                if u.lock == Some(i) { u.lock = None; }
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        if self.record {
            vec![invariant(KEEP, |s: &S| s.reported.iter().all(|r| *r == 0 || *r == s.mark))]
        } else {
            vec![invariant(ONCE, |s: &S| s.builds <= 1)]
        }
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("01", "setup_race");
    let g = |d| M { design: d, record: false };
    let r = |d| M { design: d, record: true };
    vec![
        check("setup_race-gate-as-built", md, fam, "as-built", "safety", Expect::Violation(ONCE), &g(Design::AsBuilt)),
        check("setup_race-gate-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &g(Design::Reviewed)),
        check("setup_race-gate-control-early-release", md, fam, "control", "safety", Expect::Violation(ONCE), &g(Design::Control)),
        reach("setup_race-gate-reviewed-reach-built-once", md, fam, "reviewed", &g(Design::Reviewed), "never: both runs done after one build",
              |s: &S| s.p == [P::Done; 2] && s.builds == 1),
        check("setup_race-record-as-built", md, fam, "as-built", "safety", Expect::Violation(KEEP), &r(Design::AsBuilt)),
        check("setup_race-record-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &r(Design::Reviewed)),
        check("setup_race-record-control-early-release", md, fam, "control", "safety", Expect::Violation(KEEP), &r(Design::Control)),
        reach("setup_race-record-reviewed-reach-second-refused", md, fam, "reviewed", &r(Design::Reviewed), "never: one run recorded, the other refused",
              |s: &S| s.p.contains(&P::Done) && s.p.contains(&P::Refused)),
    ]
}
