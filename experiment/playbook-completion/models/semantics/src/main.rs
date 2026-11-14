//! Semantics lane explorer models of IVG at pin 3eaa79cf (playbook 3.3a: shared mechanisms, laws, generic
//! controls; 3.3 model check of module 00's universal axioms; F-C0605).
//!
//!     CARGO_TARGET_DIR=$RUN_DIR/target/semantics cargo run --release -- --out RESULTS.json [--only FAMILY ...]
//!
//! One file per shared mechanism (semantics/mechanisms.json): a generic machine over a per-mechanism trait, with one
//! trait instance per object (or group of objects with the same variant) that uses the mechanism. For each instance:
//! an as-built check (expected to violate exactly the law the object's hand-rolled variant departs from, naming its
//! findings, or to pass where the pin keeps the laws) and a reviewed check (the instance with the mechanism's
//! canonical variant, expected to pass exhaustively within bounds). For each mechanism: one negative control per
//! law (a generic mutant of a canonical instance the checker must catch) and sharpness witnesses. `sys00` composes
//! the mechanisms and checks the universal axioms. "Exhaustive" means every state within the declared bounds.
//! The exit status is 0 only when every check met its expectation.
#![allow(dead_code)] // each generic machine keeps its trait object for attribution; not every instance reads it
mod cap;
mod catalog;
mod derived;
mod epoch;
mod excl;
mod harness;
mod install;
mod ledger;
mod queue;
mod removal;
mod retry;
mod scope;
mod snapshot;
mod sys00;
mod unit;

use harness::{esc, Outcome};

const PIN: &str = "3eaa79cf77d3e0a879b2cced634cf2729d81499e";

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args.iter().position(|a| a == "--out").and_then(|i| args.get(i + 1)).cloned();
    let only: Vec<String> = args.iter().position(|a| a == "--only").map(|i| args[i + 1..].to_vec()).unwrap_or_default();
    let want = |f: &str| only.is_empty() || only.iter().any(|o| o == f);
    let families: Vec<(&str, fn() -> Vec<Outcome>)> = vec![
        ("ledger", ledger::checks),
        ("retry", retry::checks),
        ("excl", excl::checks),
        ("derived", derived::checks),
        ("removal", removal::checks),
        ("snapshot", snapshot::checks),
        ("queue", queue::checks),
        ("install", install::checks),
        ("scope", scope::checks),
        ("unit", unit::checks),
        ("cap", cap::checks),
        ("catalog", catalog::checks),
        ("epoch", epoch::checks),
        ("sys00", sys00::checks),
    ];
    let mut res: Vec<Outcome> = vec![];
    for (name, f) in families {
        if want(name) {
            res.extend(f());
        }
    }
    let mut json = format!("{{\n  \"pin\": \"{PIN}\",\n  \"generated_by\": \"experiment/playbook-completion/models/semantics (cargo run --release)\",\n  \"checks\": [\n");
    for (i, o) in res.iter().enumerate() {
        let m = &o.meta;
        println!("{:<58} {:<10} {:<10} expect {:<70} -> {} | {} states, {} transitions, depth {}, {}, {:.2}s{}",
                 o.id, m.design, m.kind, o.expect, if o.met { "MET" } else { "NOT MET" }, o.states, o.transitions, o.depth,
                 if o.truncated { "truncated" } else { "exhaustive" }, o.seconds,
                 if o.found.is_empty() { String::new() } else { format!(" | found '{}'", o.found) });
        if !o.trace.is_empty() && m.kind != "sharpness" {
            println!("{}", o.trace);
        }
        let objs = m.objects.iter().map(|x| format!("\"{x}\"")).collect::<Vec<_>>().join(", ");
        let (violates, also) = match &o.violates {
            None => ("null".to_string(), "null".to_string()),
            Some(v) => {
                let all = v.iter().map(|x| format!("\"{}\"", esc(x))).collect::<Vec<_>>().join(", ");
                let others = v.iter().filter(|x| x.as_str() != o.found).map(|x| format!("\"{}\"", esc(x))).collect::<Vec<_>>().join(", ");
                (format!("[{all}]"), format!("[{others}]"))
            }
        };
        if let Some(v) = &o.violates {
            if v.iter().any(|x| x.as_str() != o.found) {
                println!("    complement: the model also violates {:?}{}", v.iter().filter(|x| x.as_str() != o.found).collect::<Vec<_>>(),
                         if o.complement_truncated { " (truncated)" } else { "" });
            }
        }
        let fs = m.findings.iter().map(|x| format!("\"{x}\"")).collect::<Vec<_>>().join(", ");
        json += &format!(
            "    {{\"id\": \"{}\", \"mechanism\": \"{}\", \"family\": \"{}\", \"instance\": \"{}\", \"objects\": [{}], \"design\": \"{}\", \"kind\": \"{}\", \
\"law\": \"{}\", \"findings\": [{}], \"exception\": \"{}\", \"expectation\": \"{}\", \"result\": \"{}\", \"found\": \"{}\", \"states\": {}, \
\"transitions\": {}, \"depth\": {}, \"scope\": \"{}\", \"seconds\": {:.3}, \"violates\": {}, \"also_violates\": {}, \"complement_scope\": \"{}\", \"counterexample\": \"{}\"}}{}\n",
            esc(&o.id), m.mechanism, m.family, esc(&m.instance), objs, m.design, m.kind, esc(m.law), fs, m.exception,
            esc(&o.expect), if o.met { "met" } else { "not-met" }, esc(&o.found), o.states, o.transitions, o.depth,
            if o.truncated { "truncated" } else { "exhaustive" }, o.seconds, violates, also,
            if o.violates.is_none() { "n/a" } else if o.complement_truncated { "truncated" } else { "exhaustive" }, esc(&o.trace),
            if i + 1 < res.len() { "," } else { "" });
    }
    json += "  ]\n}\n";
    if let Some(p) = out {
        std::fs::write(&p, json).expect("write results");
    }
    let met = res.iter().filter(|o| o.met).count();
    println!("model checks: {} of {} met their expectation", met, res.len());
    std::process::exit(if met == res.len() { 0 } else { 1 });
}
