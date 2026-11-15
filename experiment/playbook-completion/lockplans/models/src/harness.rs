//! Shared check harness: every family states each check's expected outcome, the harness runs the explorer and
//! records whether the expectation was met.
//!
//! - `Expect::Pass`: no violation of any kept property, and the state cap was not reached (exhaustive within the
//!   model's declared bounds).
//! - `Expect::Violation(name)`: the explorer reports a violation of exactly that property (shortest trace).
//! - `Reach` wraps a model with a single invariant "not goal"; a sharpness check expects its violation, i.e. the
//!   goal state is reachable.
//! - `Keep` keeps only the named invariants / action properties / AG EF properties of a model, so a check
//!   attributes a counterexample to one property.
use explorer::*;
use std::fmt::Debug;

pub fn limits() -> Limits {
    Limits { max_states: 20_000_000, max_depth: usize::MAX, check_deadlock: false }
}

#[derive(Clone, Debug)]
pub enum Expect {
    Pass,
    Violation(&'static str),
}

pub struct Outcome {
    pub id: String,
    pub module: &'static str,
    pub family: &'static str,
    pub design: &'static str,
    pub kind: &'static str,
    pub expect: String,
    pub met: bool,
    pub found: String,
    pub states: usize,
    pub transitions: usize,
    pub depth: usize,
    pub truncated: bool,
    pub seconds: f64,
    pub trace: String,
}

/// Generic trace printer: action and resulting state, one line each.
pub fn show<S: Debug, A: Debug>(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n  init: {:?}\n", c.property, c.kind,
                          c.steps.len(), c.init);
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:?}\n      -> {:?}\n", i + 1, a, s);
    }
    out
}

#[allow(clippy::too_many_arguments)]
pub fn judge<S: Debug, A: Debug>(id: &str, module: &'static str, family: &'static str, design: &'static str,
                                 kind: &'static str, expect: Expect, rep: Report<S, A>) -> Outcome {
    let found = rep.violation.as_ref().map(|c| c.property.clone()).unwrap_or_default();
    // `explore` sets `truncated` only at the state cap or depth limit (max_depth is unbounded here); a model's own
    // `within_bounds` cut is the declared bound, so a run that stays under the cap is exhaustive within bounds.
    let capped = rep.truncated;
    let met = match &expect {
        Expect::Pass => rep.violation.is_none() && !capped,
        Expect::Violation(p) => rep.violation.as_ref().is_some_and(|c| c.property == *p),
    };
    Outcome {
        id: id.to_string(), module, family, design, kind,
        expect: match &expect { Expect::Pass => "exhaustive pass".into(), Expect::Violation(p) => format!("violation of '{p}'") },
        met, found, states: rep.states, transitions: rep.transitions, depth: rep.depth, truncated: capped,
        seconds: rep.seconds, trace: rep.violation.as_ref().map(|c| show(c)).unwrap_or_default(),
    }
}

/// Run `m` (all its properties) and judge.
#[allow(clippy::too_many_arguments)]
pub fn check<M: Model>(id: &str, module: &'static str, family: &'static str, design: &'static str,
                       kind: &'static str, expect: Expect, m: &M) -> Outcome {
    judge(id, module, family, design, kind, expect, explore(m, limits()))
}

/// Keep only some properties of a model. `None` keeps all of that class; `Some(vec![])` keeps none.
pub struct Keep<'a, M: Model> {
    pub m: &'a M,
    pub inv: Option<Vec<&'static str>>,
    pub ap: Option<Vec<&'static str>>,
    pub ag: Option<Vec<&'static str>>,
}

#[allow(dead_code)]
impl<'a, M: Model> Keep<'a, M> {
    pub fn invariants(m: &'a M, names: &[&'static str]) -> Self {
        Keep { m, inv: Some(names.to_vec()), ap: Some(vec![]), ag: Some(vec![]) }
    }
    pub fn action_props(m: &'a M, names: &[&'static str]) -> Self {
        Keep { m, inv: Some(vec![]), ap: Some(names.to_vec()), ag: Some(vec![]) }
    }
    pub fn progress(m: &'a M) -> Self {
        Keep { m, inv: Some(vec![]), ap: Some(vec![]), ag: None }
    }
    pub fn safety(m: &'a M) -> Self {
        Keep { m, inv: None, ap: None, ag: Some(vec![]) }
    }
}

fn keep<T>(v: Vec<T>, names: &Option<Vec<&'static str>>, name: impl Fn(&T) -> &'static str) -> Vec<T> {
    match names {
        None => v,
        Some(n) => v.into_iter().filter(|x| n.contains(&name(x))).collect(),
    }
}

impl<'a, M: Model> Model for Keep<'a, M> {
    type State = M::State;
    type Action = M::Action;
    fn init_states(&self) -> Vec<M::State> { self.m.init_states() }
    fn actions(&self, s: &M::State) -> Vec<M::Action> { self.m.actions(s) }
    fn next(&self, s: &M::State, a: &M::Action) -> Option<M::State> { self.m.next(s, a) }
    fn within_bounds(&self, s: &M::State) -> bool { self.m.within_bounds(s) }
    fn invariants(&self) -> Vec<Invariant<M::State>> { keep(self.m.invariants(), &self.inv, |i| i.name) }
    fn action_properties(&self) -> Vec<ActionProperty<M::State, M::Action>> {
        keep(self.m.action_properties(), &self.ap, |p| p.name)
    }
    fn always_possibly(&self) -> Vec<Invariant<M::State>> { keep(self.m.always_possibly(), &self.ag, |i| i.name) }
}

/// Sharpness: the goal is reachable iff the explorer reports a violation of "never: <name>".
pub struct Reach<'a, M: Model> {
    pub m: &'a M,
    pub name: &'static str,
    pub goal: fn(&M::State) -> bool,
}

impl<'a, M: Model> Model for Reach<'a, M>
where
    M::State: 'static,
{
    type State = M::State;
    type Action = M::Action;
    fn init_states(&self) -> Vec<M::State> { self.m.init_states() }
    fn actions(&self, s: &M::State) -> Vec<M::Action> { self.m.actions(s) }
    fn next(&self, s: &M::State, a: &M::Action) -> Option<M::State> { self.m.next(s, a) }
    fn within_bounds(&self, s: &M::State) -> bool { self.m.within_bounds(s) }
    fn invariants(&self) -> Vec<Invariant<M::State>> {
        let g = self.goal;
        vec![invariant(self.name, move |s: &M::State| !g(s))]
    }
}

/// A sharpness check: expects the goal to be reachable.
pub fn reach<M: Model>(id: &str, module: &'static str, family: &'static str, design: &'static str, m: &M,
                       name: &'static str, goal: fn(&M::State) -> bool) -> Outcome
where
    M::State: 'static,
{
    let r = Reach { m, name, goal };
    check(id, module, family, design, "sharpness", Expect::Violation(name), &r)
}

pub fn esc(s: &str) -> String {
    let mut o = String::new();
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)),
            c => o.push(c),
        }
    }
    o
}
