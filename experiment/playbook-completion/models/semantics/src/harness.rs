//! Check harness (derived from models/breadth-a/src/harness.rs, copied, not shared): every check states its
//! mechanism, object, design, the law it attributes a counterexample to, the findings or exception it stands for,
//! and its expectation; the harness runs the explorer and records whether the expectation was met.
//!
//! - `Expect::Pass`: no violation of any kept property and the state cap not reached (exhaustive within the
//!   model's declared bounds).
//! - `Expect::Violation(name)`: the explorer reports a violation of exactly that property (shortest trace).
//! - `Keep` keeps only named properties, so a counterexample is attributed to one law.
//! - `Reach` turns a goal into the invariant "never: goal"; a sharpness check expects its violation.
//! - `fair_lasso` (added here): a liveness check under weak fairness. It explores the whole reachable graph and
//!   looks for a strongly connected set of states, all satisfying `stuck`, that contains a transition whose action
//!   is `fair` (the fairly scheduled worker). Such a cycle is an infinite fair run on which `stuck` holds forever.
//!   The explorer itself checks only AG EF, which a starvation does not violate (the adversary could stop).
use explorer::*;
use std::collections::{HashMap, VecDeque};
use std::fmt::Debug;
use std::hash::Hash;

pub fn limits() -> Limits {
    Limits { max_states: 5_000_000, max_depth: usize::MAX, check_deadlock: false }
}

#[derive(Clone, Debug)]
pub enum Expect {
    Pass,
    Violation(&'static str),
}

#[derive(Clone, Debug)]
pub struct Meta {
    pub mechanism: &'static str,
    pub family: &'static str,
    pub instance: String,
    pub objects: Vec<&'static str>,
    /// as-built | reviewed | control | sharpness | exception
    pub design: &'static str,
    /// safety | progress | sharpness | liveness
    pub kind: &'static str,
    pub law: &'static str,
    pub findings: Vec<&'static str>,
    pub exception: &'static str,
}

pub struct Outcome {
    pub id: String,
    pub meta: Meta,
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

pub fn show<S: Debug, A: Debug>(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n  init: {:?}\n", c.property, c.kind,
                          c.steps.len(), c.init);
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:?}\n      -> {:?}\n", i + 1, a, s);
    }
    out
}

pub fn judge<S: Debug, A: Debug>(id: &str, meta: Meta, expect: Expect, rep: Report<S, A>) -> Outcome {
    let found = rep.violation.as_ref().map(|c| c.property.clone()).unwrap_or_default();
    let capped = rep.truncated;
    let met = match &expect {
        Expect::Pass => rep.violation.is_none() && !capped,
        Expect::Violation(p) => rep.violation.as_ref().is_some_and(|c| c.property == *p),
    };
    Outcome {
        id: id.to_string(), meta,
        expect: match &expect { Expect::Pass => "exhaustive pass".into(), Expect::Violation(p) => format!("violation of '{p}'") },
        met, found, states: rep.states, transitions: rep.transitions, depth: rep.depth, truncated: capped,
        seconds: rep.seconds, trace: rep.violation.as_ref().map(|c| show(c)).unwrap_or_default(),
    }
}

pub fn check<M: Model>(id: &str, meta: Meta, expect: Expect, m: &M) -> Outcome {
    judge(id, meta, expect, explore(m, limits()))
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
    /// Keep exactly the named invariants and action properties (names are looked up in both classes).
    pub fn only(m: &'a M, names: &[&'static str]) -> Self {
        Keep { m, inv: Some(names.to_vec()), ap: Some(names.to_vec()), ag: Some(vec![]) }
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

/// Sharpness: expects the goal to be reachable.
pub fn reach<M: Model>(id: &str, mut meta: Meta, m: &M, name: &'static str, goal: fn(&M::State) -> bool) -> Outcome
where
    M::State: 'static,
{
    meta.kind = "sharpness";
    let r = Reach { m, name, goal };
    check(id, meta, Expect::Violation(name), &r)
}

/// Liveness under weak fairness (see the module comment). Returns a report in the explorer's shape: a violation
/// named `name` whose trace is a path to the first state of a fair cycle followed by the cycle itself.
pub fn fair_lasso<M: Model>(m: &M, name: &'static str, stuck: fn(&M::State) -> bool, fair: fn(&M::Action) -> bool)
                           -> Report<M::State, M::Action> {
    let start = std::time::Instant::now();
    let mut states: Vec<M::State> = vec![];
    let mut index: HashMap<M::State, usize> = HashMap::new();
    let mut parent: Vec<Option<(usize, M::Action)>> = vec![];
    let mut edges: Vec<Vec<(usize, M::Action)>> = vec![];
    let mut q = VecDeque::new();
    let mut truncated = false;
    for s in m.init_states() {
        if index.contains_key(&s) { continue; }
        index.insert(s.clone(), states.len());
        states.push(s);
        parent.push(None);
        edges.push(vec![]);
        q.push_back(states.len() - 1);
    }
    let mut transitions = 0;
    while let Some(i) = q.pop_front() {
        if !m.within_bounds(&states[i]) { continue; }
        let s = states[i].clone();
        for a in m.actions(&s) {
            let Some(n) = m.next(&s, &a) else { continue };
            transitions += 1;
            let j = match index.get(&n) {
                Some(&j) => j,
                None => {
                    if states.len() >= limits().max_states { truncated = true; continue; }
                    let j = states.len();
                    index.insert(n.clone(), j);
                    states.push(n);
                    parent.push(Some((i, a.clone())));
                    edges.push(vec![]);
                    q.push_back(j);
                    j
                }
            };
            edges[i].push((j, a));
        }
    }
    // Tarjan's SCC over the subgraph of `stuck` states (iterative).
    let n = states.len();
    let inside: Vec<bool> = states.iter().map(|s| stuck(s)).collect();
    let mut idx = vec![usize::MAX; n];
    let mut low = vec![0usize; n];
    let mut on = vec![false; n];
    let mut stack: Vec<usize> = vec![];
    let mut comp = vec![usize::MAX; n];
    let mut next_idx = 0;
    let mut ncomp = 0;
    for root in 0..n {
        if !inside[root] || idx[root] != usize::MAX { continue; }
        let mut call: Vec<(usize, usize)> = vec![(root, 0)];
        idx[root] = next_idx; low[root] = next_idx; next_idx += 1; stack.push(root); on[root] = true;
        while let Some(&(v, ei)) = call.last() {
            if ei < edges[v].len() {
                let w = edges[v][ei].0;
                call.last_mut().unwrap().1 += 1;
                if !inside[w] { continue; }
                if idx[w] == usize::MAX {
                    idx[w] = next_idx; low[w] = next_idx; next_idx += 1; stack.push(w); on[w] = true;
                    call.push((w, 0));
                } else if on[w] {
                    low[v] = low[v].min(idx[w]);
                }
            } else {
                call.pop();
                if let Some(&(u, _)) = call.last() { low[u] = low[u].min(low[v]); }
                if low[v] == idx[v] {
                    loop {
                        let w = stack.pop().unwrap();
                        on[w] = false;
                        comp[w] = ncomp;
                        if w == v { break; }
                    }
                    ncomp += 1;
                }
            }
        }
    }
    // A fair transition inside one component: u -> w with comp[u] == comp[w] (a self-loop counts).
    let mut witness: Option<(usize, usize)> = None;
    'outer: for u in 0..n {
        if !inside[u] { continue; }
        for (w, a) in &edges[u] {
            if inside[*w] && comp[*w] == comp[u] && fair(a) { witness = Some((u, *w)); break 'outer; }
        }
    }
    let violation = witness.map(|(u, w)| {
        // prefix: init -> u
        let mut steps: Vec<(M::Action, M::State)> = vec![];
        let mut k = u;
        while let Some((p, a)) = &parent[k] { steps.push((a.clone(), states[k].clone())); k = *p; }
        steps.reverse();
        let init = states[k].clone();
        // the fair step u -> w, then a path w -> u inside the component (BFS)
        let fair_a = edges[u].iter().find(|(x, a)| *x == w && fair(a)).unwrap().1.clone();
        steps.push((fair_a, states[w].clone()));
        if w != u {
            let c = comp[u];
            let mut prev: HashMap<usize, (usize, M::Action)> = HashMap::new();
            let mut bq = VecDeque::from([w]);
            let mut seen = vec![false; n];
            seen[w] = true;
            while let Some(x) = bq.pop_front() {
                if x == u { break; }
                for (y, a) in &edges[x] {
                    if inside[*y] && comp[*y] == c && !seen[*y] { seen[*y] = true; prev.insert(*y, (x, a.clone())); bq.push_back(*y); }
                }
            }
            let mut back: Vec<(M::Action, M::State)> = vec![];
            let mut x = u;
            while x != w { let (p, a) = prev[&x].clone(); back.push((a, states[x].clone())); x = p; }
            back.reverse();
            steps.extend(back);
        }
        Counterexample { property: name.to_string(), kind: ViolationKind::AlwaysPossibly, init, steps }
    });
    Report { states: n, transitions, depth: 0, truncated, seconds: start.elapsed().as_secs_f64(), violation }
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

/// Shorthand for a Meta.
#[allow(clippy::too_many_arguments)]
pub fn meta(mechanism: &'static str, family: &'static str, instance: &str, objects: &[&'static str], design: &'static str,
            kind: &'static str, law: &'static str, findings: &[&'static str], exception: &'static str) -> Meta {
    Meta { mechanism, family, instance: instance.to_string(), objects: objects.to_vec(), design, kind, law,
           findings: findings.to_vec(), exception }
}

#[allow(dead_code)]
pub fn _assert_hash<T: Hash + Eq>() {}
