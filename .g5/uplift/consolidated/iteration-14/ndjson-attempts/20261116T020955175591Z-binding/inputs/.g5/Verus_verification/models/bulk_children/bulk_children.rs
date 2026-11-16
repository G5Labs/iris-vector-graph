// As-built modern graph-scoped SQL bulk writer at product 3eaa79cf.
// Values are stored scalar/type identities; node_read owns the numeric codec.
// A falsey admitted ID is inactive. Malformed shapes/widths are checked before this slice.
use vstd::prelude::*;
verus! {
broadcast use vstd::set_lib::group_set_lib_default;
pub type Node = (int,int); // graph, ID
pub type Child = (Node,int); // node, label/property key
pub struct Store { pub parents:Set<Node>, pub labels:Set<Child>, pub props:Map<Child,int> }
pub struct Input { pub graph:int, pub id:int, pub active:bool, pub labels:Set<int>, pub props:Map<int,Option<int>> }
pub enum GraphKey {Absent,Null,Name(int)}
pub open spec fn select_graph(key:GraphKey,keyword:int) -> int {
    match key {GraphKey::Absent=>keyword,GraphKey::Null=>0,GraphKey::Name(g)=>g}
}
pub open spec fn prepare(r:Input,key:GraphKey,keyword:int) -> Input {
    Input{graph:select_graph(key,keyword),..r}
}
pub struct Fault {pub parents:Set<Node>,pub labels:Set<Child>,pub props:Set<Child>}
pub open spec fn no_fault() -> Fault {Fault{parents:Set::empty(),labels:Set::empty(),props:Set::empty()}}
pub struct Answer { pub store:Store, pub ids:Option<Seq<int>> }
pub open spec fn node(r:Input) -> Node { (r.graph,r.id) }
// Key 0 is the id property. An explicitly supplied null omits it; absence injects the ID.
pub open spec fn offered(r:Input) -> Map<int,int> {
    Map::new(r.props.dom().filter(|k:int| r.props[k].is_some()).union(if r.props.contains_key(0) {Set::empty()} else {set![0]}),
        |k:int| if k==0 && !r.props.contains_key(0) {r.id} else {r.props[k].unwrap()})
}
pub open spec fn targets(xs:Seq<Input>) -> Set<Node>
    decreases xs.len(),
{
    if xs.len()==0 {Set::empty()} else {
        let tail=targets(xs.drop_first());
        if xs[0].active {tail.insert(node(xs[0]))} else {tail}
    }
}
// The deciding parent census is before ANY parent of the batch is inserted.
// Existing orphan labels deliberately remain; the product cleans properties only.
pub open spec fn cleanup(s:Store, wanted:Set<Node>) -> Store {
    Store{props:Map::new(s.props.dom().filter(|k:Child| !(wanted.contains(k.0) && !s.parents.contains(k.0))),
        |k:Child| s.props[k]),..s}
}
pub open spec fn add_props(old:Map<Child,int>,r:Input,reject:Fault) -> Map<Child,int> {
    let p=offered(r);
    Map::new(old.dom().union(p.dom().map_by(|k:int|(node(r),k),|k:Child|k.1).difference(reject.props)),
        |k:Child| if old.contains_key(k) {old[k]} else {p[k.1]})
}
pub open spec fn apply(s:Store,r:Input,reject:Fault) -> Store {
    if !r.active {s} else {
        Store{parents:if reject.parents.contains(node(r)) {s.parents} else {s.parents.insert(node(r))},
            labels:s.labels.union(r.labels.map_by(|k:int|(node(r),k),|k:Child|k.1).difference(reject.labels)),
            props:add_props(s.props,r,reject)}
    }
}
pub open spec fn fold(s:Store,xs:Seq<Input>,reject:Fault) -> Store
    decreases xs.len(),
{
    if xs.len()==0 {s} else {fold(apply(s,xs[0],reject),xs.drop_first(),reject)}
}
pub open spec fn returned(xs:Seq<Input>) -> Seq<int>
    decreases xs.len(),
{
    if xs.len()==0 {seq![]} else {
        if xs[0].active {seq![xs[0].id]+returned(xs.drop_first())} else {returned(xs.drop_first())}
    }
}
pub open spec fn met(s:Store,r:Input) -> bool {
    !r.active || (s.parents.contains(node(r))
        && (forall|l:int| r.labels.contains(l) ==> s.labels.contains((node(r),l)))
        && (forall|k:int| offered(r).contains_key(k) ==> s.props.contains_key((node(r),k))))
}
pub open spec fn complete(s:Store,xs:Seq<Input>) -> bool
    decreases xs.len(),
{
    xs.len()==0 || (met(s,xs[0]) && complete(s,xs.drop_first()))
}
// reject models silently skipped attempted parent/label/property INSERTs.
// Existing keys need no INSERT. No product decision is supplied as an input.
// raised models a provider exception. WriteTxn rollback is assumed faithful to the database.
pub open spec fn run(s:Store,xs:Seq<Input>,reject:Fault,raised:bool) -> Answer {
    let out=fold(cleanup(s,targets(xs)),xs,reject);
    if raised || !complete(out,xs) {Answer{store:s,ids:None}}
    else {Answer{store:out,ids:Some(returned(xs))}}
}
pub open spec fn extends(s:Store,t:Store) -> bool {
    s.parents.subset_of(t.parents) && s.labels.subset_of(t.labels)
        && (forall|k:Child| #[trigger] s.props.contains_key(k) ==> t.props.contains_key(k) && t.props[k]==s.props[k])
}
pub proof fn lemma_apply_extends(s:Store,r:Input,reject:Fault)
    ensures extends(s,apply(s,r,reject)),
{}
pub proof fn lemma_fold_extends(s:Store,xs:Seq<Input>,reject:Fault)
    ensures extends(s,fold(s,xs,reject)),
    decreases xs.len(),
{
    if xs.len()>0 {
        lemma_apply_extends(s,xs[0],reject);
        lemma_fold_extends(apply(s,xs[0],reject),xs.drop_first(),reject);
        let a=apply(s,xs[0],reject);
        let t=fold(a,xs.drop_first(),reject);
        assert(fold(s,xs,reject)==t);
        assert forall|n:Node| s.parents.contains(n) implies t.parents.contains(n) by {
            assert(a.parents.contains(n));
        }
        assert forall|k:Child| s.labels.contains(k) implies t.labels.contains(k) by {
            assert(a.labels.contains(k));
        }
        assert forall|k:Child| #[trigger] s.props.contains_key(k) implies t.props.contains_key(k) && t.props[k]==s.props[k] by {
            assert(a.props.contains_key(k));assert(a.props[k]==s.props[k]);
        }
    }
}
pub proof fn lemma_met_extends(s:Store,t:Store,r:Input)
    requires extends(s,t),met(s,r),
    ensures met(t,r),
{
    if r.active {
        assert forall|l:int| r.labels.contains(l) implies t.labels.contains((node(r),l)) by {
            assert(s.labels.contains((node(r),l)));
        }
        assert forall|k:int| offered(r).contains_key(k) implies t.props.contains_key((node(r),k)) by {
            assert(s.props.contains_key((node(r),k)));
        }
    }
}
pub proof fn lemma_fold_complete(s:Store,xs:Seq<Input>)
    ensures complete(fold(s,xs,no_fault()),xs),
    decreases xs.len(),
{
    if xs.len()>0 {
        let a=apply(s,xs[0],no_fault());
        assert(met(a,xs[0]));
        lemma_fold_extends(a,xs.drop_first(),no_fault());
        lemma_met_extends(a,fold(a,xs.drop_first(),no_fault()),xs[0]);
        lemma_fold_complete(a,xs.drop_first());
    }
}
pub proof fn theorem_no_refusal_returns_in_order(s:Store,xs:Seq<Input>)
    ensures run(s,xs,no_fault(),false).ids==Some(returned(xs)),
{
    lemma_fold_complete(cleanup(s,targets(xs)),xs);
}
pub proof fn theorem_existing_value_wins(s:Store,r:Input,k:int)
    requires r.active,s.parents.contains(node(r)),s.props.contains_key((node(r),k)),
    ensures run(s,seq![r],no_fault(),false).store.props.contains_key((node(r),k)),
        run(s,seq![r],no_fault(),false).store.props[(node(r),k)]==s.props[(node(r),k)],
{
    theorem_no_refusal_returns_in_order(s,seq![r]);
    reveal_with_fuel(fold,2);reveal_with_fuel(targets,2);
}
pub proof fn theorem_missing_value_inserted(s:Store,r:Input,k:int)
    requires r.active,!s.props.contains_key((node(r),k)),offered(r).contains_key(k),
    ensures run(s,seq![r],no_fault(),false).store.props.contains_key((node(r),k)),
        run(s,seq![r],no_fault(),false).store.props[(node(r),k)]==offered(r)[k],
{
    theorem_no_refusal_returns_in_order(s,seq![r]);
    reveal_with_fuel(fold,2);reveal_with_fuel(targets,2);
}
pub proof fn theorem_orphan_value_replaced(s:Store,r:Input,k:int)
    requires r.active,!s.parents.contains(node(r)),offered(r).contains_key(k),
    ensures run(s,seq![r],no_fault(),false).store.props.contains_key((node(r),k)),
        run(s,seq![r],no_fault(),false).store.props[(node(r),k)]==offered(r)[k],
{
    theorem_no_refusal_returns_in_order(s,seq![r]);
    reveal_with_fuel(fold,2);reveal_with_fuel(targets,2);
}
pub proof fn theorem_orphan_unoffered_value_removed(s:Store,r:Input,k:int)
    requires r.active,!s.parents.contains(node(r)),!offered(r).contains_key(k),
    ensures !run(s,seq![r],no_fault(),false).store.props.contains_key((node(r),k)),
{
    theorem_no_refusal_returns_in_order(s,seq![r]);
    reveal_with_fuel(fold,2);reveal_with_fuel(targets,2);
}
pub proof fn theorem_existing_and_incoming_labels_union(s:Store,r:Input,l:int)
    requires r.active,s.labels.contains((node(r),l)) || r.labels.contains(l),
    ensures run(s,seq![r],no_fault(),false).store.labels.contains((node(r),l)),
{
    theorem_no_refusal_returns_in_order(s,seq![r]);reveal_with_fuel(fold,2);
}
pub proof fn theorem_repeated_id_first_property_wins(s:Store,a:Input,b:Input,k:int)
    requires a.active,b.active,node(a)==node(b),!s.parents.contains(node(a)),offered(a).contains_key(k),
    ensures run(s,seq![a,b],no_fault(),false).store.props[(node(a),k)]==offered(a)[k],
        run(s,seq![a,b],no_fault(),false).ids==Some(seq![a.id,b.id]),
{
    theorem_no_refusal_returns_in_order(s,seq![a,b]);
    reveal_with_fuel(fold,3);reveal_with_fuel(targets,3);reveal_with_fuel(returned,3);
}
pub proof fn theorem_other_graph_frame(s:Store,r:Input,n:Node,k:int)
    requires n.0!=r.graph,
    ensures run(s,seq![r],no_fault(),false).store.parents.contains(n)==s.parents.contains(n),
        run(s,seq![r],no_fault(),false).store.labels.contains((n,k))==s.labels.contains((n,k)),
        run(s,seq![r],no_fault(),false).store.props.contains_key((n,k))==s.props.contains_key((n,k)),
        s.props.contains_key((n,k)) ==> run(s,seq![r],no_fault(),false).store.props[(n,k)]==s.props[(n,k)],
{
    theorem_no_refusal_returns_in_order(s,seq![r]);
    reveal_with_fuel(fold,2);reveal_with_fuel(targets,2);
}
pub proof fn theorem_unrequested_node_frame(s:Store,r:Input,n:Node,k:int)
    requires n!=node(r),
    ensures run(s,seq![r],no_fault(),false).store.parents.contains(n)==s.parents.contains(n),
        run(s,seq![r],no_fault(),false).store.labels.contains((n,k))==s.labels.contains((n,k)),
        run(s,seq![r],no_fault(),false).store.props.contains_key((n,k))==s.props.contains_key((n,k)),
        s.props.contains_key((n,k)) ==> run(s,seq![r],no_fault(),false).store.props[(n,k)]==s.props[(n,k)],
{
    theorem_no_refusal_returns_in_order(s,seq![r]);
    reveal_with_fuel(fold,2);reveal_with_fuel(targets,2);
}
pub proof fn theorem_node_graph_key_wins(r:Input,g:int,keyword:int)
    ensures node(prepare(r,GraphKey::Name(g),keyword)).0==g,
        node(prepare(r,GraphKey::Null,keyword)).0==0,
        node(prepare(r,GraphKey::Absent,keyword)).0==keyword,
{}
pub proof fn theorem_null_omitted_and_default_id(r:Input,k:int)
    requires r.props.contains_key(k),r.props[k].is_none(),
    ensures !offered(r).contains_key(k),
        !r.props.contains_key(0) ==> offered(r).contains_key(0) && offered(r)[0]==r.id,
{}
pub proof fn theorem_missing_attempted_property_rolls_back(s:Store,r:Input,k:int)
    requires r.active,offered(r).contains_key(k),
        !s.props.contains_key((node(r),k)),
    ensures run(s,seq![r],Fault{props:set![(node(r),k)],..no_fault()},false).ids.is_none(),
        run(s,seq![r],Fault{props:set![(node(r),k)],..no_fault()},false).store==s,
{
    reveal_with_fuel(fold,2);reveal_with_fuel(targets,2);
    assert(!fold(cleanup(s,targets(seq![r])),seq![r],Fault{props:set![(node(r),k)],..no_fault()}).props.contains_key((node(r),k)));
}
pub proof fn theorem_raised_failure_rolls_back(s:Store,xs:Seq<Input>,reject:Fault)
    ensures run(s,xs,reject,true).ids.is_none(),run(s,xs,reject,true).store==s,
{}
pub proof fn theorem_missing_attempted_label_rolls_back(s:Store,r:Input,l:int)
    requires r.active,r.labels.contains(l),!s.labels.contains((node(r),l)),
    ensures run(s,seq![r],Fault{labels:set![(node(r),l)],..no_fault()},false).ids.is_none(),
        run(s,seq![r],Fault{labels:set![(node(r),l)],..no_fault()},false).store==s,
{
    reveal_with_fuel(fold,2);
    assert(!fold(cleanup(s,targets(seq![r])),seq![r],Fault{labels:set![(node(r),l)],..no_fault()}).labels.contains((node(r),l)));
}
pub proof fn theorem_missing_parent_rolls_back(s:Store,r:Input)
    requires r.active,!s.parents.contains(node(r)),
    ensures run(s,seq![r],Fault{parents:set![node(r)],..no_fault()},false).ids.is_none(),
        run(s,seq![r],Fault{parents:set![node(r)],..no_fault()},false).store==s,
{
    reveal_with_fuel(fold,2);
}

// The actual reader has no ORDER BY. It folds a provider ordering of all property
// keys, deriving values from storage. Valid orders name each stored key exactly once.
// Alias collisions remain representable, rather than excluded from the model.
pub open spec fn alias(k:int) -> int {if k==0 {2} else if k==1 {3} else {k}}
pub open spec fn read_props(p:Map<Child,int>,n:Node,keys:Seq<int>) -> Map<int,int>
    decreases keys.len(),
{
    if keys.len()==0 {Map::empty()} else {
        let tail=read_props(p,n,keys.drop_last());
        let k=keys.last();
        if p.contains_key((n,k)) {tail.insert(alias(k),p[(n,k)])} else {tail}
    }
}
pub open spec fn reader_order(p:Map<Child,int>,n:Node,keys:Seq<int>) -> bool {
    keys.no_duplicates() && (forall|k:int| keys.contains(k) <==> p.contains_key((n,k)))
}
pub struct Read {pub present:bool,pub id:int,pub labels:Set<int>,pub props:Map<int,int>}
pub open spec fn read(s:Store,n:Node,keys:Seq<int>) -> Read {
    Read{present:s.parents.contains(n) || (exists|k:int| s.labels.contains((n,k)))
        || (exists|k:int| s.props.contains_key((n,k))),id:n.1,
        labels:s.labels.filter(|k:Child|k.0==n).map_by(|k:Child|k.1,|l:int|(n,l)),props:read_props(s.props,n,keys)}
}
pub proof fn theorem_reader_uses_own_graph(s:Store,n:Node,k:int)
    requires s.props.contains_key((n,k)),
    ensures read(s,n,seq![k]).props[alias(k)]==s.props[(n,k)],read(s,n,seq![k]).present,
{
    reveal_with_fuel(read_props,2);
}
pub proof fn lemma_read_complete_key(p:Map<Child,int>,n:Node,keys:Seq<int>,k:int)
    requires keys.contains(k),p.contains_key((n,k)),
        forall|j:int| keys.contains(j) && p.contains_key((n,j)) && alias(j)==alias(k) ==> j==k,
    ensures read_props(p,n,keys).contains_key(alias(k)),read_props(p,n,keys)[alias(k)]==p[(n,k)],
    decreases keys.len(),
{
    assert(keys.len()>0);
    if keys.last()!=k {
        let i=choose|i:int| 0<=i<keys.len() && keys[i]==k;
        assert(i<keys.len()-1);
        assert(keys.drop_last()[i]==k);
        assert(keys.drop_last().contains(k));
        assert forall|j:int| keys.drop_last().contains(j) && p.contains_key((n,j)) && alias(j)==alias(k) implies j==k by {
            assert(keys.contains(j));
        }
        lemma_read_complete_key(p,n,keys.drop_last(),k);
    }
}
pub proof fn theorem_orphan_replacement_reaches_reader(s:Store,r:Input,k:int)
    requires r.active,!s.parents.contains(node(r)),offered(r).contains_key(k),
    ensures read(run(s,seq![r],no_fault(),false).store,node(r),seq![k]).props[alias(k)]==offered(r)[k],
{
    theorem_orphan_value_replaced(s,r,k);
    theorem_reader_uses_own_graph(run(s,seq![r],no_fault(),false).store,node(r),k);
}
pub proof fn theorem_orphan_reaches_complete_reader(s:Store,r:Input,k:int,keys:Seq<int>)
    requires r.active,!s.parents.contains(node(r)),offered(r).contains_key(k),
        reader_order(run(s,seq![r],no_fault(),false).store.props,node(r),keys),
        forall|j:int| run(s,seq![r],no_fault(),false).store.props.contains_key((node(r),j)) && alias(j)==alias(k) ==> j==k,
    ensures read(run(s,seq![r],no_fault(),false).store,node(r),keys).props[alias(k)]==offered(r)[k],
{
    theorem_orphan_value_replaced(s,r,k);
    let p=run(s,seq![r],no_fault(),false).store.props;
    assert(keys.contains(k));
    assert forall|j:int| keys.contains(j) && p.contains_key((node(r),j)) && alias(j)==alias(k) implies j==k by {}
    lemma_read_complete_key(p,node(r),keys,k);
}
pub proof fn theorem_existing_reaches_complete_reader(s:Store,r:Input,k:int,keys:Seq<int>)
    requires r.active,s.parents.contains(node(r)),s.props.contains_key((node(r),k)),
        reader_order(run(s,seq![r],no_fault(),false).store.props,node(r),keys),
        forall|j:int| run(s,seq![r],no_fault(),false).store.props.contains_key((node(r),j)) && alias(j)==alias(k) ==> j==k,
    ensures read(run(s,seq![r],no_fault(),false).store,node(r),keys).props[alias(k)]==s.props[(node(r),k)],
{
    theorem_existing_value_wins(s,r,k);
    let p=run(s,seq![r],no_fault(),false).store.props;
    assert(keys.contains(k));
    assert forall|j:int| keys.contains(j) && p.contains_key((node(r),j)) && alias(j)==alias(k) implies j==k by {}
    lemma_read_complete_key(p,node(r),keys,k);
}
pub proof fn witness_alias_row_order_can_change_result(n:Node,a:int,b:int)
    requires a!=b,
    ensures read_props(map![(n,0)=>a,(n,2)=>b],n,seq![0,2])[2]==b,
        read_props(map![(n,0)=>a,(n,2)=>b],n,seq![2,0])[2]==a,
{
    reveal_with_fuel(read_props,3);
}
}
