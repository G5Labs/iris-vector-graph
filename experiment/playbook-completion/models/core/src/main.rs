//! Core models of the completion audit (lane core-models): erase -> redact -> replay of iris-vector-graph at pin
//! 3eaa79cf, explored with the G5Labs/actors explorer at c03f9fa.
//!
//!     cargo run --release -- [--list] [--only ID|PREFIX* ...] [--out RESULTS.json]
//!
//! Machines (see MODELS.md): M1 targeting (m1.rs), M2 concurrency (m2.rs), M3 retry/restore (m3_retry.rs),
//! M3 readers/verify (m3_readers.rs), refinement of reviewed M2 against an executable L1 (refine.rs).
//! Every check states its expectation: `pass` (no violation of any kept property, exhaustive within the declared
//! bounds), or the named property it must violate (an as-built finding, a control, a progress-only mutant, or a
//! sharpness witness). The exit status is 0 only when every selected check met its expectation.
mod m1;
mod m2;
mod m3_readers;
mod m3_retry;
mod refine;
mod util;

use explorer::*;
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
        // `refinement::audit` also flags the model's own bound as truncation; only the state cap or the depth limit
        // makes a run non-exhaustive within the declared bounds.
        truncated: r.states >= std::env::var("IVG_CAP").ok().and_then(|v| v.parse().ok()).unwrap_or(cap), seconds: r.seconds,
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
    /// as-built | reviewed | control | progress-mutant | sharpness
    pub design: &'static str,
    pub expect: Expect,
    pub what: &'static str,
    pub run: Box<dyn Fn() -> Res>,
}

pub const CAP: usize = 60_000_000;

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

pub fn m2_check<M: Model<State = m2::S, Action = m2::A>>(m: M, cap: usize) -> Res {
    summarize(explore(&m, limits(cap)), m2::show, cap)
}

fn checks() -> Vec<Check> {
    let mut v = vec![];
    v.extend(m1::checks());
    v.extend(m2_checks());
    v.extend(m3_retry::checks());
    v.extend(m3_readers::checks());
    v.extend(refine::checks());
    v
}

fn m2_checks() -> Vec<Check> {
    use m2::*;
    let mut v: Vec<Check> = vec![];
    let nlt = "INV-no-live-tombstone: no tombstone describes a live incarnation (no transaction open)";
    let stmt = "INV-stmt: live statement entries are exactly the live recorded edges (no transaction open)";
    let adj = "INV-adj: adjacency equals the edge rows (no transaction open)";
    let audit = "INV-audit: each audit counts exactly its own target's tombstones";
    let owner = "INV-marker-owner: a run tombstones and finishes only under its own target's marker";
    let settled = "settled: no marker, no run, no open transaction, every erased target redacted";
    let safety = ["INV-no-live-tombstone: no tombstone describes a live incarnation (no transaction open)",
        "INV-stmt: live statement entries are exactly the live recorded edges (no transaction open)",
        "INV-adj: adjacency equals the edge rows (no transaction open)",
        "INV-text: a revision with a tombstone keeps no free text and no retry key (Decision 2)",
        "INV-retry: a bound key names a revision with no tombstone; a redacted key is unbound",
        "INV-audit-settled: once settled every tombstone is counted by one audit of its own target",
        "INV-replay: with no unrecorded write and every erased target redacted, replay equals the store",
        "INV-audit: each audit counts exactly its own target's tombstones",
        "INV-marker-owner: a run tombstones and finishes only under its own target's marker",
        "INV-marker: while the marker names t no record of t is added"];

    // ---- as-built: the findings, each with the shortest trace (other freedoms switched off to isolate it)
    let quiet = |mut c: Cfg| { c.estop = false; c.pstop = false; c };
    v.push(Check { id: "m2-as-built-F1302-commit-after-check", machine: "M2", design: "as-built", expect: Expect::Violation(nlt),
        what: "F-1302: a commit lands between the unlocked liveness check and the first tombstone (no process stops)",
        run: Box::new(move || m2_check(Only::keep(M2::new(quiet(Cfg::new(Design::AsBuilt))), &[nlt]), CAP)) });
    v.push(Check { id: "m2-as-built-P1311-erase-rollback", machine: "M2", design: "as-built", expect: Expect::Violation(nlt),
        what: "P-1311: the liveness check reads an open erasure's uncommitted deletes; the erasure then rolls back",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.estop = true; c.max_commits = 0;
            m2_check(Only::keep(M2::new(c), &[nlt]), CAP) }) });
    v.push(Check { id: "m2-as-built-commit-rollback", machine: "M2", design: "as-built", expect: Expect::Violation(nlt),
        what: "variant: the liveness check reads a ledger commit's uncommitted delete; the commit is stopped and rolls back",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.pstop = true;
            m2_check(Only::keep(M2::new(c), &[nlt]), CAP) }) });
    v.push(Check { id: "m2-as-built-bypass-rollback", machine: "M2", design: "as-built", expect: Expect::Violation(nlt),
        what: "variant: the liveness check reads a ledger-bypassing writer's uncommitted delete; the writer rolls back",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.bypass = Bypass::NonSerializing; c.max_commits = 0;
            m2_check(Only::keep(M2::new(c), &[nlt]), CAP) }) });
    v.push(Check { id: "m2-as-built-F1303-audit", machine: "M2", design: "as-built", expect: Expect::Violation(audit),
        what: "F-1303: two targets started together; the shared counters make an audit count the other target's tombstones",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.max_commits = 0;
            m2_check(Only::keep(M2::new(c), &[audit]), CAP) }) });
    v.push(Check { id: "m2-as-built-F1303-owner", machine: "M2", design: "as-built", expect: Expect::Violation(owner),
        what: "F-1303: a run tombstones under the other target's marker (or a Final removes it)",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.max_commits = 0;
            m2_check(Only::keep(M2::new(c), &[owner]), CAP) }) });
    v.push(Check { id: "m2-as-built-F1201-stmt", machine: "M2", design: "as-built", expect: Expect::Violation(stmt),
        what: "F-1201: a commit into the graph between the eraser's row delete and its ledger cleanup loses its statement",
        run: Box::new(move || m2_check(Only::keep(M2::new(quiet(Cfg::new(Design::AsBuilt))), &[stmt]), CAP)) });
    v.push(Check { id: "m2-as-built-F1201-adjacency", machine: "M2", design: "as-built", expect: Expect::Violation(adj),
        what: "same root cause as F-1201: the eraser's RemoveGraph kills the adjacency of an edge committed after its row delete",
        run: Box::new(move || m2_check(Only::keep(M2::new(quiet(Cfg::new(Design::AsBuilt))), &[adj]), CAP)) });
    let replay = "INV-replay: with no unrecorded write and every erased target redacted, replay equals the store";
    v.push(Check { id: "m2-as-built-stale-final", machine: "M2", design: "as-built", expect: Expect::Violation(replay),
        what: "new: Final trusts a scan that ended before newer records of the target were committed and erased; the call reports complete",
        run: Box::new(move || { let c = quiet(Cfg::new(Design::AsBuilt));
            m2_check(Only::keep(M2::new(c), &[replay]), CAP) }) });
    v.push(Check { id: "m2-as-built-paced-resume", machine: "M2", design: "as-built", expect: Expect::Violation(settled),
        what: "a resumed call restarts its scan at the first record; resumed with the same max_batches it never reaches Final",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.pace = 1; c.max_commits = 0;
            m2_check(Only::keep(M2::new(c), &[settled]), CAP) }) });
    v.push(Check { id: "m2-sharp-paced-loop", machine: "M2", design: "sharpness", expect: Expect::Violation("reach: a paused call left every record of A tombstoned, the marker set, and Final never ran"),
        what: "witness (as-built, paced): the resumed calls loop over the first record; every record of A is a tombstone and Final is unreachable",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.pace = 1; c.max_commits = 0;
            m2_check(Only::reach_state(M2::new(c), "reach: a paused call left every record of A tombstoned, the marker set, and Final never ran",
                |s| s.marker == Some(0) && s.runs_idle() && s.pending & 1 != 0 && s.audited == [0, 0]
                    && s.revs[0].recs.iter().all(|r| !matches!(r, Rec::Live { e, .. } if g_of(*e as usize) == 0))), CAP) }) });
    v.push(Check { id: "m2-as-built-marker-holds", machine: "M2", design: "as-built", expect: Expect::Pass,
        what: "at the pin INV-marker holds (BlocksCommit refuses commits into the marked target); no process stops, 1 commit",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.max_commits = 1;
            m2_check(Only::keep(M2::new(c), &["INV-marker: while the marker names t no record of t is added"]), CAP) }) });
    v.push(Check { id: "m2-as-built-unpaced-progress", machine: "M2", design: "as-built", expect: Expect::Pass,
        what: "companion of the paced check: with unpaced resumes the as-built machine can always settle (AG EF)",
        run: Box::new(move || { let mut c = quiet(Cfg::new(Design::AsBuilt)); c.max_commits = 0;
            m2_check(Only::keep(M2::new(c), &[settled]), CAP) }) });

    // ---- reviewed
    v.push(Check { id: "m2-reviewed", machine: "M2", design: "reviewed", expect: Expect::Pass,
        what: "HD-1201 + HD-1301: every safety property and AG EF settled; eraser, committer and runs may be stopped",
        run: Box::new(move || m2_check(M2::new(Cfg::new(Design::Reviewed)), CAP)) });
    // the bypass writer in three partitions (1 write + 1 commit with every process stoppable exceeded 19 GB)
    for (pf, writes, commits) in [("w1c0", 1u8, 0u8), ("w2c0", 2u8, 0u8), ("w1c1", 1u8, 1u8)] {
        v.push(Check { id: Box::leak(format!("m2-reviewed-bypass-serializing-{pf}").into_boxed_str()), machine: "M2", design: "reviewed", expect: Expect::Pass,
            what: Box::leak(format!("reviewed + a ledger-bypassing writer that serializes like a ledger write ({writes} bypass writes, {commits} commits): every property except INV-stmt (the writer's own, F-0303) and AG EF").into_boxed_str()),
            run: Box::new(move || { let mut c = Cfg::new(Design::Reviewed); c.bypass = Bypass::Serializing; c.max_commits = commits; c.max_writes = writes;
                if commits > 0 { c.pstop = false; c.estop = false; } // committer and eraser not stopped in this partition
                let keep: Vec<&'static str> = safety.iter().copied().filter(|n| *n != stmt).chain([settled]).collect();
                m2_check(Only::keep(M2::new(c), &keep), CAP) }) });
    }
    v.push(Check { id: "m2-reviewed-bypass-stmt", machine: "M2", design: "reviewed", expect: Expect::Violation(stmt),
        what: "a ledger-bypassing delete of a recorded edge leaves its live statement (F-0303 class): the writer itself breaks INV-stmt",
        run: Box::new(move || { let mut c = Cfg::new(Design::Reviewed); c.bypass = Bypass::Serializing; c.max_commits = 0;
            m2_check(Only::keep(M2::new(c), &[stmt]), CAP) }) });
    v.push(Check { id: "m2-reviewed-bypass-nonserializing", machine: "M2", design: "reviewed", expect: Expect::Violation(nlt),
        what: "reviewed design + a bypass writer that does not serialize: the locked Start still reads its uncommitted delete",
        run: Box::new(move || { let mut c = Cfg::new(Design::Reviewed); c.bypass = Bypass::NonSerializing; c.max_commits = 0;
            m2_check(Only::keep(M2::new(c), &[nlt]), CAP) }) });

    // ---- progress-only mutants of the reviewed design: AG EF fails, every safety property holds
    for (id, mu, pace, what) in [
        ("m2-progress-final-keeps-marker", Mutant::FinalKeepsMarker, 0u8, "Final writes the audit but never removes the marker"),
        ("m2-progress-paced-restart", Mutant::None, 1u8, "every resumed call restarts the scan and pauses after one record"),
    ] {
        v.push(Check { id: Box::leak(format!("{id}-progress").into_boxed_str()), machine: "M2", design: "progress-mutant",
            expect: Expect::Violation(settled), what,
            run: Box::new(move || { let mut c = Cfg::new(Design::Reviewed); c.mutant = mu; c.pace = pace;
                m2_check(Only::keep(M2::new(c), &[settled]), CAP) }) });
        v.push(Check { id: Box::leak(format!("{id}-safety").into_boxed_str()), machine: "M2", design: "progress-mutant",
            expect: Expect::Pass, what: "the same mutant keeps every safety property",
            run: Box::new(move || { let mut c = Cfg::new(Design::Reviewed); c.mutant = mu; c.pace = pace;
                m2_check(Only::keep(M2::new(c), &safety), CAP) }) });
    }

    // ---- controls: mutants of the reviewed design that the checker must catch
    for (id, mu, prop, what) in [
        ("m2-control-counters-swapped", Mutant::CountersSwapped, audit, "the audit reads the other target's counter"),
        ("m2-control-batch-under-other-marker", Mutant::BatchUnderOtherMarker, owner, "the batch's own-marker check is dropped"),
        ("m2-control-erase-no-head-lock", Mutant::EraseNoHeadLock, stmt, "the eraser takes no head lock (HD-1201 dropped)"),
        ("m2-control-unlocked-start", Mutant::UnlockedStart, nlt, "the opening check is unlocked, the marker comes with the first tombstone (HD-1301 dropped)"),
        ("m2-control-final-trusts-old-scan", Mutant::FinalTrustsOldScan, "INV-replay: with no unrecorded write and every erased target redacted, replay equals the store", "Final trusts the end of an earlier scan (the pin's Final)"),
    ] {
        v.push(Check { id, machine: "M2", design: "control", expect: Expect::Violation(prop), what,
            run: Box::new(move || { let mut c = Cfg::new(Design::Reviewed); c.mutant = mu;
                m2_check(Only::keep(M2::new(c), &[prop]), CAP) }) });
    }

    // ---- sharpness: key states and steps are reachable in the reviewed machine
    let rv = || M2::new(Cfg::new(Design::Reviewed));
    v.push(Check { id: "m2-sharp-commit-refused", machine: "M2", design: "sharpness", expect: Expect::Violation("reach: a commit into the marked target is refused"),
        what: "witness: BlocksCommit refuses a commit into the marked target",
        run: Box::new(move || m2_check(Only::reach_step(rv(), "reach: a commit into the marked target is refused",
            |s, a, _| matches!(a, A::PEnd) && matches!(s.p, Pp::Open { ok: false, .. })), CAP)) });
    v.push(Check { id: "m2-sharp-both-audited", machine: "M2", design: "sharpness", expect: Expect::Violation("reach: both targets audited"),
        what: "witness: both targets redacted and audited",
        run: Box::new(move || m2_check(Only::reach_state(rv(), "reach: both targets audited",
            |s| s.audited[0] > 0 && s.audited[1] > 0), CAP)) });
    v.push(Check { id: "m2-sharp-resume-completes", machine: "M2", design: "sharpness", expect: Expect::Violation("reach: a stopped run is resumed and audited"),
        what: "witness: a run stopped after a tombstone is resumed by a later call that writes the audit",
        run: Box::new(move || m2_check(Only::reach_step(rv(), "reach: a stopped run is resumed and audited",
            |s, a, t| matches!(a, A::Final(p) if matches!(s.runs[*p as usize], Run::Scan { made: false, .. }))
                && matches!(t.revs.last().map(|r| r.recs[0]), Some(Rec::Audit { n, .. }) if n > 0) && t.revs.len() > s.revs.len()), CAP)) });
    v.push(Check { id: "m2-sharp-erase-rollback", machine: "M2", design: "sharpness", expect: Expect::Violation("reach: an erasure is rolled back after its ledger cleanup"),
        what: "witness: an erasure stopped after E3 is rolled back",
        run: Box::new(move || m2_check(Only::reach_step(rv(), "reach: an erasure is rolled back after its ledger cleanup",
            |s, a, _| matches!(a, A::EStop) && matches!(s.e, Ep::Open { step: 3, .. })), CAP)) });
    v.push(Check { id: "m2-sharp-final-other-marker", machine: "M2", design: "sharpness", expect: Expect::Violation("reach: a Final runs under another target's marker"),
        what: "witness (as-built): Final with another target's marker",
        run: Box::new(move || { let mut c = Cfg::new(Design::AsBuilt); c.max_commits = 0; c.estop = false; c.pstop = false;
            m2_check(Only::reach_step(M2::new(c), "reach: a Final runs under another target's marker",
            |s, a, t| matches!(a, A::Final(p) if matches!(s.runs[*p as usize], Run::Scan { t: tg, .. } if s.marker.is_some() && s.marker != Some(tg)))
                && t.revs.len() > s.revs.len()), CAP) }) });
    v.push(Check { id: "m2-sharp-final-no-marker", machine: "M2", design: "sharpness", expect: Expect::Violation("reach: a Final runs with no marker and drops statements"),
        what: "witness (as-built): Final with no marker that still drops statements and writes an audit",
        run: Box::new(move || { let mut c = Cfg::new(Design::AsBuilt); c.max_commits = 1; c.estop = false; c.pstop = false;
            m2_check(Only::reach_step(M2::new(c), "reach: a Final runs with no marker and drops statements",
            |s, a, t| matches!(a, A::Final(_)) && s.marker.is_none() && t.revs.len() > s.revs.len()), CAP) }) });
    v
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let out = args.iter().position(|a| a == "--out").and_then(|i| args.get(i + 1)).cloned();
    let only: Vec<String> = args.iter().position(|a| a == "--only")
        .map(|i| args[i + 1..].iter().take_while(|a| !a.starts_with("--")).cloned().collect()).unwrap_or_default();
    let all = checks();
    if args.iter().any(|a| a == "--list") {
        for c in &all { println!("{:<48} {:<5} {:<16} {}", c.id, c.machine, c.design, c.what); }
        return;
    }
    let mut json = String::from("{\n  \"crate\": \"experiment/playbook-completion/models/core\",\n  \"explorer_rev\": \"c03f9fa9be961610f2b274ffbb6a2c88d7d4d877\",\n  \"product_pin\": \"3eaa79cf77d3e0a879b2cced634cf2729d81499e\",\n");
    json += &format!("  \"max_states\": {},\n  \"checks\": [\n", CAP);
    let mut met_all = true;
    let mut first = true;
    let mut n = 0;
    // --only takes exact ids; an id ending in '*' selects by prefix
    let sel = |id: &str| only.is_empty() || only.iter().any(|o| match o.strip_suffix('*') { Some(p) => id.starts_with(p), None => id == o });
    for c in all.iter().filter(|c| sel(c.id)) {
        n += 1;
        let r = (c.run)();
        let (exp, met) = match c.expect {
            Expect::Pass => ("pass".to_string(), r.violation.is_none() && !r.truncated),
            Expect::Violation(p) => (format!("violation of '{p}'"),
                r.violation.as_ref().map_or(false, |(found, _, _)| p.is_empty() || found == p)),
        };
        met_all &= met;
        let result = match (&r.violation, met) {
            (None, true) => "pass".to_string(),
            (Some(_), true) => "expected-violation".to_string(),
            (None, false) => if r.truncated { "truncated".into() } else { "no-violation (expected one)".into() },
            (Some((p, _, _)), false) => format!("unexpected violation of '{p}'"),
        };
        println!("{:<48} {:<16} {} | {} states, {} transitions, depth {}, {}, {:.1}s",
                 c.id, c.design, if met { "MET" } else { "NOT MET" }, r.states, r.transitions, r.depth,
                 if r.truncated { "TRUNCATED at the state cap" } else { "exhaustive within bounds" }, r.seconds);
        println!("    expect {exp}; result {result}");
        if let Some((_, _, t)) = &r.violation { println!("{t}"); }
        if !first { json += ",\n"; }
        first = false;
        json += &format!("    {{\"id\": \"{}\", \"machine\": \"{}\", \"design\": \"{}\", \"what\": \"{}\", \"expectation\": \"{}\", \"met\": {}, \"result\": \"{}\", \"states\": {}, \"transitions\": {}, \"depth\": {}, \"exhaustive\": {}, \"seconds\": {:.2}, \"violated\": \"{}\", \"kind\": \"{}\", \"trace\": \"{}\"}}",
            c.id, c.machine, c.design, esc(c.what), esc(&exp), met, esc(&result), r.states, r.transitions, r.depth,
            if r.truncated { "\"truncated\"" } else { "\"exhaustive-within-bounds\"" }, r.seconds,
            esc(r.violation.as_ref().map_or("", |v| v.0.as_str())), r.violation.as_ref().map_or("", |v| v.1.as_str()),
            esc(r.violation.as_ref().map_or("", |v| v.2.as_str())));
        if let Some(p) = &out {
            std::fs::write(p, format!("{json}\n  ]\n}}\n")).expect("write results");
        }
    }
    println!("core models: {n} checks, {}", if met_all { "every expectation met" } else { "SOME EXPECTATION NOT MET" });
    std::process::exit(if met_all { 0 } else { 1 });
}
