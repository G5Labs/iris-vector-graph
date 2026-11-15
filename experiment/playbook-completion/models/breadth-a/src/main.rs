//! Breadth lane A explorer models for IVG modules 01-06 at pin 3eaa79cf (playbook §3.3 explorers, §3.3a
//! mechanisms, §3.7 validation).
//!
//!     cargo run --release -- --out models/breadth-a/RESULTS.json [--only FAMILY ...]
//!
//! Each family file models one mechanism over its abstracted real state, cites the product lines of every modeled
//! step, and runs: an as-built check expected to violate the named invariant (reproducing a finding, shortest
//! trace), a reviewed design expected to pass exhaustively within the model's declared bounds (where decisions.md
//! supports or assumes the intended contract, or the product's own documentation states it), a negative control (a
//! mutant the checker must catch, so the model is not trivially permissive), sharpness checks (key states
//! reachable) and AG EF progress checks where progress matters. "Exhaustive" means every state within the declared
//! bounds (processes, writes, calls), not every size.
//!
//! The exit status is 0 only when every check met its expectation.
mod adj_degree;
mod adj_rebuild_txn;
mod adj_token;
mod gid_mode;
mod harness;
mod ins_legacy;
mod ins_setup;
mod tmp_bucket;
mod tmp_mark;
mod vec_build_publish;
mod vec_ivf;
mod vec_queue;
mod vec_route_batch;
mod wrt_bulk_atomic;
mod wrt_ledger_stmt;

use harness::{esc, Outcome};

const PIN: &str = "3eaa79cf77d3e0a879b2cced634cf2729d81499e";

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args.iter().position(|a| a == "--out").and_then(|i| args.get(i + 1)).cloned();
    let only: Vec<String> = args.iter().position(|a| a == "--only").map(|i| args[i + 1..].to_vec()).unwrap_or_default();
    let want = |f: &str| only.is_empty() || only.iter().any(|o| o == f);
    let families: Vec<(&str, fn() -> Vec<Outcome>)> = vec![
        ("adj_degree", adj_degree::checks),
        ("adj_token", adj_token::checks),
        ("adj_rebuild_txn", adj_rebuild_txn::checks),
        ("gid_mode", gid_mode::checks),
        ("wrt_bulk_atomic", wrt_bulk_atomic::checks),
        ("wrt_ledger_stmt", wrt_ledger_stmt::checks),
        ("tmp_mark", tmp_mark::checks),
        ("tmp_bucket", tmp_bucket::checks),
        ("vec_queue", vec_queue::checks),
        ("vec_ivf", vec_ivf::checks),
        ("vec_build_publish", vec_build_publish::checks),
        ("vec_route_batch", vec_route_batch::checks),
        ("ins_setup", ins_setup::checks),
        ("ins_legacy", ins_legacy::checks),
    ];
    let mut res: Vec<Outcome> = vec![];
    for (name, f) in families {
        if want(name) {
            res.extend(f());
        }
    }
    let mut json = format!("{{\n  \"pin\": \"{PIN}\",\n  \"generated_by\": \"experiment/playbook-completion/models/breadth-a (cargo run --release)\",\n  \"checks\": [\n");
    for (i, o) in res.iter().enumerate() {
        println!("{:<52} {:<9} {:<11} expect {:<78} -> {} | {} states, {} transitions, depth {}, {}, {:.2}s{}",
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
