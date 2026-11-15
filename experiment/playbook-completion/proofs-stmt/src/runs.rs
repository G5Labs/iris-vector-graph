//! Composition of runs and traces over concatenated operation lists and programs.
use vstd::prelude::*;
use ivg_proofs_env2::spec::*;
use crate::lay::*;
use crate::prog::*;

verus! {

pub proof fn lemma_run_ops_empty(sem: Sem, u: U, s: State, p: usize)
    ensures run_ops(sem, u, s, p, Seq::<Op>::empty()) == s,
{
}

pub proof fn lemma_run_ops_cons(sem: Sem, u: U, s: State, p: usize, op: Op, rest: Seq<Op>)
    ensures run_ops(sem, u, s, p, seq![op] + rest) == run_ops(sem, u, step(sem, u, s, p, op, false).0, p, rest),
{
    let ops = seq![op] + rest;
    assert(ops[0] == op);
    assert(ops.drop_first() =~= rest);
}

pub proof fn lemma_run_ops_one(sem: Sem, u: U, s: State, p: usize, op: Op)
    ensures run_ops(sem, u, s, p, seq![op]) == step(sem, u, s, p, op, false).0,
{
    lemma_run_ops_cons(sem, u, s, p, op, Seq::empty());
    assert(seq![op] + Seq::<Op>::empty() =~= seq![op]);
    lemma_run_ops_empty(sem, u, step(sem, u, s, p, op, false).0, p);
}

pub proof fn lemma_run_ops_concat(sem: Sem, u: U, s: State, p: usize, a: Seq<Op>, b: Seq<Op>)
    ensures run_ops(sem, u, s, p, a + b) == run_ops(sem, u, run_ops(sem, u, s, p, a), p, b),
    decreases a.len(),
{
    if a.len() == 0 {
        assert(a + b =~= b);
    } else {
        let s1 = step(sem, u, s, p, a[0], false).0;
        assert((a + b)[0] == a[0]);
        assert((a + b).drop_first() =~= a.drop_first() + b);
        lemma_run_ops_concat(sem, u, s1, p, a.drop_first(), b);
    }
}

pub proof fn lemma_run_prog_empty(sem: Sem, u: U, ly: Lay, s: State, p: usize)
    ensures run_prog(sem, u, ly, s, p, Seq::<(St, u32)>::empty()) == s,
{
}

pub proof fn lemma_run_prog_one(sem: Sem, u: U, ly: Lay, s: State, p: usize, x: (St, u32))
    ensures run_prog(sem, u, ly, s, p, seq![x]) == run_st(sem, u, ly, s, p, x.0),
{
    let pg = seq![x];
    assert(pg[0] == x);
    assert(pg.drop_first() =~= Seq::<(St, u32)>::empty());
    lemma_run_prog_empty(sem, u, ly, run_st(sem, u, ly, s, p, x.0), p);
}

pub proof fn lemma_run_prog_concat(sem: Sem, u: U, ly: Lay, s: State, p: usize, a: Seq<(St, u32)>, b: Seq<(St, u32)>)
    ensures run_prog(sem, u, ly, s, p, a + b) == run_prog(sem, u, ly, run_prog(sem, u, ly, s, p, a), p, b),
    decreases a.len(),
{
    if a.len() == 0 {
        assert(a + b =~= b);
    } else {
        let s1 = run_st(sem, u, ly, s, p, a[0].0);
        assert((a + b)[0] == a[0]);
        assert((a + b).drop_first() =~= a.drop_first() + b);
        lemma_run_prog_concat(sem, u, ly, s1, p, a.drop_first(), b);
    }
}

pub proof fn lemma_trace_ops_concat(sem: Sem, u: U, s: State, p: usize, a: Seq<Op>, b: Seq<Op>)
    ensures trace_ops(sem, u, s, p, a + b) == trace_ops(sem, u, s, p, a) + trace_ops(sem, u, run_ops(sem, u, s, p, a), p, b),
    decreases a.len(),
{
    if a.len() == 0 {
        assert(a + b =~= b);
        assert(trace_ops(sem, u, s, p, a) =~= Seq::<(State, Op)>::empty());
        assert(Seq::<(State, Op)>::empty() + trace_ops(sem, u, s, p, b) =~= trace_ops(sem, u, s, p, b));
    } else {
        let s1 = step(sem, u, s, p, a[0], false).0;
        assert((a + b)[0] == a[0]);
        assert((a + b).drop_first() =~= a.drop_first() + b);
        lemma_trace_ops_concat(sem, u, s1, p, a.drop_first(), b);
        let x = seq![(s, a[0])];
        assert(x + (trace_ops(sem, u, s1, p, a.drop_first()) + trace_ops(sem, u, run_ops(sem, u, s1, p, a.drop_first()), p, b))
            =~= (x + trace_ops(sem, u, s1, p, a.drop_first())) + trace_ops(sem, u, run_ops(sem, u, s1, p, a.drop_first()), p, b));
    }
}

pub proof fn lemma_trace_prog_concat(sem: Sem, u: U, ly: Lay, s: State, p: usize, a: Seq<(St, u32)>, b: Seq<(St, u32)>)
    ensures trace_prog(sem, u, ly, s, p, a + b)
        == trace_prog(sem, u, ly, s, p, a) + trace_prog(sem, u, ly, run_prog(sem, u, ly, s, p, a), p, b),
    decreases a.len(),
{
    if a.len() == 0 {
        assert(a + b =~= b);
        assert(trace_prog(sem, u, ly, s, p, a) =~= Seq::<(State, Op)>::empty());
        assert(Seq::<(State, Op)>::empty() + trace_prog(sem, u, ly, s, p, b) =~= trace_prog(sem, u, ly, s, p, b));
    } else {
        let s1 = run_st(sem, u, ly, s, p, a[0].0);
        assert((a + b)[0] == a[0]);
        assert((a + b).drop_first() =~= a.drop_first() + b);
        lemma_trace_prog_concat(sem, u, ly, s1, p, a.drop_first(), b);
        let x = trace_ops(sem, u, s, p, ops_of(u, ly, s.g, a[0].0));
        let y = trace_prog(sem, u, ly, s1, p, a.drop_first());
        let z = trace_prog(sem, u, ly, run_prog(sem, u, ly, s1, p, a.drop_first()), p, b);
        assert(x + (y + z) =~= (x + y) + z);
    }
}

pub proof fn lemma_trace_prog_one(sem: Sem, u: U, ly: Lay, s: State, p: usize, x: (St, u32))
    ensures trace_prog(sem, u, ly, s, p, seq![x]) == trace_ops(sem, u, s, p, ops_of(u, ly, s.g, x.0)),
{
    let pg = seq![x];
    assert(pg[0] == x);
    assert(pg.drop_first() =~= Seq::<(St, u32)>::empty());
    let t = trace_ops(sem, u, s, p, ops_of(u, ly, s.g, x.0));
    assert(trace_prog(sem, u, ly, run_st(sem, u, ly, s, p, x.0), p, Seq::<(St, u32)>::empty()) =~= Seq::<(State, Op)>::empty());
    assert(t + Seq::<(State, Op)>::empty() =~= t);
}

} // verus!
