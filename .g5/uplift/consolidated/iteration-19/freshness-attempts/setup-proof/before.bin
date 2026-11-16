// product 3eaa79cf: the schema-record decision and write order of initialize_schema across a namespace's lifecycle.
//   iris_vector_graph/_engine/schema.py SchemaMixin.initialize_schema :2097-2160, _record_and_initialize :2198-2300.
use vstd::prelude::*;
verus! {
pub type Schema=int;
/// The namespace as setup sees it: the recorded IVG Schema (^IVG.Deploy("schema")) and the schemas holding IVG tables.
pub struct Ns {pub recorded:Option<Schema>,pub held:Set<Schema>}
pub enum How {New,Existing,Inferred,Explicit}
pub enum Outcome {Refused,Report(How)}
pub open spec fn others(ns:Ns,t:Schema)->Set<Schema> {ns.held.remove(t)}
/// _record_and_initialize's record transitions (data-model.md).
pub open spec fn decide(ns:Ns,t:Schema,explicit:bool)->Outcome {
 match ns.recorded {
  Some(s)=>if s!=t {Outcome::Refused} else {Outcome::Report(How::Existing)},
  None=>if ns.held.is_empty() {Outcome::Report(How::New)}
   else if others(ns,t).is_empty() {Outcome::Report(How::Inferred)}
   else if explicit {Outcome::Report(How::Explicit)} else {Outcome::Refused},
 }
}
/// A dry run, or a refusal, writes nothing; a real run creates this schema's tables and records it last.
pub open spec fn setup(ns:Ns,t:Schema,explicit:bool,dry:bool)->Ns {
 if dry || decide(ns,t,explicit)==Outcome::Refused {ns} else {Ns{recorded:Some(t),held:ns.held.insert(t)}}
}
/// A real run stopped after creating the tables and before the record (the record is the last write).
pub open spec fn interrupted(ns:Ns,t:Schema)->Ns {Ns{recorded:ns.recorded,held:ns.held.insert(t)}}
pub open spec fn fresh()->Ns {Ns{recorded:None,held:Set::empty()}}

pub proof fn theorem_dry_run_writes_nothing(ns:Ns,t:Schema,e:bool) ensures setup(ns,t,e,true)==ns {}
pub proof fn theorem_refusal_writes_nothing(ns:Ns,t:Schema,e:bool)
 requires decide(ns,t,e)==Outcome::Refused ensures setup(ns,t,e,false)==ns {}
pub proof fn theorem_fresh_namespace_is_new_and_recorded(t:Schema)
 ensures decide(fresh(),t,false)==Outcome::Report(How::New),setup(fresh(),t,false,false)==(Ns{recorded:Some(t),held:set![t]}),
{assert(Set::<Schema>::empty().insert(t)=~=set![t]);}
pub proof fn theorem_second_run_existing_and_unchanged(ns:Ns,t:Schema,e:bool)
 requires decide(ns,t,e)!=Outcome::Refused
 ensures decide(setup(ns,t,e,false),t,e)==Outcome::Report(How::Existing),
  setup(setup(ns,t,e,false),t,e,false)==setup(ns,t,e,false),
{let n1=setup(ns,t,e,false);assert(n1.held.insert(t)=~=n1.held);}
/// A record naming another schema refuses the engine before anything is written.
pub proof fn theorem_mismatch_refused(s:Schema,t:Schema,h:Set<Schema>,e:bool)
 requires s!=t ensures decide(Ns{recorded:Some(s),held:h},t,e)==Outcome::Refused,setup(Ns{recorded:Some(s),held:h},t,e,false)==(Ns{recorded:Some(s),held:h}) {}
/// An interrupted setup is inferred on the next run and ends where an uninterrupted run ends.
pub proof fn theorem_interrupted_setup_resumes(t:Schema)
 ensures decide(interrupted(fresh(),t),t,false)==Outcome::Report(How::Inferred),
  setup(interrupted(fresh(),t),t,false,false)==setup(fresh(),t,false,false),
{
 let i=interrupted(fresh(),t);assert(i.held=~=set![t]);assert(i.held.contains(t));assert(!i.held.is_empty());
 assert(others(i,t)=~=Set::<Schema>::empty());assert(i.held.insert(t)=~=set![t]);
 assert(Set::<Schema>::empty().insert(t)=~=set![t]);
}
/// Tables in another schema: refused unless the caller named this schema, then recorded as explicit.
pub proof fn theorem_other_schema_needs_a_name(o:Schema,t:Schema)
 requires o!=t
 ensures decide(Ns{recorded:None,held:set![o]},t,false)==Outcome::Refused,
  decide(Ns{recorded:None,held:set![o]},t,true)==Outcome::Report(How::Explicit),
  setup(Ns{recorded:None,held:set![o]},t,true,false)==(Ns{recorded:Some(t),held:set![o,t]}),
{
 let n=Ns{recorded:None,held:set![o]};assert(n.held.contains(o));assert(!n.held.is_empty());
 assert(others(n,t).contains(o));assert(!others(n,t).is_empty());assert(n.held.insert(t)=~=set![o,t]);
}
}
