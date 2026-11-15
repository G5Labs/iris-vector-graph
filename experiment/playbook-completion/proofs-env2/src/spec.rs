//! The IRIS environment contract (iris-contract round r6, `iris-contract/src/lib.rs`; contract-2's S-1) restricted to
//! the clauses the audit's proof crates rely on, as a Verus specification.
//!
//! Scope (the Verus subset of the contract): globals (SET, KILL subtree, $GET, $DATA, $INCREMENT), process-private
//! globals, nested transactions (TSTART / TCOMMIT / TROLLBACK 1 / TROLLBACK), the SQL transaction verbs and the
//! driver's commit / rollback / autocommit, the pin's Txn_Begin / Txn_End / Txn_Undo (S-1), dynamic SQL INSERT /
//! UPDATE / DELETE by key and SELECT on keyed tables with row locks, the lock table (exclusive and shared modes,
//! hierarchical names, incremental counts, deferred release inside a transaction, immediate release, release-all,
//! non-incremental LOCK), lock waits, READ UNCOMMITTED visibility, value-based rollback and process stop.
//! Outside it (the harness reports such cases as outside the Verus subset, never as agreeing): the r6 extension
//! clauses X-* (functional index, %NOINDEX, BUILD INDEX, DDL, NULL encodings, INSERT ... SELECT, $ORDER, SELECT *,
//! vectors, $ZSTRIP), contract-2's embedded-SQL operations (E-1) and X2 clauses.
//!
//! Permitted-outcome structure: `outcomes(sem, u, s, p, op)` is every permitted (next state, observation) of one
//! operation; it has two elements exactly at the contract's Freedom (an INSERT of a key whose row another open
//! transaction deleted: it may wait or proceed), one otherwise. `step(.., choice)` selects one of them; `run` drives a
//! case with a sequence of choices and `permitted` is the set of outcomes over every choice sequence.
//!
//! Representation (equivalent to the contract's for the subset; checked by the differential harness): every global
//! node and every SQL row a case names is a *cell* of a finite universe `U` (a global cell carries its path, root then
//! subscripts; a row cell its table); values are interned (`Val::Num(n)` for the canonical decimal form of an i64,
//! `Val::Str(id)` for any other string); a process's undo log is one flat sequence with a mark per open level (the
//! contract's per-level lists; an inner commit appends its level to its parent's, which is removing the mark); row
//! locks are one flag per row cell (the contract's deferred exclusive lock on `#row.T(k)`, which no user lock name
//! relates to); a unique index entry exists exactly when its row does in the subset, so uniqueness reads the row.
//! Arithmetic beyond the machine types (lock counts, $INCREMENT, levels) answers `Err(Overflow)` and changes nothing;
//! the harness counts such answers (none occur in the recorded rounds).
use vstd::prelude::*;
use crate::ext::*;

verus! {

// ------------------------------------------------------------------------------------------------ vocabulary

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Val {
    Num(i64),
    Str(usize),
    /// SQL NULL as a stored cell (the contract's NULL_CELL).
    Null,
    /// The empty string.
    Empty,
    /// The string $Char(0).
    Nul,
}

/// A parameter of the NULL-encoding operations (X-NULL), as the client binds it.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Param { PNull, PEmpty, PNul, PV(Val) }

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mode { E, S }

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Kind { Dbapi, Term }

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Ends { One, All }

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SqlStartSem { UnlessSqlOwns, NothingIfOpen, Always }

/// The contract's Freedom (INSERT over another transaction's uncommitted DELETE): both outcomes permitted (validated),
/// or one of them only (seeded readings).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum FreedomSem { Both, WaitOnly, GoOnly }

/// The clause switches. Field for field the contract's `Semantics` (r6 core and the autocommit-off statement switches,
/// contract-2's S-1 switch), plus readings seeded for the Verus model (last group). `clauses::validated()` is the
/// validated contract; each other value is a mutant.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Sem {
    pub unlock_deferred: bool,
    pub rollback_one_is_one_level: bool,
    pub incr_survives: bool,
    pub dirty_reads: bool,
    pub hierarchical: bool,
    pub shared_compatible: bool,
    pub incremental: bool,
    pub sql_start: SqlStartSem,
    pub sql_commit: Ends,
    pub sql_rollback: Ends,
    pub drv_rollback: Ends,
    pub drv_commit: Ends,
    pub autocommit_on_commits: bool,
    pub dml_waits: bool,
    pub stop_rolls_back: bool,
    pub rollback_physical: bool,
    pub ppg_rolled_back: bool,
    pub failed_dml_opens_txn: bool,
    pub empty_dml_opens_txn: bool,
    pub select_opens_txn: bool,
    pub sqlproc_levels_end_with_statement: bool,
    // ------------------------------------------------ readings seeded for the Verus model (not contract switches)
    /// The contract's Freedom.
    pub freedom: FreedomSem,
    /// INSERT of a key another open transaction inserted waits for it (the PostgreSQL reading) instead of -119.
    pub insert_dup_waits: bool,
    /// A DML statement inside a transaction keeps its row lock to the outermost end (mutant: to the statement's end).
    pub row_lock_held: bool,
    /// A waiting lock is granted at `Await` once nothing conflicts (mutant: never).
    pub lock_wait_grants: bool,
    /// A process stop rolls back every level (mutant: only the top level).
    pub stop_all_levels: bool,
    /// KILL is logged and undone by a rollback (mutant: not logged).
    pub kill_logged: bool,
    /// SQL SELECT reads uncommitted rows (mutant: committed rows only; contract-2's sql_select_committed_only).
    pub select_dirty: bool,
    // ------------------------------------------------ proofs-env2: the r6 extension clauses and contract-2's E-1
    pub vector_l2_available: bool,
    pub zstrip_c_c1: bool,
    pub zstrip_w_observed: bool,
    pub numeric_collation: bool,
    pub dbapi_empty_param_null: bool,
    pub os_empty_param_null: bool,
    pub os_reads_empty_as_c0: bool,
    pub coalesce_folds_null_empty: bool,
    pub statement_atomic: bool,
    pub emb_select_committed_only: bool,
    pub emb_ignores_autocommit: bool,
    pub emb_empty_host_null: bool,
    pub emb_ignores_row_locks: bool,
    pub emb_own_txn: bool,
    pub maxlen_enforced: bool,
    // X2-BATCH / X2-IOU (contract-2)
    pub batch_raises_on_dup: bool,
    pub batch_atomic: bool,
    pub batch_single_row_skips: bool,
    pub iou_retries_insert: bool,
    pub iou_ignores_row_locks: bool,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ErrK { Command, Dead, Busy, NothingPending, BadPending, Overflow }

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum RefK {
    AutocommitOffInTxn, DrvCommitTerm, DrvRollbackTerm, SetAutocommitTerm, PpgSetDbapi, PpgGetDbapi, LockOnlyDbapi,
    // proofs-env2
    ZStripDbapi, ZClassDbapi, PutELocked, InsertSelectBusy, InsertSelectNoTwin, OrderTooLong, SqlFnOther, EmbAssertHeld,
    UpsertTerm, InsertManyTerm, BatchHeld, UpsertFreedom,
}

/// One operation of a schedule. Cells (`c`, `r`) index the universe; `r` is a row cell; `t` a table.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
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
    Set { c: usize, v: Val },
    Kill { c: usize },
    Get { c: usize },
    Data { c: usize },
    Incr { c: usize },
    PpgSet { c: usize, v: Val },
    PpgGet { c: usize },
    Lock { c: usize, mode: Mode, wait: bool },
    Unlock { c: usize, mode: Mode, immediate: bool },
    LockOnly { c: usize, wait: bool },
    ReleaseAll,
    Insert { r: usize, v: Val },
    Update { r: usize, v: Val },
    Delete { r: usize },
    Select { t: usize },
    Terminate { target: usize },
    Await,
    /// contract-2 S-1: `SELECT Graph_KG.Txn_Begin(hold)` (Txn.cls:19-30).
    SqlTxnBegin { hold: bool },
    /// contract-2 S-1: `SELECT Graph_KG.Txn_End(level)` (Txn.cls:36-45).
    SqlTxnEnd { level: u64 },
    /// contract-2 S-1: `SELECT Graph_KG.Txn_Undo(level)` (Txn.cls:49-58).
    SqlTxnUndo { level: u64 },
    // ------------------------------------------------ proofs-env2
    /// X-TLEVEL-SQL: `SELECT $TLEVEL`.
    SqlTLevel,
    /// X-VEC (functions): 0 VECTOR_COSINE, 1 VECTOR_DOT_PRODUCT, 2 VECTOR_L2, 3 another name.
    SqlFn { f: u8 },
    /// X-ZSTRIP: `$ZSTRIP(s, mask, rem)`; `a` indexes the universe's arguments.
    ZStrip { a: usize },
    /// X-ZSTRIP: the code points `$ZSTRIP($CHAR(i), "*" _ class)` removes, as ranges; `ch` the class character.
    ZClass { ch: u32 },
    /// X-ORDER: the subscripts under the global node `c`, in `$ORDER` order.
    Order { c: usize },
    /// X-NULL: write row `r` of table E with the bound (or literal) parameter.
    PutE { r: usize, v: Param, literal: bool },
    /// X-NULL: read row `r` of table E.
    GetE { r: usize },
    /// X-NULL: `SELECT COUNT(*) FROM t WHERE COALESCE(v, '') = COALESCE(?, '')`.
    MatchE { t: usize, v: Param },
    /// X-STMT: `INSERT INTO to (k, v) SELECT k, v FROM from`.
    InsertSelect { from: usize, to: usize },
    /// E-1: `RegisterDefaultNode(k)`: embedded SELECT INTO, then embedded INSERT of row `r` of N (value "").
    EmbRegister { r: usize },
    /// E-1: `RetractTemporalRows`: embedded DELETE of row `r` of R.
    EmbRetract { r: usize },
    /// E-1: `VerifyGraph`: the count of rows of table `t` (R) its embedded cursor reads.
    EmbCount { t: usize },
    /// E-1: `VectorRouteGuard`: refused if table `t` (G) has a row.
    EmbRoute { t: usize },
    /// E-1: `AssertTemporalRow`: embedded INSERT ... WHERE NOT EXISTS of row `rn` of N ("") and `rr` of R0 (`vt`);
    /// `empty`: the graph key bound as "" (else $Char(0)).
    EmbAssert { rn: usize, rr: usize, empty: bool, vt: Val },
    /// X2-IOU: `INSERT OR UPDATE` of row `r` with `v`.
    Upsert { r: usize, v: Val },
    /// X2-BATCH: DB-API `executemany` of an INSERT into table `t` over the universe's parameter rows `b`.
    InsertMany { t: usize, b: usize },
}

/// A lock hold: counts of exclusive / shared holds, and of holds released inside a transaction (kept until the
/// outermost transaction ends).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Hold { pub e: u64, pub s: u64, pub de: u64, pub ds: u64 }

/// An undo-log entry: the cell, its value before the write and the value written; `ppg` for a process-private global.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Undo { pub c: usize, pub old: Option<Val>, pub written: Option<Val>, pub ppg: bool }

pub enum Obs {
    Ok,
    Level(nat),
    Value(Option<Val>),
    Data(u8),
    Test(bool),
    /// (row cell, value) of every row of the table, in cell order (the harness renders keys and sorts as the
    /// contract does).
    Rows(Seq<(usize, Val)>),
    Count(i64),
    SqlError(i64),
    Err(ErrK),
    Blocked,
    Pending,
    Refused(RefK),
    // ------------------------------------------------ proofs-env2
    /// A subscript list (name ids, rendered by the harness).
    Subs(Seq<u64>),
    /// Code points.
    Codes(Seq<u32>),
    /// A class as code-point ranges (rendered "a-b,c-d" as a value).
    Ranges(Seq<(u32, u32)>),
    /// A row of E as the client reads it: its value (None: NULL on the DB-API) and whether SQL says NULL.
    Cell(Option<Val>, bool),
    /// A product method's error text "err:<SQLCODE>".
    ErrText(i64),
    /// VectorRouteGuard's "refused".
    RouteRefused,
    /// A vector SQL function's value: 0 "0.6", 1 "0.8944".
    FnVal(u8),
}

/// The universe of one case: per cell, its path (a global: root id then subscript ids) or its table (a row);
/// per table, whether it exists; per interned non-canonical string, the value Rust's i64 parse gives it ($INCREMENT
/// of a non-numeric string starts at 0).
pub struct U {
    pub paths: Seq<Seq<u64>>,
    pub is_row: Seq<bool>,
    pub table: Seq<usize>,
    pub texists: Seq<bool>,
    pub parse: Seq<i64>,
    // ------------------------------------------------ proofs-env2
    /// The code points of each interned name (subscripts, for `$ORDER`).
    pub names: Seq<Seq<u32>>,
    /// The arguments of the case's `$ZSTRIP` calls.
    pub zargs: Seq<ZArg>,
    /// Per row cell: its key exceeds the pin's VARCHAR(256) (contract-2 -104).
    pub long: Seq<bool>,
    /// Per row cell: its key's id (INSERT ... SELECT matches source and target rows by key).
    pub key: Seq<usize>,
    /// The parameter rows of the case's `executemany` calls (row cell, value).
    pub batches: Seq<Seq<(usize, Val)>>,
}

pub struct ZArg {
    pub s: Seq<u32>,
    pub mask: Seq<u32>,
    pub rem: Seq<u32>,
}

impl U {
    pub open spec fn n(self) -> nat { self.paths.len() }
}

pub struct Proc {
    pub alive: bool,
    pub sqlflag: bool,
    pub autocommit: bool,
    pub kind: Kind,
    /// One mark per open level: the undo-log index where the level starts. `$TLEVEL` is `marks.len()`.
    pub marks: Seq<nat>,
    pub undo: Seq<Undo>,
    pub locks: Seq<Hold>,
    pub rlocks: Seq<bool>,
    pub ppg: Seq<Option<Val>>,
    pub pending: Option<Op>,
}

pub struct State {
    pub g: Seq<Option<Val>>,
    pub procs: Seq<Proc>,
}

pub struct Case {
    pub nprocs: nat,
    pub kinds: Seq<Kind>,
    pub steps: Seq<(usize, Op)>,
    pub observe: Seq<usize>,
    pub observe_tables: Seq<usize>,
}

pub enum RunRes {
    /// The run reached a Freedom with no choice left in the sequence.
    NeedMore,
    /// Observations per step, final observations, and the number of choices used.
    Done(Seq<Obs>, Seq<Obs>, nat),
}

// ------------------------------------------------------------------------------------------------ well-formedness

pub open spec fn wf_univ(u: U) -> bool {
    &&& u.is_row.len() == u.n()
    &&& u.table.len() == u.n()
    &&& u.long.len() == u.n()
    &&& u.key.len() == u.n()
    &&& forall|c: int| 0 <= c < u.n() && u.is_row[c] ==> (u.table[c] as int) < u.texists.len()
}

pub open spec fn wf_op(u: U, op: Op) -> bool {
    match op {
        Op::Set { c, .. } | Op::Kill { c } | Op::Get { c } | Op::Data { c } | Op::Incr { c } | Op::PpgSet { c, .. }
        | Op::PpgGet { c } | Op::Lock { c, .. } | Op::Unlock { c, .. } | Op::LockOnly { c, .. } => (c as int) < u.n(),
        Op::Insert { r, .. } | Op::Update { r, .. } | Op::Delete { r } => (r as int) < u.n() && u.is_row[r as int],
        Op::Select { t } => (t as int) < u.texists.len(),
        Op::ZStrip { a } => (a as int) < u.zargs.len(),
        Op::Order { c } => (c as int) < u.n() && is_glob(u, c as int),
        Op::PutE { r, .. } | Op::GetE { r } | Op::EmbRegister { r } | Op::EmbRetract { r } => (r as int) < u.n() && u.is_row[r as int],
        Op::MatchE { t, .. } | Op::EmbCount { t } | Op::EmbRoute { t } => (t as int) < u.texists.len(),
        Op::InsertSelect { from, to } => (from as int) < u.texists.len() && (to as int) < u.texists.len(),
        Op::Upsert { r, .. } => (r as int) < u.n() && u.is_row[r as int],
        Op::InsertMany { t, b } => (t as int) < u.texists.len() && (b as int) < u.batches.len() && batch_ok(u, t, u.batches[b as int]),
        Op::EmbAssert { rn, rr, .. } => (rn as int) < u.n() && u.is_row[rn as int] && (rr as int) < u.n() && u.is_row[rr as int],
        _ => true,
    }
}

pub open spec fn wf_proc(u: U, pr: Proc) -> bool {
    &&& pr.locks.len() == u.n()
    &&& pr.rlocks.len() == u.n()
    &&& pr.ppg.len() == u.n()
    &&& forall|i: int| 0 <= i < pr.undo.len() ==> (pr.undo[i].c as int) < u.n()
    &&& (pr.pending matches Some(op) ==> wf_op(u, op))
}

pub open spec fn wf(u: U, s: State) -> bool {
    &&& s.g.len() == u.n()
    &&& u.n() <= usize::MAX
    &&& s.procs.len() <= usize::MAX
    &&& forall|q: int| 0 <= q < s.procs.len() ==> wf_proc(u, #[trigger] s.procs[q])
}

// ------------------------------------------------------------------------------------------------ small helpers

pub open spec fn level(pr: Proc) -> nat { pr.marks.len() }

pub open spec fn zero_hold() -> Hold { Hold { e: 0, s: 0, de: 0, ds: 0 } }

pub open spec fn any(h: Hold) -> bool { h.e > 0 || h.s > 0 || h.de > 0 || h.ds > 0 }

pub open spec fn excl(h: Hold) -> bool { h.e > 0 || h.de > 0 }

pub open spec fn upd(s: State, p: usize, pr: Proc) -> State {
    State { g: s.g, procs: s.procs.update(p as int, pr) }
}

pub open spec fn set_sqlflag(s: State, p: usize, b: bool) -> State {
    upd(s, p, Proc { sqlflag: b, ..s.procs[p as int] })
}

pub open spec fn set_pending(s: State, p: usize, op: Option<Op>) -> State {
    upd(s, p, Proc { pending: op, ..s.procs[p as int] })
}

pub open spec fn is_glob(u: U, c: int) -> bool { 0 <= c < u.n() && !u.is_row[c] }

/// `a` is `b` or an ancestor of it (`Node::covers`).
pub open spec fn covers(u: U, a: int, b: int) -> bool {
    &&& is_glob(u, a)
    &&& is_glob(u, b)
    &&& u.paths[a].len() <= u.paths[b].len()
    &&& u.paths[b].subrange(0, u.paths[a].len() as int) == u.paths[a]
}

pub open spec fn related(sem: Sem, u: U, a: int, b: int) -> bool {
    if sem.hierarchical { covers(u, a, b) || covers(u, b, a) } else { a == b }
}

pub open spec fn hold_conflicts(sem: Sem, h: Hold, mode: Mode) -> bool {
    match mode {
        Mode::E => any(h),
        Mode::S => excl(h) || (!sem.shared_compatible && any(h)),
    }
}

/// Another live process holds a lock on a name related to `c` that conflicts with `mode` (`Engine::conflicts`).
pub open spec fn conflicts(sem: Sem, u: U, s: State, p: usize, c: usize, mode: Mode) -> bool {
    exists|q: int, m: int|
        0 <= q < s.procs.len() && q != p && s.procs[q].alive && 0 <= m < u.n() && related(sem, u, m, c as int)
            && hold_conflicts(sem, #[trigger] s.procs[q].locks[m], mode)
}

/// Another live process holds the row lock of row cell r.
pub open spec fn row_held(s: State, p: usize, r: usize) -> bool {
    exists|q: int| 0 <= q < s.procs.len() && q != p && s.procs[q].alive && #[trigger] s.procs[q].rlocks[r as int]
}

// ------------------------------------------------------------------------------------------------ globals and the log

/// SET (or KILL of one node) by p; logged inside a transaction when `logged`.
pub open spec fn write(s: State, p: usize, c: usize, v: Option<Val>, logged: bool) -> State {
    let pr = s.procs[p as int];
    let pr2 = if logged && level(pr) > 0 {
        Proc { undo: pr.undo.push(Undo { c, old: s.g[c as int], written: v, ppg: false }), ..pr }
    } else {
        pr
    };
    State { g: s.g.update(c as int, v), procs: s.procs.update(p as int, pr2) }
}

/// KILL node: every defined cell the node covers, in cell order.
pub open spec fn kill_from(sem: Sem, u: U, s: State, p: usize, node: usize, j: nat) -> State
    decreases u.n() - j
{
    if j >= u.n() {
        s
    } else {
        let s2 = if covers(u, node as int, j as int) && s.g[j as int] is Some {
            write(s, p, j as usize, None, sem.kill_logged)
        } else {
            s
        };
        kill_from(sem, u, s2, p, node, j + 1)
    }
}

/// Undo one entry: a global is restored only if it still holds the value this process wrote (E-ROLLBACK-OTHER),
/// unless the rollback is physical (mutant); a process-private global only under the ppg mutant.
pub open spec fn restore1(sem: Sem, g: Seq<Option<Val>>, pp: Seq<Option<Val>>, e: Undo) -> (Seq<Option<Val>>, Seq<Option<Val>>) {
    if e.ppg {
        if sem.ppg_rolled_back { (g, pp.update(e.c as int, e.old)) } else { (g, pp) }
    } else if sem.rollback_physical || g[e.c as int] == e.written {
        (g.update(e.c as int, e.old), pp)
    } else {
        (g, pp)
    }
}

/// Undo a sequence of entries, last first.
pub open spec fn rb(sem: Sem, g: Seq<Option<Val>>, pp: Seq<Option<Val>>, es: Seq<Undo>) -> (Seq<Option<Val>>, Seq<Option<Val>>)
    decreases es.len()
{
    if es.len() == 0 {
        (g, pp)
    } else {
        let r = restore1(sem, g, pp, es.last());
        rb(sem, r.0, r.1, es.drop_last())
    }
}

pub open spec fn tstart(s: State, p: usize) -> State {
    let pr = s.procs[p as int];
    upd(s, p, Proc { marks: pr.marks.push(pr.undo.len()), ..pr })
}

/// The outermost transaction ended: deferred unlocks take effect, the log and the SQL flag are cleared.
pub open spec fn txn_end(s: State, p: usize) -> State {
    let pr = s.procs[p as int];
    upd(s, p, Proc {
        sqlflag: false,
        undo: Seq::empty(),
        marks: Seq::empty(),
        locks: Seq::new(pr.locks.len(), |i: int| Hold { de: 0, ds: 0, ..pr.locks[i] }),
        rlocks: Seq::new(pr.rlocks.len(), |i: int| false),
        ..pr
    })
}

/// The start of the top level's entries (clamped to the log).
pub open spec fn top_mark(pr: Proc) -> nat {
    if pr.marks.last() <= pr.undo.len() { pr.marks.last() } else { pr.undo.len() }
}

/// TROLLBACK 1 at a level > 0: undo the top level's entries.
pub open spec fn undo_top(sem: Sem, s: State, p: usize) -> State {
    let pr = s.procs[p as int];
    let m = top_mark(pr);
    let r = rb(sem, s.g, pr.ppg, pr.undo.subrange(m as int, pr.undo.len() as int));
    let pr2 = Proc { undo: pr.undo.subrange(0, m as int), marks: pr.marks.drop_last(), ppg: r.1, ..pr };
    let s2 = State { g: r.0, procs: s.procs.update(p as int, pr2) };
    if pr2.marks.len() == 0 { txn_end(s2, p) } else { s2 }
}

/// TCOMMIT at a level > 0: the top level's entries join the parent level (its mark goes).
pub open spec fn commit_top(s: State, p: usize) -> State {
    let pr = s.procs[p as int];
    if pr.marks.len() == 0 {
        s
    } else {
        let s2 = upd(s, p, Proc { marks: pr.marks.drop_last(), ..pr });
        if pr.marks.len() == 1 { txn_end(s2, p) } else { s2 }
    }
}

pub open spec fn rollback_n(sem: Sem, s: State, p: usize, n: nat) -> State
    decreases n
{
    if n == 0 || level(s.procs[p as int]) == 0 { s } else { rollback_n(sem, undo_top(sem, s, p), p, (n - 1) as nat) }
}

pub open spec fn commit_n(s: State, p: usize, n: nat) -> State
    decreases n
{
    if n == 0 || level(s.procs[p as int]) == 0 { s } else { commit_n(commit_top(s, p), p, (n - 1) as nat) }
}

pub open spec fn rollback_all(sem: Sem, s: State, p: usize) -> State {
    rollback_n(sem, s, p, level(s.procs[p as int]))
}

pub open spec fn commit_all(s: State, p: usize) -> State {
    commit_n(s, p, level(s.procs[p as int]))
}

/// SQL COMMIT / ROLLBACK and the driver's commit() / rollback(): end one or every level; the SQL flag is cleared.
pub open spec fn end_levels(s: State, sem: Sem, p: usize, ends: Ends, commit: bool) -> State {
    let l = level(s.procs[p as int]);
    let n: nat = match ends { Ends::One => 1, Ends::All => l };
    let s2 = if l == 0 { s } else if commit { commit_n(s, p, n) } else { rollback_n(sem, s, p, n) };
    set_sqlflag(s2, p, false)
}

// ------------------------------------------------------------------------------------------------ locks

pub open spec fn set_hold(s: State, p: usize, c: usize, h: Hold) -> State {
    let pr = s.procs[p as int];
    upd(s, p, Proc { locks: pr.locks.update(c as int, h), ..pr })
}

/// Acquire one hold (None: a count beyond u64).
pub open spec fn acquire(sem: Sem, s: State, p: usize, c: usize, mode: Mode) -> Option<State> {
    let h = s.procs[p as int].locks[c as int];
    match mode {
        Mode::E => if !sem.incremental {
            Some(set_hold(s, p, c, Hold { e: 1, ..h }))
        } else if h.e == u64::MAX {
            None
        } else {
            Some(set_hold(s, p, c, Hold { e: (h.e + 1) as u64, ..h }))
        },
        Mode::S => if !sem.incremental {
            Some(set_hold(s, p, c, Hold { s: 1, ..h }))
        } else if h.s == u64::MAX {
            None
        } else {
            Some(set_hold(s, p, c, Hold { s: (h.s + 1) as u64, ..h }))
        },
    }
}

/// Unlock one hold; deferred to the outermost transaction end inside a transaction unless immediate.
pub open spec fn release(sem: Sem, s: State, p: usize, c: usize, mode: Mode, immediate: bool) -> Option<State> {
    let pr = s.procs[p as int];
    let defer = sem.unlock_deferred && !immediate && level(pr) > 0;
    let h = pr.locks[c as int];
    match mode {
        Mode::E => if h.e == 0 {
            Some(s)
        } else if !defer {
            Some(set_hold(s, p, c, Hold { e: (h.e - 1) as u64, ..h }))
        } else if h.de == u64::MAX {
            None
        } else {
            Some(set_hold(s, p, c, Hold { e: (h.e - 1) as u64, de: (h.de + 1) as u64, ..h }))
        },
        Mode::S => if h.s == 0 {
            Some(s)
        } else if !defer {
            Some(set_hold(s, p, c, Hold { s: (h.s - 1) as u64, ..h }))
        } else if h.ds == u64::MAX {
            None
        } else {
            Some(set_hold(s, p, c, Hold { s: (h.s - 1) as u64, ds: (h.ds + 1) as u64, ..h }))
        },
    }
}

pub open spec fn defer_hold(h: Hold) -> Hold {
    Hold { e: 0, s: 0, de: (h.de + h.e) as u64, ds: (h.ds + h.s) as u64 }
}

pub open spec fn defer_overflows(h: Hold) -> bool {
    h.de + h.e > u64::MAX || h.ds + h.s > u64::MAX
}

/// Release every lock: deferred inside a transaction, else at once (row locks too).
pub open spec fn release_all(sem: Sem, s: State, p: usize) -> Option<State> {
    let pr = s.procs[p as int];
    if sem.unlock_deferred && level(pr) > 0 {
        if exists|c: int| 0 <= c < pr.locks.len() && defer_overflows(#[trigger] pr.locks[c]) {
            None
        } else {
            Some(upd(s, p, Proc { locks: Seq::new(pr.locks.len(), |i: int| defer_hold(pr.locks[i])), ..pr }))
        }
    } else {
        Some(upd(s, p, Proc {
            locks: Seq::new(pr.locks.len(), |i: int| zero_hold()),
            rlocks: Seq::new(pr.rlocks.len(), |i: int| false),
            ..pr
        }))
    }
}

// ------------------------------------------------------------------------------------------------ SQL rows

pub open spec fn set_rlock(s: State, p: usize, r: usize, b: bool) -> State {
    let pr = s.procs[p as int];
    upd(s, p, Proc { rlocks: pr.rlocks.update(r as int, b), ..pr })
}

/// Statement transaction: at level 0 with autocommit on the statement is its own transaction (true); with
/// autocommit off it opens a level SQL owns.
pub open spec fn stmt_begin(s: State, p: usize) -> (State, bool) {
    let pr = s.procs[p as int];
    if level(pr) == 0 && !pr.autocommit {
        (set_sqlflag(tstart(s, p), p, true), false)
    } else if level(pr) == 0 {
        (tstart(s, p), true)
    } else {
        (s, false)
    }
}

/// End of the statement: its own transaction commits; inside a transaction the row keeps its lock to the end.
pub open spec fn stmt_end(sem: Sem, s: State, p: usize, implicit: bool, r: usize) -> State {
    if implicit { commit_top(s, p) } else if sem.row_lock_held { set_rlock(s, p, r, true) } else { s }
}

/// A failing (or, under a mutant, empty) DML statement at level 0 with autocommit off still opens the transaction.
pub open spec fn failed_stmt(sem: Sem, s: State, p: usize) -> State {
    let pr = s.procs[p as int];
    if sem.failed_dml_opens_txn && level(pr) == 0 && !pr.autocommit { set_sqlflag(tstart(s, p), p, true) } else { s }
}

pub open spec fn dml_insert(sem: Sem, u: U, s: State, p: usize, r: usize, v: Val) -> (State, Obs) {
    if !u.texists[u.table[r as int] as int] {
        (s, Obs::SqlError(-30i64))
    } else if s.g[r as int] is Some {
        (failed_stmt(sem, s, p), Obs::SqlError(-119i64))
    } else {
        let b = stmt_begin(s, p);
        let s2 = write(b.0, p, r, Some(v), true);
        (stmt_end(sem, s2, p, b.1, r), Obs::Count(1i64))
    }
}

/// UPDATE (`nv` Some) or DELETE (`nv` None) by key.
pub open spec fn dml_change(sem: Sem, u: U, s: State, p: usize, r: usize, nv: Option<Val>) -> (State, Obs) {
    if !u.texists[u.table[r as int] as int] {
        (s, Obs::SqlError(-30i64))
    } else if s.g[r as int] is None {
        (if sem.empty_dml_opens_txn { failed_stmt(sem, s, p) } else { s }, Obs::Count(0i64))
    } else {
        let b = stmt_begin(s, p);
        let s2 = write(b.0, p, r, nv, true);
        (stmt_end(sem, s2, p, b.1, r), Obs::Count(1i64))
    }
}

pub open spec fn run_dml(sem: Sem, u: U, s: State, p: usize, op: Op) -> (State, Obs) {
    match op {
        Op::Insert { r, v } => dml_insert(sem, u, s, p, r, v),
        Op::Update { r, v } => dml_change(sem, u, s, p, r, Some(v)),
        Op::Delete { r } => dml_change(sem, u, s, p, r, None),
        _ => (s, Obs::Err(ErrK::BadPending)),
    }
}

/// The Freedom's condition: the key's row is not visible and another open transaction holds its row lock.
pub open spec fn freedom_cond(sem: Sem, s: State, p: usize, r: usize) -> bool {
    sem.dml_waits && s.g[r as int] is None && row_held(s, p, r)
}

/// Whether `op` by p waits now (`Engine::blocked_on`).
pub open spec fn blocked(sem: Sem, u: U, s: State, p: usize, op: Op) -> bool {
    match op {
        Op::Lock { c, mode, .. } => conflicts(sem, u, s, p, c, mode),
        Op::LockOnly { c, .. } => conflicts(sem, u, s, p, c, Mode::E),
        Op::Update { r, .. } | Op::Delete { r } => sem.dml_waits && s.g[r as int] is Some && row_held(s, p, r),
        Op::Insert { r, .. } => freedom_cond(sem, s, p, r)
            || (sem.insert_dup_waits && s.g[r as int] is Some && row_held(s, p, r)),
        Op::EmbRegister { r } => !sem.emb_ignores_row_locks && freedom_cond(sem, s, p, r),
        Op::EmbRetract { r } => !sem.emb_ignores_row_locks && sem.dml_waits && s.g[r as int] is Some && row_held(s, p, r),
        Op::Upsert { r, .. } => !sem.iou_ignores_row_locks && sem.dml_waits && s.g[r as int] is Some && row_held(s, p, r),
        _ => false,
    }
}

pub open spec fn rows_from(u: U, g: Seq<Option<Val>>, t: usize, j: nat) -> Seq<(usize, Val)>
    decreases u.n() - j
{
    if j >= u.n() {
        Seq::empty()
    } else {
        let rest = rows_from(u, g, t, j + 1);
        if u.is_row[j as int] && u.table[j as int] == t && g[j as int] is Some {
            seq![(j as usize, g[j as int]->Some_0)] + rest
        } else {
            rest
        }
    }
}

pub open spec fn select_obs(u: U, g: Seq<Option<Val>>, t: usize) -> Obs {
    if u.texists[t as int] { Obs::Rows(rows_from(u, g, t, 0)) } else { Obs::SqlError(-30i64) }
}

/// A query with autocommit off at level 0 opens a transaction only under the mutant.
pub open spec fn select_txn(sem: Sem, s: State, p: usize) -> State {
    let pr = s.procs[p as int];
    if sem.select_opens_txn && level(pr) == 0 && !pr.autocommit { set_sqlflag(tstart(s, p), p, true) } else { s }
}

// ------------------------------------------------------------------------------------------------ reads

pub open spec fn has_kids(u: U, g: Seq<Option<Val>>, c: int) -> bool {
    exists|j: int| 0 <= j < u.n() && j != c && covers(u, c, j) && #[trigger] g[j] is Some
}

pub open spec fn data_of(u: U, g: Seq<Option<Val>>, c: int) -> u8 {
    ((if g[c] is Some { 1int } else { 0int }) + (if has_kids(u, g, c) { 10int } else { 0int })) as u8
}

pub open spec fn num_of(u: U, v: Option<Val>) -> i64 {
    match v {
        None => 0,
        Some(Val::Num(n)) => n,
        Some(Val::Str(id)) => if (id as int) < u.parse.len() { u.parse[id as int] } else { 0 },
        Some(_) => 0,
    }
}

/// The committed view (used only by the no-dirty-reads mutants): every other process's open transactions undone,
/// physically, in process order.
pub open spec fn cv_from(sem: Sem, s: State, p: usize, q: nat) -> State
    decreases s.procs.len() - q
{
    if q >= s.procs.len() {
        s
    } else {
        let s2 = if q != p { rollback_all(Sem { rollback_physical: true, ..sem }, s, q as usize) } else { s };
        cv_from(sem, State { g: s2.g, procs: s.procs }, p, q + 1)
    }
}

// ------------------------------------------------------------------------------------------------ process stop

pub open spec fn stop(sem: Sem, s: State, t: usize) -> State {
    let s1 = if !sem.stop_rolls_back {
        commit_all(s, t)
    } else if sem.stop_all_levels {
        rollback_all(sem, s, t)
    } else {
        rollback_n(sem, s, t, 1)
    };
    let pr = s1.procs[t as int];
    upd(s1, t, Proc {
        locks: Seq::new(pr.locks.len(), |i: int| zero_hold()),
        rlocks: Seq::new(pr.rlocks.len(), |i: int| false),
        ppg: Seq::new(pr.ppg.len(), |i: int| None),
        pending: None,
        alive: false,
        ..pr
    })
}

// ------------------------------------------------------------------------------------------------ one operation

pub open spec fn num_obs(n: nat) -> Obs {
    if n <= i64::MAX { Obs::Value(Some(Val::Num(n as i64))) } else { Obs::Err(ErrK::Overflow) }
}

/// The operation's effect once it is not blocked (also what `Await` completes).
pub open spec fn lock_now(sem: Sem, s: State, p: usize, c: usize, mode: Mode) -> (State, Obs) {
    match acquire(sem, s, p, c, mode) {
        Some(s2) => (s2, Obs::Test(true)),
        None => (s, Obs::Err(ErrK::Overflow)),
    }
}

/// The two worlds of the Freedom: `goes` (the row id is not the key: the INSERT proceeds; its new row's lock is not
/// the key's) or waits.
pub open spec fn freedom_step(sem: Sem, u: U, s: State, p: usize, op: Op, r: usize, choice: bool) -> (State, Obs) {
    let goes = match sem.freedom { FreedomSem::Both => choice, FreedomSem::WaitOnly => false, FreedomSem::GoOnly => true };
    if goes {
        let o = run_dml(sem, u, s, p, op);
        (set_rlock(o.0, p, r, false), o.1)
    } else {
        (set_pending(s, p, Some(op)), Obs::Pending)
    }
}

pub open spec fn await_step(sem: Sem, u: U, s: State, p: usize) -> (State, Obs) {
    match s.procs[p as int].pending {
        None => (s, Obs::Err(ErrK::NothingPending)),
        Some(pend) => {
            let lockwait = pend is Lock || pend is LockOnly;
            if blocked(sem, u, s, p, pend) || (lockwait && !sem.lock_wait_grants) {
                (s, Obs::Blocked)
            } else {
                let s1 = set_pending(s, p, None);
                match pend {
                    Op::Lock { c, mode, .. } => lock_now(sem, s1, p, c, mode),
                    Op::LockOnly { c, .. } => lock_now(sem, s1, p, c, Mode::E),
                    Op::Insert { .. } | Op::Update { .. } | Op::Delete { .. } => run_dml(sem, u, s1, p, pend),
                    Op::EmbRegister { r } => { let o = emb_dml(sem, u, s1, p, r, Some(Val::Empty)); (o.0, reg_obs(o.1)) },
                    Op::EmbRetract { r } => { let o = emb_dml(sem, u, s1, p, r, None); (o.0, retract_obs(o.1)) },
                    Op::Upsert { r, v } => upsert_run(sem, u, s1, p, r, v, true),
                    _ => (s1, Obs::Err(ErrK::BadPending)),
                }
            }
        },
    }
}

pub open spec fn txn_step(sem: Sem, s: State, p: usize, op: Op) -> (State, Obs) {
    let pr = s.procs[p as int];
    let l = level(pr);
    match op {
        Op::TStart => (tstart(s, p), Obs::Ok),
        Op::TCommit => if l == 0 { (s, Obs::Err(ErrK::Command)) } else { (commit_top(s, p), Obs::Ok) },
        Op::TRollbackOne => if l == 0 {
            (s, Obs::Ok)
        } else if sem.rollback_one_is_one_level {
            (undo_top(sem, s, p), Obs::Ok)
        } else {
            (rollback_all(sem, s, p), Obs::Ok)
        },
        Op::TRollback => (rollback_all(sem, s, p), Obs::Ok),
        Op::SqlStart => {
            let start = match sem.sql_start {
                SqlStartSem::UnlessSqlOwns => !pr.sqlflag,
                SqlStartSem::NothingIfOpen => l == 0,
                SqlStartSem::Always => true,
            };
            if start { (set_sqlflag(tstart(s, p), p, true), Obs::Ok) } else { (s, Obs::Ok) }
        },
        Op::SqlCommit => (end_levels(s, sem, p, sem.sql_commit, true), Obs::Ok),
        Op::SqlRollback => (end_levels(s, sem, p, sem.sql_rollback, false), Obs::Ok),
        Op::DrvCommit => (end_levels(s, sem, p, sem.drv_commit, true), Obs::Ok),
        Op::DrvRollback => (end_levels(s, sem, p, sem.drv_rollback, false), Obs::Ok),
        Op::SetAutocommit { on } => if l > 0 && !on && pr.autocommit {
            (s, Obs::Refused(RefK::AutocommitOffInTxn))
        } else {
            let s2 = if on && l > 0 && sem.autocommit_on_commits { end_levels(s, sem, p, sem.drv_commit, true) } else { s };
            (upd(s2, p, Proc { autocommit: on, ..s2.procs[p as int] }), Obs::Ok)
        },
        Op::TLevel => (s, Obs::Level(l)),
        Op::SqlTxnBegin { hold } => {
            let s1 = select_txn(sem, s, p);
            let before = level(s1.procs[p as int]);
            let s2 = if hold && before == 0 { tstart(s1, p) } else { s1 };
            let s3 = tstart(s2, p);
            let answer = level(s3.procs[p as int]);
            let s4 = if sem.sqlproc_levels_end_with_statement { commit_n(s3, p, (answer - before) as nat) } else { s3 };
            (s4, num_obs(answer))
        },
        Op::SqlTxnEnd { level: lv } => {
            let s1 = select_txn(sem, s, p);
            let l1 = level(s1.procs[p as int]);
            let s2 = if lv >= 1 && l1 >= lv { commit_n(s1, p, (l1 - lv + 1) as nat) } else { s1 };
            (s2, num_obs(level(s2.procs[p as int])))
        },
        Op::SqlTxnUndo { level: lv } => {
            let s1 = select_txn(sem, s, p);
            let l1 = level(s1.procs[p as int]);
            let s2 = if lv >= 1 && l1 >= lv {
                if sem.rollback_one_is_one_level { rollback_n(sem, s1, p, (l1 - lv + 1) as nat) } else { rollback_all(sem, s1, p) }
            } else {
                s1
            };
            (s2, num_obs(level(s2.procs[p as int])))
        },
        _ => (s, Obs::Err(ErrK::BadPending)),
    }
}

pub open spec fn is_txn_op(op: Op) -> bool {
    op is TStart || op is TCommit || op is TRollbackOne || op is TRollback || op is SqlStart || op is SqlCommit
        || op is SqlRollback || op is DrvCommit || op is DrvRollback || op is SetAutocommit || op is TLevel
        || op is SqlTxnBegin || op is SqlTxnEnd || op is SqlTxnUndo
}

pub open spec fn glob_step(sem: Sem, u: U, s: State, p: usize, op: Op) -> (State, Obs) {
    let pr = s.procs[p as int];
    match op {
        Op::Set { c, v } => (write(s, p, c, Some(v), true), Obs::Ok),
        Op::Kill { c } => (kill_from(sem, u, s, p, c, 0), Obs::Ok),
        Op::Get { c } => {
            let v = if sem.dirty_reads { s.g[c as int] } else { cv_from(sem, s, p, 0).g[c as int] };
            (s, Obs::Value(v))
        },
        Op::Data { c } => (s, Obs::Data(data_of(u, s.g, c as int))),
        Op::Incr { c } => {
            let cur = num_of(u, s.g[c as int]);
            if cur == i64::MAX {
                (s, Obs::Err(ErrK::Overflow))
            } else {
                let nv = Val::Num((cur + 1) as i64);
                (write(s, p, c, Some(nv), !sem.incr_survives), Obs::Value(Some(nv)))
            }
        },
        Op::PpgSet { c, v } => {
            let pr2 = Proc {
                ppg: pr.ppg.update(c as int, Some(v)),
                undo: if level(pr) > 0 { pr.undo.push(Undo { c, old: pr.ppg[c as int], written: Some(v), ppg: true }) } else { pr.undo },
                ..pr
            };
            (upd(s, p, pr2), Obs::Ok)
        },
        Op::PpgGet { c } => (s, Obs::Value(pr.ppg[c as int])),
        _ => (s, Obs::Err(ErrK::BadPending)),
    }
}

pub open spec fn is_glob_op(op: Op) -> bool {
    op is Set || op is Kill || op is Get || op is Data || op is Incr || op is PpgSet || op is PpgGet
}

pub open spec fn lock_step(sem: Sem, u: U, s: State, p: usize, op: Op) -> (State, Obs) {
    match op {
        Op::Lock { c, mode, wait } => if conflicts(sem, u, s, p, c, mode) {
            if wait { (set_pending(s, p, Some(op)), Obs::Pending) } else { (s, Obs::Test(false)) }
        } else {
            lock_now(sem, s, p, c, mode)
        },
        Op::Unlock { c, mode, immediate } => match release(sem, s, p, c, mode, immediate) {
            Some(s2) => (s2, Obs::Ok),
            None => (s, Obs::Err(ErrK::Overflow)),
        },
        Op::LockOnly { c, wait } => match release_all(sem, s, p) {
            None => (s, Obs::Err(ErrK::Overflow)),
            Some(s1) => if conflicts(sem, u, s1, p, c, Mode::E) {
                if wait { (set_pending(s1, p, Some(op)), Obs::Pending) } else { (s1, Obs::Test(false)) }
            } else {
                lock_now(sem, s1, p, c, Mode::E)
            },
        },
        Op::ReleaseAll => match release_all(sem, s, p) {
            Some(s2) => (s2, Obs::Ok),
            None => (s, Obs::Err(ErrK::Overflow)),
        },
        _ => (s, Obs::Err(ErrK::BadPending)),
    }
}

pub open spec fn is_lock_op(op: Op) -> bool {
    op is Lock || op is Unlock || op is LockOnly || op is ReleaseAll
}

pub open spec fn row_step(sem: Sem, u: U, s: State, p: usize, op: Op, choice: bool) -> (State, Obs) {
    match op {
        Op::Insert { r, .. } => if sem.maxlen_enforced && u.long[r as int] {
            (failed_stmt(sem, s, p), Obs::SqlError(-104i64))
        } else if freedom_cond(sem, s, p, r) {
            freedom_step(sem, u, s, p, op, r, choice)
        } else if blocked(sem, u, s, p, op) {
            (set_pending(s, p, Some(op)), Obs::Pending)
        } else {
            run_dml(sem, u, s, p, op)
        },
        Op::Update { .. } | Op::Delete { .. } => if blocked(sem, u, s, p, op) {
            (set_pending(s, p, Some(op)), Obs::Pending)
        } else {
            run_dml(sem, u, s, p, op)
        },
        Op::Select { t } => {
            let s1 = select_txn(sem, s, p);
            let g = if sem.select_dirty { s1.g } else { cv_from(sem, s1, p, 0).g };
            (s1, select_obs(u, g, t))
        },
        _ => (s, Obs::Err(ErrK::BadPending)),
    }
}

pub open spec fn is_row_op(op: Op) -> bool {
    op is Insert || op is Update || op is Delete || op is Select
}

/// One permitted outcome of `op` by p; `choice` selects the Freedom's world (true: proceeds) and is ignored
/// elsewhere.
pub open spec fn step(sem: Sem, u: U, s: State, p: usize, op: Op, choice: bool) -> (State, Obs) {
    if (p as int) >= s.procs.len() || !s.procs[p as int].alive {
        (s, Obs::Err(ErrK::Dead))
    } else if s.procs[p as int].pending is Some && !(op is Await) {
        (s, Obs::Err(ErrK::Busy))
    } else if is_txn_op(op) {
        txn_step(sem, s, p, op)
    } else if is_glob_op(op) {
        glob_step(sem, u, s, p, op)
    } else if is_lock_op(op) {
        lock_step(sem, u, s, p, op)
    } else if is_row_op(op) {
        row_step(sem, u, s, p, op, choice)
    } else if is_ext_op(op) {
        ext_step(sem, u, s, p, op, choice)
    } else {
        match op {
            Op::Terminate { target } => if (target as int) < s.procs.len() && s.procs[target as int].alive {
                (stop(sem, s, target), Obs::Ok)
            } else {
                (s, Obs::Ok)
            },
            Op::Await => await_step(sem, u, s, p),
            _ => (s, Obs::Err(ErrK::BadPending)),
        }
    }
}

/// The operation has two permitted outcomes (the Freedom).
pub open spec fn choice_point(sem: Sem, u: U, s: State, p: usize, op: Op) -> bool {
    &&& (p as int) < s.procs.len()
    &&& s.procs[p as int].alive
    &&& s.procs[p as int].pending is None
    &&& sem.freedom == FreedomSem::Both
    &&& ((op matches Op::Insert { r, .. } && !(sem.maxlen_enforced && u.long[r as int]) && freedom_cond(sem, s, p, r))
        || ext_choice(sem, u, s, p, op))
}

/// Every permitted (next state, observation) of `op` by p.
pub open spec fn outcomes(sem: Sem, u: U, s: State, p: usize, op: Op) -> Seq<(State, Obs)> {
    if choice_point(sem, u, s, p, op) {
        seq![step(sem, u, s, p, op, false), step(sem, u, s, p, op, true)]
    } else {
        seq![step(sem, u, s, p, op, false)]
    }
}

pub open spec fn permits(sem: Sem, u: U, s: State, p: usize, op: Op, s2: State, o: Obs) -> bool {
    outcomes(sem, u, s, p, op).contains((s2, o))
}

// ------------------------------------------------------------------------------------------------ a case

/// Verbs one client path cannot express (`refused_by_driver`).
pub open spec fn driver_refusal(kind: Kind, op: Op) -> Option<RefK> {
    match kind {
        Kind::Term => match op {
            Op::DrvCommit => Some(RefK::DrvCommitTerm),
            Op::DrvRollback => Some(RefK::DrvRollbackTerm),
            Op::SetAutocommit { .. } => Some(RefK::SetAutocommitTerm),
            Op::Upsert { .. } => Some(RefK::UpsertTerm),
            Op::InsertMany { .. } => Some(RefK::InsertManyTerm),
            _ => None,
        },
        Kind::Dbapi => match op {
            Op::PpgSet { .. } => Some(RefK::PpgSetDbapi),
            Op::PpgGet { .. } => Some(RefK::PpgGetDbapi),
            Op::LockOnly { .. } => Some(RefK::LockOnlyDbapi),
            Op::ZStrip { .. } => Some(RefK::ZStripDbapi),
            Op::ZClass { .. } => Some(RefK::ZClassDbapi),
            _ => None,
        },
    }
}

pub open spec fn kind_of(case: Case, q: int) -> Kind {
    if 0 <= q < case.kinds.len() { case.kinds[q] } else { Kind::Dbapi }
}

pub open spec fn init_proc(u: U, kind: Kind) -> Proc {
    Proc {
        alive: true,
        sqlflag: false,
        autocommit: true,
        kind,
        marks: Seq::empty(),
        undo: Seq::empty(),
        locks: Seq::new(u.n(), |i: int| zero_hold()),
        rlocks: Seq::new(u.n(), |i: int| false),
        ppg: Seq::new(u.n(), |i: int| None),
        pending: None,
    }
}

pub open spec fn init_state(u: U, case: Case) -> State {
    State { g: Seq::new(u.n(), |i: int| None), procs: Seq::new(case.nprocs, |q: int| init_proc(u, kind_of(case, q))) }
}

pub open spec fn finals_from(u: U, case: Case, s: State, i: nat) -> Seq<Obs>
    decreases case.observe.len() + case.observe_tables.len() - i
{
    let n1 = case.observe.len();
    let n = n1 + case.observe_tables.len();
    if i >= n {
        Seq::empty()
    } else {
        let o = if i < n1 { Obs::Value(s.g[case.observe[i as int] as int]) } else { select_obs(u, s.g, case.observe_tables[i - n1]) };
        seq![o] + finals_from(u, case, s, i + 1)
    }
}

pub open spec fn run_from(sem: Sem, u: U, case: Case, s: State, i: nat, choices: Seq<bool>, ci: nat, obs: Seq<Obs>) -> RunRes
    decreases case.steps.len() - i
{
    if i >= case.steps.len() {
        RunRes::Done(obs, finals_from(u, case, s, 0), ci)
    } else {
        let p = case.steps[i as int].0;
        let op = case.steps[i as int].1;
        match driver_refusal(kind_of(case, p as int), op) {
            Some(rk) => run_from(sem, u, case, s, i + 1, choices, ci, obs.push(Obs::Refused(rk))),
            None => if choice_point(sem, u, s, p, op) {
                if ci >= choices.len() {
                    RunRes::NeedMore
                } else {
                    let o = step(sem, u, s, p, op, choices[ci as int]);
                    run_from(sem, u, case, o.0, i + 1, choices, ci + 1, obs.push(o.1))
                }
            } else {
                let o = step(sem, u, s, p, op, false);
                run_from(sem, u, case, o.0, i + 1, choices, ci, obs.push(o.1))
            },
        }
    }
}

pub open spec fn run(sem: Sem, u: U, case: Case, choices: Seq<bool>) -> RunRes {
    run_from(sem, u, case, init_state(u, case), 0, choices, 0, Seq::empty())
}

/// The permitted outcomes of a case: every complete run, over every choice sequence it consumes exactly.
pub open spec fn permitted(sem: Sem, u: U, case: Case, obs: Seq<Obs>, finals: Seq<Obs>) -> bool {
    exists|cs: Seq<bool>| run(sem, u, case, cs) == RunRes::Done(obs, finals, cs.len())
}

pub open spec fn wf_case(u: U, case: Case) -> bool {
    &&& forall|i: int| 0 <= i < case.steps.len() ==> (#[trigger] case.steps[i]).0 < case.nprocs && wf_op(u, case.steps[i].1)
    &&& forall|i: int| 0 <= i < case.observe.len() ==> (#[trigger] case.observe[i] as int) < u.n()
    &&& forall|i: int| 0 <= i < case.observe_tables.len() ==> (#[trigger] case.observe_tables[i] as int) < u.texists.len()
}

} // verus!
