//! Shared harness for breadth lane B model checks (playbook §3.3 explorers, §5 controls).
//!
//! Every check states its design (`as-built`, `reviewed`, `control`, `positive`) and its expectation:
//! - `Expect::Pass`: an exhaustive pass within the model's declared bounds (no violation, state cap not reached);
//! - `Expect::Violation(p)`: the explorer must find a violation of property `p` (an as-built design reproducing a
//!   finding, a negative control the checker must catch, or a reachability witness written as "never reaches X").
//!
//! A check *meets* its expectation or not; the binary exits 0 only when every selected check met it. Each check
//! writes `results/<id>.json`; `RESULTS.json` is rebuilt from every file in `results/` after each run, so partial
//! runs (`--only`) update their own entries only.
use explorer::*;
use std::fmt::Debug;
use std::path::PathBuf;

pub const MAX_STATES: usize = 20_000_000;

pub fn limits() -> Limits {
    Limits { max_states: MAX_STATES, max_depth: usize::MAX, check_deadlock: false }
}

#[derive(Clone, Debug)]
pub enum Expect {
    Pass,
    Violation(&'static str),
}

pub struct Outcome {
    pub id: String,
    pub module: &'static str,
    pub machine: &'static str,
    pub design: &'static str,
    pub expect: String,
    pub met: bool,
    pub found: String,
    pub kind: String,
    pub states: usize,
    pub transitions: usize,
    pub depth: usize,
    pub truncated: bool,
    pub seconds: f64,
    pub trace: String,
    pub covers: &'static str,
}

/// Judge a report against its expectation. `covers` names the statements / findings the check is about.
#[allow(clippy::too_many_arguments)]
pub fn judge<S: Debug, A: Debug>(id: &str, module: &'static str, machine: &'static str, design: &'static str,
                                 expect: Expect, covers: &'static str, rep: Report<S, A>,
                                 show: impl Fn(&Counterexample<S, A>) -> String) -> Outcome {
    let found = rep.violation.as_ref().map(|c| c.property.clone()).unwrap_or_default();
    let kind = rep.violation.as_ref().map(|c| format!("{:?}", c.kind)).unwrap_or_default();
    let capped = rep.states >= MAX_STATES;
    let met = match expect {
        Expect::Pass => rep.violation.is_none() && !capped,
        Expect::Violation(p) => rep.violation.as_ref().is_some_and(|c| c.property == p),
    };
    Outcome {
        id: id.to_string(), module, machine, design,
        expect: match expect { Expect::Pass => "exhaustive pass".into(), Expect::Violation(p) => format!("violation of '{p}'") },
        met, found, kind, states: rep.states, transitions: rep.transitions, depth: rep.depth,
        truncated: capped || (rep.truncated && rep.violation.is_none() && rep.states >= MAX_STATES),
        seconds: rep.seconds, trace: rep.violation.as_ref().map(&show).unwrap_or_default(), covers,
    }
}

/// Default counterexample printer: one line per step with the action and the state.
pub fn show_debug<S: Debug, A: Debug>(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n  init: {:?}\n", c.property, c.kind, c.steps.len(), c.init);
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:?}\n      -> {:?}\n", i + 1, a, s);
    }
    out
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

fn crate_dir() -> PathBuf { PathBuf::from(env!("CARGO_MANIFEST_DIR")) }

impl Outcome {
    pub fn json(&self) -> String {
        format!(
            "{{\"id\": \"{}\", \"module\": \"{}\", \"machine\": \"{}\", \"design\": \"{}\", \"expectation\": \"{}\", \
\"result\": \"{}\", \"met\": {}, \"found\": \"{}\", \"violation_kind\": \"{}\", \"states\": {}, \"transitions\": {}, \
\"depth\": {}, \"search\": \"{}\", \"seconds\": {:.3}, \"covers\": \"{}\", \"counterexample\": \"{}\"}}",
            esc(&self.id), self.module, self.machine, self.design, esc(&self.expect),
            if self.met { "met" } else { "not-met" }, self.met, esc(&self.found), self.kind, self.states,
            self.transitions, self.depth, if self.truncated { "truncated" } else { "exhaustive" }, self.seconds,
            esc(self.covers), esc(&self.trace))
    }
}

/// Run the selected checks, print a line each, write results/<id>.json and rebuild RESULTS.json.
pub fn run_all(all: Vec<(&'static str, Box<dyn Fn() -> Outcome>)>, prune: bool) -> ! {
    let args: Vec<String> = std::env::args().collect();
    let only: Vec<String> = args.iter().position(|a| a == "--only").map(|i| args[i + 1..].to_vec()).unwrap_or_default();
    let list = args.iter().any(|a| a == "--list");
    let want = |id: &str| only.is_empty() || only.iter().any(|o| id == o || (o.ends_with('*') && id.starts_with(&o[..o.len() - 1])));
    if list {
        for (id, _) in &all { println!("{id}"); }
        std::process::exit(0);
    }
    let dir = crate_dir().join("results");
    std::fs::create_dir_all(&dir).expect("results dir");
    let mut met = 0usize;
    let mut n = 0usize;
    for (id, f) in &all {
        if !want(id) { continue; }
        let o = f();
        n += 1;
        if o.met { met += 1; }
        println!("{:<44} {:<9} expect {:<60} -> {} | {} states, {} transitions, depth {}, {}, {:.2}s{}",
                 o.id, o.design, o.expect, if o.met { "MET" } else { "NOT MET" }, o.states, o.transitions, o.depth,
                 if o.truncated { "truncated at the state cap" } else { "exhaustive within bounds" }, o.seconds,
                 if o.found.is_empty() { String::new() } else { format!(" | found '{}'", o.found) });
        if !o.trace.is_empty() { println!("{}", o.trace); }
        std::fs::write(dir.join(format!("{}.json", o.id)), o.json() + "\n").expect("write result");
    }
    // Rebuild RESULTS.json from every per-check file.
    let mut files: Vec<_> = std::fs::read_dir(&dir).expect("read results").filter_map(|e| e.ok()).map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|x| x == "json")).collect();
    files.sort();
    let known: Vec<&str> = all.iter().map(|(id, _)| *id).collect();
    let mut body = Vec::new();
    for p in files {
        let stem = p.file_stem().unwrap().to_string_lossy().to_string();
        if prune && !known.contains(&stem.as_str()) { let _ = std::fs::remove_file(&p); continue; } // a check that no longer exists
        body.push(std::fs::read_to_string(&p).expect("read").trim().to_string());
    }
    let json = format!("{{\n  \"crate\": \"experiment/playbook-completion/models/breadth-b\",\n  \"explorer_rev\": \"c03f9fa9be961610f2b274ffbb6a2c88d7d4d877\",\n  \"product_pin\": \"3eaa79cf77d3e0a879b2cced634cf2729d81499e\",\n  \"max_states\": {},\n  \"checks\": [\n    {}\n  ]\n}}\n", MAX_STATES, body.join(",\n    "));
    std::fs::write(crate_dir().join("RESULTS.json"), json).expect("write RESULTS.json");
    println!("breadth-b model checks: {met} of {n} met their expectation");
    std::process::exit(if met == n { 0 } else { 1 });
}

/// A reachability witness: "never reaches X" is expected to be violated, which proves X is reachable (sharpness).
pub fn never<S>(name: &'static str, goal: impl Fn(&S) -> bool + 'static) -> Invariant<S> {
    invariant(name, move |s| !goal(s))
}

/// Wrap a model keeping only the named invariants / action properties / always-possibly goals, or replacing them.
pub struct Only<M: Model> {
    pub m: M,
    pub keep: Vec<&'static str>,
    pub extra_inv: Vec<fn(&M::State) -> bool>,
    pub extra_names: Vec<&'static str>,
}

impl<M: Model> Only<M> {
    pub fn new(m: M, keep: &[&'static str]) -> Self { Only { m, keep: keep.to_vec(), extra_inv: vec![], extra_names: vec![] } }
    /// Add a reachability witness ("never reaches <name>").
    pub fn witness(mut self, name: &'static str, goal: fn(&M::State) -> bool) -> Self {
        self.extra_names.push(name);
        self.extra_inv.push(goal);
        self
    }
}

impl<M: Model> Model for Only<M> where M::State: 'static {
    type State = M::State;
    type Action = M::Action;
    fn init_states(&self) -> Vec<Self::State> { self.m.init_states() }
    fn actions(&self, s: &Self::State) -> Vec<Self::Action> { self.m.actions(s) }
    fn next(&self, s: &Self::State, a: &Self::Action) -> Option<Self::State> { self.m.next(s, a) }
    fn within_bounds(&self, s: &Self::State) -> bool { self.m.within_bounds(s) }
    fn invariants(&self) -> Vec<Invariant<Self::State>> {
        let mut v: Vec<Invariant<Self::State>> = self.m.invariants().into_iter().filter(|i| self.keep.contains(&i.name)).collect();
        for (n, g) in self.extra_names.iter().zip(self.extra_inv.iter()) {
            let g = *g;
            v.push(invariant(n, move |s| !g(s)));
        }
        v
    }
    fn action_properties(&self) -> Vec<ActionProperty<Self::State, Self::Action>> {
        self.m.action_properties().into_iter().filter(|p| self.keep.contains(&p.name)).collect()
    }
    fn always_possibly(&self) -> Vec<Invariant<Self::State>> {
        self.m.always_possibly().into_iter().filter(|p| self.keep.contains(&p.name)).collect()
    }
}

/// Convenience: a boxed check closure.
pub fn check(id: &'static str, f: impl Fn() -> Outcome + 'static) -> (&'static str, Box<dyn Fn() -> Outcome>) {
    (id, Box::new(f))
}
