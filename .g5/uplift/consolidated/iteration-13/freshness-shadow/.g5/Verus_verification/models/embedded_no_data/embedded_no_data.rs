// IVG embedded cursor: a no-row statement (SQLCODE 100) is an empty result with row count 0; every other error
// raises; the batch call. Verus model, consolidated uplift (2026-11-14). Product baseline 3eaa79cf.
// As-built transcription of iris_vector_graph/embedded.py:
//   _is_no_data :193-196, _no_data_ok :199-206, _is_ddtab_error :209-211, _exec_inline :265-277,
//   EmbeddedCursor.execute :312-385, EmbeddedCursor.executemany :387-413.
// It does not verify the product's bodies; bindings are in NOTES.md.
//
// Run:  $VERUS_BIN embedded_no_data.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;

verus! {

/// An exception as the cursor inspects it: SQLCODE 100 on the error itself, on its cause, and whether its text
/// names an unsupported path ("<UNIMPLEMENTED>" or "ddtab").
pub struct Err {
    pub code100: bool,
    pub cause100: bool,
    pub ddtab: bool,
}

/// What one execution path would do: return a result set, or raise.
pub enum R {
    Rs,
    Raise(Err),
}

pub enum Verb {
    Txn,
    Update,
    Delete,
    Insert,
    Select,
}

pub open spec fn is_dml(v: Verb) -> bool {
    v is Update || v is Delete || v is Insert
}

/// _is_no_data :196
pub open spec fn is_no_data(e: Err) -> bool {
    e.code100 || e.cause100
}

/// Outcome of the path chain before the outer handler.
pub enum Chain {
    Got { rs: bool },
    Fail(Err),
}

/// _exec_inline :272-277: folds an error whose own SQLCODE is 100 into "no result".
pub open spec fn exec_inline(r: R) -> Chain {
    match r {
        R::Rs => Chain::Got { rs: true },
        R::Raise(e) => if e.code100 { Chain::Got { rs: false } } else { Chain::Fail(e) },
    }
}

pub open spec fn lift(r: R) -> Chain {
    match r {
        R::Rs => Chain::Got { rs: true },
        R::Raise(e) => Chain::Fail(e),
    }
}

/// execute :326-359: the written-in or prepared path; on an unsupported-path error, iris.sql.exec with values
/// written in; then %SQL.Statement; three failures raise one RuntimeError whose cause is the third error.
pub open spec fn chain(inline: bool, first: R, second: R, third: R) -> Chain {
    let c1 = if inline { exec_inline(first) } else { lift(first) };
    match c1 {
        Chain::Got { rs } => Chain::Got { rs },
        Chain::Fail(e1) => if !e1.ddtab { Chain::Fail(e1) } else {
            match second {
                R::Rs => Chain::Got { rs: true },
                R::Raise(e2) => if !e2.ddtab { Chain::Fail(e2) } else {
                    match third {
                        R::Rs => Chain::Got { rs: true },
                        R::Raise(e3) => Chain::Fail(Err { code100: false, cause100: e3.code100, ddtab: false }),
                    }
                },
            }
        },
    }
}

/// The cursor after execute.
pub enum Res {
    Skipped,
    Done { rs: bool, rowcount: int },
    Raised,
}

/// execute :312-385 (description is not modeled).
pub open spec fn execute(verb: Verb, inline: bool, first: R, second: R, third: R) -> Res {
    if verb is Txn {
        Res::Skipped
    } else {
        match chain(inline, first, second, third) {
            Chain::Fail(e) => if is_no_data(e) { Res::Done { rs: false, rowcount: no_data_rowcount() } } else { Res::Raised },
            Chain::Got { rs } => {
                let no_data = !rs && is_dml(verb);
                Res::Done { rs, rowcount: if no_data { 0 } else { -1 } }
            },
        }
    }
}

/// :373 `self.rowcount = 0 if no_data else -1`
pub open spec fn no_data_rowcount() -> int {
    0
}

/// M17, first outcome: a DML statement that ends in SQLCODE 100, on any path and on the error or its cause, is an
/// empty result with row count 0.
pub proof fn theorem_no_data_is_empty(verb: Verb, inline: bool, first: R, second: R, third: R)
    requires
        is_dml(verb),
        match chain(inline, first, second, third) {
            Chain::Fail(e) => is_no_data(e),
            Chain::Got { rs } => !rs,
        },
    ensures execute(verb, inline, first, second, third) == (Res::Done { rs: false, rowcount: 0 }),
{
}

/// The no-row rule on each path: prepared, written in (folded inside _exec_inline), the second and the third path.
pub proof fn theorem_no_data_on_every_path(verb: Verb, e: Err, d: Err)
    requires is_dml(verb), e.code100, !e.ddtab, d.ddtab, !d.code100, !d.cause100,
    ensures
        execute(verb, false, R::Raise(e), R::Rs, R::Rs) == (Res::Done { rs: false, rowcount: 0 }),
        execute(verb, true, R::Raise(e), R::Rs, R::Rs) == (Res::Done { rs: false, rowcount: 0 }),
        execute(verb, false, R::Raise(d), R::Raise(e), R::Rs) == (Res::Done { rs: false, rowcount: 0 }),
        execute(verb, false, R::Raise(d), R::Raise(d), R::Raise(e)) == (Res::Done { rs: false, rowcount: 0 }),
{
}

/// M17, second outcome: an error that is not SQLCODE 100 (on itself or its cause) raises, whatever path it ends on.
pub proof fn theorem_other_error_raises(verb: Verb, inline: bool, first: R, second: R, third: R)
    requires
        !(verb is Txn),
        chain(inline, first, second, third) is Fail,
        !is_no_data(chain(inline, first, second, third)->Fail_0),
    ensures execute(verb, inline, first, second, third) == Res::Raised,
{
}

/// A statement that succeeded has row count -1 ("not known"), never the number of rows it changed.
pub proof fn theorem_success_rowcount_unknown(verb: Verb, inline: bool, second: R, third: R)
    requires !(verb is Txn),
    ensures execute(verb, inline, R::Rs, second, third) == (Res::Done { rs: true, rowcount: -1 }),
{
}

/// As built, a non-DML statement whose written-in path meets SQLCODE 100 reports row count -1, while the same error on
/// the prepared path reports 0 (both are empty results). Recorded, not a requirement.
pub proof fn witness_inline_select_no_data_rowcount()
{
    let e = Err { code100: true, cause100: false, ddtab: false };
    assert(execute(Verb::Select, true, R::Raise(e), R::Rs, R::Rs) == (Res::Done { rs: false, rowcount: -1 }));
    assert(execute(Verb::Select, false, R::Raise(e), R::Rs, R::Rs) == (Res::Done { rs: false, rowcount: 0 }));
}

/// Transaction words run nothing.
pub proof fn theorem_txn_skipped(inline: bool, first: R, second: R, third: R)
    ensures execute(Verb::Txn, inline, first, second, third) == Res::Skipped,
{
}

// ============================================================================ the batch call

/// One row of a batch: whether it holds an empty text (written-in path), what its first-pass execution does, and what
/// the fallback's iris.sql.exec and %SQL.Statement do.
pub struct Row {
    pub inline: bool,
    pub first: R,
    pub fexec: R,
    pub fstmt: R,
}

/// Batch state: rows run so far (by index, in order; a run that ended in SQLCODE 100 counts), and how it ended.
pub struct B {
    pub log: Seq<nat>,
    pub count: nat,
    pub raised: bool,
    pub fell_back: bool,
}

/// _no_data_ok(_exec_inline | stmt.execute): ok, folded, or an error.
pub open spec fn first_pass_row(r: Row) -> Chain {
    let c = if r.inline { exec_inline(r.first) } else { lift(r.first) };
    match c {
        Chain::Fail(e) => if is_no_data(e) { Chain::Got { rs: false } } else { Chain::Fail(e) },
        g => g,
    }
}

/// The first pass over rows i..n (:390-398): stops at the first error; Fail(e) carries it to the handler.
pub open spec fn pass1(rows: Seq<Row>, i: nat, b: B) -> (B, Option<Err>)
    decreases rows.len() - i,
{
    if i >= rows.len() {
        (b, None)
    } else {
        match first_pass_row(rows[i as int]) {
            Chain::Got { .. } => pass1(rows, i + 1, B { log: b.log.push(i), count: b.count + 1, ..b }),
            Chain::Fail(e) => (b, Some(e)),
        }
    }
}

/// The fallback (:399-410): from row `start`, each row through iris.sql.exec, then %SQL.Statement on an
/// unsupported-path error; any other error raises.
pub open spec fn fallback(rows: Seq<Row>, i: nat, b: B) -> B
    decreases rows.len() - i,
{
    if i >= rows.len() {
        b
    } else {
        let r = rows[i as int];
        let ok = match r.fexec {
            R::Rs => true,
            R::Raise(e) => is_no_data(e) || (e.ddtab && match r.fstmt { R::Rs => true, R::Raise(e3) => is_no_data(e3) }),
        };
        if ok { fallback(rows, i + 1, B { log: b.log.push(i), count: b.count + 1, ..b }) } else { B { raised: true, ..b } }
    }
}

/// The row the fallback starts from, as built: the first row (:402 `count = 0`, `for params in seq`).
pub open spec fn fallback_start(failed_at: nat) -> nat {
    0
}

pub open spec fn executemany(rows: Seq<Row>) -> B {
    let b0 = B { log: Seq::empty(), count: 0, raised: false, fell_back: false };
    let (b1, err) = pass1(rows, 0, b0);
    match err {
        None => b1,
        Some(e) => if !e.ddtab { B { raised: true, ..b1 } } else {
            let k = b1.log.len();
            fallback(rows, fallback_start(k), B { count: if fallback_start(k) == 0 { 0 } else { b1.count }, fell_back: true, ..b1 })
        },
    }
}

proof fn lemma_pass1_ok(rows: Seq<Row>, i: nat, b: B)
    requires
        i <= rows.len(),
        !b.raised,
        forall|j: int| i <= j < rows.len() ==> !(first_pass_row(#[trigger] rows[j]) is Fail),
    ensures
        pass1(rows, i, b).1 is None,
        pass1(rows, i, b).0.count == b.count + (rows.len() - i),
        pass1(rows, i, b).0.log == b.log + Seq::new((rows.len() - i) as nat, |j: int| (i + j) as nat),
        !pass1(rows, i, b).0.raised,
    decreases rows.len() - i,
{
    if i < rows.len() {
        let b1 = B { log: b.log.push(i), count: b.count + 1, ..b };
        assert(!(first_pass_row(rows[i as int]) is Fail));
        lemma_pass1_ok(rows, i + 1, b1);
        let s1 = Seq::new((rows.len() - (i + 1)) as nat, |j: int| (i + 1 + j) as nat);
        let s0 = Seq::new((rows.len() - i) as nat, |j: int| (i + j) as nat);
        assert forall|k: int| 0 <= k < (b1.log + s1).len() implies #[trigger] (b1.log + s1)[k] == (b.log + s0)[k] by {
            if k < b.log.len() {
            } else if k == b.log.len() {
            } else {
                assert((b1.log + s1)[k] == s1[k - b.log.len() - 1]);
                assert((b.log + s0)[k] == s0[k - b.log.len()]);
            }
        }
        assert(b1.log + s1 =~= b.log + s0);
    } else {
        assert(b.log + Seq::new(0nat, |j: int| (i + j) as nat) =~= b.log);
    }
}

/// With no first-pass error, each row runs once, in order, and the row count is the number of rows (no-row
/// statements included).
pub proof fn theorem_batch_counts_rows(rows: Seq<Row>)
    requires forall|j: int| 0 <= j < rows.len() ==> !(first_pass_row(#[trigger] rows[j]) is Fail),
    ensures
        executemany(rows).count == rows.len(),
        executemany(rows).log == Seq::new(rows.len(), |j: int| j as nat),
        !executemany(rows).raised,
{
    let b0 = B { log: Seq::empty(), count: 0, raised: false, fell_back: false };
    lemma_pass1_ok(rows, 0, b0);
    assert(Seq::<nat>::empty() + Seq::new(rows.len(), |j: int| (0 + j) as nat) =~= Seq::new(rows.len(), |j: int| j as nat));
}

/// A first-pass error that is neither SQLCODE 100 nor an unsupported path stops the batch and raises.
pub proof fn theorem_batch_other_error_raises(rows: Seq<Row>)
    requires
        rows.len() >= 1,
        first_pass_row(rows[0]) is Fail,
        !(first_pass_row(rows[0])->Fail_0).ddtab,
    ensures executemany(rows).raised, executemany(rows).log.len() == 0,
{
}

/// Suspected as built (bug-adp-001): when the first pass meets an unsupported-path error at row 1 after row 0 ran,
/// the fallback runs row 0 again.
pub proof fn witness_ddtab_mid_batch_reruns_rows()
{
    let ok = Row { inline: false, first: R::Rs, fexec: R::Rs, fstmt: R::Rs };
    let dd = Row { inline: true, first: R::Raise(Err { code100: false, cause100: false, ddtab: true }), fexec: R::Rs, fstmt: R::Rs };
    let rows = seq![ok, dd];
    let b0 = B { log: Seq::empty(), count: 0, raised: false, fell_back: false };
    assert(first_pass_row(ok) == (Chain::Got { rs: true }));
    assert(pass1(rows, 1, B { log: b0.log.push(0), count: 1, ..b0 }).1 is Some);
    assert(pass1(rows, 0, b0).0.log == seq![0nat]);
    let b2 = executemany(rows);
    reveal_with_fuel(fallback, 3);
    assert(b2.log =~= seq![0nat, 0nat, 1nat]);
    assert(b2.count == 2);
}

/// A no-row row in a batch is counted and the batch goes on.
pub proof fn witness_batch_no_data_row_counts()
{
    let nd = Row { inline: false, first: R::Raise(Err { code100: true, cause100: false, ddtab: false }), fexec: R::Rs, fstmt: R::Rs };
    let ok = Row { inline: false, first: R::Rs, fexec: R::Rs, fstmt: R::Rs };
    let rows = seq![nd, ok];
    assert(first_pass_row(nd) is Got);
    assert(first_pass_row(ok) is Got);
    theorem_batch_counts_rows(rows);
    assert(executemany(rows).count == 2);
}

} // verus!
