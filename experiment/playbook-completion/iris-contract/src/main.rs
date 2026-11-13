//! iris-contract CLI.
//!
//!   iris-contract permitted <cases.json> [--mutant NAME]      every permitted outcome per case (JSON)
//!   iris-contract check <cases.json> <observed.json> [--out report.json]
//!       differential: every observed outcome must be permitted by the contract (0 outside), and every mutant
//!       must be killed (some observed outcome outside the mutant's permitted set). Also reports sharpness: how
//!       many cases the contract permits exactly one outcome for, and the largest permitted set.
//!   iris-contract mutants                                     list the mutants
//!   iris-contract selftest                                    explorer self-tests of the contract machine
use iris_contract::*;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::fs;

fn load_cases(path: &str) -> Vec<Case> {
    serde_json::from_str(&fs::read_to_string(path).expect("cases")).expect("cases json")
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("permitted") => {
            let cases = load_cases(&args[2]);
            let sem = match args.iter().position(|a| a == "--mutant") {
                Some(i) => mutant(&args[i + 1]).expect("unknown mutant"),
                None => Semantics::default(),
            };
            let out: BTreeMap<String, Vec<Outcome>> =
                cases.iter().map(|c| (c.id.clone(), permitted(c, &sem).into_iter().collect())).collect();
            println!("{}", serde_json::to_string_pretty(&out).unwrap());
        }
        Some("check") => {
            let cases = load_cases(&args[2]);
            let observed: BTreeMap<String, Vec<Outcome>> =
                serde_json::from_str(&fs::read_to_string(&args[3]).expect("observed")).expect("observed json");
            let report = check(&cases, &observed);
            let text = serde_json::to_string_pretty(&report).unwrap();
            if let Some(i) = args.iter().position(|a| a == "--out") {
                fs::write(&args[i + 1], &text).unwrap();
            }
            let outside = report["contract"]["outside"].as_u64().unwrap();
            let alive: Vec<String> = report["mutants"].as_object().unwrap().iter()
                .filter(|(_, v)| !v["killed"].as_bool().unwrap()).map(|(k, _)| k.clone()).collect();
            println!("cases {} observed-runs {} outside-contract {} singleton-cases {} max-permitted {} mutants {} killed {} alive {:?}",
                report["contract"]["cases"], report["contract"]["runs"], outside, report["contract"]["singleton"],
                report["contract"]["max_permitted"], report["mutants"].as_object().unwrap().len(),
                report["mutants"].as_object().unwrap().len() - alive.len(), alive);
            std::process::exit(if outside == 0 && alive.is_empty() { 0 } else { 1 });
        }
        Some("mutants") => {
            for (n, _) in mutants() {
                println!("{n}");
            }
        }
        Some("selftest") => std::process::exit(selftest::run()),
        _ => {
            eprintln!("usage: iris-contract permitted|check|mutants|selftest ...");
            std::process::exit(2);
        }
    }
}

fn check(cases: &[Case], observed: &BTreeMap<String, Vec<Outcome>>) -> Value {
    let base = Semantics::default();
    let mut outside = vec![];
    let mut singleton = 0;
    let mut max_permitted = 0;
    let mut runs = 0;
    for c in cases {
        let perm = permitted(c, &base);
        max_permitted = max_permitted.max(perm.len());
        if perm.len() == 1 {
            singleton += 1;
        }
        for o in observed.get(&c.id).into_iter().flatten() {
            runs += 1;
            if !perm.contains(o) {
                outside.push(json!({"case": c.id, "clause": c.clause, "observed": o, "permitted": perm}));
            }
        }
    }
    let mut ms = serde_json::Map::new();
    for (name, sem) in mutants() {
        let mut killers = vec![];
        for c in cases {
            let perm = permitted(c, &sem);
            if observed.get(&c.id).into_iter().flatten().any(|o| !perm.contains(o)) {
                killers.push(c.id.clone());
            }
        }
        ms.insert(name.to_string(), json!({"killed": !killers.is_empty(), "killed_by": killers}));
    }
    json!({
        "contract": {"cases": cases.len(), "runs": runs, "outside": outside.len(), "outside_detail": outside,
                     "singleton": singleton, "max_permitted": max_permitted},
        "mutants": ms,
    })
}

mod selftest {
    //! Structural self-tests of the contract machine with the explorer: two processes running every op over a
    //! small alphabet; invariants that must hold for the validated semantics and that a broken acquire violates.
    use explorer::*;
    use iris_contract::*;

    pub struct M {
        pub sem: Semantics,
        pub broken_acquire: bool,
    }

    fn alphabet() -> Vec<Op> {
        let a = Node::new("^X", &["a"]);
        let root = Node::new("^X", &[]);
        vec![
            Op::TStart, Op::TCommit, Op::TRollbackOne, Op::TRollback, Op::SqlStart, Op::SqlCommit, Op::SqlRollback,
            Op::Set { node: a.clone(), value: "1".into() }, Op::Kill { node: root.clone() },
            Op::Lock { node: a.clone(), mode: Mode::E, wait: false }, Op::Lock { node: root.clone(), mode: Mode::S, wait: false },
            Op::Unlock { node: a.clone(), mode: Mode::E, immediate: false }, Op::Unlock { node: root.clone(), mode: Mode::S, immediate: true },
            Op::Insert { table: "T".into(), k: "1".into(), v: "x".into() }, Op::Delete { table: "T".into(), k: "1".into() },
            Op::Await,
        ]
    }

    impl Model for M {
        type State = (Engine, u8);
        type Action = (usize, Op);
        fn init_states(&self) -> Vec<Self::State> {
            vec![(Engine::new(2, self.sem.clone()), 0)]
        }
        fn actions(&self, _s: &Self::State) -> Vec<Self::Action> {
            (0..2).flat_map(|p| alphabet().into_iter().map(move |o| (p, o))).collect()
        }
        fn next(&self, s: &Self::State, a: &Self::Action) -> Option<Self::State> {
            if s.1 >= 6 {
                return None;
            }
            let (p, op) = a;
            let mut outs = s.0.step(*p, op);
            let (mut e, o) = outs.remove(0);
            if self.broken_acquire {
                // control: a lock request that ignores conflicts
                if let (Op::Lock { node, mode, .. }, Obs::Test { test: false }) = (op, &o) {
                    let h = e.procs[*p].locks.entry(node.clone()).or_default();
                    if *mode == Mode::E { h.e += 1 } else { h.s += 1 }
                }
            }
            if matches!(o, Obs::Error { .. }) {
                return None;
            }
            Some((e, s.1 + 1))
        }
        fn invariants(&self) -> Vec<Invariant<Self::State>> {
            vec![
                invariant("no two processes hold conflicting locks", |s: &(Engine, u8)| {
                    let e = &s.0;
                    for (p, pp) in e.procs.iter().enumerate() {
                        for (q, qq) in e.procs.iter().enumerate() {
                            if p == q { continue; }
                            for (n, h) in &pp.locks {
                                for (m, k) in &qq.locks {
                                    let excl = h.e + h.de > 0;
                                    let any_k = k.e + k.s + k.de + k.ds > 0;
                                    if n.related(m) && excl && any_k { return false; }
                                }
                            }
                        }
                    }
                    true
                }),
                invariant("outside a transaction nothing is deferred or undoable", |s: &(Engine, u8)| {
                    s.0.procs.iter().all(|p| p.tlevel > 0 || (p.undo.is_empty() && !p.sqlflag
                        && p.locks.values().all(|h| h.de == 0 && h.ds == 0)))
                }),
                invariant("undo stack depth equals the transaction level", |s: &(Engine, u8)| {
                    s.0.procs.iter().all(|p| p.undo.len() as u32 == p.tlevel)
                }),
            ]
        }
    }

    pub fn run() -> i32 {
        let limits = Limits { max_states: 3_000_000, max_depth: 6, check_deadlock: false };
        let good = explore(&M { sem: Semantics::default(), broken_acquire: false }, limits);
        println!("selftest contract: {}", good.summary());
        if !good.passed() { println!("{}", good.trace()); }
        let bad = explore(&M { sem: Semantics::default(), broken_acquire: true }, limits);
        println!("selftest control (acquire ignores conflicts): {}", bad.summary());
        let ok = good.passed() && !bad.passed()
            && bad.violation.as_ref().map(|v| v.property.contains("conflicting")).unwrap_or(false);
        println!("selftest {}", if ok { "PASS" } else { "FAIL" });
        if ok { 0 } else { 1 }
    }
}
