//! Lane models-2, proof debt D-10: core model M1 (targeting; copy of models/core/src/m1.rs with a piece mode) covered in
//! the profile (2 pre-enable writes, 2 commits) by a partition of its state space by pre-enable world. See ../MODELS.md.
//!
//!     ivg-core-partition --list
//!     ivg-core-partition --pieces PRE COMMITS                     the pieces (pre-enable worlds) of a profile
//!     ivg-core-partition --coverage PRE COMMITS [--broken-key]    coverage of the piece keys (structure + independent enumeration)
//!     ivg-core-partition --union PRE COMMITS reviewed|as-built [--broken-key]
//!                                                                 union of the pieces' reachable sets == the full reachable set
//!                                                                 (own breadth-first enumeration, no explorer)
//!     ivg-core-partition --family NAME PRE COMMITS [--out F.json] one check family over every piece of a profile (explorer)
//!     ivg-core-partition --only ID ... [--out F.json]             copied original checks (fidelity of the copy)
//!
//! The exit status is 0 only when every expectation is met.
mod m1;
mod util;

use explorer::*;
use m1::*;
use std::collections::{BTreeSet, HashMap, HashSet, VecDeque};
use std::fmt::Debug;
use util::Only;

pub struct Res {
    pub states: usize,
    pub transitions: usize,
    pub depth: usize,
    pub truncated: bool,
    pub seconds: f64,
    pub violation: Option<(String, String, String)>,
}

pub fn summarize<S: Debug, A: Debug>(r: Report<S, A>, show: fn(&Counterexample<S, A>) -> String, cap: usize) -> Res {
    Res {
        states: r.states, transitions: r.transitions, depth: r.depth,
        // the explorer's own flag (state cap or depth limit) or the cap reached: either makes a run non-exhaustive
        truncated: r.truncated || r.states >= std::env::var("IVG_CAP").ok().and_then(|v| v.parse().ok()).unwrap_or(cap),
        seconds: r.seconds,
        violation: r.violation.as_ref().map(|c| (c.property.clone(), format!("{:?}", c.kind), show(c))),
    }
}

pub fn limits(cap: usize) -> Limits {
    let cap = std::env::var("IVG_CAP").ok().and_then(|v| v.parse().ok()).unwrap_or(cap);
    Limits { max_states: cap, max_depth: usize::MAX, check_deadlock: false }
}

pub enum Expect { Pass, Violation(&'static str) }

pub struct Check {
    pub id: &'static str,
    pub machine: &'static str,
    pub design: &'static str,
    pub expect: Expect,
    pub what: &'static str,
    pub run: Box<dyn Fn() -> Res>,
}

pub const CAP: usize = 60_000_000;

const P1: &str = "RED-B1.1/RED-X2: no tombstone of content live in any graph";
const P2: &str = "RED-B12/SC-001: a complete redaction leaves no dead content of its target, except records it counts as unattributed";
const P3: &str = "RED-I1/I2: only records in the target's documented reach change, each into its own tombstone";
const P5: &str = "ERS-I2/I3: live statement entries are exactly the live saved edges";
const EF: &str = "every erased target can still be completely redacted";

fn esc(s: &str) -> String {
    let mut o = String::new();
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""), '\\' => o.push_str("\\\\"), '\n' => o.push_str("\\n"),
            c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)), c => o.push(c),
        }
    }
    o
}

// ------------------------------------------------------------------------------------------------ pieces

/// The reachable pre-enable states of the full model (piece keys), by breadth-first search over the full model's own
/// transitions. Also checks the structure the partition rests on: from a pre-enable state the only enabled actions
/// are pre-enable writes (whose successors are pre-enable) and Enable (whose successor is enabled). Returns the worlds
/// sorted by key and the structural errors found.
fn pre_worlds(pre: u8, commits: u8) -> (Vec<S1>, Vec<String>, usize) {
    let full = M1::new(Design::Reviewed).prof(pre, commits);
    let init = full.init_states();
    let mut seen: HashSet<S1> = init.iter().cloned().collect();
    let mut q: VecDeque<S1> = init.into_iter().collect();
    let mut errs = vec![];
    let mut pre_transitions = 0usize;
    while let Some(s) = q.pop_front() {
        if s.enabled { errs.push(format!("enabled state in the pre-enable search: {}", brief(&s))); continue; }
        for a in full.actions(&s) {
            let Some(t) = full.next(&s, &a) else { continue };
            match a {
                A1::Enable => { if !t.enabled { errs.push("Enable left enabled = false".into()); } }
                A1::PreNode(..) | A1::PreEdge(..) => {
                    pre_transitions += 1;
                    if t.enabled { errs.push("a pre-enable write enabled the ledger".into()); }
                    if seen.insert(t.clone()) { q.push_back(t); }
                }
                other => errs.push(format!("{:?} enabled before enable() at {}", other, brief(&s))),
            }
        }
    }
    let mut v: Vec<S1> = seen.into_iter().collect();
    v.sort_by_key(key_of);
    (v, errs, pre_transitions)
}

/// An enumeration of the pre-enable worlds written independently of m1.rs's `next` (from the action description in
/// models/core/MODELS.md: a pre-enable write adds one absent node row, or one absent edge row with both endpoint node
/// rows in the edge's graph): every sequence of at most `pre` writes, as (writes, node-row bits, edge-row bits).
fn closed_form_worlds(pre: u8) -> BTreeSet<(u8, u8, u8)> {
    // edges: (graph, source, target) with graph D = 0, G = 1 and ids a|1 = 0, b|1 = 1, n = 2 (E0 G:a|1->n, E1 G:b|1->n,
    // E2 D:a|1->b|1); a node row of id i in graph g is bit 3g + i
    const EDGES: [(u8, u8, u8); 3] = [(1, 0, 2), (1, 1, 2), (0, 0, 1)];
    let mut out = BTreeSet::new();
    fn go(k: u8, maxk: u8, n: u8, e: u8, out: &mut BTreeSet<(u8, u8, u8)>) {
        out.insert((k, n, e));
        if k == maxk { return; }
        for bit in 0..6u8 { if n & (1 << bit) == 0 { go(k + 1, maxk, n | (1 << bit), e, out); } }
        for (x, (g, a, b)) in EDGES.iter().enumerate() {
            if e & (1 << x) == 0 { go(k + 1, maxk, n | (1 << (3 * g + a)) | (1 << (3 * g + b)), e | (1 << x), out); }
        }
    }
    go(0, pre, 0, 0, &mut out);
    out
}

fn world_name(w: &S1) -> String {
    let (p, n, e) = key_of(w);
    format!("w{p}n{n:02x}e{e}")
}

fn world_desc(w: &S1) -> String {
    let nodes: Vec<String> = (0..2u8).flat_map(|g| (0..3u8).filter(move |&id| w.node(g, id)).map(move |id| format!("{}:{}", GN[g as usize], ID[id as usize]))).collect();
    let edges: Vec<&str> = (0..3u8).filter(|&e| w.edge(e)).map(|e| &EN[e as usize][..2]).collect();
    format!("{} pre-enable writes; node rows {{{}}}; edge rows {{{}}}", w.pre, nodes.join(", "), edges.join(", "))
}

/// The world has a node row of n in G (genesis then records n with ghost graph G): the condition under which the
/// as-built F-1305 violation is reachable in its piece (MODELS.md, "expectations per piece", stated before the runs).
fn has_g_n(w: &S1) -> bool { w.node(1, 2) }

// ------------------------------------------------------------------------------------------------ coverage checks

fn coverage(pre: u8, commits: u8, broken: bool) -> bool {
    let (mut worlds, errs, pre_tr) = pre_worlds(pre, commits);
    if broken {
        // negative control of the coverage check: drop the last piece key, as a partition that forgot one world would
        worlds.pop();
    }
    let keys: BTreeSet<(u8, u8, u8)> = worlds.iter().map(key_of).collect();
    let cf = closed_form_worlds(pre);
    let distinct = keys.len() == worlds.len();
    let equal = keys == cf;
    println!("profile ({pre}, {commits}): {} pre-enable worlds by search ({} pre-enable write transitions), {} by the independent enumeration; keys distinct: {distinct}; equal: {equal}; structural errors: {}",
             worlds.len(), pre_tr, cf.len(), errs.len());
    for e in &errs { println!("  STRUCTURE: {e}"); }
    for k in cf.difference(&keys) { println!("  MISSING from the pieces: {k:?}"); }
    for k in keys.difference(&cf) { println!("  EXTRA piece: {k:?}"); }
    for w in &worlds { println!("  piece {:<10} {}", world_name(w), world_desc(w)); }
    let ok = errs.is_empty() && distinct && equal;
    println!("coverage{}: {}", if broken { " (control: one piece key dropped)" } else { "" }, if ok { "PASS" } else { "FAIL" });
    ok
}

/// Breadth-first reachable set of a model (no explorer).
fn reach<M: Model<State = S1, Action = A1>>(m: &M) -> HashSet<S1> {
    let mut seen: HashSet<S1> = m.init_states().into_iter().collect();
    let mut q: VecDeque<S1> = seen.iter().cloned().collect();
    while let Some(s) = q.pop_front() {
        for a in m.actions(&s) {
            if let Some(t) = m.next(&s, &a) { if !seen.contains(&t) { seen.insert(t.clone()); q.push_back(t); } }
        }
    }
    seen
}

fn union_check(pre: u8, commits: u8, design: Design, broken: bool) -> bool {
    let full = M1::new(design).prof(pre, commits);
    let f = reach(&full);
    let mut owner: HashMap<&S1, Option<usize>> = f.iter().map(|s| (s, None)).collect();
    let (mut worlds, errs, _) = pre_worlds(pre, commits);
    if broken { worlds.pop(); }
    let mut sum = 0usize;
    let mut outside = 0usize;
    let mut overlap = 0usize;
    for (i, w) in worlds.iter().enumerate() {
        let p = reach(&M1::new(design).prof(pre, commits).piece(w.clone()));
        sum += p.len();
        for s in &p {
            match owner.get_mut(s) {
                None => outside += 1,
                Some(o) => {
                    if s.enabled { if o.is_some() { overlap += 1; } *o = Some(i); }
                    else if o.is_none() { *o = Some(i); } else { overlap += 1; }
                }
            }
        }
    }
    let uncovered = owner.values().filter(|o| o.is_none()).count();
    let ok = errs.is_empty() && outside == 0 && overlap == 0 && uncovered == 0 && sum == f.len();
    println!("union ({pre}, {commits}) {:?}{}: full reachable set {} states (own breadth-first search); {} pieces; sum of piece sets {}; piece states outside the full set {}; states in two pieces {}; full states in no piece {}: {}",
             design, if broken { " (control: one piece dropped)" } else { "" }, f.len(), worlds.len(), sum, outside, overlap, uncovered,
             if ok { "PASS" } else { "FAIL" });
    ok
}

// ------------------------------------------------------------------------------------------------ families

struct Family {
    name: &'static str,
    design: Design,
    mutant: Mutant,
    keep: Vec<&'static str>,
    /// expected violated property for this world, or None for "pass, exhaustive"
    expect: fn(&S1) -> Option<&'static str>,
    what: &'static str,
}

fn families() -> Vec<Family> {
    vec![
        Family { name: "reviewed", design: Design::Reviewed, mutant: Mutant::None, keep: vec![],
            expect: |_| None, what: "HD-1303 + HD-1304 working assumptions: every property, AG EF and PARTITION" },
        Family { name: "as-built-isolation-stmt", design: Design::AsBuilt, mutant: Mutant::None, keep: vec![P3, P5, EF, PART],
            expect: |_| None, what: "at the pin, sequentially: RED-I1/I2, ERS-I2/I3, AG EF and PARTITION hold" },
        Family { name: "as-built-F1304", design: Design::AsBuilt, mutant: Mutant::None, keep: vec![P1, PART],
            expect: |_| Some(P1), what: "F-1304: the unprefixed default-graph target counts default-graph rows only but matches every node record" },
        Family { name: "as-built-F1305", design: Design::AsBuilt, mutant: Mutant::None, keep: vec![P2, PART],
            expect: |w| if has_g_n(w) { Some(P2) } else { None },
            what: "F-1305: violation in exactly the pieces whose world has a node row of n in G; elsewhere RED-B12/SC-001 holds" },
        Family { name: "control-liveness-collapsed", design: Design::Reviewed, mutant: Mutant::LivenessCollapsed, keep: vec![P1, PART],
            expect: |_| Some(P1), what: "negative control: the reviewed design with one liveness predicate (a default-graph prefix target counts default-graph rows only)" },
        Family { name: "control-dropstatements-all-graphs", design: Design::Reviewed, mutant: Mutant::DropStatementsAllGraphs, keep: vec![P5, PART],
            expect: |_| Some(P5), what: "negative control: the reviewed design with DropStatements ignoring the graph" },
    ]
}

fn run_family(name: &str, pre: u8, commits: u8, out: Option<String>) -> bool {
    let fam = families().into_iter().find(|f| f.name == name).unwrap_or_else(|| panic!("unknown family {name}"));
    let (worlds, errs, _) = pre_worlds(pre, commits);
    for e in &errs { println!("STRUCTURE: {e}"); }
    let mut json = format!("{{\n  \"crate\": \"experiment/playbook-completion/models/core-partition\",\n  \"explorer_rev\": \"c03f9fa9be961610f2b274ffbb6a2c88d7d4d877\",\n  \"product_pin\": \"3eaa79cf77d3e0a879b2cced634cf2729d81499e\",\n  \"family\": \"{}\",\n  \"what\": \"{}\",\n  \"profile\": [{pre}, {commits}],\n  \"max_states\": {},\n  \"pieces\": [\n",
                           fam.name, esc(fam.what), std::env::var("IVG_CAP").ok().and_then(|v| v.parse().ok()).unwrap_or(CAP));
    let (mut met_all, mut tot_states, mut tot_tr, mut tot_s, mut nviol, mut npass, mut ntrunc) = (errs.is_empty(), 0usize, 0usize, 0f64, 0, 0, 0);
    let mut max_states = 0usize;
    for (i, w) in worlds.iter().enumerate() {
        let mut m = M1::new(fam.design).prof(pre, commits).piece(w.clone());
        m.mutant = fam.mutant;
        let exp = (fam.expect)(w);
        let r = run(Only::keep(m, &fam.keep));
        let met = match exp {
            None => r.violation.is_none() && !r.truncated,
            Some(p) => r.violation.as_ref().map_or(false, |(found, _, _)| found == p),
        };
        met_all &= met;
        tot_states += r.states; tot_tr += r.transitions; tot_s += r.seconds; max_states = max_states.max(r.states);
        if r.violation.is_some() { nviol += 1 } else { npass += 1 }
        if r.truncated { ntrunc += 1 }
        let result = match (&r.violation, met) {
            (None, true) => "pass".to_string(),
            (Some(_), true) => "expected-violation".to_string(),
            (None, false) => if r.truncated { "truncated".into() } else { "no-violation (expected one)".into() },
            (Some((p, _, _)), false) => format!("unexpected violation of '{p}'"),
        };
        println!("{}-{:<10} {} | {} states, {} transitions, depth {}, {}, {:.1}s | expect {} | {result} | {}",
                 fam.name, world_name(w), if met { "MET" } else { "NOT MET" }, r.states, r.transitions, r.depth,
                 if r.truncated { "TRUNCATED" } else { "exhaustive within bounds" }, r.seconds,
                 exp.map_or("pass".to_string(), |p| format!("violation of '{p}'")), world_desc(w));
        if let Some((_, _, t)) = &r.violation { println!("{t}"); }
        if i > 0 { json += ",\n"; }
        json += &format!("    {{\"piece\": \"{}\", \"world\": \"{}\", \"expectation\": \"{}\", \"met\": {met}, \"result\": \"{}\", \"states\": {}, \"transitions\": {}, \"depth\": {}, \"exhaustive\": {}, \"seconds\": {:.2}, \"violated\": \"{}\", \"trace\": \"{}\"}}",
            world_name(w), esc(&world_desc(w)), esc(&exp.map_or("pass".to_string(), |p| format!("violation of '{p}'"))), esc(&result),
            r.states, r.transitions, r.depth, if r.truncated { "\"truncated\"" } else { "\"exhaustive-within-bounds\"" }, r.seconds,
            esc(r.violation.as_ref().map_or("", |v| v.0.as_str())), esc(r.violation.as_ref().map_or("", |v| v.2.as_str())));
    }
    println!("family {} profile ({pre}, {commits}): {} pieces, {} met, {} with a violation, {} without, {} truncated; states {} (largest piece {}), transitions {}, {:.1}s: {}",
             fam.name, worlds.len(), if met_all { worlds.len().to_string() } else { "NOT ALL".into() }, nviol, npass, ntrunc, tot_states, max_states, tot_tr, tot_s,
             if met_all { "EVERY EXPECTATION MET" } else { "SOME EXPECTATION NOT MET" });
    json += &format!("\n  ],\n  \"pieces_total\": {},\n  \"states_total\": {tot_states},\n  \"transitions_total\": {tot_tr},\n  \"largest_piece_states\": {max_states},\n  \"with_violation\": {nviol},\n  \"without_violation\": {npass},\n  \"truncated\": {ntrunc},\n  \"seconds_total\": {tot_s:.2},\n  \"met\": {met_all}\n}}\n", worlds.len());
    if let Some(p) = out { std::fs::write(p, json).expect("write results"); }
    met_all
}

// ------------------------------------------------------------------------------------------------ copied original checks

/// The original profile checks run on the copy (no piece mode): their state counts must equal the registered
/// core-m1-* runs, which shows the copy is the same machine.
fn fidelity_checks() -> Vec<Check> {
    let mut v = vec![];
    for (pf, pre, com) in PROFILES {
        v.push(Check { id: Box::leak(format!("fidelity-m1-reviewed-{pf}").into_boxed_str()), machine: "M1", design: "reviewed", expect: Expect::Pass,
            what: "copy of m1-reviewed-<profile>", run: Box::new(move || run(Only::keep(M1::new(Design::Reviewed).prof(pre, com), &[]))) });
        v.push(Check { id: Box::leak(format!("fidelity-m1-as-built-isolation-stmt-{pf}").into_boxed_str()), machine: "M1", design: "as-built", expect: Expect::Pass,
            what: "copy of m1-as-built-isolation-stmt-<profile>", run: Box::new(move || run(Only::keep(M1::new(Design::AsBuilt).prof(pre, com), &[P3, P5, EF]))) });
    }
    v.push(Check { id: "full-m1-reviewed-22", machine: "M1", design: "reviewed", expect: Expect::Pass,
        what: "the unpartitioned (2, 2) profile, reviewed, every property and AG EF (needs the heavy lock and a large cap)",
        run: Box::new(move || run(Only::keep(M1::new(Design::Reviewed).prof(2, 2), &[]))) });
    v.push(Check { id: "full-m1-as-built-isolation-stmt-22", machine: "M1", design: "as-built", expect: Expect::Pass,
        what: "the unpartitioned (2, 2) profile, as built: RED-I1/I2, ERS-I2/I3 and AG EF (needs the heavy lock and a large cap)",
        run: Box::new(move || run(Only::keep(M1::new(Design::AsBuilt).prof(2, 2), &[P3, P5, EF]))) });
    v
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let arg = |i: usize| args.get(i).cloned().unwrap_or_default();
    let num = |i: usize| arg(i).parse::<u8>().expect("number");
    let out = args.iter().position(|a| a == "--out").and_then(|i| args.get(i + 1)).cloned();
    let broken = args.iter().any(|a| a == "--broken-key");
    let ok = match arg(1).as_str() {
        "--list" => {
            for f in families() { println!("family {:<36} {:?} {:?} keep {:?}: {}", f.name, f.design, f.mutant, f.keep, f.what); }
            for c in fidelity_checks() { println!("{:<48} {}", c.id, c.what); }
            true
        }
        "--pieces" => { let (w, e, _) = pre_worlds(num(2), num(3)); for x in &w { println!("{:<10} {}", world_name(x), world_desc(x)); } e.is_empty() }
        "--coverage" => coverage(num(2), num(3), broken),
        "--union" => union_check(num(2), num(3), if arg(4) == "as-built" { Design::AsBuilt } else { Design::Reviewed }, broken),
        "--family" => run_family(&arg(2), num(3), num(4), out),
        "--only" => {
            let only: Vec<String> = args[2..].iter().take_while(|a| !a.starts_with("--")).cloned().collect();
            let mut met_all = true;
            for c in fidelity_checks().into_iter().filter(|c| only.iter().any(|o| o == c.id)) {
                let r = (c.run)();
                let met = match c.expect { Expect::Pass => r.violation.is_none() && !r.truncated,
                    Expect::Violation(p) => r.violation.as_ref().map_or(false, |(f, _, _)| f == p) };
                met_all &= met;
                println!("{:<48} {:<10} {} | {} states, {} transitions, depth {}, {}, {:.1}s", c.id, c.design, if met { "MET" } else { "NOT MET" },
                         r.states, r.transitions, r.depth, if r.truncated { "TRUNCATED" } else { "exhaustive within bounds" }, r.seconds);
                if let Some((_, _, t)) = &r.violation { println!("{t}"); }
            }
            met_all
        }
        _ => { eprintln!("usage: see the header of src/main.rs"); false }
    };
    std::process::exit(if ok { 0 } else { 1 });
}
