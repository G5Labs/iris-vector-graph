use vstd::prelude::*;
use vstd::seq_lib::*;
#[path="parser.rs"] pub mod parser;
#[path="json_width.rs"] pub mod json_width;
#[path="catalog.rs"] pub mod catalog;
#[path="workflow.rs"] pub mod workflow;
#[path="ivf.rs"] pub mod ivf;
#[path="numbers.rs"] pub mod numbers;
verus! {
pub type Text=parser::Text;
// SQL identifiers and normalized graph/model keys are opaque atoms, not selected-route inputs.
pub type Name=nat;
pub type Key=(Name,int,Option<int>,nat); // registry/schema, graph, model, kind
pub type Number=(int,nat); // finite native number as exact rational; denominator>0
pub enum Cell {Null,Int(int),Float(Number),Bool(bool),Text(Text),Name(Name)}
pub struct Row {pub graph:int,pub model:Option<int>,pub kind:Option<nat>,pub cols:Seq<Cell>}
pub struct Fault {pub code:Option<int>,pub message:Text}
pub enum Raw<T> {Rows(T),Error(Fault)}
pub enum Decode<T> {Value(T),Error}
pub struct Route {pub table:Option<Name>,pub width:Option<int>,pub dtype:Cell}
pub struct Cached {pub route:Route,pub at:int}
pub struct Engine {pub cache:Map<Key,Cached>,pub reads:nat}
pub struct Request {pub registry:Name,pub graph:Option<int>,pub model:Option<int>,pub kind:nat,pub now:int,pub write_at:int,pub ttl:int}
pub enum Selection {Table{Name:Name,route:Option<Route>},Empty,Error}
pub struct Resolved {pub engine:Engine,pub selection:Selection}
pub open spec fn graph(r:Request)->int {r.graph.unwrap_or(0)}
pub open spec fn key(r:Request)->Key {(r.registry,graph(r),r.model,r.kind)}
pub open spec fn truthy(c:Cell)->bool {match c{Cell::Null=>false,Cell::Int(n)=>n!=0,Cell::Float(n)=>n.0!=0,Cell::Bool(b)=>b,Cell::Text(t)=>t.len()>0,Cell::Name(_)=>true}}
pub open spec fn upper(c:char)->char {match c{'a'=>'A','b'=>'B','c'=>'C','d'=>'D','e'=>'E','f'=>'F','g'=>'G','h'=>'H','i'=>'I','j'=>'J','k'=>'K','l'=>'L','m'=>'M','n'=>'N','o'=>'O','p'=>'P','q'=>'Q','r'=>'R','s'=>'S','t'=>'T','u'=>'U','v'=>'V','w'=>'W','x'=>'X','y'=>'Y','z'=>'Z',_=>c}}
pub open spec fn double()->Cell {Cell::Text(seq!['D','O','U','B','L','E'])}
pub open spec fn dim(c:Cell)->Decode<Option<int>> {match c{
    Cell::Null=>Decode::Value(None),Cell::Text(t)=>if t.len()==0{Decode::Value(None)}else{match parser::integer(t){Some(n)=>Decode::Value(Some(n)),None=>Decode::Error}},
    Cell::Int(n)=>Decode::Value(Some(n)),Cell::Bool(b)=>Decode::Value(Some(if b{1int}else{0int})),
    Cell::Float(n)=>if n.1==0{Decode::Error}else{Decode::Value(Some(if n.0>=0{n.0/(n.1 as int)}else{-((-n.0)/(n.1 as int))}))},_=>Decode::Error}}
pub open spec fn matches(r:Request,row:Row)->bool {row.graph==graph(r) && row.model==r.model && row.kind.unwrap_or(0)==r.kind}
pub open spec fn selected_rows(r:Request,rows:Seq<Row>)->Seq<Seq<Cell>> {rows.filter(|x:Row|matches(r,x)).map_values(|x:Row|x.cols)}
pub open spec fn preference(row:Seq<Cell>)->nat {if row.len()>0{match row[0]{Cell::Name(n)=>if n<3{n}else{3},_=>3}}else{3}}
pub open spec fn choose_row(rows:Seq<Seq<Cell>>,best:Option<Seq<Cell>>)->Option<Seq<Cell>>
    decreases rows.len(),
{if rows.len()==0{best}else{let row=rows[0];let next=if row.len()<5{best}else{match best{None=>Some(row),Some(old)=>if preference(row)<preference(old){Some(row)}else{best}}};choose_row(rows.drop_first(),next)}}
pub open spec fn decode(row:Seq<Cell>)->Decode<Route> {
    if row.len()<5{Decode::Error}else{let table=match row[0]{Cell::Name(t)=>Some(t),_=>None};
        match dim(row[1]){Decode::Error=>Decode::Error,Decode::Value(width)=>Decode::Value(Route{table,width,dtype:if truthy(row[2]){row[2]}else{double()}})}}
}
pub open spec fn find(t:Text,p:Text,i:nat)->Option<nat>
    decreases t.len()-i,
{if i+p.len()>t.len(){None}else if t.subrange(i as int,(i+p.len()) as int)==p{Some(i)}else if i>=t.len(){None}else{find(t,p,i+1)}}
pub open spec fn absent(f:Fault)->bool {f.code==Some(-30) || find(f.message,seq!['S','Q','L','C','O','D','E',':',' ','<','-','3','0','>'],0).is_some()}
pub open spec fn legacy(kind:nat)->Name {if kind==1{2}else{0}}
pub open spec fn fallback(r:Request,readable:bool)->Selection {
    if !readable || (graph(r)==0 && r.model.is_none()){Selection::Table{Name:legacy(r.kind),route:None}}else{Selection::Empty}
}
pub open spec fn cached(r:Request,e:Engine)->bool {r.ttl!=0 && e.cache.contains_key(key(r)) && r.now-e.cache[key(r)].at<=r.ttl}
pub open spec fn evict(r:Request,e:Engine)->Engine {
    if r.ttl!=0 && e.cache.contains_key(key(r)) && r.now-e.cache[key(r)].at>r.ttl{Engine{cache:e.cache.remove(key(r)),..e}}else{e}
}
pub open spec fn route_selection(route:Route)->Selection {
    match route.table {Some(t)=>Selection::Table{Name:t,route:Some(route)},None=>Selection::Empty}
}
pub open spec fn resolve(r:Request,e:Engine,raw:Raw<Seq<Row>>)->Resolved {
    if cached(r,e) {Resolved{engine:e,selection:route_selection(e.cache[key(r)].route)}}
    else {
        let old=evict(r,e);let next=Engine{reads:old.reads+1,..old};
        match raw {
            Raw::Error(f)=>Resolved{engine:next,selection:if absent(f){fallback(r,false)}else{Selection::Error}},
            Raw::Rows(all)=>{
                let rows=selected_rows(r,all);
                if rows.len()==0 {Resolved{engine:next,selection:fallback(r,true)}}
                else {
                    match choose_row(rows,None) {
                        None=>Resolved{engine:next,selection:fallback(r,false)},
                        Some(row)=>match decode(row) {
                            Decode::Error=>Resolved{engine:next,selection:Selection::Error},
                            Decode::Value(route)=>{
                                let engine=Engine{cache:next.cache.insert(key(r),Cached{route,at:r.write_at}),..next};
                                Resolved{engine,selection:route_selection(route)}
                            },
                        },
                    }
                }
            },
        }
    }
}
pub open spec fn invalidate(e:Engine,g:Option<int>,m:Option<int>,kind:Option<nat>)->Engine {
    Engine{cache:e.cache.restrict(e.cache.dom().filter(|k:Key|!(g.is_none() || (k.1==g.unwrap() && (m.is_none() || k.2==m) && (kind.is_none() || k.3==kind.unwrap()))))),..e}
}
pub proof fn theorem_absent_named_does_not_cache(r:Request,e:Engine)
    requires !cached(r,e),graph(r)!=0 || r.model.is_some(),
    ensures resolve(r,e,Raw::Rows(seq![])).selection is Empty,
        resolve(r,e,Raw::Rows(seq![])).engine.cache==evict(r,e).cache,
        resolve(r,e,Raw::Rows(seq![])).engine.reads==e.reads+1,
{}
pub proof fn theorem_positive_hit_preserves_row_without_read(r:Request,e:Engine,raw:Raw<Seq<Row>>)
    requires cached(r,e),e.cache[key(r)].route.table.is_some(),
    ensures resolve(r,e,raw).engine==e,resolve(r,e,raw).selection==(Selection::Table{Name:e.cache[key(r)].route.table.unwrap(),route:Some(e.cache[key(r)].route)}),
{}
pub proof fn theorem_other_registry_error_is_not_legacy(r:Request,e:Engine,f:Fault)
    requires !cached(r,e),!absent(f),
    ensures resolve(r,e,Raw::Error(f)).selection is Error,resolve(r,e,Raw::Error(f)).engine.reads==e.reads+1,
{}
pub proof fn theorem_cache_strict_expiry(r:Request,e:Engine)
    requires e.cache.contains_key(key(r)),r.ttl>0,
    ensures r.now-e.cache[key(r)].at==r.ttl ==> cached(r,e),
        r.now-e.cache[key(r)].at>r.ttl ==> !cached(r,e) && !evict(r,e).cache.contains_key(key(r)),
{}
pub proof fn theorem_zero_ttl_requeries(r:Request,e:Engine,raw:Raw<Seq<Row>>)
    requires r.ttl==0,
    ensures !cached(r,e),resolve(r,e,raw).engine.reads==e.reads+1,
{}
pub proof fn theorem_row_field_decoding()
    ensures dim(Cell::Null)==Decode::Value(None),dim(Cell::Text(seq![]))==Decode::Value(None),dim(Cell::Bool(false))==Decode::Value(Some(0)),
        dim(Cell::Text(seq!['4']))==Decode::Value(Some(4)),dim(Cell::Text(seq!['b','a','d'])) is Error,
{parser::theorem_raw_integer_carriers();}
pub proof fn theorem_one_matching_raw_row_is_cached(r:Request,e:Engine,row:Row,route:Route)
    requires !cached(r,e),matches(r,row),row.cols.len()>=5,decode(row.cols)==Decode::Value(route),
    ensures resolve(r,e,Raw::Rows(seq![row])).selection==route_selection(route),
        resolve(r,e,Raw::Rows(seq![row])).engine.cache[key(r)]==(Cached{route,at:r.write_at}),
        resolve(r,e,Raw::Rows(seq![row])).engine.reads==e.reads+1,
{reveal_with_fuel(Seq::filter,2);reveal_with_fuel(choose_row,2);assert(selected_rows(r,seq![row]) =~= seq![row.cols]);}
pub proof fn theorem_absent_then_raw_published_route_is_seen(r:Request,e:Engine,row:Row,route:Route)
    requires !cached(r,e),graph(r)!=0 || r.model.is_some(),matches(r,row),row.cols.len()>=5,decode(row.cols)==Decode::Value(route),
    ensures resolve(r,resolve(r,e,Raw::Rows(seq![])).engine,Raw::Rows(seq![row])).selection==route_selection(route),
        resolve(r,resolve(r,e,Raw::Rows(seq![])).engine,Raw::Rows(seq![row])).engine.reads==e.reads+2,
{theorem_absent_named_does_not_cache(r,e);theorem_one_matching_raw_row_is_cached(r,resolve(r,e,Raw::Rows(seq![])).engine,row,route);}
pub proof fn theorem_cache_key_is_pair_and_registry_specific(r:Request,s:Request,e:Engine)
    requires key(r)!=key(s),!e.cache.contains_key(key(s)),
    ensures !cached(s,Engine{cache:e.cache.insert(key(r),Cached{route:Route{table:Some(9),width:Some(4),dtype:double()},at:r.write_at}),..e}),
{}

}
