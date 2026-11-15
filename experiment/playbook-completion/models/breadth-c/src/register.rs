//! M6: re-registering a FHIR graph with new settings and json links (F-1511; module 15).
//!
//! As built at 3eaa79cf (`Graph.KG.FHIRGraph.Register`, iris_src/src/Graph/KG/FHIRGraph.cls:167-280): the
//! `fhir_graphs` upsert (endpoints, denylist, interval) runs with no transaction (`Exec`, autocommit) before `Open`
//! and `LoadColumns`, which can throw (schema metadata, `HS.FHIRServer.Schema.LoadSchema`); the `json_links` update
//! runs next, then, when the links changed, `Rebuild`, which can fail. A throw returns
//! `{"status":"error"}` (:276-278) with the earlier writes kept.
//! Reviewed (F-1511 "what would close it"; SYS-I3): validate first, then write the row and the links in one
//! transaction; a failed rebuild after a links change rolls the links back (or the call reports the partial state).
//!
//! Properties:
//! - `a refused register changes nothing` (SYS-I3): when the call ends refused, settings and links are as before;
//! - `registered links match the graph`: when the call ends, the stored links are the ones the graph was built from,
//!   or the call reported the rebuild as pending (as built it does: FHIRGraph.cls:262-271);
//! - always possibly: the call ends;
//! - witness: a register that changes settings and links and rebuilds succeeds.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, ControlUpsertOutsideTxn }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Pc { Start, Upserted, Loaded, LinksWritten, Done { ok: bool } }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub pc: Pc,
    /// committed state of the registry row: settings new?, links new?
    pub settings_new: bool,
    pub links_new: bool,
    /// the links the projected graph was (re)built from are the new ones
    pub graph_new: bool,
    /// the reviewed design's pending (uncommitted) writes
    pub pend_settings: bool,
    pub pend_links: bool,
    /// as built: a failed rebuild after a links change is reported (`rebuilt: false`, last_error "json_links
    /// changed; rebuild pending", FHIRGraph.cls:262-271) and the call answers registered
    pub rebuild_pending: bool,
}

#[derive(Clone, Debug)]
pub enum A { Upsert, Load { ok: bool }, WriteLinks, Rebuild { ok: bool } }

pub struct M { pub design: Design }

impl M {
    fn in_txn_settings(&self) -> bool { self.design == Design::Reviewed }
    fn in_txn_links(&self) -> bool { self.design != Design::AsBuilt }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { pc: Pc::Start, settings_new: false, links_new: false, graph_new: false, pend_settings: false,
                 pend_links: false, rebuild_pending: false }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::Upsert, A::Load { ok: true }, A::Load { ok: false }, A::WriteLinks, A::Rebuild { ok: true },
             A::Rebuild { ok: false }]
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut t = s.clone();
        let refuse = |t: &mut S| {
            // the error path: pending writes are rolled back; committed ones stay
            t.pend_settings = false;
            t.pend_links = false;
            t.pc = Pc::Done { ok: false };
        };
        match a {
            A::Upsert => {
                if s.pc != Pc::Start { return None; }
                if self.in_txn_settings() { t.pend_settings = true; } else { t.settings_new = true; }
                t.pc = Pc::Upserted;
            }
            A::Load { ok } => {
                if s.pc != Pc::Upserted { return None; }
                if *ok { t.pc = Pc::Loaded; } else { refuse(&mut t); }
            }
            A::WriteLinks => {
                if s.pc != Pc::Loaded { return None; }
                if self.in_txn_links() { t.pend_links = true; } else { t.links_new = true; }
                t.pc = Pc::LinksWritten;
            }
            A::Rebuild { ok } => {
                if s.pc != Pc::LinksWritten { return None; }
                if *ok {
                    t.graph_new = true;
                    if s.pend_settings { t.settings_new = true; }
                    if s.pend_links { t.links_new = true; }
                    t.pend_settings = false;
                    t.pend_links = false;
                    t.pc = Pc::Done { ok: true };
                } else if self.design == Design::AsBuilt {
                    t.rebuild_pending = true;
                    t.pc = Pc::Done { ok: true };
                } else {
                    refuse(&mut t);
                }
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("a refused register changes nothing", |s: &S|
                s.pc != Pc::Done { ok: false } || (!s.settings_new && !s.links_new)),
            invariant("registered links match the graph", |s: &S|
                !matches!(s.pc, Pc::Done { .. }) || s.links_new == s.graph_new || s.rebuild_pending),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("the call ends", |s: &S| matches!(s.pc, Pc::Done { .. }))]
    }
}

pub struct Witness { pub m: M }
impl Model for Witness {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { self.m.init_states() }
    fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
    fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant("a changed register succeeds", |s: &S|
            !(s.pc == Pc::Done { ok: true } && s.settings_new && s.links_new && s.graph_new))]
    }
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<22} pc={:?} committed settings_new={} links_new={} graph_new={} pending=({},{})\n",
                        i + 1, format!("{:?}", a), s.pc, s.settings_new, s.links_new, s.graph_new, s.pend_settings,
                        s.pend_links);
    }
    out
}
