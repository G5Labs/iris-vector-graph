//! The executable model: exec functions computing one permitted outcome per choice, each verified to equal the
//! specification (`spec.rs`) through the views below. `e_run` drives a case with a choice sequence; the harness
//! (`harness/`) enumerates the choice sequences and so computes the permitted outcome set of every recorded case.
use vstd::prelude::*;
use crate::spec::*;
use crate::wf::*;
use crate::ext::*;
use crate::ext_exec::*;

verus! {

// ------------------------------------------------------------------------------------------------ exec types, views

pub struct EZArg {
    pub s: Vec<u32>,
    pub mask: Vec<u32>,
    pub rem: Vec<u32>,
}

pub struct Univ {
    pub paths: Vec<Vec<u64>>,
    pub is_row: Vec<bool>,
    pub table: Vec<usize>,
    pub texists: Vec<bool>,
    pub parse: Vec<i64>,
    pub names: Vec<Vec<u32>>,
    pub zargs: Vec<EZArg>,
    pub long: Vec<bool>,
    pub key: Vec<usize>,
    pub batches: Vec<Vec<(usize, Val)>>,
}

pub open spec fn paths_view(v: Seq<Vec<u64>>) -> Seq<Seq<u64>> {
    Seq::new(v.len(), |i: int| v[i]@)
}

pub open spec fn names_view(v: Seq<Vec<u32>>) -> Seq<Seq<u32>> {
    Seq::new(v.len(), |i: int| v[i]@)
}

pub open spec fn batches_view(v: Seq<Vec<(usize, Val)>>) -> Seq<Seq<(usize, Val)>> {
    Seq::new(v.len(), |i: int| v[i]@)
}

pub open spec fn zargs_view(v: Seq<EZArg>) -> Seq<ZArg> {
    Seq::new(v.len(), |i: int| ZArg { s: v[i].s@, mask: v[i].mask@, rem: v[i].rem@ })
}

impl View for Univ {
    type V = U;
    open spec fn view(&self) -> U {
        U { paths: paths_view(self.paths@), is_row: self.is_row@, table: self.table@, texists: self.texists@, parse: self.parse@,
            names: names_view(self.names@), zargs: zargs_view(self.zargs@), long: self.long@, key: self.key@,
            batches: batches_view(self.batches@) }
    }
}

pub struct EProc {
    pub alive: bool,
    pub sqlflag: bool,
    pub autocommit: bool,
    pub kind: Kind,
    pub marks: Vec<usize>,
    pub undo: Vec<Undo>,
    pub locks: Vec<Hold>,
    pub rlocks: Vec<bool>,
    pub ppg: Vec<Option<Val>>,
    pub pending: Option<Op>,
}

pub open spec fn marks_view(v: Seq<usize>) -> Seq<nat> {
    Seq::new(v.len(), |i: int| v[i] as nat)
}

impl View for EProc {
    type V = Proc;
    open spec fn view(&self) -> Proc {
        Proc {
            alive: self.alive,
            sqlflag: self.sqlflag,
            autocommit: self.autocommit,
            kind: self.kind,
            marks: marks_view(self.marks@),
            undo: self.undo@,
            locks: self.locks@,
            rlocks: self.rlocks@,
            ppg: self.ppg@,
            pending: self.pending,
        }
    }
}

pub struct EState {
    pub g: Vec<Option<Val>>,
    pub procs: Vec<EProc>,
}

pub open spec fn procs_view(v: Seq<EProc>) -> Seq<Proc> {
    Seq::new(v.len(), |i: int| v[i]@)
}

impl View for EState {
    type V = State;
    open spec fn view(&self) -> State {
        State { g: self.g@, procs: procs_view(self.procs@) }
    }
}

pub enum EObs {
    Ok,
    Level(usize),
    Value(Option<Val>),
    Data(u8),
    Test(bool),
    Rows(Vec<(usize, Val)>),
    Count(i64),
    SqlError(i64),
    Err(ErrK),
    Blocked,
    Pending,
    Refused(RefK),
    Subs(Vec<u64>),
    Codes(Vec<u32>),
    Ranges(Vec<(u32, u32)>),
    Cell(Option<Val>, bool),
    ErrText(i64),
    RouteRefused,
    FnVal(u8),
}

impl View for EObs {
    type V = Obs;
    open spec fn view(&self) -> Obs {
        match self {
            EObs::Ok => Obs::Ok,
            EObs::Level(n) => Obs::Level(*n as nat),
            EObs::Value(v) => Obs::Value(*v),
            EObs::Data(d) => Obs::Data(*d),
            EObs::Test(b) => Obs::Test(*b),
            EObs::Rows(r) => Obs::Rows(r@),
            EObs::Count(n) => Obs::Count(*n),
            EObs::SqlError(n) => Obs::SqlError(*n),
            EObs::Err(e) => Obs::Err(*e),
            EObs::Blocked => Obs::Blocked,
            EObs::Pending => Obs::Pending,
            EObs::Refused(r) => Obs::Refused(*r),
            EObs::Subs(v) => Obs::Subs(v@),
            EObs::Codes(v) => Obs::Codes(v@),
            EObs::Ranges(v) => Obs::Ranges(v@),
            EObs::Cell(v, b) => Obs::Cell(*v, *b),
            EObs::ErrText(c) => Obs::ErrText(*c),
            EObs::RouteRefused => Obs::RouteRefused,
            EObs::FnVal(f) => Obs::FnVal(*f),
        }
    }
}

pub struct ECase {
    pub nprocs: usize,
    pub kinds: Vec<Kind>,
    pub steps: Vec<(usize, Op)>,
    pub observe: Vec<usize>,
    pub observe_tables: Vec<usize>,
}

impl View for ECase {
    type V = Case;
    open spec fn view(&self) -> Case {
        Case { nprocs: self.nprocs as nat, kinds: self.kinds@, steps: self.steps@, observe: self.observe@, observe_tables: self.observe_tables@ }
    }
}

pub open spec fn obs_view(v: Seq<EObs>) -> Seq<Obs> {
    Seq::new(v.len(), |i: int| v[i]@)
}

pub enum ERunRes {
    NeedMore,
    Done(Vec<EObs>, Vec<EObs>, usize),
    /// The case or universe is not well formed (the harness never builds one).
    Invalid,
}

// ------------------------------------------------------------------------------------------------ view lemmas

pub proof fn lemma_procs_view_update(v: Seq<EProc>, p: int, x: EProc)
    requires 0 <= p < v.len(),
    ensures procs_view(v.update(p, x)) == procs_view(v).update(p, x@),
{
    assert(procs_view(v.update(p, x)) =~= procs_view(v).update(p, x@));
}

pub proof fn lemma_obs_view_push(v: Seq<EObs>, x: EObs)
    ensures obs_view(v.push(x)) == obs_view(v).push(x@),
{
    assert(obs_view(v.push(x)) =~= obs_view(v).push(x@));
}

pub proof fn lemma_marks_view_push(v: Seq<usize>, x: usize)
    ensures marks_view(v.push(x)) == marks_view(v).push(x as nat),
{
    assert(marks_view(v.push(x)) =~= marks_view(v).push(x as nat));
}

pub proof fn lemma_marks_view_drop_last(v: Seq<usize>)
    requires v.len() > 0,
    ensures marks_view(v.drop_last()) == marks_view(v).drop_last(), marks_view(v).last() == v.last() as nat,
{
    assert(marks_view(v.drop_last()) =~= marks_view(v).drop_last());
}

// ------------------------------------------------------------------------------------------------ small helpers

pub fn eq_oval(a: Option<Val>, b: Option<Val>) -> (r: bool)
    ensures r == (a == b),
{
    match (a, b) {
        (None, None) => true,
        (Some(Val::Num(x)), Some(Val::Num(y))) => x == y,
        (Some(Val::Str(x)), Some(Val::Str(y))) => x == y,
        (Some(Val::Null), Some(Val::Null)) => true,
        (Some(Val::Empty), Some(Val::Empty)) => true,
        (Some(Val::Nul), Some(Val::Nul)) => true,
        _ => false,
    }
}

pub fn clone_proc(pr: &EProc) -> (r: EProc)
    ensures r@ == pr@, r.marks@ == pr.marks@,
{
    EProc {
        alive: pr.alive,
        sqlflag: pr.sqlflag,
        autocommit: pr.autocommit,
        kind: pr.kind,
        marks: pr.marks.clone(),
        undo: pr.undo.clone(),
        locks: pr.locks.clone(),
        rlocks: pr.rlocks.clone(),
        ppg: pr.ppg.clone(),
        pending: pr.pending,
    }
}

pub fn clone_state(s: &EState) -> (r: EState)
    ensures r@ == s@, r.procs.len() == s.procs.len(), r.g.len() == s.g.len(),
{
    let mut procs: Vec<EProc> = Vec::new();
    let mut i: usize = 0;
    while i < s.procs.len()
        invariant
            i <= s.procs.len(),
            procs.len() == i,
            forall|j: int| 0 <= j < i ==> (#[trigger] procs@[j])@ == s.procs@[j]@,
        decreases s.procs.len() - i,
    {
        procs.push(clone_proc(&s.procs[i]));
        i += 1;
    }
    let r = EState { g: s.g.clone(), procs };
    assert(procs_view(r.procs@) =~= procs_view(s.procs@));
    r
}

/// Replace process p (the state's view updates p's view).
pub fn put_proc(s: &mut EState, p: usize, pr: EProc)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == upd(old(s)@, p, pr@), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    proof { lemma_procs_view_update(s.procs@, p as int, pr); }
    s.procs.set(p, pr);
}

pub fn e_set_sqlflag(s: &mut EState, p: usize, b: bool)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == set_sqlflag(old(s)@, p, b), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let mut pr = clone_proc(&s.procs[p]);
    pr.sqlflag = b;
    put_proc(s, p, pr);
}

pub fn e_set_pending(s: &mut EState, p: usize, op: Option<Op>)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == set_pending(old(s)@, p, op), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let mut pr = clone_proc(&s.procs[p]);
    pr.pending = op;
    put_proc(s, p, pr);
}

pub fn e_set_hold(s: &mut EState, p: usize, c: usize, h: Hold)
    requires (p as int) < old(s).procs.len(), (c as int) < old(s).procs@[p as int].locks.len(),
    ensures final(s)@ == set_hold(old(s)@, p, c, h), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let mut pr = clone_proc(&s.procs[p]);
    pr.locks.set(c, h);
    put_proc(s, p, pr);
}

pub fn e_set_rlock(s: &mut EState, p: usize, r: usize, b: bool)
    requires (p as int) < old(s).procs.len(), (r as int) < old(s).procs@[p as int].rlocks.len(),
    ensures final(s)@ == set_rlock(old(s)@, p, r, b), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let mut pr = clone_proc(&s.procs[p]);
    pr.rlocks.set(r, b);
    put_proc(s, p, pr);
}

// ------------------------------------------------------------------------------------------------ universe

#[verifier::loop_isolation(false)]
pub fn e_covers(u: &Univ, a: usize, b: usize) -> (r: bool)
    requires wf_univ(u@), u.paths.len() == u.is_row.len(),
    ensures r == covers(u@, a as int, b as int),
{
    if a >= u.paths.len() || b >= u.paths.len() || u.is_row[a] || u.is_row[b] {
        return false;
    }
    let pa = &u.paths[a];
    let pb = &u.paths[b];
    assert(u@.paths[a as int] == pa@);
    assert(u@.paths[b as int] == pb@);
    if pa.len() > pb.len() {
        return false;
    }
    let mut k: usize = 0;
    while k < pa.len()
        invariant
            k <= pa.len(),
            pa.len() <= pb.len(),
            forall|i: int| 0 <= i < k ==> pa@[i] == pb@[i],
        decreases pa.len() - k,
    {
        if pa[k] != pb[k] {
            assert(pb@.subrange(0, pa@.len() as int)[k as int] != pa@[k as int]);
            return false;
        }
        k += 1;
    }
    assert(pb@.subrange(0, pa@.len() as int) =~= pa@);
    true
}

pub fn e_related(sem: &Sem, u: &Univ, a: usize, b: usize) -> (r: bool)
    requires wf_univ(u@), u.paths.len() == u.is_row.len(),
    ensures r == related(*sem, u@, a as int, b as int),
{
    if sem.hierarchical { e_covers(u, a, b) || e_covers(u, b, a) } else { a == b }
}

pub fn e_any(h: Hold) -> (r: bool)
    ensures r == any(h),
{
    h.e > 0 || h.s > 0 || h.de > 0 || h.ds > 0
}

pub fn e_excl(h: Hold) -> (r: bool)
    ensures r == excl(h),
{
    h.e > 0 || h.de > 0
}

pub fn e_hold_conflicts(sem: &Sem, h: Hold, mode: Mode) -> (r: bool)
    ensures r == hold_conflicts(*sem, h, mode),
{
    match mode {
        Mode::E => e_any(h),
        Mode::S => e_excl(h) || (!sem.shared_compatible && e_any(h)),
    }
}

#[verifier::loop_isolation(false)]
pub fn e_conflicts(sem: &Sem, u: &Univ, s: &EState, p: usize, c: usize, mode: Mode) -> (r: bool)
    requires wf_univ(u@), wf(u@, s@),
    ensures r == conflicts(*sem, u@, s@, p, c, mode),
{
    let n = u.paths.len();
    let mut q: usize = 0;
    while q < s.procs.len()
        invariant
            q <= s.procs.len(),
            forall|qq: int, m: int| 0 <= qq < q && qq != p && s@.procs[qq].alive && 0 <= m < u@.n()
                && related(*sem, u@, m, c as int) ==> !hold_conflicts(*sem, #[trigger] s@.procs[qq].locks[m], mode),
        decreases s.procs.len() - q,
    {
        assert(s@.procs[q as int] == s.procs@[q as int]@);
        assert(wf_proc(u@, s@.procs[q as int]));
        if q != p && s.procs[q].alive {
            let mut m: usize = 0;
            while m < n
                invariant
                    m <= n,
                    n == u@.n(),
                    s.procs@[q as int].locks.len() == n,
                    forall|mm: int| 0 <= mm < m && related(*sem, u@, mm, c as int)
                        ==> !hold_conflicts(*sem, #[trigger] s@.procs[q as int].locks[mm], mode),
                decreases n - m,
            {
                if e_related(sem, u, m, c) && e_hold_conflicts(sem, s.procs[q].locks[m], mode) {
                    assert(hold_conflicts(*sem, s@.procs[q as int].locks[m as int], mode));
                    return true;
                }
                m += 1;
            }
        }
        q += 1;
    }
    false
}

#[verifier::loop_isolation(false)]
pub fn e_row_held(s: &EState, p: usize, r: usize) -> (b: bool)
    requires forall|q: int| 0 <= q < s.procs.len() ==> (r as int) < (#[trigger] s.procs@[q]).rlocks.len(),
    ensures b == row_held(s@, p, r),
{
    let mut q: usize = 0;
    while q < s.procs.len()
        invariant
            q <= s.procs.len(),
            forall|qq: int| 0 <= qq < q && qq != p && s@.procs[qq].alive ==> !(#[trigger] s@.procs[qq].rlocks[r as int]),
        decreases s.procs.len() - q,
    {
        assert(s@.procs[q as int] == s.procs@[q as int]@);
        if q != p && s.procs[q].alive && s.procs[q].rlocks[r] {
            assert(s@.procs[q as int].rlocks[r as int]);
            return true;
        }
        q += 1;
    }
    false
}

// ------------------------------------------------------------------------------------------------ globals and log

pub fn e_level(pr: &EProc) -> (r: usize)
    ensures r as nat == level(pr@),
{
    pr.marks.len()
}

pub fn e_write(s: &mut EState, p: usize, c: usize, v: Option<Val>, logged: bool)
    requires (p as int) < old(s).procs.len(), (c as int) < old(s).g.len(),
    ensures final(s)@ == write(old(s)@, p, c, v, logged), final(s).procs.len() == old(s).procs.len(),
        final(s).g.len() == old(s).g.len(),
{
    let old_v = s.g[c];
    let mut pr = clone_proc(&s.procs[p]);
    if logged && pr.marks.len() > 0 {
        pr.undo.push(Undo { c, old: old_v, written: v, ppg: false });
    }
    s.g.set(c, v);
    put_proc(s, p, pr);
}

#[verifier::loop_isolation(false)]
pub fn e_kill(sem: &Sem, u: &Univ, s: &mut EState, p: usize, node: usize)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(),
    ensures final(s)@ == kill_from(*sem, u@, old(s)@, p, node, 0), final(s).procs.len() == old(s).procs.len(),
        wf(u@, final(s)@),
{
    let n = u.paths.len();
    let mut j: usize = 0;
    while j < n
        invariant
            j <= n,
            n == u@.n(),
            wf(u@, s@),
            s.procs.len() == old(s).procs.len(),
            kill_from(*sem, u@, old(s)@, p, node, 0) == kill_from(*sem, u@, s@, p, node, j as nat),
        decreases n - j,
    {
        if e_covers(u, node, j) && s.g[j].is_some() {
            proof { lemma_write_wf(u@, s@, p, j, None, sem.kill_logged); }
            e_write(s, p, j, None, sem.kill_logged);
        }
        j += 1;
    }
}

pub fn e_restore1(sem: &Sem, g: &mut Vec<Option<Val>>, pp: &mut Vec<Option<Val>>, e: Undo)
    requires (e.c as int) < old(g).len(), (e.c as int) < old(pp).len(),
    ensures (final(g)@, final(pp)@) == restore1(*sem, old(g)@, old(pp)@, e), final(g).len() == old(g).len(),
        final(pp).len() == old(pp).len(),
{
    if e.ppg {
        if sem.ppg_rolled_back {
            pp.set(e.c, e.old);
        }
    } else if sem.rollback_physical || eq_oval(g[e.c], e.written) {
        g.set(e.c, e.old);
    }
}

/// Undo entries es[from..], last first.
#[verifier::loop_isolation(false)]
pub fn e_rb(sem: &Sem, g: &mut Vec<Option<Val>>, pp: &mut Vec<Option<Val>>, es: &Vec<Undo>, from: usize)
    requires
        from <= es.len(),
        old(g).len() == old(pp).len(),
        forall|i: int| 0 <= i < es.len() ==> (es@[i].c as int) < old(g).len(),
    ensures
        (final(g)@, final(pp)@) == rb(*sem, old(g)@, old(pp)@, es@.subrange(from as int, es.len() as int)),
        final(g).len() == old(g).len(), final(pp).len() == old(pp).len(),
{
    let mut k: usize = es.len();
    while k > from
        invariant
            from <= k <= es.len(),
            g.len() == old(g).len(),
            pp.len() == old(pp).len(),
            rb(*sem, old(g)@, old(pp)@, es@.subrange(from as int, es.len() as int))
                == rb(*sem, g@, pp@, es@.subrange(from as int, k as int)),
        decreases k - from,
    {
        let e = es[k - 1];
        proof {
            let sub = es@.subrange(from as int, k as int);
            assert(sub.last() == e);
            assert(sub.drop_last() =~= es@.subrange(from as int, k - 1));
        }
        e_restore1(sem, g, pp, e);
        k -= 1;
    }
    assert(es@.subrange(from as int, k as int).len() == 0);
}

pub fn e_tstart(s: &mut EState, p: usize)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == tstart(old(s)@, p), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let mut pr = clone_proc(&s.procs[p]);
    let l = pr.undo.len();
    proof { lemma_marks_view_push(pr.marks@, l); }
    pr.marks.push(l);
    put_proc(s, p, pr);
}

#[verifier::loop_isolation(false)]
pub fn e_txn_end(s: &mut EState, p: usize)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == txn_end(old(s)@, p), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let old_pr = clone_proc(&s.procs[p]);
    let mut locks: Vec<Hold> = Vec::new();
    let mut i: usize = 0;
    while i < old_pr.locks.len()
        invariant
            i <= old_pr.locks.len(),
            locks.len() == i,
            forall|j: int| 0 <= j < i ==> #[trigger] locks@[j] == (Hold { de: 0, ds: 0, ..old_pr.locks@[j] }),
        decreases old_pr.locks.len() - i,
    {
        let h = old_pr.locks[i];
        locks.push(Hold { de: 0, ds: 0, ..h });
        i += 1;
    }
    let mut rlocks: Vec<bool> = Vec::new();
    let mut i: usize = 0;
    while i < old_pr.rlocks.len()
        invariant
            i <= old_pr.rlocks.len(),
            rlocks.len() == i,
            forall|j: int| 0 <= j < i ==> !(#[trigger] rlocks@[j]),
        decreases old_pr.rlocks.len() - i,
    {
        rlocks.push(false);
        i += 1;
    }
    let pr = EProc {
        alive: old_pr.alive,
        sqlflag: false,
        autocommit: old_pr.autocommit,
        kind: old_pr.kind,
        marks: Vec::new(),
        undo: Vec::new(),
        locks,
        rlocks,
        ppg: old_pr.ppg,
        pending: old_pr.pending,
    };
    let ghost opr = old(s)@.procs[p as int];
    assert(pr@.locks =~= Seq::new(opr.locks.len(), |i: int| Hold { de: 0, ds: 0, ..opr.locks[i] }));
    assert(pr@.rlocks =~= Seq::new(opr.rlocks.len(), |i: int| false));
    assert(pr@.marks =~= Seq::<nat>::empty());
    assert(pr@.undo =~= Seq::<Undo>::empty());
    put_proc(s, p, pr);
}

pub fn e_undo_top(sem: &Sem, s: &mut EState, p: usize)
    requires (p as int) < old(s).procs.len(), old(s).procs@[p as int].marks.len() > 0,
        old(s).g.len() == old(s).procs@[p as int].ppg.len(),
        forall|i: int| 0 <= i < old(s).procs@[p as int].undo.len() ==> (old(s).procs@[p as int].undo@[i].c as int) < old(s).g.len(),
    ensures final(s)@ == undo_top(*sem, old(s)@, p), final(s).procs.len() == old(s).procs.len(), final(s).g.len() == old(s).g.len(),
{
    let pr0 = clone_proc(&s.procs[p]);
    let ghost opr = old(s)@.procs[p as int];
    proof { lemma_marks_view_drop_last(pr0.marks@); }
    let last = pr0.marks[pr0.marks.len() - 1];
    let m = if last <= pr0.undo.len() { last } else { pr0.undo.len() };
    assert(m as nat == top_mark(opr));
    let mut g = s.g.clone();
    let mut pp = pr0.ppg.clone();
    e_rb(sem, &mut g, &mut pp, &pr0.undo, m);
    let mut undo: Vec<Undo> = Vec::new();
    let mut i: usize = 0;
    while i < m
        invariant
            m <= pr0.undo.len(),
            i <= m,
            undo.len() == i,
            forall|j: int| 0 <= j < i ==> #[trigger] undo@[j] == pr0.undo@[j],
        decreases m - i,
    {
        undo.push(pr0.undo[i]);
        i += 1;
    }
    assert(undo@ =~= pr0.undo@.subrange(0, m as int));
    let mut marks = pr0.marks.clone();
    marks.pop();
    assert(marks@ =~= pr0.marks@.drop_last());
    let pr2 = EProc {
        alive: pr0.alive,
        sqlflag: pr0.sqlflag,
        autocommit: pr0.autocommit,
        kind: pr0.kind,
        marks,
        undo,
        locks: pr0.locks,
        rlocks: pr0.rlocks,
        ppg: pp,
        pending: pr0.pending,
    };
    let empty = pr2.marks.len() == 0;
    s.g = g;
    proof { lemma_procs_view_update(s.procs@, p as int, pr2); }
    s.procs.set(p, pr2);
    if empty {
        e_txn_end(s, p);
    }
}

pub fn e_commit_top(s: &mut EState, p: usize)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == commit_top(old(s)@, p), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let mut pr = clone_proc(&s.procs[p]);
    let len = pr.marks.len();
    if len == 0 {
        return;
    }
    proof { lemma_marks_view_drop_last(pr.marks@); }
    pr.marks.pop();
    put_proc(s, p, pr);
    if len == 1 {
        e_txn_end(s, p);
    }
}

#[verifier::loop_isolation(false)]
pub fn e_rollback_n(sem: &Sem, u: &Univ, s: &mut EState, p: usize, n: usize)
    requires wf(u@, old(s)@), (p as int) < old(s).procs.len(),
    ensures final(s)@ == rollback_n(*sem, old(s)@, p, n as nat), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    let mut i: usize = 0;
    while i < n && s.procs[p].marks.len() > 0
        invariant
            i <= n,
            wf(u@, s@),
            s.procs.len() == old(s).procs.len(),
            rollback_n(*sem, old(s)@, p, n as nat) == rollback_n(*sem, s@, p, (n - i) as nat),
        decreases n - i,
    {
        assert(s@.procs[p as int] == s.procs@[p as int]@);
        assert(wf_proc(u@, s@.procs[p as int]));
        proof { lemma_undo_top_wf(*sem, u@, s@, p); }
        e_undo_top(sem, s, p);
        i += 1;
    }
    assert(s@.procs[p as int] == s.procs@[p as int]@);
}

#[verifier::loop_isolation(false)]
pub fn e_commit_n(u: &Univ, s: &mut EState, p: usize, n: usize)
    requires wf(u@, old(s)@), (p as int) < old(s).procs.len(),
    ensures final(s)@ == commit_n(old(s)@, p, n as nat), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    let mut i: usize = 0;
    while i < n && s.procs[p].marks.len() > 0
        invariant
            i <= n,
            wf(u@, s@),
            s.procs.len() == old(s).procs.len(),
            commit_n(old(s)@, p, n as nat) == commit_n(s@, p, (n - i) as nat),
        decreases n - i,
    {
        assert(s@.procs[p as int] == s.procs@[p as int]@);
        proof { lemma_commit_top_wf(u@, s@, p); }
        e_commit_top(s, p);
        i += 1;
    }
    assert(s@.procs[p as int] == s.procs@[p as int]@);
}

pub fn e_end_levels(u: &Univ, s: &mut EState, sem: &Sem, p: usize, ends: Ends, commit: bool)
    requires wf(u@, old(s)@), (p as int) < old(s).procs.len(),
    ensures final(s)@ == end_levels(old(s)@, *sem, p, ends, commit), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    let l = s.procs[p].marks.len();
    assert(l as nat == level(old(s)@.procs[p as int]));
    let n: usize = match ends { Ends::One => 1, Ends::All => l };
    if l != 0 {
        if commit { e_commit_n(u, s, p, n); } else { e_rollback_n(sem, u, s, p, n); }
    }
    proof { lemma_set_sqlflag_wf(u@, s@, p, false); }
    e_set_sqlflag(s, p, false);
}

// ------------------------------------------------------------------------------------------------ locks

pub fn e_acquire(sem: &Sem, s: &mut EState, p: usize, c: usize, mode: Mode) -> (ok: bool)
    requires (p as int) < old(s).procs.len(), (c as int) < old(s).procs@[p as int].locks.len(),
    ensures ok == acquire(*sem, old(s)@, p, c, mode) is Some,
        ok ==> final(s)@ == acquire(*sem, old(s)@, p, c, mode)->Some_0,
        !ok ==> final(s)@ == old(s)@,
        final(s).procs.len() == old(s).procs.len(),
{
    let h = s.procs[p].locks[c];
    match mode {
        Mode::E => {
            if !sem.incremental {
                e_set_hold(s, p, c, Hold { e: 1, ..h });
                true
            } else if h.e == u64::MAX {
                false
            } else {
                e_set_hold(s, p, c, Hold { e: h.e + 1, ..h });
                true
            }
        },
        Mode::S => {
            if !sem.incremental {
                e_set_hold(s, p, c, Hold { s: 1, ..h });
                true
            } else if h.s == u64::MAX {
                false
            } else {
                e_set_hold(s, p, c, Hold { s: h.s + 1, ..h });
                true
            }
        },
    }
}

pub fn e_release(sem: &Sem, s: &mut EState, p: usize, c: usize, mode: Mode, immediate: bool) -> (ok: bool)
    requires (p as int) < old(s).procs.len(), (c as int) < old(s).procs@[p as int].locks.len(),
    ensures ok == release(*sem, old(s)@, p, c, mode, immediate) is Some,
        ok ==> final(s)@ == release(*sem, old(s)@, p, c, mode, immediate)->Some_0,
        !ok ==> final(s)@ == old(s)@,
        final(s).procs.len() == old(s).procs.len(),
{
    let defer = sem.unlock_deferred && !immediate && s.procs[p].marks.len() > 0;
    let h = s.procs[p].locks[c];
    match mode {
        Mode::E => {
            if h.e == 0 {
                true
            } else if !defer {
                e_set_hold(s, p, c, Hold { e: h.e - 1, ..h });
                true
            } else if h.de == u64::MAX {
                false
            } else {
                e_set_hold(s, p, c, Hold { e: h.e - 1, de: h.de + 1, ..h });
                true
            }
        },
        Mode::S => {
            if h.s == 0 {
                true
            } else if !defer {
                e_set_hold(s, p, c, Hold { s: h.s - 1, ..h });
                true
            } else if h.ds == u64::MAX {
                false
            } else {
                e_set_hold(s, p, c, Hold { s: h.s - 1, ds: h.ds + 1, ..h });
                true
            }
        },
    }
}

#[verifier::loop_isolation(false)]
pub fn e_release_all(sem: &Sem, s: &mut EState, p: usize) -> (ok: bool)
    requires (p as int) < old(s).procs.len(),
    ensures ok == release_all(*sem, old(s)@, p) is Some,
        ok ==> final(s)@ == release_all(*sem, old(s)@, p)->Some_0,
        !ok ==> final(s)@ == old(s)@,
        final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    let pr = clone_proc(&s.procs[p]);
    let ghost opr = old(s)@.procs[p as int];
    let n = pr.locks.len();
    if sem.unlock_deferred && pr.marks.len() > 0 {
        let mut i: usize = 0;
        while i < n
            invariant
                i <= n,
                n == pr.locks.len(),
                forall|j: int| 0 <= j < i ==> !defer_overflows(#[trigger] pr.locks@[j]),
            decreases n - i,
        {
            let h = pr.locks[i];
            if h.e > u64::MAX - h.de || h.s > u64::MAX - h.ds {
                assert(defer_overflows(opr.locks[i as int]));
                return false;
            }
            i += 1;
        }
        let mut locks: Vec<Hold> = Vec::new();
        let mut i: usize = 0;
        while i < n
            invariant
                i <= n,
                n == pr.locks.len(),
                locks.len() == i,
                forall|j: int| 0 <= j < n ==> !defer_overflows(#[trigger] pr.locks@[j]),
                forall|j: int| 0 <= j < i ==> #[trigger] locks@[j] == defer_hold(pr.locks@[j]),
            decreases n - i,
        {
            let h = pr.locks[i];
            assert(!defer_overflows(pr.locks@[i as int]));
            locks.push(Hold { e: 0, s: 0, de: h.de + h.e, ds: h.ds + h.s });
            i += 1;
        }
        let mut pr2 = pr;
        pr2.locks = locks;
        assert(pr2@.locks =~= Seq::new(opr.locks.len(), |i: int| defer_hold(opr.locks[i])));
        assert(pr2@ == Proc { locks: Seq::new(opr.locks.len(), |i: int| defer_hold(opr.locks[i])), ..opr });
        put_proc(s, p, pr2);
        true
    } else {
        let mut locks: Vec<Hold> = Vec::new();
        let mut i: usize = 0;
        while i < n
            invariant
                i <= n,
                locks.len() == i,
                forall|j: int| 0 <= j < i ==> #[trigger] locks@[j] == zero_hold(),
            decreases n - i,
        {
            locks.push(Hold { e: 0, s: 0, de: 0, ds: 0 });
            i += 1;
        }
        let m = pr.rlocks.len();
        let mut rlocks: Vec<bool> = Vec::new();
        let mut i: usize = 0;
        while i < m
            invariant
                i <= m,
                rlocks.len() == i,
                forall|j: int| 0 <= j < i ==> !(#[trigger] rlocks@[j]),
            decreases m - i,
        {
            rlocks.push(false);
            i += 1;
        }
        let mut pr2 = pr;
        pr2.locks = locks;
        pr2.rlocks = rlocks;
        assert(pr2@.locks =~= Seq::new(opr.locks.len(), |i: int| zero_hold()));
        assert(pr2@.rlocks =~= Seq::new(opr.rlocks.len(), |i: int| false));
        put_proc(s, p, pr2);
        true
    }
}

// ------------------------------------------------------------------------------------------------ SQL rows

pub fn e_stmt_begin(s: &mut EState, p: usize) -> (implicit: bool)
    requires (p as int) < old(s).procs.len(),
    ensures (final(s)@, implicit) == stmt_begin(old(s)@, p), final(s).procs.len() == old(s).procs.len(),
        final(s).g@ == old(s).g@,
{
    let l = s.procs[p].marks.len();
    let ac = s.procs[p].autocommit;
    if l == 0 && !ac {
        e_tstart(s, p);
        e_set_sqlflag(s, p, true);
        false
    } else if l == 0 {
        e_tstart(s, p);
        true
    } else {
        false
    }
}

pub fn e_failed_stmt(sem: &Sem, s: &mut EState, p: usize)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == failed_stmt(*sem, old(s)@, p), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    if sem.failed_dml_opens_txn && s.procs[p].marks.len() == 0 && !s.procs[p].autocommit {
        e_tstart(s, p);
        e_set_sqlflag(s, p, true);
    }
}

pub fn e_dml(sem: &Sem, u: &Univ, s: &mut EState, p: usize, r: usize, nv: Option<Val>, insert: bool) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), (r as int) < u@.n(), u@.is_row[r as int],
    ensures
        insert && nv is Some ==> (final(s)@, o@) == dml_insert(*sem, u@, old(s)@, p, r, nv->Some_0),
        !insert ==> (final(s)@, o@) == dml_change(*sem, u@, old(s)@, p, r, nv),
        wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    let t = u.table[r];
    if !u.texists[t] {
        return EObs::SqlError(-30);
    }
    if insert && s.g[r].is_some() {
        proof { lemma_failed_stmt_wf(*sem, u@, s@, p); }
        e_failed_stmt(sem, s, p);
        return EObs::SqlError(-119);
    }
    if !insert && s.g[r].is_none() {
        if sem.empty_dml_opens_txn {
            proof { lemma_failed_stmt_wf(*sem, u@, s@, p); }
            e_failed_stmt(sem, s, p);
        }
        return EObs::Count(0);
    }
    proof { lemma_stmt_begin_wf(u@, s@, p); }
    let implicit = e_stmt_begin(s, p);
    proof { lemma_write_wf(u@, s@, p, r, nv, true); }
    e_write(s, p, r, nv, true);
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    if implicit {
        proof { lemma_commit_top_wf(u@, s@, p); }
        e_commit_top(s, p);
    } else if sem.row_lock_held {
        proof { lemma_set_rlock_wf(u@, s@, p, r, true); }
        e_set_rlock(s, p, r, true);
    }
    EObs::Count(1)
}

pub fn e_run_dml(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), wf_op(u@, op),
    ensures (final(s)@, o@) == run_dml(*sem, u@, old(s)@, p, op), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    match op {
        Op::Insert { r, v } => e_dml(sem, u, s, p, r, Some(v), true),
        Op::Update { r, v } => e_dml(sem, u, s, p, r, Some(v), false),
        Op::Delete { r } => e_dml(sem, u, s, p, r, None, false),
        _ => EObs::Err(ErrK::BadPending),
    }
}

pub fn e_freedom_cond(sem: &Sem, u: &Univ, s: &EState, p: usize, r: usize) -> (b: bool)
    requires wf(u@, s@), (r as int) < u@.n(),
    ensures b == freedom_cond(*sem, s@, p, r),
{
    proof {
        assert forall|q: int| 0 <= q < s.procs.len() implies (r as int) < (#[trigger] s.procs@[q]).rlocks.len() by {
            assert(s@.procs[q] == s.procs@[q]@);
            assert(wf_proc(u@, s@.procs[q]));
        }
    }
    sem.dml_waits && s.g[r].is_none() && e_row_held(s, p, r)
}

pub fn e_blocked(sem: &Sem, u: &Univ, s: &EState, p: usize, op: Op) -> (b: bool)
    requires wf_univ(u@), wf(u@, s@), wf_op(u@, op),
    ensures b == blocked(*sem, u@, s@, p, op),
{
    proof {
        assert forall|q: int| 0 <= q < s.procs.len() implies u@.n() == (#[trigger] s.procs@[q]).rlocks.len() by {
            assert(s@.procs[q] == s.procs@[q]@);
            assert(wf_proc(u@, s@.procs[q]));
        }
    }
    match op {
        Op::Lock { c, mode, .. } => e_conflicts(sem, u, s, p, c, mode),
        Op::LockOnly { c, .. } => e_conflicts(sem, u, s, p, c, Mode::E),
        Op::Update { r, .. } | Op::Delete { r } => sem.dml_waits && s.g[r].is_some() && e_row_held(s, p, r),
        Op::Insert { r, .. } => e_freedom_cond(sem, u, s, p, r) || (sem.insert_dup_waits && s.g[r].is_some() && e_row_held(s, p, r)),
        Op::EmbRegister { r } => !sem.emb_ignores_row_locks && e_freedom_cond(sem, u, s, p, r),
        Op::EmbRetract { r } => !sem.emb_ignores_row_locks && sem.dml_waits && s.g[r].is_some() && e_row_held(s, p, r),
        Op::Upsert { r, .. } => !sem.iou_ignores_row_locks && sem.dml_waits && s.g[r].is_some() && e_row_held(s, p, r),
        _ => false,
    }
}

#[verifier::loop_isolation(false)]
pub fn e_rows(u: &Univ, g: &Vec<Option<Val>>, t: usize) -> (rows: Vec<(usize, Val)>)
    requires wf_univ(u@), g.len() == u@.n(),
    ensures rows@ == rows_from(u@, g@, t, 0),
{
    let n = u.paths.len();
    let mut rows: Vec<(usize, Val)> = Vec::new();
    let mut j: usize = 0;
    while j < n
        invariant
            j <= n,
            n == u@.n(),
            rows@ + rows_from(u@, g@, t, j as nat) == rows_from(u@, g@, t, 0),
        decreases n - j,
    {
        if u.is_row[j] && u.table[j] == t {
            match g[j] {
                Some(v) => {
                    proof {
                        let rest = rows_from(u@, g@, t, (j + 1) as nat);
                        assert(rows@.push((j, v)) + rest =~= rows@ + (seq![(j, v)] + rest));
                    }
                    rows.push((j, v));
                },
                None => {},
            }
        }
        j += 1;
    }
    assert(rows@ + rows_from(u@, g@, t, n as nat) =~= rows@);
    rows
}

pub fn e_select_obs(u: &Univ, g: &Vec<Option<Val>>, t: usize) -> (o: EObs)
    requires wf_univ(u@), g.len() == u@.n(), (t as int) < u@.texists.len(),
    ensures o@ == select_obs(u@, g@, t),
{
    if u.texists[t] { EObs::Rows(e_rows(u, g, t)) } else { EObs::SqlError(-30) }
}

pub fn e_select_txn(sem: &Sem, s: &mut EState, p: usize)
    requires (p as int) < old(s).procs.len(),
    ensures final(s)@ == select_txn(*sem, old(s)@, p), final(s).procs.len() == old(s).procs.len(), final(s).g@ == old(s).g@,
{
    if sem.select_opens_txn && s.procs[p].marks.len() == 0 && !s.procs[p].autocommit {
        e_tstart(s, p);
        e_set_sqlflag(s, p, true);
    }
}

// ------------------------------------------------------------------------------------------------ reads

#[verifier::loop_isolation(false)]
pub fn e_data(u: &Univ, g: &Vec<Option<Val>>, c: usize) -> (d: u8)
    requires wf_univ(u@), g.len() == u@.n(), (c as int) < u@.n(),
    ensures d == data_of(u@, g@, c as int),
{
    let n = u.paths.len();
    let mut kids = false;
    let mut j: usize = 0;
    while j < n
        invariant
            j <= n,
            n == u@.n(),
            !kids ==> forall|jj: int| 0 <= jj < j && jj != c && covers(u@, c as int, jj) ==> !(#[trigger] g@[jj] is Some),
            kids ==> has_kids(u@, g@, c as int),
        decreases n - j,
    {
        if !kids && j != c && e_covers(u, c, j) && g[j].is_some() {
            kids = true;
        }
        j += 1;
    }
    let a: u8 = if g[c].is_some() { 1 } else { 0 };
    let b: u8 = if kids { 10 } else { 0 };
    a + b
}

pub fn e_num_of(u: &Univ, v: Option<Val>) -> (n: i64)
    ensures n == num_of(u@, v),
{
    match v {
        None => 0,
        Some(Val::Num(n)) => n,
        Some(Val::Str(id)) => if id < u.parse.len() { u.parse[id] } else { 0 },
        Some(_) => 0,
    }
}

pub proof fn lemma_cv_unfold(sem: Sem, s: State, p: usize, q: nat)
    requires q < s.procs.len(),
    ensures cv_from(sem, s, p, q) == cv_from(sem, State {
        g: (if q != p { rollback_all(Sem { rollback_physical: true, ..sem }, s, q as usize) } else { s }).g,
        procs: s.procs }, p, q + 1),
{
}

pub proof fn lemma_cv_end(sem: Sem, s: State, p: usize, q: nat)
    requires q >= s.procs.len(),
    ensures cv_from(sem, s, p, q) == s,
{
}

/// The globals after rolling back all of q's levels (on a scratch copy).
pub fn e_rollback_all_g(sem: &Sem, u: &Univ, s: &EState, q: usize) -> (g: Vec<Option<Val>>)
    requires wf_univ(u@), wf(u@, s@), (q as int) < s.procs.len(),
    ensures g@ == rollback_all(*sem, s@, q).g, g.len() == u@.n(),
{
    let mut scratch = clone_state(s);
    let l = scratch.procs[q].marks.len();
    assert(scratch@.procs[q as int] == scratch.procs@[q as int]@);
    e_rollback_n(sem, u, &mut scratch, q, l);
    scratch.g
}

/// The committed view's globals (no-dirty-reads mutants only).
#[verifier::loop_isolation(false)]
pub fn e_cv(sem: &Sem, u: &Univ, s: &EState, p: usize) -> (g: Vec<Option<Val>>)
    requires wf_univ(u@), wf(u@, s@),
    ensures g@ == cv_from(*sem, s@, p, 0).g, g.len() == u@.n(),
{
    let phys = Sem { rollback_physical: true, ..*sem };
    let mut cur = clone_state(s);
    let mut q: usize = 0;
    while q < s.procs.len()
        invariant
            q <= s.procs.len(),
            wf(u@, cur@),
            cur@.procs == s@.procs,
            cur.procs.len() == s.procs.len(),
            cv_from(*sem, s@, p, 0) == cv_from(*sem, cur@, p, q as nat),
        decreases s.procs.len() - q,
    {
        proof { lemma_cv_unfold(*sem, cur@, p, q as nat); }
        if q != p {
            let g2 = e_rollback_all_g(&phys, u, &cur, q);
            cur.g = g2;
        }
        assert(cur@.g.len() == u@.n());
        q += 1;
    }
    proof { lemma_cv_end(*sem, cur@, p, q as nat); }
    cur.g
}

// ------------------------------------------------------------------------------------------------ process stop

#[verifier::loop_isolation(false)]
pub fn e_stop(sem: &Sem, u: &Univ, s: &mut EState, t: usize)
    requires wf_univ(u@), wf(u@, old(s)@), (t as int) < old(s).procs.len(),
    ensures final(s)@ == stop(*sem, old(s)@, t), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    let l = s.procs[t].marks.len();
    assert(l as nat == level(old(s)@.procs[t as int]));
    if !sem.stop_rolls_back {
        e_commit_n(u, s, t, l);
    } else if sem.stop_all_levels {
        e_rollback_n(sem, u, s, t, l);
    } else {
        e_rollback_n(sem, u, s, t, 1);
    }
    let pr = clone_proc(&s.procs[t]);
    let ghost opr = s@.procs[t as int];
    let n1 = pr.locks.len();
    let mut locks: Vec<Hold> = Vec::new();
    let mut i: usize = 0;
    while i < n1
        invariant i <= n1, locks.len() == i, forall|j: int| 0 <= j < i ==> #[trigger] locks@[j] == zero_hold(),
        decreases n1 - i,
    {
        locks.push(Hold { e: 0, s: 0, de: 0, ds: 0 });
        i += 1;
    }
    let n2 = pr.rlocks.len();
    let mut rlocks: Vec<bool> = Vec::new();
    let mut i: usize = 0;
    while i < n2
        invariant i <= n2, rlocks.len() == i, forall|j: int| 0 <= j < i ==> !(#[trigger] rlocks@[j]),
        decreases n2 - i,
    {
        rlocks.push(false);
        i += 1;
    }
    let n3 = pr.ppg.len();
    let mut ppg: Vec<Option<Val>> = Vec::new();
    let mut i: usize = 0;
    while i < n3
        invariant i <= n3, ppg.len() == i, forall|j: int| 0 <= j < i ==> (#[trigger] ppg@[j]) is None,
        decreases n3 - i,
    {
        ppg.push(None);
        i += 1;
    }
    let pr2 = EProc {
        alive: false,
        sqlflag: pr.sqlflag,
        autocommit: pr.autocommit,
        kind: pr.kind,
        marks: pr.marks,
        undo: pr.undo,
        locks,
        rlocks,
        ppg,
        pending: None,
    };
    assert(pr2@.locks =~= Seq::new(opr.locks.len(), |i: int| zero_hold()));
    assert(pr2@.rlocks =~= Seq::new(opr.rlocks.len(), |i: int| false));
    assert(pr2@.ppg =~= Seq::new(opr.ppg.len(), |i: int| None::<Val>));
    proof {
        assert(wf_proc(u@, opr));
        lemma_upd_wf(u@, s@, t, pr2@);
    }
    put_proc(s, t, pr2);
}

// ------------------------------------------------------------------------------------------------ one operation

pub fn e_num_obs(n: usize) -> (o: EObs)
    ensures o@ == num_obs(n as nat),
{
    if (n as u128) <= (i64::MAX as u128) { EObs::Value(Some(Val::Num(n as i64))) } else { EObs::Err(ErrK::Overflow) }
}

pub fn e_lock_now(sem: &Sem, u: &Univ, s: &mut EState, p: usize, c: usize, mode: Mode) -> (o: EObs)
    requires wf(u@, old(s)@), (p as int) < old(s).procs.len(), (c as int) < u@.n(),
    ensures (final(s)@, o@) == lock_now(*sem, old(s)@, p, c, mode), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    proof { lemma_acquire_wf(*sem, u@, s@, p, c, mode); }
    if e_acquire(sem, s, p, c, mode) { EObs::Test(true) } else { EObs::Err(ErrK::Overflow) }
}

pub fn e_await(sem: &Sem, u: &Univ, s: &mut EState, p: usize) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(),
    ensures (final(s)@, o@) == await_step(*sem, u@, old(s)@, p), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    match s.procs[p].pending {
        None => EObs::Err(ErrK::NothingPending),
        Some(pend) => {
            let lockwait = match pend { Op::Lock { .. } | Op::LockOnly { .. } => true, _ => false };
            if e_blocked(sem, u, s, p, pend) || (lockwait && !sem.lock_wait_grants) {
                EObs::Blocked
            } else {
                proof { lemma_set_pending_wf(u@, s@, p, None); }
                e_set_pending(s, p, None);
                match pend {
                    Op::Lock { c, mode, .. } => e_lock_now(sem, u, s, p, c, mode),
                    Op::LockOnly { c, .. } => e_lock_now(sem, u, s, p, c, Mode::E),
                    Op::Insert { .. } | Op::Update { .. } | Op::Delete { .. } => e_run_dml(sem, u, s, p, pend),
                    Op::EmbRegister { r } => { let o = e_emb_dml(sem, u, s, p, r, Some(Val::Empty)); e_reg_obs(o) },
                    Op::EmbRetract { r } => { let o = e_emb_dml(sem, u, s, p, r, None); e_retract_obs(o) },
                    Op::Upsert { r, v } => e_upsert_run(sem, u, s, p, r, v, true),
                    _ => EObs::Err(ErrK::BadPending),
                }
            }
        },
    }
}

pub fn e_txn_basic(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(),
        op is TStart || op is TCommit || op is TRollbackOne || op is TRollback || op is SqlStart || op is TLevel,
    ensures (final(s)@, o@) == txn_step(*sem, old(s)@, p, op), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    proof { lemma_txn_step_wf(*sem, u@, s@, p, op); }
    let l = s.procs[p].marks.len();
    match op {
        Op::TStart => { e_tstart(s, p); EObs::Ok },
        Op::TCommit => if l == 0 { EObs::Err(ErrK::Command) } else { e_commit_top(s, p); EObs::Ok },
        Op::TRollbackOne => if l == 0 {
            EObs::Ok
        } else if sem.rollback_one_is_one_level {
            e_undo_top(sem, s, p);
            EObs::Ok
        } else {
            e_rollback_n(sem, u, s, p, l);
            EObs::Ok
        },
        Op::TRollback => { e_rollback_n(sem, u, s, p, l); EObs::Ok },
        Op::SqlStart => {
            let start = match sem.sql_start {
                SqlStartSem::UnlessSqlOwns => !s.procs[p].sqlflag,
                SqlStartSem::NothingIfOpen => l == 0,
                SqlStartSem::Always => true,
            };
            if start { e_tstart(s, p); e_set_sqlflag(s, p, true); }
            EObs::Ok
        },
        _ => EObs::Level(l),
    }
}

pub fn e_txn_ends(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(),
        op is SqlCommit || op is SqlRollback || op is DrvCommit || op is DrvRollback || op is SetAutocommit,
    ensures (final(s)@, o@) == txn_step(*sem, old(s)@, p, op), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    proof { lemma_txn_step_wf(*sem, u@, s@, p, op); }
    let l = s.procs[p].marks.len();
    match op {
        Op::SqlCommit => { e_end_levels(u, s, sem, p, sem.sql_commit, true); EObs::Ok },
        Op::SqlRollback => { e_end_levels(u, s, sem, p, sem.sql_rollback, false); EObs::Ok },
        Op::DrvCommit => { e_end_levels(u, s, sem, p, sem.drv_commit, true); EObs::Ok },
        Op::DrvRollback => { e_end_levels(u, s, sem, p, sem.drv_rollback, false); EObs::Ok },
        Op::SetAutocommit { on } => if l > 0 && !on && s.procs[p].autocommit {
            EObs::Refused(RefK::AutocommitOffInTxn)
        } else {
            if on && l > 0 && sem.autocommit_on_commits { e_end_levels(u, s, sem, p, sem.drv_commit, true); }
            let mut pr = clone_proc(&s.procs[p]);
            pr.autocommit = on;
            put_proc(s, p, pr);
            EObs::Ok
        },
        _ => EObs::Ok,
    }
}

pub fn e_txn_sqlproc(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(),
        op is SqlTxnBegin || op is SqlTxnEnd || op is SqlTxnUndo,
    ensures (final(s)@, o@) == txn_step(*sem, old(s)@, p, op), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    proof { lemma_txn_step_wf(*sem, u@, s@, p, op); }
    proof { lemma_select_txn_wf(*sem, u@, s@, p); }
    e_select_txn(sem, s, p);
    match op {
        Op::SqlTxnBegin { hold } => {
            let before = s.procs[p].marks.len();
            proof { lemma_tstart_wf(u@, s@, p); }
            if hold && before == 0 { e_tstart(s, p); }
            proof { lemma_tstart_wf(u@, s@, p); }
            e_tstart(s, p);
            let answer = s.procs[p].marks.len();
            assert(answer as nat == level(s@.procs[p as int]));
            if sem.sqlproc_levels_end_with_statement {
                e_commit_n(u, s, p, answer - before);
            }
            e_num_obs(answer)
        },
        Op::SqlTxnEnd { level: lv } => {
            let l1 = s.procs[p].marks.len();
            if lv >= 1 && (l1 as u128) >= (lv as u128) {
                e_commit_n(u, s, p, l1 - (lv as usize) + 1);
            }
            let l2 = s.procs[p].marks.len();
            assert(s@.procs[p as int] == s.procs@[p as int]@);
            e_num_obs(l2)
        },
        Op::SqlTxnUndo { level: lv } => {
            let l1 = s.procs[p].marks.len();
            if lv >= 1 && (l1 as u128) >= (lv as u128) {
                if sem.rollback_one_is_one_level {
                    e_rollback_n(sem, u, s, p, l1 - (lv as usize) + 1);
                } else {
                    e_rollback_n(sem, u, s, p, l1);
                }
            }
            let l2 = s.procs[p].marks.len();
            assert(s@.procs[p as int] == s.procs@[p as int]@);
            e_num_obs(l2)
        },
        _ => EObs::Ok,
    }
}

pub fn e_txn_step(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), is_txn_op(op),
    ensures (final(s)@, o@) == txn_step(*sem, old(s)@, p, op), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    match op {
        Op::TStart | Op::TCommit | Op::TRollbackOne | Op::TRollback | Op::SqlStart | Op::TLevel => e_txn_basic(sem, u, s, p, op),
        Op::SqlCommit | Op::SqlRollback | Op::DrvCommit | Op::DrvRollback | Op::SetAutocommit { .. } => e_txn_ends(sem, u, s, p, op),
        _ => e_txn_sqlproc(sem, u, s, p, op),
    }
}

pub fn e_glob_step(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), is_glob_op(op), wf_op(u@, op),
    ensures (final(s)@, o@) == glob_step(*sem, u@, old(s)@, p, op), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    proof { lemma_glob_step_wf(*sem, u@, s@, p, op); }
    match op {
        Op::Set { c, v } => { e_write(s, p, c, Some(v), true); EObs::Ok },
        Op::Kill { c } => { e_kill(sem, u, s, p, c); EObs::Ok },
        Op::Get { c } => {
            let v = if sem.dirty_reads { s.g[c] } else { let g = e_cv(sem, u, s, p); g[c] };
            EObs::Value(v)
        },
        Op::Data { c } => EObs::Data(e_data(u, &s.g, c)),
        Op::Incr { c } => {
            let cur = e_num_of(u, s.g[c]);
            if cur == i64::MAX {
                EObs::Err(ErrK::Overflow)
            } else {
                let nv = Val::Num(cur + 1);
                e_write(s, p, c, Some(nv), !sem.incr_survives);
                EObs::Value(Some(nv))
            }
        },
        Op::PpgSet { c, v } => {
            let mut pr = clone_proc(&s.procs[p]);
            let old = pr.ppg[c];
            if pr.marks.len() > 0 {
                pr.undo.push(Undo { c, old, written: Some(v), ppg: true });
            }
            pr.ppg.set(c, Some(v));
            put_proc(s, p, pr);
            EObs::Ok
        },
        Op::PpgGet { c } => EObs::Value(s.procs[p].ppg[c]),
        _ => EObs::Err(ErrK::BadPending),
    }
}

pub fn e_lock_step(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), is_lock_op(op), wf_op(u@, op),
    ensures (final(s)@, o@) == lock_step(*sem, u@, old(s)@, p, op), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    proof { lemma_lock_step_wf(*sem, u@, s@, p, op); }
    match op {
        Op::Lock { c, mode, wait } => if e_conflicts(sem, u, s, p, c, mode) {
            if wait { e_set_pending(s, p, Some(op)); EObs::Pending } else { EObs::Test(false) }
        } else {
            e_lock_now(sem, u, s, p, c, mode)
        },
        Op::Unlock { c, mode, immediate } => if e_release(sem, s, p, c, mode, immediate) { EObs::Ok } else { EObs::Err(ErrK::Overflow) },
        Op::LockOnly { c, wait } => {
            proof { lemma_release_all_wf(*sem, u@, s@, p); }
            if !e_release_all(sem, s, p) {
                EObs::Err(ErrK::Overflow)
            } else if e_conflicts(sem, u, s, p, c, Mode::E) {
                if wait {
                    proof { lemma_set_pending_wf(u@, s@, p, Some(op)); }
                    e_set_pending(s, p, Some(op));
                    EObs::Pending
                } else {
                    EObs::Test(false)
                }
            } else {
                e_lock_now(sem, u, s, p, c, Mode::E)
            }
        },
        Op::ReleaseAll => if e_release_all(sem, s, p) { EObs::Ok } else { EObs::Err(ErrK::Overflow) },
        _ => EObs::Err(ErrK::BadPending),
    }
}

pub fn e_row_step(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op, choice: bool) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), (p as int) < old(s).procs.len(), is_row_op(op), wf_op(u@, op),
    ensures (final(s)@, o@) == row_step(*sem, u@, old(s)@, p, op, choice), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    assert(wf_proc(u@, s@.procs[p as int]));
    proof { lemma_row_step_wf(*sem, u@, s@, p, op, choice); }
    match op {
        Op::Insert { r, .. } => if sem.maxlen_enforced && u.long[r] {
            proof { lemma_failed_stmt_wf(*sem, u@, s@, p); }
            e_failed_stmt(sem, s, p);
            EObs::SqlError(-104)
        } else if e_freedom_cond(sem, u, s, p, r) {
            let goes = match sem.freedom { FreedomSem::Both => choice, FreedomSem::WaitOnly => false, FreedomSem::GoOnly => true };
            if goes {
                let o = e_run_dml(sem, u, s, p, op);
                assert(s@.procs[p as int] == s.procs@[p as int]@);
                assert(wf_proc(u@, s@.procs[p as int]));
                e_set_rlock(s, p, r, false);
                o
            } else {
                e_set_pending(s, p, Some(op));
                EObs::Pending
            }
        } else if e_blocked(sem, u, s, p, op) {
            e_set_pending(s, p, Some(op));
            EObs::Pending
        } else {
            e_run_dml(sem, u, s, p, op)
        },
        Op::Update { .. } | Op::Delete { .. } => if e_blocked(sem, u, s, p, op) {
            e_set_pending(s, p, Some(op));
            EObs::Pending
        } else {
            e_run_dml(sem, u, s, p, op)
        },
        Op::Select { t } => {
            proof { lemma_select_txn_wf(*sem, u@, s@, p); }
            e_select_txn(sem, s, p);
            if sem.select_dirty {
                e_select_obs(u, &s.g, t)
            } else {
                let g = e_cv(sem, u, s, p);
                e_select_obs(u, &g, t)
            }
        },
        _ => EObs::Err(ErrK::BadPending),
    }
}

pub fn e_is_txn_op(op: Op) -> (b: bool)
    ensures b == is_txn_op(op),
{
    match op {
        Op::TStart | Op::TCommit | Op::TRollbackOne | Op::TRollback | Op::SqlStart | Op::SqlCommit | Op::SqlRollback
        | Op::DrvCommit | Op::DrvRollback | Op::SetAutocommit { .. } | Op::TLevel | Op::SqlTxnBegin { .. }
        | Op::SqlTxnEnd { .. } | Op::SqlTxnUndo { .. } => true,
        _ => false,
    }
}

pub fn e_is_glob_op(op: Op) -> (b: bool)
    ensures b == is_glob_op(op),
{
    match op {
        Op::Set { .. } | Op::Kill { .. } | Op::Get { .. } | Op::Data { .. } | Op::Incr { .. } | Op::PpgSet { .. } | Op::PpgGet { .. } => true,
        _ => false,
    }
}

pub fn e_is_lock_op(op: Op) -> (b: bool)
    ensures b == is_lock_op(op),
{
    match op {
        Op::Lock { .. } | Op::Unlock { .. } | Op::LockOnly { .. } | Op::ReleaseAll => true,
        _ => false,
    }
}

pub fn e_is_row_op(op: Op) -> (b: bool)
    ensures b == is_row_op(op),
{
    match op {
        Op::Insert { .. } | Op::Update { .. } | Op::Delete { .. } | Op::Select { .. } => true,
        _ => false,
    }
}

/// One permitted outcome, verified equal to the specification's `step`.
pub fn e_step(sem: &Sem, u: &Univ, s: &mut EState, p: usize, op: Op, choice: bool) -> (o: EObs)
    requires wf_univ(u@), wf(u@, old(s)@), wf_op(u@, op),
    ensures (final(s)@, o@) == step(*sem, u@, old(s)@, p, op, choice), wf(u@, final(s)@), final(s).procs.len() == old(s).procs.len(),
{
    if p >= s.procs.len() || !s.procs[p].alive {
        return EObs::Err(ErrK::Dead);
    }
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    let is_await = match op { Op::Await => true, _ => false };
    if s.procs[p].pending.is_some() && !is_await {
        return EObs::Err(ErrK::Busy);
    }
    if e_is_txn_op(op) {
        e_txn_step(sem, u, s, p, op)
    } else if e_is_glob_op(op) {
        e_glob_step(sem, u, s, p, op)
    } else if e_is_lock_op(op) {
        e_lock_step(sem, u, s, p, op)
    } else if e_is_row_op(op) {
        e_row_step(sem, u, s, p, op, choice)
    } else if e_is_ext_op(op) {
        e_ext_step(sem, u, s, p, op, choice)
    } else {
        match op {
            Op::Terminate { target } => {
                if target < s.procs.len() && s.procs[target].alive {
                    assert(s@.procs[target as int] == s.procs@[target as int]@);
                    e_stop(sem, u, s, target);
                }
                EObs::Ok
            },
            Op::Await => e_await(sem, u, s, p),
            _ => EObs::Err(ErrK::BadPending),
        }
    }
}

pub fn e_choice_point(sem: &Sem, u: &Univ, s: &EState, p: usize, op: Op) -> (b: bool)
    requires wf(u@, s@), wf_op(u@, op), wf_univ(u@),
    ensures b == choice_point(*sem, u@, s@, p, op),
{
    if p >= s.procs.len() || !s.procs[p].alive || s.procs[p].pending.is_some() {
        return false;
    }
    assert(s@.procs[p as int] == s.procs@[p as int]@);
    let is_both = match sem.freedom { FreedomSem::Both => true, _ => false };
    match op {
        Op::Insert { r, .. } => is_both && !(sem.maxlen_enforced && u.long[r]) && e_freedom_cond(sem, u, s, p, r),
        Op::EmbRegister { r } => is_both && !e_emb_visible(sem, u, s, p, r) && !(sem.maxlen_enforced && u.long[r])
            && !sem.emb_ignores_row_locks && e_freedom_cond(sem, u, s, p, r),
        _ => false,
    }
}

// ------------------------------------------------------------------------------------------------ a case

pub fn e_driver_refusal(kind: Kind, op: Op) -> (r: Option<RefK>)
    ensures r == driver_refusal(kind, op),
{
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

pub fn e_kind_of(case: &ECase, q: usize) -> (k: Kind)
    ensures k == kind_of(case@, q as int),
{
    if q < case.kinds.len() { case.kinds[q] } else { Kind::Dbapi }
}

#[verifier::loop_isolation(false)]
pub fn e_init_state(u: &Univ, case: &ECase) -> (s: EState)
    requires wf_univ(u@),
    ensures s@ == init_state(u@, case@), wf(u@, s@),
{
    let n = u.paths.len();
    let mut procs: Vec<EProc> = Vec::new();
    let mut q: usize = 0;
    while q < case.nprocs
        invariant
            q <= case.nprocs,
            n == u@.n(),
            procs.len() == q,
            forall|j: int| 0 <= j < q ==> (#[trigger] procs@[j])@ == init_proc(u@, kind_of(case@, j)),
        decreases case.nprocs - q,
    {
        let mut locks: Vec<Hold> = Vec::new();
        let mut rlocks: Vec<bool> = Vec::new();
        let mut ppg: Vec<Option<Val>> = Vec::new();
        let mut i: usize = 0;
        while i < n
            invariant
                i <= n,
                locks.len() == i, rlocks.len() == i, ppg.len() == i,
                forall|j: int| 0 <= j < i ==> #[trigger] locks@[j] == zero_hold(),
                forall|j: int| 0 <= j < i ==> !(#[trigger] rlocks@[j]),
                forall|j: int| 0 <= j < i ==> (#[trigger] ppg@[j]) is None,
            decreases n - i,
        {
            locks.push(Hold { e: 0, s: 0, de: 0, ds: 0 });
            rlocks.push(false);
            ppg.push(None);
            i += 1;
        }
        let pr = EProc {
            alive: true, sqlflag: false, autocommit: true, kind: e_kind_of(case, q),
            marks: Vec::new(), undo: Vec::new(), locks, rlocks, ppg, pending: None,
        };
        assert(pr@.locks =~= Seq::new(u@.n(), |i: int| zero_hold()));
        assert(pr@.rlocks =~= Seq::new(u@.n(), |i: int| false));
        assert(pr@.ppg =~= Seq::new(u@.n(), |i: int| None::<Val>));
        assert(pr@.marks =~= Seq::<nat>::empty());
        assert(pr@.undo =~= Seq::<Undo>::empty());
        procs.push(pr);
        q += 1;
    }
    let mut g: Vec<Option<Val>> = Vec::new();
    let mut i: usize = 0;
    while i < n
        invariant i <= n, g.len() == i, forall|j: int| 0 <= j < i ==> (#[trigger] g@[j]) is None,
        decreases n - i,
    {
        g.push(None);
        i += 1;
    }
    let s = EState { g, procs };
    assert(s@.g =~= Seq::new(u@.n(), |i: int| None::<Val>));
    assert(s@.procs =~= Seq::new(case@.nprocs, |q: int| init_proc(u@, kind_of(case@, q))));
    assert forall|q: int| 0 <= q < s@.procs.len() implies wf_proc(u@, #[trigger] s@.procs[q]) by {
        assert(s@.procs[q] == init_proc(u@, kind_of(case@, q)));
    }
    s
}

#[verifier::loop_isolation(false)]
pub fn e_finals(u: &Univ, case: &ECase, s: &EState) -> (f: Vec<EObs>)
    requires wf_univ(u@), wf(u@, s@), wf_case(u@, case@), case.observe.len() + case.observe_tables.len() <= usize::MAX,
    ensures obs_view(f@) == finals_from(u@, case@, s@, 0),
{
    let n1 = case.observe.len();
    let n = n1 + case.observe_tables.len();
    let mut f: Vec<EObs> = Vec::new();
    let mut i: usize = 0;
    while i < n
        invariant
            i <= n,
            n1 == case@.observe.len(),
            n == case@.observe.len() + case@.observe_tables.len(),
            obs_view(f@) + finals_from(u@, case@, s@, i as nat) == finals_from(u@, case@, s@, 0),
        decreases n - i,
    {
        let o = if i < n1 {
            let c = case.observe[i];
            assert((c as int) < u@.n());
            EObs::Value(s.g[c])
        } else {
            let t = case.observe_tables[i - n1];
            assert(case@.observe_tables[i - n1] == t);
            e_select_obs(u, &s.g, t)
        };
        proof {
            let rest = finals_from(u@, case@, s@, (i + 1) as nat);
            lemma_obs_view_push(f@, o);
            assert(obs_view(f@).push(o@) + rest =~= obs_view(f@) + (seq![o@] + rest));
        }
        f.push(o);
        i += 1;
    }
    assert(obs_view(f@) + finals_from(u@, case@, s@, n as nat) =~= obs_view(f@));
    f
}

pub fn e_wf_univ(u: &Univ) -> (b: bool)
    ensures b ==> wf_univ(u@),
{
    let n = u.paths.len();
    if u.is_row.len() != n || u.table.len() != n || u.long.len() != n || u.key.len() != n {
        return false;
    }
    let mut c: usize = 0;
    while c < n
        invariant
            c <= n, n == u@.n(), u.is_row.len() == n, u.table.len() == n,
            forall|cc: int| 0 <= cc < c && u.is_row@[cc] ==> (u.table@[cc] as int) < u.texists.len(),
        decreases n - c,
    {
        if u.is_row[c] && u.table[c] >= u.texists.len() {
            return false;
        }
        c += 1;
    }
    true
}

pub fn e_wf_op(u: &Univ, op: Op) -> (b: bool)
    requires wf_univ(u@),
    ensures b == wf_op(u@, op),
{
    let n = u.paths.len();
    match op {
        Op::Set { c, .. } | Op::Kill { c } | Op::Get { c } | Op::Data { c } | Op::Incr { c } | Op::PpgSet { c, .. }
        | Op::PpgGet { c } | Op::Lock { c, .. } | Op::Unlock { c, .. } | Op::LockOnly { c, .. } => c < n,
        Op::Insert { r, .. } | Op::Update { r, .. } | Op::Delete { r } => r < n && u.is_row[r],
        Op::Select { t } => t < u.texists.len(),
        Op::ZStrip { a } => a < u.zargs.len(),
        Op::Order { c } => c < n && !u.is_row[c],
        Op::PutE { r, .. } | Op::GetE { r } | Op::EmbRegister { r } | Op::EmbRetract { r } => r < n && u.is_row[r],
        Op::MatchE { t, .. } | Op::EmbCount { t } | Op::EmbRoute { t } => t < u.texists.len(),
        Op::InsertSelect { from, to } => from < u.texists.len() && to < u.texists.len(),
        Op::EmbAssert { rn, rr, .. } => rn < n && u.is_row[rn] && rr < n && u.is_row[rr],
        Op::Upsert { r, .. } => r < n && u.is_row[r],
        Op::InsertMany { t, b } => t < u.texists.len() && b < u.batches.len() && {
            assert(u@.batches[b as int] == u.batches@[b as int]@);
            e_batch_ok(u, t, &u.batches[b])
        },
        _ => true,
    }
}

pub fn e_wf_case(u: &Univ, case: &ECase) -> (b: bool)
    requires wf_univ(u@),
    ensures b ==> wf_case(u@, case@) && case.observe.len() + case.observe_tables.len() <= usize::MAX,
{
    if case.observe.len() > usize::MAX - case.observe_tables.len() {
        return false;
    }
    let mut i: usize = 0;
    while i < case.steps.len()
        invariant
            i <= case.steps.len(), wf_univ(u@),
            forall|j: int| 0 <= j < i ==> (#[trigger] case@.steps[j]).0 < case@.nprocs && wf_op(u@, case@.steps[j].1),
        decreases case.steps.len() - i,
    {
        let (p, op) = case.steps[i];
        if p >= case.nprocs || !e_wf_op(u, op) {
            return false;
        }
        i += 1;
    }
    let mut i: usize = 0;
    while i < case.observe.len()
        invariant
            i <= case.observe.len(),
            forall|j: int| 0 <= j < i ==> (#[trigger] case@.observe[j] as int) < u@.n(),
        decreases case.observe.len() - i,
    {
        if case.observe[i] >= u.paths.len() {
            return false;
        }
        i += 1;
    }
    let mut i: usize = 0;
    while i < case.observe_tables.len()
        invariant
            i <= case.observe_tables.len(),
            forall|j: int| 0 <= j < i ==> (#[trigger] case@.observe_tables[j] as int) < u@.texists.len(),
        decreases case.observe_tables.len() - i,
    {
        if case.observe_tables[i] >= u.texists.len() {
            return false;
        }
        i += 1;
    }
    true
}

/// Drive a case with a choice sequence: verified equal to the specification's `run` (Invalid only for a case the
/// harness would never build).
#[verifier::loop_isolation(false)]
pub fn e_run(sem: &Sem, u: &Univ, case: &ECase, choices: &Vec<bool>) -> (res: ERunRes)
    ensures
        res is NeedMore ==> run(*sem, u@, case@, choices@) is NeedMore,
        res matches ERunRes::Done(obs, finals, used) ==>
            run(*sem, u@, case@, choices@) == RunRes::Done(obs_view(obs@), obs_view(finals@), used as nat),
{
    if !e_wf_univ(u) || !e_wf_case(u, case) {
        return ERunRes::Invalid;
    }
    let mut s = e_init_state(u, case);
    let mut obs: Vec<EObs> = Vec::new();
    assert(obs_view(obs@) =~= Seq::<Obs>::empty());
    let mut i: usize = 0;
    let mut ci: usize = 0;
    while i < case.steps.len()
        invariant
            i <= case.steps.len(),
            ci <= choices.len(),
            wf_univ(u@), wf_case(u@, case@), wf(u@, s@), case.observe.len() + case.observe_tables.len() <= usize::MAX,
            run(*sem, u@, case@, choices@) == run_from(*sem, u@, case@, s@, i as nat, choices@, ci as nat, obs_view(obs@)),
        decreases case.steps.len() - i,
    {
        let (p, op) = case.steps[i];
        assert(case@.steps[i as int] == (p, op));
        match e_driver_refusal(e_kind_of(case, p), op) {
            Some(rk) => {
                proof { lemma_obs_view_push(obs@, EObs::Refused(rk)); }
                obs.push(EObs::Refused(rk));
            },
            None => {
                if e_choice_point(sem, u, &s, p, op) {
                    if ci >= choices.len() {
                        return ERunRes::NeedMore;
                    }
                    let o = e_step(sem, u, &mut s, p, op, choices[ci]);
                    proof { lemma_obs_view_push(obs@, o); }
                    obs.push(o);
                    ci += 1;
                } else {
                    let o = e_step(sem, u, &mut s, p, op, false);
                    proof { lemma_obs_view_push(obs@, o); }
                    obs.push(o);
                }
            },
        }
        i += 1;
    }
    let f = e_finals(u, case, &s);
    ERunRes::Done(obs, f, ci)
}

} // verus!
