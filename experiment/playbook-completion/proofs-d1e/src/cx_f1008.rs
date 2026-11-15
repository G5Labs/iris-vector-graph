//! Proved counterexample for control `control_f1008_every_graph_mixed` (F-1008), compiled only with it.
//!
//! The live trace b-10-live-scope (default graph b10_s -> b10_k, named graph b10g1 b10_k -> b10_m; VarLength.Ends
//! ('b10_s', '', 'out', 2, 2, pAll=1) answered b10_m at length 2) and m10-walk-as-built-one-graph: default graph
//! 1 -> 2, graph 1 2 -> 3; the every-graph expansion of length 2 from 1 answers 3, which is not an L1 step (no walk of
//! length 2 from 1 stays in one graph).
use vstd::prelude::*;
use actors::protocol::*;
use crate::atrav_l1::*;
use crate::atrav_l2::*;
use crate::atrav_runs::*;

verus! {

pub open spec fn c0() -> TS2 { t_init(Set::empty().insert(1int).insert(2int)) }
pub open spec fn c1() -> TS2 { p_addedge(c0(), 0, 1, 2) }
pub open spec fn c2() -> TS2 { p_addedge(c1(), 1, 2, 3) }
pub open spec fn ends() -> Set<int> { Set::empty().insert(3int) }

pub proof fn counterexample_f1008()
    ensures
        init2(c0()),
        step2(c0(), TL2::AddEdge { g: 0, a: 1, b: 2 }, c1()),
        step2(c1(), TL2::AddEdge { g: 1, a: 2, b: 3 }, c2()),
        step2(c2(), TL2::VarLen { start: 1, lo: 2, hi: 2, all: true, ends: ends() }, c2()),
        !step_or_stutter::<TravL1>(abst(c2()), labt(TL2::VarLen { start: 1, lo: 2, hi: 2, all: true, ends: ends() }), abst(c2())),
{
    lemma_t_steps(c0(), 0, 1, 2, 0, Map::empty());
    lemma_t_steps(c1(), 1, 2, 3, 0, Map::empty());
    let out = c2().out;
    assert(out =~= Set::empty().insert(E { g: 0, a: 1, b: 2 }).insert(E { g: 1, a: 2, b: 3 }));
    let f = st_any(out, true);
    assert(out.contains(E { g: 0, a: 1, b: 2 }) && out.contains(E { g: 1, a: 2, b: 3 }));
    assert(f(1, 2));
    assert(f(2, 3));
    // the mixed walk: f(1, c) only for c = 2, f(2, y) only for y = 3
    assert forall|c: int| #[trigger] f(1, c) implies c == 2 by {
        let g = choose|g: int| (true || g == 0) && #[trigger] out.contains(E { g, a: 1, b: c });
    }
    assert forall|y: int| #[trigger] f(2, y) implies y == 3 by {
        let g = choose|g: int| (true || g == 0) && #[trigger] out.contains(E { g, a: 2, b: y });
    }
    assert forall|x: int| #[trigger] ends().contains(x) <==> reach2(c2(), 1, 2, 2, true, x) by {
        lemma_walk2(f, 1, x);
        if x == 3 { assert(f(1, 2) && f(2, 3)); assert(walk(f, 1, 3, 2)); }
        if reach2(c2(), 1, 2, 2, true, x) {
            let l = choose|l: nat| 2 <= l <= 2 && #[trigger] walk(f, 1, x, l);
            assert(l == 2);
            let c = choose|c: int| #[trigger] f(1, c) && f(c, x);
        }
    }
    assert(varlen2(c2(), 1, 2, 2, true, ends()));
    // no single-graph walk of length 2 from 1 reaches 3
    assert forall|l: nat, g: int| 2 <= l <= 2 && (true || g == 0) implies !#[trigger] walk(st_out(out, g), 1, 3, l) by {
        lemma_walk2(st_out(out, g), 1, 3);
        if walk(st_out(out, g), 1, 3, 2) {
            let c = choose|c: int| #[trigger] st_out(out, g)(1, c) && st_out(out, g)(c, 3);
            assert(out.contains(E { g, a: 1, b: c }));
            assert(g == 0 && c == 2);
            assert(out.contains(E { g: 0, a: 2, b: 3 }));
        }
    }
    assert(!reach1(abst(c2()).edges, 1, 2, 2, true, 3));
    if varlen1(abst(c2()).edges, 1, 2, 2, true, ends()) { assert(ends().contains(3)); assert(false); }
}

} // verus!
