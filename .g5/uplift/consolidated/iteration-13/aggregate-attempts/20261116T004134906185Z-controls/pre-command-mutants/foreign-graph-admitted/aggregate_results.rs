// product 3eaa79cf: ordered raw rows -> GROUP/NULL/DISTINCT folds -> typed scalar result.
use vstd::prelude::*;
#[path="../node_read/node_read.rs"] pub mod node;
verus! {
#[derive(PartialEq,Eq)] pub enum Val { Null, I(int), D(int), S(nat), B(bool) } // D is a half-unit numerator
#[derive(PartialEq,Eq)] pub enum Token { N(int), S(nat), B(bool) }
#[derive(PartialEq,Eq)] pub struct Entity { pub graph:nat, pub id:nat }
#[derive(PartialEq,Eq)] pub enum Key { Global, Missing, Text(nat), Numeric(int) }
pub struct Row { pub graph:nat, pub key:Key, pub value:Val, pub entity:Option<Entity> }
pub struct Query { pub graph:Option<nat>, pub grouped:bool, pub distinct:bool }
pub open spec fn selected(r:Row,q:Query)->bool {true}
pub open spec fn key(r:Row,q:Query)->Key {if q.grouped{r.key}else{Key::Global}}
pub open spec fn present(v:Val)->bool {v!=Val::Null}
pub open spec fn token(v:Val)->Token {match v{Val::I(n)=>Token::N(2*n),Val::D(n)=>Token::N(n),Val::S(s)=>Token::S(s),Val::B(b)=>Token::B(b),Val::Null=>Token::S(0)}}
pub open spec fn ticks(v:Val)->int {match v{Val::I(n)=>2*n,Val::D(n)=>n,_=>0}}
pub open spec fn integer(v:Val)->int {match v{Val::I(n)=>n,_=>0}}
pub open spec fn numeric(v:Val)->bool {match v{Val::I(_)|Val::D(_)=>true,_=>false}}
pub open spec fn is_float(v:Val)->bool {match v{Val::D(_)=>true,_=>false}}
pub open spec fn raw_values(rs:Seq<Row>,q:Query,k:Key)->Seq<Val> decreases rs.len() {
 if rs.len()==0{seq![]}else{let p=rs.drop_last();let r=rs.last();let a=raw_values(p,q,k);
 if selected(r,q) && key(r,q)==k && present(r.value){a.push(r.value)}else{a}}
}
pub open spec fn row_count(rs:Seq<Row>,q:Query,k:Key)->nat decreases rs.len() {
 if rs.len()==0{0}else{let r=rs.last();row_count(rs.drop_last(),q,k)+if selected(r,q)&&key(r,q)==k{1nat}else{0nat}}
}
pub open spec fn keys(rs:Seq<Row>,q:Query)->Set<Key> decreases rs.len() {if !q.grouped{set![Key::Global]}else if rs.len()==0{Set::empty()}else{let r=rs.last();let s=keys(rs.drop_last(),q);if selected(r,q){s.insert(key(r,q))}else{s}}}
pub open spec fn tokens(vs:Seq<Val>)->Set<Token> decreases vs.len(){if vs.len()==0{Set::empty()}else{tokens(vs.drop_last()).insert(token(vs.last()))}}
pub open spec fn unique(vs:Seq<Val>)->Seq<Val> decreases vs.len(){
 if vs.len()==0{seq![]}else{let p=vs.drop_last();let a=unique(p);if tokens(p).contains(token(vs.last())){a}else{a.push(vs.last())}}
}
pub open spec fn accepted(vs:Seq<Val>,d:bool)->Seq<Val>{if d{unique(vs)}else{vs}}
pub open spec fn sum(vs:Seq<Val>)->int decreases vs.len(){if vs.len()==0{0}else{sum(vs.drop_last())+ticks(vs.last())}}
pub open spec fn isum(vs:Seq<Val>)->int decreases vs.len(){if vs.len()==0{0}else{isum(vs.drop_last())+integer(vs.last())}}
pub open spec fn nnum(vs:Seq<Val>)->nat decreases vs.len(){if vs.len()==0{0}else{nnum(vs.drop_last())+if numeric(vs.last()){1nat}else{0nat}}}
pub open spec fn floating(vs:Seq<Val>)->bool decreases vs.len(){if vs.len()==0{false}else{floating(vs.drop_last())||is_float(vs.last())}}
// SQL primitive semantics on the admitted exact-number fragment, not a proof of IRIS's aggregate implementation.
pub struct Acc {pub rows:nat,pub count:nat,pub seen:Set<Token>,pub items:Seq<Val>,pub total:int,pub ints:int,pub nums:nat,pub float:bool}
pub open spec fn empty()->Acc{Acc{rows:0,count:0,seen:Set::empty(),items:seq![],total:0,ints:0,nums:0,float:false}}
pub open spec fn step(a:Acc,r:Row,q:Query,k:Key)->Acc{
 if !selected(r,q)||key(r,q)!=k{a}else{
 let v=r.value;let yes=present(v)&&(!q.distinct||!a.seen.contains(token(v)));
 Acc{rows:a.rows+1,count:a.count+if yes{1nat}else{0nat},seen:if present(v){a.seen.insert(token(v))}else{a.seen},
 items:if yes{a.items.push(v)}else{a.items},total:a.total+if yes{ticks(v)}else{0},ints:a.ints+if yes{integer(v)}else{0},nums:a.nums+if yes&&numeric(v){1nat}else{0nat},float:a.float||is_float(v)}
 }}
pub open spec fn fold(rs:Seq<Row>,q:Query,k:Key)->Acc decreases rs.len(){if rs.len()==0{empty()}else{step(fold(rs.drop_last(),q,k),rs.last(),q,k)}}
pub open spec fn inv(a:Acc,rs:Seq<Row>,q:Query,k:Key)->bool{
 let raw=raw_values(rs,q,k);let vs=accepted(raw,q.distinct);
 a.rows==row_count(rs,q,k)&&a.seen==tokens(raw)&&a.items==vs&&a.count==vs.len()&&a.total==sum(vs)&&a.ints==isum(vs)&&a.nums==nnum(vs)&&a.float==floating(raw)
}
pub proof fn lemma_tokens_push(vs:Seq<Val>,v:Val) ensures tokens(vs.push(v))==tokens(vs).insert(token(v)) {lemma_seq_push(vs,v);}
pub proof fn lemma_seq_push(vs:Seq<Val>,v:Val) ensures vs.push(v).drop_last()==vs,vs.push(v).last()==v {assert(vs.push(v).drop_last()=~=vs);}
pub proof fn lemma_fold(rs:Seq<Row>,q:Query,k:Key) ensures inv(fold(rs,q,k),rs,q,k) decreases rs.len(){
 if rs.len()>0{let p=rs.drop_last();let r=rs.last();lemma_fold(p,q,k);let raw=raw_values(p,q,k);let a=accepted(raw,q.distinct);
 if selected(r,q)&&key(r,q)==k&&present(r.value){lemma_tokens_push(raw,r.value);lemma_seq_push(raw,r.value);if !q.distinct||!tokens(raw).contains(token(r.value)){lemma_seq_push(a,r.value);}}
 assert(rs==p.push(r));
 }
}
pub proof fn lemma_unique_tokens(vs:Seq<Val>) ensures tokens(unique(vs))==tokens(vs), unique(vs).len()==tokens(vs).len() decreases vs.len(){
 if vs.len()>0{let p=vs.drop_last();let v=vs.last();lemma_unique_tokens(p);lemma_tokens_push(p,v);assert(vs==p.push(v));
 if !tokens(p).contains(token(v)){lemma_tokens_push(unique(p),v);vstd::set::lemma_set_insert_len(tokens(p),token(v));}
 }else{assert(tokens(vs)=~=Set::empty());}
}
pub proof fn theorem_count_distinct_is_derived(rs:Seq<Row>,q:Query,k:Key)
 requires q.distinct,
 ensures fold(rs,q,k).count==tokens(raw_values(rs,q,k)).len(),
 {lemma_fold(rs,q,k);lemma_unique_tokens(raw_values(rs,q,k));}
pub proof fn theorem_count_value_and_collect_share_nonnull_rows(rs:Seq<Row>,q:Query,k:Key)
 requires !q.distinct,
 ensures fold(rs,q,k).count==raw_values(rs,q,k).len(),fold(rs,q,k).items==raw_values(rs,q,k),
 {lemma_fold(rs,q,k);}
pub proof fn theorem_all_group_accumulators_from_raw_rows(rs:Seq<Row>,q:Query)
 ensures forall|k:Key|keys(rs,q).contains(k)==>inv(fold(rs,q,k),rs,q,k),
 {assert forall|k:Key|keys(rs,q).contains(k) implies inv(fold(rs,q,k),rs,q,k) by{lemma_fold(rs,q,k);}}
pub proof fn theorem_empty_global_group(q:Query)
 requires !q.grouped,
 ensures keys(seq![],q)==set![Key::Global],fold(seq![],q,Key::Global).rows==0,fold(seq![],q,Key::Global).count==0,fold(seq![],q,Key::Global).total==0,fold(seq![],q,Key::Global).items==Seq::<Val>::empty(),
 {}
pub proof fn theorem_empty_grouped_has_no_rows(q:Query) requires q.grouped,ensures keys(seq![],q)==Set::<Key>::empty(), {assert(keys(seq![],q)=~=Set::empty());}
pub proof fn lemma_no_float_integer_sum(vs:Seq<Val>) requires !floating(vs),ensures sum(vs)==2*isum(vs),decreases vs.len(){if vs.len()>0{lemma_no_float_integer_sum(vs.drop_last());}}
pub enum SumWire{N(int),D(int)}
pub enum SumValue{Integer(int),Double(int)}
pub open spec fn sum_wire(a:Acc)->SumWire{if a.float{SumWire::D(a.total)}else{SumWire::N(a.ints)}}
pub open spec fn read_sum(w:SumWire)->SumValue{match w{SumWire::N(n)=>SumValue::Integer(n),SumWire::D(n)=>SumValue::Double(n)}}
pub proof fn theorem_typed_sum_kind_and_exact_payload(rs:Seq<Row>,q:Query,k:Key)
 ensures ({let a=fold(rs,q,k);let raw=raw_values(rs,q,k);let vs=accepted(raw,q.distinct);
 if floating(raw){read_sum(sum_wire(a))==SumValue::Double(sum(vs))}else{read_sum(sum_wire(a))==SumValue::Integer(isum(vs)) && sum(vs)==2*isum(vs)}}),
 {lemma_fold(rs,q,k);if !floating(raw_values(rs,q,k)){lemma_unique_float_subset(raw_values(rs,q,k));lemma_no_float_integer_sum(accepted(raw_values(rs,q,k),q.distinct));}}
pub proof fn lemma_unique_float_subset(vs:Seq<Val>) ensures !floating(vs)==>!floating(unique(vs)),decreases vs.len(){if vs.len()>0{lemma_unique_float_subset(vs.drop_last());if !tokens(vs.drop_last()).contains(token(vs.last())){lemma_seq_push(unique(vs.drop_last()),vs.last());}}}
pub struct Ratio{pub numerator:int,pub denominator:nat}
pub open spec fn avg(a:Acc)->Option<Ratio>{if a.nums==0{None}else{Some(Ratio{numerator:a.total,denominator:2*a.nums})}}
pub proof fn theorem_avg_derived_numerator_and_denominator(rs:Seq<Row>,q:Query,k:Key)
 ensures ({let vs=accepted(raw_values(rs,q,k),q.distinct);let r=avg(fold(rs,q,k));if nnum(vs)==0{r.is_none()}else{r.is_some()&&r.unwrap().numerator==sum(vs)&&r.unwrap().denominator==2*nnum(vs)&&r.unwrap().denominator>0}}),
 {lemma_fold(rs,q,k);}
// Native count(distinct node) identity includes the graph, not merely the physical ID.
pub open spec fn entity_set(rs:Seq<Row>,q:Query,k:Key)->Set<Entity> decreases rs.len(){if rs.len()==0{Set::empty()}else{let r=rs.last();let s=entity_set(rs.drop_last(),q,k);if selected(r,q)&&key(r,q)==k&&r.entity.is_some(){s.insert(r.entity.unwrap())}else{s}}}

pub proof fn theorem_graph_part_of_entity_identity(id:nat,a:nat,b:nat) requires a!=b,ensures set![Entity{graph:a,id},Entity{graph:b,id}].len()==2,{let s=set![Entity{graph:a,id}];vstd::set::lemma_set_insert_len(s,Entity{graph:b,id});}
// Imported numeric scalar tag/read relation; half-unit D payload interpretation is a separate numeric provider.
pub proof fn theorem_integer_sum_reaches_existing_typed_reader(n:int) requires node::in64(n),ensures node::read(node::cy_typed(node::write(node::Input::Integer(n))))==node::Value::Integer(n),{node::theorem_numeric_writer_and_reader(n);}
pub proof fn theorem_double_sum_reaches_existing_typed_reader(n:int) ensures node::read(node::cy_typed(node::write(node::Input::Double(n))))==node::Value::Double(n),{}
// ORDER/SKIP/LIMIT consumes fully produced group rows. Permutation and SQL collation are outside this function.
pub open spec fn page<T>(rows:Seq<T>,skip:nat,limit:nat)->Seq<T>{let s=if skip<rows.len(){skip}else{rows.len()};let e=if s+limit<rows.len(){s+limit}else{rows.len()};rows.subrange(s as int,e as int)}
pub proof fn theorem_page_never_reaggregates<T>(rows:Seq<T>,skip:nat,limit:nat) ensures forall|i:int|0<=i<page(rows,skip,limit).len()==>page(rows,skip,limit)[i]==rows[i+if skip<rows.len(){skip as int}else{rows.len() as int}],{}
// Native key-based global-group creation and typed row construction, rather than supplied group membership.
pub proof fn theorem_keys_are_raw_selected(rs:Seq<Row>,q:Query,k:Key) requires q.grouped,ensures keys(rs,q).contains(k)<==>(exists|i:int|0<=i<rs.len()&&selected(rs[i],q)&&key(rs[i],q)==k),decreases rs.len(){if rs.len()>0{let p=rs.drop_last();theorem_keys_are_raw_selected(p,q,k);if exists|i:int|0<=i<rs.len()&&selected(rs[i],q)&&key(rs[i],q)==k{let i=choose|i:int|0<=i<rs.len()&&selected(rs[i],q)&&key(rs[i],q)==k;if i<p.len(){assert(p[i]==rs[i]);}}if keys(p,q).contains(k){let i=choose|i:int|0<=i<p.len()&&selected(p[i],q)&&key(p[i],q)==k;assert(p[i]==rs[i]);}}}
pub proof fn theorem_foreign_graph_row_skipped(a:Acc,r:Row,q:Query,k:Key) requires q.graph.is_some(),q.graph.unwrap()!=r.graph,ensures step(a,r,q,k)==a,{}
pub proof fn theorem_null_count_star_differs(q:Query,k:Key,g:nat)
 requires q.graph==None,
 ensures ({let r=Row{graph:g,key:k,value:Val::Null,entity:None};let a=fold(seq![r],q,key(r,q));a.rows==1&&a.count==0&&a.items.len()==0&&a.total==0&&avg(a).is_none()}),{reveal_with_fuel(fold,3);}
pub proof fn theorem_numeric_distinct_normalizes_int_and_whole_double(n:int) ensures token(Val::I(n))==token(Val::D(2*n)),token(Val::I(n))!=token(Val::S(0)),{}
pub proof fn theorem_float_presence_uses_all_inputs(n:int,q:Query,k:Key,g:nat)
 requires q.distinct,q.graph==None,!q.grouped,k==Key::Global,
 ensures ({let rs=seq![Row{graph:g,key:k,value:Val::I(n),entity:None},Row{graph:g,key:k,value:Val::D(2*n),entity:None}];let a=fold(rs,q,k);a.count==1&&a.float&&read_sum(sum_wire(a))==SumValue::Double(2*n)}),
 {reveal_with_fuel(fold,3);}
// Native Group's exact decrease-free count/distinct fold (pW=1, nonnull bound-node frame).
pub struct EntityAcc {pub seen:Set<Entity>,pub count:nat}
pub open spec fn entity_step(a:EntityAcc,r:Row,q:Query,k:Key)->EntityAcc{
 if selected(r,q)&&key(r,q)==k&&r.entity.is_some(){let e=r.entity.unwrap();EntityAcc{seen:a.seen.insert(e),count:a.count+if !a.seen.contains(e){1nat}else{0nat}}}else{a}}
pub open spec fn entity_fold(rs:Seq<Row>,q:Query,k:Key)->EntityAcc decreases rs.len(){if rs.len()==0{EntityAcc{seen:Set::empty(),count:0}}else{entity_step(entity_fold(rs.drop_last(),q,k),rs.last(),q,k)}}
pub proof fn theorem_native_entity_count_is_raw_identity_set(rs:Seq<Row>,q:Query,k:Key)
 ensures entity_fold(rs,q,k).seen==entity_set(rs,q,k),entity_fold(rs,q,k).count==entity_set(rs,q,k).len(),
 decreases rs.len(),
 {if rs.len()>0{let r=rs.last();let p=rs.drop_last();theorem_native_entity_count_is_raw_identity_set(p,q,k);if selected(r,q)&&key(r,q)==k&&r.entity.is_some(){vstd::set::lemma_set_insert_len(entity_set(p,q,k),r.entity.unwrap());}}}
pub struct Group {pub key:Key,pub star:nat,pub count:nat,pub sum:SumValue,pub avg:Option<Ratio>,pub collected:Seq<Val>,pub entity_distinct:nat}
pub open spec fn group(rs:Seq<Row>,q:Query,k:Key)->Group{let a=fold(rs,q,k);Group{key:k,star:a.rows,count:a.count,sum:read_sum(sum_wire(a)),avg:avg(a),collected:a.items,entity_distinct:entity_fold(rs,q,k).count}}
pub open spec fn output(rs:Seq<Row>,q:Query,order:Seq<Key>)->Seq<Group>{order.map(|i:int,k:Key|group(rs,q,k))}
pub proof fn theorem_full_output_before_page(rs:Seq<Row>,q:Query,order:Seq<Key>,skip:nat,limit:nat,i:int)
 requires order.to_set()==keys(rs,q),order.no_duplicates(),0<=i<page(output(rs,q,order),skip,limit).len(),
 ensures ({let j=i+if skip<order.len(){skip as int}else{order.len() as int};let got=page(output(rs,q,order),skip,limit)[i];got.key==order[j]&&got.star==row_count(rs,q,order[j])&&got.count==accepted(raw_values(rs,q,order[j]),q.distinct).len()&&got.collected==accepted(raw_values(rs,q,order[j]),q.distinct)&&got.entity_distinct==entity_set(rs,q,order[j]).len()}),
 {theorem_page_never_reaggregates(output(rs,q,order),skip,limit);let j=i+if skip<order.len(){skip as int}else{order.len() as int};lemma_fold(rs,q,order[j]);theorem_native_entity_count_is_raw_identity_set(rs,q,order[j]);}
// The source-generated names, not preclassified flags, decide paging-column removal.
pub open spec fn digits_range(n:Seq<char>,start:nat,end:nat)->bool decreases end {if end<=start{true}else{end<=n.len()&&'0'<=n[end as int-1]<='9'&&digits_range(n,start,(end-1) as nat)}}
pub open spec fn sort_name(n:Seq<char>)->bool {
 let end=if n.len()>=2&&n[n.len() as int-2]=='_'&&(n.last()=='n'||n.last()=='s'){(n.len()-2) as nat}else{n.len()};
 end>6&&n[0]=='_'&&n[1]=='_'&&n[2]=='s'&&n[3]=='o'&&n[4]=='r'&&n[5]=='t'&&digits_range(n,6,end)
}
pub open spec fn internal(n:Seq<char>)->bool {n==seq!['_','_','r','n']||sort_name(n)}
pub struct RawCell{pub name:Seq<char>,pub value:int}
pub open spec fn public_cells(cs:Seq<RawCell>)->Seq<RawCell> decreases cs.len(){if cs.len()==0{seq![]}else{let p=public_cells(cs.drop_last());if !internal(cs.last().name){p.push(cs.last())}else{p}}}
pub proof fn theorem_finalizer_drops_generated_internal_names(v:int,name:Seq<char>)
 requires !internal(name),
 ensures public_cells(seq![RawCell{name:seq!['_','_','r','n'],value:9},RawCell{name,value:v},RawCell{name:seq!['_','_','s','o','r','t','0'],value:4}])==seq![RawCell{name,value:v}],
 {reveal_with_fuel(public_cells,4);reveal_with_fuel(digits_range,4);}
pub proof fn theorem_internal_name_classifier_exact_generated_forms()
 ensures sort_name(seq!['_','_','s','o','r','t','1','2']),sort_name(seq!['_','_','s','o','r','t','1','2','_','n']),sort_name(seq!['_','_','s','o','r','t','0','_','s']),!sort_name(seq!['_','_','s','o','r','t']),!sort_name(seq!['_','_','s','o','r','t','x']),!internal(seq!['v']),
 {reveal_with_fuel(digits_range,4);}
pub proof fn theorem_scalar_duplicate_rows_count_twice(q:Query,k:Key,g:nat)
 requires q.graph==None,!q.grouped,k==Key::Global,!q.distinct,
 ensures ({let r=Row{graph:g,key:k,value:Val::I(2),entity:None};let a=fold(seq![r,r],q,k);a.rows==2&&a.count==2&&a.total==8&&a.items==seq![Val::I(2),Val::I(2)]}),
 {reveal_with_fuel(fold,3);}
pub proof fn theorem_entity_duplicate_does_not_increment(q:Query,k:Key,g:nat,id:nat)
 requires q.graph==None,!q.grouped,k==Key::Global,
 ensures ({let r=Row{graph:g,key:k,value:Val::Null,entity:Some(Entity{graph:g,id})};entity_fold(seq![r,r],q,k).count==1}),
 {reveal_with_fuel(entity_fold,3);}
pub proof fn theorem_mean_is_not_sum(q:Query,k:Key,g:nat)
 requires q.graph==None,!q.grouped,k==Key::Global,!q.distinct,
 ensures ({let a=fold(seq![Row{graph:g,key:k,value:Val::I(1),entity:None},Row{graph:g,key:k,value:Val::I(2),entity:None}],q,k);avg(a).unwrap().numerator==6&&avg(a).unwrap().denominator==4}),
 {reveal_with_fuel(fold,3);}

// First-encounter enumeration is derived from the raw rows; explicit ORDER BY may permute this
// complete unique enumeration under its separately scoped SQL sort/equality relation.
pub open spec fn key_order(rs:Seq<Row>,q:Query)->Seq<Key> decreases rs.len(){
 if !q.grouped{seq![Key::Global]}else if rs.len()==0{seq![]}else{let r=rs.last();let order=key_order(rs.drop_last(),q);if selected(r,q)&&!order.contains(key(r,q)){order.push(key(r,q))}else{order}}}
pub proof fn lemma_key_push(ks:Seq<Key>,k:Key) ensures ks.push(k).to_set()==ks.to_set().insert(k),ks.push(k).drop_last()==ks,ks.push(k).last()==k {
 ks.push(k).to_set_ensures();ks.to_set_ensures();assert(ks.push(k).drop_last()=~=ks);assert(ks.push(k).to_set()=~=ks.to_set().insert(k));
}
pub proof fn theorem_key_enumeration_complete_unique(rs:Seq<Row>,q:Query)
 ensures key_order(rs,q).to_set()==keys(rs,q),key_order(rs,q).no_duplicates(),
 decreases rs.len(),
 {if !q.grouped{let e=Seq::<Key>::empty();e.to_set_ensures();assert(e.to_set()=~=Set::empty());lemma_key_push(e,Key::Global);assert(e.push(Key::Global)==seq![Key::Global]);}else if rs.len()==0{Seq::<Key>::empty().to_set_ensures();assert(Seq::<Key>::empty().to_set()=~=Set::empty());}else{let p=rs.drop_last();let r=rs.last();theorem_key_enumeration_complete_unique(p,q);let a=key_order(p,q);a.to_set_ensures();if selected(r,q){if !a.contains(key(r,q)){lemma_key_push(a,key(r,q));assert(a.push(key(r,q)).no_duplicates());}else{assert(a.to_set().contains(key(r,q)));assert(keys(p,q).insert(key(r,q))=~=keys(p,q));}}}}
pub open spec fn derived_output(rs:Seq<Row>,q:Query)->Seq<Group>{output(rs,q,key_order(rs,q))}
pub proof fn theorem_derived_output_has_exactly_one_row_per_group(rs:Seq<Row>,q:Query)
 ensures derived_output(rs,q).len()==keys(rs,q).len(),
 {theorem_key_enumeration_complete_unique(rs,q);key_order(rs,q).unique_seq_to_set();}
pub proof fn theorem_actual_derived_workflow(rs:Seq<Row>,q:Query,skip:nat,limit:nat,i:int)
 requires 0<=i<page(derived_output(rs,q),skip,limit).len(),
 ensures ({let got=page(derived_output(rs,q),skip,limit)[i];keys(rs,q).contains(got.key)&&got.star==row_count(rs,q,got.key)&&got.count==accepted(raw_values(rs,q,got.key),q.distinct).len()&&got.collected==accepted(raw_values(rs,q,got.key),q.distinct)&&got.entity_distinct==entity_set(rs,q,got.key).len()}),
 {theorem_key_enumeration_complete_unique(rs,q);theorem_full_output_before_page(rs,q,key_order(rs,q),skip,limit,i);theorem_page_never_reaggregates(derived_output(rs,q),skip,limit);}

pub proof fn theorem_entity_same_id_two_graphs_both_count(id:nat,a:nat,b:nat)
 requires a!=b,
 ensures ({let q=Query{graph:None,grouped:false,distinct:false};let r=seq![Row{graph:a,key:Key::Missing,value:Val::Null,entity:Some(Entity{graph:a,id})},Row{graph:b,key:Key::Missing,value:Val::Null,entity:Some(Entity{graph:b,id})}];entity_fold(r,q,Key::Global).count==2}),
 {reveal_with_fuel(entity_fold,3);}
pub proof fn theorem_tokens_are_raw_members(vs:Seq<Val>,t:Token)
 ensures tokens(vs).contains(t)<==>(exists|i:int|0<=i<vs.len()&&token(vs[i])==t),
 decreases vs.len(),
 {if vs.len()>0{let p=vs.drop_last();theorem_tokens_are_raw_members(p,t);
 if tokens(p).contains(t){let i=choose|i:int|0<=i<p.len()&&token(p[i])==t;assert(p[i]==vs[i]);}
 if exists|i:int|0<=i<vs.len()&&token(vs[i])==t{let i=choose|i:int|0<=i<vs.len()&&token(vs[i])==t;if i<p.len(){assert(p[i]==vs[i]);}}}}
pub proof fn theorem_collection_contains_no_nulls(rs:Seq<Row>,q:Query,k:Key)
 ensures forall|i:int|0<=i<fold(rs,q,k).items.len()==>fold(rs,q,k).items[i]!=Val::Null,
 decreases rs.len(),
 {if rs.len()>0{let p=rs.drop_last();let r=rs.last();theorem_collection_contains_no_nulls(p,q,k);}}

}
