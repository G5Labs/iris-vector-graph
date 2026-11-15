//! Explorer models of breadth lane C (modules 15-18), playbook §3.3 explorers and §3.7 validation kinds.
//!
//!     CARGO_TARGET_DIR=$RUN_DIR/target/breadth-c cargo run --release -- --out RESULTS.json [--only ID ...]
//!
//! Five machines, each as built at 3eaa79cf and in a reviewed design taken from experiment/playbook-completion/
//! decisions.md, with negative controls (mutants of the reviewed design the checker must reject) and witnesses
//! (sharpness: a goal the reviewed design must still reach, written as "never reached" so the checker must find it):
//!   M1 retry    client and server retries over an ambiguous acknowledgement      HD-1603, HD-1702   (16, 17)
//!   M2 unit     Bolt explicit transaction / HTTP tx-commit atomicity and retry   F-1601, F-1610     (16)
//!   M3 fhir     FHIR sync vs erase, durable removal, unreadable resource         HD-1502..1504      (15)
//!   M4 snapcut  save_snapshot against a concurrent writer                         HD-1802            (18)
//!   M5 restore  replacing restore against the live ledger and redaction marks    HD-1801, F-1801    (18)
//!   M6 register re-registering a FHIR graph: a refusal after partial writes        F-1511             (15)
//! An as-built check keeps one property, so its counterexample is attributed to one finding. Every check states
//! its expectation; the exit status is 0 only when every check met it. "exhaustive" means every reachable state
//! within the model's declared bounds was explored (no state cap hit); it is bounded evidence, not a proof.
mod fhir;
mod register;
mod restore;
mod retry;
mod snapcut;
mod unit;

use explorer::*;
use std::fmt::Debug;

struct Only<M: Model> { m: M, keep: &'static [&'static str] }

impl<M: Model> Model for Only<M> {
    type State = M::State;
    type Action = M::Action;
    fn init_states(&self) -> Vec<M::State> { self.m.init_states() }
    fn actions(&self, s: &M::State) -> Vec<M::Action> { self.m.actions(s) }
    fn next(&self, s: &M::State, a: &M::Action) -> Option<M::State> { self.m.next(s, a) }
    fn within_bounds(&self, s: &M::State) -> bool { self.m.within_bounds(s) }
    fn invariants(&self) -> Vec<Invariant<M::State>> {
        self.m.invariants().into_iter().filter(|p| self.keep.contains(&p.name)).collect()
    }
    fn action_properties(&self) -> Vec<ActionProperty<M::State, M::Action>> {
        self.m.action_properties().into_iter().filter(|p| self.keep.contains(&p.name)).collect()
    }
    fn always_possibly(&self) -> Vec<Invariant<M::State>> {
        self.m.always_possibly().into_iter().filter(|p| self.keep.contains(&p.name)).collect()
    }
}

struct Outcome {
    id: String,
    module: &'static str,
    machine: &'static str,
    design: &'static str,
    kind: &'static str,
    refs: &'static str,
    expect: String,
    met: bool,
    result: &'static str,
    found: String,
    states: usize,
    transitions: usize,
    depth: usize,
    truncated: bool,
    seconds: f64,
    trace: String,
}

const MAX_STATES: usize = 20_000_000;

fn limits() -> Limits { Limits { max_states: MAX_STATES, max_depth: usize::MAX, check_deadlock: false } }

#[allow(clippy::too_many_arguments)]
fn judge<S: Debug, A: Debug>(id: &str, module: &'static str, machine: &'static str, design: &'static str,
                             kind: &'static str, refs: &'static str, expect: Option<&str>, rep: Report<S, A>,
                             show: impl Fn(&Counterexample<S, A>) -> String) -> Outcome {
    let found = rep.violation.as_ref().map(|c| c.property.clone()).unwrap_or_default();
    let capped = rep.states >= MAX_STATES || rep.truncated;
    let met = match expect {
        None => rep.violation.is_none() && !capped,
        Some(p) => rep.violation.as_ref().is_some_and(|c| c.property == p),
    };
    let result = match (expect, met) {
        (None, true) => "pass",
        (Some(_), true) => "expected-violation",
        (_, false) => "fail",
    };
    Outcome {
        id: id.to_string(), module, machine, design, kind, refs,
        expect: expect.map_or("exhaustive pass".to_string(), |p| format!("violation of '{p}'")),
        met, result, found, states: rep.states, transitions: rep.transitions, depth: rep.depth, truncated: capped,
        seconds: rep.seconds, trace: rep.violation.as_ref().map(&show).unwrap_or_default(),
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
    let mut res: Vec<Outcome> = vec![];

    // ------------------------------------------------------------------ M1 retry (16, 17)
    {
        use retry::*;
        const ONCE: &str = "at most once";
        const HONEST: &str = "a definite failure means nothing was applied";
        let refs = "HD-1603 HD-1702; sdk.py:209-228; cypher_api.py:250-268";
        if want("cmc-retry-as-built-once") {
            let m = Only { m: M::new(Design::AsBuilt), keep: &[ONCE] };
            res.push(judge("cmc-retry-as-built-once", "16,17", "retry", "as-built", "mc", refs, Some(ONCE),
                           explore(&m, limits()), show));
        }
        if want("cmc-retry-as-built-honest") {
            let m = Only { m: M::new(Design::AsBuilt), keep: &[HONEST] };
            res.push(judge("cmc-retry-as-built-honest", "16,17", "retry", "as-built", "mc", refs, Some(HONEST),
                           explore(&m, limits()), show));
        }
        if want("cmc-retry-reviewed") {
            res.push(judge("cmc-retry-reviewed", "16,17", "retry", "reviewed", "mc", refs, None,
                           explore(&M::new(Design::Reviewed), limits()), show));
        }
        if want("cmc-retry-ctl-client") {
            let m = Only { m: M::new(Design::ControlClientRetriesWriteOnTimeout), keep: &[ONCE] };
            res.push(judge("cmc-retry-ctl-client", "16,17", "retry", "control: reviewed, client retries a write on timeout",
                           "control", refs, Some(ONCE), explore(&m, limits()), show));
        }
        if want("cmc-retry-ctl-server") {
            let m = Only { m: M::new(Design::ControlServerRetriesWriteAfterSend), keep: &[ONCE] };
            res.push(judge("cmc-retry-ctl-server", "16,17", "retry", "control: reviewed, server re-runs a sent write",
                           "control", refs, Some(ONCE), explore(&m, limits()), show));
        }
        for (id, goal) in [("cmc-retry-wit-read", "read retried after a timeout succeeds"),
                           ("cmc-retry-wit-write", "write applied once and reported")] {
            if want(id) {
                let w = Witness { m: M::new(Design::Reviewed), goal };
                res.push(judge(id, "16,17", "retry", "reviewed", "witness", refs, Some(goal), explore(&w, limits()), show));
            }
        }
    }

    // ------------------------------------------------------------------ M2 unit (16)
    {
        use unit::*;
        const ATOM: &str = "unit atomicity";
        const ONCE: &str = "at most once";
        let rb = "F-1601; bolt_server.py:500-510, 579-581";
        let rh = "F-1610; cypher_api.py:379-410";
        if want("cmc-unit-bolt-as-built-atomic") {
            let m = Only { m: M { design: Design::AsBuilt, entry: Entry::Bolt }, keep: &[ATOM] };
            res.push(judge("cmc-unit-bolt-as-built-atomic", "16", "unit", "as-built (Bolt)", "mc", rb, Some(ATOM),
                           explore(&m, limits()), show));
        }
        if want("cmc-unit-bolt-as-built-once") {
            let m = Only { m: M { design: Design::AsBuilt, entry: Entry::Bolt }, keep: &[ONCE] };
            res.push(judge("cmc-unit-bolt-as-built-once", "16", "unit", "as-built (Bolt, driver retry)", "mc", rb,
                           Some(ONCE), explore(&m, limits()), show));
        }
        if want("cmc-unit-http-as-built-atomic") {
            let m = Only { m: M { design: Design::AsBuilt, entry: Entry::HttpTxCommit }, keep: &[ATOM] };
            res.push(judge("cmc-unit-http-as-built-atomic", "16", "unit", "as-built (HTTP tx/commit)", "mc", rh,
                           Some(ATOM), explore(&m, limits()), show));
        }
        if want("cmc-unit-bolt-reviewed") {
            res.push(judge("cmc-unit-bolt-reviewed", "16", "unit", "reviewed (Bolt)", "mc", rb, None,
                           explore(&M { design: Design::Reviewed, entry: Entry::Bolt }, limits()), show));
        }
        if want("cmc-unit-http-reviewed") {
            res.push(judge("cmc-unit-http-reviewed", "16", "unit", "reviewed (HTTP tx/commit)", "mc", rh, None,
                           explore(&M { design: Design::Reviewed, entry: Entry::HttpTxCommit }, limits()), show));
        }
        if want("cmc-unit-ctl-rollback") {
            let m = Only { m: M { design: Design::ControlRollbackKeepsFirstWrite, entry: Entry::Bolt }, keep: &[ATOM] };
            res.push(judge("cmc-unit-ctl-rollback", "16", "unit", "control: reviewed, ROLLBACK publishes the first write",
                           "control", rb, Some(ATOM), explore(&m, limits()), show));
        }
        if want("cmc-unit-wit-bolt") {
            let g = "a committed unit with both writes visible";
            let w = Witness { m: M { design: Design::Reviewed, entry: Entry::Bolt } };
            res.push(judge("cmc-unit-wit-bolt", "16", "unit", "reviewed (Bolt)", "witness", rb, Some(g),
                           explore(&w, limits()), show));
        }
    }

    // ------------------------------------------------------------------ M3 fhir (15)
    {
        use fhir::*;
        const WM: &str = "watermark soundness";
        const DUR: &str = "durable removal holds";
        const PROG: &str = "every key is projected and the watermark reaches the end";
        let refs = "HD-1502 HD-1503 HD-1504; FHIRGraph.cls:543-626, 1923-1979, 2380-2395; Eraser.cls:1151-1180";
        let m = |design, erase, poison, repair| M { design, erase, poison, repair };
        if want("cmc-fhir-erase-as-built") {
            let x = Only { m: m(Design::AsBuilt, true, 0, false), keep: &[WM] };
            res.push(judge("cmc-fhir-erase-as-built", "15", "fhir", "as-built", "mc", refs, Some(WM),
                           explore(&x, limits()), show));
        }
        if want("cmc-fhir-durable-as-built") {
            let x = Only { m: m(Design::AsBuilt, true, 0, false), keep: &[DUR] };
            res.push(judge("cmc-fhir-durable-as-built", "15", "fhir", "as-built (unschedule, then erase)", "mc", refs,
                           Some(DUR), explore(&x, limits()), show));
        }
        if want("cmc-fhir-reviewed") {
            res.push(judge("cmc-fhir-reviewed", "15", "fhir", "reviewed (erase serialized with sync)", "mc", refs, None,
                           explore(&m(Design::Reviewed, true, 0, false), limits()), show));
        }
        if want("cmc-fhir-ctl-erase-lock") {
            let x = Only { m: m(Design::ControlEraseIgnoresLock, true, 0, false), keep: &[WM] };
            res.push(judge("cmc-fhir-ctl-erase-lock", "15", "fhir", "control: reviewed, erase skips the sync lock",
                           "control", refs, Some(WM), explore(&x, limits()), show));
        }
        if want("cmc-fhir-poison-as-built-norepair") {
            let x = Only { m: m(Design::AsBuilt, false, 0b010, false), keep: &[PROG] };
            res.push(judge("cmc-fhir-poison-as-built-norepair", "15", "fhir", "as-built (unreadable key 2, no repair)",
                           "mc", refs, Some(PROG), explore(&x, limits()), show));
        }
        if want("cmc-fhir-poison-as-built-repair") {
            let x = Only { m: m(Design::AsBuilt, false, 0b010, true), keep: &[WM, PROG] };
            res.push(judge("cmc-fhir-poison-as-built-repair", "15", "fhir",
                           "as-built (unreadable key 2, operator repair premise)", "mc", refs, None,
                           explore(&x, limits()), show));
        }
        if want("cmc-fhir-poison-quarantine") {
            res.push(judge("cmc-fhir-poison-quarantine", "15", "fhir",
                           "reviewed alternative (quarantine, erase serialized), no repair", "mc", refs, None,
                           explore(&m(Design::ReviewedQuarantine, true, 0b010, false), limits()), show));
        }
        if want("cmc-fhir-wit-refill") {
            let g = "an erased graph is fully projected again by later syncs";
            let w = Witness { m: m(Design::Reviewed, true, 0, false) };
            res.push(judge("cmc-fhir-wit-refill", "15", "fhir", "reviewed", "witness", refs, Some(g),
                           explore(&w, limits()), show));
        }
    }

    // ------------------------------------------------------------------ M4 snapcut (18)
    {
        use snapcut::*;
        const CUT: &str = "the archive is a committed state";
        const DANG: &str = "the archive has no dangling edge";
        let refs = "HD-1802 SNP-Q1.17; snapshot.py:864-1034; SYS-P2";
        if want("cmc-snap-as-built-committed") {
            let x = Only { m: M { design: Design::AsBuilt }, keep: &[CUT] };
            res.push(judge("cmc-snap-as-built-committed", "18", "snapcut", "as-built", "mc", refs, Some(CUT),
                           explore(&x, limits()), show));
        }
        if want("cmc-snap-as-built-dangling") {
            let x = Only { m: M { design: Design::AsBuilt }, keep: &[DANG] };
            res.push(judge("cmc-snap-as-built-dangling", "18", "snapcut", "as-built", "mc", refs, Some(DANG),
                           explore(&x, limits()), show));
        }
        if want("cmc-snap-reviewed") {
            res.push(judge("cmc-snap-reviewed", "18", "snapcut", "reviewed (export gate)", "mc", refs, None,
                           explore(&M { design: Design::Reviewed }, limits()), show));
        }
        if want("cmc-snap-ctl-gate") {
            let x = Only { m: M { design: Design::ControlWriterSkipsGate }, keep: &[CUT] };
            res.push(judge("cmc-snap-ctl-gate", "18", "snapcut", "control: reviewed, a writer skips the gate", "control",
                           refs, Some(CUT), explore(&x, limits()), show));
        }
        if want("cmc-snap-wit") {
            let g = "a save after a committed create archives it whole";
            res.push(judge("cmc-snap-wit", "18", "snapcut", "reviewed", "witness", refs, Some(g),
                           explore(&Witness { m: M { design: Design::Reviewed } }, limits()), show));
        }
    }

    // ------------------------------------------------------------------ M5 restore (18)
    {
        use restore::*;
        const HIST: &str = "one history";
        const RED: &str = "a redacted record holds no content";
        const GROW: &str = "the ledger only grows";
        const LIVE: &str = "a new commit can succeed";
        let refs = "HD-1801 F-1801 SNP-I3.6 SNP-B3.7; snapshot.py:1139-1152, 1554-1588, 1654-1692; Eraser.cls:806-812; Ledger.cls:500-567; LedgerRevision.cls:44";
        for (id, p) in [("cmc-restore-as-built-history", HIST), ("cmc-restore-as-built-redaction", RED),
                        ("cmc-restore-as-built-grows", GROW), ("cmc-restore-as-built-commit", LIVE)] {
            if want(id) {
                let keep: &'static [&'static str] = match p { HIST => &[HIST], RED => &[RED], GROW => &[GROW], _ => &[LIVE] };
                let x = Only { m: M { design: Design::AsBuilt }, keep };
                res.push(judge(id, "18", "restore", "as-built", "mc", refs, Some(p), explore(&x, limits()), show));
            }
        }
        if want("cmc-restore-reviewed") {
            res.push(judge("cmc-restore-reviewed", "18", "restore", "reviewed (refuse divergent, keep marks)", "mc", refs,
                           None, explore(&M { design: Design::Reviewed }, limits()), show));
        }
        if want("cmc-restore-ctl-marks") {
            let x = Only { m: M { design: Design::ControlReviewedForgetsMarks }, keep: &[RED] };
            res.push(judge("cmc-restore-ctl-marks", "18", "restore", "control: reviewed, live redaction marks dropped",
                           "control", refs, Some(RED), explore(&x, limits()), show));
        }
        if want("cmc-restore-wit") {
            let g = "a restore of a newer archive succeeds and the ledger commits on";
            res.push(judge("cmc-restore-wit", "18", "restore", "reviewed", "witness", refs, Some(g),
                           explore(&Witness { m: M { design: Design::Reviewed } }, limits()), show));
        }
    }

    // ------------------------------------------------------------------ M6 register (15)
    {
        use register::*;
        const NOCHG: &str = "a refused register changes nothing";
        const LINKS: &str = "registered links match the graph";
        let refs = "F-1511 SYS-I3; FHIRGraph.cls:167-280";
        if want("cmc-register-as-built-refusal") {
            let x = Only { m: M { design: Design::AsBuilt }, keep: &[NOCHG] };
            res.push(judge("cmc-register-as-built-refusal", "15", "register", "as-built", "mc", refs, Some(NOCHG),
                           explore(&x, limits()), show));
        }
        if want("cmc-register-as-built-links") {
            let x = Only { m: M { design: Design::AsBuilt }, keep: &[LINKS] };
            res.push(judge("cmc-register-as-built-links", "15", "register", "as-built (rebuild failure reported)", "mc",
                           refs, None, explore(&x, limits()), show));
        }
        if want("cmc-register-reviewed") {
            res.push(judge("cmc-register-reviewed", "15", "register", "reviewed (validate, then one transaction)", "mc",
                           refs, None, explore(&M { design: Design::Reviewed }, limits()), show));
        }
        if want("cmc-register-ctl-upsert") {
            let x = Only { m: M { design: Design::ControlUpsertOutsideTxn }, keep: &[NOCHG] };
            res.push(judge("cmc-register-ctl-upsert", "15", "register", "control: reviewed, upsert outside the transaction",
                           "control", refs, Some(NOCHG), explore(&x, limits()), show));
        }
        if want("cmc-register-wit") {
            let g = "a changed register succeeds";
            res.push(judge("cmc-register-wit", "15", "register", "reviewed", "witness", refs, Some(g),
                           explore(&Witness { m: M { design: Design::Reviewed } }, limits()), show));
        }
    }

    let mut json = String::from("{\n  \"crate\": \"ivg-breadth-c-models\",\n  \"explorer_rev\": \"c03f9fa9be961610f2b274ffbb6a2c88d7d4d877\",\n  \"product_pin\": \"3eaa79cf77d3e0a879b2cced634cf2729d81499e\",\n  \"checks\": [\n");
    for (i, o) in res.iter().enumerate() {
        println!("{:<36} {:<52} expect {:<75} -> {} | {} states, {} transitions, depth {}, {}, {:.2}s{}",
                 o.id, o.design, o.expect, if o.met { "MET" } else { "NOT MET" }, o.states, o.transitions, o.depth,
                 if o.truncated { "truncated" } else { "exhaustive within bounds" }, o.seconds,
                 if o.found.is_empty() { String::new() } else { format!(" | found '{}'", o.found) });
        if !o.trace.is_empty() { println!("{}", o.trace); }
        json += &format!("    {{\"id\": \"{}\", \"module\": \"{}\", \"machine\": \"{}\", \"design\": \"{}\", \"kind\": \"{}\", \
\"refs\": \"{}\", \"expectation\": \"{}\", \"met\": {}, \"result\": \"{}\", \"property_found\": \"{}\", \"states\": {}, \
\"transitions\": {}, \"depth\": {}, \"exhaustive\": {}, \"seconds\": {:.3}, \"counterexample\": \"{}\"}}{}\n",
            o.id, o.module, o.machine, esc(o.design), o.kind, esc(o.refs), esc(&o.expect), o.met, o.result,
            esc(&o.found), o.states, o.transitions, o.depth, !o.truncated, o.seconds, esc(&o.trace),
            if i + 1 < res.len() { "," } else { "" });
    }
    json += "  ]\n}\n";
    if let Some(p) = out { std::fs::write(&p, json).expect("write results"); }
    let failed = res.iter().filter(|o| !o.met).count();
    println!("{} checks, {} met their expectation, {} did not", res.len(), res.len() - failed, failed);
    std::process::exit(if failed == 0 { 0 } else { 1 });
}
