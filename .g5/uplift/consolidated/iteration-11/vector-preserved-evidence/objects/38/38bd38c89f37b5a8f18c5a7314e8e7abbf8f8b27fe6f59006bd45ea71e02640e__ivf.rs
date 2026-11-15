// Separate IVF admission. Clustering/native methods are explicit providers, effects survive failures.
use vstd::prelude::*;
use crate::*;
use crate::workflow::{Stored,Effect,Error};
verus! {
pub struct Args {pub name:Text,pub nlist:Cell,pub batch_size:Cell,pub build_batch:Cell,pub metric:Text,pub node_ids:Option<Seq<Cell>>}
pub struct Providers {pub dependencies:Raw<()>,pub rows:Raw<Seq<Stored>>,pub cluster:Raw<()>,pub build:Raw<()>,pub adds:Seq<Raw<()>>,pub finalize:Raw<()>,pub info:Raw<Cell>}
pub struct Local {pub indexes:Map<Text,nat>,pub scopes:Map<Text,int>}
pub struct Result {pub engine:Engine,pub local:Local,pub trace:Seq<Effect>,pub error:Option<Error>,pub returned:Option<Text>}
pub open spec fn positive(c:Cell)->bool {match c{Cell::Float(n)=>n.1>0 && n.0>=n.1 && n.0%(n.1 as int)==0,_=>match dim(c){Decode::Value(Some(n))=>n>=1,_=>false}}}
pub open spec fn metric(m:Text)->bool {m==seq!['c','o','s','i','n','e'] || m==seq!['l','2'] || m==seq!['d','o','t'] || m==seq!['e','u','c','l','i','d','e','a','n']}
pub open spec fn valid(a:Args)->bool {json_width::trim(a.name).len()>0 && positive(a.nlist) && positive(a.batch_size) && positive(a.build_batch) && metric(a.metric)}
pub open spec fn raw_int(c:Cell)->Option<nat> {match c{Cell::Int(n)=>if n>=1{Some(n as nat)}else{None},Cell::Bool(true)=>Some(1),_=>None}}
pub open spec fn eligible(rows:Seq<Stored>,table:Name,g:int,ids:Option<Seq<Cell>>)->Seq<Stored> {
    rows.filter(|r:Stored|r.table==table && r.graph==g && (ids.is_none() || ids.unwrap().contains(r.id)))
}
pub open spec fn vectors(rows:Seq<Stored>)->Seq<Stored> {rows.filter(|r:Stored|!(r.emb is Null))}
pub open spec fn csv_width(r:Stored)->Option<nat> {match r.emb{Cell::Text(t)=>crate::parser::width(workflow::csv(t)),_=>None}}
pub open spec fn rectangular(rows:Seq<Stored>)->bool {rows.len()>0 && csv_width(rows[0]).is_some() && forall|i:int|0<=i<rows.len() ==> #[trigger] csv_width(rows[i])==csv_width(rows[0])}
pub open spec fn add_batches(n:nat,b:nat,i:nat,replies:Seq<Raw<()>>)->(Seq<Effect>,Option<Error>)
    recommends b>0,
    decreases if i<n{n-i}else{0},
{
    if b==0{(seq![],Some(Error::Input))}else if i>=n{(seq![],None)}else{let number=i/b;let event=Effect::AddBatch(if n-i<b{(n-i) as nat}else{b});
        if number>=replies.len() || replies[number as int] is Error{(seq![event],Some(Error::Build))}
        else{let z=add_batches(n,b,i+b,replies);(seq![event]+z.0,z.1)}}
}
pub open spec fn run(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers)->Result {
    let base=Result{engine:e,local:l,trace:seq![],error:None,returned:None};
    if !valid(a){Result{error:Some(Error::Input),..base}}else if p.dependencies is Error{Result{error:Some(Error::Provider),..base}}else{
        let route=resolve(r,e,registry);let tr=seq![Effect::Route(key(r))]+if route.engine.reads>e.reads{seq![Effect::RegistryRead(key(r))]}else{seq![]};
        let base=Result{engine:route.engine,trace:tr,..base};
        match route.selection{
            Selection::Error=>Result{error:Some(Error::Registry),..base},Selection::Empty=>Result{error:Some(Error::NoRoute),..base},
            Selection::Table{Name:table,route:_}=>{
                let base=Result{trace:base.trace+seq![Effect::Cursor],..base};
                if a.node_ids.is_some() && a.node_ids.unwrap().len()==0{Result{error:Some(Error::Input),..base}}else{
                    let base=Result{trace:base.trace+seq![Effect::IvfRead(table,graph(r))],..base};
                    match p.rows{Raw::Error(_)=>Result{error:Some(Error::Provider),..base},Raw::Rows(raw)=>{
                        let rows=eligible(raw,table,graph(r),a.node_ids);
                        if rows.len()==0{Result{error:Some(Error::NoVectors),..base}}else{
                            let vs=vectors(rows);
                            if !rectangular(vs){Result{error:Some(Error::Shape),..base}}
                            else if raw_int(a.nlist).is_none() || raw_int(a.batch_size).is_none() || p.cluster is Error{Result{error:Some(Error::Cluster),..base}}
                            else{
                                let base=Result{trace:base.trace+seq![Effect::Build(table)],..base};
                                if p.build is Error{Result{error:Some(Error::Build),..base}}
                                else if raw_int(a.build_batch).is_none(){Result{error:Some(Error::Input),..base}}
                                else{
                                    let z=add_batches(vs.len(),raw_int(a.build_batch).unwrap(),0,p.adds);let base=Result{trace:base.trace+z.0,..base};
                                    if z.1.is_some(){Result{error:z.1,..base}}else{
                                        let base=Result{trace:base.trace+seq![Effect::Finalize],..base};
                                        if p.finalize is Error{Result{error:Some(Error::Build),..base}}else{
                                            let base=Result{trace:base.trace+seq![Effect::Info],..base};
                                            match p.info{Raw::Error(_)=>Result{error:Some(Error::Info),..base},Raw::Rows(raw)=>{
                                                let text=workflow::cell_str(raw);
                                                if json_width::parsed(text).is_none(){Result{error:Some(Error::Info),..base}}else{
                                                    Result{local:Local{indexes:l.indexes.insert(a.name,1),scopes:l.scopes.insert(a.name,graph(r))},trace:base.trace+seq![Effect::Publish],returned:Some(text),..base}
                                                }
                                            }}
                                        }
                                    }
                                }
                            }
                        }
                    }}
                }
            }
        }
    }
}
pub open spec fn native(x:Effect)->bool {x is Build || x is AddBatch || x is Finalize || x is Info}
pub open spec fn no_vector_effects(t:Seq<Effect>)->bool {forall|i:int|0<=i<t.len() ==> !(t[i] is IvfRead) && !native(t[i])}
pub proof fn theorem_no_route_refuses_before_vector_read(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers)
    requires valid(a),p.dependencies is Rows,resolve(r,e,registry).selection is Empty,
    ensures run(e,l,r,registry,a,p).error==Some(Error::NoRoute),no_vector_effects(run(e,l,r,registry,a,p).trace),run(e,l,r,registry,a,p).local==l,
{}
pub proof fn theorem_empty_ids_after_cursor_before_select(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers)
    requires valid(a),p.dependencies is Rows,resolve(r,e,registry).selection is Table,a.node_ids==Some(seq![]),
    ensures run(e,l,r,registry,a,p).error==Some(Error::Input),no_vector_effects(run(e,l,r,registry,a,p).trace),run(e,l,r,registry,a,p).trace.last()==Effect::Cursor,
{}
pub proof fn theorem_all_none_vectors_are_shape_error(rows:Seq<Stored>)
    requires forall|i:int|0<=i<rows.len() ==> rows[i].emb is Null,
    ensures vectors(rows).len()==0,!rectangular(vectors(rows)),
{
    assert(rows.all(|r:Stored|r.emb is Null)) by {assert forall|i:int|0<=i<rows.len() implies (rows[i].emb is Null) by {};}
    rows.lemma_all_neg_filter_empty(|r:Stored|!(r.emb is Null));
}

pub proof fn lemma_adds_terminate_and_keep_prefix(n:nat,b:nat,i:nat,replies:Seq<Raw<()>>)
    requires b>0,
    ensures i<n ==> add_batches(n,b,i,replies).0.len()>0 && add_batches(n,b,i,replies).0[0]==Effect::AddBatch(if n-i<b{(n-i) as nat}else{b}),
{}
pub proof fn theorem_invalid_raw_batch_fails_after_build(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers,raw:Seq<Stored>,table:Name)
    requires valid(a),p.dependencies is Rows,resolve(r,e,registry).selection==(Selection::Table{Name:table,route:None}),
        a.node_ids.is_none(),p.rows==Raw::Rows(raw),eligible(raw,table,graph(r),None).len()>0,rectangular(vectors(eligible(raw,table,graph(r),None))),
        raw_int(a.nlist).is_some(),raw_int(a.batch_size).is_some(),p.cluster is Rows,p.build is Rows,raw_int(a.build_batch).is_none(),
    ensures run(e,l,r,registry,a,p).error==Some(Error::Input),run(e,l,r,registry,a,p).trace.last()==Effect::Build(table),run(e,l,r,registry,a,p).local==l,
{}
pub proof fn theorem_info_error_never_publishes(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers)
    requires p.info is Error,
    ensures run(e,l,r,registry,a,p).local==l,run(e,l,r,registry,a,p).returned.is_none(),
{}
}
