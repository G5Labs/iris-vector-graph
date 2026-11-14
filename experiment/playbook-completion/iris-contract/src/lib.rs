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
//! Extension (round r3, playbook §3.2 coverage of the module lanes' engine features): a functional index on the
//! table F (an `%iFind.Index.Basic` index, the only `%Library.FunctionalIndex` subclass usable without compiling a
//! class) whose entries are written by the row's statement; `%NOINDEX` inserts and `BUILD INDEX`; DDL
//! (CREATE / DROP TABLE, ALTER TABLE ADD COLUMN) and its relation to an open transaction; the SQL encodings of NULL
//! and the empty string on the two client paths; statement-level atomicity of a multi-row INSERT ... SELECT;
//! `$ORDER` subscript collation; `SELECT *` column order; `SELECT $TLEVEL`; `$ZSTRIP` character classes; and the
//! availability of the vector SQL functions and of `$VECTOR` values in globals.
//!
//! Outside the subset (refused by `Op::Unsupported` and never claimed): ECP/mirroring and multi-node, journal
//! restore after a crash, SQL isolation levels other than the default, lock escalation thresholds, %NOLOCK /
//! %NOJOURN, HNSW vector index maintenance, iFind's word dictionary and ranking, and timing. Each is listed in
//! CONTRACT.md with the modules that rely on it.
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
    /// The client path driving this process: "dbapi" (default) or "term". Decides how values are bound and read.
    #[serde(default)]
    pub kind: String,
}

impl Proc {
    pub fn new() -> Proc {
        Proc { alive: true, tlevel: 0, sqlflag: false, autocommit: true, undo: vec![], ppg_undo: vec![],
               locks: BTreeMap::new(), ppg: BTreeMap::new(), pending: None, kind: "dbapi".into() }
    }
    fn term(&self) -> bool {
        self.kind == "term"
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
    /// The driver's `setAutoCommit(True)` with a transaction open commits like `commit()` (observed in round r4,
    /// rand-stmt-9091-9/-15, and env/explore-9); the mutant only sets the flag.
    pub autocommit_on_commits: bool,
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
    // ------------------------------------------------------------------ extension (r3)
    /// A functional index's entries are written by the row's statement in the row's process and transaction:
    /// visible at once to other processes, undone with the row (mutant: written outside the transaction).
    pub fx_in_row_txn: bool,
    /// `INSERT %NOINDEX` writes the row and no index entry (mutant: the hint is ignored).
    pub noindex_skips_index: bool,
    /// `INSERT %NOCHECK` of a key already present (unique check skipped).
    pub nocheck_dup: NoCheckDup,
    /// DDL (CREATE / DROP TABLE, ALTER TABLE) issued inside a transaction is undone by its rollback (observed on
    /// both client paths, explore-5 J4; the mutant is the common reading that DDL is not transactional).
    pub ddl_rolled_back: bool,
    /// What DDL does to the issuing process's open transaction.
    pub ddl_txn: DdlTxn,
    /// A DB-API parameter bound to Python '' is stored as SQL NULL (mutant) or as the empty string.
    pub dbapi_empty_param_null: bool,
    /// An ObjectScript `%ExecDirect` parameter "" is stored as SQL NULL (P-0706) or as the empty string (mutant).
    pub os_empty_param_null: bool,
    /// An ObjectScript result set reads the SQL empty string as $Char(0) (mutant: as "").
    pub os_reads_empty_as_c0: bool,
    /// `COALESCE(v, '') = COALESCE(?, '')` treats NULL and '' alike on both sides (mutant: '' stored as $Char(0)
    /// does not equal the '' COALESCE gives for NULL).
    pub coalesce_folds_null_empty: bool,
    /// A failing multi-row statement undoes its own earlier rows (statement atomicity; mutant: keeps them).
    pub statement_atomic: bool,
    /// With autocommit off at level 0, a DML statement that fails still opens the transaction (observed, D5).
    pub failed_dml_opens_txn: bool,
    /// With autocommit off at level 0, an UPDATE / DELETE that finds no row opens the transaction (mutant;
    /// observed: it does not, explore-5 J5).
    pub empty_dml_opens_txn: bool,
    /// `BUILD INDEX` writes are part of the issuing process's transaction (mutant; observed: they are not).
    pub build_index_in_txn: bool,
    /// After `BUILD INDEX` on a table, a DB-API INSERT (index-maintaining, not %NOINDEX) of a key already present
    /// raises DataError <LIST ERROR> instead of SQLCODE -119 (observed: round r5 rand-fx-6061-1 / -21,
    /// env/explore-10; the mutant reports -119).
    pub rebuilt_dup_list_error: bool,
    /// `$ORDER` visits canonical numeric subscripts first, in numeric order, then strings (mutant: string order).
    pub numeric_collation: bool,
    /// `SELECT *` column order.
    pub select_star: StarOrder,
    /// `ALTER TABLE ADD COLUMN` appends the column at the end of `SELECT *` (mutant: inserts it first).
    pub add_column_last: bool,
    /// A `SELECT` with the driver's autocommit off opens a transaction (mutant; validated: it does not).
    pub select_opens_txn: bool,
    /// `VECTOR_L2` exists on this engine (the product's premise P-1710; mutant).
    pub vector_l2_available: bool,
    /// A `$VECTOR` element SET in a global is undone by a rollback like any SET.
    pub vector_set_rolled_back: bool,
    /// The Native API can read a `$VECTOR` value (mutant; observed: `get` raises <LIST ERROR>).
    pub vector_native_readable: bool,
    /// `$ZSTRIP` class C: control characters.
    pub zstrip_c: ZClassC,
    /// `$ZSTRIP` class W: whitespace.
    pub zstrip_w: ZClassW,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum NoCheckDup {
    /// A second row with the same key is written.
    SecondRow,
    /// The insert fails with -119 anyway (mutant: the hint does not skip the unique check).
    Fails,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum DdlTxn {
    /// The open transaction stays open; its earlier writes are still undone by a later rollback.
    Untouched,
    /// The DDL commits every open level first (Oracle-style implicit commit; mutant or observed).
    CommitsAll,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum StarOrder {
    Declared,
    Alphabetical,
    IdFirst,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ZClassC {
    /// 0-31 and 127-159.
    C0C1,
    /// 0-31 and 127 only (mutant).
    AsciiOnly,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ZClassW {
    /// The validated whitespace set (see `zstrip_class`).
    Observed,
    /// The space character only (mutant).
    SpaceOnly,
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
            autocommit_on_commits: true,
            dml_waits_on_row_lock: true,
            stop_rolls_back: true,
            rollback_physical: false,
            ppg_rolled_back: false,
            fx_in_row_txn: true,
            noindex_skips_index: true,
            nocheck_dup: NoCheckDup::SecondRow,
            ddl_rolled_back: true,
            ddl_txn: DdlTxn::Untouched,
            dbapi_empty_param_null: false,
            os_empty_param_null: true,
            os_reads_empty_as_c0: true,
            coalesce_folds_null_empty: true,
            statement_atomic: true,
            failed_dml_opens_txn: true,
            empty_dml_opens_txn: false,
            build_index_in_txn: false,
            rebuilt_dup_list_error: true,
            numeric_collation: true,
            select_star: StarOrder::Declared,
            add_column_last: true,
            select_opens_txn: false,
            vector_l2_available: false,
            vector_set_rolled_back: true,
            vector_native_readable: false,
            zstrip_c: ZClassC::C0C1,
            zstrip_w: ZClassW::Observed,
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

/// The row lock of the row (k, tag): row locks name row ids, so a second row with the same key (a %NOCHECK or
/// %NOINDEX duplicate) has its own lock, unrelated to the first row's.
pub fn row_lock_at(table: &str, k: &str, tag: &str) -> Node {
    if tag == "#1" { row_lock(table, k) } else { row_lock(table, &format!("{k}{tag}")) }
}

/// A row of `table` with key `k`: the first row of a key is `row_node` (tag "#1"); further rows with the same key
/// (tag "#n", n >= 2) exist only after `%NOCHECK`, or after a `%NOINDEX` row left the key out of the unique index.
pub fn row_at(table: &str, k: &str, tag: &str) -> Node {
    if tag == "#1" {
        row_node(table, k)
    } else {
        Node { root: format!("^SQL.{table}"), subs: vec![k.to_string(), tag.to_string()] }
    }
}

/// The unique (primary key) index entry of the row (k, tag). Unique checks and by-key UPDATE / DELETE go through it.
pub fn pk_node(table: &str, k: &str, tag: &str) -> Node {
    Node { root: format!("^PK.{table}"), subs: vec![k.to_string(), tag.to_string()] }
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
    Insert {
        table: String,
        k: String,
        v: String,
        /// `INSERT %NOINDEX`
        #[serde(default, skip_serializing_if = "is_false")]
        noindex: bool,
        /// `INSERT %NOCHECK`
        #[serde(default, skip_serializing_if = "is_false")]
        nocheck: bool,
    },
    Update { table: String, k: String, v: String },
    Delete { table: String, k: String },
    Select { table: String },
    /// Stop another process (control connection); the case waits until it is gone.
    Terminate { target: usize },
    /// Observe a pending operation of this process: done (with its result) or still blocked.
    Await,
    Unsupported { what: String },
    // ------------------------------------------------------------------ extension (r3)
    /// The keys of the rows the functional index of `table` lists for `word` (`%ID %FIND search_index`); an
    /// entry whose row is gone reads as "?".
    Find { table: String, word: String },
    /// `BUILD INDEX FOR TABLE table`: purge the index and rebuild it from the rows.
    BuildIndex { table: String },
    CreateTable { table: String },
    DropTable { table: String },
    TableExists { table: String },
    AddColumn { table: String, col: String },
    /// `SELECT *`: the column names in order.
    SelectStar { table: String },
    /// Write a row of table E with `v` (None: NULL) bound as a parameter (`literal` false) or as an SQL literal.
    PutE {
        k: String,
        v: Option<String>,
        #[serde(default, skip_serializing_if = "is_false")]
        literal: bool,
    },
    /// Read a row of E: the client's value and whether SQL says `v IS NULL`.
    GetE { k: String },
    /// The product's graph guard: `SELECT COUNT(*) FROM E WHERE COALESCE(v, '') = COALESCE(?, '')`, `v` bound as a
    /// parameter on the process's client path.
    MatchE { v: Option<String> },
    /// `INSERT INTO to (k, v) SELECT k, v FROM from`
    InsertSelect { from: String, to: String },
    /// The subscripts under `node` in `$ORDER` order.
    Order { node: Node },
    /// `SELECT $TLEVEL`
    SqlTLevel,
    /// A vector SQL function on two fixed vectors ((1,0) and (0.6,0.8)), rounded to 4 places.
    SqlFn { name: String },
    /// `SET $VECTOR(node, i, "double") = x`
    VecSet { node: Node, i: u32, x: String },
    /// `$VECTOR(node, i)`
    VecGet { node: Node, i: u32 },
    /// `$ZSTRIP(s, mask, rem)` on the code points `s`; observes the code points of the result.
    ZStrip {
        s: Vec<u32>,
        mask: String,
        #[serde(default)]
        rem: String,
    },
    /// The code points 0..=65535 that `$ZSTRIP($CHAR(i), "*" _ class)` removes, as ranges.
    ZClass { class: String },
}

fn is_false(b: &bool) -> bool {
    !*b
}

/// The table an SQL operation names (TableExists excluded: the catalog answers it), for the ghost-table refusal.
fn op_table(op: &Op) -> Option<&str> {
    match op {
        Op::Insert { table, .. } | Op::Update { table, .. } | Op::Delete { table, .. } | Op::Select { table }
        | Op::Find { table, .. } | Op::BuildIndex { table } | Op::CreateTable { table } | Op::DropTable { table }
        | Op::AddColumn { table, .. } | Op::SelectStar { table } => Some(table),
        Op::InsertSelect { to, .. } => Some(to),
        _ => None,
    }
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
    Keys { keys: Vec<String> },
    Cell { value: Option<String>, null: bool },
    Subs { subs: Vec<String> },
    Cols { cols: Vec<String> },
    Codes { codes: Vec<u32> },
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Engine {
    pub g: BTreeMap<Node, String>,
    pub procs: Vec<Proc>,
    pub sem: Semantics,
}

/// The tables the driver creates before every case (table name -> declared columns).
pub fn initial_tables() -> Vec<(&'static str, &'static str)> {
    vec![("T", "k,v"), ("F", "k,v"), ("S", "k,v"), ("E", "k,v"), ("C", "zeta,alpha,mid,k")]
}

/// The tables DDL cases create and drop (the driver drops them before every case).
pub const DDL_TABLES: [&str; 2] = ["D1", "D2"];

fn cat_node(t: &str) -> Node {
    Node { root: "#cat".into(), subs: vec![t.to_string()] }
}

fn cols_node(t: &str) -> Node {
    Node { root: "#cols".into(), subs: vec![t.to_string()] }
}

/// The functional index's entry for `word` of the row (k, tag).
pub fn idx_node(table: &str, word: &str, k: &str, tag: &str) -> Node {
    Node { root: format!("^IDX.{table}"), subs: vec![word.to_string(), k.to_string(), tag.to_string()] }
}

/// The table carrying the functional (iFind) index.
fn indexed(table: &str) -> bool {
    table == "F"
}

/// SQL NULL as stored in the model's row value (row values are otherwise the SQL string itself).
pub const NULL_CELL: &str = "\u{1}NULL";
/// A `$VECTOR` value in a global: the prefix, then `i=x` elements separated by ';'.
const VEC_PREFIX: &str = "\u{2}vec:";

/// The words a functional (iFind Basic) index takes from a value: split on spaces, lower case.
fn words(v: &str) -> BTreeSet<String> {
    v.split_whitespace().map(|w| w.to_lowercase()).collect()
}

impl Engine {
    pub fn new(nprocs: usize, sem: Semantics) -> Engine {
        let mut g = BTreeMap::new();
        for (t, cols) in initial_tables() {
            g.insert(cat_node(t), "1".to_string());
            g.insert(cols_node(t), cols.to_string());
        }
        Engine { g, procs: (0..nprocs).map(|_| Proc::new()).collect(), sem }
    }

    pub fn with_kinds(kinds: &[String], nprocs: usize, sem: Semantics) -> Engine {
        let mut e = Engine::new(nprocs, sem);
        for (i, k) in kinds.iter().enumerate() {
            if i < e.procs.len() {
                e.procs[i].kind = k.clone();
            }
        }
        e
    }

    pub fn table_exists(&self, t: &str) -> bool {
        self.g.contains_key(&cat_node(t))
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
                if node.root == "#cat" || node.root == "#cols" {
                    // DDL undone by the rollback: a statement a process compiled against the table while the DDL
                    // was in effect keeps the undone definition (explore-4 B1, explore-6 K2, smoke alter case);
                    // that process's later use of the table (TableExists aside) is outside the subset
                    let t = node.subs[0].clone();
                    let seen: Vec<String> = self.g.keys()
                        .filter(|n| n.root == "#ddlseen" && n.subs[0] == t).map(|n| n.subs[1].clone()).collect();
                    for q in seen {
                        self.g.insert(Node { root: "#ghost".into(), subs: vec![t.clone(), q] }, "1".into());
                    }
                }
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
        let open: BTreeSet<String> = self.procs.iter().flat_map(|q| q.undo.iter().flatten())
            .filter(|(n, _, _)| n.root == "#cat" || n.root == "#cols").map(|(n, _, _)| n.subs[0].clone()).collect();
        self.g.retain(|n, _| n.root != "#ddlseen" || open.contains(&n.subs[0]));
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

    /// The tags of the rows with key `k` (main row "#1", further rows "#n").
    fn row_tags(&self, table: &str, k: &str) -> Vec<String> {
        let root = format!("^SQL.{table}");
        self.g.keys().filter(|n| n.root == root && !n.subs.is_empty() && n.subs[0] == k)
            .map(|n| n.subs.get(1).cloned().unwrap_or_else(|| "#1".into())).collect()
    }

    /// The tags of the rows with key `k` that the unique index lists.
    fn pk_tags(&self, table: &str, k: &str) -> Vec<String> {
        let root = format!("^PK.{table}");
        self.g.keys().filter(|n| n.root == root && n.subs.len() == 2 && n.subs[0] == k).map(|n| n.subs[1].clone())
            .collect()
    }

    /// Every row of the table as (k, tag, value).
    fn all_rows(&self, table: &str) -> Vec<(String, String, String)> {
        let root = format!("^SQL.{table}");
        self.g.iter().filter(|(n, _)| n.root == root && !n.subs.is_empty())
            .map(|(n, v)| (n.subs[0].clone(), n.subs.get(1).cloned().unwrap_or_else(|| "#1".into()), v.clone()))
            .collect()
    }

    /// Write a new row (k, value) of `table` as one statement's effect: the row, its unique-index entry and its
    /// functional-index entries, unless `%NOINDEX`. The first free tag is the row's slot.
    fn put_row(&mut self, p: usize, table: &str, k: &str, v: &str, noindex: bool) -> String {
        let tags = self.row_tags(table, k);
        let tag = (1..).map(|i| format!("#{i}")).find(|t| !tags.contains(t)).unwrap();
        self.write(p, &row_at(table, k, &tag), Some(v.to_string()), true);
        if !(noindex && self.sem.noindex_skips_index) {
            self.write(p, &pk_node(table, k, &tag), Some("1".into()), true);
        }
        if indexed(table) {
            self.index_row(p, table, k, &tag, None, Some(v), noindex);
        }
        tag
    }

    /// Run one DML statement's effect, assuming its row lock is available. Statement-level transaction: at level
    /// 0 with autocommit on, the statement is its own transaction; with autocommit off it opens one SQL owns.
    /// INSERT checks uniqueness through the unique index (`%NOCHECK` skips the check); UPDATE / DELETE by key find
    /// their rows through it. By-key access to a key some row of which is in no index (`%NOINDEX`) is outside the
    /// subset (the plan decides whether such a row is reached).
    fn dml(&mut self, p: usize, table: &str, k: &str, new: Option<&str>, insert: bool, hints: (bool, bool)) -> Obs {
        let (noindex, nocheck) = hints;
        if !self.table_exists(table) {
            return Obs::SqlError { sqlcode: -30 };
        }
        if insert {
            if nocheck && self.rebuilt(table) {
                return Obs::Refused { what: "INSERT %NOCHECK on a table BUILD INDEX rebuilt".into() };
            }
            let skip_check = nocheck && self.sem.nocheck_dup == NoCheckDup::SecondRow;
            if !skip_check && self.row_tags(table, k).len() > 1 {
                // explore-5 J3: with several rows already holding the key, the unique check's failure reaches the
                // DB-API client as <LIST ERROR> (DataError), not SQLCODE -119; not modelled
                return Obs::Refused { what: "unique check on a key that already has several rows".into() };
            }
            if !self.pk_tags(table, k).is_empty() && !skip_check {
                if self.rebuilt(table) && !noindex && !self.procs[p].term() && self.sem.rebuilt_dup_list_error {
                    // after BUILD INDEX on the table, an index-maintaining INSERT of a present key reaches the
                    // DB-API as DataError <LIST ERROR>; the row is not written; ObjectScript still sees -119, and so
                    // does an INSERT %NOINDEX (env/explore-10; round r5 rand-fx-6061-1 and -21)
                    if self.procs[p].tlevel == 0 && !self.procs[p].autocommit {
                        return Obs::Refused { what: "autocommit-off failure after BUILD INDEX".into() };
                    }
                    return Obs::Error { error: "<LIST ERROR>".into() };
                }
                self.failed_stmt(p);
                return Obs::SqlError { sqlcode: -119 };
            }
            let implicit = self.stmt_begin(p);
            let tag = self.put_row(p, table, k, new.unwrap_or_default(), noindex);
            self.stmt_end(p, implicit, table, &[(k.to_string(), tag)]);
            return Obs::Count { rowcount: 1 };
        }
        let targets = self.pk_tags(table, k);
        let rows = self.row_tags(table, k);
        if targets.len() != rows.len() || rows.len() > 1 {
            // explore-5 J3: which of several rows with one key a by-key statement reaches depends on the plan
            return Obs::Refused { what: "by-key DML on a key with several rows or a row in no index".into() };
        }
        if targets.is_empty() {
            if self.sem.empty_dml_opens_txn {
                self.failed_stmt(p);
            }
            return Obs::Count { rowcount: 0 };
        }
        let implicit = self.stmt_begin(p);
        for tag in &targets {
            let rn = row_at(table, k, tag);
            let old = self.g.get(&rn).cloned();
            self.write(p, &rn, new.map(|s| s.to_string()), true);
            if new.is_none() {
                self.write(p, &pk_node(table, k, tag), None, true);
            }
            if indexed(table) {
                self.index_row(p, table, k, tag, old.as_deref(), new, false);
            }
        }
        let locked: Vec<(String, String)> = targets.iter().map(|t| (k.to_string(), t.clone())).collect();
        self.stmt_end(p, implicit, table, &locked);
        Obs::Count { rowcount: targets.len() as i64 }
    }

    fn select(&self, table: &str) -> Obs {
        if !self.table_exists(table) {
            return Obs::SqlError { sqlcode: -30 };
        }
        // a full scan (%IGNOREINDEX *): every row, indexed or not; duplicate keys ordered by value
        let mut rows: Vec<(String, String)> = self.all_rows(table).into_iter().map(|(k, _, v)| (k, v)).collect();
        rows.sort();
        Obs::Rows { rows }
    }

    /// The functional index's entries for a row whose value goes from `old` to `new` (None: no row). Written by the
    /// row's statement; logged in the row's transaction unless the clause is mutated.
    fn index_row(&mut self, p: usize, table: &str, k: &str, tag: &str, old: Option<&str>, new: Option<&str>,
                 noindex: bool) {
        let logged = self.sem.fx_in_row_txn;
        if let Some(o) = old {
            for w in words(o) {
                let n = idx_node(table, &w, k, tag);
                if self.g.contains_key(&n) {
                    self.write(p, &n, None, logged);
                }
            }
        }
        if let Some(v) = new {
            if !(noindex && self.sem.noindex_skips_index) {
                for w in words(v) {
                    self.write(p, &idx_node(table, &w, k, tag), Some("1".into()), logged);
                }
            }
        }
    }

    fn find(&self, table: &str, word: &str) -> Obs {
        if !self.table_exists(table) {
            return Obs::SqlError { sqlcode: -30 };
        }
        let root = format!("^IDX.{table}");
        let w = word.to_lowercase();
        let mut keys: Vec<String> = self.g.keys().filter(|n| n.root == root && n.subs.len() == 3 && n.subs[0] == w)
            .map(|n| if self.g.contains_key(&row_at(table, &n.subs[1], &n.subs[2])) { n.subs[1].clone() } else { "?".into() })
            .collect();
        keys.sort();
        Obs::Keys { keys }
    }

    /// `BUILD INDEX FOR TABLE`: purge every index of the table and rebuild it from the rows. Observed: not part of
    /// the issuing process's transaction (round r3 exploration, A7: the rebuilt entries survive its rollback).
    /// BUILD INDEX ran on the table since its storage was last emptied.
    fn rebuilt(&self, table: &str) -> bool {
        self.g.contains_key(&Node { root: "#built".into(), subs: vec![table.to_string()] })
    }

    fn build_index(&mut self, p: usize, table: &str) -> Obs {
        if !self.table_exists(table) {
            return Obs::SqlError { sqlcode: -30 };
        }
        let own = self.procs[p].locks.keys().any(|n| n.root == format!("#row.{table}"));
        if own || self.others_hold_rows(p, table) {
            // the extent cannot be locked exclusively (explore-5 J2 / J2b: SQLCODE -400, ERROR #5798)
            return Obs::SqlError { sqlcode: -400 };
        }
        let logged = self.sem.build_index_in_txn;
        self.g.insert(Node { root: "#built".into(), subs: vec![table.to_string()] }, "1".into());
        let (pr, ir) = (format!("^PK.{table}"), format!("^IDX.{table}"));
        let old: Vec<Node> = self.g.keys().filter(|n| n.root == pr || n.root == ir).cloned().collect();
        for n in old {
            self.write(p, &n, None, logged);
        }
        for (k, tag, v) in self.all_rows(table) {
            self.write(p, &pk_node(table, &k, &tag), Some("1".into()), logged);
            if indexed(table) {
                for w in words(&v) {
                    self.write(p, &idx_node(table, &w, &k, &tag), Some("1".into()), logged);
                }
            }
        }
        Obs::Ok
    }

    // ------------------------------------------------------------------------------------------- DDL

    /// The catalog lives in model nodes (#cat, #cols) so the (mutant) transactional reading reuses the undo log.
    fn ddl_begin(&mut self, p: usize) {
        if self.sem.ddl_txn == DdlTxn::CommitsAll {
            while self.procs[p].tlevel > 0 {
                self.commit_top(p);
            }
        }
    }

    fn create_table(&mut self, p: usize, t: &str) -> Obs {
        if self.table_exists(t) {
            return Obs::SqlError { sqlcode: -201 };
        }
        self.ddl_begin(p);
        let logged = self.sem.ddl_rolled_back;
        self.write(p, &cat_node(t), Some("1".into()), logged);
        self.write(p, &cols_node(t), Some("k,v".into()), logged);
        Obs::Ok
    }

    /// Another process holds a row lock of the table (an open transaction wrote one of its rows).
    fn others_hold_rows(&self, p: usize, t: &str) -> bool {
        let root = format!("#row.{t}");
        self.procs.iter().enumerate().any(|(q, pr)| q != p && pr.alive && pr.locks.keys().any(|n| n.root == root))
    }

    fn drop_table(&mut self, p: usize, t: &str) -> Obs {
        if !self.table_exists(t) {
            return Obs::SqlError { sqlcode: -30 };
        }
        if self.others_hold_rows(p, t) {
            // the table lock is not granted within the lock timeout (explore-4 B5: -110 after 10 s)
            return Obs::SqlError { sqlcode: -110 };
        }
        self.ddl_begin(p);
        let logged = self.sem.ddl_rolled_back;
        self.write(p, &cat_node(t), None, logged);
        self.write(p, &cols_node(t), None, logged);
        let (rr, pr, ir) = (format!("^SQL.{t}"), format!("^PK.{t}"), format!("^IDX.{t}"));
        let data: Vec<Node> = self.g.keys().filter(|n| n.root == rr || n.root == pr || n.root == ir).cloned().collect();
        for n in data {
            self.write(p, &n, None, logged);
        }
        Obs::Ok
    }

    fn add_column(&mut self, p: usize, t: &str, col: &str) -> Obs {
        if !self.table_exists(t) {
            return Obs::SqlError { sqlcode: -30 };
        }
        self.ddl_begin(p);
        let cur = self.g.get(&cols_node(t)).cloned().unwrap_or_default();
        let next = if self.sem.add_column_last { format!("{cur},{col}") } else { format!("{col},{cur}") };
        let logged = self.sem.ddl_rolled_back;
        self.write(p, &cols_node(t), Some(next), logged);
        Obs::Ok
    }

    fn select_star(&self, t: &str) -> Obs {
        if !self.table_exists(t) {
            return Obs::SqlError { sqlcode: -30 };
        }
        let mut cols: Vec<String> = self.g.get(&cols_node(t)).map(|c| c.split(',').map(String::from).collect())
            .unwrap_or_default();
        match self.sem.select_star {
            StarOrder::Declared => {}
            StarOrder::Alphabetical => cols.sort(),
            StarOrder::IdFirst => cols.insert(0, "ID".into()),
        }
        Obs::Cols { cols }
    }

    // ------------------------------------------------------------------------------------------- NULL and ''

    /// The SQL value a `PutE` stores. A parameter "" is NULL or '' depending on the client path; $Char(0) is the
    /// SQL empty string (IRIS stores '' as $Char(0)).
    fn stored_cell(&self, p: usize, v: &Option<String>, literal: bool) -> String {
        match v {
            None => NULL_CELL.into(),
            Some(s) if s.is_empty() && !literal => {
                let null = if self.procs[p].term() { self.sem.os_empty_param_null } else { self.sem.dbapi_empty_param_null };
                if null { NULL_CELL.into() } else { String::new() }
            }
            Some(s) if s == "\u{0}" => String::new(),
            Some(s) => s.clone(),
        }
    }

    fn match_cells(&self, p: usize, v: &Option<String>) -> Obs {
        let param = self.stored_cell(p, v, false);
        let blank = |c: &str| c == NULL_CELL || c.is_empty();
        let n = self.all_rows("E").into_iter().filter(|(_, _, c)| {
            if self.sem.coalesce_folds_null_empty && blank(&param) { blank(c) } else { *c == param }
        }).count();
        Obs::Count { rowcount: n as i64 }
    }

    fn get_cell(&self, p: usize, k: &str) -> Obs {
        match self.g.get(&row_node("E", k)) {
            None => Obs::Rows { rows: vec![] },
            Some(c) => {
                let null = c == NULL_CELL;
                let value = if self.procs[p].term() {
                    // an ObjectScript result set: NULL reads as "", the SQL empty string as $Char(0)
                    Some(if null { String::new() } else if c.is_empty() && self.sem.os_reads_empty_as_c0 {
                        "\u{0}".into()
                    } else { c.clone() })
                } else if null { None } else { Some(c.clone()) };
                Obs::Cell { value, null }
            }
        }
    }

    // ------------------------------------------------------------------------------------------- statements

    /// Open the statement's transaction context: at level 0 with autocommit on the statement is its own
    /// transaction (returns true); with autocommit off it opens a level SQL owns.
    fn stmt_begin(&mut self, p: usize) -> bool {
        let implicit = self.procs[p].tlevel == 0 && self.procs[p].autocommit;
        if self.procs[p].tlevel == 0 && !self.procs[p].autocommit {
            self.tstart(p);
            self.procs[p].sqlflag = true;
        }
        if implicit {
            self.tstart(p);
        }
        implicit
    }

    /// `rows`: (key, tag) of the rows the statement wrote; each keeps its row lock to the outermost end.
    fn stmt_end(&mut self, p: usize, implicit: bool, table: &str, rows: &[(String, String)]) {
        if implicit {
            self.commit_top(p);
        } else {
            for (k, tag) in rows {
                let h = self.procs[p].locks.entry(row_lock_at(table, k, tag)).or_default();
                h.de += 1;
            }
        }
    }

    /// `INSERT INTO to (k, v) SELECT k, v FROM from`: rows in key order (the cases insert the source rows in key
    /// order, so this is also their row-id order). A key already in `to` fails the statement with -119; an atomic
    /// statement leaves nothing of its own behind, the mutant keeps the rows written before the failing one.
    fn insert_select(&mut self, p: usize, from: &str, to: &str) -> Obs {
        if !self.table_exists(from) || !self.table_exists(to) {
            return Obs::SqlError { sqlcode: -30 };
        }
        let src: Vec<(String, String)> = match self.select(from) {
            Obs::Rows { rows } => rows,
            _ => vec![],
        };
        let fail = src.iter().position(|(k, _)| !self.pk_tags(to, k).is_empty());
        if fail.is_some() && self.rebuilt(to) {
            return Obs::Refused { what: "INSERT ... SELECT failing on a table BUILD INDEX rebuilt".into() };
        }
        let n = match fail {
            Some(i) if self.sem.statement_atomic || i == 0 => {
                // the statement ran and failed: with autocommit off it has still opened the transaction (D5)
                self.failed_stmt(p);
                return Obs::SqlError { sqlcode: -119 };
            }
            Some(i) => i,
            None => src.len(),
        };
        let implicit = self.stmt_begin(p);
        let mut keys = vec![];
        for (k, v) in &src[..n] {
            let tag = self.put_row(p, to, k, v, false);
            keys.push((k.clone(), tag));
        }
        self.stmt_end(p, implicit, to, &keys);
        if fail.is_some() { Obs::SqlError { sqlcode: -119 } } else { Obs::Count { rowcount: n as i64 } }
    }

    /// A DML statement that failed (or found nothing) as a whole: with autocommit off at level 0 the statement
    /// still opened the transaction, if the clause says so.
    fn failed_stmt(&mut self, p: usize) {
        if self.sem.failed_dml_opens_txn && self.procs[p].tlevel == 0 && !self.procs[p].autocommit {
            self.tstart(p);
            self.procs[p].sqlflag = true;
        }
    }

    // ------------------------------------------------------------------------------------------- globals: order

    fn order(&self, node: &Node) -> Obs {
        let d = node.subs.len();
        let mut subs: Vec<String> = self.g.keys().filter(|n| n.root == node.root && n.subs.len() > d && node.covers(n))
            .map(|n| n.subs[d].clone()).collect::<BTreeSet<_>>().into_iter().collect();
        if subs.iter().any(|x| x.len() > MAX_CHARS && canonical_number(x).is_some()) {
            return Obs::Refused { what: format!("canonical numeric subscript longer than {MAX_CHARS} characters") };
        }
        if self.sem.numeric_collation {
            subs.sort_by(|a, b| collate(a, b));
        }
        Obs::Subs { subs }
    }

    // ------------------------------------------------------------------------------------------- vectors

    fn vec_set(&mut self, p: usize, node: &Node, i: u32, x: &str) -> Obs {
        let mut elems = vec_elems(self.g.get(node));
        elems.insert(i, x.to_string());
        let enc = format!("{VEC_PREFIX}{}", elems.iter().map(|(i, x)| format!("{i}={x}")).collect::<Vec<_>>().join(";"));
        let logged = self.sem.vector_set_rolled_back;
        self.write(p, node, Some(enc), logged);
        Obs::Ok
    }

    fn vec_get(&self, node: &Node, i: u32) -> Obs {
        Obs::Value { value: vec_elems(self.g.get(node)).get(&i).cloned() }
    }

    fn sql_fn(&self, name: &str) -> Obs {
        match name {
            "VECTOR_COSINE" | "VECTOR_DOT_PRODUCT" => Obs::Value { value: Some("0.6".into()) },
            "VECTOR_L2" if self.sem.vector_l2_available => Obs::Value { value: Some("0.8944".into()) },
            "VECTOR_L2" => Obs::SqlError { sqlcode: -359 },
            other => Obs::Refused { what: format!("sql_fn {other}") },
        }
    }
}

fn vec_elems(v: Option<&String>) -> BTreeMap<u32, String> {
    let mut m = BTreeMap::new();
    if let Some(body) = v.and_then(|s| s.strip_prefix(VEC_PREFIX)) {
        for part in body.split(';').filter(|s| !s.is_empty()) {
            if let Some((i, x)) = part.split_once('=') {
                if let Ok(i) = i.parse() {
                    m.insert(i, x.to_string());
                }
            }
        }
    }
    m
}

/// IRIS canonical number form of a subscript: `-`? then an integer without leading zeros (none before a fraction),
/// an optional fraction without trailing zeros; not "-0". Such a subscript collates as a number whatever its
/// magnitude (explore-7: every canonical-format string of 1 to 41 characters, far past the 64-bit range); longer
/// ones were not observed, so `order` refuses them (outside the subset).
pub const MAX_CHARS: usize = 41;

pub fn canonical_number(s: &str) -> Option<(bool, String, String)> {
    let (neg, body) = match s.strip_prefix('-') {
        Some(b) => (true, b),
        None => (false, s),
    };
    let (int, frac) = match body.split_once('.') {
        Some((i, f)) => {
            if f.is_empty() || f.ends_with('0') {
                return None;
            }
            (i, f)
        }
        None => (body, ""),
    };
    if !int.chars().all(|c| c.is_ascii_digit()) || !frac.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    if int.is_empty() && frac.is_empty() {
        return None;
    }
    if !frac.is_empty() && int == "0" {
        return None; // 0.5 is written .5
    }
    if int.len() > 1 && int.starts_with('0') {
        return None;
    }
    if neg && int == "0" && frac.is_empty() {
        return None; // -0
    }
    Some((neg, int.to_string(), frac.to_string()))
}

fn cmp_abs(a: &(bool, String, String), b: &(bool, String, String)) -> std::cmp::Ordering {
    let ai = a.1.trim_start_matches('0');
    let bi = b.1.trim_start_matches('0');
    ai.len().cmp(&bi.len()).then_with(|| ai.cmp(bi)).then_with(|| a.2.cmp(&b.2))
}

/// `$ORDER` collation of two subscripts: canonical numbers first, numerically; then strings by code point.
pub fn collate(a: &str, b: &str) -> std::cmp::Ordering {
    use std::cmp::Ordering::*;
    match (canonical_number(a), canonical_number(b)) {
        (Some(x), Some(y)) => match (x.0, y.0) {
            (false, false) => cmp_abs(&x, &y),
            (true, true) => cmp_abs(&y, &x),
            (true, false) => Less,
            (false, true) => Greater,
        },
        (Some(_), None) => Less,
        (None, Some(_)) => Greater,
        (None, None) => a.chars().map(|c| c as u32).cmp(b.chars().map(|c| c as u32)),
    }
}

/// The code points of a `$ZSTRIP` character class (the classes the product uses: C and W).
pub fn zstrip_class(sem: &Semantics, class: char, c: u32) -> bool {
    match class {
        'C' => match sem.zstrip_c {
            ZClassC::C0C1 => c <= 31 || (127..=159).contains(&c),
            ZClassC::AsciiOnly => c <= 31 || c == 127,
        },
        'W' => match sem.zstrip_w {
            ZClassW::Observed => WHITESPACE.contains(&c),
            ZClassW::SpaceOnly => c == 32,
        },
        _ => false,
    }
}

/// The W class observed on this engine (explore-5 J7: tab, space and no-break space only; LF, VT, FF and CR are not
/// whitespace for $ZSTRIP).
pub const WHITESPACE: &[u32] = &[9, 32, 160];

/// `$ZSTRIP(s, mask, rem)`: actions `*` (all), `<` (leading), `>` (trailing), `=` (contiguous duplicates of one
/// character reduced to one); classes C and W; `rem` adds characters.
pub fn zstrip(sem: &Semantics, s: &[u32], mask: &str, rem: &str) -> Vec<u32> {
    let actions: Vec<char> = mask.chars().filter(|c| "*<>=".contains(*c)).collect();
    let classes: Vec<char> = mask.chars().filter(|c| !"*<>=".contains(*c)).map(|c| c.to_ascii_uppercase()).collect();
    let remset: Vec<u32> = rem.chars().map(|c| c as u32).collect();
    let m = |c: u32| remset.contains(&c) || classes.iter().any(|k| zstrip_class(sem, *k, c));
    if actions.contains(&'*') {
        return s.iter().copied().filter(|c| !m(*c)).collect();
    }
    let mut v: Vec<u32> = s.to_vec();
    if actions.contains(&'<') {
        let i = v.iter().position(|c| !m(*c)).unwrap_or(v.len());
        v.drain(..i);
    }
    if actions.contains(&'>') {
        while v.last().map(|c| m(*c)).unwrap_or(false) {
            v.pop();
        }
    }
    if actions.contains(&'=') {
        let mut out: Vec<u32> = vec![];
        for c in v {
            if m(c) && out.last() == Some(&c) {
                continue;
            }
            out.push(c);
        }
        v = out;
    }
    v
}

pub fn ranges(sem: &Semantics, class: char) -> String {
    let mut out = vec![];
    let mut start: Option<u32> = None;
    for c in 0..=65536u32 {
        let inc = c <= 65535 && zstrip_class(sem, class, c);
        match (inc, start) {
            (true, None) => start = Some(c),
            (false, Some(s)) => {
                out.push(format!("{s}-{}", c - 1));
                start = None;
            }
            _ => {}
        }
    }
    out.join(",")
}

impl Engine {

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
                    && self.row_tags(table, k).iter().any(|t| self.conflicts(p, &row_lock_at(table, k, t), Mode::E))
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
        if let Some(t) = op_table(op) {
            if e.g.contains_key(&Node { root: "#ghost".into(), subs: vec![t.to_string(), p.to_string()] }) {
                return vec![(e, Obs::Refused { what: format!("use of {t} by a process that compiled against DDL \
                    a rollback undid") })];
            }
            let in_window = e.procs.iter().any(|q| q.undo.iter().flatten()
                .any(|(n, _, _)| (n.root == "#cat" || n.root == "#cols") && n.subs[0] == t));
            // a statement on a table the catalog lacks fails at prepare and caches nothing (explore-5 J4e)
            if in_window && e.table_exists(t)
                && !matches!(op, Op::CreateTable { .. } | Op::DropTable { .. } | Op::AddColumn { .. }) {
                e.g.insert(Node { root: "#ddlseen".into(), subs: vec![t.to_string(), p.to_string()] }, "1".into());
            }
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
                if e.procs[p].tlevel > 0 && !*on && e.procs[p].autocommit {
                    // turning autocommit off inside an open transaction was never observed (outside the subset)
                    Obs::Refused { what: "set_autocommit off inside a transaction".into() }
                } else {
                    if *on && e.procs[p].tlevel > 0 && e.sem.autocommit_on_commits {
                        // the driver commits as commit() does (env/explore-9: one level, whether autocommit was off
                        // or already on, whoever opened the level)
                        let ends = e.sem.drv_commit;
                        e.end_levels(p, ends, true);
                        e.procs[p].sqlflag = false;
                    }
                    e.procs[p].autocommit = *on;
                    Obs::Ok
                }
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
                match v {
                    // a $VECTOR value: the Native API cannot decode it (explore-4 G2: <LIST ERROR>, type 16)
                    Some(x) if x.starts_with(VEC_PREFIX) => {
                        if e.procs[p].term() {
                            Obs::Refused { what: "term get of a $VECTOR value (binary)".into() }
                        } else if e.sem.vector_native_readable {
                            Obs::Value { value: Some(x) }
                        } else {
                            Obs::Error { error: "<LIST ERROR>".into() }
                        }
                    }
                    v => Obs::Value { value: v },
                }
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
            Op::Select { table } => {
                e.select_txn(p);
                e.select(table)
            }
            Op::Find { table, word } => {
                e.select_txn(p);
                e.find(table, word)
            }
            Op::BuildIndex { table } => e.build_index(p, table),
            Op::CreateTable { table } => e.create_table(p, table),
            Op::DropTable { table } => e.drop_table(p, table),
            Op::TableExists { table } => Obs::Test { test: e.table_exists(table) },
            Op::AddColumn { table, col } => e.add_column(p, table, col),
            Op::SelectStar { table } => {
                e.select_txn(p);
                e.select_star(table)
            }
            Op::PutE { k, .. } => {
                if e.conflicts(p, &row_lock("E", k), Mode::E) {
                    // outside the subset: the E cases never write a key another process holds
                    Obs::Refused { what: "put_e on a locked key".into() }
                } else {
                    let k = k.clone();
                    e.run_dml(p, op, "E", &k)
                }
            }
            Op::GetE { k } => {
                e.select_txn(p);
                e.get_cell(p, k)
            }
            Op::MatchE { v } => {
                e.select_txn(p);
                e.match_cells(p, v)
            }
            Op::InsertSelect { from, to } => {
                let busy = e.procs.iter().enumerate().any(|(q, pr)| q != p && pr.locks.keys().any(|n| n.root.starts_with("#row.")));
                if busy {
                    Obs::Refused { what: "insert_select while another process holds row locks".into() }
                } else {
                    e.insert_select(p, from, to)
                }
            }
            Op::Order { node } => e.order(node),
            Op::SqlTLevel => {
                e.select_txn(p);
                Obs::Level { tlevel: e.procs[p].tlevel }
            }
            Op::SqlFn { name } => e.sql_fn(name),
            Op::VecSet { node, i, x } => e.vec_set(p, node, *i, x),
            Op::VecGet { node, i } => e.vec_get(node, *i),
            Op::ZStrip { s, mask, rem } => Obs::Codes { codes: zstrip(&e.sem, s, mask, rem) },
            Op::ZClass { class } => Obs::Value { value: Some(ranges(&e.sem, class.chars().next().unwrap_or('?'))) },
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

    /// A query with the driver's autocommit off at level 0: opens a transaction only under the mutant.
    fn select_txn(&mut self, p: usize) {
        if self.sem.select_opens_txn && self.procs[p].tlevel == 0 && !self.procs[p].autocommit {
            self.tstart(p);
            self.procs[p].sqlflag = true;
        }
    }

    fn run_dml(&mut self, p: usize, op: &Op, table: &str, k: &str) -> Obs {
        match op {
            Op::Insert { v, noindex, nocheck, .. } => self.dml(p, table, k, Some(v), true, (*noindex, *nocheck)),
            Op::Update { v, .. } => self.dml(p, table, k, Some(v), false, (false, false)),
            Op::Delete { .. } => self.dml(p, table, k, None, false, (false, false)),
            Op::PutE { v, literal, .. } => {
                let cell = self.stored_cell(p, v, *literal);
                self.dml(p, "E", k, Some(&cell), true, (false, false))
            }
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
        Op::SelectStar { .. } => "select_star",
        Op::PpgSet { .. } => "ppg_set",
        Op::PpgGet { .. } => "ppg_get",
        Op::LockOnly { .. } => "lock_only",
        Op::VecSet { .. } => "vec_set",
        Op::VecGet { .. } => "vec_get",
        Op::ZStrip { .. } => "z_strip",
        Op::ZClass { .. } => "z_class",
        _ => return None,
    };
    let refused = match kind {
        "term" => matches!(op, Op::DrvCommit | Op::DrvRollback | Op::SetAutocommit { .. } | Op::SelectStar { .. }),
        _ => matches!(op, Op::PpgSet { .. } | Op::PpgGet { .. } | Op::LockOnly { .. } | Op::VecSet { .. }
            | Op::VecGet { .. } | Op::ZStrip { .. } | Op::ZClass { .. }),
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
    let mut frontier: Vec<(Engine, Vec<Obs>)> = vec![(Engine::with_kinds(&case.kinds, case.procs, sem.clone()), vec![])];
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
        ("autocommit-on-keeps-txn", Semantics { autocommit_on_commits: false, ..d.clone() }),
        ("dml-ignores-row-locks", Semantics { dml_waits_on_row_lock: false, ..d.clone() }),
        ("stop-commits", Semantics { stop_rolls_back: false, ..d.clone() }),
        ("rollback-physical", Semantics { rollback_physical: true, ..d.clone() }),
        ("ppg-rolled-back", Semantics { ppg_rolled_back: true, ..d.clone() }),
        // ---------------------------------------------------------------- extension (r3)
        ("fx-outside-row-txn", Semantics { fx_in_row_txn: false, ..d.clone() }),
        ("noindex-ignored", Semantics { noindex_skips_index: false, ..d.clone() }),
        ("nocheck-still-unique", Semantics { nocheck_dup: NoCheckDup::Fails, ..d.clone() }),
        ("ddl-not-rolled-back", Semantics { ddl_rolled_back: false, ..d.clone() }),
        ("ddl-commits-open-txn", Semantics { ddl_txn: DdlTxn::CommitsAll, ..d.clone() }),
        ("dbapi-empty-param-null", Semantics { dbapi_empty_param_null: true, ..d.clone() }),
        ("objectscript-empty-param-empty", Semantics { os_empty_param_null: false, ..d.clone() }),
        ("objectscript-reads-empty-as-empty", Semantics { os_reads_empty_as_c0: false, ..d.clone() }),
        ("coalesce-c0-differs", Semantics { coalesce_folds_null_empty: false, ..d.clone() }),
        ("statement-not-atomic", Semantics { statement_atomic: false, ..d.clone() }),
        ("failed-dml-opens-nothing", Semantics { failed_dml_opens_txn: false, ..d.clone() }),
        ("empty-dml-opens-txn", Semantics { empty_dml_opens_txn: true, ..d.clone() }),
        ("build-index-in-txn", Semantics { build_index_in_txn: true, ..d.clone() }),
        ("rebuilt-table-dup-reports-119", Semantics { rebuilt_dup_list_error: false, ..d.clone() }),
        ("string-collation", Semantics { numeric_collation: false, ..d.clone() }),
        ("select-star-alphabetical", Semantics { select_star: StarOrder::Alphabetical, ..d.clone() }),
        ("select-star-id-first", Semantics { select_star: StarOrder::IdFirst, ..d.clone() }),
        ("add-column-first", Semantics { add_column_last: false, ..d.clone() }),
        ("select-opens-txn", Semantics { select_opens_txn: true, ..d.clone() }),
        ("vector-l2-available (product premise P-1710)", Semantics { vector_l2_available: true, ..d.clone() }),
        ("vector-set-not-rolled-back", Semantics { vector_set_rolled_back: false, ..d.clone() }),
        ("native-api-reads-vectors", Semantics { vector_native_readable: true, ..d.clone() }),
        ("zstrip-c-ascii-only", Semantics { zstrip_c: ZClassC::AsciiOnly, ..d.clone() }),
        ("zstrip-w-space-only", Semantics { zstrip_w: ZClassW::SpaceOnly, ..d.clone() }),
    ]
}

pub fn mutant(name: &str) -> Option<Semantics> {
    mutants().into_iter().find(|(n, _)| *n == name || n.starts_with(name)).map(|(_, s)| s)
}
