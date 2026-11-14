//! M-04 Derived store with staleness (axiom AX-08). Generic machine over `DerivedObject`.
//!
//! Abstract state: the committed source value `src` (0..2) and an open writer's uncommitted value `dirty` (visible to
//! other processes: E-VIS); the derived value `der` (the source value it reflects; none = cleared, which a reader
//! with a current stamp reads as 0, the warm-stamp reading of F-0406); `stamp` and the live `token` (monotone, not
//! undone by rollback: E-INCR). `f` is the identity on the abstract domain, so the laws are independent of the
//! derivation; a `wrong` path computes f(v)+1 (a maintenance function that counts twice, F-0501).
//! The writer runs one write path per transaction: optional shared writer lock (held to the end, E-LOCK-DEFER), an
//! optional token step before the write, the write (a `sync` path updates `der` in the same transaction, as a
//! functional index does, X-FX; `survives` makes that update a $Increment a rollback keeps, F-C0801), an optional
//! token step after, then commit or roll back (at any point: a stop rolls back, E-STOP). A reader fill stores a value
//! with the token it read: `Plain` (token, compute, store), `Probe` (token, probe the writer lock exclusively with no
//! wait, compute, store only if granted and the token unchanged: ADR-0012 / Adj.cls:34-39), controls `ProbeLate` and
//! `TokenAfter`. A rebuild (no writer open) recomputes and stamps. A clear removes `der` and keeps (as built) or
//! invalidates the stamp. An answer through the gate reads `der` when the stamp is current (or always, unchecked).
//!
//! Laws: M04-L1 (invariant) no writer open => (stamp = token => value(der) = src); M04-L2 (action) a commit that
//! changes the source moved the token or is sync; M04-L3 (action) a rebuild leaves der = src with the current stamp;
//! M04-L4 (action) an answer with no writer open equals src.
//! Bounds: 2 writes, 2 fills, 1 rebuild, 1 clear, 2 answers.
use crate::harness::*;
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct WPath { pub lock: bool, pub pre: bool, pub post: bool, pub sync: bool, pub wrong: bool, pub survives: bool }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Fill { Off, Plain, Probe, ProbeLate, TokenAfter }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Clear { NoClear, KeepStamp, Restamp }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Gate { Checked, Unchecked }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rebuild { Correct, StampOnly }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Cfg { pub paths: Vec<WPath>, pub fill: Fill, pub clear: Clear, pub gate: Gate, pub rebuild: Rebuild }

pub const NONE: WPath = WPath { lock: false, pre: false, post: false, sync: false, wrong: false, survives: false };
pub const TOKEN: WPath = WPath { lock: true, pre: true, post: true, sync: false, wrong: false, survives: false };
pub const POST_ONLY: WPath = WPath { lock: true, pre: false, post: true, sync: false, wrong: false, survives: false };
pub const SYNC: WPath = WPath { lock: false, pre: false, post: false, sync: true, wrong: false, survives: false };

pub fn reviewed_cfg() -> Cfg { Cfg { paths: vec![TOKEN], fill: Fill::Probe, clear: Clear::Restamp, gate: Gate::Checked, rebuild: Rebuild::Correct } }

/// One as-built variant of an object: its configuration, the law it departs from and its findings (or exception).
pub struct Variant { pub label: &'static str, pub cfg: Cfg, pub law: &'static str, pub findings: &'static [&'static str], pub exception: &'static str }

pub trait DerivedObject {
    fn name(&self) -> &'static str;
    fn objects(&self) -> &'static [&'static str];
    fn as_built(&self) -> Vec<Variant>;
    fn reviewed(&self) -> Cfg { reviewed_cfg() }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum W { Idle, Begun(u8), Pre(u8), Written(u8, u8), Post(u8, u8) }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum R { Idle, Token(u8), Probed(u8, bool), Computed(u8, bool, u8), Early(u8), LateProbed(u8, bool, u8) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub src: u8,
    pub dirty: Option<u8>,
    pub der: Option<u8>,
    pub sync_der: Option<u8>,
    pub stamp: u8,
    pub token: u8,
    pub w: W,
    pub bumped: bool,
    pub r: R,
    pub n: [u8; 5],
    pub last_ok: bool,
}

#[derive(Clone, Debug)]
pub enum A { Begin(u8), PreBump, Write(u8), PostBump, Commit, Rollback, RToken, RProbe, RCompute, RStore, Rebuild, Clear, Answer }

pub struct Machine<'a, O: DerivedObject> { pub o: &'a O, pub c: Cfg }

pub const L1: &str = "M04-L1 current or stale";
pub const L2: &str = "M04-L2 every source write maintains or moves the token";
pub const L3: &str = "M04-L3 a rebuild is current and correct";
pub const L4: &str = "M04-L4 a gated read answers the source";

fn val(d: Option<u8>) -> u8 { d.unwrap_or(0) }

impl<'a, O: DerivedObject> Machine<'a, O> {
    fn path(&self, s: &S) -> Option<WPath> {
        match s.w { W::Idle => None, W::Begun(p) | W::Pre(p) | W::Written(p, _) | W::Post(p, _) => Some(self.c.paths[p as usize]) }
    }
    fn writer_locked(&self, s: &S) -> bool { self.path(s).is_some_and(|p| p.lock) }
}

impl<'a, O: DerivedObject> Model for Machine<'a, O> {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { src: 1, dirty: None, der: Some(1), sync_der: None, stamp: 0, token: 0, w: W::Idle, bumped: false, r: R::Idle, n: [0; 5], last_ok: true }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v: Vec<A> = (0..self.c.paths.len() as u8).map(A::Begin).collect();
        v.extend([A::PreBump, A::Write(0), A::Write(2), A::PostBump, A::Commit, A::Rollback, A::RToken, A::RProbe, A::RCompute, A::RStore,
                  A::Rebuild, A::Clear, A::Answer]);
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let c = &self.c;
        let mut u = s.clone();
        match *a {
            A::Begin(p) => { if s.w != W::Idle || s.n[0] >= 2 { return None; } u.n[0] += 1; u.w = W::Begun(p); u.bumped = false; }
            A::PreBump => { let W::Begun(p) = s.w else { return None }; if !c.paths[p as usize].pre { return None; } u.token += 1; u.bumped = true; u.w = W::Pre(p); }
            A::Write(v) => {
                let p = match s.w { W::Begun(p) if !c.paths[p as usize].pre => p, W::Pre(p) => p, _ => return None };
                if v == s.src { return None; }
                let wp = c.paths[p as usize];
                u.dirty = Some(v);
                if wp.sync { let fv = if wp.wrong { v + 1 } else { v }; if wp.survives { u.der = Some(fv); } else { u.sync_der = Some(fv); } }
                u.w = W::Written(p, v);
            }
            A::PostBump => { let W::Written(p, v) = s.w else { return None }; if !c.paths[p as usize].post { return None; } u.token += 1; u.bumped = true; u.w = W::Post(p, v); }
            A::Commit => {
                let (p, v) = match s.w { W::Written(p, v) if !c.paths[p as usize].post => (p, v), W::Post(p, v) => (p, v), _ => return None };
                let wp = c.paths[p as usize];
                u.src = v; u.dirty = None;
                if wp.sync && !wp.survives { u.der = s.sync_der; u.stamp = s.token; }
                if wp.sync && wp.survives { u.stamp = s.token; }
                u.sync_der = None; u.w = W::Idle;
            }
            A::Rollback => { if s.w == W::Idle { return None; } u.dirty = None; u.sync_der = None; u.w = W::Idle; }
            A::RToken => {
                if c.fill == Fill::Off || s.n[1] >= 2 { return None; }
                match (s.r, c.fill) {
                    (R::Idle, Fill::TokenAfter) => return None,
                    (R::Idle, _) => { u.r = R::Token(s.token); u.n[1] += 1; }
                    (R::Early(v), Fill::TokenAfter) => { u.r = R::Computed(s.token, true, v); }
                    _ => return None,
                }
            }
            A::RProbe => {
                let granted = !self.writer_locked(s);
                match (s.r, c.fill) {
                    (R::Token(t), Fill::Probe) => u.r = R::Probed(t, granted),
                    (R::Computed(t, _, v), Fill::ProbeLate) => u.r = R::LateProbed(t, granted, v),
                    _ => return None,
                }
            }
            A::RCompute => {
                let seen = s.dirty.unwrap_or(s.src);
                match (s.r, c.fill) {
                    (R::Token(t), Fill::Plain) => u.r = R::Computed(t, true, seen),
                    (R::Probed(t, g), Fill::Probe) => u.r = R::Computed(t, g, seen),
                    (R::Token(t), Fill::ProbeLate) => u.r = R::Computed(t, true, seen),
                    (R::Idle, Fill::TokenAfter) => { if s.n[1] >= 2 { return None; } u.n[1] += 1; u.r = R::Early(seen); }
                    _ => return None,
                }
            }
            A::RStore => {
                let (t, g, v) = match (s.r, c.fill) {
                    (R::Computed(t, g, v), Fill::Plain) | (R::Computed(t, g, v), Fill::TokenAfter) => (t, g, v),
                    (R::Computed(t, g, v), Fill::Probe) => (t, g && s.token == t, v),
                    (R::LateProbed(t, g, v), Fill::ProbeLate) => (t, g && s.token == t, v),
                    _ => return None,
                };
                if g { u.der = Some(v); u.stamp = t; }
                u.r = R::Idle;
            }
            A::Rebuild => {
                if s.w != W::Idle || s.n[2] >= 1 { return None; }
                u.n[2] += 1;
                if c.rebuild == Rebuild::Correct { u.der = Some(s.src); }
                u.stamp = s.token;
            }
            A::Clear => {
                if c.clear == Clear::NoClear || s.n[3] >= 1 || s.der.is_none() { return None; }
                u.n[3] += 1; u.der = None;
                if c.clear == Clear::Restamp { u.stamp = 255; }
            }
            A::Answer => {
                if s.w != W::Idle || s.n[4] >= 2 { return None; }
                u.n[4] += 1;
                let ans = match c.gate { Gate::Checked => if s.stamp == s.token { val(s.der) } else { s.src }, Gate::Unchecked => val(s.der) };
                u.last_ok = ans == s.src;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(L1, |s: &S| s.w != W::Idle || s.stamp != s.token || val(s.der) == s.src)]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        let paths = self.c.paths.clone();
        vec![
            action_property(L2, move |o: &S, a: &A, n: &S| {
                if !matches!(a, A::Commit) || n.src == o.src { return true; }
                let p = match o.w { W::Written(p, _) | W::Post(p, _) => paths[p as usize], _ => return true };
                p.sync || o.bumped
            }),
            action_property(L3, |_o: &S, a: &A, n: &S| !matches!(a, A::Rebuild) || (n.der == Some(n.src) && n.stamp == n.token)),
            action_property(L4, |_o: &S, a: &A, n: &S| !matches!(a, A::Answer) || n.last_ok),
        ]
    }
}


macro_rules! object {
    ($t:ident, $name:expr, [$($o:expr),*], [$($v:expr),*]) => {
        pub struct $t;
        impl DerivedObject for $t {
            fn name(&self) -> &'static str { $name }
            fn objects(&self) -> &'static [&'static str] { &[$($o),*] }
            fn as_built(&self) -> Vec<Variant> { vec![$($v),*] }
        }
    };
}

fn cfg(paths: Vec<WPath>, fill: Fill, clear: Clear, gate: Gate) -> Cfg { Cfg { paths, fill, clear, gate, rebuild: Rebuild::Correct } }
fn var(label: &'static str, cfg: Cfg, law: &'static str, findings: &'static [&'static str]) -> Variant { Variant { label, cfg, law, findings, exception: "" } }

// A declared functional index: every row writer maintains the entry in its own transaction (X-FX; AdjIndex.cls:12-23).
object!(AdjacencyFunctional, "adjacency-functional", ["04/adjacency-entry", "05/latest-event-index", "09/compiled-shape", "05/triple-row"],
        [var("canonical", cfg(vec![SYNC], Fill::Off, Clear::NoClear, Gate::Checked), "", &[])]);
// Degree cache and result cache: the writer bumps after its write; a reader fill stores dirty counts (F-0402); a
// writer stopped between write and bump (F-C0401); clearing the cache keeps the warm stamp (F-0406).
object!(DegreeCache, "degree-cache", ["04/degree-cache-entry"],
        [var("F0402", cfg(vec![POST_ONLY], Fill::Plain, Clear::NoClear, Gate::Checked), L1, &["F-0402"]),
         var("FC0401", cfg(vec![POST_ONLY], Fill::Probe, Clear::NoClear, Gate::Checked), L1, &["F-C0401"]),
         var("F0406", cfg(vec![TOKEN], Fill::Probe, Clear::KeepStamp, Gate::Checked), L1, &["F-0406"])]);
// The result cache read through the adjacency token (AlgoCache.cls:1-50): a build stores dirty answers (F-0402).
object!(ResultCache04, "result-cache-04", ["04/result-cache-entry"],
        [var("F0402", cfg(vec![POST_ONLY], Fill::Plain, Clear::NoClear, Gate::Checked), L1, &["F-0402"])]);
// Algorithm cache: a node written without an edge moves no token (F-1004).
object!(AlgoCacheEdgeless, "algo-cache-edgeless", ["10/result-cache-entry"],
        [var("F1004", cfg(vec![TOKEN, NONE], Fill::Probe, Clear::NoClear, Gate::Checked), L2, &["F-1004"])]);
// Interned snapshot: some edge writers leave it with nothing saying it is out of date (F-1005); a rolled-back edge
// write leaves its counters raised ($Increment, F-C0801).
object!(InternedSnapshot, "interned-snapshot", ["10/interned-snapshot"],
        [var("F1005", cfg(vec![TOKEN, NONE], Fill::Off, Clear::NoClear, Gate::Checked), L2, &["F-1005"]),
         var("FC0801", cfg(vec![WPath { survives: true, ..SYNC }], Fill::Off, Clear::NoClear, Gate::Checked), L1, &["F-C0801"])]);
// BM25: a node text change neither reindexes nor marks the index stale (F-0703).
object!(Bm25TextChange, "bm25-text-change", ["07/bm25-index", "17/index-handle"],
        [var("F0703", cfg(vec![SYNC, NONE], Fill::Off, Clear::NoClear, Gate::Checked), L2, &["F-0703"])]);
// Ledger statement map: a direct edge delete leaves the ledger's live link (F-0303).
object!(StatementMapDirectDelete, "statement-map-direct-delete", ["11/edge-statement"],
        [var("F0303", cfg(vec![SYNC, NONE], Fill::Off, Clear::NoClear, Gate::Checked), L2, &["F-0303"])]);
// Temporal bucket aggregate: an update-mode write counts its edge again (F-0501).
object!(BucketAggregateUpdate, "bucket-aggregate-update", ["05/temporal-coordinates"],
        [var("F0501", cfg(vec![WPath { wrong: true, ..SYNC }], Fill::Off, Clear::NoClear, Gate::Checked), L1, &["F-0501"])]);
// An engine keeps a graph's mode forever: another engine's change is never seen (F-0208).
object!(EngineModeCache, "engine-mode-cache", ["02/graph-mode"],
        [var("F0208", cfg(vec![NONE], Fill::Off, Clear::NoClear, Gate::Checked), L2, &["F-0208"])]);
// TTL caches with no staleness signal: the 5 s strict-mode guard (F-0302); the documented 30 s route memory (EXC-05).
object!(TtlCache, "ttl-cache", ["03/ledger-state", "06/route"],
        [var("F0302", cfg(vec![NONE], Fill::Off, Clear::NoClear, Gate::Checked), L2, &["F-0302"]),
         Variant { label: "EXC05", cfg: cfg(vec![NONE], Fill::Off, Clear::NoClear, Gate::Checked), law: L2, findings: &[], exception: "EXC-05" }]);
// The native gate checks the edge index's declaration but reads the label index unchecked (F-0906).
object!(NativeGateLabelIndex, "native-gate-label-index", ["09/engine-native-path"],
        [var("F0906", cfg(vec![NONE], Fill::Off, Clear::NoClear, Gate::Unchecked), L4, &["F-0906"])]);
// IVF / tree / PLAID indexes: the erasure path removes vectors without maintaining them (F-0606).
object!(IvfErase, "ivf-erase", ["06/ivf-index"],
        [var("F0606", cfg(vec![SYNC, NONE], Fill::Off, Clear::NoClear, Gate::Checked), L2, &["F-0606"])]);

fn instance_checks<O: DerivedObject>(o: &O) -> Vec<Outcome> {
    let n = o.name();
    let mut out = vec![];
    for v in o.as_built() {
        let m = Machine { o, c: v.cfg.clone() };
        let id = if v.label == "canonical" { format!("derived-{n}-as-built") } else { format!("derived-{n}-as-built-{}", v.label) };
        if v.law.is_empty() {
            out.push(check_keep(&id, meta("M-04", "derived", n, o.objects(), "as-built", "safety", "all", v.findings, ""), Expect::Pass, &Keep::safety(&m)));
        } else {
            let design = if v.exception.is_empty() { "as-built" } else { "exception" };
            out.push(check_keep(&id, meta("M-04", "derived", n, o.objects(), design, "safety", v.law, v.findings, v.exception), Expect::Violation(v.law), &Keep::only(&m, &[v.law])));
        }
    }
    let rv = Machine { o, c: o.reviewed() };
    out.push(check_keep(&format!("derived-{n}-reviewed"), meta("M-04", "derived", n, o.objects(), "reviewed", "safety", "all", &[], ""), Expect::Pass, &Keep::safety(&rv)));
    out
}

pub fn checks() -> Vec<Outcome> {
    let mut out = vec![];
    out.extend(instance_checks(&AdjacencyFunctional));
    out.extend(instance_checks(&DegreeCache));
    out.extend(instance_checks(&ResultCache04));
    out.extend(instance_checks(&AlgoCacheEdgeless));
    out.extend(instance_checks(&InternedSnapshot));
    out.extend(instance_checks(&Bm25TextChange));
    out.extend(instance_checks(&StatementMapDirectDelete));
    out.extend(instance_checks(&BucketAggregateUpdate));
    out.extend(instance_checks(&EngineModeCache));
    out.extend(instance_checks(&TtlCache));
    out.extend(instance_checks(&NativeGateLabelIndex));
    out.extend(instance_checks(&IvfErase));
    let o = &DegreeCache;
    let ctl = |id: &str, law: &'static str, c: Cfg| {
        let m = Machine { o, c };
        check_keep(id, meta("M-04", "derived", "degree-cache", o.objects(), "control", "safety", law, &[], ""), Expect::Violation(law), &Keep::only(&m, &[law]))
    };
    let r = reviewed_cfg();
    out.push(ctl("derived-control-C1-unmaintained-path", L2, Cfg { paths: vec![TOKEN, NONE], ..r.clone() }));
    out.push(ctl("derived-control-C2-token-after-compute", L1, Cfg { fill: Fill::TokenAfter, ..r.clone() }));
    out.push(ctl("derived-control-C3-rebuild-stamp-only", L3, Cfg { rebuild: Rebuild::StampOnly, ..r.clone() }));
    out.push(ctl("derived-control-C4-unchecked-gate", L4, Cfg { gate: Gate::Unchecked, ..r.clone() }));
    out.push(ctl("derived-control-C5-probe-late", L1, Cfg { fill: Fill::ProbeLate, ..r.clone() }));
    let rv = Machine { o, c: r };
    let sm = || meta("M-04", "derived", "degree-cache", DegreeCache.objects(), "reviewed", "sharpness", "", &[], "");
    out.push(reach("derived-sharp-stale", sm(), &rv, "never: stale (stamp behind token) with no writer open", |s: &S| s.w == W::Idle && s.stamp != s.token));
    out.push(reach("derived-sharp-fill-current", sm(), &rv, "never: a reader fill made the entry current after a write",
                   |s: &S| s.n[0] >= 1 && s.n[2] == 0 && s.stamp == s.token && s.der == Some(s.src) && s.src != 1));
    out.push(reach("derived-sharp-rebuilt", sm(), &rv, "never: rebuilt and current after a committed write",
                   |s: &S| s.n[2] == 1 && s.src != 1 && s.stamp == s.token));
    out
}
