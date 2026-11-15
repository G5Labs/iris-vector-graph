#[path="../temporal_window_reader/temporal_window_reader.rs"]
pub mod paging;
use vstd::prelude::*;
verus! {
broadcast use vstd::set_lib::group_set_lib_default;
pub type Key=(nat,int,int,Seq<char>,Seq<char>,Seq<char>,Seq<char>);
pub type Edge=(int,int,Seq<char>,Seq<char>,Seq<char>); // graph,timestamp,source,predicate,target
pub enum Scalar { Number(int), NumericText(int), Text(int) }
pub type Global=Map<Key,Scalar>;
pub open spec fn encode_scalar(v:Scalar) -> Scalar {
    match v {Scalar::Number(n)=>Scalar::NumericText(n),_=>v}
}
pub open spec fn weight_value(v:Scalar) -> Option<int> {
    match v {Scalar::Number(n)|Scalar::NumericText(n)=>Some(n),_=>None}
}
pub open spec fn out(e:Edge) -> Key {(0,e.0,e.1,e.2,e.3,e.4,seq![])}
pub open spec fn inbound(e:Edge) -> Key {(1,e.0,e.1,e.4,e.3,e.2,seq![])}
pub open spec fn prop(e:Edge,a:Seq<char>) -> Key {(2,e.0,e.1,e.2,e.3,e.4,a)}
pub open spec fn same_event(k:Key,e:Edge) -> bool {k.1==e.0 && k.2==e.1 && k.3==e.2 && k.4==e.3 && k.5==e.4}
pub open spec fn insert(s:Global,e:Edge,w:int,attrs:Map<Seq<char>,Scalar>,reverse:bool) -> Global {
    if s.contains_key(out(e)){s}else{
        let b=s.insert(out(e),Scalar::Number(w));
        let b=if reverse {b.insert(inbound(e),Scalar::Number(w))} else {b};
        Map::new(b.dom().union(attrs.dom().map_by(|a:Seq<char>|prop(e,a),|k:Key|k.6)),
            |k:Key| if k.0==2 && same_event(k,e) && attrs.contains_key(k.6) {attrs[k.6]}else{b[k]})
    }
}
pub enum Line { Value{key:Key,value:Scalar}, Malformed }
pub struct Imported {pub state:Global,pub applied:nat}
pub open spec fn captured(k:Key,stores:Set<nat>,zero_start:bool) -> bool {
    stores.contains(k.0) && (!zero_start || (k.1>0 && k.2>0))
}
pub open spec fn export(s:Global,keys:Seq<Key>,stores:Set<nat>,zero_start:bool) -> Seq<Line>
    decreases keys.len(),
{if keys.len()==0{seq![]}else{
    let tail=export(s,keys.drop_first(),stores,zero_start);
    if s.contains_key(keys[0]) && captured(keys[0],stores,zero_start) {
        seq![Line::Value{key:keys[0],value:encode_scalar(s[keys[0]])}]+tail
    }else{tail}
}}
pub open spec fn apply(s:Global,line:Line,rejected:Set<Key>) -> Imported {
    match line {
        Line::Malformed=>Imported{state:s,applied:0},
        Line::Value{key,value}=>if rejected.contains(key){Imported{state:s,applied:0}}
            else{Imported{state:s.insert(key,value),applied:1}},
    }
}
pub open spec fn import(s:Global,lines:Seq<Line>,rejected:Set<Key>) -> Imported
    decreases lines.len(),
{if lines.len()==0{Imported{state:s,applied:0}}else{
    let one=apply(s,lines[0],rejected);let rest=import(one.state,lines.drop_first(),rejected);
    Imported{state:rest.state,applied:one.applied+rest.applied}
}}
pub open spec fn current_layout() -> Seq<char> {seq!['g','r','a','p','h','-','s','c','o','p','e','d']}
pub struct Restored {pub state:Global,pub refused:bool,pub applied:nat,pub failed_rows:nat}
pub open spec fn restore(s:Global,lines:Seq<Line>,layout:Option<Seq<char>>,merge:bool,rejected:Set<Key>) -> Restored {
    if layout.is_some() && layout.unwrap()!=current_layout(){Restored{state:s,refused:true,applied:0,failed_rows:0}}
    else {let r=import(if merge{s}else{Map::empty()},lines,rejected);
        Restored{state:r.state,refused:false,applied:r.applied,failed_rows:0}}
}
pub open spec fn weight(s:Global,e:Edge,reverse:bool,g:int,lo:int,hi:int,args:paging::Args) -> Option<int> {
    let k=if reverse{inbound(e)}else{out(e)};
    if e.0==g && lo<=e.1 && e.1<=hi && s.contains_key(k)
        && paging::server_admits(paging::window_spec(args),if reverse{e.4}else{e.2}) {weight_value(s[k])}else{None}
}
pub open spec fn attrs(s:Global,e:Edge) -> Map<Seq<char>,Scalar> {
    Map::new(s.dom().filter(|k:Key|k.0==2 && same_event(k,e)).map_by(|k:Key|k.6,|a:Seq<char>|prop(e,a)),|a:Seq<char>|s[prop(e,a)])
}
pub proof fn theorem_writer_derives_direction_and_attrs(s:Global,e:Edge,w:int,a:Map<Seq<char>,Scalar>,field:Seq<char>)
    requires !s.contains_key(out(e)),a.contains_key(field),
    ensures insert(s,e,w,a,true)[out(e)]==Scalar::Number(w),insert(s,e,w,a,true)[inbound(e)]==Scalar::Number(w),
        attrs(insert(s,e,w,a,true),e)[field]==a[field],
{}
pub proof fn theorem_collision_changes_nothing(s:Global,e:Edge,w:int,a:Map<Seq<char>,Scalar>,reverse:bool)
    requires s.contains_key(out(e)),
    ensures insert(s,e,w,a,reverse)==s,
{}
pub proof fn lemma_export_import_key(src:Global,dst:Global,keys:Seq<Key>,stores:Set<nat>,k:Key)
    requires src.contains_key(k),stores.contains(k.0),
        keys.contains(k) || (dst.contains_key(k) && dst[k]==encode_scalar(src[k])),
    ensures import(dst,export(src,keys,stores,false),Set::empty()).state.contains_key(k),
        import(dst,export(src,keys,stores,false),Set::empty()).state[k]==encode_scalar(src[k]),
    decreases keys.len(),
{
    if keys.len()>0 {
        let head=keys[0];let next=if src.contains_key(head) && captured(head,stores,false){dst.insert(head,encode_scalar(src[head]))}else{dst};
        if head==k {assert(next.contains_key(k));assert(next[k]==encode_scalar(src[k]));}
        if head!=k && keys.contains(k) {
            let i=choose|i:int|0<=i<keys.len() && keys[i]==k;
            assert(i>0);assert(keys.drop_first()[i-1]==k);assert(keys.drop_first().contains(k));
        }
        lemma_export_import_key(src,next,keys.drop_first(),stores,k);
        let tail=export(src,keys.drop_first(),stores,false);
        if src.contains_key(head) && captured(head,stores,false) {
            let line=Line::Value{key:head,value:encode_scalar(src[head])};
            assert((seq![line]+tail).drop_first() =~= tail);
            assert(import(dst,export(src,keys,stores,false),Set::empty()).state==import(next,tail,Set::empty()).state);
        }
    }
}
pub proof fn theorem_restore_reaches_window(src:Global,keys:Seq<Key>,stores:Set<nat>,e:Edge,g:int,lo:int,hi:int,reverse:bool)
    requires e.0==g,lo<=e.1,e.1<=hi,
        src.contains_key(if reverse{inbound(e)}else{out(e)}),
        keys.contains(if reverse{inbound(e)}else{out(e)}),stores.contains(if reverse{1nat}else{0nat}),
    ensures weight(restore(Map::empty(),export(src,keys,stores,false),Some(current_layout()),false,Set::empty()).state,e,reverse,g,lo,hi,paging::plain(None))
        ==weight_value(src[if reverse{inbound(e)}else{out(e)}]),
{
    let k=if reverse{inbound(e)}else{out(e)};
    lemma_export_import_key(src,Map::empty(),keys,stores,k);
}
pub proof fn theorem_restore_attrs(src:Global,keys:Seq<Key>,stores:Set<nat>,e:Edge,a:Seq<char>)
    requires src.contains_key(prop(e,a)),keys.contains(prop(e,a)),stores.contains(2nat),
    ensures attrs(restore(Map::empty(),export(src,keys,stores,false),Some(current_layout()),false,Set::empty()).state,e)[a]==encode_scalar(src[prop(e,a)]),
{lemma_export_import_key(src,Map::empty(),keys,stores,prop(e,a));}
pub proof fn theorem_zero_graph_epoch_is_preserved(e:Edge,w:int)
    requires e.0==0,e.1==0,e.2.len()>0,
    ensures weight(restore(Map::empty(),export(map![out(e)=>Scalar::Number(w)],seq![out(e)],set![0nat],false),Some(current_layout()),false,Set::empty()).state,
        e,false,0,0,0,paging::plain(None))==Some(w),
{reveal_with_fuel(export,2);reveal_with_fuel(import,2);}
pub proof fn theorem_wrong_graph_and_empty_sources(s:Global,e:Edge,g:int)
    requires g!=e.0,
    ensures weight(s,e,false,g,e.1,e.1,paging::plain(None))==None,
        weight(s,e,false,e.0,e.1,e.1,paging::plain(Some(seq![])))==None,
{}
pub proof fn theorem_layout_refuses_before_erasure(s:Global,lines:Seq<Line>,merge:bool,rejected:Set<Key>,declared:Seq<char>)
    requires declared!=current_layout(),
    ensures restore(s,lines,Some(declared),merge,rejected).refused,
        restore(s,lines,Some(declared),merge,rejected).state==s,
        !restore(s,lines,None,merge,rejected).refused,
{}
pub proof fn theorem_swallowed_line_is_not_reported(k:Key,good:Key,v:Scalar)
    requires k!=good,
    ensures ({let r=restore(Map::empty(),seq![Line::Value{key:good,value:v},Line::Value{key:k,value:v}],Some(current_layout()),false,set![k]);
        !r.refused && r.applied==1 && r.failed_rows==0 && r.state.contains_key(good) && !r.state.contains_key(k)}),
{reveal_with_fuel(import,3);}
pub proof fn theorem_numeric_attribute_becomes_text(e:Edge,a:Seq<char>,n:int)
    ensures attrs(restore(Map::empty(),export(map![prop(e,a)=>Scalar::Number(n)],seq![prop(e,a)],set![2nat],false),Some(current_layout()),false,Set::empty()).state,e)[a]==Scalar::NumericText(n),
        Scalar::NumericText(n)!=Scalar::Number(n),
{reveal_with_fuel(export,2);reveal_with_fuel(import,2);}
pub proof fn theorem_text_attribute_preserved(e:Edge,a:Seq<char>,v:int)
    ensures attrs(restore(Map::empty(),export(map![prop(e,a)=>Scalar::Text(v)],seq![prop(e,a)],set![2nat],false),Some(current_layout()),false,Set::empty()).state,e)[a]==Scalar::Text(v),
{reveal_with_fuel(export,2);reveal_with_fuel(import,2);}

// Native API provider contract: complete finite leaf enumeration. The desired
// key is derived from source state, not supplied by the query caller.
pub open spec fn export_temporal(src:Global) -> Seq<Line> {
    export(src,src.dom().to_seq(),set![0nat,1nat,2nat],false)
}
pub proof fn theorem_complete_source_reaches_window(src:Global,e:Edge,reverse:bool,lo:int,hi:int)
    requires src.contains_key(if reverse{inbound(e)}else{out(e)}),lo<=e.1,e.1<=hi,
    ensures weight(restore(Map::empty(),export_temporal(src),Some(current_layout()),false,Set::empty()).state,e,reverse,e.0,lo,hi,paging::plain(None))
        ==weight_value(src[if reverse{inbound(e)}else{out(e)}]),
{
    src.dom().lemma_to_seq_to_set_id();
    assert(src.dom().to_seq().contains(if reverse{inbound(e)}else{out(e)}));
    theorem_restore_reaches_window(src,src.dom().to_seq(),set![0nat,1nat,2nat],e,e.0,lo,hi,reverse);
}
pub proof fn theorem_actual_writer_restore_window(s:Global,e:Edge,w:int,a:Map<Seq<char>,Scalar>,reverse:bool)
    requires !s.contains_key(out(e)),
    ensures weight(restore(Map::empty(),export_temporal(insert(s,e,w,a,reverse)),Some(current_layout()),false,Set::empty()).state,e,false,e.0,e.1,e.1,paging::plain(None))==Some(w),
{
    let src=insert(s,e,w,a,reverse);assert(src.contains_key(out(e)));assert(src[out(e)]==Scalar::Number(w));
    theorem_complete_source_reaches_window(src,e,false,e.1,e.1);
}

}
