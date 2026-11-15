//! M2, concurrency: two redaction targets, two redacting processes, a ledger committer, a graph eraser and a
//! ledger-bypassing content writer, every one of them with its own open transaction where the product has one.
//!
//! World. Named graph G1 holds tenant A, named graph G2 tenant B; the targets are A = (G1, no prefix) and
//! B = (G2, no prefix). Edges a0 (G1, committed by the genesis-like revision r0 with statement 1), a1 (G1, created
//! by changeset CA), b0 (G2, committed by r0 with statement 2). r0 spans both tenants (Decision 2). Records are
//! relationship records (create_rel / delete_rel) carrying their edge's graph; for these record kinds and graph
//! targets the three targeting predicates coincide (Matches: record graph; LiveRows: rows of the graph;
//! DropStatements: statements of the graph) -- where they differ is machine M1's subject.
//!
//! What this machine represents that the original redaction/erasure machines collapsed:
//! - the eraser's EraseGraph as separate steps of one open transaction (Eraser.cls:47-261): E1 DELETEs the graph's
//!   rows (the adjacency functional index removes each row's ^KG entry with it), E2 Adjacency.RemoveGraph kills
//!   the graph's ^KG subtree (Adjacency.cls:428-447), E3 EraseLedgerFor kills every ("stmt") entry of the graph
//!   and its ("tuple") entry (Eraser.cls:1117-1144), E4 TCOMMIT; or a process stop that rolls everything back;
//!   no head lock at the pin;
//! - dirty reads (IRIS contract "Visibility": globals unisolated, SQL READ UNCOMMITTED) and value-based rollback
//!   (contract "Rollback over another's write": a rollback does not overwrite a node another process changed
//!   after this process wrote it), via per-process undo logs {item, before, after};
//! - row locks (contract "Row locks": a DELETE waits for a row another open transaction inserted; the insert of a
//!   key another open transaction deleted is left to the contract's Freedom and modelled as a wait);
//! - Redact's two opening reads as separate unlocked steps (LedgerRedact.cls:202-205 marker, 206-210 LiveRows),
//!   batches (one record each: batch_size=1 is a legal configuration) under the head lock that set the marker on
//!   their first tombstone only if none exists (322-324), shared counters under the one marker (342-344),
//!   Final (409-442) that re-checks LiveRows, drops statements (446-471), writes the audit with ITS digest and the
//!   shared count, and kills the whole marker subtree, also with no marker (no audit when no marker and no
//!   statement, 418) or with another target's marker; process stop and resume (a resumed call restarts its scan
//!   from the first record, 214); optional pacing (max_batches > 0: a call stops after `pace` records);
//! - the ledger commit (Ledger.cls:400-528) as one open transaction under the head lock: apply writes the row,
//!   adjacency, statement and tuple entries (LedgerApply AllocStmt 160-169, DeleteRelInternal 652-693), then
//!   BlocksCommit (LedgerRedact.cls:258-269) may refuse it, then commit or rollback; or a process stop;
//! - a ledger-bypassing writer W (any of the 25 census writers: EdgeScan bulk ingest, FHIRGraph, TemporalPolicy,
//!   Adjacency.RetractTemporalRow(s), the SQL store, nodes_edges, schema inference): inserts or deletes a content
//!   row of either graph in its own transaction, during any redaction phase, never consults the marker, takes no
//!   head lock at the pin (mode `NonSerializing`) or serializes like a ledger write (`Serializing`, the HD-1201
//!   working assumption "same-target writes serialize").
//!
//! Designs. `AsBuilt` as above. `Reviewed` = HD-1201 + HD-1301 working answers: the eraser holds the head lock from
//! E1 to E4; Start checks the marker and liveness and sets its marker in one step under the head lock; batches and
//! Final run only under their own target's marker; counters are per target.
use explorer::*;

pub const NE: usize = 3;
pub const ENAME: [&str; NE] = ["a0", "a1", "b0"];
pub const TNAME: [&str; 2] = ["A", "B"];
pub fn g_of(e: usize) -> u8 { if e < 2 { 0 } else { 1 } }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed }

/// Model mutants (controls and progress-only mutants of the reviewed design).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Mutant {
    None,
    /// control: the audit takes the other target's counter
    CountersSwapped,
    /// control: a batch may tombstone under another target's marker (marker-ownership check dropped)
    BatchUnderOtherMarker,
    /// control: the eraser takes no head lock (HD-1201 dropped)
    EraseNoHeadLock,
    /// control: the opening check is unlocked and the marker comes with the first tombstone (HD-1301 dropped)
    UnlockedStart,
    /// progress-only: Final writes the audit and resets the counters but never removes the marker
    FinalKeepsMarker,
    /// control: Final trusts the end of the scan it saw earlier (the pin's behaviour), instead of re-checking
    /// under the lock that no record was appended since its last batch
    FinalTrustsOldScan,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Bypass { Off, NonSerializing, Serializing }

#[derive(Clone, Copy, Debug)]
pub struct Cfg {
    pub design: Design,
    pub mutant: Mutant,
    pub bypass: Bypass,
    /// the eraser / committer may be stopped mid-transaction (rollback)
    pub estop: bool,
    pub pstop: bool,
    /// Bounds. Commits and bypass writes (which create new content) are bounded by guards; erasures and Redact calls
    /// are not counted when their bound is 0 (the default), so the explored graph is finite and exact: no state is cut
    /// by a bound, and AG EF is decided without the explorer's frontier rule (states cut by a bound count as able to
    /// reach the goal), which would otherwise let any bounded action "rescue" a stuck state.
    /// 0: calls (Redact entries) are not counted, so resumes are unbounded and a non-progress cycle stays inside the
    /// bounds (the explorer counts states cut by a bound as able to reach the goal)
    /// records a call may scan before it pauses (max_batches > 0 with batch_size 1); 0 = unpaced
    pub pace: u8,
    pub max_erases: u8,
    pub max_commits: u8,
    pub max_starts: u8,
    pub max_writes: u8,
}

impl Cfg {
    pub fn new(design: Design) -> Cfg {
        Cfg { design, mutant: Mutant::None, bypass: Bypass::Off, estop: true, pstop: true, pace: 0,
              max_erases: 0, max_commits: 2, max_starts: 0, max_writes: 2 }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Item { Row(u8), Adj(u8), Stmt(u8), Tuple(u8), Next }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Undo { pub item: Item, pub before: u8, pub after: u8 }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rec {
    Live { e: u8, inc: u8, del: bool },
    Tomb { e: u8, inc: u8, del: bool },
    Audit { t: u8, n: u8 },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Rev { pub recs: Vec<Rec>, pub text: bool, pub key: u8 }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Run {
    Idle,
    /// as-built: the marker check passed; LiveRows not yet read
    Checked(u8),
    Scan { t: u8, i: u8, j: u8, made: bool, done: bool, scanned: u8 },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Ep { Idle, Open { g: u8, step: u8 } }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Pp { Idle, Open { c: u8, ok: bool, inc: u8 } }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Wp { Idle, Open { e: u8, ins: bool } }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Who { E, P, W, Committed }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    /// content rows: 0 absent, else the live incarnation
    pub row: [u8; NE],
    /// ^KG adjacency entries (bit per edge)
    pub adj: u8,
    /// ^IVG.Ledger("stmt", id) for id 1..=4: 0 absent, else 1 + 2*edge + closed
    pub stmt: [u8; 4],
    pub next: u8,
    /// ^IVG.Ledger("tuple", edge) = statement id (0 none)
    pub tuple: [u8; NE],
    pub revs: Vec<Rev>,
    /// ^IVG.Ledger("idem", key) = revision index + 1 (keys 0: r0, 1: CA, 2: DA)
    pub idem: [u8; 3],
    pub idem_red: u8,
    pub red_rev: u8,
    pub marker: Option<u8>,
    /// ("redacting","n","records"): the pin keeps one (index 0); the reviewed design one per target
    pub count: [u8; 2],
    pub runs: [Run; 2],
    pub e: Ep,
    pub e_undo: Vec<Undo>,
    pub p: Pp,
    pub p_undo: Vec<Undo>,
    pub w: Wp,
    pub w_undo: Vec<Undo>,
    // ghosts
    pub inc_next: [u8; NE],
    /// the live incarnation of the edge was saved by the ledger
    pub recorded: u8,
    pub tombs_of: [u8; 2],
    pub audited: [u8; 2],
    /// targets erased (committed) and not yet completely redacted
    pub pending: u8,
    pub unrecorded: bool,
    pub committed: u8,
    pub starts: u8,
    pub erases: u8,
    pub commits: u8,
    pub writes: u8,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum A {
    /// as-built opening read 1 (marker) of process p for target t; reviewed: the locked Start
    Read1(u8, u8),
    /// as-built opening read 2 (LiveRows, unlocked)
    Read2(u8),
    Batch(u8),
    Final(u8),
    Stop(u8),
    E1(u8),
    E2,
    E3,
    E4,
    EStop,
    /// ledger commit of changeset c (0: CA create a1 in G1; 1: DA delete a0 in G1)
    PBegin(u8),
    PEnd,
    PStop,
    /// bypass write: insert (true) or delete (false) edge e's row
    WBegin(u8, bool),
    WEnd,
    WStop,
}

impl S {
    fn get(&self, it: Item) -> u8 {
        match it {
            Item::Row(e) => self.row[e as usize],
            Item::Adj(e) => (self.adj >> e) & 1,
            Item::Stmt(id) => self.stmt[id as usize - 1],
            Item::Tuple(e) => self.tuple[e as usize],
            Item::Next => self.next,
        }
    }
    fn set(&mut self, it: Item, v: u8) {
        match it {
            Item::Row(e) => self.row[e as usize] = v,
            Item::Adj(e) => if v == 1 { self.adj |= 1 << e } else { self.adj &= !(1 << e) },
            Item::Stmt(id) => self.stmt[id as usize - 1] = v,
            Item::Tuple(e) => self.tuple[e as usize] = v,
            Item::Next => self.next = v,
        }
    }
    fn write(&mut self, who: Who, it: Item, v: u8) {
        let before = self.get(it);
        if before == v { return; }
        let u = Undo { item: it, before, after: v };
        match who {
            Who::E => self.e_undo.push(u),
            Who::P => self.p_undo.push(u),
            Who::W => self.w_undo.push(u),
            Who::Committed => {}
        }
        self.set(it, v);
    }
    /// Value-based rollback (IRIS contract: a node another process changed since is left alone).
    fn rollback(&mut self, who: Who) {
        let log = match who { Who::E => std::mem::take(&mut self.e_undo), Who::P => std::mem::take(&mut self.p_undo),
                              Who::W => std::mem::take(&mut self.w_undo), Who::Committed => vec![] };
        for u in log.iter().rev() {
            if self.get(u.item) == u.after { self.set(u.item, u.before); }
        }
    }
    fn logs(&self) -> [(Who, &Vec<Undo>); 3] { [(Who::E, &self.e_undo), (Who::P, &self.p_undo), (Who::W, &self.w_undo)] }
    /// Another open transaction holds a row lock on edge e's row (it inserted or deleted it).
    fn row_locked_by_other(&self, e: usize, me: Who) -> bool {
        self.logs().iter().any(|(w, l)| *w != me && l.iter().any(|u| u.item == Item::Row(e as u8)))
    }
    /// Another open transaction inserted a row of graph g (a DELETE of the graph waits for it).
    fn uncommitted_insert_in(&self, g: u8, me: Who) -> bool {
        self.logs().iter().any(|(w, l)| *w != me && l.iter().any(|u| match u.item {
            Item::Row(e) => g_of(e as usize) == g && u.before == 0, _ => false }))
    }
    pub fn live(&self, t: u8) -> bool { (0..NE).any(|e| g_of(e) == t && self.row[e] != 0) }
    pub fn quiescent(&self) -> bool { self.e == Ep::Idle && self.p == Pp::Idle && self.w == Wp::Idle }
    pub fn runs_idle(&self) -> bool { self.runs.iter().all(|r| *r == Run::Idle) }
    pub fn settled(&self) -> bool { self.marker.is_none() && self.runs_idle() && self.quiescent() }
    pub fn stmt_of(v: u8) -> Option<(usize, bool)> { if v == 0 { None } else { Some((((v - 1) / 2) as usize, (v - 1) % 2 == 1)) } }
    fn norm(&self, mut i: u8, mut j: u8) -> (u8, u8, bool) {
        while (i as usize) < self.revs.len() && (j as usize) >= self.revs[i as usize].recs.len() { i += 1; j = 0; }
        (i, j, (i as usize) >= self.revs.len())
    }
    /// What verify() replays: the relationships of the live records, in order.
    pub fn replay(&self) -> u8 {
        let mut m = 0u8;
        for r in &self.revs {
            for x in &r.recs {
                if let Rec::Live { e, del, .. } = *x { if del { m &= !(1 << e) } else { m |= 1 << e } }
            }
        }
        m
    }
    pub fn rows(&self) -> u8 { (0..NE).filter(|&e| self.row[e] != 0).fold(0, |m, e| m | 1 << e) }
}

pub struct M2 { pub cfg: Cfg }

impl M2 {
    pub fn new(cfg: Cfg) -> M2 { M2 { cfg } }
    fn reviewed(&self) -> bool { self.cfg.design == Design::Reviewed }
    fn e_locks(&self) -> bool { self.reviewed() && self.cfg.mutant != Mutant::EraseNoHeadLock }
    fn locked_start(&self) -> bool { self.reviewed() && self.cfg.mutant != Mutant::UnlockedStart }
    fn shared_counters(&self) -> bool { !self.reviewed() }
    /// Reviewed: the scan follows the tail (as the original L2 machine): Final only when the cursor is at the current
    /// end of the ledger, a batch whenever it is not. As built: the call runs Final once a batch has passed the last
    /// record that existed then (LedgerRedact.cls:222-231), whatever was appended before Final takes the lock.
    fn at_end(&self, s: &S, i: u8, j: u8, done: bool) -> bool {
        if self.reviewed() && self.cfg.mutant != Mutant::FinalTrustsOldScan { s.norm(i, j).2 } else { done }
    }
    fn head_free(&self, s: &S) -> bool {
        !(matches!(s.p, Pp::Open { .. })
            || (matches!(s.e, Ep::Open { .. }) && self.e_locks())
            || (matches!(s.w, Wp::Open { .. }) && self.cfg.bypass == Bypass::Serializing))
    }
    fn tombstone(&self, s: &mut S, i: usize, j: usize, t: u8) {
        if let Rec::Live { e, inc, del } = s.revs[i].recs[j] { s.revs[i].recs[j] = Rec::Tomb { e, inc, del }; }
        if s.marker.is_none() { s.marker = Some(t); }
        if s.red_rev & (1 << i) == 0 {
            s.revs[i].text = false;
            let k = s.revs[i].key;
            if k != 0 {
                s.idem[k as usize - 1] = 0;
                s.idem_red |= 1 << (k - 1);
                s.revs[i].key = 0;
            }
            s.red_rev |= 1 << i;
        }
        let ci = if self.shared_counters() { 0 } else { t as usize };
        s.count[ci] += 1;
        s.tombs_of[t as usize] += 1;
    }
}

impl Model for M2 {
    type State = S;
    type Action = A;

    fn init_states(&self) -> Vec<S> {
        vec![S {
            row: [1, 0, 1], adj: 0b101, stmt: [1, 5, 0, 0], next: 3, tuple: [1, 0, 2],
            revs: vec![Rev { recs: vec![Rec::Live { e: 0, inc: 1, del: false }, Rec::Live { e: 2, inc: 1, del: false }],
                             text: true, key: 1 }],
            idem: [1, 0, 0], idem_red: 0, red_rev: 0, marker: None, count: [0, 0], runs: [Run::Idle, Run::Idle],
            e: Ep::Idle, e_undo: vec![], p: Pp::Idle, p_undo: vec![], w: Wp::Idle, w_undo: vec![],
            inc_next: [2, 1, 2], recorded: 0b101, tombs_of: [0, 0], audited: [0, 0], pending: 0, unrecorded: false,
            committed: 0, starts: 0, erases: 0, commits: 0, writes: 0,
        }]
    }

    fn actions(&self, _s: &S) -> Vec<A> {
        let mut v = vec![];
        for p in 0..2 {
            v.extend([A::Read1(p, 0), A::Read1(p, 1), A::Read2(p), A::Batch(p), A::Final(p), A::Stop(p)]);
        }
        v.extend([A::E1(0), A::E1(1), A::E2, A::E3, A::E4]);
        if self.cfg.estop { v.push(A::EStop); }
        if self.cfg.max_commits > 0 { v.extend([A::PBegin(0), A::PBegin(1), A::PEnd]); }
        if self.cfg.pstop { v.push(A::PStop); }
        if self.cfg.bypass != Bypass::Off {
            for e in 0..NE as u8 { v.extend([A::WBegin(e, true), A::WBegin(e, false)]); }
            v.extend([A::WEnd, A::WStop]);
        }
        v
    }

    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        match *a {
            A::Read1(p, t) => {
                let pi = p as usize;
                if s.runs[pi] != Run::Idle { return None; }
                if self.locked_start() && !self.head_free(s) { return None; } // the reviewed Start waits for the lock
                if self.cfg.max_starts > 0 { u.starts += 1; } // 0: calls are not counted (unbounded resumes)
                if let Some(m) = s.marker { if m != t { return Some(u); } } // redaction_in_progress
                if !self.locked_start() {
                    u.runs[pi] = Run::Checked(t);
                } else {
                    if s.live(t) { return Some(u); } // target_live
                    if s.marker.is_none() { u.marker = Some(t); }
                    let (i, j, done) = s.norm(0, 0);
                    u.runs[pi] = Run::Scan { t, i, j, made: false, done, scanned: 0 };
                }
            }
            A::Read2(p) => {
                let pi = p as usize;
                let Run::Checked(t) = s.runs[pi] else { return None };
                if s.live(t) { u.runs[pi] = Run::Idle; return Some(u); } // target_live (a dirty read)
                let (i, j, done) = s.norm(0, 0);
                u.runs[pi] = Run::Scan { t, i, j, made: false, done, scanned: 0 };
            }
            A::Batch(p) => {
                let pi = p as usize;
                let Run::Scan { t, i, j, made, done, scanned } = s.runs[pi] else { return None };
                if self.at_end(s, i, j, done) || !self.head_free(s) { return None; }
                let (i, j, _) = s.norm(i, j);
                if self.reviewed() {
                    match self.cfg.mutant {
                        Mutant::BatchUnderOtherMarker => { if s.marker.is_none() { return None; } }
                        Mutant::UnlockedStart => { if let Some(m) = s.marker { if m != t { return None; } } }
                        _ => { if s.marker != Some(t) { return None; } }
                    }
                }
                let mut made = made;
                if let Rec::Live { e, .. } = s.revs[i as usize].recs[j as usize] {
                    if g_of(e as usize) == t { self.tombstone(&mut u, i as usize, j as usize, t); made = true; }
                }
                let (ni, nj, nd) = u.norm(i, j + 1);
                let sc = scanned + 1;
                u.runs[pi] = if self.cfg.pace > 0 && sc >= self.cfg.pace && !nd {
                    Run::Idle // max_batches reached: the call returns incomplete, the marker stays
                } else {
                    Run::Scan { t, i: ni, j: nj, made, done: nd, scanned: sc }
                };
            }
            A::Final(p) => {
                let pi = p as usize;
                let Run::Scan { t, i, j, done, .. } = s.runs[pi] else { return None };
                if !self.at_end(s, i, j, done) || !self.head_free(s) { return None; }
                if self.reviewed() && s.marker != Some(t) {
                    if !(s.marker.is_none() && self.cfg.mutant == Mutant::UnlockedStart) { return None; }
                }
                u.runs[pi] = Run::Idle;
                if s.live(t) { return Some(u); } // target_live: the marker stays
                let mut dropped = 0u8;
                for id in 1..=4u8 {
                    if let Some((e, _)) = S::stmt_of(s.stmt[id as usize - 1]) {
                        if g_of(e) == t {
                            u.write(Who::Committed, Item::Stmt(id), 0);
                            if u.tuple[e] == id { u.write(Who::Committed, Item::Tuple(e as u8), 0); }
                            dropped += 1;
                        }
                    }
                }
                let n = if self.shared_counters() { s.count[0] }
                        else if self.cfg.mutant == Mutant::CountersSwapped { s.count[1 - t as usize] }
                        else { s.count[t as usize] };
                let write_audit = if self.reviewed() { n > 0 || dropped > 0 } else { s.marker.is_some() || dropped > 0 };
                if write_audit {
                    u.revs.push(Rev { recs: vec![Rec::Audit { t, n }], text: true, key: 0 });
                    u.audited[t as usize] += n;
                }
                if !(self.reviewed() && self.cfg.mutant == Mutant::FinalKeepsMarker) { u.marker = None; }
                if write_audit || s.marker.is_some() { u.count = [0, 0]; }
                u.pending &= !(1 << t);
            }
            A::Stop(p) => {
                if s.runs[p as usize] == Run::Idle { return None; }
                u.runs[p as usize] = Run::Idle;
            }
            A::E1(g) => {
                if s.e != Ep::Idle { return None; }
                if self.e_locks() && !self.head_free(s) { return None; }
                if s.uncommitted_insert_in(g, Who::E) { return None; } // the DELETE waits for the row lock
                for e in 0..NE {
                    if g_of(e) == g && s.row[e] != 0 {
                        u.write(Who::E, Item::Row(e as u8), 0);
                        u.write(Who::E, Item::Adj(e as u8), 0); // the row's functional index entry goes with it
                    }
                }
                u.e = Ep::Open { g, step: 1 };
                if self.cfg.max_erases > 0 { u.erases += 1; }
            }
            A::E2 => {
                let Ep::Open { g, step: 1 } = s.e else { return None };
                for e in 0..NE { if g_of(e) == g && s.adj & (1 << e) != 0 { u.write(Who::E, Item::Adj(e as u8), 0); } }
                u.e = Ep::Open { g, step: 2 };
            }
            A::E3 => {
                let Ep::Open { g, step: 2 } = s.e else { return None };
                for id in 1..=4u8 {
                    if let Some((e, _)) = S::stmt_of(s.stmt[id as usize - 1]) {
                        if g_of(e) == g {
                            u.write(Who::E, Item::Tuple(e as u8), 0);
                            u.write(Who::E, Item::Stmt(id), 0);
                        }
                    }
                }
                u.e = Ep::Open { g, step: 3 };
            }
            A::E4 => {
                let Ep::Open { g, step: 3 } = s.e else { return None };
                u.e_undo.clear();
                u.e = Ep::Idle;
                u.pending |= 1 << g;
            }
            A::EStop => {
                if s.e == Ep::Idle { return None; }
                u.rollback(Who::E);
                u.e = Ep::Idle;
            }
            A::PBegin(c) => {
                if s.p != Pp::Idle || s.committed & (1 << c) != 0 || !self.head_free(s) { return None; }
                if s.commits >= self.cfg.max_commits { return None; }
                let blocked = s.marker == Some(0); // both changesets write into G1 (target A)
                let inc;
                if c == 0 {
                    // create_rel a1: refused as relationship_exists when the row is visible; waits on a row another
                    // open transaction deleted (contract Freedom, modelled as a wait)
                    if s.row[1] != 0 || s.row_locked_by_other(1, Who::P) { return None; }
                    if s.next > 4 { return None; }
                    inc = s.inc_next[1];
                    u.inc_next[1] += 1;
                    u.write(Who::P, Item::Row(1), inc);
                    u.write(Who::P, Item::Adj(1), 1);
                    let id = s.next;
                    u.write(Who::P, Item::Next, id + 1);
                    u.write(Who::P, Item::Stmt(id), 1 + 2 * 1);
                    u.write(Who::P, Item::Tuple(1), id);
                } else {
                    // delete_rel by statement 1 (a0): the statement must be live and FindEdge must see the row
                    if s.stmt[0] != 1 || s.row[0] == 0 || s.row_locked_by_other(0, Who::P) { return None; }
                    inc = s.row[0];
                    u.write(Who::P, Item::Row(0), 0);
                    u.write(Who::P, Item::Adj(0), 0);
                    u.write(Who::P, Item::Stmt(1), 2);
                    if s.tuple[0] == 1 { u.write(Who::P, Item::Tuple(0), 0); }
                }
                u.p = Pp::Open { c, ok: !blocked, inc };
                u.commits += 1;
            }
            A::PEnd => {
                let Pp::Open { c, ok, inc } = s.p else { return None };
                if ok {
                    let e = if c == 0 { 1u8 } else { 0u8 };
                    u.revs.push(Rev { recs: vec![Rec::Live { e, inc, del: c == 1 }], text: true, key: c + 2 });
                    u.idem[c as usize + 1] = u.revs.len() as u8;
                    u.committed |= 1 << c;
                    if c == 0 { u.recorded |= 1 << 1 } else { u.recorded &= !1 }
                    u.p_undo.clear();
                } else {
                    u.rollback(Who::P); // BlocksCommit: redaction_in_progress
                }
                u.p = Pp::Idle;
            }
            A::PStop => {
                if s.p == Pp::Idle { return None; }
                u.rollback(Who::P);
                u.p = Pp::Idle;
            }
            A::WBegin(e, ins) => {
                if s.w != Wp::Idle || s.writes >= self.cfg.max_writes { return None; }
                if self.cfg.bypass == Bypass::Serializing && !self.head_free(s) { return None; }
                let ei = e as usize;
                if s.row_locked_by_other(ei, Who::W) { return None; }
                if ins {
                    if s.row[ei] != 0 { return None; }
                    let inc = s.inc_next[ei];
                    u.inc_next[ei] += 1;
                    u.write(Who::W, Item::Row(e), inc);
                    u.write(Who::W, Item::Adj(e), 1);
                } else {
                    if s.row[ei] == 0 { return None; }
                    u.write(Who::W, Item::Row(e), 0);
                    u.write(Who::W, Item::Adj(e), 0);
                }
                u.w = Wp::Open { e, ins };
                u.writes += 1;
            }
            A::WEnd => {
                let Wp::Open { e, .. } = s.w else { return None };
                u.w_undo.clear();
                u.recorded &= !(1 << e);
                u.unrecorded = true;
                u.w = Wp::Idle;
            }
            A::WStop => {
                if s.w == Wp::Idle { return None; }
                u.rollback(Who::W);
                u.w = Wp::Idle;
            }
        }
        Some(u)
    }

    fn within_bounds(&self, s: &S) -> bool {
        (self.cfg.max_starts == 0 || s.starts <= self.cfg.max_starts) && (self.cfg.max_erases == 0 || s.erases <= self.cfg.max_erases)
    }

    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("INV-no-live-tombstone: no tombstone describes a live incarnation (no transaction open)", |s: &S| {
                if !s.quiescent() { return true; }
                s.revs.iter().all(|r| r.recs.iter().all(|x| match *x {
                    Rec::Tomb { e, inc, .. } => s.row[e as usize] != inc,
                    _ => true,
                }))
            }),
            invariant("INV-stmt: live statement entries are exactly the live recorded edges (no transaction open)", |s: &S| {
                if !s.quiescent() { return true; }
                let edges_ok = (0..NE).all(|e| {
                    let live_rec = s.row[e] != 0 && s.recorded & (1 << e) != 0;
                    let id = s.tuple[e];
                    let has_stmt = id != 0 && s.stmt[id as usize - 1] == 1 + 2 * e as u8;
                    live_rec == has_stmt
                });
                let stmts_ok = (1..=4u8).all(|id| match S::stmt_of(s.stmt[id as usize - 1]) {
                    Some((e, false)) => s.tuple[e] == id && s.row[e] != 0 && s.recorded & (1 << e) != 0,
                    _ => true,
                });
                edges_ok && stmts_ok
            }),
            invariant("INV-adj: adjacency equals the edge rows (no transaction open)", |s: &S| {
                !s.quiescent() || (0..NE).all(|e| ((s.adj >> e) & 1 == 1) == (s.row[e] != 0))
            }),
            invariant("INV-text: a revision with a tombstone keeps no free text and no retry key (Decision 2)", |s: &S| {
                s.revs.iter().all(|r| !r.recs.iter().any(|x| matches!(x, Rec::Tomb { .. })) || (!r.text && r.key == 0))
            }),
            invariant("INV-retry: a bound key names a revision with no tombstone; a redacted key is unbound", |s: &S| {
                (0..3).all(|k| {
                    let r = s.idem[k];
                    (r == 0 || !s.revs[r as usize - 1].recs.iter().any(|x| matches!(x, Rec::Tomb { .. })))
                        && (s.idem_red & (1 << k) == 0 || r == 0)
                })
            }),
            invariant("INV-audit-settled: once settled every tombstone is counted by one audit of its own target", |s: &S| {
                !s.settled() || s.audited == s.tombs_of
            }),
            invariant("INV-replay: with no unrecorded write and every erased target redacted, replay equals the store", |s: &S| {
                if !s.settled() || s.pending != 0 || s.unrecorded { return true; }
                s.replay() == s.rows()
            }),
        ]
    }

    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![
            action_property("INV-audit: each audit counts exactly its own target's tombstones", |s: &S, a: &A, t: &S| {
                if !matches!(a, A::Final(_)) || t.revs.len() <= s.revs.len() { return true; }
                match t.revs.last().unwrap().recs[0] {
                    Rec::Audit { t: tg, n } => n as i16 == s.tombs_of[tg as usize] as i16 - s.audited[tg as usize] as i16,
                    _ => true,
                }
            }),
            action_property("INV-marker-owner: a run tombstones and finishes only under its own target's marker",
                |s: &S, a: &A, t: &S| match *a {
                    A::Batch(p) => {
                        let Run::Scan { t: tg, .. } = s.runs[p as usize] else { return true };
                        if t.tombs_of == s.tombs_of { return true; }
                        (s.marker.is_none() || s.marker == Some(tg)) && t.marker == Some(tg)
                    }
                    A::Final(p) => {
                        let Run::Scan { t: tg, .. } = s.runs[p as usize] else { return true };
                        !(s.marker.is_some() && t.marker.is_none()) || s.marker == Some(tg)
                    }
                    _ => true,
                }),
            action_property("INV-marker: while the marker names t no record of t is added", |s: &S, _a: &A, t: &S| {
                let Some(m) = s.marker else { return true };
                if t.marker != Some(m) { return true; }
                t.revs[s.revs.len().min(t.revs.len())..].iter().all(|r| r.recs.iter().all(|x| match *x {
                    Rec::Live { e, .. } => g_of(e as usize) != m,
                    _ => true,
                }))
            }),
        ]
    }

    fn always_possibly(&self) -> Vec<Invariant<S>> {
        // An erased target that a later write made live again can only be redacted after another erasure, which the
        // operator may or may not want: the goal asks every erased target that is still erased to be redacted.
        vec![invariant("settled: no marker, no run, no open transaction, every erased target redacted",
                       |s: &S| s.settled() && (0..2u8).all(|t| s.pending & (1 << t) == 0 || s.live(t)))]
    }
}

pub fn act(a: &A) -> String {
    match *a {
        A::Read1(p, t) => format!("p{p} Redact {} (marker check)", TNAME[t as usize]),
        A::Read2(p) => format!("p{p} LiveRows (unlocked)"),
        A::Batch(p) => format!("p{p} Batch"),
        A::Final(p) => format!("p{p} Final"),
        A::Stop(p) => format!("p{p} Stop"),
        A::E1(g) => format!("E EraseGraph(G{}) DELETE rows", g + 1),
        A::E2 => "E RemoveGraph (adjacency)".into(),
        A::E3 => "E EraseLedgerFor (stmt/tuple)".into(),
        A::E4 => "E TCOMMIT".into(),
        A::EStop => "E stopped (rollback)".into(),
        A::PBegin(c) => format!("P commit {} (apply, open)", ["CA create a1", "DA delete a0"][c as usize]),
        A::PEnd => "P TCOMMIT/TROLLBACK".into(),
        A::PStop => "P stopped (rollback)".into(),
        A::WBegin(e, ins) => format!("W bypass {} {} (open)", if ins { "insert" } else { "delete" }, ENAME[e as usize]),
        A::WEnd => "W commit".into(),
        A::WStop => "W stopped (rollback)".into(),
    }
}

pub fn brief(s: &S) -> String {
    let rows: Vec<String> = (0..NE).filter(|&e| s.row[e] != 0).map(|e| format!("{}#{}", ENAME[e], s.row[e])).collect();
    let stm: Vec<String> = (1..=4u8).filter_map(|id| S::stmt_of(s.stmt[id as usize - 1])
        .map(|(e, c)| format!("{id}:{}{}", ENAME[e], if c { "(closed)" } else { "" }))).collect();
    let recs: Vec<String> = s.revs.iter().enumerate().map(|(n, r)| format!("r{n}[{}]{}", r.recs.iter().map(|x| match *x {
        Rec::Live { e, inc, del } => format!("{}{}#{}", if del { "-" } else { "+" }, ENAME[e as usize], inc),
        Rec::Tomb { e, inc, del } => format!("~{}{}#{}", if del { "-" } else { "+" }, ENAME[e as usize], inc),
        Rec::Audit { t, n } => format!("audit({}:{n})", TNAME[t as usize]),
    }).collect::<Vec<_>>().join(","), if r.text { "" } else { "*" })).collect();
    let adj: Vec<&str> = (0..NE).filter(|&e| s.adj & (1 << e) != 0).map(|e| ENAME[e]).collect();
    format!("rows={:?} adj={:?} stmt=[{}] marker={:?} count={:?} recs={} runs={:?} E={:?} P={:?} W={:?}",
            rows, adj, stm.join(" "), s.marker.map(|t| TNAME[t as usize]), s.count, recs.join(" "), s.runs, s.e, s.p, s.w)
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n", c.property, c.kind, c.steps.len());
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<34} {}\n", i + 1, act(a), brief(s));
    }
    out
}
