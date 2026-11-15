//! Lock-plan explorer models (gate 3.5-lockplans) for IVG modules 01, 05, 06, 08, 10, 16, 17 at pin 3eaa79cf.
//!
//!     cargo run --release -- --out lockplans/models/RESULTS.json [--only FAMILY ...]
//!
//! Each family models one lock plan over its abstracted state, cites the product lines of every modelled step, and
//! runs: as-built checks (expected to violate the named property where the live probe found a violation, or to pass
//! where the lock plan holds), a reviewed design expected to pass exhaustively within the declared bounds, a negative
//! control the explorer must catch, and sharpness checks (key states reachable). A reviewed design is a statement
//! about a model only. The exit status is 0 only when every check met its expectation.
mod conn_mutex;
mod guard_insert;
mod harness;
mod nkg_intern;
mod setup_race;
mod tmp_conc;

use harness::{esc, Outcome};

const PIN: &str = "3eaa79cf77d3e0a879b2cced634cf2729d81499e";

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args.iter().position(|a| a == "--out").and_then(|i| args.get(i + 1)).cloned();
    let only: Vec<String> = args.iter().position(|a| a == "--only").map(|i| args[i + 1..].to_vec()).unwrap_or_default();
    let want = |f: &str| only.is_empty() || only.iter().any(|o| o == f);
    let families: Vec<(&str, fn() -> Vec<Outcome>)> = vec![
        ("guard_insert", guard_insert::checks),
        ("conn_mutex", conn_mutex::checks),
        ("tmp_conc", tmp_conc::checks),
        ("nkg_intern", nkg_intern::checks),
        ("setup_race", setup_race::checks),
    ];
    let mut res: Vec<Outcome> = vec![];
    for (name, f) in families {
        if want(name) {
            res.extend(f());
        }
    }
    let mut json = format!("{{\n  \"pin\": \"{PIN}\",\n  \"generated_by\": \"experiment/playbook-completion/lockplans/models (cargo run --release)\",\n  \"explorer\": \"playbook-reference-actors c03f9fa9be961610f2b274ffbb6a2c88d7d4d877\",\n  \"checks\": [\n");
    for (i, o) in res.iter().enumerate() {
        println!("{:<56} {:<9} {:<11} expect {:<80} -> {} | {} states, {} transitions, depth {}, {}, {:.2}s{}",
                 o.id, o.design, o.kind, o.expect, if o.met { "MET" } else { "NOT MET" }, o.states, o.transitions, o.depth,
                 if o.truncated { "truncated" } else { "exhaustive" }, o.seconds,
                 if o.found.is_empty() { String::new() } else { format!(" | found '{}'", o.found) });
        if !o.trace.is_empty() && o.kind != "sharpness" {
            println!("{}", o.trace);
        }
        json += &format!(
            "    {{\"id\": \"{}\", \"module\": \"{}\", \"family\": \"{}\", \"design\": \"{}\", \"kind\": \"{}\", \"expectation\": \"{}\", \
\"result\": \"{}\", \"found\": \"{}\", \"states\": {}, \"transitions\": {}, \"depth\": {}, \"scope\": \"{}\", \"seconds\": {:.3}, \
\"counterexample\": \"{}\"}}{}\n",
            esc(&o.id), o.module, o.family, o.design, o.kind, esc(&o.expect), if o.met { "met" } else { "not-met" },
            esc(&o.found), o.states, o.transitions, o.depth, if o.truncated { "truncated" } else { "exhaustive" }, o.seconds,
            esc(&o.trace), if i + 1 < res.len() { "," } else { "" });
    }
    json += "  ]\n}\n";
    if let Some(p) = out {
        std::fs::write(&p, json).expect("write results");
    }
    let met = res.iter().filter(|o| o.met).count();
    println!("model checks: {} of {} met their expectation", met, res.len());
    std::process::exit(if met == res.len() { 0 } else { 1 });
}
