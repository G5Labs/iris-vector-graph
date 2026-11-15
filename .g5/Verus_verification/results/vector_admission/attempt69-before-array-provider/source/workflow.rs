// Actual search phase order and readers. Numeric SQL/numpy kernels remain provider replies.
use vstd::prelude::*;
use crate::*;
verus! {
pub enum Query {Text(Text),List(Seq<Cell>),Null,Other(Cell)}
pub enum Entry {Primary,Optimized,Client}
pub struct Args {pub query:Query,pub k:nat,pub label:Option<Text>,pub dtype:Option<Cell>,pub engine_dtype:Cell}
pub struct Stored {pub table:Name,pub graph:int,pub id:Cell,pub emb:Cell,pub labels:Set<Text>}
pub struct Scored {pub row:Stored,pub cells:Seq<Cell>}
pub struct Kernel {pub query_norm:Number,pub row_norm:Number,pub score:Number}
pub struct ClientRow {pub row:Stored,pub kernel:Raw<Kernel>}
pub struct Env {pub request:Request,pub registry:Raw<Seq<Row>>,pub catalog:catalog::Catalog,
    pub seed:Raw<Seq<Stored>>,pub primary:Raw<Seq<Scored>>,pub embedded:Raw<Seq<Scored>>,pub dbapi:Raw<Seq<Scored>>,pub client:Raw<Seq<ClientRow>>,pub diagnostic:Raw<Seq<Stored>>}
pub enum Effect {Route(Key),RegistryRead(Key),CatalogRead(Name,nat),Cursor,
    SeedRead(Name,int,Text),Score(Entry,Name,int,Query,Cell,Option<Text>,Option<Text>),
    ClientRead(Name,int,Option<Text>),Kernel(Cell),DiagnosticRead(Name,int),
    IvfRead(Name,int),Build(Name),AddBatch(nat),Finalize,Info,Publish}
pub enum Error {Registry,Dtype,Width{query:Option<nat>,stored:Option<int>},Provider,Reader,Query,Input,NoRoute,NoVectors,Shape,Cluster,Build,Info}
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
    if rows.len()==0 || rows[0].emb is Null{None}else{let t=cell_str(rows[0].emb);if t.len()==0{None}else{Some((t.filter(|c:char|c==',').len()+1) as int)}}
}
pub open spec fn diagnostic(a:Args,v:Env,table:Name)->(Error,Seq<Effect>) {
    (Error::Width{query:diag_query(a.query),stored:match v.diagnostic{Raw::Error(_)=>None,Raw::Rows(rows)=>stored_width(rows.filter(|s:Stored|s.table==table && s.graph==graph(v.request)))}},seq![Effect::DiagnosticRead(table,graph(v.request))])
}
pub open spec fn seeds(raw:Seq<Stored>,table:Name,g:int,id:Text)->Seq<Stored> {raw.filter(|s:Stored|s.table==table && s.graph==g && s.id==Cell::Text(id))}
pub open spec fn expanded(q:Query,s:Stored)->Query {Query::Text(csv(cell_str(s.emb)))}
pub open spec fn score_effect(stage:Entry,table:Name,a:Args,v:Env,d:Cell,exclude:Option<Text>)->Effect {Effect::Score(stage,table,graph(v.request),a.query,d,label(a,false),exclude)}
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
pub open spec fn scenario(v:Seq<Env>,stage:Entry)->Env recommends v.len()==3,{v[(2-rank(stage)) as int]}
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
                if !valid{Result{engine:p.engine,trace:base,outcome:Outcome::Error(Error::Query)}}else{
                    let t=base+seq![Effect::ClientRead(table,graph(v.request),label(a,true))];
                    match v.client{Raw::Error(_)=>Result{engine:p.engine,trace:t,outcome:Outcome::Error(Error::Provider)},Raw::Rows(rows)=>{
                        let rows=rows.filter(|s:ClientRow|!(s.row.emb is Null) && selected(s.row,table,graph(v.request),label(a,true),None));let z=client_fold(rows,a.query);let sorted=sort(z.0);
                        Result{engine:p.engine,trace:t+z.1,outcome:Outcome::Rows(sorted.take((if sorted.len()<a.k{sorted.len()}else{a.k}) as int))}
                    }}
                }
            }else if stage is Optimized{
                let t=p.trace+seq![score_effect(stage,table,a,v,d,None)];
                match provider_read(v.embedded,table,graph(v.request),label(a,false),None,a.k,true,false){Decode::Value(rows)=>Result{engine:p.engine,trace:t,outcome:Outcome::Rows(rows)},Decode::Error=>{
                    let t=t+seq![Effect::Cursor,score_effect(stage,table,a,v,d,None)];
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
                    let t=st+if seed_fault{seq![]}else{seq![score_effect(stage,table,a2,v,d,id)]};
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
pub proof fn theorem_catalog_only_when_literal_and_no_route_width(q:Query,r:Option<Route>,c:catalog::Catalog)
    ensures !qliteral(q) || (declared(r).is_some() && declared(r).unwrap()!=0) ==> width_check(q,r,c).1==0,
{}
pub proof fn theorem_primary_dtype_precedes_width(e:Engine,a:Args,v:Env,table:Name,route:Option<Route>)
    requires resolve(v.request,e,v.registry).selection==(Selection::Table{Name:table,route}),dtype(a,route) is Error,
    ensures prepare(Entry::Primary,e,a,v).gate==Gate::Stop(Error::Dtype),quiet(prepare(Entry::Primary,e,a,v).trace),
{}
pub proof fn theorem_reader_none_difference(n:Number)
    requires n.1>0,
    ensures read_scores(seq![seq![Cell::Null,Cell::Float(n)]],true,false)==Decode::Value(seq![]),
        read_scores(seq![seq![Cell::Null,Cell::Float(n)]],false,false)==Decode::Value(seq![(Cell::Null,n)]),
{reveal_with_fuel(read_scores,2);}
pub proof fn theorem_primary_exact_pair_reader()
    ensures read_scores(seq![seq![Cell::Int(7),Cell::Int(1),Cell::Null]],false,true) is Error,
        read_scores(seq![seq![Cell::Int(7),Cell::Int(1),Cell::Null]],false,false)==Decode::Value(seq![(Cell::Int(7),(1,1))]),
{reveal_with_fuel(read_scores,2);}
pub proof fn theorem_client_shape_refusal_is_derived(row:ClientRow,q:Query)
    requires shape_bad(q,row.row.emb),
    ensures kernel(row,q)==None,client_fold(seq![row],q).0.len()==0,client_fold(seq![row],q).1==seq![Effect::Kernel(row.row.id)],
{reveal_with_fuel(client_fold,2);}
pub proof fn theorem_primary_generic_failure_really_calls_optimized(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell,f:Fault)
    requires vs.len()==3,qliteral(a.query),prepare(Entry::Primary,e,a,vs[0]).gate==(Gate::Ready{Name:table,route,dtype:d}),
        vs[0].primary==Raw::Error(f),!width_fault(f),
    ensures run(Entry::Primary,e,a,vs).outcome==run(Entry::Optimized,prepare(Entry::Primary,e,a,vs[0]).engine,a,vs).outcome,
        run(Entry::Primary,e,a,vs).engine==run(Entry::Optimized,prepare(Entry::Primary,e,a,vs[0]).engine,a,vs).engine,
{reveal_with_fuel(run,2);}
pub proof fn theorem_optimized_double_failure_really_calls_client(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell)
    requires vs.len()==3,prepare(Entry::Optimized,e,a,vs[1]).gate==(Gate::Ready{Name:table,route,dtype:d}),
        provider_read(vs[1].embedded,table,graph(vs[1].request),label(a,false),None,a.k,true,false) is Error,
        provider_read(vs[1].dbapi,table,graph(vs[1].request),label(a,false),None,a.k,false,false) is Error,
    ensures run(Entry::Optimized,e,a,vs).outcome==run(Entry::Client,prepare(Entry::Optimized,e,a,vs[1]).engine,a,vs).outcome,
{reveal_with_fuel(run,2);}
pub proof fn theorem_primary_width_fault_does_not_fallback(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell,f:Fault)
    requires vs.len()==3,qliteral(a.query),prepare(Entry::Primary,e,a,vs[0]).gate==(Gate::Ready{Name:table,route,dtype:d}),vs[0].primary==Raw::Error(f),width_fault(f),
    ensures run(Entry::Primary,e,a,vs).outcome==Outcome::Error(diagnostic(a,vs[0],table).0),
        run(Entry::Primary,e,a,vs).trace.last()==Effect::DiagnosticRead(table,graph(vs[0].request)),
{reveal_with_fuel(run,1);}
pub proof fn lemma_all_shape_bad_drop(rows:Seq<ClientRow>,q:Query)
    requires forall|i:int|0<=i<rows.len() ==> #[trigger] shape_bad(q,rows[i].row.emb),
    ensures client_fold(rows,q).0.len()==0,client_fold(rows,q).1.len()==rows.len(),
    decreases rows.len(),
{if rows.len()>0{lemma_all_shape_bad_drop(rows.drop_first(),q);}}
pub proof fn theorem_seed_failure_passes_expansion_without_identity(e:Engine,a:Args,vs:Seq<Env>,table:Name,route:Option<Route>,d:Cell,id:Text,s:Stored,f:Fault)
    requires vs.len()==3,a.query==Query::Text(id),!json_width::literal(id),json_width::trim(id)==id,
        prepare(Entry::Primary,e,a,vs[0]).gate==(Gate::Ready{Name:table,route,dtype:d}),
        vs[0].seed==Raw::Rows(seq![s]),s.table==table,s.graph==graph(vs[0].request),s.id==Cell::Text(id),vs[0].primary==Raw::Error(f),!width_fault(f),
    ensures run(Entry::Primary,e,a,vs).outcome==run(Entry::Optimized,prepare(Entry::Primary,e,a,vs[0]).engine,Args{query:expanded(a.query,s),..a},vs).outcome,
{reveal_with_fuel(run,2);reveal_with_fuel(Seq::filter,2);assert(seeds(seq![s],table,graph(vs[0].request),id) =~= seq![s]);}
pub proof fn theorem_raw_literal_three_route_four_refuses(route:Option<Route>,c:catalog::Catalog)
    requires declared(route)==Some(4),
    ensures width_check(Query::Text(seq!['[','1',',','2',',','3',']']),route,c)==(Some(Error::Width{query:Some(3),stored:Some(4)}),0),
{json_width::theorem_numeric_outer_counts();}

}
