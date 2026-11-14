//! Module 11 (ledger core) explorer models at pin 3eaa79cf. Six small machines over abstracted real state; each has
//! an as-built design (reproducing a finding, or passing where the pin is right), a reviewed design (only where
//! experiment/playbook-completion/decisions.md supports or assumes the contract), a negative control (a mutant the
//! checker must catch) and sharpness witnesses (key states reachable; AG EF where progress matters).
//!
//! Abstracted state (globals/tables at the pin):
//! - `^IVG.Ledger("meta","state")`, `("head")`, the revision row `Graph_KG.ledger_revisions` (IdKey Seq, unique), the
//!   head lock `^IVG.Ledger("head")` (Ledger.cls:252-329 Enable, :397-528 Commit/CommitInTxn, :532-566 WriteRevision);
//! - the retry key map `^IVG.Ledger("idem",key)` (Ledger.cls:453-463, :526);
//! - the stats row `Graph_KG.ledger_stats` (one `$List` data node `^Graph.KG.LedgerStatsD("default")`, %OpenId/%Save,
//!   LedgerStats.cls:51-88; saved inside commits by WriteRevision Ledger.cls:559-565 and by Bump after the commit);
//! - the guard cache of one engine (iris_vector_graph/ledger/guard.py:20-80: TTL 5 s, fail-open probe);
//! - post-commit properties written by the client after the commit (ledger/client.py:430-487; no `replayed` test);
//! - the adoption path (client.py:291-296 enable -> replay.py:806-857 verify(adopt=True): records read up to the head,
//!   then the live tables, then a commit of kind adoption with no expected head; LedgerGenesis.cls:82-129 Adopt).
//! IRIS facts the machines encode (premises; observed live on AUDITB, see findings/audit/11.json): a global set inside
//! an open transaction is visible to other processes at once (dirty read, P-0002); a `Lock -` inside a transaction is
//! deferred to its end (Ledger.cls:388-396 comment; b-11-live-concurrency2 F-1102b: a Bump waited 10 s on the stats row
//! lock held by a caller transaction, then failed); a rollback restores each node's before-image.
//!
//! Shared invariant across modules 08 and 11 (machine `guard`): **in strict mode every governed write is recorded
//! or refused** (LED-B11, LED-B11.5; specs/213-graph-revision-ledger/contracts/ledger-api.md:82-92). It covers the
//! engine API writers (module 11, incl. the unguarded paths of F-1108) and Cypher writes (module 08, F-0801, which
//! call the same cached guard: iris_vector_graph/_engine/query.py write path -> ledger_check). Raw SQL and BulkLoader are
//! outside it by the contract's named exception (HD-0301) and are not modelled as governed writers.
use breadth_b::*;
use explorer::*;

// =============================================================================================================== enable
// F-1104, LED-B1.12 (two enables at the same time both get the genesis back), LED-B1.7, LED-B1.8.
// as-built: Enable reads the state before the head lock and never re-reads it (Ledger.cls:254-266); the enabled
// fast path answers the head with no lock (:255-260), so a dirty "enabled" with head 0 answers "revision row missing";
// a second genesis re-runs and its seq-1 row save fails (P-1106). reviewed (HD-1104 lifecycle unchanged; LED-B1.12
// contract): take the head lock first, then read the state. control: reviewed without the head lock.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum EDesign { AsBuilt, Reviewed, ControlNoLock }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Epc { Idle, Ready, Locked, Head0, Done(bool) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct ES { enabled: bool, head: u8, rev1: bool, lock: Option<u8>, pc: [Epc; 2], pre: [(bool, u8, bool); 2] }

#[derive(Clone, Debug)]
pub enum EA { Start(u8), Lock(u8), SetState(u8), Save(u8) }

pub struct Enable { pub d: EDesign }

const E_OK: &str = "LED-B1.12 every concurrent enable answers the genesis";
const E_CONS: &str = "LED-B1.7 between transactions: enabled iff revision 1 exists and is the head";
const E_W_BOTH: &str = "witness: both enables answered and the ledger is enabled at head 1";
const E_DONE: &str = "AG EF every enable call finishes";

impl Model for Enable {
    type State = ES;
    type Action = EA;
    fn init_states(&self) -> Vec<ES> {
        vec![ES { enabled: false, head: 0, rev1: false, lock: None, pc: [Epc::Idle; 2], pre: [(false, 0, false); 2] }]
    }
    fn actions(&self, _: &ES) -> Vec<EA> {
        let mut v = vec![];
        for i in 0..2 { v.extend([EA::Start(i), EA::Lock(i), EA::SetState(i), EA::Save(i)]); }
        v
    }
    fn next(&self, s: &ES, a: &EA) -> Option<ES> {
        let mut t = s.clone();
        let locked = self.d != EDesign::ControlNoLock;
        match *a {
            EA::Start(i) => {
                let i = i as usize;
                if s.pc[i] != Epc::Idle { return None; }
                match self.d {
                    EDesign::AsBuilt => {
                        if s.enabled {
                            // fast path, no lock: RevisionResponse(head) needs the head's revision row
                            t.pc[i] = Epc::Done(s.head >= 1 && s.rev1);
                        } else { t.pc[i] = Epc::Ready; }
                    }
                    _ => t.pc[i] = Epc::Ready,
                }
            }
            EA::Lock(i) => {
                let iu = i as usize;
                if s.pc[iu] != Epc::Ready { return None; }
                if locked { if s.lock.is_some() { return None; } t.lock = Some(i); }
                t.pre[iu] = (s.enabled, s.head, s.rev1);
                // reviewed: the state is read under the lock
                if self.d != EDesign::AsBuilt && s.enabled {
                    t.pc[iu] = Epc::Done(s.head >= 1 && s.rev1);
                    if locked { t.lock = None; }
                } else { t.pc[iu] = Epc::Locked; }
            }
            EA::SetState(i) => {
                let iu = i as usize;
                if s.pc[iu] != Epc::Locked { return None; }
                t.enabled = true; // ^IVG.Ledger("meta","state") = "enabled", visible at once
                t.head = 0;       // ^IVG.Ledger("head") = 0
                t.pc[iu] = Epc::Head0;
            }
            EA::Save(i) => {
                let iu = i as usize;
                if s.pc[iu] != Epc::Head0 { return None; }
                if s.rev1 {
                    // %Save of seq 1 fails (unique IdKey): TROLLBACK restores this process's before-images
                    let (e, h, r) = s.pre[iu];
                    t.enabled = e; t.head = h; t.rev1 = r;
                    t.pc[iu] = Epc::Done(false);
                } else {
                    t.rev1 = true; t.head = 1;
                    t.pc[iu] = Epc::Done(true);
                }
                if locked { t.lock = None; }
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<ES>> {
        vec![
            invariant(E_OK, |s: &ES| !s.pc.contains(&Epc::Done(false))),
            invariant(E_CONS, |s: &ES| s.pc.iter().any(|p| matches!(p, Epc::Locked | Epc::Head0))
                || (s.enabled == s.rev1 && (s.head == 1) == s.rev1)),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<ES>> {
        vec![invariant(E_DONE, |s: &ES| s.pc.iter().all(|p| matches!(p, Epc::Done(_))))]
    }
}

fn e_both(s: &ES) -> bool { s.pc == [Epc::Done(true); 2] && s.enabled && s.head == 1 }

// ============================================================================================================== adopt
// F-1103, LED-B1.20 (an adoption records only the unrecorded writes it was built from), LED-B1.21.
// Facts: u = an unrecorded write made while disabled; e = an edge a concurrent commit records.
// as-built: verify(adopt=True) reads the records up to the head, then the stores, then commits the difference with no
// expected head (replay.py:806-857). reviewed (the finding's remedy; decisions.md HD-1101/1401 coherent-cut working
// answers): the adoption carries the verified head as expected head; on stale head it verifies again.
// control: reviewed but the server skips the expected-head check for kind adoption.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum ADesign { AsBuilt, Reviewed, ControlNoCheck }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Apc { Idle, Recs { h: u8, rep: u8 }, Diff { h: u8, diff: u8 }, Done }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct AS { store: u8, rec: [u8; 2], head: u8, ad: [Apc; 2], tries: [u8; 2], committed_e: bool }

#[derive(Clone, Debug)]
pub enum AA { ReadRecords(u8), ReadStore(u8), CommitAdoption(u8), CommitEdge }

pub struct Adopt { pub d: ADesign, pub adopters: u8, pub committer: bool }

const A_ONCE: &str = "LED-B1.20 every fact is recorded at most once";
const A_REPLAY: &str = "when no adoption runs the history replays to the store";
const A_W: &str = "witness: an adoption committed and the history equals the store";
const A_DONE: &str = "AG EF every adoption finishes";
const U: u8 = 1;
const EB: u8 = 2;

impl Model for Adopt {
    type State = AS;
    type Action = AA;
    fn init_states(&self) -> Vec<AS> {
        let mut ad = [Apc::Done; 2];
        for i in 0..self.adopters as usize { ad[i] = Apc::Idle; }
        vec![AS { store: U, rec: [0, 0], head: 1, ad, tries: [0, 0], committed_e: !self.committer }]
    }
    fn actions(&self, _: &AS) -> Vec<AA> {
        vec![AA::ReadRecords(0), AA::ReadRecords(1), AA::ReadStore(0), AA::ReadStore(1), AA::CommitAdoption(0),
             AA::CommitAdoption(1), AA::CommitEdge]
    }
    fn next(&self, s: &AS, a: &AA) -> Option<AS> {
        let mut t = s.clone();
        let replayed = |s: &AS| (if s.rec[0] > 0 { U } else { 0 }) | (if s.rec[1] > 0 { EB } else { 0 });
        match *a {
            AA::ReadRecords(i) => {
                let i = i as usize;
                if s.ad[i] != Apc::Idle { return None; }
                t.ad[i] = Apc::Recs { h: s.head, rep: replayed(s) };
            }
            AA::ReadStore(i) => {
                let i = i as usize;
                let Apc::Recs { h, rep } = s.ad[i] else { return None };
                t.ad[i] = Apc::Diff { h, diff: s.store & !rep };
            }
            AA::CommitAdoption(i) => {
                let i = i as usize;
                let Apc::Diff { h, diff } = s.ad[i] else { return None };
                if diff == 0 { t.ad[i] = Apc::Done; return Some(t); }
                if self.d == ADesign::Reviewed && h != s.head {
                    if s.tries[i] >= 3 { return None; }
                    t.tries[i] += 1;
                    t.ad[i] = Apc::Idle; // StaleHeadError: verify again
                    return Some(t);
                }
                for (k, bit) in [(0usize, U), (1usize, EB)] {
                    if diff & bit != 0 { t.rec[k] = (t.rec[k] + 1).min(3); }
                }
                t.head += 1;
                t.ad[i] = Apc::Done;
            }
            AA::CommitEdge => {
                if s.committed_e { return None; }
                t.committed_e = true;
                t.store |= EB;
                t.rec[1] = (t.rec[1] + 1).min(3);
                t.head += 1;
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<AS>> {
        vec![
            invariant(A_ONCE, |s: &AS| s.rec.iter().all(|&c| c <= 1)),
            invariant(A_REPLAY, |s: &AS| !(s.ad.iter().all(|p| *p == Apc::Done) && s.committed_e)
                || ((s.rec[0] > 0) == (s.store & U != 0) && (s.rec[1] > 0) == (s.store & EB != 0))),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<AS>> {
        vec![invariant(A_DONE, |s: &AS| s.ad.iter().all(|p| *p == Apc::Done) && s.committed_e)]
    }
}

fn a_w(s: &AS) -> bool { s.head >= 3 && s.ad.iter().all(|p| *p == Apc::Done) && s.rec == [1, 1] && s.store == U | EB }

// ============================================================================================================== stats
// F-1102, LED-B13.4 (each outcome adds exactly one to its count), LED-B13.2, LED-P3.
// as-built: one whole row; Bump = %OpenId (no lock) then %Save of the whole row from the opened copy
// (LedgerStats.cls:65-88); a commit inside a caller transaction saves the row and holds its lock until the caller's
// transaction ends (observed live); a Bump that meets that lock times out after 10 s and its status is ignored
// (Ledger.cls:415 `Do ...Bump`, guard.py:82-86). reviewed (finding remedy: $Increment / UPDATE c=c+1): each counter is
// one atomic increment of its own field that never waits on another transaction; the commit counter is counted in
// the commit's transaction and a rollback takes back only its own increment. control: reviewed with Bump split into a
// read and a write again.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum SDesign { AsBuilt, Reviewed, ControlSplitBump }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Apcs { Idle, InTxn { pre_c: u8, pre_r: u8 }, Done }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Bpc { Idle(u8), Read { left: u8, c: u8, r: u8 } }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct SS { row_c: u8, row_r: u8, lock: bool, a: Apcs, b: [Bpc; 2], issued: u8, committed: u8 }

#[derive(Clone, Debug)]
pub enum SA { ACommitInTxn, AEnd(bool), BRead(u8), BSave(u8), BTimeout(u8), BAtomic(u8) }

pub struct Stats { pub d: SDesign, pub with_a: bool, pub bumps: [u8; 2] }

const S_EXACT: &str = "LED-B13.4 when no update is in flight each count equals its outcomes";
const S_W: &str = "witness: two bumps and a kept commit are all counted";
const S_QUIET: &str = "AG EF every counter update finishes";

impl Model for Stats {
    type State = SS;
    type Action = SA;
    fn init_states(&self) -> Vec<SS> {
        vec![SS { row_c: 0, row_r: 0, lock: false, a: if self.with_a { Apcs::Idle } else { Apcs::Done },
                  b: [Bpc::Idle(self.bumps[0]), Bpc::Idle(self.bumps[1])], issued: 0, committed: 0 }]
    }
    fn actions(&self, _: &SS) -> Vec<SA> {
        vec![SA::ACommitInTxn, SA::AEnd(true), SA::AEnd(false), SA::BRead(0), SA::BRead(1), SA::BSave(0), SA::BSave(1),
             SA::BTimeout(0), SA::BTimeout(1), SA::BAtomic(0), SA::BAtomic(1)]
    }
    fn next(&self, s: &SS, a: &SA) -> Option<SS> {
        let mut t = s.clone();
        let atomic = self.d == SDesign::Reviewed;
        match *a {
            SA::ACommitInTxn => {
                if s.a != Apcs::Idle { return None; }
                if self.d == SDesign::AsBuilt {
                    if s.lock { return None; }
                    t.lock = true; // %Save's row lock, held to the end of the caller's transaction
                    t.a = Apcs::InTxn { pre_c: s.row_c, pre_r: s.row_r };
                    t.row_c = s.row_c + 1; // fresh %OpenId inside WriteRevision, whole-row save
                } else {
                    t.a = Apcs::InTxn { pre_c: 0, pre_r: 0 };
                    t.row_c = s.row_c + 1; // atomic increment in the transaction
                }
            }
            SA::AEnd(keep) => {
                let Apcs::InTxn { pre_c, pre_r } = s.a else { return None };
                if keep { t.committed += 1; } else if self.d == SDesign::AsBuilt {
                    t.row_c = pre_c; t.row_r = pre_r; // before-image of the one row node
                } else { t.row_c = s.row_c - 1; }  // takes back only its own increment
                t.lock = false;
                t.a = Apcs::Done;
            }
            SA::BRead(i) => {
                if atomic { return None; }
                let iu = i as usize;
                let Bpc::Idle(left) = s.b[iu] else { return None };
                if left == 0 { return None; }
                t.b[iu] = Bpc::Read { left, c: s.row_c, r: s.row_r };
            }
            SA::BSave(i) => {
                let iu = i as usize;
                let Bpc::Read { left, c, r } = s.b[iu] else { return None };
                if self.d == SDesign::AsBuilt {
                    if s.lock { return None; } // waits for the row lock (or times out, below)
                    t.row_c = c; t.row_r = r + 1; // whole row from the opened copy
                } else {
                    t.row_r = r + 1; // control: its own field, but from a stale read
                }
                t.issued += 1;
                t.b[iu] = Bpc::Idle(left - 1);
            }
            SA::BTimeout(i) => {
                if self.d != SDesign::AsBuilt { return None; }
                let iu = i as usize;
                let Bpc::Read { left, .. } = s.b[iu] else { return None };
                if !s.lock { return None; }
                t.issued += 1; // the outcome happened; its count is dropped (status ignored)
                t.b[iu] = Bpc::Idle(left - 1);
            }
            SA::BAtomic(i) => {
                if !atomic { return None; }
                let iu = i as usize;
                let Bpc::Idle(left) = s.b[iu] else { return None };
                if left == 0 { return None; }
                t.row_r = s.row_r + 1;
                t.issued += 1;
                t.b[iu] = Bpc::Idle(left - 1);
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<SS>> {
        vec![invariant(S_EXACT, |s: &SS| {
            let quiet = !matches!(s.a, Apcs::InTxn { .. }) && s.b.iter().all(|b| matches!(b, Bpc::Idle(_)));
            !quiet || (s.row_r == s.issued && s.row_c == s.committed)
        })]
    }
    fn always_possibly(&self) -> Vec<Invariant<SS>> {
        vec![invariant(S_QUIET, |s: &SS| !matches!(s.a, Apcs::InTxn { .. }) && s.b.iter().all(|b| *b == Bpc::Idle(0)))]
    }
}

fn s_w(s: &SS) -> bool { s.issued == 2 && s.row_r == 2 && s.committed == 1 && s.row_c == 1 && s.a == Apcs::Done }

// ============================================================================================================== guard
// Shared invariant SG (modules 08 and 11): in strict mode every governed write is recorded or refused.
// F-0801 (TTL cache: engine E1 keeps "not strict" up to 5 s after engine E2 turned strict on; guard.py:38-59),
// F-0801/LED-B11.3 (fail-open: a failed probe reads as never-enabled, guard.py:55-56), F-1108 (writers with no guard:
// nodes_edges.py:2301-2339 bulk_delete_adjacency; api/gql/resolvers/mutation.py:23-230).
// reviewed (HD-0801 alternative "fresh checks or fail-closed"; HD-1103 option (c) plus guarding every engine writer):
// every governed engine write reads strict at write time, a failed probe refuses, no unguarded engine writer.
// control: reviewed with fail-open restored.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum GDesign { AsBuilt, Reviewed, ControlFailOpen }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct GS { strict: bool, cache: Option<bool>, age: u8, probe_fails: bool, bad: bool, refused: bool, writes: u8 }

#[derive(Clone, Debug)]
pub enum GA { SetStrict(bool), Tick, ProbeFails(bool), GuardedWrite, CypherWrite, UnguardedWrite, LedgerCommit }

/// `ttl` ticks of cache life (0 = probe every time); `failures` lets the probe fail; `unguarded` adds F-1108's writers.
pub struct Guard { pub d: GDesign, pub ttl: u8, pub failures: bool, pub unguarded: bool }

const G_SG: &str = "SG in strict mode every governed write is recorded or refused";
const G_W_REFUSED: &str = "witness: a guarded write is refused in strict mode";
const G_OFF: &str = "AG EF strict mode can be turned off and writes land again";

impl Guard {
    fn check(&self, s: &GS, t: &mut GS) -> bool {
        // returns true when the guard refuses
        let fresh = self.d != GDesign::AsBuilt;
        if !fresh {
            if let Some(v) = s.cache { if s.age < self.ttl { return v; } }
        }
        let v = if s.probe_fails { self.d == GDesign::Reviewed } else { s.strict };
        if !fresh { t.cache = Some(if s.probe_fails { false } else { s.strict }); t.age = 0; }
        v
    }
}

impl Model for Guard {
    type State = GS;
    type Action = GA;
    fn init_states(&self) -> Vec<GS> {
        vec![GS { strict: false, cache: None, age: 0, probe_fails: false, bad: false, refused: false, writes: 0 }]
    }
    fn actions(&self, _: &GS) -> Vec<GA> {
        vec![GA::SetStrict(true), GA::SetStrict(false), GA::Tick, GA::ProbeFails(true), GA::ProbeFails(false),
             GA::GuardedWrite, GA::CypherWrite, GA::UnguardedWrite, GA::LedgerCommit]
    }
    fn next(&self, s: &GS, a: &GA) -> Option<GS> {
        let mut t = s.clone();
        match *a {
            GA::SetStrict(v) => { if s.strict == v { return None; } t.strict = v; } // engine E2: refreshes E2 only
            GA::Tick => { if s.age >= self.ttl { return None; } t.age += 1; }
            GA::ProbeFails(v) => { if !self.failures || s.probe_fails == v { return None; } t.probe_fails = v; }
            GA::GuardedWrite | GA::CypherWrite => {
                if s.writes >= 3 { return None; }
                t.writes += 1;
                if self.check(s, &mut t) { t.refused = true; } else if s.strict { t.bad = true; }
            }
            GA::UnguardedWrite => {
                if !self.unguarded || s.writes >= 3 { return None; }
                t.writes += 1;
                let guarded = self.d != GDesign::AsBuilt;
                if guarded && self.check(s, &mut t) { t.refused = true; } else if s.strict { t.bad = true; }
            }
            GA::LedgerCommit => { if s.writes >= 3 { return None; } t.writes += 1; } // recorded: always fine
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<GS>> { vec![invariant(G_SG, |s: &GS| !s.bad)] }
    fn always_possibly(&self) -> Vec<Invariant<GS>> {
        vec![invariant(G_OFF, |s: &GS| !s.strict || s.writes >= 3)]
    }
}

fn g_refused(s: &GS) -> bool { s.refused && s.strict }

// ============================================================================================================== retry
// F-1101 (core, no erasure), F-1106; LED-B10.5 (a replayed commit changes nothing, post-commit properties too),
// LED-B4.7.8 (a replayed commit gives back the first commit's statement ids), LED-B4.7.
// as-built: client.py:430-435 applies post-commit properties after any successful answer, replayed or not; the replay
// branch answers RevisionResponse(seq, 1, {}) (Ledger.cls:459-461). reviewed (HD-1105 supported: idempotent retries;
// HD-1305): a replay applies no post-commit property and answers the first commit's statement ids.
// control: reviewed with the post-commit properties applied on replay again.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum RDesign { AsBuilt, Reviewed, ControlReapply }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct RS { bound: bool, node: bool, prop: u8, rec_prop: u8, governed: bool, retries: u8,
                answer: Option<(bool, Option<u8>)> }

#[derive(Clone, Debug)]
pub enum RA { Commit, GovernedSet, Retry }

pub struct Retry { pub d: RDesign }

const R_NOOP: &str = "LED-B10.5 a replayed commit changes nothing";
const R_STMT: &str = "LED-B4.7.8 a replayed commit answers the first commit's statement ids";
const R_GOV: &str = "a governed value is the store's value until the next governed change";
const R_W: &str = "witness: a retry was replayed after a later governed change";

impl Model for Retry {
    type State = RS;
    type Action = RA;
    fn init_states(&self) -> Vec<RS> {
        vec![RS { bound: false, node: false, prop: 0, rec_prop: 0, governed: false, retries: 0, answer: None }]
    }
    fn actions(&self, _: &RS) -> Vec<RA> { vec![RA::Commit, RA::GovernedSet, RA::Retry] }
    fn next(&self, s: &RS, a: &RA) -> Option<RS> {
        let mut t = s.clone();
        match a {
            RA::Commit => {
                if s.bound { return None; }
                t.bound = true; t.node = true; t.prop = 1; // post-commit property V1 (unrecorded)
                t.answer = Some((false, Some(1)));
            }
            RA::GovernedSet => {
                if !s.node || s.governed { return None; }
                t.governed = true; t.prop = 2; t.rec_prop = 2;
                t.answer = None;
            }
            RA::Retry => {
                if !s.bound || s.retries >= 2 { return None; }
                t.retries += 1;
                let ids = if self.d == RDesign::AsBuilt { None } else { Some(1) };
                t.answer = Some((true, ids));
                if self.d != RDesign::Reviewed { t.prop = 1; }
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<RS>> {
        vec![invariant(R_GOV, |s: &RS| !s.governed || s.prop == s.rec_prop)]
    }
    fn action_properties(&self) -> Vec<ActionProperty<RS, RA>> {
        vec![
            action_property(R_NOOP, |s: &RS, a: &RA, t: &RS| !matches!(a, RA::Retry)
                || (s.node == t.node && s.prop == t.prop && s.bound == t.bound)),
            action_property(R_STMT, |_: &RS, a: &RA, t: &RS| !matches!(a, RA::Retry)
                || t.answer.is_some_and(|(_, ids)| ids == Some(1))),
        ]
    }
}

fn r_w(s: &RS) -> bool { s.governed && s.retries >= 1 && s.prop == 2 }

// ============================================================================================================= commit
// Commit core: LED-B4.3 (no commit builds on a head whose transaction has not ended), LED-B4.11.2 (one chain, no
// gaps), LED-B4.7.5 (one revision per retry key), LED-B9.4/P-1102 (inside a caller transaction the head lock is held
// until the caller ends). Process 1 commits inside a caller transaction (4.7.0 nesting, client.py:381-400) and the
// caller then commits or rolls back; process 2 commits plainly; both may use the same retry key.
// as-built: Lock -^IVG.Ledger("head") inside the transaction is deferred to the outermost end (Ledger.cls:388-410);
// expected to pass. control: the unlock takes effect at once (the head lock is free while the caller can still roll
// back). There is no separate reviewed design: the pin's design is the one checked.

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum CDesign { AsBuilt, ControlImmediateUnlock }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum C1 { Idle, Locked, Written { pre_head: u8, pre_key: Option<u8> }, InnerDone { pre_head: u8, pre_key: Option<u8> }, Done }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum C2 { Idle, Locked, Done }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct CS { head: u8, revs: u8, key: Option<u8>, lock: Option<u8>, p1: C1, p2: C2, built_on_open: bool, same_key: bool }

#[derive(Clone, Debug)]
pub enum CA { P1Lock, P1Write, P1Inner, P1Caller(bool), P2Lock, P2Commit }

pub struct Commit { pub d: CDesign }

const C_CHAIN: &str = "LED-B4.11.2 revisions form one chain 1..head with no gaps";
const C_OPEN: &str = "LED-B4.3 no commit builds on a head whose transaction has not ended";
const C_KEY: &str = "LED-B4.7.5 a bound retry key names a kept revision";
const C_W_REPLAY: &str = "witness: the second process got the first revision back (replay)";
const C_W_ROLLBACK: &str = "witness: the caller rolled back and the other commit landed after it";
const C_DONE: &str = "AG EF both commits finish";

impl Model for Commit {
    type State = CS;
    type Action = CA;
    fn init_states(&self) -> Vec<CS> {
        [false, true].iter().map(|&same_key| CS { head: 0, revs: 0, key: None, lock: None, p1: C1::Idle, p2: C2::Idle,
            built_on_open: false, same_key }).collect()
    }
    fn actions(&self, _: &CS) -> Vec<CA> {
        vec![CA::P1Lock, CA::P1Write, CA::P1Inner, CA::P1Caller(true), CA::P1Caller(false), CA::P2Lock, CA::P2Commit]
    }
    fn next(&self, s: &CS, a: &CA) -> Option<CS> {
        let mut t = s.clone();
        match *a {
            CA::P1Lock => { if s.p1 != C1::Idle || s.lock.is_some() { return None; } t.lock = Some(1); t.p1 = C1::Locked; }
            CA::P1Write => {
                if s.p1 != C1::Locked { return None; }
                if s.key.is_some() { t.p1 = C1::Done; t.lock = None; return Some(t); } // replay of p2's key
                let seq = s.head + 1;
                t.p1 = C1::Written { pre_head: s.head, pre_key: s.key };
                t.head = seq; t.revs |= 1 << (seq - 1); t.key = Some(seq);
            }
            CA::P1Inner => {
                let C1::Written { pre_head, pre_key } = s.p1 else { return None };
                t.p1 = C1::InnerDone { pre_head, pre_key };
                if self.d == CDesign::ControlImmediateUnlock { t.lock = None; }
            }
            CA::P1Caller(keep) => {
                let C1::InnerDone { pre_head, pre_key } = s.p1 else { return None };
                if !keep {
                    // rollback restores this process's before-images of the head and its key; its revision row goes
                    let seq = pre_head + 1;
                    t.revs &= !(1 << (seq - 1));
                    t.head = pre_head;
                    if s.key == Some(seq) { t.key = pre_key; }
                }
                if t.lock == Some(1) { t.lock = None; }
                t.p1 = C1::Done;
            }
            CA::P2Lock => { if s.p2 != C2::Idle || s.lock.is_some() { return None; } t.lock = Some(2); t.p2 = C2::Locked; }
            CA::P2Commit => {
                if s.p2 != C2::Locked { return None; }
                if s.same_key && s.key.is_some() {
                    // replay: answer the bound revision, write nothing
                } else {
                    if matches!(s.p1, C1::Written { .. } | C1::InnerDone { .. }) { t.built_on_open = true; }
                    let seq = s.head + 1;
                    t.head = seq; t.revs |= 1 << (seq - 1);
                    if s.same_key { t.key = Some(seq); }
                }
                t.lock = None; t.p2 = C2::Done;
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<CS>> {
        vec![
            invariant(C_CHAIN, |s: &CS| s.revs == ((1u16 << s.head) - 1) as u8),
            invariant(C_OPEN, |s: &CS| !s.built_on_open),
            invariant(C_KEY, |s: &CS| s.key.is_none_or(|k| s.revs & (1 << (k - 1)) != 0)),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<CS>> {
        vec![invariant(C_DONE, |s: &CS| s.p1 == C1::Done && s.p2 == C2::Done)]
    }
}

fn c_replay(s: &CS) -> bool { s.same_key && s.p2 == C2::Done && s.p1 != C1::Idle && s.revs == 1 && s.head == 1 && s.lock.is_none() }
fn c_rollback(s: &CS) -> bool { s.p1 == C1::Done && s.p2 == C2::Done && s.head == 1 && s.revs == 1 && !s.same_key }

// ============================================================================================================= checks
fn ex<M: Model>(m: &M) -> Report<M::State, M::Action> { explore(m, limits()) }

pub fn checks() -> Vec<(&'static str, Box<dyn Fn() -> Outcome>)> {
    vec![
        // enable
        check("m11-enable-as-built", || judge("m11-enable-as-built", "11", "enable", "as-built", Expect::Violation(E_OK),
            "F-1104; LED-B1.12, LED-P6", ex(&Only::new(Enable { d: EDesign::AsBuilt }, &[E_OK])), show_debug)),
        check("m11-enable-as-built-consistency", || judge("m11-enable-as-built-consistency", "11", "enable", "as-built", Expect::Pass,
            "LED-B1.7 holds at the pin: the failed second genesis rolls back (F-1104 'ledger itself intact')",
            ex(&Only::new(Enable { d: EDesign::AsBuilt }, &[E_CONS, E_DONE])), show_debug)),
        check("m11-enable-reviewed", || judge("m11-enable-reviewed", "11", "enable", "reviewed", Expect::Pass,
            "F-1104 remedy: lock, then read state; LED-B1.12, LED-B1.7, AG EF done", ex(&Enable { d: EDesign::Reviewed }), show_debug)),
        check("m11-enable-control-nolock", || judge("m11-enable-control-nolock", "11", "enable", "control", Expect::Violation(E_OK),
            "mutant: reviewed Enable without the head lock", ex(&Only::new(Enable { d: EDesign::ControlNoLock }, &[E_OK])), show_debug)),
        check("m11-enable-positive", || judge("m11-enable-positive", "11", "enable", "positive", Expect::Violation(E_W_BOTH),
            "sharpness: both concurrent enables answer and the ledger is enabled at head 1",
            ex(&Only::new(Enable { d: EDesign::Reviewed }, &[]).witness(E_W_BOTH, e_both)), show_debug)),
        // adopt
        check("m11-adopt-as-built-commit", || judge("m11-adopt-as-built-commit", "11", "adopt", "as-built", Expect::Violation(A_ONCE),
            "F-1103 (a commit lands between the record read and the store read); LED-B1.20",
            ex(&Only::new(Adopt { d: ADesign::AsBuilt, adopters: 1, committer: true }, &[A_ONCE])), show_debug)),
        check("m11-adopt-as-built-two-enables", || judge("m11-adopt-as-built-two-enables", "11", "adopt", "as-built", Expect::Violation(A_ONCE),
            "F-1103 (two concurrent re-enables each adopt); LED-B1.20, LED-B1.21",
            ex(&Only::new(Adopt { d: ADesign::AsBuilt, adopters: 2, committer: false }, &[A_ONCE])), show_debug)),
        check("m11-adopt-reviewed", || judge("m11-adopt-reviewed", "11", "adopt", "reviewed", Expect::Pass,
            "F-1103 remedy: adoption carries the verified head; LED-B1.20, replay = store, AG EF done",
            ex(&Adopt { d: ADesign::Reviewed, adopters: 2, committer: true }), show_debug)),
        check("m11-adopt-control-nocheck", || judge("m11-adopt-control-nocheck", "11", "adopt", "control", Expect::Violation(A_ONCE),
            "mutant: reviewed with the server's expected-head check skipped for adoptions",
            ex(&Adopt { d: ADesign::ControlNoCheck, adopters: 2, committer: true }), show_debug)),
        check("m11-adopt-positive", || judge("m11-adopt-positive", "11", "adopt", "positive", Expect::Violation(A_W),
            "sharpness: an adoption and a concurrent commit both land, history = store",
            ex(&Only::new(Adopt { d: ADesign::Reviewed, adopters: 2, committer: true }, &[]).witness(A_W, a_w)), show_debug)),
        // stats
        check("m11-stats-as-built-rmw", || judge("m11-stats-as-built-rmw", "11", "stats", "as-built", Expect::Violation(S_EXACT),
            "F-1102 (two Bumps read-modify-write the row); LED-B13.4, LED-P3",
            ex(&Only::new(Stats { d: SDesign::AsBuilt, with_a: false, bumps: [1, 1] }, &[S_EXACT])), show_debug)),
        check("m11-stats-as-built-caller-txn", || judge("m11-stats-as-built-caller-txn", "11", "stats", "as-built", Expect::Violation(S_EXACT),
            "F-1102 (a Bump meets the row lock of a caller transaction and times out; or saves a stale whole row)",
            ex(&Only::new(Stats { d: SDesign::AsBuilt, with_a: true, bumps: [1, 0] }, &[S_EXACT])), show_debug)),
        check("m11-stats-reviewed", || judge("m11-stats-reviewed", "11", "stats", "reviewed", Expect::Pass,
            "F-1102 remedy: atomic per-counter increments; LED-B13.4, AG EF quiet",
            ex(&Stats { d: SDesign::Reviewed, with_a: true, bumps: [2, 1] }), show_debug)),
        check("m11-stats-control-split", || judge("m11-stats-control-split", "11", "stats", "control", Expect::Violation(S_EXACT),
            "mutant: reviewed with Bump split into read and write", ex(&Stats { d: SDesign::ControlSplitBump, with_a: true, bumps: [1, 1] }), show_debug)),
        check("m11-stats-positive", || judge("m11-stats-positive", "11", "stats", "positive", Expect::Violation(S_W),
            "sharpness: concurrent bumps and a kept commit are all counted",
            ex(&Only::new(Stats { d: SDesign::Reviewed, with_a: true, bumps: [1, 1] }, &[]).witness(S_W, s_w)), show_debug)),
        // guard (shared invariant SG with module 08)
        check("m11-guard-as-built-ttl", || judge("m11-guard-as-built-ttl", "11", "guard", "as-built", Expect::Violation(G_SG),
            "F-0801 (TTL window); LED-B11, LED-B11.1, LED-B11.2; SG",
            ex(&Guard { d: GDesign::AsBuilt, ttl: 2, failures: false, unguarded: false }), show_debug)),
        check("m11-guard-as-built-failopen", || judge("m11-guard-as-built-failopen", "11", "guard", "as-built", Expect::Violation(G_SG),
            "F-0801 (fail-open probe); LED-B11.3; SG", ex(&Guard { d: GDesign::AsBuilt, ttl: 0, failures: true, unguarded: false }), show_debug)),
        check("m11-guard-as-built-unguarded", || judge("m11-guard-as-built-unguarded", "11", "guard", "as-built", Expect::Violation(G_SG),
            "F-1108 (bulk_delete_adjacency, GraphQL mutations); LED-B11.5; SG",
            ex(&Guard { d: GDesign::AsBuilt, ttl: 0, failures: false, unguarded: true }), show_debug)),
        check("m11-guard-reviewed", || judge("m11-guard-reviewed", "11", "guard", "reviewed", Expect::Pass,
            "HD-0801/HD-1103 alternatives: fresh check, fail closed, every engine writer guarded; SG, AG EF strict off",
            ex(&Guard { d: GDesign::Reviewed, ttl: 2, failures: true, unguarded: true }), show_debug)),
        check("m11-guard-control-failopen", || judge("m11-guard-control-failopen", "11", "guard", "control", Expect::Violation(G_SG),
            "mutant: reviewed guard failing open again", ex(&Guard { d: GDesign::ControlFailOpen, ttl: 2, failures: true, unguarded: true }), show_debug)),
        check("m11-guard-positive", || judge("m11-guard-positive", "11", "guard", "positive", Expect::Violation(G_W_REFUSED),
            "sharpness: a guarded write is refused in strict mode",
            ex(&Only::new(Guard { d: GDesign::Reviewed, ttl: 2, failures: true, unguarded: true }, &[]).witness(G_W_REFUSED, g_refused)), show_debug)),
        // retry
        check("m11-retry-as-built-pcp", || judge("m11-retry-as-built-pcp", "11", "retry", "as-built", Expect::Violation(R_NOOP),
            "F-1101 core; LED-B10.5", ex(&Only::new(Retry { d: RDesign::AsBuilt }, &[R_NOOP])), show_debug)),
        check("m11-retry-as-built-governed", || judge("m11-retry-as-built-governed", "11", "retry", "as-built", Expect::Violation(R_GOV),
            "F-1101: a replay overwrites a later governed set_prop (verify diverges)", ex(&Only::new(Retry { d: RDesign::AsBuilt }, &[R_GOV])), show_debug)),
        check("m11-retry-as-built-stmt-ids", || judge("m11-retry-as-built-stmt-ids", "11", "retry", "as-built", Expect::Violation(R_STMT),
            "F-1106; LED-B4.7.8", ex(&Only::new(Retry { d: RDesign::AsBuilt }, &[R_STMT])), show_debug)),
        check("m11-retry-reviewed", || judge("m11-retry-reviewed", "11", "retry", "reviewed", Expect::Pass,
            "HD-1105/HD-1305: a replay applies nothing and answers the first stmt ids", ex(&Retry { d: RDesign::Reviewed }), show_debug)),
        check("m11-retry-control-reapply", || judge("m11-retry-control-reapply", "11", "retry", "control", Expect::Violation(R_NOOP),
            "mutant: reviewed but post-commit properties applied on replay", ex(&Retry { d: RDesign::ControlReapply }), show_debug)),
        check("m11-retry-positive", || judge("m11-retry-positive", "11", "retry", "positive", Expect::Violation(R_W),
            "sharpness: a replay after a later governed change is reachable",
            ex(&Only::new(Retry { d: RDesign::Reviewed }, &[]).witness(R_W, r_w)), show_debug)),
        // commit core
        check("m11-commit-as-built", || judge("m11-commit-as-built", "11", "commit", "as-built", Expect::Pass,
            "LED-B4.3, LED-B4.11.2, LED-B4.7.5, LED-B9.4 hold with the deferred unlock; AG EF done",
            ex(&Commit { d: CDesign::AsBuilt }), show_debug)),
        check("m11-commit-control-unlock", || judge("m11-commit-control-unlock", "11", "commit", "control", Expect::Violation(C_OPEN),
            "mutant: head lock released while the caller transaction can still roll back",
            ex(&Commit { d: CDesign::ControlImmediateUnlock }), show_debug)),
        check("m11-commit-control-unlock-chain", || judge("m11-commit-control-unlock-chain", "11", "commit", "control", Expect::Violation(C_CHAIN),
            "mutant (chain only): a caller rollback under an immediate unlock leaves a gap",
            ex(&Only::new(Commit { d: CDesign::ControlImmediateUnlock }, &[C_CHAIN])), show_debug)),
        check("m11-commit-positive-replay", || judge("m11-commit-positive-replay", "11", "commit", "positive", Expect::Violation(C_W_REPLAY),
            "sharpness: a same-key commit is replayed", ex(&Only::new(Commit { d: CDesign::AsBuilt }, &[]).witness(C_W_REPLAY, c_replay)), show_debug)),
        check("m11-commit-positive-rollback", || judge("m11-commit-positive-rollback", "11", "commit", "positive", Expect::Violation(C_W_ROLLBACK),
            "sharpness: a caller rollback followed by the other commit is reachable",
            ex(&Only::new(Commit { d: CDesign::AsBuilt }, &[]).witness(C_W_ROLLBACK, c_rollback)), show_debug)),
    ]
}
