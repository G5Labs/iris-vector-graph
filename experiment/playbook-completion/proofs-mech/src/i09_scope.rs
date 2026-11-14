//! M-09 instances: one type per object variant of mechanisms.json (family `scope`, models/semantics/src/scope.rs).
//! The explorer reviews every departing object against the canonical configuration CANON: each gets its own
//! `<Name>Reviewed` type with CANON parameters.
use vstd::prelude::*;
use crate::exec::*;
use crate::m09_scope::*;

verus! {

pub open spec fn canon() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::Scoped, del: DelPol::Scoped, match_blind: false } }

/// canonical: 03/node-in-one-graph,03/edge-in-one-graph,05/temporal-coordinates,08/cypher-node,08/cypher-edge,12/graph-content (schema.py:395-402, 34-45; ADR-0001; translator.py; Eraser.cls:113-125).
pub struct ScopeCanonical;
impl ScopePolicy for ScopeCanonical { open spec fn cfg() -> ScCfg { canon() } }
impl ScopeObject for ScopeCanonical {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_scope_canonical(s0: ScS, ls: Seq<ScA>, t: ScS, a: ScA) requires reached::<ScopeM<ScopeCanonical>>(s0, ls, t)
    ensures law_l1(t), law_l4::<ScopeCanonical>(t) { theorem_scope::<ScopeCanonical>(s0, ls, t, a); }

/// name-check-missing, reviewed (CANON): 02/graph-name.
pub struct NameCheckMissingReviewed;
impl ScopePolicy for NameCheckMissingReviewed { open spec fn cfg() -> ScCfg { canon() } }
impl ScopeObject for NameCheckMissingReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_name_check_missing_reviewed(s0: ScS, ls: Seq<ScA>, t: ScS, a: ScA) requires reached::<ScopeM<NameCheckMissingReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4::<NameCheckMissingReviewed>(t) { theorem_scope::<NameCheckMissingReviewed>(s0, ls, t, a); }

/// name-check-missing: an unvalidated entry maps the name "0" onto the default graph's key (nodes_edges.py:968-1015). Objects: 02/graph-name; findings F-0202,F-0203.
pub struct NameCheckMissingAsBuilt;
impl ScopePolicy for NameCheckMissingAsBuilt { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Unvalidated, read: ReadPol::Scoped, del: DelPol::Scoped, match_blind: false } } }
pub proof fn refute_name_check_missing_l1() ensures !obl_l1::<NameCheckMissingAsBuilt>() {}
pub proof fn keep_name_check_missing_l2() ensures obl_l2::<NameCheckMissingAsBuilt>() {}
pub proof fn keep_name_check_missing_l3() ensures obl_l3::<NameCheckMissingAsBuilt>() {}
pub proof fn keep_name_check_missing_l4() ensures obl_l4::<NameCheckMissingAsBuilt>() {}

/// all-graphs-walk, reviewed (CANON): 08/graph-scope.
pub struct AllGraphsWalkReviewed;
impl ScopePolicy for AllGraphsWalkReviewed { open spec fn cfg() -> ScCfg { canon() } }
impl ScopeObject for AllGraphsWalkReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_all_graphs_walk_reviewed(s0: ScS, ls: Seq<ScA>, t: ScS, a: ScA) requires reached::<ScopeM<AllGraphsWalkReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4::<AllGraphsWalkReviewed>(t) { theorem_scope::<AllGraphsWalkReviewed>(s0, ls, t, a); }

/// all-graphs-walk: an all-graphs walk crosses graphs (translator.py:15404-15431). Objects: 08/graph-scope; findings F-0818,F-0819,F-0820.
pub struct AllGraphsWalkAsBuilt;
impl ScopePolicy for AllGraphsWalkAsBuilt { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::Merged, del: DelPol::Scoped, match_blind: false } } }
pub proof fn keep_all_graphs_walk_l1() ensures obl_l1::<AllGraphsWalkAsBuilt>() {}
pub proof fn refute_all_graphs_walk_l2() ensures !obl_l2::<AllGraphsWalkAsBuilt>() {}
pub proof fn keep_all_graphs_walk_l3() ensures obl_l3::<AllGraphsWalkAsBuilt>() {}
pub proof fn keep_all_graphs_walk_l4() ensures obl_l4::<AllGraphsWalkAsBuilt>() {}

/// unscoped-read, reviewed (CANON): 10/default-graph-algorithm-call,16/graph-a-caller-names,17/link,07/fused-search,06/route,10/native-route.
pub struct UnscopedReadReviewed;
impl ScopePolicy for UnscopedReadReviewed { open spec fn cfg() -> ScCfg { canon() } }
impl ScopeObject for UnscopedReadReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_unscoped_read_reviewed(s0: ScS, ls: Seq<ScA>, t: ScS, a: ScA) requires reached::<ScopeM<UnscopedReadReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4::<UnscopedReadReviewed>(t) { theorem_scope::<UnscopedReadReviewed>(s0, ls, t, a); }

/// unscoped-read: an id's data is taken from any graph that has it (algorithms.py:658-678 and the other cited readers). Objects: 10/default-graph-algorithm-call,16/graph-a-caller-names,17/link,07/fused-search,06/route,10/native-route; findings F-1002,F-1006,F-1008,F-1013,F-1001,F-1603,F-1604,F-1701,F-0609,F-0711,F-0605,F-0616.
pub struct UnscopedReadAsBuilt;
impl ScopePolicy for UnscopedReadAsBuilt { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::JoinAny, del: DelPol::Scoped, match_blind: false } } }
pub proof fn keep_unscoped_read_l1() ensures obl_l1::<UnscopedReadAsBuilt>() {}
pub proof fn refute_unscoped_read_l2() ensures !obl_l2::<UnscopedReadAsBuilt>() {}
pub proof fn keep_unscoped_read_l3() ensures obl_l3::<UnscopedReadAsBuilt>() {}
pub proof fn keep_unscoped_read_l4() ensures obl_l4::<UnscopedReadAsBuilt>() {}

/// interned-no-graph-dimension, reviewed (CANON): 10/interned-snapshot.
pub struct InternedNoGraphDimensionReviewed;
impl ScopePolicy for InternedNoGraphDimensionReviewed { open spec fn cfg() -> ScCfg { canon() } }
impl ScopeObject for InternedNoGraphDimensionReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_interned_no_graph_dimension_reviewed(s0: ScS, ls: Seq<ScA>, t: ScS, a: ScA) requires reached::<ScopeM<InternedNoGraphDimensionReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4::<InternedNoGraphDimensionReviewed>(t) { theorem_scope::<InternedNoGraphDimensionReviewed>(s0, ls, t, a); }

/// interned-no-graph-dimension: the interned snapshot has no graph dimension (documented exception EXC-06, CONTEXT.md:97-102). Objects: 10/interned-snapshot.
pub struct InternedNoGraphDimensionAsBuilt;
impl ScopePolicy for InternedNoGraphDimensionAsBuilt { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::Merged, del: DelPol::Scoped, match_blind: false } } }
pub proof fn keep_interned_no_graph_dimension_l1() ensures obl_l1::<InternedNoGraphDimensionAsBuilt>() {}
pub proof fn refute_interned_no_graph_dimension_l2() ensures !obl_l2::<InternedNoGraphDimensionAsBuilt>() {}
pub proof fn keep_interned_no_graph_dimension_l3() ensures obl_l3::<InternedNoGraphDimensionAsBuilt>() {}
pub proof fn keep_interned_no_graph_dimension_l4() ensures obl_l4::<InternedNoGraphDimensionAsBuilt>() {}

/// delete-every-graph, reviewed (CANON): 15/reifier.
pub struct DeleteEveryGraphReviewed;
impl ScopePolicy for DeleteEveryGraphReviewed { open spec fn cfg() -> ScCfg { canon() } }
impl ScopeObject for DeleteEveryGraphReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_delete_every_graph_reviewed(s0: ScS, ls: Seq<ScA>, t: ScS, a: ScA) requires reached::<ScopeM<DeleteEveryGraphReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4::<DeleteEveryGraphReviewed>(t) { theorem_scope::<DeleteEveryGraphReviewed>(s0, ls, t, a); }

/// delete-every-graph: a reifier delete removes the id in every graph (schema.py:3361-3397). Objects: 15/reifier; findings F-1503.
pub struct DeleteEveryGraphAsBuilt;
impl ScopePolicy for DeleteEveryGraphAsBuilt { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::Scoped, del: DelPol::EveryGraph, match_blind: false } } }
pub proof fn keep_delete_every_graph_l1() ensures obl_l1::<DeleteEveryGraphAsBuilt>() {}
pub proof fn keep_delete_every_graph_l2() ensures obl_l2::<DeleteEveryGraphAsBuilt>() {}
pub proof fn refute_delete_every_graph_l3() ensures !obl_l3::<DeleteEveryGraphAsBuilt>() {}
pub proof fn keep_delete_every_graph_l4() ensures obl_l4::<DeleteEveryGraphAsBuilt>() {}

/// three-predicates, reviewed (CANON): 13/redaction-target,11/node-id.
pub struct ThreePredicatesReviewed;
impl ScopePolicy for ThreePredicatesReviewed { open spec fn cfg() -> ScCfg { canon() } }
impl ScopeObject for ThreePredicatesReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}
pub proof fn laws_three_predicates_reviewed(s0: ScS, ls: Seq<ScA>, t: ScS, a: ScA) requires reached::<ScopeM<ThreePredicatesReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4::<ThreePredicatesReviewed>(t) { theorem_scope::<ThreePredicatesReviewed>(s0, ls, t, a); }

/// three-predicates: node records are graph-blind, so the record match differs from erase and liveness (LedgerRedact.cls:89-178, LedgerApply.cls:79-84). Objects: 13/redaction-target,11/node-id; findings F-1304,F-1305,F-1105,F-1401.
pub struct ThreePredicatesAsBuilt;
impl ScopePolicy for ThreePredicatesAsBuilt { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::Scoped, del: DelPol::Scoped, match_blind: true } } }
pub proof fn keep_three_predicates_l1() ensures obl_l1::<ThreePredicatesAsBuilt>() {}
pub proof fn keep_three_predicates_l2() ensures obl_l2::<ThreePredicatesAsBuilt>() {}
pub proof fn keep_three_predicates_l3() ensures obl_l3::<ThreePredicatesAsBuilt>() {}
pub proof fn refute_three_predicates_l4() ensures !obl_l4::<ThreePredicatesAsBuilt>() {}

/// mutant (scope-control-C1-key-ignores-name): the key ignores the name.
pub struct CtlKeyIgnoresName;
impl ScopePolicy for CtlKeyIgnoresName { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::IgnoresName, read: ReadPol::Scoped, del: DelPol::Scoped, match_blind: false } } }
pub proof fn refute_ctl_key_ignores_name_l1() ensures !obl_l1::<CtlKeyIgnoresName>() {}
pub proof fn keep_ctl_key_ignores_name_l2() ensures obl_l2::<CtlKeyIgnoresName>() {}
pub proof fn keep_ctl_key_ignores_name_l3() ensures obl_l3::<CtlKeyIgnoresName>() {}
pub proof fn keep_ctl_key_ignores_name_l4() ensures obl_l4::<CtlKeyIgnoresName>() {}

/// mutant (scope-control-C2-join-across-graphs): a read joins across graphs.
pub struct CtlJoinAcrossGraphs;
impl ScopePolicy for CtlJoinAcrossGraphs { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::JoinAny, del: DelPol::Scoped, match_blind: false } } }
pub proof fn keep_ctl_join_across_graphs_l1() ensures obl_l1::<CtlJoinAcrossGraphs>() {}
pub proof fn refute_ctl_join_across_graphs_l2() ensures !obl_l2::<CtlJoinAcrossGraphs>() {}
pub proof fn keep_ctl_join_across_graphs_l3() ensures obl_l3::<CtlJoinAcrossGraphs>() {}
pub proof fn keep_ctl_join_across_graphs_l4() ensures obl_l4::<CtlJoinAcrossGraphs>() {}

/// mutant (scope-control-C3-delete-every-graph): a delete removes the id in every graph.
pub struct CtlDeleteEveryGraph;
impl ScopePolicy for CtlDeleteEveryGraph { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::Scoped, del: DelPol::EveryGraph, match_blind: false } } }
pub proof fn keep_ctl_delete_every_graph_l1() ensures obl_l1::<CtlDeleteEveryGraph>() {}
pub proof fn keep_ctl_delete_every_graph_l2() ensures obl_l2::<CtlDeleteEveryGraph>() {}
pub proof fn refute_ctl_delete_every_graph_l3() ensures !obl_l3::<CtlDeleteEveryGraph>() {}
pub proof fn keep_ctl_delete_every_graph_l4() ensures obl_l4::<CtlDeleteEveryGraph>() {}

/// mutant (scope-control-C4-graph-blind-match): the record match is graph-blind.
pub struct CtlGraphBlindMatch;
impl ScopePolicy for CtlGraphBlindMatch { open spec fn cfg() -> ScCfg { ScCfg { key: KeyPol::Validated, read: ReadPol::Scoped, del: DelPol::Scoped, match_blind: true } } }
pub proof fn keep_ctl_graph_blind_match_l1() ensures obl_l1::<CtlGraphBlindMatch>() {}
pub proof fn keep_ctl_graph_blind_match_l2() ensures obl_l2::<CtlGraphBlindMatch>() {}
pub proof fn keep_ctl_graph_blind_match_l3() ensures obl_l3::<CtlGraphBlindMatch>() {}
pub proof fn refute_ctl_graph_blind_match_l4() ensures !obl_l4::<CtlGraphBlindMatch>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// scope-sharp-same-id-two-graphs-differ: one id live in both graphs with different values.
pub proof fn sharp_same_id_two_graphs_differ()
    ensures ({
        let t = run::<ScopeM<ScopeCanonical>>(scope_s0(), seq![ScA::Write(0, 1, 2)]);
        t is Some && cell(t->0, 0, 1) != 0 && cell(t->0, 1, 1) != 0 && cell(t->0, 0, 1) != cell(t->0, 1, 1)
    })
{
    reveal_with_fuel(run, 2);
}

/// scope-sharp-named-write: a write is accepted under the named graph.
pub proof fn sharp_named_write()
    ensures ({
        let t = run::<ScopeM<ScopeCanonical>>(scope_s0(), seq![ScA::Write(1, 0, 2)]);
        t is Some && t->0.accepted.contains(1)
    })
{
    reveal_with_fuel(run, 2);
}

} // verus!
