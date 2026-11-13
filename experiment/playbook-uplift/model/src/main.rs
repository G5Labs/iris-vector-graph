//! Model checking of the erasure -> redaction -> replay slice (playbook §3.3 explorers, §3.7).
//!
//!     cargo run --release -- --out "$RUN_DIR/mc/summary.json" [--only ID ...]
//!
//! Five machines, each in the design at the pin (`as-built`) and in a reviewed design that changes one thing:
//! 1. `redaction`  the L2 redaction core (proofs/src/l2.rs) with two processes, four changesets, erasure and a
//!    ledger-bypassing write;
//! 2. `refinement` the same machine audited against an executable L1 (proofs/src/l1.rs) through the abstraction
//!    function of the Verus proof;
//! 3. `erasure`    EraseGraph interleaved with ledger commits into the erased graph;
//! 4. `readers`    a lock-free record reader (verify, reconstruct, diff, export) racing a redaction;
//! 5. `retry`      a replayed retry that re-applies post-commit properties after an erasure.
//!
//! Every check states its expected outcome. An as-built check expects a named violation (the finding, with the
//! shortest trace); a reviewed check expects an exhaustive pass within its bounds. The exit status is 0 only when
//! every check met its expectation. Results are bounded: "exhaustive" means every state within the declared
//! bounds (number of revisions, starts, erasures, retries), not every size.
mod erasure;
mod readers;
mod redaction;
mod refine;
mod retry;

use explorer::*;
use std::fmt::Debug;

struct Outcome {
    id: &'static str,
    machine: &'static str,
    design: &'static str,
    expect: String,
    met: bool,
    found: String,
    states: usize,
    transitions: usize,
    depth: usize,
    truncated: bool,
    seconds: f64,
    trace: String,
}

fn limits() -> Limits { Limits { max_states: 40_000_000, max_depth: usize::MAX, check_deadlock: false } }

fn judge<S: Debug, A: Debug>(id: &'static str, machine: &'static str, design: &'static str, expect: Option<&str>,
                             rep: Report<S, A>, show: impl Fn(&Counterexample<S, A>) -> String) -> Outcome {
    let found = rep.violation.as_ref().map(|c| c.property.clone()).unwrap_or_default();
    // `refinement::audit` flags a state cut by the model's declared bounds as truncation; `explore` does not. Either
    // way the result is exhaustive within the bounds as long as the state cap was not reached.
    let capped = rep.states >= limits().max_states;
    let met = match expect {
        None => rep.violation.is_none() && !capped,
        Some(p) => rep.violation.as_ref().map_or(false, |c| p.is_empty() || c.property == p),
    };
    Outcome {
        id, machine, design,
        expect: expect.map_or("exhaustive pass".to_string(), |p| if p.is_empty() { "a violation".into() } else { format!("violation of '{p}'") }),
        met, found, states: rep.states, transitions: rep.transitions, depth: rep.depth, truncated: capped,
        seconds: rep.seconds, trace: rep.violation.as_ref().map(|c| show(c)).unwrap_or_default(),
    }
}

fn esc(s: &str) -> String {
    s.chars().flat_map(|c| match c {
        '"' => "\\\"".chars().collect::<Vec<_>>(), '\\' => "\\\\".chars().collect(), '\n' => "\\n".chars().collect(),
        c if (c as u32) < 0x20 => format!("\\u{:04x}", c as u32).chars().collect(), c => vec![c],
    }).collect()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args.iter().position(|a| a == "--out").and_then(|i| args.get(i + 1)).cloned();
    let only: Vec<String> = args.iter().position(|a| a == "--only").map(|i| args[i + 1..].to_vec()).unwrap_or_default();
    let want = |id: &str| only.is_empty() || only.iter().any(|o| o == id);
    use redaction::Design as RD;
    let mut res: Vec<Outcome> = vec![];
    let live = "no tombstone of live content";
    let audit = "each audit counts exactly its own target's tombstones";

    if want("redaction-as-built-live") {
        let m = redaction::Only { m: redaction::M { design: RD::AsBuilt }, keep: live };
        res.push(judge("redaction-as-built-live", "redaction", "as-built", Some(live), explore(&m, limits()), redaction::show));
    }
    if want("redaction-as-built-audit") {
        let m = redaction::Only { m: redaction::M { design: RD::AsBuilt }, keep: audit };
        res.push(judge("redaction-as-built-audit", "redaction", "as-built", Some(audit), explore(&m, limits()), redaction::show));
    }
    if want("redaction-reviewed") {
        let m = redaction::M { design: RD::Reviewed };
        res.push(judge("redaction-reviewed", "redaction", "reviewed", None, explore(&m, limits()), redaction::show));
    }
    if want("refinement-as-built") {
        let r = explorer::refinement::audit(refine::binding(RD::AsBuilt), limits()).expect("audit");
        res.push(judge("refinement-as-built", "refinement", "as-built", Some(""), r, redaction::show));
    }
    if want("refinement-reviewed") {
        let r = explorer::refinement::audit(refine::binding(RD::Reviewed), limits()).expect("audit");
        res.push(judge("refinement-reviewed", "refinement", "reviewed", None, r, redaction::show));
    }
    let stm = "statements of G equal the edges of G whenever no transaction is open";
    if want("erasure-as-built") {
        res.push(judge("erasure-as-built", "erasure", "as-built", Some(stm),
            explore(&erasure::M3 { design: erasure::Design::AsBuilt }, limits()), erasure::show));
    }
    if want("erasure-reviewed") {
        res.push(judge("erasure-reviewed", "erasure", "reviewed", None,
            explore(&erasure::M3 { design: erasure::Design::Reviewed }, limits()), erasure::show));
    }
    let half = "an accepted view never shows a redaction half done";
    if want("readers-as-built") {
        res.push(judge("readers-as-built", "readers", "as-built", Some(half),
            explore(&readers::M4 { design: readers::Design::AsBuilt }, limits()), readers::show));
    }
    if want("readers-reviewed") {
        res.push(judge("readers-reviewed", "readers", "reviewed", None,
            explore(&readers::M4 { design: readers::Design::Reviewed }, limits()), readers::show));
    }
    let rlive = "after erasure only a recorded commit makes the tenant's content live again";
    if want("retry-as-built") {
        res.push(judge("retry-as-built", "retry", "as-built", Some(rlive),
            explore(&retry::M5 { design: retry::Design::AsBuilt }, limits()), retry::show));
    }
    if want("retry-reviewed") {
        res.push(judge("retry-reviewed", "retry", "reviewed", None,
            explore(&retry::M5 { design: retry::Design::Reviewed }, limits()), retry::show));
    }

    let mut json = String::from("{\n  \"checks\": [\n");
    for (i, o) in res.iter().enumerate() {
        println!("{:<26} {:<9} expect {:<70} -> {} | {} states, {} transitions, depth {}, {}, {:.2}s{}",
                 o.id, o.design, o.expect, if o.met { "MET" } else { "NOT MET" }, o.states, o.transitions, o.depth,
                 if o.truncated { "truncated at the state cap" } else { "exhaustive within bounds" }, o.seconds,
                 if o.found.is_empty() { String::new() } else { format!(" | found '{}'", o.found) });
        if !o.trace.is_empty() { println!("{}", o.trace); }
        json += &format!("    {{\"id\": \"{}\", \"machine\": \"{}\", \"design\": \"{}\", \"expect\": \"{}\", \"met\": {}, \
\"found\": \"{}\", \"states\": {}, \"transitions\": {}, \"depth\": {}, \"truncated\": {}, \"seconds\": {:.2}, \"trace\": \"{}\"}}{}\n",
            o.id, o.machine, o.design, esc(&o.expect), o.met, esc(&o.found), o.states, o.transitions, o.depth, o.truncated,
            o.seconds, esc(&o.trace), if i + 1 < res.len() { "," } else { "" });
    }
    json += "  ]\n}\n";
    if let Some(p) = out { std::fs::write(&p, json).expect("write summary"); }
    let all = res.iter().all(|o| o.met);
    println!("model checks: {} of {} met their expectation", res.iter().filter(|o| o.met).count(), res.len());
    std::process::exit(if all { 0 } else { 1 });
}
