use vstd::prelude::*;
use vstd::seq_lib::*;
#[path="parser.rs"] pub mod parser;
#[path="json_width.rs"] pub mod json_width;
#[path="catalog.rs"] pub mod catalog;
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
pub open spec fn node_request(r:Request)->Request {Request{kind:0,..r}}
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

pub proof fn theorem_each_raw_key_field_prevents_alias(r:Request,s:Request)
    requires r.registry!=s.registry || graph(r)!=graph(s) || r.model!=s.model || r.kind!=s.kind,
    ensures key(r)!=key(s),
{}

pub proof fn theorem_invalidation_removes_exact_requested_scope(e:Engine,g:Option<int>,m:Option<int>,kind:Option<nat>,k:Key)
    ensures invalidate(e,g,m,kind).cache.contains_key(k) <==> e.cache.contains_key(k) && !(g.is_none() || (k.1==g.unwrap() && (m.is_none() || k.2==m) && (kind.is_none() || k.3==kind.unwrap()))),
{}

}

pub mod workflow {
// Actual search phase order and readers. Numeric SQL/numpy kernels remain provider replies.
use vstd::prelude::*;
use crate::*;
verus! {
pub enum Query {Text(Text),List(Seq<Cell>),Null,Other(Cell)}
pub enum Entry {Primary,Optimized,Client}
pub enum ScoreKind {Primary,Embedded,Dbapi}
pub struct Args {pub query:Query,pub k:nat,pub label:Option<Text>,pub dtype:Option<Cell>,pub engine_dtype:Cell}
pub struct Stored {pub table:Name,pub graph:int,pub id:Cell,pub emb:Cell,pub labels:Set<Text>}
pub struct Scored {pub row:Stored,pub cells:Seq<Cell>}
pub struct Kernel {pub query_norm:Number,pub row_norm:Number,pub score:Number}
pub struct ClientRow {pub row:Stored,pub kernel:Raw<Kernel>}
pub struct Env {pub request:Request,pub registry:Raw<Seq<Row>>,pub catalog:catalog::Catalog,
    pub array:Raw<()>,pub seed:Raw<Seq<Stored>>,pub primary:Raw<Seq<Scored>>,pub embedded:Raw<Seq<Scored>>,pub dbapi:Raw<Seq<Scored>>,pub client:Raw<Seq<ClientRow>>,pub diagnostic:Raw<Seq<Stored>>}
pub enum Effect {Route(Key),RegistryRead(Key),CatalogRead(Name,nat),Cursor,
    SeedRead(Name,int,Text),Score(ScoreKind,Name,int,Query,Cell,Option<Text>,Option<Text>),
    ClientRead(Name,int,Option<Text>),Kernel(Cell),DiagnosticRead(Name,int),
    IvfRead(Name,int),Build(Name),AddBatch(nat),Finalize,Info,Publish}
pub enum Error {Registry,Dtype,Width{query:Option<nat>,stored:Option<int>},Provider,Reader,Query,Array,Input,NoRoute,NoVectors,Shape,Cluster,Build,Info}
pub type Answer=Seq<(Cell,Number)>;
pub enum Outcome {Rows(Answer),Error(Error)}
pub struct Result {pub engine:Engine,pub trace:Seq<Effect>,pub outcome:Outcome}
pub enum Gate {Stop(Error),Empty,Ready{Name:Name,route:Option<Route>,dtype:Cell}}
pub struct Prepared {pub engine:Engine,pub trace:Seq<Effect>,pub gate:Gate}
pub open spec fn measured(q:Text)->Option<nat> {json_width::width(q)}
pub open spec fn qwidth(q:Query)->Option<nat> {match q{Query::Text(t)=>measured(t),_=>None}}
pub open spec fn qliteral(q:Query)->bool {match q{Query::Text(t)=>json_width::literal(t),_=>false}}
pub open spec fn declared(route:Option<Route>)->Option<int> {match route{Some(r)=>r.width,None=>None}}
pub open spec fn dtype(a:Args,route:Option<Route>)->Decode<Cell> {
    let raw=match a.dtype{Some(x)=>if truthy(x){x}else{match route{Some(r)=>if truthy(r.dtype){r.dtype}else{a.engine_dtype},None=>a.engine_dtype}},None=>match route{Some(r)=>if truthy(r.dtype){r.dtype}else{a.engine_dtype},None=>a.engine_dtype}};
    match raw{Cell::Text(t)=>Decode::Value(Cell::Text(t.map_values(|c:char|upper(c)))),_=>Decode::Error}
}
pub open spec fn width_check(q:Query,route:Option<Route>,cat:catalog::Catalog)->(Option<Error>,nat) {
    if !qliteral(q){(None,0)}else{
        let d=declared(route);let z=if d.is_some() && d.unwrap()!=0{(d,0nat)}else{catalog::read(cat)};
        if z.0.is_none() || z.0.unwrap()==0{(None,z.1)}else{match qwidth(q){Some(w)=>if w as int!=z.0.unwrap(){(Some(Error::Width{query:Some(w),stored:z.0}),z.1)}else{(None,z.1)},None=>(None,z.1)}}
    }
}
pub open spec fn prepare(stage:Entry,e:Engine,a:Args,v:Env)->Prepared {
    let r=resolve(v.request,e,v.registry);let t=seq![Effect::Route(key(v.request))]+if r.engine.reads>e.reads{seq![Effect::RegistryRead(key(v.request))]}else{seq![]};
    match r.selection{
        Selection::Empty=>Prepared{engine:r.engine,trace:t,gate:Gate::Empty},Selection::Error=>Prepared{engine:r.engine,trace:t,gate:Gate::Stop(Error::Registry)},
        Selection::Table{Name:table,route}=>{
            let d=if stage is Primary{dtype(a,route)}else{Decode::Value(a.engine_dtype)};
            match d{Decode::Error=>Prepared{engine:r.engine,trace:t,gate:Gate::Stop(Error::Dtype)},Decode::Value(dtype)=>{
                let ck=width_check(a.query,route,v.catalog);let t=t+if ck.1>0{seq![Effect::CatalogRead(table,ck.1)]}else{seq![]};
                Prepared{engine:r.engine,trace:t,gate:match ck.0{Some(err)=>Gate::Stop(err),None=>Gate::Ready{Name:table,route,dtype}}}
            }}
        }
    }
}
pub open spec fn numeric(c:Cell)->Option<Number> {match c{Cell::Int(n)=>Some((n,1)),Cell::Bool(b)=>Some((if b{1int}else{0int},1)),Cell::Float(n)=>if n.1>0{Some(n)}else{None},Cell::Text(t)=>numbers::decimal(t),_=>None}}
pub open spec fn read_scores(rows:Seq<Seq<Cell>>,embedded:bool,exact:bool)->Decode<Answer> decreases rows.len(),
{
    if rows.len()==0{Decode::Value(seq![])}else{let r=rows[0];
        if r.len()==0{Decode::Error}else if embedded && r[0] is Null{read_scores(rows.drop_first(),embedded,exact)}
        else if r.len()<2 || (exact && r.len()!=2){Decode::Error}else{match numeric(r[1]){None=>Decode::Error,Some(n)=>match read_scores(rows.drop_first(),embedded,exact){Decode::Error=>Decode::Error,Decode::Value(t)=>Decode::Value(seq![(r[0],n)]+t)}}}
    }
}
pub open spec fn label(a:Args,client:bool)->Option<Text> {if client{a.label}else{match a.label{Some(t)=>if t.len()>0{Some(t)}else{None},None=>None}}}
pub open spec fn selected(s:Stored,table:Name,g:int,l:Option<Text>,exclude:Option<Text>)->bool {
    s.table==table && s.graph==g && (l.is_none() || s.labels.contains(l.unwrap())) && (exclude.is_none() || exclude.unwrap().len()==0 || s.id!=Cell::Text(exclude.unwrap()))
}
pub open spec fn sql_rows(raw:Seq<Scored>,table:Name,g:int,l:Option<Text>,exclude:Option<Text>,k:nat)->Seq<Seq<Cell>> {
    let rs=raw.filter(|s:Scored|selected(s.row,table,g,l,exclude));rs.take((if rs.len()<k{rs.len()}else{k}) as int).map_values(|s:Scored|s.cells)
}
pub open spec fn provider_read(raw:Raw<Seq<Scored>>,table:Name,g:int,l:Option<Text>,exclude:Option<Text>,k:nat,embedded:bool,exact:bool)->Decode<Answer> {
    match raw{Raw::Error(_)=>Decode::Error,Raw::Rows(rows)=>read_scores(sql_rows(rows,table,g,l,exclude,k),embedded,exact)}
}
pub open spec fn width_fault(f:Fault)->bool {find(f.message,seq!['-','2','5','7'],0).is_some() || find(f.message,seq!['v','e','c','t','o','r','s',' ','o','f',' ','d','i','f','f','e','r','e','n','t',' ','l','e','n','g','t','h','s'],0).is_some()}
pub open spec fn csv(t:Text)->Text {seq!['[']+t+seq![']']}
pub open spec fn cell_str(c:Cell)->Text {match c{Cell::Text(t)=>t,Cell::Null=>seq!['N','o','n','e'],Cell::Int(n)=>numbers::integer(n),Cell::Bool(b)=>if b{seq!['T','r','u','e']}else{seq!['F','a','l','s','e']},_=>seq![]}} // ordinary CSV/NULL carrier; other __str__ provider boundary
pub open spec fn diag_query(q:Query)->Option<nat> {match q{Query::Text(t)=>match json_width::parsed(t){Some(w)=>w,None=>None},Query::List(v)=>Some(v.len()),_=>None}}
pub open spec fn stored_width(rows:Seq<Stored>)->Option<int> {
    if rows.len()==0 || rows[0].emb is Null{None}else{let t=cell_str(rows[0].emb);Some((t.filter(|c:char|c==',').len()+1) as int)}
}
pub open spec fn diagnostic(a:Args,v:Env,table:Name)->(Error,Seq<Effect>) {
    (Error::Width{query:diag_query(a.query),stored:match v.diagnostic{Raw::Error(_)=>None,Raw::Rows(rows)=>stored_width(rows.filter(|s:Stored|s.table==table && s.graph==graph(v.request)))}},seq![Effect::DiagnosticRead(table,graph(v.request))])
}
pub open spec fn seeds(raw:Seq<Stored>,table:Name,g:int,id:Text)->Seq<Stored> {raw.filter(|s:Stored|s.table==table && s.graph==g && s.id==Cell::Text(id))}
pub open spec fn expanded(q:Query,s:Stored)->Query {Query::Text(csv(cell_str(s.emb)))}
pub open spec fn score_effect(stage:ScoreKind,table:Name,a:Args,v:Env,d:Cell,exclude:Option<Text>)->Effect {Effect::Score(stage,table,graph(v.request),a.query,d,label(a,false),exclude)}
pub open spec fn shape_bad(q:Query,c:Cell)->bool {match (q,c){(Query::Text(t),Cell::Text(r))=>{let x=parser::width(json_width::trim(t));let y=parser::width(csv(r));x.is_some() && y.is_some() && x.unwrap()!=y.unwrap()},_=>false}}
pub open spec fn kernel(row:ClientRow,q:Query)->Option<(Cell,Number)> {
    if shape_bad(q,row.row.emb){None}else{match row.kernel{Raw::Error(_)=>None,Raw::Rows(k)=>if k.query_norm.0>0 && k.row_norm.0>0 && k.score.1>0{Some((row.row.id,k.score))}else{None}}}
}
pub open spec fn client_fold(rows:Seq<ClientRow>,q:Query)->(Answer,Seq<Effect>) decreases rows.len(),
{if rows.len()==0{(seq![],seq![])}else{let next=client_fold(rows.drop_first(),q);(match kernel(rows[0],q){Some(x)=>seq![x]+next.0,None=>next.0},seq![Effect::Kernel(rows[0].row.id)]+next.1)}}
pub open spec fn greater(a:Number,b:Number)->bool {a.0*(b.1 as int)>b.0*(a.1 as int)}
pub open spec fn insert(x:(Cell,Number),rows:Answer)->Answer decreases rows.len(),
{if rows.len()==0{seq![x]}else if greater(x.1,rows[0].1){seq![x]+rows}else{seq![rows[0]]+insert(x,rows.drop_first())}}
pub open spec fn sort(rows:Answer)->Answer decreases rows.len(),
{if rows.len()==0{rows}else{insert(rows.last(),sort(rows.drop_last()))}}
pub open spec fn rank(stage:Entry)->nat {match stage{Entry::Primary=>2,Entry::Optimized=>1,Entry::Client=>0}}
pub open spec fn scenario(v:Seq<Env>,stage:Entry)->Env recommends v.len()==3,{let z=v[(2-rank(stage)) as int];let r=v[0].request;Env{request:Request{registry:r.registry,graph:r.graph,model:r.model,kind:0,ttl:r.ttl,..z.request},..z}}
pub open spec fn run(stage:Entry,e:Engine,a:Args,vs:Seq<Env>)->Result
    recommends vs.len()==3,
    decreases rank(stage),
{
    let v=scenario(vs,stage);let p=prepare(stage,e,a,v);
    match p.gate{
        Gate::Empty=>Result{engine:p.engine,trace:p.trace,outcome:Outcome::Rows(seq![])},Gate::Stop(err)=>Result{engine:p.engine,trace:p.trace,outcome:Outcome::Error(err)},
        Gate::Ready{Name:table,route:_,dtype:d}=>{
            if stage is Client{
                let base=p.trace+seq![Effect::Cursor];
                let valid=match a.query{Query::Text(t)=>json_width::parsed(t).is_some(),_=>false};
                if !valid{Result{engine:p.engine,trace:base,outcome:Outcome::Error(Error::Query)}}else if v.array is Error{Result{engine:p.engine,trace:base,outcome:Outcome::Error(Error::Array)}}else{
                    let t=base+seq![Effect::ClientRead(table,graph(v.request),label(a,true))];
                    match v.client{Raw::Error(_)=>Result{engine:p.engine,trace:t,outcome:Outcome::Error(Error::Provider)},Raw::Rows(rows)=>{
                        let rows=rows.filter(|s:ClientRow|!(s.row.emb is Null) && selected(s.row,table,graph(v.request),label(a,true),None));let z=client_fold(rows,a.query);let sorted=sort(z.0);
                        Result{engine:p.engine,trace:t+z.1,outcome:Outcome::Rows(sorted.take((if sorted.len()<a.k{sorted.len()}else{a.k}) as int))}
                    }}
                }
            }else if stage is Optimized{
                let t=p.trace+seq![score_effect(ScoreKind::Embedded,table,a,v,d,None)];
                match provider_read(v.embedded,table,graph(v.request),label(a,false),None,a.k,true,false){Decode::Value(rows)=>Result{engine:p.engine,trace:t,outcome:Outcome::Rows(rows)},Decode::Error=>{
                    let t=t+seq![Effect::Cursor,score_effect(ScoreKind::Dbapi,table,a,v,d,None)];
                    match provider_read(v.dbapi,table,graph(v.request),label(a,false),None,a.k,false,false){Decode::Value(rows)=>Result{engine:p.engine,trace:t,outcome:Outcome::Rows(rows)},Decode::Error=>{let r=run(Entry::Client,p.engine,a,vs);Result{trace:t+r.trace,..r}}}
                }}
            }else{
                let base=p.trace+seq![Effect::Cursor];let id=match a.query{Query::Text(t)=>if !json_width::literal(t){Some(json_width::trim(t))}else{None},_=>None};
                let st=base+if id.is_some(){seq![Effect::SeedRead(table,graph(v.request),id.unwrap())]}else{seq![]};
                let seed=match v.seed{Raw::Rows(rows)=>seeds(rows,table,graph(v.request),id.unwrap_or(seq![])),_=>seq![]};
                if id.is_some() && v.seed is Rows && seed.len()==0{Result{engine:p.engine,trace:st,outcome:Outcome::Rows(seq![])}}
                else{
                    let a2=if id.is_some() && seed.len()>0{Args{query:expanded(a.query,seed[0]),..a}}else{a};
                    let seed_fault=id.is_some() && v.seed is Error;
                    let t=st+if seed_fault{seq![]}else{seq![score_effect(ScoreKind::Primary,table,a2,v,d,id)]};
                    let raw=if seed_fault{match v.seed{Raw::Error(f)=>Raw::Error(f),_=>v.primary}}else{v.primary};
                    let fail=match raw{Raw::Error(f)=>Some(f),_=>None};
                    if fail.is_some() && width_fault(fail.unwrap()){let z=diagnostic(a2,v,table);Result{engine:p.engine,trace:t+z.1,outcome:Outcome::Error(z.0)}}
                    else{match provider_read(raw,table,graph(v.request),label(a2,false),id,a.k,false,true){Decode::Value(rows)=>Result{engine:p.engine,trace:t,outcome:Outcome::Rows(rows)},Decode::Error=>{
                        let r=run(Entry::Optimized,p.engine,a2,vs);Result{trace:t+r.trace,..r}
                    }}}
                }
            }
        }
    }
}
pub open spec fn score_or_read(x:Effect)->bool {x is Score || x is ClientRead || x is Kernel || x is SeedRead}
pub open spec fn quiet(t:Seq<Effect>)->bool {forall|i:int|0<=i<t.len() ==> !score_or_read(t[i])}
pub proof fn theorem_prepare_absent_stops_before_dtype(stage:Entry,e:Engine,a:Args,v:Env)
    requires !cached(v.request,e),graph(v.request)!=0 || v.request.model.is_some(),v.registry==Raw::Rows(seq![]),
    ensures prepare(stage,e,a,v).gate is Empty,quiet(prepare(stage,e,a,v).trace),
{theorem_absent_named_does_not_cache(v.request,e);}
pub proof fn theorem_preflight_derived_mismatch(stage:Entry,e:Engine,a:Args,v:Env,table:Name,route:Option<Route>,d:Cell)
    requires resolve(v.request,e,v.registry).selection==(Selection::Table{Name:table,route}),
        stage is Primary ==> dtype(a,route)==Decode::Value(d),
        qliteral(a.query),qwidth(a.query).is_some(),declared(route).is_some(),declared(route).unwrap()!=0,
        qwidth(a.query).unwrap() as int!=declared(route).unwrap(),
    ensures prepare(stage,e,a,v).gate==Gate::Stop(Error::Width{query:qwidth(a.query),stored:declared(route)}),quiet(prepare(stage,e,a,v).trace),
{}
pub proof fn theorem_direct_guard_no_score(stage:Entry,e:Engine,a:Args,vs:Seq<Env>)
    requires vs.len()==3,prepare(stage,e,a,scenario(vs,stage)).gate is Stop || prepare(stage,e,a,scenario(vs,stage)).gate is Empty,
    ensures quiet(run(stage,e,a,vs).trace),
{}

pub proof fn theorem_primary_dtype_precedes_width(e:Engine,a:Args,v:Env,table:Name,route:Option<Route>)
    requires resolve(v.request,e,v.registry).selection==(Selection::Table{Name:table,route}),dtype(a,route) is Error,
    ensures prepare(Entry::Primary,e,a,v).gate==Gate::Stop(Error::Dtype),quiet(prepare(Entry::Primary,e,a,v).trace),
{}

pub proof fn theorem_primary_exact_pair_reader()
    ensures read_scores(seq![seq![Cell::Int(7),Cell::Int(1),Cell::Null]],false,true) is Error,
        read_scores(seq![seq![Cell::Int(7),Cell::Int(1),Cell::Null]],false,false)==Decode::Value(seq![(Cell::Int(7),(1,1))]),
{reveal_with_fuel(read_scores,2);}
pub proof fn theorem_client_shape_refusal_is_derived(row:ClientRow,q:Query)
    requires shape_bad(q,row.row.emb),
    ensures kernel(row,q)==None,client_fold(seq![row],q).0.len()==0,client_fold(seq![row],q).1==seq![Effect::Kernel(row.row.id)],
{reveal_with_fuel(client_fold,2);}
pub proof fn theorem_primary_generic_failure_really_calls_optimized(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell,f:Fault)
    requires vs.len()==3,qliteral(a.query),prepare(Entry::Primary,e,a,scenario(vs,Entry::Primary)).gate==(Gate::Ready{Name:table,route,dtype:d}),
        scenario(vs,Entry::Primary).primary==Raw::Error(f),!width_fault(f),
    ensures run(Entry::Primary,e,a,vs).outcome==run(Entry::Optimized,prepare(Entry::Primary,e,a,scenario(vs,Entry::Primary)).engine,a,vs).outcome,
        run(Entry::Primary,e,a,vs).engine==run(Entry::Optimized,prepare(Entry::Primary,e,a,scenario(vs,Entry::Primary)).engine,a,vs).engine,
{reveal_with_fuel(run,2);}
pub proof fn theorem_optimized_double_failure_really_calls_client(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell)
    requires vs.len()==3,prepare(Entry::Optimized,e,a,scenario(vs,Entry::Optimized)).gate==(Gate::Ready{Name:table,route,dtype:d}),
        provider_read(scenario(vs,Entry::Optimized).embedded,table,graph(scenario(vs,Entry::Optimized).request),label(a,false),None,a.k,true,false) is Error,
        provider_read(scenario(vs,Entry::Optimized).dbapi,table,graph(scenario(vs,Entry::Optimized).request),label(a,false),None,a.k,false,false) is Error,
    ensures run(Entry::Optimized,e,a,vs).outcome==run(Entry::Client,prepare(Entry::Optimized,e,a,scenario(vs,Entry::Optimized)).engine,a,vs).outcome,
{reveal_with_fuel(run,2);}

pub proof fn lemma_all_shape_bad_drop(rows:Seq<ClientRow>,q:Query)
    requires forall|i:int|0<=i<rows.len() ==> #[trigger] shape_bad(q,rows[i].row.emb),
    ensures client_fold(rows,q).0.len()==0,client_fold(rows,q).1.len()==rows.len(),
    decreases rows.len(),
{if rows.len()>0{lemma_all_shape_bad_drop(rows.drop_first(),q);}}
pub proof fn theorem_seed_failure_passes_expansion_without_identity(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell,id:Text,s:Stored,f:Fault)
    requires vs.len()==3,a.query==Query::Text(id),!json_width::literal(id),json_width::trim(id)==id,
        prepare(Entry::Primary,e,a,scenario(vs,Entry::Primary)).gate==(Gate::Ready{Name:table,route,dtype:d}),
        scenario(vs,Entry::Primary).seed==Raw::Rows(seq![s]),s.table==table,s.graph==graph(scenario(vs,Entry::Primary).request),s.id==Cell::Text(id),scenario(vs,Entry::Primary).primary==Raw::Error(f),!width_fault(f),
    ensures run(Entry::Primary,e,a,vs).outcome==run(Entry::Optimized,prepare(Entry::Primary,e,a,scenario(vs,Entry::Primary)).engine,Args{query:expanded(a.query,s),..a},vs).outcome,
{reveal_with_fuel(run,2);reveal_with_fuel(Seq::filter,2);assert(seeds(seq![s],table,graph(scenario(vs,Entry::Primary).request),id) =~= seq![s]);}


pub proof fn theorem_array_provider_failure_is_not_json_failure(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell)
    requires vs.len()==3,prepare(Entry::Client,e,a,scenario(vs,Entry::Client)).gate==(Gate::Ready{Name:table,route,dtype:d}),
        a.query is Text,json_width::parsed(match a.query{Query::Text(t)=>t,_=>seq![]}).is_some(),scenario(vs,Entry::Client).array is Error,
    ensures run(Entry::Client,e,a,vs).outcome==Outcome::Error(Error::Array),quiet(run(Entry::Client,e,a,vs).trace),
{reveal_with_fuel(run,1);}

pub proof fn theorem_whole_missing_raw_pair_returns_quiet_empty(stage:Entry,e:Engine,a:Args,vs:Seq<Env>)
    requires vs.len()==3,!cached(scenario(vs,stage).request,e),graph(scenario(vs,stage).request)!=0 || scenario(vs,stage).request.model.is_some(),scenario(vs,stage).registry==Raw::Rows(seq![]),
    ensures run(stage,e,a,vs).outcome==Outcome::Rows(seq![]),quiet(run(stage,e,a,vs).trace),run(stage,e,a,vs).engine.reads==e.reads+1,
{theorem_prepare_absent_stops_before_dtype(stage,e,a,scenario(vs,stage));theorem_direct_guard_no_score(stage,e,a,vs);}
pub proof fn theorem_whole_raw_row_four_query_three_no_scoring(stage:Entry,e:Engine,a:Args,vs:Seq<Env>,row:Row)
    requires vs.len()==3,!cached(scenario(vs,stage).request,e),matches(scenario(vs,stage).request,row),
        row.cols==seq![Cell::Name(9),Cell::Int(4),double(),Cell::Null,Cell::Null],scenario(vs,stage).registry==Raw::Rows(seq![row]),
        a.query==Query::Text(seq!['[','1',',','2',',','3',']']),a.dtype.is_none(),
    ensures run(stage,e,a,vs).outcome==Outcome::Error(Error::Width{query:Some(3),stored:Some(4)}),quiet(run(stage,e,a,vs).trace),
{
    let v=scenario(vs,stage);let route=Route{table:Some(9),width:Some(4),dtype:double()};
    theorem_one_matching_raw_row_is_cached(v.request,e,row,route);json_width::theorem_numeric_outer_counts();
    match dtype(a,Some(route)){Decode::Value(d)=>theorem_preflight_derived_mismatch(stage,e,a,v,9,Some(route),d),Decode::Error=>{assert(false);}}
    theorem_direct_guard_no_score(stage,e,a,vs);
}

pub proof fn theorem_all_search_phases_keep_original_scope(v:Seq<Env>,stage:Entry)
    requires v.len()==3,
    ensures key(scenario(v,stage).request)==key(node_request(v[0].request)),scenario(v,stage).request.kind==0,scenario(v,stage).request.ttl==v[0].request.ttl,
{}

}

}

pub mod ivf {
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
    let r=node_request(r);let base=Result{engine:e,local:l,trace:seq![],error:None,returned:None};
    if !valid(a){Result{error:Some(Error::Input),..base}}else if p.dependencies is Error{Result{error:Some(Error::Provider),..base}}else{
        let route=resolve(node_request(r),e,registry);let tr=seq![Effect::Route(key(r))]+if route.engine.reads>e.reads{seq![Effect::RegistryRead(key(r))]}else{seq![]};
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
                                                if false{Result{error:Some(Error::Info),..base}}else{
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
    requires valid(a),p.dependencies is Rows,resolve(node_request(r),e,registry).selection is Empty,
    ensures run(e,l,r,registry,a,p).error==Some(Error::NoRoute),no_vector_effects(run(e,l,r,registry,a,p).trace),run(e,l,r,registry,a,p).local==l,
{}
pub proof fn theorem_empty_ids_after_cursor_before_select(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers)
    requires valid(a),p.dependencies is Rows,resolve(node_request(r),e,registry).selection is Table,a.node_ids==Some(seq![]),
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
pub proof fn theorem_invalid_raw_batch_fails_after_build(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers,raw:Seq<Stored>,table:Name,route:Option<Route>)
    requires valid(a),p.dependencies is Rows,resolve(node_request(r),e,registry).selection==(Selection::Table{Name:table,route}),
        a.node_ids.is_none(),p.rows==Raw::Rows(raw),eligible(raw,table,graph(r),None).len()>0,rectangular(vectors(eligible(raw,table,graph(r),None))),
        raw_int(a.nlist).is_some(),raw_int(a.batch_size).is_some(),p.cluster is Rows,p.build is Rows,raw_int(a.build_batch).is_none(),
    ensures run(e,l,r,registry,a,p).error==Some(Error::Input),run(e,l,r,registry,a,p).trace.last()==Effect::Build(table),run(e,l,r,registry,a,p).local==l,
{}
pub proof fn theorem_info_error_never_publishes(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers)
    requires p.info is Error,
    ensures run(e,l,r,registry,a,p).local==l,run(e,l,r,registry,a,p).returned.is_none(),
{}
pub open spec fn reaches_info(e:Engine,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers,table:Name)->bool {
    valid(a) && p.dependencies is Rows && (match resolve(node_request(r),e,registry).selection{Selection::Table{Name:t,route:_}=>t==table,_=>false}) && a.node_ids.is_none() && p.rows is Rows
    && {let rows=eligible(match p.rows{Raw::Rows(rows)=>rows,_=>seq![]},table,graph(r),None);let vs=vectors(rows);
        rows.len()>0 && rectangular(vs) && raw_int(a.nlist).is_some() && raw_int(a.batch_size).is_some() && p.cluster is Rows && p.build is Rows
        && raw_int(a.build_batch).is_some() && add_batches(vs.len(),raw_int(a.build_batch).unwrap(),0,p.adds).1.is_none() && p.finalize is Rows}
}

pub proof fn theorem_valid_info_publishes_after_native_prefix(e:Engine,l:Local,r:Request,registry:Raw<Seq<Row>>,a:Args,p:Providers,table:Name,text:Text)
    requires reaches_info(e,r,registry,a,p,table),p.info==Raw::Rows(Cell::Text(text)),json_width::parsed(text).is_some(),
    ensures run(e,l,r,registry,a,p).error.is_none(),run(e,l,r,registry,a,p).trace.last()==Effect::Publish,
        run(e,l,r,registry,a,p).local.indexes[a.name]==1,run(e,l,r,registry,a,p).local.scopes[a.name]==graph(r),run(e,l,r,registry,a,p).returned==Some(text),
{}

}

}

use workflow::{Args,Env,Entry,Query,scenario,Gate,Outcome,Error,Effect,qliteral,declared,width_check,read_scores,prepare,run,width_fault,diagnostic};

verus! {
pub proof fn theorem_raw_literal_three_route_four_refuses(route:Option<Route>,c:catalog::Catalog)
    requires declared(route)==Some(4),
    ensures width_check(Query::Text(seq!['[','1',',','2',',','3',']']),route,c)==(Some(Error::Width{query:Some(3),stored:Some(4)}),0),
{json_width::theorem_numeric_outer_counts();}

pub proof fn theorem_catalog_only_when_literal_and_no_route_width(q:Query,r:Option<Route>,c:catalog::Catalog)
    ensures !qliteral(q) || (declared(r).is_some() && declared(r).unwrap()!=0) ==> width_check(q,r,c).1==0,
{}

pub proof fn theorem_reader_none_difference(n:Number)
    requires n.1>0,
    ensures read_scores(seq![seq![Cell::Null,Cell::Float(n)]],true,false)==Decode::Value(seq![]),
        read_scores(seq![seq![Cell::Null,Cell::Float(n)]],false,false)==Decode::Value(seq![(Cell::Null,n)]),
{reveal_with_fuel(read_scores,2);}

pub proof fn theorem_primary_width_fault_does_not_fallback(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell,f:Fault)
    requires vs.len()==3,qliteral(a.query),prepare(Entry::Primary,e,a,scenario(vs,Entry::Primary)).gate==(Gate::Ready{Name:table,route,dtype:d}),scenario(vs,Entry::Primary).primary==Raw::Error(f),width_fault(f),
    ensures run(Entry::Primary,e,a,vs).outcome==Outcome::Error(diagnostic(a,scenario(vs,Entry::Primary),table).0),
        run(Entry::Primary,e,a,vs).trace.last()==Effect::DiagnosticRead(table,graph(scenario(vs,Entry::Primary).request)),
{reveal_with_fuel(run,1);}

pub proof fn theorem_malformed_info_after_build_keeps_local_maps(e:Engine,l:ivf::Local,r:Request,registry:Raw<Seq<Row>>,a:ivf::Args,p:ivf::Providers,table:Name,text:Text)
    requires ivf::reaches_info(e,r,registry,a,p,table),p.info==Raw::Rows(Cell::Text(text)),json_width::parsed(text).is_none(),
    ensures ivf::run(e,l,r,registry,a,p).error==Some(Error::Info),ivf::run(e,l,r,registry,a,p).local==l,
        ivf::run(e,l,r,registry,a,p).trace.last()==Effect::Info,ivf::run(e,l,r,registry,a,p).trace.contains(Effect::Build(table)),ivf::run(e,l,r,registry,a,p).returned.is_none(),
{
    let rr=resolve(node_request(r),e,registry);let i=1nat+(if rr.engine.reads>e.reads{1nat}else{0nat})+2;let t=ivf::run(e,l,r,registry,a,p).trace;
    assert(i<t.len());assert(t[i as int]==Effect::Build(table));assert(exists|j:int|0<=j<t.len() && t[j]==Effect::Build(table)) by {assert(0<=(i as int) && (i as int)<t.len());};
}
}
