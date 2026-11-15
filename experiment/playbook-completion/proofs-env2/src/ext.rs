//! proofs-env2: the r6 extension clauses and contract-2's E-1 brought into the specification (this increment:
//! X-TLEVEL-SQL, X-VEC's SQL functions, X-ZSTRIP, X-ORDER, X-NULL, X-STMT's INSERT ... SELECT, E-1, X2-BATCH, X2-IOU), mirroring
//! `iris-contract/src/lib.rs` (r6) and `contract-2/contract/src/lib.rs` clause for clause.
use vstd::prelude::*;
use crate::spec::*;

verus! {

pub open spec fn is_ext_op(op: Op) -> bool {
    op is SqlTLevel || op is SqlFn || op is ZStrip || op is ZClass || op is Order || op is PutE || op is GetE
        || op is MatchE || op is InsertSelect || op is EmbRegister || op is EmbRetract || op is EmbCount || op is EmbRoute
        || op is EmbAssert || op is Upsert || op is InsertMany
}

// ------------------------------------------------------------------------------------------------ X-VEC (functions)

pub open spec fn sqlfn_obs(sem: Sem, f: u8) -> Obs {
    if f == 0 || f == 1 {
        Obs::FnVal(0)
    } else if f == 2 {
        if sem.vector_l2_available { Obs::FnVal(1) } else { Obs::SqlError(-359i64) }
    } else {
        Obs::Refused(RefK::SqlFnOther)
    }
}

// ------------------------------------------------------------------------------------------------ X-ZSTRIP

/// `$ZSTRIP` character classes C and W (the classes the product uses).
pub open spec fn zclass(sem: Sem, ch: u32, c: u32) -> bool {
    if ch == 67 {
        if sem.zstrip_c_c1 { c <= 31 || (127 <= c && c <= 159) } else { c <= 31 || c == 127 }
    } else if ch == 87 {
        if sem.zstrip_w_observed { c == 9 || c == 32 || c == 160 } else { c == 32 }
    } else {
        false
    }
}

pub open spec fn is_action(c: u32) -> bool { c == 42 || c == 60 || c == 62 || c == 61 }

pub open spec fn upper(c: u32) -> u32 { if 97 <= c && c <= 122 { (c - 32) as u32 } else { c } }

/// The character is removed by the mask's classes or listed in `rem`.
pub open spec fn zm(sem: Sem, a: ZArg, c: u32) -> bool {
    a.rem.contains(c) || exists|i: int| 0 <= i < a.mask.len() && !is_action(#[trigger] a.mask[i]) && zclass(sem, upper(a.mask[i]), c)
}

pub open spec fn zfilter(sem: Sem, a: ZArg, s: Seq<u32>) -> Seq<u32>
    decreases s.len()
{
    if s.len() == 0 { s } else {
        let r = zfilter(sem, a, s.drop_last());
        if zm(sem, a, s.last()) { r } else { r.push(s.last()) }
    }
}

pub open spec fn zlead(sem: Sem, a: ZArg, s: Seq<u32>, i: nat) -> nat
    decreases s.len() - i
{
    if i >= s.len() { s.len() } else if zm(sem, a, s[i as int]) { zlead(sem, a, s, i + 1) } else { i }
}

pub open spec fn ztrail(sem: Sem, a: ZArg, s: Seq<u32>) -> Seq<u32>
    decreases s.len()
{
    if s.len() > 0 && zm(sem, a, s.last()) { ztrail(sem, a, s.drop_last()) } else { s }
}

pub open spec fn zcollapse(sem: Sem, a: ZArg, s: Seq<u32>) -> Seq<u32>
    decreases s.len()
{
    if s.len() == 0 { s } else {
        let r = zcollapse(sem, a, s.drop_last());
        let c = s.last();
        if zm(sem, a, c) && r.len() > 0 && r.last() == c { r } else { r.push(c) }
    }
}

pub open spec fn zstrip(sem: Sem, a: ZArg) -> Seq<u32> {
    if a.mask.contains(42u32) {
        zfilter(sem, a, a.s)
    } else {
        let v1 = if a.mask.contains(60u32) { a.s.subrange(zlead(sem, a, a.s, 0) as int, a.s.len() as int) } else { a.s };
        let v2 = if a.mask.contains(62u32) { ztrail(sem, a, v1) } else { v1 };
        if a.mask.contains(61u32) { zcollapse(sem, a, v2) } else { v2 }
    }
}

/// `ranges`: the code points 0..=65535 in the class, as maximal ranges.
pub open spec fn zranges(sem: Sem, ch: u32, c: nat, start: Option<u32>) -> Seq<(u32, u32)>
    decreases 65537 - c
{
    if c > 65536 {
        Seq::empty()
    } else {
        let inc = c <= 65535 && zclass(sem, ch, c as u32);
        if inc && start is None {
            zranges(sem, ch, c + 1, Some(c as u32))
        } else if !inc && start is Some {
            seq![(start->Some_0, (c - 1) as u32)] + zranges(sem, ch, c + 1, None)
        } else {
            zranges(sem, ch, c + 1, start)
        }
    }
}

// ------------------------------------------------------------------------------------------------ X-ORDER

/// Lexicographic order of code-point sequences (-1, 0, 1).
pub open spec fn lexcmp(a: Seq<u32>, b: Seq<u32>) -> int
    decreases a.len()
{
    if a.len() == 0 {
        if b.len() == 0 { 0 } else { -1 }
    } else if b.len() == 0 {
        1
    } else if a[0] < b[0] {
        -1
    } else if a[0] > b[0] {
        1
    } else {
        lexcmp(a.drop_first(), b.drop_first())
    }
}

pub open spec fn all_digits(s: Seq<u32>) -> bool { forall|i: int| 0 <= i < s.len() ==> 48 <= #[trigger] s[i] <= 57 }

/// The first index of `x` at or after i.
pub open spec fn find_cp(s: Seq<u32>, x: u32, i: nat) -> Option<nat>
    decreases s.len() - i
{
    if i >= s.len() { None } else if s[i as int] == x { Some(i) } else { find_cp(s, x, i + 1) }
}

/// IRIS canonical number form (`canonical_number`): sign, integer part, fraction.
pub open spec fn canonical(s: Seq<u32>) -> Option<(bool, Seq<u32>, Seq<u32>)> {
    let neg = s.len() > 0 && s[0] == 45;
    let body = if neg { s.drop_first() } else { s };
    let dot = find_cp(body, 46, 0);
    let ip = match dot { Some(i) => body.subrange(0, i as int), None => body };
    let frac = match dot { Some(i) => body.subrange(i as int + 1, body.len() as int), None => Seq::empty() };
    if dot is Some && (frac.len() == 0 || frac.last() == 48) {
        None
    } else if !all_digits(ip) || !all_digits(frac) {
        None
    } else if ip.len() == 0 && frac.len() == 0 {
        None
    } else if frac.len() > 0 && ip == seq![48u32] {
        None
    } else if ip.len() > 1 && ip[0] == 48 {
        None
    } else if neg && ip == seq![48u32] && frac.len() == 0 {
        None
    } else {
        Some((neg, ip, frac))
    }
}

pub open spec fn trim0(s: Seq<u32>) -> Seq<u32>
    decreases s.len()
{
    if s.len() > 0 && s[0] == 48 { trim0(s.drop_first()) } else { s }
}

pub open spec fn cmp_abs(x: (bool, Seq<u32>, Seq<u32>), y: (bool, Seq<u32>, Seq<u32>)) -> int {
    let a = trim0(x.1);
    let b = trim0(y.1);
    if a.len() < b.len() { -1 } else if a.len() > b.len() { 1 } else if lexcmp(a, b) != 0 { lexcmp(a, b) } else { lexcmp(x.2, y.2) }
}

/// `$ORDER` collation: canonical numbers first, numerically; then strings by code point.
pub open spec fn collate(a: Seq<u32>, b: Seq<u32>) -> int {
    match (canonical(a), canonical(b)) {
        (Some(x), Some(y)) => if !x.0 && !y.0 { cmp_abs(x, y) } else if x.0 && y.0 { cmp_abs(y, x) } else if x.0 { -1 } else { 1 },
        (Some(_), None) => -1,
        (None, Some(_)) => 1,
        (None, None) => lexcmp(a, b),
    }
}

pub open spec fn name_of(u: U, x: u64) -> Seq<u32> {
    if (x as int) < u.names.len() { u.names[x as int] } else { Seq::empty() }
}

pub open spec fn sub_lt(sem: Sem, u: U, x: u64, y: u64) -> bool {
    if sem.numeric_collation { collate(name_of(u, x), name_of(u, y)) < 0 } else { lexcmp(name_of(u, x), name_of(u, y)) < 0 }
}

pub open spec fn sub_of(u: U, node: int, j: int) -> u64 { u.paths[j][u.paths[node].len() as int] }

/// The distinct subscripts one level below `node` of the defined cells under it, in cell order.
pub open spec fn subs_from(u: U, g: Seq<Option<Val>>, node: int, j: nat, acc: Seq<u64>) -> Seq<u64>
    decreases u.n() - j
{
    if j >= u.n() {
        acc
    } else {
        let take = covers(u, node, j as int) && u.paths[j as int].len() > u.paths[node].len() && g[j as int] is Some
            && !acc.contains(sub_of(u, node, j as int));
        subs_from(u, g, node, j + 1, if take { acc.push(sub_of(u, node, j as int)) } else { acc })
    }
}

/// Insert x before the first element it precedes.
pub open spec fn ins_sorted(sem: Sem, u: U, x: u64, l: Seq<u64>) -> Seq<u64>
    decreases l.len()
{
    if l.len() == 0 { seq![x] } else if sub_lt(sem, u, x, l[0]) { seq![x] + l } else { seq![l[0]] + ins_sorted(sem, u, x, l.drop_first()) }
}

pub open spec fn isort(sem: Sem, u: U, l: Seq<u64>) -> Seq<u64>
    decreases l.len()
{
    if l.len() == 0 { l } else { ins_sorted(sem, u, l.last(), isort(sem, u, l.drop_last())) }
}

pub open spec fn max_chars() -> nat { 41 }

pub open spec fn too_long_number(u: U, x: u64) -> bool {
    canonical(name_of(u, x)) is Some && name_of(u, x).len() > max_chars()
}

pub open spec fn order_obs(sem: Sem, u: U, g: Seq<Option<Val>>, c: usize) -> Obs {
    let l = subs_from(u, g, c as int, 0, Seq::empty());
    if exists|i: int| 0 <= i < l.len() && too_long_number(u, #[trigger] l[i]) {
        Obs::Refused(RefK::OrderTooLong)
    } else {
        Obs::Subs(isort(sem, u, l))
    }
}

// ------------------------------------------------------------------------------------------------ X-NULL

pub open spec fn stored(sem: Sem, kind: Kind, v: Param, literal: bool) -> Val {
    match v {
        Param::PNull => Val::Null,
        Param::PEmpty => if literal {
            Val::Empty
        } else if (kind == Kind::Term && sem.os_empty_param_null) || (kind == Kind::Dbapi && sem.dbapi_empty_param_null) {
            Val::Null
        } else {
            Val::Empty
        },
        Param::PNul => Val::Empty,
        Param::PV(x) => x,
    }
}

pub open spec fn gete_obs(sem: Sem, kind: Kind, c: Option<Val>) -> Obs {
    match c {
        None => Obs::Rows(Seq::empty()),
        Some(v) => {
            let null = v == Val::Null;
            if kind == Kind::Term {
                Obs::Cell(Some(if null { Val::Empty } else if v == Val::Empty && sem.os_reads_empty_as_c0 { Val::Nul } else { v }), null)
            } else {
                Obs::Cell(if null { None } else { Some(v) }, null)
            }
        },
    }
}

pub open spec fn blank(v: Val) -> bool { v == Val::Null || v == Val::Empty }

pub open spec fn matches_e(sem: Sem, c: Val, param: Val) -> bool {
    if sem.coalesce_folds_null_empty && blank(param) { blank(c) } else { c == param }
}

pub open spec fn match_from(sem: Sem, u: U, g: Seq<Option<Val>>, t: usize, param: Val, j: nat) -> nat
    decreases u.n() - j
{
    if j >= u.n() {
        0
    } else {
        let hit = u.is_row[j as int] && u.table[j as int] == t && g[j as int] is Some && matches_e(sem, g[j as int]->Some_0, param);
        (if hit { 1nat } else { 0nat }) + match_from(sem, u, g, t, param, j + 1)
    }
}

pub open spec fn count_obs(n: nat) -> Obs {
    if n <= i64::MAX { Obs::Count(n as i64) } else { Obs::Err(ErrK::Overflow) }
}

// ------------------------------------------------------------------------------------------------ X-STMT: INSERT ... SELECT

/// Some other process holds a row lock (any table).
pub open spec fn others_hold_rows(s: State, p: usize) -> bool {
    exists|q: int, r: int| 0 <= q < s.procs.len() && q != p && 0 <= r < s.procs[q].rlocks.len() && #[trigger] s.procs[q].rlocks[r]
}

/// The row cell of table t with key k (the harness gives every source key its target row).
pub open spec fn find_twin(u: U, t: usize, k: usize, j: nat) -> Option<usize>
    decreases u.n() - j
{
    if j >= u.n() {
        None
    } else if u.is_row[j as int] && u.table[j as int] == t && u.key[j as int] == k {
        Some(j as usize)
    } else {
        find_twin(u, t, k, j + 1)
    }
}

pub open spec fn twin(u: U, to: usize, r: usize) -> usize {
    match find_twin(u, to, u.key[r as int], 0) { Some(j) => j, None => 0 }
}

pub open spec fn twins_ok(u: U, to: usize, src: Seq<(usize, Val)>) -> bool {
    forall|i: int| 0 <= i < src.len() ==> find_twin(u, to, u.key[(#[trigger] src[i]).0 as int], 0) is Some
}

/// The first source row whose key `to` already holds.
pub open spec fn first_fail(u: U, g: Seq<Option<Val>>, to: usize, src: Seq<(usize, Val)>, i: nat) -> Option<nat>
    decreases src.len() - i
{
    if i >= src.len() { None } else if g[twin(u, to, src[i as int].0) as int] is Some { Some(i) } else { first_fail(u, g, to, src, i + 1) }
}

pub open spec fn is_write(u: U, s: State, p: usize, to: usize, src: Seq<(usize, Val)>, i: nat, n: nat) -> State
    decreases n - i
{
    if i >= n || i >= src.len() { s } else {
        is_write(u, write(s, p, twin(u, to, src[i as int].0), Some(src[i as int].1), true), p, to, src, i + 1, n)
    }
}

pub open spec fn is_lock(u: U, s: State, p: usize, to: usize, src: Seq<(usize, Val)>, i: nat, n: nat) -> State
    decreases n - i
{
    if i >= n || i >= src.len() { s } else {
        is_lock(u, set_rlock(s, p, twin(u, to, src[i as int].0), true), p, to, src, i + 1, n)
    }
}

pub open spec fn insert_select(sem: Sem, u: U, s: State, p: usize, from: usize, to: usize) -> (State, Obs) {
    if others_hold_rows(s, p) {
        (s, Obs::Refused(RefK::InsertSelectBusy))
    } else if !u.texists[from as int] || !u.texists[to as int] {
        (s, Obs::SqlError(-30i64))
    } else {
        let src = rows_from(u, s.g, from, 0);
        if !twins_ok(u, to, src) {
            (s, Obs::Refused(RefK::InsertSelectNoTwin))
        } else {
            let fail = first_fail(u, s.g, to, src, 0);
            if fail is Some && (sem.statement_atomic || fail->Some_0 == 0) {
                (failed_stmt(sem, s, p), Obs::SqlError(-119i64))
            } else {
                let n: nat = match fail { Some(i) => i, None => src.len() };
                let b = stmt_begin(s, p);
                let s2 = is_write(u, b.0, p, to, src, 0, n);
                let s3 = if b.1 { commit_top(s2, p) } else if sem.row_lock_held { is_lock(u, s2, p, to, src, 0, n) } else { s2 };
                (s3, if fail is Some { Obs::SqlError(-119i64) } else { count_obs(n) })
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ E-1 (embedded SQL)

pub open spec fn set_autocommit(s: State, p: usize, on: bool) -> State {
    upd(s, p, Proc { autocommit: on, ..s.procs[p as int] })
}

/// One DML statement with its own (unlogged, lock-free) transaction: the emb-own-txn mutant.
pub open spec fn own_dml(sem: Sem, u: U, s: State, p: usize, r: usize, ins: Option<Val>) -> (State, Obs) {
    if !u.texists[u.table[r as int] as int] {
        (s, Obs::SqlError(-30i64))
    } else {
        match ins {
            Some(v) => if s.g[r as int] is Some { (failed_stmt(sem, s, p), Obs::SqlError(-119i64)) } else { (write(s, p, r, Some(v), false), Obs::Count(1i64)) },
            None => if s.g[r as int] is None {
                (if sem.empty_dml_opens_txn { failed_stmt(sem, s, p) } else { s }, Obs::Count(0i64))
            } else {
                (write(s, p, r, None, false), Obs::Count(1i64))
            },
        }
    }
}

pub open spec fn plain_dml(sem: Sem, u: U, s: State, p: usize, r: usize, ins: Option<Val>) -> (State, Obs) {
    match ins { Some(v) => dml_insert(sem, u, s, p, r, v), None => dml_change(sem, u, s, p, r, None) }
}

/// The pin's embedded DML statement: the dynamic statement's effect (E-1), unless an E-1 mutant changes it.
pub open spec fn emb_dml(sem: Sem, u: U, s: State, p: usize, r: usize, ins: Option<Val>) -> (State, Obs) {
    if sem.emb_own_txn {
        own_dml(sem, u, s, p, r, ins)
    } else if sem.emb_ignores_autocommit && level(s.procs[p as int]) == 0 {
        let ac = s.procs[p as int].autocommit;
        let o = plain_dml(sem, u, set_autocommit(s, p, true), p, r, ins);
        (set_autocommit(o.0, p, ac), o.1)
    } else {
        plain_dml(sem, u, s, p, r, ins)
    }
}

pub open spec fn emb_visible(sem: Sem, s: State, p: usize, r: usize) -> bool {
    if sem.emb_select_committed_only { cv_from(sem, s, p, 0).g[r as int] is Some } else { s.g[r as int] is Some }
}

pub open spec fn reg_obs(o: Obs) -> Obs {
    match o {
        Obs::Count(_) => Obs::Value(Some(Val::Num(0))),
        Obs::SqlError(c) => if c == -119 { Obs::Value(Some(Val::Num(0))) } else { Obs::Value(Some(Val::Num(c))) },
        other => other,
    }
}

pub open spec fn retract_obs(o: Obs) -> Obs {
    match o {
        Obs::Count(_) => Obs::Value(Some(Val::Num(1))),
        Obs::SqlError(c) => Obs::ErrText(c),
        other => other,
    }
}

pub open spec fn emb_long(sem: Sem, u: U, r: usize) -> bool { sem.maxlen_enforced && u.long[r as int] }

/// EmbRegister's Freedom (the INSERT over another transaction's uncommitted DELETE).
pub open spec fn ext_choice(sem: Sem, u: U, s: State, p: usize, op: Op) -> bool {
    op matches Op::EmbRegister { r } && !emb_visible(sem, s, p, r) && !emb_long(sem, u, r) && !sem.emb_ignores_row_locks
        && freedom_cond(sem, s, p, r)
}

pub open spec fn emb_register(sem: Sem, u: U, s: State, p: usize, r: usize, choice: bool) -> (State, Obs) {
    if emb_visible(sem, s, p, r) {
        (s, Obs::Value(Some(Val::Num(0))))
    } else if emb_long(sem, u, r) {
        (failed_stmt(sem, s, p), Obs::Value(Some(Val::Num(-104i64))))
    } else if !sem.emb_ignores_row_locks && freedom_cond(sem, s, p, r) {
        let goes = match sem.freedom { FreedomSem::Both => choice, FreedomSem::WaitOnly => false, FreedomSem::GoOnly => true };
        if goes {
            let o = emb_dml(sem, u, s, p, r, Some(Val::Empty));
            (set_rlock(o.0, p, r, false), reg_obs(o.1))
        } else {
            (set_pending(s, p, Some(Op::EmbRegister { r })), Obs::Pending)
        }
    } else {
        let o = emb_dml(sem, u, s, p, r, Some(Val::Empty));
        (o.0, reg_obs(o.1))
    }
}

pub open spec fn emb_assert(sem: Sem, u: U, s: State, p: usize, rn: usize, rr: usize, empty: bool, vt: Val) -> (State, Obs) {
    if row_held(s, p, rn) || row_held(s, p, rr) {
        (s, Obs::Refused(RefK::EmbAssertHeld))
    } else if empty && sem.emb_empty_host_null {
        (failed_stmt(sem, s, p), Obs::ErrText(-108i64))
    } else {
        let o1 = if !emb_visible(sem, s, p, rn) { emb_dml(sem, u, s, p, rn, Some(Val::Empty)) } else { (s, Obs::Ok) };
        match o1.1 {
            Obs::SqlError(c) => (o1.0, Obs::ErrText(c)),
            _ => {
                let o2 = if !emb_visible(sem, o1.0, p, rr) { emb_dml(sem, u, o1.0, p, rr, Some(vt)) } else { (o1.0, Obs::Ok) };
                match o2.1 {
                    Obs::SqlError(c) => (o2.0, Obs::ErrText(c)),
                    _ => (o2.0, Obs::Value(Some(Val::Num(1)))),
                }
            },
        }
    }
}

pub open spec fn rows_count(u: U, g: Seq<Option<Val>>, t: usize) -> nat { rows_from(u, g, t, 0).len() }

// ------------------------------------------------------------------------------------------------ X2-BATCH, X2-IOU (contract-2)

/// The parameter rows of an `executemany` are rows of its table.
pub open spec fn batch_ok(u: U, t: usize, rows: Seq<(usize, Val)>) -> bool {
    forall|i: int| 0 <= i < rows.len() ==> ((#[trigger] rows[i]).0 as int) < u.n() && u.is_row[rows[i].0 as int]
        && u.table[rows[i].0 as int] == t
}

/// Some parameter row's key is row-locked by another process (the contract refuses: outside the suite).
pub open spec fn batch_held(s: State, p: usize, rows: Seq<(usize, Val)>, i: nat) -> bool
    decreases rows.len() - i,
{
    if i < rows.len() { row_held(s, p, rows[i as int].0) || batch_held(s, p, rows, i + 1) } else { false }
}

/// The batch-atomic mutant's probe: the first row (from i) whose INSERT would fail, on the globals the earlier rows wrote
/// (an INSERT's outcome depends only on its table's existence and its row's visibility).
pub open spec fn batch_probe(u: U, g: Seq<Option<Val>>, rows: Seq<(usize, Val)>, i: nat) -> Option<i64>
    decreases rows.len() - i,
{
    if i < rows.len() {
        let r = rows[i as int].0;
        if !u.texists[u.table[r as int] as int] { Some(-30i64) }
        else if g[r as int] is Some { Some(-119i64) }
        else { batch_probe(u, g.update(r as int, Some(rows[i as int].1)), rows, i + 1) }
    } else {
        None
    }
}

/// `executemany`'s row loop from row i with n rows written: each row one INSERT statement; a failing row is skipped
/// (or, under batch-raises-on-dup, ends the call with its error).
pub open spec fn batch_run(sem: Sem, u: U, s: State, p: usize, rows: Seq<(usize, Val)>, i: nat, n: nat) -> (State, Obs)
    decreases rows.len() - i,
{
    if i < rows.len() {
        let o = dml_insert(sem, u, s, p, rows[i as int].0, rows[i as int].1);
        match o.1 {
            Obs::Count(_) => batch_run(sem, u, o.0, p, rows, i + 1, n + 1),
            Obs::SqlError(c) => if sem.batch_raises_on_dup { (o.0, Obs::SqlError(c)) } else { batch_run(sem, u, o.0, p, rows, i + 1, n) },
            _ => o,
        }
    } else {
        (s, count_obs(n))
    }
}

/// X2-BATCH: DB-API `executemany` of an INSERT (`Engine::insert_many`).
pub open spec fn insert_many(sem: Sem, u: U, s: State, p: usize, rows: Seq<(usize, Val)>) -> (State, Obs) {
    if batch_held(s, p, rows, 0) {
        (s, Obs::Refused(RefK::BatchHeld))
    } else if rows.len() == 1 && !sem.batch_single_row_skips {
        dml_insert(sem, u, s, p, rows[0].0, rows[0].1)
    } else if sem.batch_atomic && batch_probe(u, s.g, rows, 0) is Some {
        (failed_stmt(sem, s, p), Obs::SqlError(batch_probe(u, s.g, rows, 0)->Some_0))
    } else {
        batch_run(sem, u, s, p, rows, 0, 0)
    }
}

/// X2-IOU: `INSERT OR UPDATE` once not waiting (`after_wait`: completing a wait), `Engine::upsert_run`.
pub open spec fn upsert_run(sem: Sem, u: U, s: State, p: usize, r: usize, v: Val, after_wait: bool) -> (State, Obs) {
    if s.g[r as int] is Some {
        dml_change(sem, u, s, p, r, Some(v))
    } else if after_wait && !sem.iou_retries_insert {
        (failed_stmt(sem, s, p), Obs::SqlError(-109i64))
    } else if freedom_cond(sem, s, p, r) {
        (s, Obs::Refused(RefK::UpsertFreedom))
    } else {
        dml_insert(sem, u, s, p, r, v)
    }
}

// ------------------------------------------------------------------------------------------------ one operation

pub open spec fn ext_step(sem: Sem, u: U, s: State, p: usize, op: Op, choice: bool) -> (State, Obs) {
    let kind = s.procs[p as int].kind;
    match op {
        Op::SqlTLevel => { let s1 = select_txn(sem, s, p); (s1, Obs::Level(level(s1.procs[p as int]))) },
        Op::SqlFn { f } => (s, sqlfn_obs(sem, f)),
        Op::ZStrip { a } => (s, Obs::Codes(zstrip(sem, u.zargs[a as int]))),
        Op::ZClass { ch } => (s, Obs::Ranges(zranges(sem, ch, 0, None))),
        Op::Order { c } => (s, order_obs(sem, u, s.g, c)),
        Op::PutE { r, v, literal } => if row_held(s, p, r) {
            (s, Obs::Refused(RefK::PutELocked))
        } else {
            dml_insert(sem, u, s, p, r, stored(sem, kind, v, literal))
        },
        Op::GetE { r } => { let s1 = select_txn(sem, s, p); (s1, gete_obs(sem, kind, s1.g[r as int])) },
        Op::MatchE { t, v } => {
            let s1 = select_txn(sem, s, p);
            (s1, count_obs(match_from(sem, u, s1.g, t, stored(sem, kind, v, false), 0)))
        },
        Op::InsertSelect { from, to } => insert_select(sem, u, s, p, from, to),
        Op::EmbRegister { r } => emb_register(sem, u, s, p, r, choice),
        Op::EmbRetract { r } => if blocked(sem, u, s, p, op) {
            (set_pending(s, p, Some(op)), Obs::Pending)
        } else {
            let o = emb_dml(sem, u, s, p, r, None);
            (o.0, retract_obs(o.1))
        },
        Op::EmbCount { t } => {
            let s1 = select_txn(sem, s, p);
            let g = if sem.emb_select_committed_only { cv_from(sem, s1, p, 0).g } else { s1.g };
            (s1, num_obs(rows_count(u, g, t)))
        },
        Op::EmbRoute { t } => {
            let s1 = select_txn(sem, s, p);
            let g = if sem.emb_select_committed_only { cv_from(sem, s1, p, 0).g } else { s1.g };
            (s1, if rows_count(u, g, t) > 0 { Obs::RouteRefused } else { Obs::Value(Some(Val::Num(0))) })
        },
        Op::EmbAssert { rn, rr, empty, vt } => emb_assert(sem, u, s, p, rn, rr, empty, vt),
        Op::Upsert { r, v } => if blocked(sem, u, s, p, op) {
            (set_pending(s, p, Some(op)), Obs::Pending)
        } else {
            upsert_run(sem, u, s, p, r, v, false)
        },
        Op::InsertMany { b, .. } => insert_many(sem, u, s, p, u.batches[b as int]),
        _ => (s, Obs::Err(ErrK::BadPending)),
    }
}

} // verus!
