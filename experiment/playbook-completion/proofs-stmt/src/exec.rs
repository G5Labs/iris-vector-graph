//! Exec counterparts of the statement programs, verified equal to the specification (`prog.rs`): the program built
//! (`e_eg_prog` == `eg_prog_m`), a statement's expansion (`e_ops_of` == `ops_of`) and its run through proofs-env2's
//! verified `e_step` (`e_run_st` == `run_st`). The harness (harness/, unverified) builds a universe from a recorded
//! trace and calls these; it is the mechanical check of the hand translation against the journal.
use vstd::prelude::*;
use ivg_proofs_env2::spec::*;
use ivg_proofs_env2::exec::*;
use crate::lay::*;
use crate::prog::*;

verus! {

pub struct ELay {
    pub kind: Vec<CK>,
    pub gr: Vec<i64>,
    pub id: Vec<i64>,
    pub edge: Vec<bool>,
    pub dec: Vec<Option<(i64, usize)>>,
}

pub open spec fn ints_view(v: Seq<i64>) -> Seq<int> { Seq::new(v.len(), |i: int| v[i] as int) }

pub open spec fn dec_view(v: Seq<Option<(i64, usize)>>) -> Seq<Option<(int, usize)>> {
    Seq::new(v.len(), |i: int| match v[i] { Some(x) => Some((x.0 as int, x.1)), None => None })
}

impl View for ELay {
    type V = Lay;
    open spec fn view(&self) -> Lay {
        Lay { kind: self.kind@, gr: ints_view(self.gr@), id: ints_view(self.id@), edge: self.edge@, dec: dec_view(self.dec@) }
    }
}

/// What the exec program needs of a layout: per-cell vectors as long as the universe, decoded tuple cells inside it.
pub open spec fn lay_wf(u: U, ly: Lay) -> bool {
    &&& ly.kind.len() == u.n()
    &&& ly.gr.len() == u.n()
    &&& ly.id.len() == u.n()
    &&& ly.edge.len() == u.n()
    &&& forall|i: int| 0 <= i < ly.dec.len() && (#[trigger] ly.dec[i]) is Some ==> (odc(ly.dec[i]) as int) < u.n()
}

pub fn e_lay_wf(u: &Univ, ly: &ELay) -> (b: bool)
    ensures b ==> lay_wf(u@, ly@),
{
    let n = u.paths.len();
    if ly.kind.len() != n || ly.gr.len() != n || ly.id.len() != n || ly.edge.len() != n {
        return false;
    }
    let mut i: usize = 0;
    while i < ly.dec.len()
        invariant
            i <= ly.dec.len(), n == u.paths.len(),
            forall|k: int| 0 <= k < i && (#[trigger] ly@.dec[k]) is Some ==> (odc(ly@.dec[k]) as int) < u@.n(),
        decreases ly.dec.len() - i,
    {
        match ly.dec[i] {
            Some(x) => { if x.1 >= n { return false; } },
            None => {},
        }
        i += 1;
    }
    true
}

/// A statement whose operations the contract model accepts (proofs-env2 `wf_op`).
pub open spec fn st_wf(u: U, st: St) -> bool {
    match st {
        St::O { op } => wf_op(u, op),
        St::DelG { .. } => true,
        St::LedgerFor { root, .. } => (root as int) < u.n() && is_glob(u, root as int),
        St::DropNkg { ni, ver, inval, root } =>
            (ni as int) < u.n() && is_glob(u, ni as int) && (ver as int) < u.n() && (inval as int) < u.n() && (root as int) < u.n(),
    }
}

pub fn e_st_wf(u: &Univ, st: St) -> (b: bool)
    requires wf_univ(u@),
    ensures b == st_wf(u@, st),
{
    let n = u.paths.len();
    match st {
        St::O { op } => e_wf_op(u, op),
        St::DelG { .. } => true,
        St::LedgerFor { root, .. } => root < n && !u.is_row[root],
        St::DropNkg { ni, ver, inval, root } => ni < n && !u.is_row[ni] && ver < n && inval < n && root < n,
    }
}

// ------------------------------------------------------------------------------------------------ expansion

pub fn e_extend(v: &mut Vec<Op>, w: &Vec<Op>)
    ensures v@ == old(v)@ + w@,
{
    let ghost v0 = v@;
    let mut i: usize = 0;
    while i < w.len()
        invariant i <= w.len(), v@ == v0 + w@.subrange(0, i as int),
        decreases w.len() - i,
    {
        proof { assert(w@.subrange(0, i + 1) =~= w@.subrange(0, i as int).push(w@[i as int])); }
        v.push(w[i]);
        i += 1;
    }
    proof { assert(w@.subrange(0, w.len() as int) =~= w@); }
}

pub fn e_delg_ops(u: &Univ, ly: &ELay, t: usize, g: i64) -> (v: Vec<Op>)
    requires wf_univ(u@), lay_wf(u@, ly@),
    ensures v@ == delg_ops(u@, ly@, t, g, 0),
{
    let n = u.paths.len();
    let mut v: Vec<Op> = Vec::new();
    let mut j: usize = 0;
    while j < n
        invariant
            j <= n, n == u@.n(), wf_univ(u@), lay_wf(u@, ly@),
            delg_ops(u@, ly@, t, g, 0) == v@ + delg_ops(u@, ly@, t, g, j as nat),
        decreases n - j,
    {
        let ghost rest = delg_ops(u@, ly@, t, g, (j + 1) as nat);
        if u.is_row[j] && u.table[j] == t && ly.gr[j] == g {
            proof {
                assert(delg_ops(u@, ly@, t, g, j as nat) == seq![Op::Delete { r: j }] + rest);
                assert(v@.push(Op::Delete { r: j }) + rest =~= v@ + (seq![Op::Delete { r: j }] + rest));
            }
            v.push(Op::Delete { r: j });
        } else {
            proof { assert(delg_ops(u@, ly@, t, g, j as nat) == rest); }
        }
        j += 1;
    }
    proof { assert(v@ + delg_ops(u@, ly@, t, g, n as nat) =~= v@); }
    v
}

pub fn e_lf_reads(u: &Univ, ly: &ELay, gv: &Vec<Option<Val>>) -> (v: Vec<Op>)
    requires wf_univ(u@), lay_wf(u@, ly@), gv@.len() == u@.n(),
    ensures v@ == lf_reads(u@, ly@, gv@, 0),
{
    let n = u.paths.len();
    let mut v: Vec<Op> = Vec::new();
    let mut j: usize = 0;
    while j < n
        invariant
            j <= n, n == u@.n(), lay_wf(u@, ly@), gv@.len() == n,
            lf_reads(u@, ly@, gv@, 0) == v@ + lf_reads(u@, ly@, gv@, j as nat),
        decreases n - j,
    {
        let ghost rest = lf_reads(u@, ly@, gv@, (j + 1) as nat);
        let stm = match ly.kind[j] { CK::Stmt => true, _ => false };
        let def = match gv[j] { Some(_) => true, None => false };
        if stm && def {
            proof {
                assert(is_stm(u@, ly@, j as int));
                assert(lf_reads(u@, ly@, gv@, j as nat) == seq![Op::Get { c: j }] + rest);
                assert(v@.push(Op::Get { c: j }) + rest =~= v@ + (seq![Op::Get { c: j }] + rest));
            }
            v.push(Op::Get { c: j });
        } else {
            proof { assert(lf_reads(u@, ly@, gv@, j as nat) == rest); }
        }
        j += 1;
    }
    proof { assert(v@ + lf_reads(u@, ly@, gv@, n as nat) =~= v@); }
    v
}

pub fn e_lf_kills(u: &Univ, ly: &ELay, gv: &Vec<Option<Val>>, g: i64) -> (v: Vec<Op>)
    requires wf_univ(u@), lay_wf(u@, ly@), gv@.len() == u@.n(),
    ensures v@ == lf_kills(u@, ly@, gv@, g, 0),
{
    let n = u.paths.len();
    let mut v: Vec<Op> = Vec::new();
    let mut j: usize = 0;
    while j < n
        invariant
            j <= n, n == u@.n(), lay_wf(u@, ly@), gv@.len() == n,
            lf_kills(u@, ly@, gv@, g, 0) == v@ + lf_kills(u@, ly@, gv@, g, j as nat),
        decreases n - j,
    {
        let ghost rest = lf_kills(u@, ly@, gv@, g, (j + 1) as nat);
        let mut dm = false;
        let mut tc: usize = 0;
        match ly.kind[j] {
            CK::Stmt => {
                match gv[j] {
                    Some(Val::Str(i)) => {
                        if i < ly.dec.len() {
                            match ly.dec[i] {
                                Some(x) => { if x.0 == g { dm = true; tc = x.1; } },
                                None => {},
                            }
                        }
                    },
                    _ => {},
                }
            },
            _ => {},
        }
        proof {
            assert(dm == doomed(u@, ly@, gv@, g, j as int));
            if dm { assert(tc == tcell(ly@, gv@, j as int)); }
        }
        if dm {
            proof {
                assert(lf_kills(u@, ly@, gv@, g, j as nat) == seq![Op::Kill { c: tc }, Op::Kill { c: j }] + rest);
                assert(v@.push(Op::Kill { c: tc }).push(Op::Kill { c: j }) + rest
                    =~= v@ + (seq![Op::Kill { c: tc }, Op::Kill { c: j }] + rest));
            }
            v.push(Op::Kill { c: tc });
            v.push(Op::Kill { c: j });
        } else {
            proof { assert(lf_kills(u@, ly@, gv@, g, j as nat) == rest); }
        }
        j += 1;
    }
    proof { assert(v@ + lf_kills(u@, ly@, gv@, g, n as nat) =~= v@); }
    v
}

pub fn e_has_kids(u: &Univ, gv: &Vec<Option<Val>>, c: usize) -> (b: bool)
    requires wf_univ(u@), gv@.len() == u@.n(), u.paths.len() == u.is_row.len(),
    ensures b == has_kids(u@, gv@, c as int),
{
    let n = u.paths.len();
    let mut j: usize = 0;
    while j < n
        invariant
            j <= n, n == u@.n(), gv@.len() == n, wf_univ(u@), u.paths.len() == u.is_row.len(),
            forall|k: int| 0 <= k < j ==> !(k != c as int && covers(u@, c as int, k) && #[trigger] gv@[k] is Some),
        decreases n - j,
    {
        if j != c && e_covers(u, c, j) {
            match gv[j] {
                Some(_) => {
                    proof { assert(j as int != c as int && covers(u@, c as int, j as int) && gv@[j as int] is Some); }
                    return true;
                },
                None => {},
            }
        }
        j += 1;
    }
    false
}

pub fn e_nkg_ops(u: &Univ, gv: &Vec<Option<Val>>, ni: usize, ver: usize, inval: usize, root: usize) -> (v: Vec<Op>)
    requires wf_univ(u@), gv@.len() == u@.n(), u.paths.len() == u.is_row.len(), (ver as int) < u@.n(),
    ensures v@ == nkg_ops(u@, gv@, ni, ver, inval, root),
{
    let cur = e_num_of(u, gv[ver]);
    let nv = if cur < i64::MAX { Val::Num(cur + 1) } else { Val::Num(cur) };
    proof { assert(nv == nkg_next(u@, gv@[ver as int])); }
    let mut v: Vec<Op> = Vec::new();
    v.push(Op::Order { c: ni });
    v.push(Op::Get { c: ver });
    v.push(Op::Kill { c: root });
    v.push(Op::Set { c: ver, v: nv });
    let kids = e_has_kids(u, gv, ni);
    if kids {
        v.push(Op::Set { c: inval, v: Val::Num(1) });
        proof {
            assert(v@ =~= seq![Op::Order { c: ni }, Op::Get { c: ver }, Op::Kill { c: root }, Op::Set { c: ver, v: nv }]
                + seq![Op::Set { c: inval, v: Val::Num(1) }]);
        }
    } else {
        proof {
            assert(v@ =~= seq![Op::Order { c: ni }, Op::Get { c: ver }, Op::Kill { c: root }, Op::Set { c: ver, v: nv }]
                + Seq::<Op>::empty());
        }
    }
    v
}

pub fn e_ops_of(u: &Univ, ly: &ELay, gv: &Vec<Option<Val>>, st: St) -> (v: Vec<Op>)
    requires wf_univ(u@), lay_wf(u@, ly@), gv@.len() == u@.n(), u.paths.len() == u.is_row.len(), st_wf(u@, st),
    ensures v@ == ops_of(u@, ly@, gv@, st),
{
    match st {
        St::O { op } => {
            let mut v: Vec<Op> = Vec::new();
            v.push(op);
            proof { assert(v@ =~= seq![op]); }
            v
        },
        St::DelG { t, g } => e_delg_ops(u, ly, t, g),
        St::LedgerFor { root, g } => {
            let mut v: Vec<Op> = Vec::new();
            v.push(Op::Order { c: root });
            let r = e_lf_reads(u, ly, gv);
            let k = e_lf_kills(u, ly, gv, g);
            proof { assert(v@ =~= seq![Op::Order { c: root }]); }
            e_extend(&mut v, &r);
            e_extend(&mut v, &k);
            v
        },
        St::DropNkg { ni, ver, inval, root } => e_nkg_ops(u, gv, ni, ver, inval, root),
    }
}

// ------------------------------------------------------------------------------------------------ the operations are well formed

pub proof fn lemma_ops_wf(u: U, ly: Lay, gv: Seq<Option<Val>>, st: St)
    requires wf_univ(u), lay_wf(u, ly), gv.len() == u.n(), u.n() <= usize::MAX, st_wf(u, st),
    ensures forall|i: int| 0 <= i < ops_of(u, ly, gv, st).len() ==> wf_op(u, #[trigger] ops_of(u, ly, gv, st)[i]),
{
    let ops = ops_of(u, ly, gv, st);
    match st {
        St::O { op } => {
            assert forall|i: int| 0 <= i < ops.len() implies wf_op(u, #[trigger] ops[i]) by { assert(ops[i] == op); }
        },
        St::DelG { t, g } => {
            crate::eg::lemma_delg_ops_rows(u, ly, t, g, 0);
            assert forall|i: int| 0 <= i < ops.len() implies wf_op(u, #[trigger] ops[i]) by {
                assert(crate::eg::row_delete(u, ops[i]));
            }
        },
        St::LedgerFor { root, g } => {
            lemma_lf_reads_wf(u, ly, gv, 0);
            lemma_lf_kills_wf(u, ly, gv, g, 0);
            let a = seq![Op::Order { c: root }];
            let b = lf_reads(u, ly, gv, 0);
            let c = lf_kills(u, ly, gv, g, 0);
            assert forall|i: int| 0 <= i < ops.len() implies wf_op(u, #[trigger] ops[i]) by {
                if i < a.len() { assert(ops[i] == a[i]); }
                else if i < a.len() + b.len() { assert(ops[i] == b[i - a.len()]); }
                else { assert(ops[i] == c[i - a.len() - b.len()]); }
            }
        },
        St::DropNkg { ni, ver, inval, root } => {
            assert forall|i: int| 0 <= i < ops.len() implies wf_op(u, #[trigger] ops[i]) by {
                if i == 0 { assert(ops[i] == Op::Order { c: ni }); }
                else if i == 1 { assert(ops[i] == Op::Get { c: ver }); }
                else if i == 2 { assert(ops[i] == Op::Kill { c: root }); }
                else if i == 3 { assert(ops[i] == Op::Set { c: ver, v: nkg_next(u, gv[ver as int]) }); }
                else { assert(ops[i] == Op::Set { c: inval, v: Val::Num(1) }); }
            }
        },
    }
}

pub proof fn lemma_lf_reads_wf(u: U, ly: Lay, gv: Seq<Option<Val>>, j: nat)
    requires u.n() <= usize::MAX,
    ensures forall|i: int| 0 <= i < lf_reads(u, ly, gv, j).len() ==> wf_op(u, #[trigger] lf_reads(u, ly, gv, j)[i]),
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_lf_reads_wf(u, ly, gv, j + 1);
        let rest = lf_reads(u, ly, gv, j + 1);
        if is_stm(u, ly, j as int) && gv[j as int] is Some {
            let x = seq![Op::Get { c: j as usize }] + rest;
            assert forall|i: int| 0 <= i < x.len() implies wf_op(u, #[trigger] x[i]) by {
                if i > 0 { assert(x[i] == rest[i - 1]); }
            }
        }
    }
}

pub proof fn lemma_lf_kills_wf(u: U, ly: Lay, gv: Seq<Option<Val>>, g: i64, j: nat)
    requires u.n() <= usize::MAX, lay_wf(u, ly),
    ensures forall|i: int| 0 <= i < lf_kills(u, ly, gv, g, j).len() ==> wf_op(u, #[trigger] lf_kills(u, ly, gv, g, j)[i]),
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_lf_kills_wf(u, ly, gv, g, j + 1);
        let rest = lf_kills(u, ly, gv, g, j + 1);
        if doomed(u, ly, gv, g, j as int) {
            match gv[j as int]->Some_0 {
                Val::Str(k) => { assert(ly.dec[k as int] is Some); },
                _ => {},
            }
            let x = seq![Op::Kill { c: tcell(ly, gv, j as int) }, Op::Kill { c: j as usize }] + rest;
            assert forall|i: int| 0 <= i < x.len() implies wf_op(u, #[trigger] x[i]) by {
                if i > 1 { assert(x[i] == rest[i - 2]); }
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ runs

pub fn e_run_ops(sem: &Sem, u: &Univ, s: &mut EState, p: usize, ops: &Vec<Op>) -> (obs: Vec<EObs>)
    requires wf_univ(u@), wf(u@, old(s)@), forall|i: int| 0 <= i < ops@.len() ==> wf_op(u@, #[trigger] ops@[i]),
    ensures s@ == run_ops(*sem, u@, old(s)@, p, ops@), wf(u@, s@), obs@.len() == ops@.len(),
{
    let ghost s0 = s@;
    let mut obs: Vec<EObs> = Vec::new();
    let mut i: usize = 0;
    while i < ops.len()
        invariant
            i <= ops.len(), wf_univ(u@), wf(u@, s@), obs@.len() == i,
            forall|k: int| 0 <= k < ops@.len() ==> wf_op(u@, #[trigger] ops@[k]),
            run_ops(*sem, u@, s0, p, ops@) == run_ops(*sem, u@, s@, p, ops@.subrange(i as int, ops@.len() as int)),
        decreases ops.len() - i,
    {
        let ghost before = s@;
        let ghost rest = ops@.subrange(i as int, ops@.len() as int);
        let o = e_step(sem, u, s, p, ops[i], false);
        proof {
            assert(rest[0] == ops@[i as int]);
            assert(rest.drop_first() =~= ops@.subrange(i + 1, ops@.len() as int));
        }
        obs.push(o);
        i += 1;
    }
    proof { assert(ops@.subrange(ops@.len() as int, ops@.len() as int) =~= Seq::<Op>::empty()); }
    obs
}

/// One statement of a program: its operations (as `ops_of` expands them in the state it starts from) and their run.
pub fn e_run_st(sem: &Sem, u: &Univ, ly: &ELay, s: &mut EState, p: usize, st: St) -> (r: (Vec<Op>, Vec<EObs>))
    requires wf_univ(u@), lay_wf(u@, ly@), u@.n() <= usize::MAX, u.paths.len() == u.is_row.len(), wf(u@, old(s)@), st_wf(u@, st),
    ensures s@ == run_st(*sem, u@, ly@, old(s)@, p, st), r.0@ == ops_of(u@, ly@, old(s)@.g, st), wf(u@, s@),
{
    let ops = e_ops_of(u, ly, &s.g, st);
    proof { lemma_ops_wf(u@, ly@, s@.g, st); }
    let obs = e_run_ops(sem, u, s, p, &ops);
    (ops, obs)
}

// ------------------------------------------------------------------------------------------------ the programs

pub fn e_extend_prog(v: &mut Vec<(St, u32)>, w: Vec<(St, u32)>)
    ensures v@ == old(v)@ + w@,
{
    let ghost v0 = v@;
    let mut i: usize = 0;
    while i < w.len()
        invariant i <= w.len(), v@ == v0 + w@.subrange(0, i as int),
        decreases w.len() - i,
    {
        proof { assert(w@.subrange(0, i + 1) =~= w@.subrange(0, i as int).push(w@[i as int])); }
        v.push(w[i]);
        i += 1;
    }
    proof { assert(w@.subrange(0, w.len() as int) =~= w@); }
}

pub fn e_eg_tables(m: Mut, fr: Fr) -> (v: Vec<(usize, u32)>)
    ensures v@ == eg_tables(m, fr),
{
    let mut v: Vec<(usize, u32)> = Vec::new();
    v.push((fr.t_labels, 10130u32));
    v.push((fr.t_props, 10134u32));
    v.push((fr.t_docs, 10145u32));
    v.push((fr.t_nemb, 10153u32));
    v.push((fr.t_nembo, 10157u32));
    v.push((fr.t_reif, 10186u32));
    v.push((fr.t_eemb, 10198u32));
    let drop = match m { Mut::DropEdges => true, _ => false };
    if !drop {
        v.push((fr.t_edges, 10217u32));
    }
    v.push((fr.t_nodes, 10222u32));
    proof { assert(v@ =~= eg_tables(m, fr)); }
    v
}

pub fn e_delg_seg(tabs: &Vec<(usize, u32)>, g: i64) -> (v: Vec<(St, u32)>)
    ensures v@ == delg_seg(tabs@, g),
{
    let mut v: Vec<(St, u32)> = Vec::new();
    let mut i: usize = 0;
    while i < tabs.len()
        invariant i <= tabs.len(), v@ =~= delg_seg(tabs@.subrange(0, i as int), g),
        decreases tabs.len() - i,
    {
        let x = tabs[i];
        proof {
            assert(tabs@.subrange(0, i + 1) =~= tabs@.subrange(0, i as int).push(x));
            assert(delg_seg(tabs@.subrange(0, i + 1), g) =~= delg_seg(tabs@.subrange(0, i as int), g).push((St::DelG { t: x.0, g }, x.1)));
        }
        v.push((St::DelG { t: x.0, g }, x.1));
        i += 1;
    }
    proof { assert(tabs@.subrange(0, tabs.len() as int) =~= tabs@); }
    v
}

pub fn e_lf_seg(fr: Fr, g: i64) -> (v: Vec<(St, u32)>)
    ensures v@ == lf_seg(fr, g),
{
    let mut v: Vec<(St, u32)> = Vec::new();
    v.push((St::LedgerFor { root: fr.stmt_root, g }, 10256u32));
    proof { assert(v@ =~= lf_seg(fr, g)); }
    v
}

pub fn e_eg_s3(fr: Fr, nkg: bool) -> (v: Vec<(St, u32)>)
    ensures v@ == eg_s3(fr, nkg),
{
    let mut a: Vec<(St, u32)> = Vec::new();
    a.push((St::O { op: Op::Lock { c: fr.adjw, mode: Mode::S, wait: true } }, 20431u32));
    proof { assert(a@ =~= eg_s3a(fr)); }
    let mut b: Vec<(St, u32)> = Vec::new();
    b.push((St::O { op: Op::Kill { c: fr.kg_out } }, 20435u32));
    b.push((St::O { op: Op::Kill { c: fr.kg_in } }, 20436u32));
    b.push((St::O { op: Op::Kill { c: fr.kg_gen } }, 20437u32));
    b.push((St::O { op: Op::Kill { c: fr.kg_degc } }, 20438u32));
    b.push((St::O { op: Op::Kill { c: fr.kg_degw } }, 20439u32));
    b.push((St::O { op: Op::Kill { c: fr.adjnolock } }, 20440u32));
    b.push((St::O { op: Op::Kill { c: fr.kg_deg } }, 20442u32));
    b.push((St::O { op: Op::Kill { c: fr.kg_degp } }, 20443u32));
    b.push((St::O { op: Op::Incr { c: fr.kg_ver } }, 20444u32));
    proof { assert(b@ =~= eg_s3b(fr)); }
    let mut c: Vec<(St, u32)> = Vec::new();
    c.push((St::O { op: Op::Unlock { c: fr.adjw, mode: Mode::S, immediate: false } }, 20445u32));
    proof { assert(c@ =~= eg_s3c(fr)); }
    let mut d: Vec<(St, u32)> = Vec::new();
    d.push((St::O { op: Op::Kill { c: fr.tout } }, 30370u32));
    d.push((St::O { op: Op::Kill { c: fr.tin } }, 30371u32));
    d.push((St::O { op: Op::Kill { c: fr.bucket } }, 30372u32));
    d.push((St::O { op: Op::Kill { c: fr.tagg } }, 30373u32));
    d.push((St::O { op: Op::Kill { c: fr.edgeprop } }, 30374u32));
    d.push((St::O { op: Op::Kill { c: fr.tlast } }, 30375u32));
    proof { assert(d@ =~= eg_ti(fr)); }
    let mut e: Vec<(St, u32)> = Vec::new();
    e.push((St::O { op: Op::Kill { c: fr.kg_prop } }, 10239u32));
    e.push((St::O { op: Op::Kill { c: fr.kg_label } }, 10240u32));
    e.push((St::O { op: Op::Kill { c: fr.deg2p } }, 10241u32));
    e.push((St::O { op: Op::Kill { c: fr.deg2p_exact } }, 10242u32));
    e.push((St::O { op: Op::Kill { c: fr.gmode } }, 10244u32));
    e.push((St::O { op: Op::Kill { c: fr.algo_g } }, 10249u32));
    proof { assert(e@ =~= eg_er(fr)); }
    let mut f: Vec<(St, u32)> = Vec::new();
    if nkg {
        f.push((St::DropNkg { ni: fr.nkg_ni, ver: fr.nkg_ver, inval: fr.nkg_inval, root: fr.nkg }, 11041u32));
    }
    proof { assert(f@ =~= eg_nkg(fr, nkg)); }
    let mut h: Vec<(St, u32)> = Vec::new();
    h.push((St::O { op: Op::Incr { c: fr.kg_ver } }, 50301u32));
    h.push((St::O { op: Op::Incr { c: fr.nkg_ver } }, 50302u32));
    h.push((St::O { op: Op::Kill { c: fr.algo_all } }, 11052u32));
    proof { assert(h@ =~= eg_bump(fr)); }
    let mut v = a;
    e_extend_prog(&mut v, b);
    e_extend_prog(&mut v, c);
    e_extend_prog(&mut v, d);
    e_extend_prog(&mut v, e);
    e_extend_prog(&mut v, f);
    e_extend_prog(&mut v, h);
    proof { assert(v@ =~= eg_s3(fr, nkg)); }
    v
}

/// EraseGraph(g)'s program with mutant m (`head`: the reviewed design's head lock).
pub fn e_eg_prog(m: Mut, head: bool, fr: Fr, g: i64, nkg: bool) -> (v: Vec<(St, u32)>)
    ensures v@ == eg_prog_m(m, head, fr, g, nkg),
{
    let mut v: Vec<(St, u32)> = Vec::new();
    v.push((St::O { op: Op::TStart }, 10056u32));
    if head {
        v.push((St::O { op: Op::Lock { c: fr.head, mode: Mode::E, wait: true } }, 90001u32));
    }
    proof { assert(v@ =~= eg_s1(head, fr)); }
    let lf_first = match m { Mut::LedgerFirst => true, _ => false };
    let lf_after = match m { Mut::AfterCommit => true, _ => false };
    let lf_none = match m { Mut::DropLedger => true, Mut::LedgerFirst => true, Mut::AfterCommit => true, _ => false };
    let mut s0: Vec<(St, u32)> = Vec::new();
    if lf_first { s0 = e_lf_seg(fr, g); }
    proof { assert(s0@ =~= eg_s0(m, fr, g)); }
    let tabs = e_eg_tables(m, fr);
    let s2 = e_delg_seg(&tabs, g);
    let s3 = e_eg_s3(fr, nkg);
    let mut s4: Vec<(St, u32)> = Vec::new();
    if !lf_none { s4 = e_lf_seg(fr, g); }
    proof { assert(s4@ =~= eg_s4(m, fr, g)); }
    let mut s5: Vec<(St, u32)> = Vec::new();
    if head {
        s5.push((St::O { op: Op::Unlock { c: fr.head, mode: Mode::E, immediate: false } }, 90002u32));
    }
    s5.push((St::O { op: Op::TCommit }, 10258u32));
    proof { assert(s5@ =~= eg_s5(head, fr)); }
    let mut s6: Vec<(St, u32)> = Vec::new();
    if lf_after { s6 = e_lf_seg(fr, g); }
    proof { assert(s6@ =~= eg_s6(m, fr, g)); }
    e_extend_prog(&mut v, s0);
    e_extend_prog(&mut v, s2);
    e_extend_prog(&mut v, s3);
    e_extend_prog(&mut v, s4);
    e_extend_prog(&mut v, s5);
    e_extend_prog(&mut v, s6);
    v
}

} // verus!
