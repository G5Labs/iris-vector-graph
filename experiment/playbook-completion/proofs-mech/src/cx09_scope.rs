//! M-09 counterexamples: for each departing variant, a run from the initial state to a violation of the law it breaks.
use vstd::prelude::*;
use crate::exec::*;
use crate::m09_scope::*;
use crate::i09_scope::*;

verus! {

pub proof fn cx_name_check_missing_l1()
    ensures ({
        let t = run::<ScopeM<NameCheckMissingAsBuilt>>(scope_s0(), seq![ScA::Write(0, 0, 2), ScA::Write(2, 0, 2)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 3);
    let t = run::<ScopeM<NameCheckMissingAsBuilt>>(scope_s0(), seq![ScA::Write(0, 0, 2), ScA::Write(2, 0, 2)])->0;
    assert(t.accepted.contains(0) && t.keys[0] == 0);
    assert(t.accepted.contains(2) && t.keys[2] == 0);
}

pub proof fn cx_all_graphs_walk_l2()
    ensures ({
        let s = run::<ScopeM<AllGraphsWalkAsBuilt>>(scope_s0(), Seq::<ScA>::empty());
        let a = ScA::Read(0, 0);
        s is Some && scope_step::<AllGraphsWalkAsBuilt>(s->0, a) is Some && !law_l2(s->0, a, scope_step::<AllGraphsWalkAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

pub proof fn cx_unscoped_read_l2()
    ensures ({
        let s = run::<ScopeM<UnscopedReadAsBuilt>>(scope_s0(), Seq::<ScA>::empty());
        let a = ScA::Read(0, 1);
        s is Some && scope_step::<UnscopedReadAsBuilt>(s->0, a) is Some && !law_l2(s->0, a, scope_step::<UnscopedReadAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

pub proof fn cx_interned_no_graph_dimension_l2()
    ensures ({
        let s = run::<ScopeM<InternedNoGraphDimensionAsBuilt>>(scope_s0(), Seq::<ScA>::empty());
        let a = ScA::Read(0, 0);
        s is Some && scope_step::<InternedNoGraphDimensionAsBuilt>(s->0, a) is Some && !law_l2(s->0, a, scope_step::<InternedNoGraphDimensionAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

pub proof fn cx_delete_every_graph_l3()
    ensures ({
        let s = run::<ScopeM<DeleteEveryGraphAsBuilt>>(scope_s0(), Seq::<ScA>::empty());
        let a = ScA::Delete(0, 0);
        s is Some && scope_step::<DeleteEveryGraphAsBuilt>(s->0, a) is Some && !law_l3(s->0, a, scope_step::<DeleteEveryGraphAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

pub proof fn cx_three_predicates_l4()
    ensures ({
        let t = run::<ScopeM<ThreePredicatesAsBuilt>>(scope_s0(), Seq::<ScA>::empty());
        t is Some && !law_l4::<ThreePredicatesAsBuilt>(t->0)
    })
{
    reveal_with_fuel(run, 1);
}

pub proof fn cx_ctl_key_ignores_name_l1()
    ensures ({
        let t = run::<ScopeM<CtlKeyIgnoresName>>(scope_s0(), seq![ScA::Write(0, 0, 2), ScA::Write(1, 0, 2)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 3);
    let t = run::<ScopeM<CtlKeyIgnoresName>>(scope_s0(), seq![ScA::Write(0, 0, 2), ScA::Write(1, 0, 2)])->0;
    assert(t.accepted.contains(0) && t.keys[0] == 0);
    assert(t.accepted.contains(1) && t.keys[1] == 0);
}

pub proof fn cx_ctl_join_across_graphs_l2()
    ensures ({
        let s = run::<ScopeM<CtlJoinAcrossGraphs>>(scope_s0(), Seq::<ScA>::empty());
        let a = ScA::Read(0, 1);
        s is Some && scope_step::<CtlJoinAcrossGraphs>(s->0, a) is Some && !law_l2(s->0, a, scope_step::<CtlJoinAcrossGraphs>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

pub proof fn cx_ctl_delete_every_graph_l3()
    ensures ({
        let s = run::<ScopeM<CtlDeleteEveryGraph>>(scope_s0(), Seq::<ScA>::empty());
        let a = ScA::Delete(0, 0);
        s is Some && scope_step::<CtlDeleteEveryGraph>(s->0, a) is Some && !law_l3(s->0, a, scope_step::<CtlDeleteEveryGraph>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 1);
}

pub proof fn cx_ctl_graph_blind_match_l4()
    ensures ({
        let t = run::<ScopeM<CtlGraphBlindMatch>>(scope_s0(), Seq::<ScA>::empty());
        t is Some && !law_l4::<CtlGraphBlindMatch>(t->0)
    })
{
    reveal_with_fuel(run, 1);
}

} // verus!
