// product 3eaa79cf: algorithm options through the engine method and Cypher CALL ivg.*.
//   iris_vector_graph/_validate.py: DegreeCentralityInput .. KCoreInput :243-288, validate_procedure_options :291-317.
//   cypher/translator.py: CENTRALITY_ALLOWED_KEYS / COMMUNITY_ALLOWED_KEYS :105-120, _validate_centrality_proc_map
//   :123-136, _validate_community_proc_map :326-339, _PROCEDURE_OPTION_FIELDS :140-157, _procedure_options :160-180,
//   _procedure_direction :3468-3473. Engine methods: _engine/algorithms.py degree_centrality :1051 .. k_core :1764,
//   each building its model from its keyword arguments.
// Provider premise: pydantic's lax coercion of a value to an integer (a string "2", 2.0 and true accepted; 2.5 refused)
// is the same on both paths; it is an uninterpreted `coerce`. Float options (gamma, tol) are outside this model and
// checked natively by the binding.
use vstd::prelude::*;
verus! {
pub enum Proc {Degree,Betweenness,Closeness,Eigenvector,Leiden,Triangle,Scc,KCore}
pub enum Opt {TopK,MaxHops,SampleSize,MaxIter,MaxLevels,MemBudget,RandomSeed,Direction,Formula,Predicate,Gamma,Tol,Other}
pub enum Word {Out,In,Both,Harmonic,Classical,Else}
pub enum Val {Num(int),Text(Word),Unparsed}
pub uninterp spec fn coerce(v:Val)->Option<int>;
/// The options each procedure lists (the allowed-key sets) — the same names as the field map and the method keywords.
pub open spec fn listed(p:Proc,o:Opt)->bool {
 match p {
  Proc::Degree=>o==Opt::Direction||o==Opt::Predicate||o==Opt::TopK,
  Proc::Betweenness=>o==Opt::SampleSize||o==Opt::Direction||o==Opt::MaxHops||o==Opt::TopK||o==Opt::MemBudget,
  Proc::Closeness=>o==Opt::Formula||o==Opt::Direction||o==Opt::MaxHops||o==Opt::TopK,
  Proc::Eigenvector=>o==Opt::MaxIter||o==Opt::Tol||o==Opt::TopK,
  Proc::Leiden=>o==Opt::MaxLevels||o==Opt::Gamma||o==Opt::Tol||o==Opt::TopK||o==Opt::MemBudget||o==Opt::RandomSeed,
  _=>o==Opt::TopK,
 }
}
/// The method's keyword arguments (transcribed from the signatures).
pub open spec fn keyword(p:Proc,o:Opt)->bool {listed(p,o)}
pub open spec fn in_range(o:Opt,n:int)->bool {
 match o {
  Opt::TopK=>0<=n<=1_000_000, Opt::MaxHops=>0<=n<=1000, Opt::SampleSize=>0<=n<=1_000_000,
  Opt::MaxIter=>1<=n<=1000, Opt::MaxLevels=>1<=n<=100, Opt::MemBudget=>16<=n<=8192,
  Opt::RandomSeed=>0<=n<=4294967295, _=>false,
 }
}
/// The model's decision on one option value (the same model on both paths).
pub open spec fn model_ok(o:Opt,v:Val)->bool {
 match o {
  Opt::Direction=>v==Val::Text(Word::Out)||v==Val::Text(Word::In)||v==Val::Text(Word::Both),
  Opt::Formula=>v==Val::Text(Word::Harmonic)||v==Val::Text(Word::Classical),
  Opt::Predicate=>true,
  _=>match coerce(v) {Some(n)=>in_range(o,n),None=>false},
 }
}
/// Engine method: an unknown keyword is a TypeError; otherwise the model decides.
pub open spec fn python_accepts(p:Proc,o:Opt,v:Val)->bool {keyword(p,o) && model_ok(o,v)}
/// Cypher: an unlisted key is a ValueError naming the allowed keys; direction is checked first by the same three
/// values; then the same model decides.
pub open spec fn cypher_direction_ok(o:Opt,v:Val)->bool {
 o!=Opt::Direction || v==Val::Text(Word::Out)||v==Val::Text(Word::In)||v==Val::Text(Word::Both)
}
pub open spec fn cypher_accepts(p:Proc,o:Opt,v:Val)->bool {listed(p,o) && cypher_direction_ok(o,v) && model_ok(o,v)}

/// The documented promise: the Cypher form takes the same values, in the same range, as the method.
pub proof fn theorem_same_decision(p:Proc,o:Opt,v:Val)
 ensures cypher_accepts(p,o,v)==python_accepts(p,o,v),
{}
/// An option a procedure does not list is refused on both paths.
pub proof fn theorem_unlisted_refused(p:Proc,v:Val)
 ensures !cypher_accepts(p,Opt::Other,v),!python_accepts(p,Opt::Other,v),
{}
/// Ranges: topK 0 (all rows) is accepted and -1 refused; maxIter 1..1000; maxHops 0..1000; memBudgetMB from 16.
pub proof fn theorem_ranges(p:Proc,v:Val,w:Val,x:Val,y:Val)
 requires coerce(v)==Some(0int),coerce(w)==Some(-1int),coerce(x)==Some(1000int),coerce(y)==Some(1001int)
 ensures model_ok(Opt::TopK,v),!model_ok(Opt::TopK,w),model_ok(Opt::MaxIter,x),!model_ok(Opt::MaxIter,y),
  model_ok(Opt::MaxHops,v),!model_ok(Opt::MaxHops,y),!model_ok(Opt::MemBudget,v),
{}
/// A value the coercion refuses (2.5) is refused for every numeric option.
pub proof fn theorem_uncoercible_refused(o:Opt,v:Val)
 requires coerce(v).is_none(),o!=Opt::Direction,o!=Opt::Formula,o!=Opt::Predicate
 ensures !model_ok(o,v),
{}
/// Enumerations are exact: "OUT" and "Classical" are refused.
pub proof fn theorem_enumerations_exact()
 ensures !model_ok(Opt::Direction,Val::Text(Word::Else)),!model_ok(Opt::Formula,Val::Text(Word::Else)),
  model_ok(Opt::Formula,Val::Text(Word::Classical)),
{}
}
