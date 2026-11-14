//! Wrappers shared by the machines: keep a subset of a machine's properties (so one violation does not hide
//! another), and sharpness checks (a key state or step must be reachable: the check expects a "violation" of
//! "never <goal>", whose trace is the witness).
use explorer::*;

/// The machine `m` with only the properties whose names are in `keep` (all of them when `keep` is empty), plus
/// optional extra state/step goals turned into "never" properties for sharpness checks.
pub struct Only<M: Model> {
    pub m: M,
    pub keep: Vec<&'static str>,
    pub never_state: Option<(&'static str, fn(&M::State) -> bool)>,
    pub never_step: Option<(&'static str, fn(&M::State, &M::Action, &M::State) -> bool)>,
}

impl<M: Model> Only<M> {
    pub fn keep(m: M, keep: &[&'static str]) -> Self { Only { m, keep: keep.to_vec(), never_state: None, never_step: None } }
    /// Sharpness: only the "never" goal is checked; a violation is the witness that the goal is reachable.
    pub fn reach_state(m: M, name: &'static str, f: fn(&M::State) -> bool) -> Self {
        Only { m, keep: vec!["<none>"], never_state: Some((name, f)), never_step: None }
    }
    pub fn reach_step(m: M, name: &'static str, f: fn(&M::State, &M::Action, &M::State) -> bool) -> Self {
        Only { m, keep: vec!["<none>"], never_state: None, never_step: Some((name, f)) }
    }
    fn wanted(&self, n: &str) -> bool { self.keep.is_empty() || self.keep.iter().any(|k| *k == n) }
}

impl<M: Model> Model for Only<M> where M::State: 'static, M::Action: 'static {
    type State = M::State;
    type Action = M::Action;
    fn init_states(&self) -> Vec<M::State> { self.m.init_states() }
    fn actions(&self, s: &M::State) -> Vec<M::Action> { self.m.actions(s) }
    fn next(&self, s: &M::State, a: &M::Action) -> Option<M::State> { self.m.next(s, a) }
    fn within_bounds(&self, s: &M::State) -> bool { self.m.within_bounds(s) }
    fn invariants(&self) -> Vec<Invariant<M::State>> {
        let mut v: Vec<_> = self.m.invariants().into_iter().filter(|i| self.wanted(i.name)).collect();
        if let Some((n, f)) = self.never_state {
            v.push(invariant(n, move |s: &M::State| !f(s)));
        }
        v
    }
    fn action_properties(&self) -> Vec<ActionProperty<M::State, M::Action>> {
        let mut v: Vec<_> = self.m.action_properties().into_iter().filter(|p| self.wanted(p.name)).collect();
        if let Some((n, f)) = self.never_step {
            v.push(action_property(n, move |s: &M::State, a: &M::Action, t: &M::State| !f(s, a, t)));
        }
        v
    }
    fn always_possibly(&self) -> Vec<Invariant<M::State>> {
        self.m.always_possibly().into_iter().filter(|g| self.wanted(g.name)).collect()
    }
}
