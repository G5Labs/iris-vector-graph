//! IRIS environment contract: the part of InterSystems IRIS 2026.1 semantics that IVG relies on, as an executable
//! machine whose `step` returns every outcome the contract permits.
//!
//! Scope (the "semantic subset"): globals (SET, KILL subtree, $GET/$DATA, $INCREMENT), process-private globals,
//! nested transactions (TSTART / TCOMMIT / TROLLBACK 1 / TROLLBACK), the SQL transaction verbs and the DB-API
//! driver's commit/rollback on the same server process, dynamic SQL row INSERT / UPDATE / DELETE / SELECT on a
//! keyed table with row locks, the lock table (exclusive and shared modes, hierarchical names, incremental counts,
//! deferred release inside a transaction, immediate release, release-all, non-incremental LOCK), lock timeouts,
//! visibility of uncommitted data (no isolation for globals; READ UNCOMMITTED for SQL), and process stop.
//!
//! Outside the subset (refused by `Op::Unsupported` and never claimed): ECP/mirroring and multi-node, journal
//! restore after a crash, SQL isolation levels other than the default, lock escalation thresholds, DDL inside
//! transactions, %NOLOCK / %NOJOURN, iFind / vector index maintenance, and timing. Each is listed in CONTRACT.md.
//!
//! Every clause that is not documented-and-observed carries a `Semantics` switch: the validated value is the
//! default, the alternatives are the mutants the differential suite must kill. A clause whose truth on the engine
//! is unknown is modelled with both outcomes permitted (`Freedom`), never one picked.
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Node {
    pub root: String,
    #[serde(default)]
    pub subs: Vec<String>,
}

impl Node {
    pub fn new(root: &str, subs: &[&str]) -> Node {
        Node { root: root.to_string(), subs: subs.iter().map(|s| s.to_string()).collect() }
    }
    /// `self` is `other` or an ancestor of it.
    pub fn covers(&self, other: &Node) -> bool {
        self.root == other.root && self.subs.len() <= other.subs.len() && other.subs[..self.subs.len()] == self.subs[..]
    }
    pub fn related(&self, other: &Node) -> bool {
        self.covers(other) || other.covers(self)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Mode {
    E,
    S,
}

/// Lock counts one process holds on one name. `de`/`ds`: released by an unlock inside a transaction, kept until
/// the outermost transaction ends.
#[derive(Clone, Debug, Default, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Hold {
    pub e: u32,
    pub s: u32,
    pub de: u32,
    pub ds: u32,
}

impl Hold {
    fn any(&self) -> bool {
        self.e + self.s + self.de + self.ds > 0
    }
    fn excl(&self) -> bool {
        self.e + self.de > 0
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Proc {
    pub alive: bool,
    pub tlevel: u32,
    /// SQL started (and owns) the current transaction: START TRANSACTION while it is set does nothing.
    pub sqlflag: bool,
    /// Driver autocommit (DB-API default true). With it off, a DML statement at level 0 starts a transaction.
    pub autocommit: bool,
    /// Old values per transaction level, in write order.
    pub undo: Vec<Vec<(Node, Option<String>, Option<String>)>>,
    /// Process-private global old values per level (used only when PPGs are rolled back: a mutant).
    pub ppg_undo: Vec<Vec<(Node, Option<String>)>>,
    pub locks: BTreeMap<Node, Hold>,
    pub ppg: BTreeMap<Node, String>,
    pub pending: Option<Op>,
}

impl Proc {
    pub fn new() -> Proc {
        Proc { alive: true, tlevel: 0, sqlflag: false, autocommit: true, undo: vec![], ppg_undo: vec![],
               locks: BTreeMap::new(), ppg: BTreeMap::new(), pending: None }
    }
}

impl Default for Proc {
    fn default() -> Self {
        Proc::new()
    }
}

/// Switches for every clause the differential suite decides. Defaults are the validated semantics.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Semantics {
    /// An unlock inside a transaction is deferred to the outermost transaction end (IRIS docs; observed).
    pub unlock_deferred_in_txn: bool,
    /// TROLLBACK 1 undoes only the top level (observed).
    pub rollback_one_is_one_level: bool,
    /// $INCREMENT is not undone by a rollback (observed; the product relies on it, Adjacency.cls:57).
    pub incr_survives_rollback: bool,
    /// Other processes see uncommitted global and row writes (no isolation; observed).
    pub dirty_reads: bool,
    /// Lock names are hierarchical: a lock conflicts with locks on ancestors and descendants (observed).
    pub hierarchical_locks: bool,
    /// Shared locks are compatible with each other (observed).
    pub shared_compatible: bool,
    /// Lock counts are incremental (observed).
    pub incremental_locks: bool,
    /// SQL START TRANSACTION: TSTART unless SQL already owns the transaction.
    pub sql_start: SqlStart,
    /// SQL COMMIT / driver commit(): how many levels it ends.
    pub sql_commit: Ends,
    /// SQL ROLLBACK statement.
    pub sql_rollback: Ends,
    /// Driver rollback().
    pub drv_rollback: Ends,
    /// Driver commit().
    pub drv_commit: Ends,
    /// A DML statement on a row another process holds waits for the row lock.
    pub dml_waits_on_row_lock: bool,
    /// Process stop rolls back every open level and releases every lock.
    pub stop_rolls_back: bool,
    /// Rollback restores the old value even over another process's later write. Observed: it does not; a node
    /// another process changed since this process wrote it keeps the other process's value (round 1,
    /// txn-physical-rollback). The physical reading is the mutant.
    pub rollback_physical: bool,
    /// Process-private globals are rolled back by TROLLBACK (observed: they are not).
    pub ppg_rolled_back: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SqlStart {
    /// TSTART unless SQL already owns the open transaction (hypothesis from the exploratory probe).
    UnlessSqlOwns,
    /// Nothing whenever any transaction is open (the product's premise, Txn.cls:8, measured on 2026.3).
    NothingIfOpen,
    /// Always TSTART.
    Always,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Ends {
    OneLevel,
    AllLevels,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Freedom {
    Yes,
    No,
    Either,
}

impl Default for Semantics {
    fn default() -> Self {
        Semantics {
            unlock_deferred_in_txn: true,
            rollback_one_is_one_level: true,
            incr_survives_rollback: true,
            dirty_reads: true,
            hierarchical_locks: true,
            shared_compatible: true,
            incremental_locks: true,
            sql_start: SqlStart::NothingIfOpen,
            sql_commit: Ends::OneLevel,
            sql_rollback: Ends::OneLevel,
            drv_rollback: Ends::AllLevels,
            drv_commit: Ends::OneLevel,
            dml_waits_on_row_lock: true,
            stop_rolls_back: true,
            rollback_physical: false,
            ppg_rolled_back: false,
        }
    }
}

/// The SQL table's rows live under this root, keyed by the row's key (one keyed table per name).
pub fn row_node(table: &str, k: &str) -> Node {
    Node { root: format!("^SQL.{table}"), subs: vec![k.to_string()] }
}

pub fn row_lock(table: &str, k: &str) -> Node {
    Node { root: format!("#row.{table}"), subs: vec![k.to_string()] }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum Op {
    TStart,
    TCommit,
    TRollbackOne,
    TRollback,
    SqlStart,
    SqlCommit,
    SqlRollback,
    DrvCommit,
    DrvRollback,
    SetAutocommit { on: bool },
    TLevel,
    Set { node: Node, value: String },
    Kill { node: Node },
    Get { node: Node },
    Data { node: Node },
    Incr { node: Node },
    PpgSet { node: Node, value: String },
    PpgGet { node: Node },
    /// Incremental lock with timeout 0 (`timeout0`) or a waiting lock (`await` later observes it).
    Lock { node: Node, mode: Mode, wait: bool },
    Unlock { node: Node, mode: Mode, immediate: bool },
    /// Non-incremental LOCK name: release every lock held, then lock the name.
    LockOnly { node: Node, wait: bool },
    ReleaseAll,
    Insert { table: String, k: String, v: String },
    Update { table: String, k: String, v: String },
    Delete { table: String, k: String },
    Select { table: String },
    /// Stop another process (control connection); the case waits until it is gone.
    Terminate { target: usize },
    /// Observe a pending operation of this process: done (with its result) or still blocked.
    Await,
    Unsupported { what: String },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(tag = "obs", rename_all = "snake_case")]
pub enum Obs {
    Ok,
    Level { tlevel: u32 },
    Value { value: Option<String> },
    Data { data: u8 },
    Test { test: bool },
    Rows { rows: Vec<(String, String)> },
    Count { rowcount: i64 },
    SqlError { sqlcode: i64 },
    Error { error: String },
    Blocked,
    Pending,
    Refused { what: String },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Engine {
    pub g: BTreeMap<Node, String>,
    pub procs: Vec<Proc>,
    pub sem: Semantics,
}

impl Engine {
    pub fn new(nprocs: usize, sem: Semantics) -> Engine {
        Engine { g: BTreeMap::new(), procs: (0..nprocs).map(|_| Proc::new()).collect(), sem }
    }

    // ------------------------------------------------------------------------------------------- globals

    fn write(&mut self, p: usize, node: &Node, value: Option<String>, logged: bool) {
        let old = self.g.get(node).cloned();
        if logged && self.procs[p].tlevel > 0 {
            if let Some(top) = self.procs[p].undo.last_mut() {
                top.push((node.clone(), old, value.clone()));
            }
        }
        match value {
            Some(v) => {
                self.g.insert(node.clone(), v);
            }
            None => {
                self.g.remove(node);
            }
        }
    }

    fn kill_subtree(&mut self, p: usize, node: &Node) {
        let victims: Vec<Node> = self.g.keys().filter(|k| node.covers(k)).cloned().collect();
        for v in victims {
            self.write(p, &v, None, true);
        }
    }

    pub fn data(&self, node: &Node) -> u8 {
        let has_value = self.g.contains_key(node);
        let has_kids = self.g.keys().any(|k| node.covers(k) && k != node);
        (if has_value { 1 } else { 0 }) + (if has_kids { 10 } else { 0 })
    }

    // ------------------------------------------------------------------------------------------- transactions

    fn tstart(&mut self, p: usize) {
        let pr = &mut self.procs[p];
        pr.tlevel += 1;
        pr.undo.push(vec![]);
        pr.ppg_undo.push(vec![]);
    }

    fn undo_top(&mut self, p: usize) {
        let entries = self.procs[p].undo.pop().unwrap_or_default();
        for (node, old, written) in entries.into_iter().rev() {
            // physical: restore the old value whatever happened since; logical (mutant): skip a node another
            // process has changed since this process wrote it
            if self.sem.rollback_physical || self.g.get(&node) == written.as_ref() {
                match old {
                    Some(v) => {
                        self.g.insert(node, v);
                    }
                    None => {
                        self.g.remove(&node);
                    }
                }
            }
        }
        let ppg = self.procs[p].ppg_undo.pop().unwrap_or_default();
        if self.sem.ppg_rolled_back {
            for (node, old) in ppg.into_iter().rev() {
                match old {
                    Some(v) => {
                        self.procs[p].ppg.insert(node, v);
                    }
                    None => {
                        self.procs[p].ppg.remove(&node);
                    }
                }
            }
        }
        self.procs[p].tlevel -= 1;
        if self.procs[p].tlevel == 0 {
            self.txn_end(p);
        }
    }

    fn commit_top(&mut self, p: usize) {
        let entries = self.procs[p].undo.pop().unwrap_or_default();
        let ppg = self.procs[p].ppg_undo.pop().unwrap_or_default();
        self.procs[p].tlevel -= 1;
        if let Some(parent) = self.procs[p].undo.last_mut() {
            parent.extend(entries); // a later rollback of the outer level undoes the inner level's writes too
        }
        if let Some(parent) = self.procs[p].ppg_undo.last_mut() {
            parent.extend(ppg);
        }
        if self.procs[p].tlevel == 0 {
            self.txn_end(p);
        }
    }

    /// The outermost transaction ended: deferred unlocks take effect (row locks are deferred exclusive locks).
    fn txn_end(&mut self, p: usize) {
        let pr = &mut self.procs[p];
        pr.sqlflag = false;
        pr.undo.clear();
        pr.ppg_undo.clear();
        for h in pr.locks.values_mut() {
            h.de = 0;
            h.ds = 0;
        }
        pr.locks.retain(|_, h| h.any());
    }

    fn end_levels(&mut self, p: usize, ends: Ends, commit: bool) {
        if self.procs[p].tlevel == 0 {
            return;
        }
        let n = match ends {
            Ends::OneLevel => 1,
            Ends::AllLevels => self.procs[p].tlevel,
        };
        for _ in 0..n {
            if commit { self.commit_top(p) } else { self.undo_top(p) }
        }
        if self.procs[p].tlevel == 0 || ends == Ends::AllLevels {
            self.procs[p].sqlflag = false;
        }
    }

    // ------------------------------------------------------------------------------------------- locks

    fn conflicts(&self, p: usize, node: &Node, mode: Mode) -> bool {
        self.procs.iter().enumerate().any(|(q, pr)| {
            q != p && pr.alive && pr.locks.iter().any(|(m, h)| {
                let rel = if self.sem.hierarchical_locks { m.related(node) } else { m == node };
                rel && match mode {
                    Mode::E => h.any(),
                    Mode::S => h.excl() || (!self.sem.shared_compatible && h.any()),
                }
            })
        })
    }

    fn acquire(&mut self, p: usize, node: &Node, mode: Mode) {
        let incremental = self.sem.incremental_locks;
        let h = self.procs[p].locks.entry(node.clone()).or_default();
        match mode {
            Mode::E => h.e = if incremental { h.e + 1 } else { 1 },
            Mode::S => h.s = if incremental { h.s + 1 } else { 1 },
        }
    }

    fn release(&mut self, p: usize, node: &Node, mode: Mode, immediate: bool) {
        let defer = self.sem.unlock_deferred_in_txn && !immediate && self.procs[p].tlevel > 0;
        if let Some(h) = self.procs[p].locks.get_mut(node) {
            match mode {
                Mode::E if h.e > 0 => {
                    h.e -= 1;
                    if defer { h.de += 1 }
                }
                Mode::S if h.s > 0 => {
                    h.s -= 1;
                    if defer { h.ds += 1 }
                }
                _ => {}
            }
        }
        self.procs[p].locks.retain(|_, h| h.any());
    }

    /// Release every lock. Inside a transaction the release is deferred like an unlock (observed: round 1,
    /// lock-release-all-in-txn), unless the deferral clause is mutated.
    fn release_all(&mut self, p: usize) {
        if self.sem.unlock_deferred_in_txn && self.procs[p].tlevel > 0 {
            for h in self.procs[p].locks.values_mut() {
                h.de += h.e;
                h.ds += h.s;
                h.e = 0;
                h.s = 0;
            }
        } else {
            self.procs[p].locks.clear();
        }
    }

    // ------------------------------------------------------------------------------------------- SQL rows

    /// Run one DML statement's effect, assuming its row lock is available. Statement-level transaction: at level
    /// 0 with autocommit on, the statement is its own transaction; with autocommit off it opens one SQL owns.
    fn dml(&mut self, p: usize, table: &str, k: &str, new: Option<&str>, insert: bool) -> Obs {
        let row = row_node(table, k);
        let exists = self.g.contains_key(&row);
        if insert && exists {
            return Obs::SqlError { sqlcode: -119 };
        }
        if !insert && !exists {
            return Obs::Count { rowcount: 0 };
        }
        let implicit = self.procs[p].tlevel == 0 && self.procs[p].autocommit;
        if self.procs[p].tlevel == 0 && !self.procs[p].autocommit {
            self.tstart(p);
            self.procs[p].sqlflag = true;
        }
        if implicit {
            self.tstart(p);
        }
        self.write(p, &row, new.map(|s| s.to_string()), true);
        if implicit {
            self.commit_top(p);
        } else {
            // the row lock is held until the outermost transaction ends
            let h = self.procs[p].locks.entry(row_lock(table, k)).or_default();
            h.de += 1;
        }
        Obs::Count { rowcount: 1 }
    }

    fn select(&self, table: &str) -> Obs {
        let root = format!("^SQL.{table}");
        let rows = self.g.iter().filter(|(n, _)| n.root == root && n.subs.len() == 1)
            .map(|(n, v)| (n.subs[0].clone(), v.clone())).collect();
        Obs::Rows { rows }
    }

    // ------------------------------------------------------------------------------------------- processes

    fn stop(&mut self, p: usize) {
        if self.sem.stop_rolls_back {
            while self.procs[p].tlevel > 0 {
                self.undo_top(p);
            }
        } else {
            while self.procs[p].tlevel > 0 {
                self.commit_top(p);
            }
        }
        self.procs[p].locks.clear();
        self.procs[p].ppg.clear();
        self.procs[p].pending = None;
        self.procs[p].alive = false;
    }

    /// Whether `op` by `p` is blocked now. A DELETE/UPDATE waits only for a row it can see (dirty view) whose row
    /// lock another process holds. An INSERT of a key that is visible fails at once (-119); see `insert_freedom` for
    /// an INSERT whose key another process holds a row lock on but which is not visible (deleted, uncommitted).
    fn blocked_on(&self, p: usize, op: &Op) -> bool {
        match op {
            Op::Lock { node, mode, .. } => self.conflicts(p, node, *mode),
            Op::LockOnly { node, .. } => self.conflicts(p, node, Mode::E),
            Op::Update { table, k, .. } | Op::Delete { table, k } => {
                self.sem.dml_waits_on_row_lock
                    && self.g.contains_key(&row_node(table, k))
                    && self.conflicts(p, &row_lock(table, k), Mode::E)
            }
            // only reached for an INSERT already pending (the waiting world of `insert_freedom`)
            Op::Insert { .. } => self.insert_freedom(p, op),
            _ => false,
        }
    }

    /// Freedom (not decided by the suite): an INSERT of an invisible key whose row lock another process holds may
    /// wait or proceed, depending on whether the table's row id is its key.
    fn insert_freedom(&self, p: usize, op: &Op) -> bool {
        match op {
            Op::Insert { table, k, .. } => {
                self.sem.dml_waits_on_row_lock
                    && !self.g.contains_key(&row_node(table, k))
                    && self.conflicts(p, &row_lock(table, k), Mode::E)
            }
            _ => false,
        }
    }

    /// Every permitted (next engine, observation) for process `p` performing `op` now.
    pub fn step(&self, p: usize, op: &Op) -> Vec<(Engine, Obs)> {
        let mut e = self.clone();
        if !e.procs[p].alive {
            return vec![(e, Obs::Error { error: "dead".into() })];
        }
        if e.procs[p].pending.is_some() && !matches!(op, Op::Await) {
            return vec![(e, Obs::Error { error: "busy".into() })];
        }
        let obs = match op {
            Op::TStart => {
                e.tstart(p);
                Obs::Ok
            }
            Op::TCommit => {
                if e.procs[p].tlevel == 0 {
                    Obs::Error { error: "<COMMAND>".into() }
                } else {
                    e.commit_top(p);
                    Obs::Ok
                }
            }
            Op::TRollbackOne => {
                if e.procs[p].tlevel == 0 {
                    Obs::Ok
                } else {
                    if e.sem.rollback_one_is_one_level {
                        e.undo_top(p)
                    } else {
                        while e.procs[p].tlevel > 0 {
                            e.undo_top(p)
                        }
                    }
                    Obs::Ok
                }
            }
            Op::TRollback => {
                while e.procs[p].tlevel > 0 {
                    e.undo_top(p);
                }
                Obs::Ok
            }
            Op::SqlStart => {
                let start = match e.sem.sql_start {
                    SqlStart::UnlessSqlOwns => !e.procs[p].sqlflag,
                    SqlStart::NothingIfOpen => e.procs[p].tlevel == 0,
                    SqlStart::Always => true,
                };
                if start {
                    e.tstart(p);
                    e.procs[p].sqlflag = true;
                }
                Obs::Ok
            }
            Op::SqlCommit => {
                let ends = e.sem.sql_commit;
                e.end_levels(p, ends, true);
                e.procs[p].sqlflag = false;
                Obs::Ok
            }
            Op::SqlRollback => {
                let ends = e.sem.sql_rollback;
                e.end_levels(p, ends, false);
                e.procs[p].sqlflag = false;
                Obs::Ok
            }
            Op::DrvCommit => {
                let ends = e.sem.drv_commit;
                e.end_levels(p, ends, true);
                e.procs[p].sqlflag = false;
                Obs::Ok
            }
            Op::DrvRollback => {
                let ends = e.sem.drv_rollback;
                e.end_levels(p, ends, false);
                e.procs[p].sqlflag = false;
                Obs::Ok
            }
            Op::SetAutocommit { on } => {
                e.procs[p].autocommit = *on;
                Obs::Ok
            }
            Op::TLevel => Obs::Level { tlevel: e.procs[p].tlevel },
            Op::Set { node, value } => {
                e.write(p, node, Some(value.clone()), true);
                Obs::Ok
            }
            Op::Kill { node } => {
                e.kill_subtree(p, node);
                Obs::Ok
            }
            Op::Get { node } => {
                // dirty_reads=false is a mutant: it hides other processes' uncommitted writes
                let v = if e.sem.dirty_reads { e.g.get(node).cloned() } else { e.committed_view(p, node) };
                Obs::Value { value: v }
            }
            Op::Data { node } => Obs::Data { data: e.data(node) },
            Op::Incr { node } => {
                let cur: i64 = e.g.get(node).and_then(|v| v.parse().ok()).unwrap_or(0);
                let logged = !e.sem.incr_survives_rollback;
                e.write(p, node, Some((cur + 1).to_string()), logged);
                Obs::Value { value: Some((cur + 1).to_string()) }
            }
            Op::PpgSet { node, value } => {
                let old = e.procs[p].ppg.insert(node.clone(), value.clone());
                if let Some(top) = e.procs[p].ppg_undo.last_mut() {
                    top.push((node.clone(), old));
                }
                Obs::Ok
            }
            Op::PpgGet { node } => Obs::Value { value: e.procs[p].ppg.get(node).cloned() },
            Op::Lock { node, mode, wait } => {
                if e.conflicts(p, node, *mode) {
                    if *wait {
                        e.procs[p].pending = Some(op.clone());
                        Obs::Pending
                    } else {
                        Obs::Test { test: false }
                    }
                } else {
                    e.acquire(p, node, *mode);
                    Obs::Test { test: true }
                }
            }
            Op::LockOnly { node, wait } => {
                // The release of every held lock happens first, even when the new lock then times out.
                e.release_all(p);
                if e.conflicts(p, node, Mode::E) {
                    if *wait {
                        e.procs[p].pending = Some(op.clone());
                        Obs::Pending
                    } else {
                        Obs::Test { test: false }
                    }
                } else {
                    e.acquire(p, node, Mode::E);
                    Obs::Test { test: true }
                }
            }
            Op::Unlock { node, mode, immediate } => {
                e.release(p, node, *mode, *immediate);
                Obs::Ok
            }
            Op::ReleaseAll => {
                e.release_all(p);
                Obs::Ok
            }
            Op::Insert { table, k, .. } | Op::Update { table, k, .. } | Op::Delete { table, k } => {
                if e.insert_freedom(p, op) {
                    let mut waits = e.clone();
                    waits.procs[p].pending = Some(op.clone());
                    // the world where the row id is not the key: the new row's lock is a different name
                    let mut goes = e.clone();
                    let o = goes.run_dml(p, op, table, k);
                    if let Some(h) = goes.procs[p].locks.remove(&row_lock(table, k)) {
                        goes.procs[p].locks.insert(row_lock(table, &format!("{k}'new")), h);
                    }
                    return vec![(waits, Obs::Pending), (goes, o)];
                }
                if e.blocked_on(p, op) {
                    e.procs[p].pending = Some(op.clone());
                    Obs::Pending
                } else {
                    e.run_dml(p, op, table, k)
                }
            }
            Op::Select { table } => e.select(table),
            Op::Terminate { target } => {
                let t = *target;
                if t < e.procs.len() && e.procs[t].alive {
                    e.stop(t);
                }
                Obs::Ok
            }
            Op::Await => match e.procs[p].pending.clone() {
                None => Obs::Error { error: "nothing pending".into() },
                Some(pend) => {
                    if e.blocked_on(p, &pend) {
                        Obs::Blocked
                    } else {
                        e.procs[p].pending = None;
                        match &pend {
                            Op::Lock { node, mode, .. } => {
                                e.acquire(p, node, *mode);
                                Obs::Test { test: true }
                            }
                            Op::LockOnly { node, .. } => {
                                e.acquire(p, node, Mode::E);
                                Obs::Test { test: true }
                            }
                            Op::Insert { table, k, .. } | Op::Update { table, k, .. } | Op::Delete { table, k } => {
                                let (t, k) = (table.clone(), k.clone());
                                e.run_dml(p, &pend, &t, &k)
                            }
                            _ => Obs::Error { error: "bad pending".into() },
                        }
                    }
                }
            },
            Op::Unsupported { what } => Obs::Refused { what: what.clone() },
        };
        vec![(e, obs)]
    }

    fn run_dml(&mut self, p: usize, op: &Op, table: &str, k: &str) -> Obs {
        match op {
            Op::Insert { v, .. } => self.dml(p, table, k, Some(v), true),
            Op::Update { v, .. } => self.dml(p, table, k, Some(v), false),
            Op::Delete { .. } => self.dml(p, table, k, None, false),
            _ => unreachable!(),
        }
    }

    /// The value as of the last committed state, seen by `p` (used only by the `dirty_reads = false` mutant):
    /// other processes' open transactions are undone in a scratch copy.
    fn committed_view(&self, p: usize, node: &Node) -> Option<String> {
        let mut scratch = self.clone();
        scratch.sem.rollback_physical = true;
        for q in 0..scratch.procs.len() {
            if q != p {
                while scratch.procs[q].tlevel > 0 {
                    scratch.undo_top(q);
                }
            }
        }
        scratch.g.get(node).cloned()
    }
}

/// A test case: processes and a schedule of (process, operation).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Case {
    pub id: String,
    pub procs: usize,
    pub steps: Vec<(usize, Op)>,
    /// Globals and tables whose final contents are part of the outcome.
    #[serde(default)]
    pub observe: Vec<Node>,
    #[serde(default)]
    pub observe_tables: Vec<String>,
    #[serde(default)]
    pub clause: String,
    /// Driver per process: "dbapi" (DB-API + Native API on one connection, the product's client path; default) or
    /// "term" (an ObjectScript terminal on the server). A verb one driver cannot express is refused, not modelled.
    #[serde(default)]
    pub kinds: Vec<String>,
}

fn refused_by_driver(kind: &str, op: &Op) -> Option<String> {
    let name = match op {
        Op::DrvCommit => "drv_commit",
        Op::DrvRollback => "drv_rollback",
        Op::SetAutocommit { .. } => "set_autocommit",
        Op::PpgSet { .. } => "ppg_set",
        Op::PpgGet { .. } => "ppg_get",
        Op::LockOnly { .. } => "lock_only",
        _ => return None,
    };
    let refused = match kind {
        "term" => matches!(op, Op::DrvCommit | Op::DrvRollback | Op::SetAutocommit { .. }),
        _ => matches!(op, Op::PpgSet { .. } | Op::PpgGet { .. } | Op::LockOnly { .. }),
    };
    if refused { Some(format!("{name} on {kind}")) } else { None }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Outcome {
    pub obs: Vec<Obs>,
    pub finals: Vec<Obs>,
}

/// Every outcome the contract permits for the case.
pub fn permitted(case: &Case, sem: &Semantics) -> BTreeSet<Outcome> {
    let mut frontier: Vec<(Engine, Vec<Obs>)> = vec![(Engine::new(case.procs, sem.clone()), vec![])];
    for (p, op) in &case.steps {
        let kind = case.kinds.get(*p).map(String::as_str).unwrap_or("dbapi");
        let mut next = vec![];
        for (e, obs) in frontier {
            if let Some(what) = refused_by_driver(kind, op) {
                let mut obs2 = obs.clone();
                obs2.push(Obs::Refused { what });
                next.push((e, obs2));
                continue;
            }
            for (e2, o) in e.step(*p, op) {
                let mut obs2 = obs.clone();
                obs2.push(o);
                next.push((e2, obs2));
            }
        }
        frontier = next;
    }
    frontier.into_iter().map(|(e, obs)| {
        let mut finals: Vec<Obs> = case.observe.iter().map(|n| Obs::Value { value: e.g.get(n).cloned() }).collect();
        for t in &case.observe_tables {
            finals.push(e.select(t));
        }
        Outcome { obs, finals }
    }).collect()
}

/// The named mutants of the contract: each must be killed by at least one differential case.
pub fn mutants() -> Vec<(&'static str, Semantics)> {
    let d = Semantics::default();
    vec![
        ("unlock-immediate-in-txn", Semantics { unlock_deferred_in_txn: false, ..d.clone() }),
        ("rollback-one-undoes-all", Semantics { rollback_one_is_one_level: false, ..d.clone() }),
        ("incr-rolled-back", Semantics { incr_survives_rollback: false, ..d.clone() }),
        ("no-dirty-reads", Semantics { dirty_reads: false, ..d.clone() }),
        ("flat-lock-names", Semantics { hierarchical_locks: false, ..d.clone() }),
        ("shared-conflicts-shared", Semantics { shared_compatible: false, ..d.clone() }),
        ("non-incremental-locks", Semantics { incremental_locks: false, ..d.clone() }),
        ("sql-start-unless-sql-owns", Semantics { sql_start: SqlStart::UnlessSqlOwns, ..d.clone() }),
        ("sql-start-always", Semantics { sql_start: SqlStart::Always, ..d.clone() }),
        ("sql-commit-ends-all (product premise, 2026.3)", Semantics { sql_commit: Ends::AllLevels, ..d.clone() }),
        ("sql-rollback-ends-all (product premise, 2026.3)", Semantics { sql_rollback: Ends::AllLevels, ..d.clone() }),
        ("driver-rollback-one-level", Semantics { drv_rollback: Ends::OneLevel, ..d.clone() }),
        ("driver-commit-ends-all", Semantics { drv_commit: Ends::AllLevels, ..d.clone() }),
        ("dml-ignores-row-locks", Semantics { dml_waits_on_row_lock: false, ..d.clone() }),
        ("stop-commits", Semantics { stop_rolls_back: false, ..d.clone() }),
        ("rollback-physical", Semantics { rollback_physical: true, ..d.clone() }),
        ("ppg-rolled-back", Semantics { ppg_rolled_back: true, ..d.clone() }),
    ]
}

pub fn mutant(name: &str) -> Option<Semantics> {
    mutants().into_iter().find(|(n, _)| *n == name || n.starts_with(name)).map(|(_, s)| s)
}
