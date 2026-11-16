// History reader transcription. Text is a sequence of character codepoints.
// SQL comparison mode is a provider configuration; SqlUpperAscii represents its
// ASCII upper / trailing space+tab fragment only. JSON source parsing is outside
// the typed view projection; other SQL collation characters remain conditional.
use vstd::prelude::*;
use vstd::seq_lib::*;
use vstd::relations::*;
verus! {
pub enum Collation { Binary, SqlUpperAscii }
pub struct Row {
    pub seq:int,pub revision_id:Seq<int>,pub parent_id:Option<Seq<int>>,
    pub kind:Option<Seq<int>>,pub actor:Option<Seq<int>>,pub actor_type:Option<Seq<int>>,
    pub conn_user:Option<Seq<int>>,pub committed_ms:Option<int>,pub message:Option<Seq<int>>,
    pub source:Option<Seq<int>>,pub correlation_id:Option<Seq<int>>,pub idempotency_key:Option<Seq<int>>,pub op_count:Option<int>
}
pub struct Table {pub ids:Seq<int>,pub rows:Map<int,Row>,pub collation:Collation}
pub struct Params {pub after:int,pub after_truthy:bool,pub limit:int,pub descending:bool,
    pub actor:Option<Seq<int>>,pub actor_type:Option<Seq<int>>,pub since:Option<int>,pub until:Option<int>,
    pub correlation_id:Option<Seq<int>>,pub source:Option<Seq<int>>}
pub struct View {pub wire:Row,pub seq:int,pub committed_ms:int,pub op_count:int,
    pub parent_id:Option<Seq<int>>,pub message:Option<Seq<int>>,pub correlation_id:Option<Seq<int>>,pub idempotency_key:Option<Seq<int>>,
    pub kind:Seq<int>,pub actor:Seq<int>,pub actor_type:Seq<int>,pub conn_user:Seq<int>}
pub struct Page {pub revisions:Seq<View>,pub next:Option<int>}
pub enum Outcome {Page(Page), SqlRefused, QueryError, DecodeError}
pub enum Fault {None, Open, Execute, Fetch, Decode}
pub struct Attempt {pub outcome:Outcome,pub close_calls:nat}
pub enum CursorInput {Integer(int), IntegerText(int)}
pub open spec fn upper(s:Seq<int>) -> Seq<int> {
    s.map_values(|c:int| if 97<=c<=122 {c-32}else{c})
}
pub open spec fn trim_tail(s:Seq<int>) -> Seq<int>
    decreases s.len(),
{if s.len()>0 && (s[s.len()-1]==32 || s[s.len()-1]==9) {trim_tail(s.drop_last())}else{s}}
pub open spec fn text_eq(a:Seq<int>,b:Seq<int>,c:Collation) -> bool {
    match c {Collation::Binary=>a==b,Collation::SqlUpperAscii=>trim_tail(upper(a))==trim_tail(upper(b))}
}
pub open spec fn optional_match(value:Option<Seq<int>>,filter:Option<Seq<int>>,c:Collation) -> bool {
    filter.is_none() || (value.is_some() && text_eq(value.unwrap(),filter.unwrap(),c))
}
pub open spec fn matches(r:Row,p:Params,c:Collation) -> bool {
    (if p.descending {!p.after_truthy || r.seq<p.after}else{r.seq>p.after})
    && optional_match(r.actor,p.actor,c) && optional_match(r.actor_type,p.actor_type,c)
    && (p.since.is_none() || (r.committed_ms.is_some() && r.committed_ms.unwrap()>=p.since.unwrap()))
    && (p.until.is_none() || (r.committed_ms.is_some() && r.committed_ms.unwrap()<=p.until.unwrap()))
    && optional_match(r.correlation_id,p.correlation_id,c) && optional_match(r.source,p.source,c)
}
pub open spec fn less(desc:bool) -> spec_fn(int,int)->bool { |a:int,b:int| if desc {a>=b}else{a<=b} }
pub open spec fn admitted(t:Table,p:Params) -> Seq<int> { t.ids.filter(|id:int| matches(t.rows[id],p,t.collation)) }
pub open spec fn ordered(t:Table,p:Params) -> Seq<int> { admitted(t,p).sort_by(less(p.descending)) }
pub open spec fn prefix(ids:Seq<int>,limit:int) -> Seq<int> {
    ids.take(if limit<0 {0}else{if limit<ids.len(){limit}else{ids.len() as int}})
}
pub open spec fn selected(t:Table,p:Params) -> Seq<int> {prefix(ordered(t,p),p.limit)}
pub open spec fn nonempty(s:Option<Seq<int>>) -> Option<Seq<int>> {
    if s.is_some() && s.unwrap().len()>0 {s}else{None}
}
pub open spec fn stringify(s:Option<Seq<int>>) -> Seq<int> {s.unwrap_or(seq![78,111,110,101])}
pub open spec fn decode(r:Row) -> View {
    View{wire:r,seq:r.seq,committed_ms:r.committed_ms.unwrap_or(0),op_count:r.op_count.unwrap_or(0),
        parent_id:nonempty(r.parent_id),message:nonempty(r.message),correlation_id:nonempty(r.correlation_id),idempotency_key:nonempty(r.idempotency_key),
        kind:stringify(r.kind),actor:stringify(r.actor),actor_type:stringify(r.actor_type),conn_user:stringify(r.conn_user)}
}
pub open spec fn finish(rows:Seq<View>,limit:int) -> Page {
    Page{revisions:rows,next:if rows.len()>0 && rows.len()==limit {Some(rows[rows.len()-1].seq)}else{None}}
}
pub open spec fn history(t:Table,p:Params) -> Outcome {
    if p.limit<0 {Outcome::SqlRefused}else{Outcome::Page(finish(selected(t,p).map_values(|id:int|decode(t.rows[id])),p.limit))}
}
pub open spec fn attempt(t:Table,p:Params,fault:Fault) -> Attempt {
    if matches!(fault,Fault::Open) {Attempt{outcome:Outcome::QueryError,close_calls:0}}
    else {Attempt{outcome:if p.limit<0 {Outcome::SqlRefused}else{match fault {
        Fault::Execute|Fault::Fetch=>Outcome::QueryError,Fault::Decode=>Outcome::DecodeError,
        _=>history(t,p)}},close_calls:1}}
}
pub open spec fn defaults(limit:int,descending:bool,after:int) -> Params {
    Params{limit,descending,after,after_truthy:after!=0,actor:None,actor_type:None,since:None,until:None,correlation_id:None,source:None}
}
pub open spec fn cursor_input(p:Params,raw:CursorInput) -> Params {
    match raw {CursorInput::Integer(n)=>Params{after:n,after_truthy:n!=0,..p},
        CursorInput::IntegerText(n)=>Params{after:n,after_truthy:true,..p}}
}
pub open spec fn frame(t:Table) -> bool {
    t.ids.no_duplicates() && (forall|id:int| t.rows.contains_key(id)<==>t.ids.contains(id))
    && (forall|id:int| t.rows.contains_key(id)==>t.rows[id].seq==id)
}
pub proof fn lemma_integer_order(desc:bool)
    ensures total_ordering(less(desc)),
{}
pub proof fn theorem_filter_sort_preserves_matches(t:Table,p:Params)
    requires frame(t),
    ensures forall|i:int| 0<=i<ordered(t,p).len() ==> matches(t.rows[ordered(t,p)[i]],p,t.collation),
{
    lemma_integer_order(p.descending);
    let ids=admitted(t,p);ids.lemma_sort_by_ensures(less(p.descending));
    assert forall|i:int| 0<=i<ordered(t,p).len() implies matches(t.rows[ordered(t,p)[i]],p,t.collation) by {
        let id=ordered(t,p)[i];assert(ordered(t,p).contains(id));assert(ids.contains(id));
        let j=choose|j:int| 0<=j<ids.len() && ids[j]==id;
        t.ids.lemma_filter_pred(|id:int|matches(t.rows[id],p,t.collation),j);
    }
}
pub proof fn theorem_order_is_derived(t:Table,p:Params)
    ensures sorted_by(ordered(t,p),less(p.descending)),
        admitted(t,p).to_multiset()==ordered(t,p).to_multiset(),
{
    lemma_integer_order(p.descending);admitted(t,p).lemma_sort_by_ensures(less(p.descending));
}
pub proof fn lemma_sort_already_ordered(ids:Seq<int>,desc:bool)
    requires sorted_by(ids,less(desc)),
    ensures ids.sort_by(less(desc))==ids,
{
    lemma_integer_order(desc);ids.lemma_sort_by_ensures(less(desc));
    lemma_sorted_unique(ids.sort_by(less(desc)),ids,less(desc));
}
pub proof fn theorem_filter_happens_before_limit(t:Table)
    requires frame(t),t.ids==seq![1,2,3],t.rows.contains_key(1),t.rows.contains_key(2),t.rows.contains_key(3),t.rows[1].actor==Some(seq![66]),
        t.rows[2].actor==Some(seq![65]),t.rows[3].actor==Some(seq![65]),
    ensures selected(t,Params{actor:Some(seq![65]),..defaults(2,false,0)})==seq![2,3],
{
    let p=Params{actor:Some(seq![65]),..defaults(2,false,0)};
    assert(t.ids.contains(1));assert(t.ids.contains(2));assert(t.ids.contains(3));
    assert(upper(seq![65]) =~= seq![65]);assert(upper(seq![66]) =~= seq![66]);
    assert(seq![66int][0]!=seq![65int][0]);
    match t.collation {Collation::Binary=>{assert(!text_eq(seq![66],seq![65],t.collation));},
        Collation::SqlUpperAscii=>{assert(upper(seq![66])[0]!=upper(seq![65])[0]);assert(!text_eq(seq![66],seq![65],t.collation));}}
    assert(!text_eq(seq![66],seq![65],t.collation));
    assert(!optional_match(t.rows[1].actor,p.actor,t.collation));
    assert(!matches(t.rows[1],p,t.collation));assert(matches(t.rows[2],p,t.collation));assert(matches(t.rows[3],p,t.collation));
    assert(admitted(t,p)==seq![2,3]) by {reveal_with_fuel(Seq::filter,5);}
    lemma_sort_already_ordered(seq![2,3],false);
}
pub proof fn theorem_page_rows_pass_raw_filters(t:Table,p:Params)
    requires frame(t),p.limit>=0,
    ensures match history(t,p) {Outcome::Page(page)=>forall|i:int| 0<=i<page.revisions.len() ==> matches(page.revisions[i].wire,p,t.collation),_=>false},
{
    theorem_filter_sort_preserves_matches(t,p);
    assert forall|i:int| 0<=i<selected(t,p).len() implies matches(t.rows[selected(t,p)[i]],p,t.collation) by {
        assert(selected(t,p)[i]==ordered(t,p)[i]);
    }
}
pub proof fn theorem_page_length_and_decoded_sequence(t:Table,p:Params)
    requires frame(t),p.limit>=0,
    ensures match history(t,p) {Outcome::Page(page)=>
        page.revisions.len()==if p.limit<admitted(t,p).len(){p.limit as nat}else{admitted(t,p).len()}
        && (forall|i:int| 0<=i<page.revisions.len() ==> page.revisions[i].seq==selected(t,p)[i]),_=>false},
{
    theorem_order_is_derived(t,p);
    broadcast use group_to_multiset_ensures;
    ordered(t,p).to_multiset_ensures();admitted(t,p).to_multiset_ensures();
    assert(ordered(t,p).len()==admitted(t,p).len());
    assert forall|i:int| 0<=i<selected(t,p).len() implies decode(t.rows[selected(t,p)[i]]).seq==selected(t,p)[i] by {
        let id=selected(t,p)[i];assert(ordered(t,p).contains(id));
        let ids=admitted(t,p);lemma_integer_order(p.descending);ids.lemma_sort_by_ensures(less(p.descending));
        assert(ids.contains(id));let j=choose|j:int| 0<=j<ids.len() && ids[j]==id;
        t.ids.lemma_filter_contains_rev(|id:int|matches(t.rows[id],p,t.collation),id);
    }
}
pub proof fn theorem_direction_and_exclusive_cursor(r:Row,p:Params,c:Collation)
    ensures (!p.descending && r.seq<=p.after) ==> !matches(r,p,c),
        (p.descending && p.after_truthy && r.seq>=p.after) ==> !matches(r,p,c),
{}
pub proof fn theorem_empty_filter_is_not_omitted(c:Collation)
    ensures optional_match(None,None,c),!optional_match(None,Some(seq![]),c),
        optional_match(Some(seq![]),Some(seq![]),c),
{}
pub proof fn theorem_time_boundaries_are_inclusive(r:Row,p:Params,c:Collation)
    requires r.committed_ms==p.since,r.committed_ms==p.until,r.committed_ms.is_some(),
        p.after<r.seq,!p.descending,p.actor.is_none(),p.actor_type.is_none(),p.source.is_none(),p.correlation_id.is_none(),
    ensures matches(r,p,c),
{}
pub proof fn theorem_full_page_supplies_cursor(rows:Seq<View>,limit:int)
    requires rows.len()==limit,limit>0,
    ensures finish(rows,limit).next==Some(rows[rows.len()-1].seq),
{}
pub proof fn theorem_short_or_empty_page_ends(rows:Seq<View>,limit:int)
    requires rows.len()==0 || rows.len()<limit,
    ensures finish(rows,limit).next==None,
{}
pub proof fn theorem_after_last_is_empty(t:Table,p:Params)
    requires frame(t),p.limit>=0,!p.descending,
        forall|i:int| 0<=i<t.ids.len() ==> t.ids[i]<=p.after,
    ensures match history(t,p) {Outcome::Page(page)=>page.revisions.len()==0 && page.next==None,_=>false},
{
    assert(admitted(t,p)==seq![]) by {
        assert(admitted(t,p).len()==0) by {
            if admitted(t,p).len()>0 {
                t.ids.lemma_filter_pred(|id:int|matches(t.rows[id],p,t.collation),0);
                let id=admitted(t,p)[0];t.ids.lemma_filter_contains_rev(|id:int|matches(t.rows[id],p,t.collation),id);
                let i=choose|i:int| 0<=i<t.ids.len() && t.ids[i]==id;
            }
        }
        assert(admitted(t,p) =~= seq![]);
    }
    lemma_sort_already_ordered(seq![],p.descending);
}
pub proof fn theorem_zero_and_negative_limits(t:Table,p:Params)
    ensures (p.limit<0 ==> history(t,p)==Outcome::SqlRefused),
        (p.limit==0 ==> match history(t,p) {Outcome::Page(page)=>page.revisions.len()==0 && page.next==None,_=>false}),
{}
pub proof fn theorem_decode_normalizes_fields(r:Row)
    requires r.committed_ms.is_none(),r.op_count.is_none(),r.parent_id==Some(seq![]),r.message==Some(seq![]),r.actor.is_none(),
    ensures decode(r).seq==r.seq,decode(r).committed_ms==0,decode(r).op_count==0,
        decode(r).parent_id==None,decode(r).message==None,decode(r).actor==seq![78,111,110,101],
{}
pub proof fn theorem_sqlupper_ascii_neighbor()
    ensures text_eq(seq![80,108,97,110],seq![112,76,65,78],Collation::SqlUpperAscii),
        !text_eq(seq![80,108,97,110],seq![112,76,65,78],Collation::Binary),
{assert(upper(seq![80,108,97,110]) =~= upper(seq![112,76,65,78]));}
pub proof fn theorem_trailing_space_tab_neighbor(a:Seq<int>)
    ensures text_eq(a,a+seq![32,9],Collation::SqlUpperAscii),
{
    assert(upper(a+seq![32,9]) =~= upper(a)+seq![32,9]);
    assert((upper(a)+seq![32,9]).drop_last() =~= upper(a)+seq![32]);
    assert((upper(a)+seq![32]).drop_last() =~= upper(a));
    reveal_with_fuel(trim_tail,4);
}
pub proof fn theorem_failed_reader_never_becomes_empty(t:Table,p:Params)
    requires p.limit>=0,
    ensures attempt(t,p,Fault::Execute).outcome==Outcome::QueryError,
        attempt(t,p,Fault::Fetch).outcome==Outcome::QueryError,
        attempt(t,p,Fault::Decode).outcome==Outcome::DecodeError,
        attempt(t,p,Fault::Execute).close_calls==1,attempt(t,p,Fault::Decode).close_calls==1,
        attempt(t,p,Fault::Open).close_calls==0,
{}
pub proof fn theorem_raw_cursor_truthiness_precedes_conversion(r:Row,c:Collation)
    requires r.seq>0,
    ensures matches(r,cursor_input(defaults(2,true,0),CursorInput::Integer(0)),c),
        !matches(r,cursor_input(defaults(2,true,0),CursorInput::IntegerText(0)),c),
{}
}
