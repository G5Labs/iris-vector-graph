// As-built transcription at 3eaa79cf. Normal changeset after admission, one graph.
// SQL/global writes share an IRIS transaction; head serialization and successful
// database statements are provider assumptions. No ObjectScript body is verified.
use vstd::prelude::*;
verus! {
pub struct Graph {
    pub nodes: Set<int>, pub labels: Set<(int,int)>,
    pub props: Map<(int,int),int>, pub rels: Map<nat,(int,int)>, pub next: nat,
}
pub enum Op { Create(int), Label(int,int), Set(int,int,int), Rel(int,int) }
pub enum Record { Create(int), Label(int,int), Set(int,int,Option<int>,int), Rel(nat,int,int) }
pub struct Applied { pub graph: Graph, pub records: Seq<Record>, pub error: Option<nat> }
pub struct Store { pub graph: Graph, pub head: nat, pub revisions: Map<nat,Seq<Record>>, pub binding: Option<nat> }
pub struct Reply { pub store: Store, pub error: Option<nat> }
pub open spec fn value(g: Graph, n: int, k: int) -> Option<int> {
    if g.props.contains_key((n,k)) { Some(g.props[(n,k)]) } else { None }
}
// Reserved keys id and __graph are abstracted as -1 and -2.
pub open spec fn fails(g: Graph, op: Op) -> bool {
    match op {
        Op::Create(n) => g.nodes.contains(n),
        Op::Label(n,_) => !g.nodes.contains(n),
        Op::Set(n,k,_) => k == -1 || k == -2 || !g.nodes.contains(n),
        Op::Rel(s,o) => !g.nodes.contains(s) || !g.nodes.contains(o)
            || exists|id:nat| g.rels.contains_key(id) && g.rels[id] == (s,o),
    }
}
pub open spec fn write(g: Graph, op: Op) -> (Graph,Seq<Record>) {
    match op {
        Op::Create(n) => (Graph { nodes:g.nodes.insert(n), ..g },seq![Record::Create(n)]),
        Op::Label(n,k) => if g.labels.contains((n,k)) { (g,seq![]) }
            else { (Graph { labels:g.labels.insert((n,k)), ..g },seq![Record::Label(n,k)]) },
        Op::Set(n,k,v) => if value(g,n,k) == Some(v) { (g,seq![]) }
            else { (Graph { props:g.props.insert((n,k),v), ..g },seq![Record::Set(n,k,value(g,n,k),v)]) },
        Op::Rel(s,o) => (Graph { rels:g.rels.insert(g.next,(s,o)), next:g.next+1, ..g },
            seq![Record::Rel(g.next,s,o)]),
    }
}
pub open spec fn apply_all(g: Graph, ops: Seq<Op>, index: nat) -> Applied
    decreases ops.len(),
{
    if ops.len() == 0 { Applied { graph:g, records:seq![], error:None } }
    else if fails(g,ops[0]) { Applied { graph:g, records:seq![], error:Some(index) } }
    else {
        let (next,records) = write(g,ops[0]);
        let rest = apply_all(next,ops.drop_first(),index+1);
        Applied { graph:rest.graph, records:records+rest.records, error:rest.error }
    }
}
pub open spec fn commit(s: Store, ops: Seq<Op>) -> Reply {
    let work = apply_all(s.graph,ops,0);
    if work.error.is_some() { Reply { store:s, error:work.error } }
    else { Reply { store: Store { graph:work.graph, head:s.head+1,
        revisions:s.revisions.insert(s.head+1,work.records), binding:Some(s.head+1) }, error:None } }
}
pub open spec fn revision(s: Store, seq: nat) -> Option<Seq<Record>> {
    if s.revisions.contains_key(seq) { Some(s.revisions[seq]) } else { None }
}
pub open spec fn empty() -> Graph {
    Graph { nodes:Set::empty(),labels:Set::empty(),props:Map::empty(),rels:Map::empty(),next:1 }
}
pub open spec fn initial() -> Store { Store { graph:empty(),head:0,revisions:Map::empty(),binding:None } }
pub proof fn theorem_failure_publishes_nothing(s: Store, ops: Seq<Op>)
    requires apply_all(s.graph,ops,0).error.is_some(),
    ensures commit(s,ops).store == s,
{}
pub proof fn theorem_two_writes_produce_priors()
    ensures ({ let r=commit(initial(),seq![Op::Create(0),Op::Set(0,0,1),Op::Set(0,0,2)]);
        r.error == None && value(r.store.graph,0,0)==Some(2)
        && revision(r.store,1)==Some(seq![Record::Create(0),Record::Set(0,0,None,1),Record::Set(0,0,Some(1),2)]) }),
{ reveal_with_fuel(apply_all,5); }
pub proof fn theorem_same_value_records_nothing(g: Graph, n:int,k:int,v:int)
    requires value(g,n,k)==Some(v),
    ensures write(g,Op::Set(n,k,v)) == (g,seq![]),
{}
pub proof fn theorem_real_endpoint_decides(g: Graph, s:int,o:int)
    requires !g.nodes.contains(o),
    ensures fails(g,Op::Rel(s,o)),
{}
pub proof fn theorem_valid_relationship_reachable()
    ensures ({ let r=commit(initial(),seq![Op::Create(0),Op::Create(1),Op::Rel(0,1)]);
        r.error==None && r.store.graph.rels.contains_key(1) && r.store.graph.rels[1]==(0,1)
        && r.store.graph.next==2 && r.store.head==1 }),
{ reveal_with_fuel(apply_all,5); }
pub proof fn theorem_mid_failure_rolls_back_prefix()
    ensures ({ let s=commit(initial(),seq![Op::Create(0),Op::Create(1),Op::Set(0,0,1)]).store;
        let r=commit(s,seq![Op::Create(2),Op::Label(0,7),Op::Set(0,0,2),Op::Rel(2,0),Op::Rel(0,99),Op::Create(3)]);
        r.error==Some(4) && r.store==s && r.store.graph.next==1 && value(r.store.graph,0,0)==Some(1)
        && !r.store.graph.nodes.contains(2) && !r.store.graph.nodes.contains(3) }),
{ reveal_with_fuel(apply_all,9); }
pub proof fn theorem_reserved_key_refuses(g:Graph,n:int)
    ensures fails(g,Op::Set(n,-1,3)), fails(g,Op::Set(n,-2,3)),
{}
pub proof fn theorem_noop_has_no_property_record()
    ensures ({ let r=commit(initial(),seq![Op::Create(0),Op::Set(0,0,1),Op::Set(0,0,1)]);
        revision(r.store,1)==Some(seq![Record::Create(0),Record::Set(0,0,None,1)]) }),
{ reveal_with_fuel(apply_all,5); }
}
