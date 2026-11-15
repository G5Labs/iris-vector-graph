//! Differential harness of lane proofs-env (no IRIS): the verified exec model (`ivg_proofs_env2::exec::e_run`) against
//! the executable contract's permitted sets and the recorded observations of a registered round.
//!
//!   proofs-env-harness check <cases.json> <observed.json> <contract-permitted.json> --round NAME --tables T,S,E,C
//!       [--out report.json] [--mutants-out mutants.json]
//!
//! For every case whose operations all lie in the Verus subset: the permitted set is the set of outcomes of `e_run`
//! over every choice sequence (depth-first: a run that reaches a Freedom with no choice left is extended by false and
//! by true); it must equal the contract's set (`iris-contract permitted`), and every observed outcome must lie in it.
//! Cases with an operation outside the subset are counted by reason, never compared. Each mutant of the Verus model is
//! killed when some observed outcome of an in-subset case lies outside the mutant's permitted set.
//! This file is test code (trusted as the drivers are); the outcome computation it calls is verified.
use ivg_proofs_env2::exec::*;
use ivg_proofs_env2::spec::*;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;

struct Interner {
    strs: BTreeMap<String, usize>,
    list: Vec<String>,
}

impl Interner {
    fn new() -> Self {
        Interner { strs: BTreeMap::new(), list: vec![] }
    }
    fn id(&mut self, s: &str) -> usize {
        if let Some(i) = self.strs.get(s) {
            return *i;
        }
        let i = self.list.len();
        self.strs.insert(s.to_string(), i);
        self.list.push(s.to_string());
        i
    }
}

/// One case translated into the Verus model's universe.
struct Built {
    case: ECase,
    univ: Univ,
    /// cell -> rendered key (rows) ; value ids -> strings
    row_key: Vec<String>,
    vals: Vec<String>,
    names: Vec<String>,
}

#[derive(Default)]
struct Ctx {
    names: Interner,
    vals: Interner,
    cells: BTreeMap<(bool, String, Vec<String>), usize>,
    paths: Vec<Vec<u64>>,
    is_row: Vec<bool>,
    table: Vec<usize>,
    row_key: Vec<String>,
    keys: Interner,
    long: Vec<bool>,
    key: Vec<usize>,
    zargs: Vec<EZArg>,
    batches: Vec<Vec<(usize, Val)>>,
}

impl Default for Interner {
    fn default() -> Self {
        Interner::new()
    }
}

impl Ctx {
    fn glob(&mut self, node: &Value) -> Result<usize, String> {
        let root = node["root"].as_str().ok_or("node root")?.to_string();
        if root.starts_with('#') || root.starts_with("^SQL.") || root.starts_with("^PK.") || root.starts_with("^IDX.") {
            return Err(format!("node root {root} is a model-internal name"));
        }
        let subs: Vec<String> = node["subs"].as_array().map(|a| a.iter().map(|x| x.as_str().unwrap_or("").to_string()).collect())
            .unwrap_or_default();
        let key = (false, root.clone(), subs.clone());
        if let Some(c) = self.cells.get(&key) {
            return Ok(*c);
        }
        let mut path = vec![self.names.id(&root) as u64];
        for s in &subs {
            path.push(self.names.id(s) as u64);
        }
        let c = self.paths.len();
        self.cells.insert(key, c);
        self.paths.push(path);
        self.is_row.push(false);
        self.table.push(0);
        self.row_key.push(String::new());
        self.long.push(false);
        self.key.push(0);
        Ok(c)
    }
    fn row(&mut self, table: usize, tname: &str, k: &str) -> usize {
        let key = (true, tname.to_string(), vec![k.to_string()]);
        if let Some(c) = self.cells.get(&key) {
            return *c;
        }
        let c = self.paths.len();
        self.cells.insert(key, c);
        self.paths.push(vec![]);
        self.is_row.push(true);
        self.table.push(table);
        self.row_key.push(k.to_string());
        self.long.push(false);
        let kid = self.keys.id(k);
        self.key.push(kid);
        c
    }
    fn param(&mut self, v: &Value) -> Param {
        match v.as_str() {
            None => Param::PNull,
            Some("") => Param::PEmpty,
            Some("\u{0}") => Param::PNul,
            Some(s) => Param::PV(self.val(s)),
        }
    }
    fn val(&mut self, s: &str) -> Val {
        if s.is_empty() {
            return Val::Empty;
        }
        if s == "\u{0}" {
            return Val::Nul;
        }
        match s.parse::<i64>() {
            Ok(n) if n.to_string() == s => Val::Num(n),
            _ => Val::Str(self.vals.id(s)),
        }
    }
}

fn mode_of(v: &Value) -> Result<Mode, String> {
    match v.as_str() {
        Some("E") => Ok(Mode::E),
        Some("S") => Ok(Mode::S),
        other => Err(format!("mode {other:?}")),
    }
}

/// The contract variant's tables: (name, exists initially). F carries the functional index (X-FX): outside.
fn table_id(tables: &[String], name: &str) -> Option<usize> {
    tables.iter().position(|t| t == name)
}

/// Every (table, key) a case's row operations name (INSERT ... SELECT: every key of its source also in its target),
/// so that row cells are allocated in key order per table (the contract's INSERT ... SELECT reads its source in key
/// order).
fn row_keys(c: &Value) -> Vec<(String, String)> {
    let mut rows: BTreeSet<(String, String)> = BTreeSet::new();
    let mut sel: Vec<(String, String)> = vec![];
    for st in c["steps"].as_array().into_iter().flatten() {
        let o = &st[1];
        let k = o.get("k").and_then(|k| k.as_str()).map(String::from);
        match o["op"].as_str().unwrap_or("") {
            "insert" | "update" | "delete" | "upsert" => if let (Some(t), Some(k)) = (o["table"].as_str(), k) { rows.insert((t.to_string(), k)); },
            "insert_many" => if let Some(t) = o["table"].as_str() {
                for kv in o["rows"].as_array().into_iter().flatten() {
                    if let Some(k) = kv[0].as_str() { rows.insert((t.to_string(), k.to_string())); }
                }
            },
            "put_e" | "get_e" => if let Some(k) = k { rows.insert(("E".into(), k)); },
            "emb_register" => if let Some(k) = k { rows.insert(("N".into(), k)); },
            "emb_retract" => if let Some(k) = k { rows.insert(("R".into(), k)); },
            "emb_assert" => if let Some(k) = k { rows.insert(("N".into(), k.clone())); rows.insert(("R0".into(), k)); },
            "insert_select" => sel.push((o["from"].as_str().unwrap_or("").into(), o["to"].as_str().unwrap_or("").into())),
            _ => {}
        }
    }
    for _ in 0..sel.len() {
        for (from, to) in &sel {
            let ks: Vec<String> = rows.iter().filter(|(t, _)| t == from).map(|(_, k)| k.clone()).collect();
            for k in ks { rows.insert((to.clone(), k)); }
        }
    }
    rows.into_iter().collect()
}

fn build(c: &Value, tables: &[String], long_keys_refused: bool) -> Result<Built, String> {
    let mut x = Ctx::default();
    // row cells first, sorted by (table position, key): cell order is key order within a table
    let mut rk = row_keys(c);
    rk.sort_by(|a, b| (table_id(tables, &a.0), &a.1).cmp(&(table_id(tables, &b.0), &b.1)));
    for (t, k) in &rk {
        if let Some(tid) = table_id(tables, t) {
            let r = x.row(tid, t, k);
            x.long[r] = long_keys_refused && matches!(t.as_str(), "N" | "R" | "R0") && k.chars().count() > 256;
        }
    }
    let nprocs = c["procs"].as_u64().ok_or("procs")? as usize;
    let kinds: Vec<Kind> = c.get("kinds").and_then(|k| k.as_array()).map(|a| a.iter().map(|k| match k.as_str() {
        Some("term") => Kind::Term,
        _ => Kind::Dbapi,
    }).collect()).unwrap_or_default();
    let tab = |x: &mut Ctx, name: &str| -> Result<usize, String> {
        let _ = x;
        table_id(tables, name).ok_or(format!("table {name} outside the Verus subset"))
    };
    let mut steps = vec![];
    for st in c["steps"].as_array().ok_or("steps")? {
        let p = st[0].as_u64().ok_or("proc")? as usize;
        let o = &st[1];
        let name = o["op"].as_str().ok_or("op")?;
        let op = match name {
            "t_start" => Op::TStart,
            "t_commit" => Op::TCommit,
            "t_rollback_one" => Op::TRollbackOne,
            "t_rollback" => Op::TRollback,
            "sql_start" => Op::SqlStart,
            "sql_commit" => Op::SqlCommit,
            "sql_rollback" => Op::SqlRollback,
            "drv_commit" => Op::DrvCommit,
            "drv_rollback" => Op::DrvRollback,
            "set_autocommit" => Op::SetAutocommit { on: o["on"].as_bool().ok_or("on")? },
            "t_level" => Op::TLevel,
            "set" => {
                let c = x.glob(&o["node"])?;
                Op::Set { c, v: x.val(o["value"].as_str().ok_or("value")?) }
            }
            "kill" => Op::Kill { c: x.glob(&o["node"])? },
            "get" => Op::Get { c: x.glob(&o["node"])? },
            "data" => Op::Data { c: x.glob(&o["node"])? },
            "incr" => Op::Incr { c: x.glob(&o["node"])? },
            "ppg_set" => {
                let c = x.glob(&o["node"])?;
                Op::PpgSet { c, v: x.val(o["value"].as_str().ok_or("value")?) }
            }
            "ppg_get" => Op::PpgGet { c: x.glob(&o["node"])? },
            "lock" => Op::Lock { c: x.glob(&o["node"])?, mode: mode_of(&o["mode"])?, wait: o["wait"].as_bool().ok_or("wait")? },
            "unlock" => Op::Unlock { c: x.glob(&o["node"])?, mode: mode_of(&o["mode"])?, immediate: o["immediate"].as_bool().ok_or("immediate")? },
            "lock_only" => Op::LockOnly { c: x.glob(&o["node"])?, wait: o["wait"].as_bool().ok_or("wait")? },
            "release_all" => Op::ReleaseAll,
            "insert" | "update" | "delete" => {
                if o.get("noindex").and_then(|b| b.as_bool()).unwrap_or(false) || o.get("nocheck").and_then(|b| b.as_bool()).unwrap_or(false) {
                    return Err("insert %NOINDEX/%NOCHECK (X-NOINDEX) outside the Verus subset".into());
                }
                let tname = o["table"].as_str().ok_or("table")?;
                if tname == "F" {
                    return Err("table F (X-FX functional index) outside the Verus subset".into());
                }
                let t = tab(&mut x, tname)?;
                let k = o["k"].as_str().ok_or("k")?;
                let r = x.row(t, tname, k);
                match name {
                    "insert" => Op::Insert { r, v: x.val(o["v"].as_str().ok_or("v")?) },
                    "update" => Op::Update { r, v: x.val(o["v"].as_str().ok_or("v")?) },
                    _ => Op::Delete { r },
                }
            }
            "select" => Op::Select { t: tab(&mut x, o["table"].as_str().ok_or("table")?)? },
            "terminate" => Op::Terminate { target: o["target"].as_u64().ok_or("target")? as usize },
            "await" => Op::Await,
            "sql_txn_begin" => Op::SqlTxnBegin { hold: o["hold"].as_bool().ok_or("hold")? },
            "sql_txn_end" => Op::SqlTxnEnd { level: o["level"].as_u64().ok_or("level")? },
            "sql_txn_undo" => Op::SqlTxnUndo { level: o["level"].as_u64().ok_or("level")? },
            "sql_t_level" => Op::SqlTLevel,
            "sql_fn" => Op::SqlFn { f: match o["name"].as_str() {
                Some("VECTOR_COSINE") => 0, Some("VECTOR_DOT_PRODUCT") => 1, Some("VECTOR_L2") => 2,
                _ => return Err("sql_fn of another name outside the Verus subset".into()),
            } },
            "z_strip" => {
                let s: Vec<u32> = o["s"].as_array().ok_or("s")?.iter().map(|v| v.as_u64().unwrap_or(0) as u32).collect();
                let mask: Vec<u32> = o["mask"].as_str().unwrap_or("").chars().map(|c| c as u32).collect();
                let rem: Vec<u32> = o.get("rem").and_then(|r| r.as_str()).unwrap_or("").chars().map(|c| c as u32).collect();
                x.zargs.push(EZArg { s, mask, rem });
                Op::ZStrip { a: x.zargs.len() - 1 }
            }
            "z_class" => Op::ZClass { ch: o["class"].as_str().and_then(|c| c.chars().next()).unwrap_or('?') as u32 },
            "order" => Op::Order { c: x.glob(&o["node"])? },
            "put_e" => {
                let t = tab(&mut x, "E")?;
                let r = x.row(t, "E", o["k"].as_str().ok_or("k")?);
                let v = x.param(&o["v"]);
                Op::PutE { r, v, literal: o.get("literal").and_then(|b| b.as_bool()).unwrap_or(false) }
            }
            "get_e" => {
                let t = tab(&mut x, "E")?;
                Op::GetE { r: x.row(t, "E", o["k"].as_str().ok_or("k")?) }
            }
            "match_e" => {
                let t = tab(&mut x, "E")?;
                let v = x.param(&o["v"]);
                Op::MatchE { t, v }
            }
            "insert_select" => {
                let (f, t) = (o["from"].as_str().ok_or("from")?, o["to"].as_str().ok_or("to")?);
                if f == "F" || t == "F" {
                    return Err("table F (X-FX functional index) outside the Verus subset".into());
                }
                Op::InsertSelect { from: tab(&mut x, f)?, to: tab(&mut x, t)? }
            }
            "emb_register" => {
                let t = tab(&mut x, "N")?;
                Op::EmbRegister { r: x.row(t, "N", o["k"].as_str().ok_or("k")?) }
            }
            "emb_retract" => {
                let t = tab(&mut x, "R")?;
                Op::EmbRetract { r: x.row(t, "R", o["k"].as_str().ok_or("k")?) }
            }
            "emb_count" => Op::EmbCount { t: tab(&mut x, "R")? },
            "emb_route" => Op::EmbRoute { t: tab(&mut x, "G")? },
            "emb_assert" => {
                let k = o["k"].as_str().ok_or("k")?;
                let (tn, tr) = (tab(&mut x, "N")?, tab(&mut x, "R0")?);
                let rn = x.row(tn, "N", k);
                let rr = x.row(tr, "R0", k);
                Op::EmbAssert { rn, rr, empty: o["mode"].as_str() == Some("empty"), vt: x.val("t") }
            }
            "upsert" | "insert_many" => {
                let tname = o["table"].as_str().ok_or("table")?;
                if tname == "F" {
                    return Err("table F (X-FX functional index) outside the Verus subset".into());
                }
                let t = tab(&mut x, tname)?;
                if name == "upsert" {
                    let r = x.row(t, tname, o["k"].as_str().ok_or("k")?);
                    Op::Upsert { r, v: x.val(o["v"].as_str().ok_or("v")?) }
                } else {
                    let mut rows = vec![];
                    for kv in o["rows"].as_array().ok_or("rows")? {
                        let r = x.row(t, tname, kv[0].as_str().ok_or("row key")?);
                        rows.push((r, x.val(kv[1].as_str().ok_or("row value")?)));
                    }
                    x.batches.push(rows);
                    Op::InsertMany { t, b: x.batches.len() - 1 }
                }
            }
            other => return Err(format!("operation {other} outside the Verus subset")),
        };
        if p >= nprocs {
            return Err("process index out of range".into());
        }
        steps.push((p, op));
    }
    let mut observe = vec![];
    for n in c.get("observe").and_then(|v| v.as_array()).cloned().unwrap_or_default() {
        observe.push(x.glob(&n)?);
    }
    let mut observe_tables = vec![];
    for t in c.get("observe_tables").and_then(|v| v.as_array()).cloned().unwrap_or_default() {
        if t.as_str() == Some("F") {
            return Err("table F (X-FX functional index) outside the Verus subset".into());
        }
        observe_tables.push(tab(&mut x, t.as_str().ok_or("table")?)?);
    }
    let parse: Vec<i64> = x.vals.list.iter().map(|s| s.parse::<i64>().unwrap_or(0)).collect();
    let names: Vec<Vec<u32>> = x.names.list.iter().map(|s| s.chars().map(|c| c as u32).collect()).collect();
    let univ = Univ {
        paths: x.paths,
        is_row: x.is_row,
        table: x.table,
        texists: vec![true; tables.len()],
        parse,
        names,
        zargs: x.zargs,
        long: x.long,
        key: x.key,
        batches: x.batches,
    };
    Ok(Built {
        case: ECase { nprocs, kinds, steps, observe, observe_tables },
        univ,
        row_key: x.row_key,
        vals: x.vals.list,
        names: x.names.list,
    })
}

fn render_val(b: &Built, v: &Option<Val>) -> Value {
    match v {
        None => Value::Null,
        Some(Val::Num(n)) => Value::String(n.to_string()),
        Some(Val::Str(id)) => Value::String(b.vals[*id].clone()),
        Some(Val::Null) => Value::String("\u{1}NULL".into()),
        Some(Val::Empty) => Value::String(String::new()),
        Some(Val::Nul) => Value::String("\u{0}".into()),
    }
}

fn render_obs(b: &Built, o: &EObs) -> Value {
    match o {
        EObs::Ok => json!({"obs": "ok"}),
        EObs::Level(n) => json!({"obs": "level", "tlevel": n}),
        EObs::Value(v) => json!({"obs": "value", "value": render_val(b, v)}),
        EObs::Data(d) => json!({"obs": "data", "data": d}),
        EObs::Test(t) => json!({"obs": "test", "test": t}),
        EObs::Rows(rows) => {
            let mut rs: Vec<(String, String)> = rows.iter().map(|(c, v)| {
                let vs = match render_val(b, &Some(*v)) { Value::String(s) => s, _ => String::new() };
                (b.row_key[*c].clone(), vs)
            }).collect();
            rs.sort();
            json!({"obs": "rows", "rows": rs})
        }
        EObs::Count(n) => json!({"obs": "count", "rowcount": n}),
        EObs::SqlError(n) => json!({"obs": "sql_error", "sqlcode": n}),
        EObs::Err(e) => json!({"obs": "error", "error": match e {
            ErrK::Command => "<COMMAND>",
            ErrK::Dead => "dead",
            ErrK::Busy => "busy",
            ErrK::NothingPending => "nothing pending",
            ErrK::BadPending => "bad pending",
            ErrK::Overflow => "verus-model arithmetic overflow",
        }}),
        EObs::Blocked => json!({"obs": "blocked"}),
        EObs::Pending => json!({"obs": "pending"}),
        EObs::Refused(r) => json!({"obs": "refused", "what": match r {
            RefK::AutocommitOffInTxn => "set_autocommit off inside a transaction",
            RefK::DrvCommitTerm => "drv_commit on term",
            RefK::DrvRollbackTerm => "drv_rollback on term",
            RefK::SetAutocommitTerm => "set_autocommit on term",
            RefK::PpgSetDbapi => "ppg_set on dbapi",
            RefK::PpgGetDbapi => "ppg_get on dbapi",
            RefK::LockOnlyDbapi => "lock_only on dbapi",
            RefK::ZStripDbapi => "z_strip on dbapi",
            RefK::ZClassDbapi => "z_class on dbapi",
            RefK::PutELocked => "put_e on a locked key",
            RefK::InsertSelectBusy => "insert_select while another process holds row locks",
            RefK::InsertSelectNoTwin => "verus-model: insert_select target row missing",
            RefK::OrderTooLong => "canonical numeric subscript longer than 41 characters",
            RefK::SqlFnOther => "verus-model: sql_fn of another name",
            RefK::EmbAssertHeld => "emb_assert on a key another process holds",
            RefK::UpsertTerm => "upsert on term",
            RefK::InsertManyTerm => "insert_many on term",
            RefK::BatchHeld => "executemany over a key another process holds",
            RefK::UpsertFreedom => "INSERT OR UPDATE of a key another process deleted",
        }}),
        EObs::Subs(v) => json!({"obs": "subs", "subs": v.iter().map(|i| b.names[*i as usize].clone()).collect::<Vec<_>>()}),
        EObs::Codes(v) => json!({"obs": "codes", "codes": v}),
        EObs::Ranges(v) => json!({"obs": "value", "value": v.iter().map(|(a, z)| format!("{a}-{z}")).collect::<Vec<_>>().join(",")}),
        EObs::Cell(v, isnull) => json!({"obs": "cell", "value": render_val(b, v), "null": *isnull}),
        EObs::ErrText(c) => json!({"obs": "value", "value": format!("err:{c}")}),
        EObs::RouteRefused => json!({"obs": "value", "value": "refused"}),
        EObs::FnVal(f) => json!({"obs": "value", "value": if *f == 0 { "0.6" } else { "0.8944" }}),
    }
}

fn canon(v: &Value) -> String {
    serde_json::to_string(v).unwrap()
}

struct Perm {
    set: BTreeSet<String>,
    runs: usize,
    overflow: bool,
    freedom: bool,
}

/// Every permitted outcome of the case under `sem`: the exec model over every choice sequence.
fn permitted(sem: &Sem, b: &Built) -> Result<Perm, String> {
    let mut set = BTreeSet::new();
    let mut stack: Vec<Vec<bool>> = vec![vec![]];
    let mut runs = 0;
    let mut overflow = false;
    let mut freedom = false;
    while let Some(ch) = stack.pop() {
        runs += 1;
        if runs > 100_000 {
            return Err("choice enumeration exceeded 100000 runs".into());
        }
        match e_run(sem, &b.univ, &b.case, &ch) {
            ERunRes::NeedMore => {
                freedom = true;
                let mut a = ch.clone();
                a.push(false);
                let mut t = ch;
                t.push(true);
                stack.push(t);
                stack.push(a);
            }
            ERunRes::Done(obs, finals, used) => {
                if used != ch.len() {
                    return Err("a run did not use its choices".into());
                }
                if obs.iter().chain(finals.iter()).any(|o| matches!(o, EObs::Err(ErrK::Overflow))) {
                    overflow = true;
                }
                let v = json!({"obs": obs.iter().map(|o| render_obs(b, o)).collect::<Vec<_>>(),
                               "finals": finals.iter().map(|o| render_obs(b, o)).collect::<Vec<_>>()});
                set.insert(canon(&v));
            }
            ERunRes::Invalid => return Err("case not well formed for the exec model".into()),
        }
    }
    Ok(Perm { set, runs, overflow, freedom })
}

/// The validated contract: the lib's exec constant, verified equal to the specification's `contract_sem()`.
pub fn validated() -> Sem {
    ivg_proofs_env2::clauses::e_contract_sem()
}

/// The Verus model's mutants: the contract's mutants that fall in the subset (same names), then readings seeded for
/// the Verus model. The last group are sharpenings the observations cannot refute (expected alive, not gating).
fn mutants() -> Vec<(&'static str, &'static str, Sem)> {
    let d = validated();
    vec![
        ("unlock-immediate-in-txn", "contract", Sem { unlock_deferred: false, ..d }),
        ("rollback-one-undoes-all", "contract", Sem { rollback_one_is_one_level: false, ..d }),
        ("incr-rolled-back", "contract", Sem { incr_survives: false, ..d }),
        ("no-dirty-reads", "contract", Sem { dirty_reads: false, ..d }),
        ("flat-lock-names", "contract", Sem { hierarchical: false, ..d }),
        ("shared-conflicts-shared", "contract", Sem { shared_compatible: false, ..d }),
        ("non-incremental-locks", "contract", Sem { incremental: false, ..d }),
        ("sql-start-unless-sql-owns", "contract", Sem { sql_start: SqlStartSem::UnlessSqlOwns, ..d }),
        ("sql-start-always", "contract", Sem { sql_start: SqlStartSem::Always, ..d }),
        ("sql-commit-ends-all (product premise, 2026.3)", "contract", Sem { sql_commit: Ends::All, ..d }),
        ("sql-rollback-ends-all (product premise, 2026.3)", "contract", Sem { sql_rollback: Ends::All, ..d }),
        ("driver-rollback-one-level", "contract", Sem { drv_rollback: Ends::One, ..d }),
        ("driver-commit-ends-all", "contract", Sem { drv_commit: Ends::All, ..d }),
        ("autocommit-on-keeps-txn", "contract", Sem { autocommit_on_commits: false, ..d }),
        ("dml-ignores-row-locks", "contract", Sem { dml_waits: false, ..d }),
        ("stop-commits", "contract", Sem { stop_rolls_back: false, ..d }),
        ("rollback-physical", "contract", Sem { rollback_physical: true, ..d }),
        ("ppg-rolled-back", "contract", Sem { ppg_rolled_back: true, ..d }),
        ("failed-dml-opens-nothing", "contract", Sem { failed_dml_opens_txn: false, ..d }),
        ("empty-dml-opens-txn", "contract", Sem { empty_dml_opens_txn: true, ..d }),
        ("select-opens-txn", "contract", Sem { select_opens_txn: true, ..d }),
        ("sqlproc-levels-end-with-statement", "contract-2", Sem { sqlproc_levels_end_with_statement: true, ..d }),
        ("sql-select-committed-only", "contract-2", Sem { select_dirty: false, ..d }),
        ("insert-dup-waits (PostgreSQL reading)", "seeded", Sem { insert_dup_waits: true, ..d }),
        ("row-lock-statement-only", "seeded", Sem { row_lock_held: false, ..d }),
        ("lock-wait-never-granted", "seeded", Sem { lock_wait_grants: false, ..d }),
        ("stop-rolls-back-top-level-only", "seeded", Sem { stop_all_levels: false, ..d }),
        ("kill-not-logged", "seeded", Sem { kill_logged: false, ..d }),
        ("freedom-proceeds-only", "seeded", Sem { freedom: FreedomSem::GoOnly, ..d }),
        // proofs-env2: the extension clauses' mutants (the contracts' names)
        ("vector-l2-available (product premise P-1710)", "contract", Sem { vector_l2_available: true, ..d }),
        ("zstrip-c-ascii-only", "contract", Sem { zstrip_c_c1: false, ..d }),
        ("zstrip-w-space-only", "contract", Sem { zstrip_w_observed: false, ..d }),
        ("string-collation", "contract", Sem { numeric_collation: false, ..d }),
        ("dbapi-empty-param-null", "contract", Sem { dbapi_empty_param_null: true, ..d }),
        ("objectscript-empty-param-empty", "contract", Sem { os_empty_param_null: false, ..d }),
        ("objectscript-reads-empty-as-empty", "contract", Sem { os_reads_empty_as_c0: false, ..d }),
        ("coalesce-c0-differs", "contract", Sem { coalesce_folds_null_empty: false, ..d }),
        ("statement-not-atomic", "contract", Sem { statement_atomic: false, ..d }),
        ("emb-select-committed-only", "contract-2", Sem { emb_select_committed_only: true, ..d }),
        ("emb-ignores-driver-autocommit", "contract-2", Sem { emb_ignores_autocommit: true, ..d }),
        ("emb-empty-host-var-empty", "contract-2", Sem { emb_empty_host_null: false, ..d }),
        ("emb-ignores-row-locks", "contract-2", Sem { emb_ignores_row_locks: true, ..d }),
        ("emb-own-txn", "contract-2", Sem { emb_own_txn: true, ..d }),
        ("maxlen-not-enforced", "contract-2", Sem { maxlen_enforced: false, ..d }),
        ("batch-raises-on-dup", "contract-2", Sem { batch_raises_on_dup: true, ..d }),
        ("batch-atomic", "contract-2", Sem { batch_atomic: true, ..d }),
        ("batch-single-row-skips", "contract-2", Sem { batch_single_row_skips: true, ..d }),
        ("iou-retries-insert", "contract-2", Sem { iou_retries_insert: true, ..d }),
        ("iou-ignores-row-locks", "contract-2", Sem { iou_ignores_row_locks: true, ..d }),
        ("freedom-waits-only (sharpening; expected alive)", "probe", Sem { freedom: FreedomSem::WaitOnly, ..d }),
    ]
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("mutants") {
        for (n, k, _) in mutants() {
            println!("{n}\t{k}");
        }
        return;
    }
    if args.len() < 5 || args[1] != "check" {
        eprintln!("usage: proofs-env-harness check <cases.json> <observed.json> <contract-permitted.json> --round NAME --tables T,S,E,C [--long-keys-refused] [--out report.json]");
        std::process::exit(2);
    }
    let opt = |name: &str| args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).cloned();
    let round = opt("--round").unwrap_or_default();
    let tables: Vec<String> = opt("--tables").unwrap_or("T,S,E,C".into()).split(',').map(String::from).collect();
    let long_keys_refused = args.iter().any(|a| a == "--long-keys-refused");
    let cases: Vec<Value> = serde_json::from_str(&fs::read_to_string(&args[2]).expect("cases")).expect("cases json");
    let observed: BTreeMap<String, Vec<Value>> = serde_json::from_str(&fs::read_to_string(&args[3]).expect("observed")).expect("observed json");
    let contract: BTreeMap<String, Vec<Value>> = serde_json::from_str(&fs::read_to_string(&args[4]).expect("permitted")).expect("permitted json");
    let base = validated();
    let mut outside_subset: BTreeMap<String, usize> = BTreeMap::new();
    let mut in_subset = vec![];
    let mut disagree = vec![];
    let mut outside_obs = vec![];
    let mut errors = vec![];
    let (mut runs, mut singleton, mut max_perm, mut freedom_cases, mut overflow_cases, mut enum_runs) = (0, 0, 0, 0, 0, 0);
    let mut built: Vec<(String, Built, Vec<String>)> = vec![];
    for c in &cases {
        let id = c["id"].as_str().unwrap_or("?").to_string();
        let b = match build(c, &tables, long_keys_refused) {
            Ok(b) => b,
            Err(why) => {
                *outside_subset.entry(why).or_default() += 1;
                continue;
            }
        };
        let perm = match permitted(&base, &b) {
            Ok(p) => p,
            Err(e) => {
                errors.push(json!({"case": id, "error": e}));
                continue;
            }
        };
        in_subset.push(id.clone());
        enum_runs += perm.runs;
        if perm.freedom { freedom_cases += 1; }
        if perm.overflow { overflow_cases += 1; }
        if perm.set.len() == 1 { singleton += 1; }
        max_perm = max_perm.max(perm.set.len());
        let theirs: BTreeSet<String> = contract.get(&id).map(|v| v.iter().map(canon).collect()).unwrap_or_default();
        if theirs != perm.set {
            disagree.push(json!({"case": id, "verus_only": perm.set.difference(&theirs).collect::<Vec<_>>(),
                                 "contract_only": theirs.difference(&perm.set).collect::<Vec<_>>()}));
        }
        let obs: Vec<String> = observed.get(&id).map(|v| v.iter().map(canon).collect()).unwrap_or_default();
        for o in &obs {
            runs += 1;
            if !perm.set.contains(o) {
                outside_obs.push(json!({"case": id, "observed": o}));
            }
        }
        built.push((id, b, obs));
    }
    let mut ms = serde_json::Map::new();
    for (name, kind, sem) in mutants() {
        let mut killers = vec![];
        let mut errs = 0;
        for (id, b, obs) in &built {
            match permitted(&sem, b) {
                Ok(p) => {
                    if obs.iter().any(|o| !p.set.contains(o)) {
                        killers.push(id.clone());
                    }
                }
                Err(_) => errs += 1,
            }
        }
        ms.insert(name.to_string(), json!({"kind": kind, "killed": !killers.is_empty(), "killed_by": killers, "errors": errs}));
    }
    let report = json!({
        "round": round,
        "tables": tables,
        "cases": cases.len(),
        "in_subset": in_subset.len(),
        "outside_subset": outside_subset,
        "agree": in_subset.len() - disagree.len() - 0,
        "disagree": disagree.len(),
        "disagree_detail": disagree,
        "observed_runs": runs,
        "observed_outside_verus": outside_obs.len(),
        "observed_outside_detail": outside_obs,
        "singleton_cases": singleton,
        "max_permitted": max_perm,
        "freedom_cases": freedom_cases,
        "overflow_cases": overflow_cases,
        "enumerated_runs": enum_runs,
        "errors": errors,
        "in_subset_ids": in_subset,
        "mutants": ms,
    });
    let text = serde_json::to_string_pretty(&report).unwrap();
    if let Some(p) = opt("--out") {
        fs::write(p, &text).unwrap();
    }
    let killed: Vec<&String> = ms.iter().filter(|(_, v)| v["killed"].as_bool().unwrap()).map(|(k, _)| k).collect();
    let alive: Vec<&String> = ms.iter().filter(|(_, v)| !v["killed"].as_bool().unwrap()).map(|(k, _)| k).collect();
    println!("HARNESS {round}: cases {} in-subset {} outside-subset {} agree {} disagree {} observed-runs {} outside-verus {} singleton {} max-permitted {} freedom-cases {} overflow {} errors {} mutants {} killed {} alive {:?}",
        cases.len(), in_subset.len(), cases.len() - in_subset.len() - errors.len(), in_subset.len() - disagree.len(), disagree.len(), runs,
        outside_obs.len(), singleton, max_perm, freedom_cases, overflow_cases, errors.len(), ms.len(), killed.len(), alive);
    let ok = disagree.is_empty() && outside_obs.is_empty() && errors.is_empty() && overflow_cases == 0;
    std::process::exit(if ok { 0 } else { 1 });
}
