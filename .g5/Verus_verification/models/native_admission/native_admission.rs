// Native Cypher admission, fallback and shadow comparison, as built at 3eaa79cf (iteration 62).
// Owners: query.native, query.native.gates, query.native.privileges, query.native.reads-only,
// query.native.fallback, query.native.equal-answers (#o05, the comparator), query.shadow, query.native.route (#o03).
//
// Transcribed deciders (see NOTES.md for the source lines and the binding):
//   resolve_native            engine.py IRISGraphEngine.__init__ (native_cypher argument vs IVG_NATIVE_CYPHER)
//   shadow_on                 _engine/query.py QueryMixin._cypher_shadow (read on every call)
//   plan                      cypher/native_plan.py plan_query (+ the ordered/limited flags of _plan_chain/_plan_stages)
//   gate                      cypher/native_plan.py native_gate with engine.py _adjacency_indexed,
//                             _native_privileges, _native_executor_current and their per-engine caches
//   try_native                _engine/query.py QueryMixin._try_native (+ _names_mapped_label, the translation check)
//   run                       iris_src Graph.KG.Cypher.Exec.Run (missing class, plan-version refusal, other faults)
//   warn                      _try_native's _native_warned set, keyed by type and the first 160 message characters
//   compare                   cypher/native_shadow.py compare (+ _key: a value's type is part of it)
//   shadow_out                _engine/query.py QueryMixin._shadow_compare
//   exec_parsed               _engine/query.py QueryMixin._execute_parsed
//   reader                    _engine/query.py QueryMixin.execute_cypher (plain RuntimeError -> error result)
// Abstracted (premises, not derived): the planner's structural grammar beyond the top-level declines and SKIP
// (Query.shape_ok), the translation's is_transactional / width (Query.transactional, Query.width_ok), the rows each
// path computes (World.native_rows, World.sql), and how merge_rows / count_create split a write (Query features of
// the read step are given).
use vstd::prelude::*;
verus! {

// ------------------------------------------------------------------ values, rows and the comparator
pub enum Val { Null, Int(int), Float(int), Str(nat), Bool(bool) }
pub type Row = Seq<Val>;

pub enum What { Columns, RowCount, NotReturnable, RowAt(nat), MissingFromNative, ExtraInNative, SqlFailed }
pub struct Mismatch { pub what: What, pub names_query: bool, pub names_plan: bool, pub names_params: bool, pub row: Option<Row> }
pub enum Cmp { Pass, Fail(Mismatch) }

pub open spec fn cnt(s: Seq<Row>, r: Row) -> nat decreases s.len() {
    if s.len() == 0 { 0 } else { (if s[0] == r { 1nat } else { 0nat }) + cnt(s.drop_first(), r) }
}
pub open spec fn remove1(s: Seq<Row>, r: Row) -> Seq<Row> decreases s.len() {
    if s.len() == 0 { s } else if s[0] == r { s.drop_first() } else { seq![s[0]] + remove1(s.drop_first(), r) }
}
// compare's LIMIT loop: Counter(returnable); for each native row, fail when its count is spent, else decrement
pub open spec fn first_unreturnable(native: Seq<Row>, budget: Seq<Row>) -> Option<Row> decreases native.len() {
    if native.len() == 0 { None }
    else if cnt(budget, native[0]) == 0 { Some(native[0]) }
    else { first_unreturnable(native.drop_first(), remove1(budget, native[0])) }
}
pub open spec fn first_diff(s: Seq<Row>, n: Seq<Row>, i: nat) -> Option<nat>
    decreases (if s.len() < n.len() { s.len() } else { n.len() }) - i
{
    if i >= s.len() || i >= n.len() { None } else if s[i as int] != n[i as int] { Some(i) } else { first_diff(s, n, i + 1) }
}
pub open spec fn bag_equal(s: Seq<Row>, n: Seq<Row>) -> bool { forall|r: Row| #[trigger] cnt(s, r) == cnt(n, r) }
pub open spec fn fail(what: What, row: Option<Row>) -> Cmp {
    // the message is f"... ({what}) for {query!r} with {params!r}"; query is _shadow_compare's
    // str(parsed.source_text or plan): CypherQuery never carries source_text, so the plan's repr is named
    Cmp::Fail(Mismatch { what, names_query: false, names_plan: true, names_params: true, row })
}
pub open spec fn compare(sql_cols: Seq<nat>, sql: Seq<Row>, nat_cols: Seq<nat>, native: Seq<Row>,
    ordered: bool, limited: bool, unlimited: Option<Seq<Row>>) -> Cmp
{
    if sql_cols != nat_cols { fail(What::Columns, None) }
    else if limited && !ordered {
        if sql.len() != native.len() { fail(What::RowCount, None) }
        else {
            let returnable = match unlimited { Some(u) => u, None => sql };
            match first_unreturnable(native, returnable) { Some(r) => fail(What::NotReturnable, Some(r)), None => Cmp::Pass }
        }
    } else if ordered {
        match first_diff(sql, native, 0) {
            Some(i) => fail(What::RowAt(i), Some(native[i as int])),
            None => if sql.len() != native.len() {
                let m = if sql.len() < native.len() { sql.len() } else { native.len() };
                fail(What::RowCount, Some(if native.len() > sql.len() { native[m as int] } else { sql[m as int] }))
            } else { Cmp::Pass },
        }
    } else if bag_equal(sql, native) { Cmp::Pass }
    else if exists|r: Row| cnt(sql, r) > #[trigger] cnt(native, r) {
        fail(What::MissingFromNative, Some(choose|r: Row| cnt(sql, r) > #[trigger] cnt(native, r)))
    } else { fail(What::ExtraInNative, Some(choose|r: Row| cnt(native, r) > #[trigger] cnt(sql, r))) }
}

// The owner's equality rule (query.native.equal-answers), stated over the query's own order, not the plan's flag.
pub open spec fn owner_equal(complete_order: bool, limited: bool, sql: Seq<Row>, unlimited: Seq<Row>, native: Seq<Row>) -> bool {
    if complete_order { sql == native }
    else if limited { sql.len() == native.len() && forall|r: Row| #[trigger] cnt(native, r) <= cnt(unlimited, r) }
    else { bag_equal(sql, native) }
}

// ------------------------------------------------------------------ queries and the planner
pub struct Query {
    pub mutation: bool,        // ast.is_mutation: CREATE/MERGE/SET/REMOVE/DELETE/FOREACH at top level or in a chained part
    pub union: bool, pub union_writes: bool,
    pub procedure: bool,
    pub chained: bool,         // subsequent_queries non-empty
    pub subquery: bool, pub subquery_writes: bool, // a CALL { } clause
    pub skip: bool,
    pub shape_ok: bool,        // abstract: every other _plan_chain/_plan_stages check passes
    pub aggregate: bool, pub order_by: bool, pub order_covers_keys: bool,
    pub complete_order: bool,  // the query's ORDER BY determines every returned row (owner notion)
    pub limit: bool,
    pub labels: Set<nat>,      // every label named in a node pattern
    pub transactional: bool, pub width_ok: bool, // the shared translation
    pub hidden_alias: bool,    // a RETURN alias starting "__" (count_create's __rows, merge_rows' __rm<i>): not a column
    pub anchor: Anchor,        // how Exec finds the walk's first nodes (the plan's anchor)
    pub shape: nat,            // _native_key (parsed repr, parameter types)
}
// Exec.Anchors: a property lookup reads Graph_KG.rdf_props and an id without a label reads Graph_KG.nodes through
// dynamic SQL (%SQL.Statement.%ExecDirect, which checks the caller's SELECT); a labelled id or a label scan reads ^KG.
pub enum Anchor { Scan, LabelledId, PropLookup, IdNoLabel }
pub open spec fn writes(q: Query) -> bool { q.mutation || q.union_writes || q.subquery_writes }
pub open spec fn wf(q: Query) -> bool { (q.union_writes ==> q.union) && (q.subquery_writes ==> q.subquery) }

pub struct Plan { pub ordered: bool, pub limited: bool }
pub open spec fn plan(q: Query) -> Option<Plan> {
    if q.mutation || q.procedure || q.union || q.chained { None }
    else if q.skip || q.subquery || !q.shape_ok { None }   // _plan_chain: skip; clauses must be MATCH/WHERE only
    else { Some(Plan { ordered: if q.aggregate { q.order_by && q.order_covers_keys } else { q.order_by }, limited: q.limit }) }
}

// ------------------------------------------------------------------ switches
pub enum EnvNative { Unset, Zero, Other }
pub open spec fn resolve_native(arg: Option<bool>, env: EnvNative) -> bool {
    match arg { Some(b) => b, None => env != EnvNative::Zero }
}
pub open spec fn shadow_on(attr: bool, env_shadow_one: bool) -> bool { attr || env_shadow_one }

// ------------------------------------------------------------------ world (database state at the call) and engine
pub enum Deployed { Missing, Version(nat) }
pub enum SqlOut { Rows(Seq<nat>, Seq<Row>), ErrorResult(nat), RaiseRuntime(nat), RaiseTyped(nat) }
pub struct Reason { pub ty: nat, pub msg: Seq<nat> }
pub struct World {
    pub index_functional: bool,
    pub sel_nodes: bool, pub sel_labels: bool, pub sel_props: bool, pub sel_edges: bool,
    pub deployed: Deployed, pub version_probe_transient: bool,
    pub fault: Option<Reason>,               // any other Exec.Run failure
    pub mapped: Set<nat>,
    pub env_shadow_one: bool,
    pub native_cols: Seq<nat>, pub native_rows: Seq<Row>,
    pub sql: SqlOut, pub sql_unlimited: SqlOut,
}
pub struct Engine {
    pub native_cypher: bool, pub shadow_attr: bool, pub in_bulk: bool, pub route_on: bool,
    pub idx_cache: Option<bool>, pub priv_cache: Option<bool>, pub exec_cache: Option<bool>,
    pub warned: Set<Reason>, pub log: Seq<Reason>, pub version_warnings: nat,
    pub native_answers: nat, pub route_sql: Set<nat>, pub route_records: nat,
}
pub spec const PLAN_VERSION: nat = 3;
pub spec const CLASS_MISSING: nat = 1;  // message ids
pub spec const RUNTIME_ERROR: nat = 1;  // type ids

pub open spec fn new_engine(arg: Option<bool>, env: EnvNative, shadow_attr: bool) -> Engine {
    Engine { native_cypher: resolve_native(arg, env), shadow_attr, in_bulk: false, route_on: true,
        idx_cache: None, priv_cache: None, exec_cache: None, warned: Set::empty(), log: seq![], version_warnings: 0,
        native_answers: 0, route_sql: Set::empty(), route_records: 0 }
}
// initialize_schema: resets the index and executor answers, never the privilege answer
pub open spec fn setup(e: Engine) -> Engine { Engine { idx_cache: None, exec_cache: None, ..e } }

pub enum Gate { Off, NoIndex, InBulk, NoSelect, NotCurrent }
pub open spec fn idx_probe(e: Engine, w: World) -> (bool, Engine) {
    match e.idx_cache { Some(b) => (b, e), None => (w.index_functional, Engine { idx_cache: Some(w.index_functional), ..e }) }
}
pub open spec fn priv_probe(e: Engine, w: World) -> (bool, Engine) {
    match e.priv_cache {
        Some(b) => (b, e),
        None => { let ok = w.sel_nodes && w.sel_labels && w.sel_props && w.sel_edges; (ok, Engine { priv_cache: Some(ok), ..e }) }
    }
}
pub open spec fn exec_probe(e: Engine, w: World) -> (bool, Engine) {
    match e.exec_cache {
        Some(b) => (b, e),
        None => if w.version_probe_transient { (false, e) }   // a dropped connection: this call only, not remembered
        else {
            let ok = match w.deployed { Deployed::Missing => false, Deployed::Version(v) => v == PLAN_VERSION };
            (ok, Engine { exec_cache: Some(ok), version_warnings: if ok { e.version_warnings } else { e.version_warnings + 1 }, ..e })
        },
    }
}
pub open spec fn gate(e: Engine, w: World) -> (Option<Gate>, Engine) {
    if !e.native_cypher { (Some(Gate::Off), e) }
    else {
        let (ix, e1) = idx_probe(e, w);
        if !ix { (Some(Gate::NoIndex), e1) }
        else if e1.in_bulk { (Some(Gate::InBulk), e1) }
        else {
            let (pv, e2) = priv_probe(e1, w);
            if !pv { (Some(Gate::NoSelect), e2) }
            else { let (cur, e3) = exec_probe(e2, w); if !cur { (Some(Gate::NotCurrent), e3) } else { (None, e3) } }
        }
    }
}
pub open spec fn names_mapped(q: Query, w: World) -> bool { exists|l: nat| q.labels.contains(l) && #[trigger] w.mapped.contains(l) }

pub enum RunOut { Rows(Seq<Row>), Raise(Reason) }
pub spec const ANCHOR_PROPS_99: nat = 2;
pub spec const ANCHOR_NODES_99: nat = 3;
pub open spec fn run(w: World, q: Query) -> RunOut {
    match w.deployed {
        Deployed::Missing => RunOut::Raise(Reason { ty: RUNTIME_ERROR, msg: seq![CLASS_MISSING] }),
        Deployed::Version(v) => if v != PLAN_VERSION { RunOut::Raise(Reason { ty: RUNTIME_ERROR, msg: seq![1000 + v] }) }
            else if q.anchor == Anchor::PropLookup && !w.sel_props { RunOut::Raise(Reason { ty: RUNTIME_ERROR, msg: seq![ANCHOR_PROPS_99] }) }
            else if q.anchor == Anchor::IdNoLabel && !w.sel_nodes { RunOut::Raise(Reason { ty: RUNTIME_ERROR, msg: seq![ANCHOR_NODES_99] }) }
            else { match w.fault { Some(r) => RunOut::Raise(r), None => RunOut::Rows(w.native_rows) } },
    }
}
pub open spec fn key(r: Reason) -> Reason { Reason { ty: r.ty, msg: if r.msg.len() > 160 { r.msg.subrange(0, 160) } else { r.msg } } }
pub open spec fn warn(e: Engine, r: Reason) -> Engine {
    let k = key(r);
    if e.warned.contains(k) { e } else { Engine { warned: e.warned.insert(k), log: e.log.push(k), ..e } }
}
pub open spec fn try_native(e: Engine, w: World, q: Query) -> (Option<(Plan, Seq<Row>)>, Engine) {
    match plan(q) {
        None => (None, e),
        Some(p) => {
            let (g, e1) = gate(e, w);
            if g.is_some() || names_mapped(q, w) || q.transactional || !q.width_ok || q.hidden_alias { (None, e1) }
            else {
                match run(w, q) {
                    RunOut::Raise(r) => (None, warn(e1, r)),
                    RunOut::Rows(rows) => (Some((p, rows)), Engine { native_answers: e1.native_answers + 1, ..e1 }),
                }
            }
        }
    }
}

// ------------------------------------------------------------------ outcomes at _execute_parsed and execute_cypher
pub enum Path { Native, Sql, RoutedSql }
pub enum Err { Mismatch(Mismatch), Runtime(nat), Typed(nat) }
pub enum Out { Answer { path: Path, cols: Seq<nat>, rows: Seq<Row> }, ErrResult(nat), Raise(Err) }
pub open spec fn sql_out(w: World, path: Path) -> Out {
    match w.sql {
        SqlOut::Rows(c, r) => Out::Answer { path, cols: c, rows: r },
        SqlOut::ErrorResult(m) => Out::ErrResult(m),
        SqlOut::RaiseRuntime(m) => Out::Raise(Err::Runtime(m)),
        SqlOut::RaiseTyped(m) => Out::Raise(Err::Typed(m)),
    }
}
pub open spec fn rows_of(s: SqlOut) -> Seq<Row> { match s { SqlOut::Rows(_, r) => r, _ => seq![] } }
pub open spec fn shadow_out(w: World, p: Plan, native: Seq<Row>) -> Out {
    match w.sql {
        SqlOut::ErrorResult(m) => Out::Raise(Err::Mismatch(Mismatch { what: What::SqlFailed, names_query: false,
            names_plan: false, names_params: false, row: None })),
        SqlOut::RaiseRuntime(m) => Out::Raise(Err::Runtime(m)),
        SqlOut::RaiseTyped(m) => Out::Raise(Err::Typed(m)),
        SqlOut::Rows(cols, rows) => {
            if p.limited && !p.ordered && (w.sql_unlimited is RaiseRuntime || w.sql_unlimited is RaiseTyped) {
                match w.sql_unlimited { SqlOut::RaiseRuntime(m) => Out::Raise(Err::Runtime(m)), SqlOut::RaiseTyped(m) => Out::Raise(Err::Typed(m)), _ => Out::ErrResult(0) }
            } else {
                let unl = if p.limited && !p.ordered { Some(rows_of(w.sql_unlimited)) } else { None };
                match compare(cols, rows, w.native_cols, native, p.ordered, p.limited, unl) {
                    Cmp::Pass => Out::Answer { path: Path::Native, cols: w.native_cols, rows: native },
                    Cmp::Fail(m) => Out::Raise(Err::Mismatch(m)),
                }
            }
        }
    }
}
pub open spec fn exec_parsed(e: Engine, w: World, q: Query) -> (Out, Engine) {
    let shadow = shadow_on(e.shadow_attr, w.env_shadow_one);
    if !shadow && e.route_on && e.route_sql.contains(q.shape) { (sql_out(w, Path::RoutedSql), e) }
    else {
        let (tn, e1) = try_native(e, w, q);
        match tn {
            None => (sql_out(w, Path::Sql), e1),
            Some((p, rows)) => if shadow { (shadow_out(w, p, rows), e1) }
                else { (Out::Answer { path: Path::Native, cols: w.native_cols, rows }, Engine { route_records: e1.route_records + 1, ..e1 }) },
        }
    }
}
// execute_cypher for a read reaching _execute_parsed: a plain RuntimeError comes back as an error result
pub open spec fn reader(o: Out, raise_on_error: bool) -> Out {
    match o { Out::Raise(Err::Runtime(m)) => if raise_on_error { o } else { Out::ErrResult(m) }, _ => o }
}
// execute_cypher's chained loop: each part runs through _execute_parsed with subsequent_queries emptied
pub open spec fn chain_part(parent: Query) -> Query { Query { chained: false, ..parent } }
// count_create's ("count", MATCH ... RETURN count(*) AS __rows) and merge_rows' prefix (RETURN ... AS __rm<i>):
// the write's read step is its own query without the write clause, returning an internal alias
pub open spec fn count_step(whole: Query) -> Query { Query { mutation: false, hidden_alias: true, ..whole } }
pub open spec fn merge_prefix(whole: Query) -> Query { Query { mutation: false, hidden_alias: true, ..whole } }
pub open spec fn native_path(o: Out) -> bool { o is Answer && o->path == Path::Native }

// ------------------------------------------------------------------ helpers for the theorems
pub open spec fn open_world(w: World) -> bool {
    w.index_functional && w.sel_nodes && w.sel_labels && w.sel_props && w.sel_edges
    && w.deployed == Deployed::Version(PLAN_VERSION) && !w.version_probe_transient && w.fault.is_none() && w.mapped.is_empty()
}
pub open spec fn plain_read(shape: nat) -> Query {
    Query { mutation: false, union: false, union_writes: false, procedure: false, chained: false, subquery: false,
        subquery_writes: false, skip: false, shape_ok: true, aggregate: false, order_by: false, order_covers_keys: false,
        complete_order: false, limit: false, labels: set![7nat], transactional: false, width_ok: true,
        hidden_alias: false, anchor: Anchor::PropLookup, shape }
}

// ================================================================== theorems: switches (query.native#o01-#o03)
pub proof fn theorem_switch_resolution(env: EnvNative, b: bool)
    ensures resolve_native(None, EnvNative::Unset), resolve_native(None, EnvNative::Other),
        !resolve_native(None, EnvNative::Zero), resolve_native(Some(b), env) == b,
{}
// As built the argument beats the environment: IVG_NATIVE_CYPHER=0 does not reach an engine built with native_cypher=True.
pub proof fn theorem_explicit_true_beats_env_zero(w: World, shape: nat)
    requires open_world(w), !w.env_shadow_one,
    ensures native_path(exec_parsed(new_engine(Some(true), EnvNative::Zero, false), w, plain_read(shape)).0),
        !native_path(exec_parsed(new_engine(None, EnvNative::Zero, false), w, plain_read(shape)).0),
{
    assert(!names_mapped(plain_read(shape), w));
}
// Per engine: two engines over the same world, one with native_cypher=False.
pub proof fn theorem_per_engine_switch(w: World, q: Query)
    requires open_world(w), !w.env_shadow_one, plan(q).is_some(), !q.transactional, q.width_ok, !q.hidden_alias,
    ensures native_path(exec_parsed(new_engine(None, EnvNative::Unset, false), w, q).0),
        exec_parsed(new_engine(Some(false), EnvNative::Unset, false), w, q).0 == sql_out(w, Path::Sql),
{
    assert(!names_mapped(q, w));
}

// ================================================================== theorems: admission gates
// Admitted implies every gate and every planner/engine check held at the call.
pub proof fn theorem_admitted_only_through_every_gate(e: Engine, w: World, q: Query)
    requires native_path(exec_parsed(e, w, q).0),
    ensures plan(q).is_some(), e.native_cypher, !e.in_bulk, !names_mapped(q, w), !q.transactional, q.width_ok, !q.hidden_alias,
        e.idx_cache == Some(true) || (e.idx_cache.is_none() && w.index_functional),
        e.priv_cache == Some(true) || (e.priv_cache.is_none() && w.sel_nodes && w.sel_labels && w.sel_props && w.sel_edges),
        e.exec_cache == Some(true) || (e.exec_cache.is_none() && !w.version_probe_transient && w.deployed == Deployed::Version(PLAN_VERSION)),
        run(w, q) is Rows,
{
    let (tn, e1) = try_native(e, w, q);
    let (g, eg) = gate(e, w);
    assert(tn.is_some());
}
// Any closed gate answers on the SQL path (no route held, shadow off).
pub proof fn theorem_closed_gate_answers_sql(e: Engine, w: World, q: Query)
    requires !shadow_on(e.shadow_attr, w.env_shadow_one), !e.route_sql.contains(q.shape),
        gate(e, w).0.is_some() || plan(q).is_none() || names_mapped(q, w) || q.transactional || !q.width_ok || q.hidden_alias,
    ensures exec_parsed(e, w, q).0 == sql_out(w, Path::Sql),
{}
pub proof fn theorem_bulk_session_keeps_sql(e: Engine, w: World, q: Query)
    requires e.native_cypher, e.idx_cache == Some(true), e.in_bulk, !shadow_on(e.shadow_attr, w.env_shadow_one),
        !e.route_sql.contains(q.shape),
    ensures gate(e, w).0 == Some(Gate::InBulk), exec_parsed(e, w, q).0 == sql_out(w, Path::Sql),
{}
pub proof fn theorem_mapped_label_keeps_sql(e: Engine, w: World, q: Query, l: nat)
    requires q.labels.contains(l), w.mapped.contains(l), !shadow_on(e.shadow_attr, w.env_shadow_one), !e.route_sql.contains(q.shape),
    ensures exec_parsed(e, w, q).0 == sql_out(w, Path::Sql),
{
    assert(names_mapped(q, w));
}
pub proof fn theorem_version_gate(e: Engine, w: World, v: nat)
    requires e.native_cypher, e.idx_cache == Some(true), !e.in_bulk, e.priv_cache == Some(true), e.exec_cache.is_none(),
        !w.version_probe_transient, w.deployed == Deployed::Version(v), v != PLAN_VERSION, w.index_functional,
    ensures gate(e, w).0 == Some(Gate::NotCurrent), gate(e, w).1.exec_cache == Some(false),
        gate(e, w).1.version_warnings == e.version_warnings + 1,
        // remembered: the next call is refused without asking, even once the class is current again
        ({ let w2 = World { deployed: Deployed::Version(PLAN_VERSION), ..w }; gate(gate(e, w).1, w2).0 == Some(Gate::NotCurrent) }),
        // a deploy through initialize_schema asks again
        ({ let w2 = World { deployed: Deployed::Version(PLAN_VERSION), ..w }; gate(setup(gate(e, w).1), w2).0.is_none() }),
{}
pub proof fn theorem_missing_class_gate(e: Engine, w: World)
    requires e.native_cypher, e.idx_cache == Some(true), !e.in_bulk, e.priv_cache == Some(true), e.exec_cache.is_none(),
        !w.version_probe_transient, w.deployed == Deployed::Missing,
    ensures gate(e, w).0 == Some(Gate::NotCurrent), gate(e, w).1.exec_cache == Some(false),
{}
pub proof fn theorem_transient_probe_not_remembered(e: Engine, w: World)
    requires e.native_cypher, e.idx_cache == Some(true), !e.in_bulk, e.priv_cache == Some(true), e.exec_cache.is_none(),
        w.version_probe_transient, w.deployed == Deployed::Version(PLAN_VERSION),
    ensures gate(e, w).0 == Some(Gate::NotCurrent), gate(e, w).1.exec_cache.is_none(),
        gate(gate(e, w).1, World { version_probe_transient: false, ..w }).0.is_none(),
{}
// query.native.privileges#o01: a caller without SELECT on one table is kept off a fresh engine's native path.
pub proof fn theorem_missing_select_keeps_sql(e: Engine, w: World)
    requires e.native_cypher, e.idx_cache == Some(true), !e.in_bulk, e.priv_cache.is_none(),
        !(w.sel_nodes && w.sel_labels && w.sel_props && w.sel_edges),
    ensures gate(e, w).0 == Some(Gate::NoSelect), gate(e, w).1.priv_cache == Some(false),
{}
// query.native.privileges#o03: a REVOKE after the engine's first native read does not reach it; setup does not reset it;
// a new engine sees it.
pub proof fn theorem_revoke_does_not_reach_running_engine(e: Engine, w: World)
    requires e.native_cypher, e.idx_cache == Some(true), !e.in_bulk, e.priv_cache == Some(true), e.exec_cache == Some(true),
        !w.sel_props,
    ensures gate(e, w).0.is_none(), gate(setup(e), World { index_functional: true, deployed: Deployed::Version(PLAN_VERSION), version_probe_transient: false, ..w }).0.is_none(),
        gate(new_engine(Some(true), EnvNative::Unset, false), World { index_functional: true, ..w }).0 == Some(Gate::NoSelect),
{}

// ================================================================== theorems: reads only
pub proof fn theorem_no_write_is_planned(q: Query)
    requires wf(q), writes(q),
    ensures plan(q).is_none(),
{}
pub proof fn theorem_no_write_runs_natively(e: Engine, w: World, q: Query)
    requires wf(q), writes(q),
    ensures !native_path(exec_parsed(e, w, q).0),
{
    let shadow = shadow_on(e.shadow_attr, w.env_shadow_one);
    assert(try_native(e, w, q).0.is_none());
    if shadow { } else { }
}
pub proof fn theorem_call_union_chained_skip_declined(q: Query)
    requires q.procedure || q.union || q.chained || q.skip,
    ensures plan(q).is_none(),
{}
// execute_cypher runs a chained query part by part, each with its chain emptied: the parent is declined, a part
// that is a supported read is admitted (refutes "chained statements take the SQL path" at execute_cypher).
pub proof fn theorem_chained_part_runs_natively(w: World, shape: nat)
    requires open_world(w), !w.env_shadow_one,
    ensures ({ let parent = Query { chained: true, ..plain_read(shape) };
               let part = chain_part(parent);
               plan(parent).is_none() && native_path(exec_parsed(new_engine(None, EnvNative::Unset, false), w, part).0) }),
{
    assert(!names_mapped(plain_read(shape), w));
}
// The read steps count_create and merge_rows build return an internal alias, so the translation's columns are one
// short of the plan and the step stays on SQL; a read statement chained after a write is its own part, admitted, and
// (theorem below) answered natively inside the write's transaction.
pub proof fn theorem_write_read_steps(e: Engine, w: World, whole: Query)
    requires whole.mutation,
    ensures plan(whole).is_none(), !native_path(exec_parsed(e, w, count_step(whole)).0),
        !native_path(exec_parsed(e, w, merge_prefix(whole)).0),
{
    let shadow = shadow_on(e.shadow_attr, w.env_shadow_one);
    assert(try_native(e, w, count_step(whole)).0.is_none());
    assert(try_native(e, w, merge_prefix(whole)).0.is_none());
}
pub proof fn theorem_read_part_of_chained_write_runs_natively(w: World, shape: nat)
    requires open_world(w), !w.env_shadow_one,
    ensures ({ let whole = Query { mutation: true, chained: true, ..plain_read(shape) };
               let read_part = Query { mutation: false, ..chain_part(whole) };
               plan(whole).is_none() && native_path(exec_parsed(new_engine(None, EnvNative::Unset, false), w, read_part).0) }),
{
    assert(!names_mapped(plain_read(shape), w));
}
// A REVOKE reaches a running engine's native read only where Exec finds its anchor through SQL: the property-lookup
// read fails and falls back to the SQL path (one warning); a label scan keeps answering natively.
pub proof fn theorem_revoke_reaches_sql_anchor_only(e: Engine, w: World, q: Query)
    requires e.native_cypher, e.idx_cache == Some(true), !e.in_bulk, e.priv_cache == Some(true), e.exec_cache == Some(true),
        !w.sel_props, w.sel_nodes, w.deployed == Deployed::Version(PLAN_VERSION), w.fault.is_none(), w.mapped.is_empty(),
        !shadow_on(e.shadow_attr, w.env_shadow_one), !e.route_sql.contains(q.shape),
        plan(q).is_some(), !q.transactional, q.width_ok, !q.hidden_alias, !e.warned.contains(Reason { ty: RUNTIME_ERROR, msg: seq![ANCHOR_PROPS_99] }),
    ensures q.anchor == Anchor::PropLookup ==> exec_parsed(e, w, q).0 == sql_out(w, Path::Sql)
            && exec_parsed(e, w, q).1.log.len() == e.log.len() + 1,
        q.anchor == Anchor::Scan ==> native_path(exec_parsed(e, w, q).0),
{
    assert(!names_mapped(q, w));
    let k = Reason { ty: RUNTIME_ERROR, msg: seq![ANCHOR_PROPS_99] };
    assert(key(k) == k);
}

// ================================================================== theorems: fallback
pub proof fn theorem_native_failure_answered_by_sql(e: Engine, w: World, q: Query)
    requires plan(q).is_some(), gate(e, w).0.is_none(), !names_mapped(q, w), !q.transactional, q.width_ok, !q.hidden_alias,
        run(w, q) is Raise,
        !(!shadow_on(e.shadow_attr, w.env_shadow_one) && e.route_on && e.route_sql.contains(q.shape)),
    ensures exec_parsed(e, w, q).0 == sql_out(w, Path::Sql),
        exec_parsed(e, w, q).1.native_answers == gate(e, w).1.native_answers,
{}
pub proof fn theorem_one_warning_per_reason(e: Engine, r: Reason, s: Reason)
    requires !e.warned.contains(key(r)), !e.warned.contains(key(s)), key(r) != key(s),
    ensures warn(warn(e, r), r).log == e.log.push(key(r)),
        warn(warn(e, r), s).log == e.log.push(key(r)).push(key(s)),
{}
// Two messages equal on their first 160 characters are one reason.
pub proof fn theorem_reason_is_type_and_160_chars(e: Engine, m: Seq<nat>, a: nat, b: nat)
    requires m.len() == 160, a != b, !e.warned.contains(Reason { ty: 1, msg: m }), !e.warned.contains(Reason { ty: 2, msg: m }),
    ensures warn(warn(e, Reason { ty: 1, msg: m.push(a) }), Reason { ty: 1, msg: m.push(b) }).log.len() == e.log.len() + 1,
        warn(warn(e, Reason { ty: 1, msg: m }), Reason { ty: 2, msg: m }).log.len() == e.log.len() + 2,
{
    assert(m.push(a).subrange(0, 160) =~= m);
    assert(m.push(b).subrange(0, 160) =~= m);
}
// A new engine warns again: the set is per engine.
pub proof fn theorem_warned_set_is_per_engine(r: Reason)
    ensures warn(new_engine(None, EnvNative::Unset, false), r).log.len() == 1,
{}

// ================================================================== theorems: shadow
pub proof fn theorem_shadow_switches(attr: bool, env: bool)
    ensures shadow_on(attr, env) == (attr || env),
{}
// Shadow mode bypasses routing: a shape whose route holds SQL is answered on the native path and compared.
pub proof fn theorem_shadow_bypasses_route(e: Engine, w: World, q: Query)
    requires shadow_on(e.shadow_attr, w.env_shadow_one), e.route_sql.contains(q.shape),
        try_native(e, w, q).0.is_some(),
    ensures exec_parsed(e, w, q).0 == shadow_out(w, try_native(e, w, q).0.unwrap().0, try_native(e, w, q).0.unwrap().1),
        exec_parsed(e, w, q).1.route_records == e.route_records,
{}
// Every native answer returned in shadow mode passed the comparison with a SQL answer.
pub proof fn theorem_shadow_returns_only_compared(e: Engine, w: World, q: Query)
    requires shadow_on(e.shadow_attr, w.env_shadow_one), native_path(exec_parsed(e, w, q).0),
    ensures try_native(e, w, q).0.is_some(), w.sql is Rows,
        ({ let (p, rows) = try_native(e, w, q).0.unwrap();
           compare(w.sql->Rows_0, w.sql->Rows_1, w.native_cols, rows, p.ordered, p.limited,
                   if p.limited && !p.ordered { Some(rows_of(w.sql_unlimited)) } else { None }) == Cmp::Pass }),
{}
// A difference raises NativeMismatch naming the plan and parameters (not the Cypher text); never an answer.
pub proof fn theorem_shadow_difference_raises(w: World, p: Plan, native: Seq<Row>, m: Mismatch)
    requires w.sql is Rows, !(p.limited && !p.ordered),
        compare(w.sql->Rows_0, w.sql->Rows_1, w.native_cols, native, p.ordered, p.limited, None) == Cmp::Fail(m),
    ensures shadow_out(w, p, native) == Out::Raise(Err::Mismatch(m)), m.names_plan, m.names_params, !m.names_query,
{}
// A SQL error result where native answered raises, naming only the SQL error; a SQL RuntimeError instead reaches
// execute_cypher as an error result (not raised); a typed SQL error propagates.
pub proof fn theorem_shadow_sql_failure(w: World, p: Plan, native: Seq<Row>, m: nat)
    ensures
        shadow_out(World { sql: SqlOut::ErrorResult(m), ..w }, p, native) == Out::Raise(Err::Mismatch(Mismatch {
            what: What::SqlFailed, names_query: false, names_plan: false, names_params: false, row: None })),
        reader(shadow_out(World { sql: SqlOut::RaiseRuntime(m), ..w }, p, native), false) == Out::ErrResult(m),
        reader(shadow_out(World { sql: SqlOut::RaiseTyped(m), ..w }, p, native), false) == Out::Raise(Err::Typed(m)),
{}
// A native failure in shadow mode is answered by SQL, uncompared, and does not raise (q-cyp-002 as built).
pub proof fn theorem_shadow_native_failure_uncompared(e: Engine, w: World, q: Query)
    requires shadow_on(e.shadow_attr, w.env_shadow_one), plan(q).is_some(), gate(e, w).0.is_none(),
        !names_mapped(q, w), !q.transactional, q.width_ok, !q.hidden_alias, run(w, q) is Raise, w.sql is Rows,
    ensures exec_parsed(e, w, q).0 == sql_out(w, Path::Sql), exec_parsed(e, w, q).0 is Answer,
{}

// ================================================================== theorems: the comparator
proof fn lemma_first_diff_none(s: Seq<Row>, n: Seq<Row>, i: nat)
    requires first_diff(s, n, i).is_none(),
    ensures forall|j: int| i <= j < s.len() && j < n.len() ==> s[j] == n[j],
    decreases (if s.len() < n.len() { s.len() } else { n.len() }) - i
{
    if i < s.len() && i < n.len() { lemma_first_diff_none(s, n, i + 1); }
}
proof fn lemma_first_diff_equal(s: Seq<Row>, i: nat)
    ensures first_diff(s, s, i).is_none(),
    decreases s.len() - i
{
    if i < s.len() { lemma_first_diff_equal(s, i + 1); }
}
pub proof fn theorem_ordered_pass_iff_equal(c: Seq<nat>, s: Seq<Row>, n: Seq<Row>)
    ensures (compare(c, s, c, n, true, false, None) == Cmp::Pass) == (s == n),
{
    if compare(c, s, c, n, true, false, None) == Cmp::Pass {
        lemma_first_diff_none(s, n, 0);
        assert(s =~= n);
    }
    if s == n { lemma_first_diff_equal(s, 0); }
}
// 1, '1', 1.0 and true are four answers.
pub proof fn theorem_type_is_part_of_the_value(c: Seq<nat>)
    ensures compare(c, seq![seq![Val::Int(1)]], c, seq![seq![Val::Str(1)]], true, false, None) is Fail,
        compare(c, seq![seq![Val::Int(1)]], c, seq![seq![Val::Float(1)]], true, false, None) is Fail,
        compare(c, seq![seq![Val::Int(1)]], c, seq![seq![Val::Bool(true)]], true, false, None) is Fail,
{
    reveal_with_fuel(first_diff, 2);
    let i1: Row = seq![Val::Int(1)];
    assert(i1 != seq![Val::Str(1)]) by { assert(i1[0] != seq![Val::Str(1)][0]); }
    assert(i1 != seq![Val::Float(1)]) by { assert(i1[0] != seq![Val::Float(1)][0]); }
    assert(i1 != seq![Val::Bool(true)]) by { assert(i1[0] != seq![Val::Bool(true)][0]); }
}
pub proof fn theorem_columns_checked_first(s: Seq<Row>, n: Seq<Row>, o: bool, l: bool, u: Option<Seq<Row>>)
    ensures compare(seq![1nat], s, seq![2nat], n, o, l, u) == fail(What::Columns, None),
{
    assert(seq![1nat] != seq![2nat]) by { assert(seq![1nat][0] != seq![2nat][0]); }
}
pub proof fn theorem_unordered_permutation_passes(c: Seq<nat>, a: Row, b: Row)
    ensures compare(c, seq![a, b], c, seq![b, a], false, false, None) == Cmp::Pass,
{
    reveal_with_fuel(cnt, 3);
    let s: Seq<Row> = seq![a, b];
    let n: Seq<Row> = seq![b, a];
    assert(s.drop_first() =~= seq![b]);
    assert(n.drop_first() =~= seq![a]);
    assert(seq![b].drop_first() =~= Seq::<Row>::empty());
    assert(seq![a].drop_first() =~= Seq::<Row>::empty());
    assert forall|r: Row| #[trigger] cnt(s, r) == cnt(n, r) by {}
    assert(bag_equal(s, n));
}
// bug-cyp-136's shape: one SQL group ('1' and 1 grouped together) vs two native groups.
pub proof fn theorem_unordered_difference_names_missing_row(c: Seq<nat>)
    ensures compare(c, seq![seq![Val::Str(1), Val::Int(2)]], c,
        seq![seq![Val::Str(1), Val::Int(1)], seq![Val::Int(1), Val::Int(1)]], false, false, None) is Fail,
{
    reveal_with_fuel(cnt, 3);
    let s: Seq<Row> = seq![seq![Val::Str(1), Val::Int(2)]];
    let n: Seq<Row> = seq![seq![Val::Str(1), Val::Int(1)], seq![Val::Int(1), Val::Int(1)]];
    let r: Row = seq![Val::Str(1), Val::Int(2)];
    assert(s.drop_first() =~= Seq::<Row>::empty());
    assert(n.drop_first() =~= seq![seq![Val::Int(1), Val::Int(1)]]);
    assert(n.drop_first().drop_first() =~= Seq::<Row>::empty());
    assert(n[0] != r) by { assert(n[0][1] != r[1]); }
    assert(n[1] != r) by { assert(n[1][0] != r[0]); }
    assert(cnt(s, r) == 1);
    assert(cnt(n, r) == 0);
    assert(!bag_equal(s, n));
}
// LIMIT without a complete order: native may keep other rows of the full answer, same count.
pub proof fn theorem_limit_other_rows_pass(c: Seq<nat>, a: Row, b: Row, x: Row)
    requires a != x, b != x, a != b,
    ensures compare(c, seq![a], c, seq![x], false, true, Some(seq![a, b, x])) == Cmp::Pass,
{
    reveal_with_fuel(cnt, 4);
    reveal_with_fuel(first_unreturnable, 2);
    let u: Seq<Row> = seq![a, b, x];
    assert(u.drop_first() =~= seq![b, x]);
    assert(u.drop_first().drop_first() =~= seq![x]);
    assert(seq![x].drop_first() =~= Seq::<Row>::empty());
    assert(seq![x].drop_first().len() == 0);
}
pub proof fn theorem_limit_outside_row_raises(c: Seq<nat>, a: Row, b: Row, z: Row)
    requires a != z, b != z,
    ensures compare(c, seq![a], c, seq![z], false, true, Some(seq![a, b])) == fail(What::NotReturnable, Some(z)),
{
    reveal_with_fuel(cnt, 3);
    reveal_with_fuel(first_unreturnable, 2);
    assert(seq![a, b].drop_first() =~= seq![b]);
    assert(seq![b].drop_first() =~= Seq::<Row>::empty());
}
// A LIMIT count difference raises without naming any row.
pub proof fn theorem_limit_count_names_no_row(c: Seq<nat>, a: Row, b: Row, u: Seq<Row>)
    ensures compare(c, seq![a, b], c, seq![a], false, true, Some(u)) == fail(What::RowCount, None),
{}
// F-0907 / equal-answers#o05: an ORDER BY that leaves ties marks the plan ordered, so a tie permutation (valid under
// the owner's rule) raises, with or without LIMIT; the LIMIT rule is reached only when the plan has no ORDER BY.
pub proof fn theorem_partial_order_compared_in_order(c: Seq<nat>, a: Row, b: Row, lim: bool)
    requires a != b,
    ensures ({ let q = Query { order_by: true, complete_order: false, limit: lim, ..plain_read(0) };
        plan(q).unwrap().ordered
        && compare(c, seq![a, b], c, seq![b, a], plan(q).unwrap().ordered, plan(q).unwrap().limited, None) is Fail
        && owner_equal(q.complete_order, false, seq![a, b], seq![a, b], seq![b, a]) }),
        ({ let q = Query { order_by: true, complete_order: false, limit: true, ..plain_read(0) };
        compare(c, seq![a], c, seq![b], plan(q).unwrap().ordered, plan(q).unwrap().limited, None) is Fail
        && owner_equal(false, true, seq![a], seq![a, b], seq![b]) }),
{
    reveal_with_fuel(first_diff, 2);
    reveal_with_fuel(cnt, 3);
    assert(seq![a, b].drop_first() =~= seq![b]);
    assert(seq![b, a].drop_first() =~= seq![a]);
    assert(seq![b].drop_first() =~= Seq::<Row>::empty());
    assert(seq![a].drop_first() =~= Seq::<Row>::empty());
    let ab: Seq<Row> = seq![a, b];
    let ba: Seq<Row> = seq![b, a];
    let bb: Seq<Row> = seq![b];
    assert forall|r: Row| #[trigger] cnt(ab, r) == cnt(ba, r) by {}
    assert forall|r: Row| #[trigger] cnt(bb, r) <= cnt(ab, r) by {}
}
// SKIP is never compared: the planner declines it.
pub proof fn theorem_skip_never_compared(e: Engine, w: World, q: Query)
    requires q.skip,
    ensures try_native(e, w, q).0.is_none(),
{}
// An aggregate ordered on every grouping key is a complete order; otherwise its groups compare as a multiset.
pub proof fn theorem_aggregate_order_flag(q: Query)
    requires plan(q).is_some(), q.aggregate,
    ensures plan(q).unwrap().ordered == (q.order_by && q.order_covers_keys),
{}

} // verus!
