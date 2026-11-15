// As-built Bolt stream at 3eaa79cf. Specification transcription, not body proof.
use vstd::prelude::*;
verus! {
pub type Bytes = Seq<u8>;
pub open spec fn max_chunk() -> nat { 65535 }
pub open spec fn header(n:nat) -> Bytes { seq![(n / 256) as u8,(n % 256) as u8] }
pub open spec fn length(raw:Bytes) -> nat { (raw[0] as nat)*256 + raw[1] as nat }
pub open spec fn end() -> Bytes { seq![0u8,0u8] }
pub open spec fn drop(raw:Bytes,n:nat) -> Bytes {
    raw.subrange(if n<raw.len(){n as int}else{raw.len() as int},raw.len() as int)
}
pub struct Decoded {pub bodies:Seq<Bytes>,pub used:nat}
// Raw header bytes decide every payload slice. used is the last actual message
// boundary, not an oracle input. A partial trailing message is not emitted.
pub open spec fn scan(raw:Bytes,current:Bytes) -> Decoded
    decreases raw.len(),
{
    if raw.len()<2 {Decoded{bodies:seq![],used:0}}
    else {
        let n=length(raw);
        if n==0 {
            let tail=scan(drop(raw,2),seq![]);
            Decoded{bodies:seq![current]+tail.bodies,used:2+tail.used}
        } else if n+2>raw.len() {Decoded{bodies:seq![],used:0}}
        else {
            let tail=scan(drop(raw,n+2),current+raw.subrange(2,(n+2) as int));
            Decoded{bodies:tail.bodies,used:if tail.bodies.len()>0{n+2+tail.used}else{0}}
        }
    }
}
pub open spec fn decode(raw:Bytes) -> Decoded {scan(raw,seq![])}
pub open spec fn chunk_wire(body:Bytes,limit:nat) -> Bytes
    recommends limit>0,limit<=max_chunk(),
    decreases body.len(),
{
    if body.len()==0 || limit==0 {seq![]}
    else {let n=if body.len()<limit{body.len()}else{limit};
        header(n)+body.take(n as int)+chunk_wire(drop(body,n),limit)}
}
pub open spec fn encode(body:Bytes,limit:nat) -> Bytes {chunk_wire(body,limit)+end()}
pub open spec fn encoded_lengths(bodies:Seq<Bytes>) -> nat
    decreases bodies.len(),
{if bodies.len()==0{0}else{encode(bodies[0],max_chunk()).len()+encoded_lengths(bodies.drop_first())}}
pub struct Receive {pub buffer:Bytes,pub queue:Seq<Bytes>}
pub enum Read {NeedMore,Message(Bytes)}
pub struct Extracted {pub next:Receive,pub read:Read,pub received:bool,pub actual_used:nat,pub cut:nat}
pub open spec fn receive(s:Receive,arrival:Bytes) -> Extracted {
    if s.queue.len()>0 {
        Extracted{next:Receive{queue:s.queue.drop_first(),..s},read:Read::Message(s.queue[0]),received:false,actual_used:0,cut:0}
    }else{
        let raw=s.buffer+arrival;let d=decode(raw);
        if d.bodies.len()==0 {
            Extracted{next:Receive{buffer:raw,queue:seq![]},read:Read::NeedMore,received:true,actual_used:d.used,cut:0}
        }else{
            // The product re-encodes decoded bodies at DEFAULT chunk size.
            let cut=encoded_lengths(d.bodies);
            Extracted{next:Receive{buffer:drop(raw,cut),queue:d.bodies.drop_first()},read:Read::Message(d.bodies[0]),received:true,actual_used:d.used,cut}
        }
    }
}
pub open spec fn ws_continues(r:Read) -> bool {match r{Read::NeedMore=>true,Read::Message(body)=>body.len()>0}}
pub proof fn lemma_header(n:nat)
    requires n<=max_chunk(),
    ensures header(n).len()==2,length(header(n))==n,
{assert(n<65536);assert(n/256<=255);}
pub proof fn lemma_drop_concat(a:Bytes,b:Bytes)
    ensures drop(a+b,a.len())==b,
{assert(drop(a+b,a.len())=~=b);}
pub proof fn lemma_scan_chunk(body:Bytes,rest:Bytes,current:Bytes)
    requires 0<body.len()<=max_chunk(),
    ensures scan(header(body.len())+body+rest,current).bodies==scan(rest,current+body).bodies,
        scan(header(body.len())+body+rest,current).used==
            (if scan(rest,current+body).bodies.len()>0{body.len()+2+scan(rest,current+body).used}else{0}),
{
    lemma_header(body.len());let raw=header(body.len())+body+rest;
    assert(length(raw)==body.len());
    assert(raw.subrange(2,(body.len()+2) as int)=~=body);
    assert(drop(raw,body.len()+2)=~=rest);
}
pub proof fn lemma_scan_terminator(rest:Bytes,current:Bytes)
    ensures scan(end()+rest,current).bodies==seq![current]+decode(rest).bodies,
        scan(end()+rest,current).used==2+decode(rest).used,
{assert(drop(end()+rest,2)=~=rest);}
// This generic producer lemma covers ALL legal chunk limits and arbitrary body
// bytes, including multi-chunk bodies larger than one uint16 payload.
pub proof fn lemma_scan_encoded_prefix(body:Bytes,limit:nat,current:Bytes,rest:Bytes)
    requires 0<limit<=max_chunk(),
    ensures scan(encode(body,limit)+rest,current).bodies==seq![current+body]+decode(rest).bodies,
        scan(encode(body,limit)+rest,current).used==encode(body,limit).len()+decode(rest).used,
    decreases body.len(),
{
    if body.len()==0 {
        lemma_scan_terminator(rest,current);assert(current+body=~=current);
    }else{
        let n=if body.len()<limit{body.len()}else{limit};let prefix=body.take(n as int);let suffix=drop(body,n);
        assert(prefix.len()==n);assert(0<prefix.len()<=max_chunk());
        lemma_scan_encoded_prefix(suffix,limit,current+prefix,rest);
        lemma_scan_chunk(prefix,encode(suffix,limit)+rest,current);
        assert(encode(body,limit)+rest=~=header(n)+prefix+(encode(suffix,limit)+rest));
        assert(prefix+suffix=~=body);assert((current+prefix)+suffix=~=current+body);
    }
}
pub proof fn theorem_encoded_bytes_derive_body_and_consumed(body:Bytes,limit:nat)
    requires 0<limit<=max_chunk(),
    ensures decode(encode(body,limit)).bodies==seq![body],decode(encode(body,limit)).used==encode(body,limit).len(),
{
    lemma_scan_encoded_prefix(body,limit,seq![],seq![]);
    assert(encode(body,limit)+seq![]=~=encode(body,limit));assert(seq![]+body=~=body);
    assert(seq![body]+seq![]=~=seq![body]);
}
pub proof fn theorem_scan_boundary_within_buffer(raw:Bytes,current:Bytes)
    ensures scan(raw,current).used<=raw.len(),
    decreases raw.len(),
{
    if raw.len()>=2 {
        let n=length(raw);
        if n==0 {theorem_scan_boundary_within_buffer(drop(raw,2),seq![]);}
        else if n+2<=raw.len(){theorem_scan_boundary_within_buffer(drop(raw,n+2),current+raw.subrange(2,(n+2) as int));}
    }
}
pub proof fn theorem_incomplete_header_or_payload(raw:Bytes)
    requires raw.len()<2 || (raw.len()>=2 && length(raw)>0 && length(raw)+2>raw.len()),
    ensures decode(raw).bodies==seq![],decode(raw).used==0,
{}
pub proof fn theorem_empty_chunk_is_emitted()
    ensures decode(end()).bodies==seq![Seq::<u8>::empty()],decode(end()).used==2,
        !ws_continues(Read::Message(seq![])),
{reveal_with_fuel(scan,2);}
pub proof fn theorem_queue_precedes_receive(s:Receive,a:Bytes)
    requires s.queue.len()>0,
    ensures !receive(s,a).received,receive(s,a).read==Read::Message(s.queue[0]),
        receive(s,a).next.queue==s.queue.drop_first(),receive(s,a).next.buffer==s.buffer,
{}
pub proof fn theorem_buffer_and_queue_come_from_raw(s:Receive,a:Bytes)
    requires s.queue.len()==0,decode(s.buffer+a).bodies.len()>0,
    ensures receive(s,a).read==Read::Message(decode(s.buffer+a).bodies[0]),
        receive(s,a).next.queue==decode(s.buffer+a).bodies.drop_first(),
        receive(s,a).cut==encoded_lengths(decode(s.buffer+a).bodies),
        receive(s,a).next.buffer==drop(s.buffer+a,encoded_lengths(decode(s.buffer+a).bodies)),
{}
pub proof fn theorem_single_default_frame(body:Bytes)
    requires 0<body.len()<=max_chunk(),
    ensures decode(encode(body,max_chunk())).bodies==seq![body],
        decode(encode(body,max_chunk())).used==body.len()+4,
        encode(body,max_chunk()).len()==body.len()+4,
{
    lemma_header(body.len());
    assert(drop(body,body.len())==Seq::<u8>::empty());
    reveal_with_fuel(chunk_wire,2);
    assert(body.take(body.len() as int)==body);
    let raw=encode(body,max_chunk());
    assert(length(raw)==body.len());
    assert(raw.subrange(2,(body.len()+2) as int)==body);
    assert(drop(raw,body.len()+2)==end());
    reveal_with_fuel(scan,3);
    assert(seq![]+body==body);
}
pub proof fn theorem_small_chunk_reencoding_leaves_terminator()
    ensures ({let body=seq![0xb0u8,0x0fu8];let wire=encode(body,1);
        let r=receive(Receive{buffer:seq![],queue:seq![]},wire);
        r.read==Read::Message(body) && r.actual_used==8 && r.cut==6 && r.next.buffer==end() && r.next.queue==seq![]}),
{
    let body=seq![0xb0u8,0x0fu8];let first=seq![0xb0u8];let last=seq![0x0fu8];
    reveal_with_fuel(chunk_wire,3);
    assert(encode(body,1)==header(1)+first+header(1)+last+end());
    assert(encode(body,1)=~=header(1)+first+(header(1)+last+end()));
    lemma_scan_chunk(first,header(1)+last+end(),seq![]);
    lemma_scan_chunk(last,end(),first);lemma_scan_terminator(seq![],body);
    assert(first+last==body);assert(seq![]+first==first);
    assert(end()+seq![]=~=end());
    assert(decode(encode(body,1)).bodies==seq![body]);
    theorem_single_default_frame(body);reveal_with_fuel(encoded_lengths,2);
}
pub proof fn theorem_default_chunk_good_neighbor()
    ensures ({let body=seq![0xb0u8,0x0fu8];let r=receive(Receive{buffer:seq![],queue:seq![]},encode(body,max_chunk()));
        r.read==Read::Message(body) && r.cut==r.actual_used && r.next.buffer==seq![]}),
{let body=seq![0xb0u8,0x0fu8];theorem_single_default_frame(body);reveal_with_fuel(encoded_lengths,2);}
pub proof fn theorem_left_terminator_returns_empty_then_queues_next(next:Bytes)
    requires 0<next.len()<=max_chunk(),
    ensures ({let r=receive(Receive{buffer:end(),queue:seq![]},encode(next,max_chunk()));
        r.read==Read::Message(seq![]) && !ws_continues(r.read) && r.next.queue==seq![next]}),
{
    let wire=encode(next,max_chunk());
    theorem_single_default_frame(next);lemma_scan_terminator(wire,seq![]);
    reveal_with_fuel(encoded_lengths,3);reveal_with_fuel(chunk_wire,1);
}

// The record fragment preserves typed scalar/list/map values as opaque cells.
// PackStream's value->bytes relation is a provider fragment, exercised in Python.
pub enum Kind {Null,Boolean,Integer,Float,Text,List,Map}
pub struct Cell {pub kind:Kind,pub payload:Bytes}
pub type Row=Seq<Cell>;
pub type Rows=Seq<Row>;
pub type Names=Seq<Seq<char>>;
pub enum Phase {Ready,Streaming,Failed,Defunct}
pub struct Session {pub phase:Phase,pub pending:Option<Rows>,pub columns:Option<Names>,pub types:Option<Names>}
// Successful Rows denotes the admitted plain-result provider fragment: <=2
// string column names and default scalar types, no graph/custom object codec.
// Cells retain type and encoded-value identity; general codec fidelity is external.
pub enum EngineResult {Rows{columns:Names,rows:Rows,error:Option<Seq<char>>},Thrown}
pub open spec fn failed_result()->EngineResult {EngineResult::Rows{columns:seq![],rows:seq![],error:Some(seq!['e'])}}
pub enum Answer {Record(Row),RunSuccess(Names),Summary{has_more:Option<bool>},Failure,Ignored}
pub struct Step {pub state:Session,pub out:Seq<Answer>,pub engine_calls:nat}
pub open spec fn scalar_name()->Seq<char> {seq!['s','c','a','l','a','r']}
pub open spec fn scalar_types(cols:Names)->Names {cols.map_values(|_n:Seq<char>|scalar_name())}
pub open spec fn run_failure(s:Session)->Step {Step{state:Session{phase:Phase::Failed,pending:None,..s},out:seq![Answer::Failure],engine_calls:1}}
pub open spec fn run(s:Session,result:EngineResult)->Step {
    match result {
        EngineResult::Rows{columns,rows,error}=>if error.is_some() && error.unwrap().len()>0 {run_failure(s)}else{Step{state:Session{phase:Phase::Streaming,pending:Some(rows),types:Some(scalar_types(columns)),..s},
            out:seq![Answer::RunSuccess(columns)],engine_calls:1}},
        _=>run_failure(s),
    }
}
pub open spec fn selected(rows:Rows,n:int)->Rows {
    if n>0 && n<rows.len(){rows.take(n)}else{rows}
}
pub open spec fn remainder(rows:Rows,n:int)->Rows {
    rows.subrange(selected(rows,n).len() as int,rows.len() as int)
}
pub open spec fn records(rows:Rows)->Seq<Answer> {rows.map_values(|r:Row|Answer::Record(r))}
pub open spec fn pull(s:Session,n:int)->Step {
    if s.pending.is_none() {
        Step{state:Session{phase:Phase::Ready,..s},out:seq![Answer::Summary{has_more:None}],engine_calls:0}
    }else{
        let rows=selected(s.pending.unwrap(),n);
        Step{state:Session{phase:Phase::Ready,pending:None,columns:None,types:None},
            out:records(rows)+seq![Answer::Summary{has_more:None}],engine_calls:0}
    }
}
pub open spec fn reset(s:Session)->Step {
    Step{state:Session{phase:Phase::Ready,pending:None,columns:None,types:None},out:seq![Answer::Summary{has_more:None}],engine_calls:0}
}
pub open spec fn discard(s:Session)->Step {
    Step{state:Session{phase:Phase::Ready,pending:None,columns:None,..s},out:seq![Answer::Summary{has_more:None}],engine_calls:0}
}
pub open spec fn rollback(s:Session)->Step {reset(s)}
pub open spec fn commit(s:Session)->Step {
    Step{state:Session{phase:Phase::Ready,..s},out:seq![Answer::Summary{has_more:None}],engine_calls:0}
}
pub open spec fn no_step(s:Session)->Step {Step{state:s,out:seq![],engine_calls:0}}
pub open spec fn run_body()->Bytes {
    seq![0xb3u8,0x10u8,0x88u8,0x52u8,0x45u8,0x54u8,0x55u8,0x52u8,0x4eu8,0x20u8,0x76u8,0xa0u8,0xa0u8]
}
pub open spec fn pull_body(n:u8)->Bytes {seq![0xb1u8,0x3fu8,0xa1u8,0x81u8,0x6eu8,n]}
pub open spec fn tiny(n:u8)->Option<int> {
    if n<=127{Some(n as int)}else if n>=240{Some(n as int-256)}else{None}
}
pub open spec fn pull_count(body:Bytes)->Option<int> {
    if body.len()==3 && body==seq![0xb1u8,0x3fu8,0xa0u8]{Some(-1)}
    else if body.len()==6 && body.take(5)==seq![0xb1u8,0x3fu8,0xa1u8,0x81u8,0x6eu8]{tiny(body[5])}else{None}
}
// Admission: standard RUN RETURN v with named engine result, tiny-integer PULL
// field maps, and tag-only decisions for the other commands. Other codec shapes
// return None (unassessed), not a claimed protocol refusal.
pub open spec fn dispatch(s:Session,body:Bytes,result:EngineResult)->Option<Step> {
    if body.len()<2{Some(no_step(s))}else{
        let tag=body[1];
        if s.phase==Phase::Failed {
            if tag==0x0f{Some(reset(s))}
            else if tag==0x02{Some(Step{state:Session{phase:Phase::Defunct,..s},..no_step(s)})}
            else{Some(Step{out:seq![Answer::Ignored],..no_step(s)})}
        }else if tag==0x10 {if body==run_body(){Some(run(s,result))}else{None}}
        else if tag==0x3f {match pull_count(body){Some(n)=>Some(pull(s,n)),None=>None}}
        else if tag==0x0f {Some(reset(s))}
        else if tag==0x2f {Some(discard(s))}
        else if tag==0x12 {Some(commit(s))}
        else if tag==0x13 {Some(rollback(s))}
        else if tag==0x11 {Some(Step{out:seq![Answer::Summary{has_more:None}],..no_step(s)})}
        else if tag==0x02 {Some(Step{state:Session{phase:Phase::Defunct,..s},..no_step(s)})}
        // Authentication/HELLO payload handling is outside this contract.
        else if tag==0x01 || tag==0x6a || tag==0x6b {None}
        else{Some(no_step(s))}
    }
}
pub open spec fn record_rows(out:Seq<Answer>)->Rows
    decreases out.len(),
{if out.len()==0{seq![]}else{match out[0]{Answer::Record(r)=>seq![r]+record_rows(out.drop_first()),_=>record_rows(out.drop_first())}}}
pub proof fn lemma_record_reader(rows:Rows)
    ensures record_rows(records(rows)+seq![Answer::Summary{has_more:None}])==rows,
    decreases rows.len(),
{
    reveal_with_fuel(record_rows,2);
    if rows.len()>0 {
        lemma_record_reader(rows.drop_first());
        assert(records(rows)[0]==Answer::Record(rows[0]));
        assert(records(rows).drop_first()==records(rows.drop_first()));
        assert((records(rows)+seq![Answer::Summary{has_more:None}]).drop_first()==records(rows.drop_first())+seq![Answer::Summary{has_more:None}]);
        assert(seq![rows[0]]+rows.drop_first()==rows);
    }
}
pub proof fn theorem_run_produces_pending_and_type_metadata(s:Session,cols:Names,rows:Rows)
    ensures run(s,EngineResult::Rows{columns:cols,rows,error:None}).state.pending==Some(rows),
        run(s,EngineResult::Rows{columns:cols,rows,error:None}).state.phase==Phase::Streaming,
        run(s,EngineResult::Rows{columns:cols,rows,error:None}).state.types==Some(scalar_types(cols)),
        run(s,EngineResult::Rows{columns:cols,rows,error:None}).state.columns==s.columns,
        run(s,EngineResult::Rows{columns:cols,rows,error:None}).out==seq![Answer::RunSuccess(cols)],
{}
pub proof fn theorem_error_produces_failure_and_failed_gate(s:Session,body:Bytes,result:EngineResult)
    requires body.len()>=2,body[1]!=0x0f,body[1]!=0x02,
    ensures run(s,failed_result()).state.phase==Phase::Failed,
        run(s,failed_result()).state.pending==None,run(s,failed_result()).out==seq![Answer::Failure],
        run(s,failed_result()).state.columns==s.columns,run(s,failed_result()).state.types==s.types,
        dispatch(run(s,failed_result()).state,body,result)==Some(Step{out:seq![Answer::Ignored],..no_step(run(s,failed_result()).state)}),
{}
pub proof fn theorem_pull_reads_input_rows_then_clears(s:Session,rows:Rows,n:int)
    requires s.pending==Some(rows),
    ensures record_rows(pull(s,n).out)==selected(rows,n),pull(s,n).state.pending==None,
        pull(s,n).state.columns==None,pull(s,n).state.types==None,pull(s,n).state.phase==Phase::Ready,
{lemma_record_reader(selected(rows,n));}
pub proof fn theorem_partial_pull_drops_suffix_and_reports_no_more(s:Session,rows:Rows,n:int)
    requires s.pending==Some(rows),0<n<rows.len(),
    ensures remainder(rows,n).len()>0,pull(s,n).state.pending==None,
        pull(s,n).out.last()==(Answer::Summary{has_more:None}),
        record_rows(pull(pull(s,n).state,n).out)==seq![],
{reveal_with_fuel(record_rows,2);}
pub proof fn theorem_all_rows_for_nonpositive_pull(s:Session,rows:Rows,n:int)
    requires s.pending==Some(rows),n<=0,
    ensures record_rows(pull(s,n).out)==rows,
{lemma_record_reader(rows);}
pub proof fn theorem_commit_preserves_but_rollback_discards(s:Session,rows:Rows)
    requires s.pending==Some(rows),
    ensures commit(s).state.pending==Some(rows),record_rows(pull(commit(s).state,-1).out)==rows,
        rollback(s).state.pending==None,record_rows(pull(rollback(s).state,-1).out)==seq![],
{lemma_record_reader(rows);reveal_with_fuel(record_rows,2);}
pub proof fn theorem_discard_keeps_types_reset_clears(s:Session)
    ensures discard(s).state.pending==None,discard(s).state.columns==None,discard(s).state.types==s.types,
        reset(s).state.pending==None,reset(s).state.types==None,
{}
pub proof fn theorem_none_pending_keeps_metadata_empty_rows_clear(s:Session,n:int)
    requires s.pending==None,
    ensures pull(s,n).state.columns==s.columns,pull(s,n).state.types==s.types,
        pull(Session{pending:Some(seq![]),..s},n).state.columns==None,
        pull(Session{pending:Some(seq![]),..s},n).state.types==None,
{}
pub proof fn theorem_failed_run_does_not_consult_engine(s:Session,r:EngineResult)
    requires s.phase==Phase::Failed,
    ensures dispatch(s,run_body(),r).unwrap().engine_calls==0,
        dispatch(s,run_body(),r).unwrap().state==s,
{}
pub proof fn theorem_reset_allows_next_result(s:Session,cols:Names,rows:Rows)
    ensures dispatch(reset(s).state,run_body(),EngineResult::Rows{columns:cols,rows,error:None}).unwrap().state.pending==Some(rows),
        dispatch(reset(s).state,run_body(),EngineResult::Rows{columns:cols,rows,error:None}).unwrap().engine_calls==1,
{}
pub proof fn theorem_raw_pull_field_drives_records(s:Session,rows:Rows,n:u8)
    requires s.phase!=Phase::Failed,s.pending==Some(rows),n<=127 || n>=240,
    ensures dispatch(s,pull_body(n),failed_result()).is_some(),
        record_rows(dispatch(s,pull_body(n),failed_result()).unwrap().out)==selected(rows,tiny(n).unwrap()),
{
    assert(pull_body(n).take(5)=~=seq![0xb1u8,0x3fu8,0xa1u8,0x81u8,0x6eu8]);
    lemma_record_reader(selected(rows,tiny(n).unwrap()));
}
pub proof fn theorem_raw_default_frame_to_run_result(s:Session,cols:Names,rows:Rows)
    requires s.phase!=Phase::Failed,cols.len()<3,
    ensures ({let received=receive(Receive{buffer:seq![],queue:seq![]},encode(run_body(),max_chunk()));
        received.read==Read::Message(run_body()) && ws_continues(received.read)
        && dispatch(s,run_body(),EngineResult::Rows{columns:cols,rows,error:None}).unwrap().state.pending==Some(rows)}),
{theorem_single_default_frame(run_body());reveal_with_fuel(encoded_lengths,2);}

pub struct WireSession {pub receiver:Receive,pub session:Session,pub open:bool}
pub struct WireStep {pub next:WireSession,pub out:Seq<Answer>,pub engine_calls:nat,pub received:bool}
pub open spec fn advance(s:WireSession,arrival:Bytes,result:EngineResult)->Option<WireStep> {
    if !s.open || s.session.phase==Phase::Defunct {
        Some(WireStep{next:WireSession{open:false,..s},out:seq![],engine_calls:0,received:false})
    }else{
        let got=receive(s.receiver,arrival);
        match got.read {
            Read::NeedMore=>Some(WireStep{next:WireSession{receiver:got.next,..s},out:seq![],engine_calls:0,received:got.received}),
            Read::Message(body)=>if !ws_continues(got.read) {
                Some(WireStep{next:WireSession{receiver:got.next,open:false,..s},out:seq![],engine_calls:0,received:got.received})
            }else{match dispatch(s.session,body,result) {
                None=>None,
                Some(done)=>Some(WireStep{next:WireSession{receiver:got.next,session:done.state,open:done.state.phase!=Phase::Defunct},
                    out:done.out,engine_calls:done.engine_calls,received:got.received}),
            }},
        }
    }
}
pub open spec fn empty_receiver()->Receive {Receive{buffer:seq![],queue:seq![]}}
pub proof fn lemma_receive_default(body:Bytes)
    requires 0<body.len()<=max_chunk(),
    ensures receive(empty_receiver(),encode(body,max_chunk())).read==Read::Message(body),
        receive(empty_receiver(),encode(body,max_chunk())).next==empty_receiver(),
{
    theorem_single_default_frame(body);reveal_with_fuel(encoded_lengths,2);
    assert(seq![]+encode(body,max_chunk())=~=encode(body,max_chunk()));
    assert(seq![body].drop_first()=~=Seq::<Bytes>::empty());
    assert(drop(encode(body,max_chunk()),encode(body,max_chunk()).len())==Seq::<u8>::empty());
}
pub proof fn theorem_raw_wire_run_then_pull_final_records(s:Session,cols:Names,rows:Rows,n:u8)
    requires s.phase!=Phase::Failed,s.phase!=Phase::Defunct,cols.len()<3,0<n<=127,
    ensures ({let start=WireSession{receiver:empty_receiver(),session:s,open:true};
        let run_step=advance(start,encode(run_body(),max_chunk()),EngineResult::Rows{columns:cols,rows,error:None}).unwrap();
        let pulled=advance(run_step.next,encode(pull_body(n),max_chunk()),failed_result()).unwrap();
        let again=advance(pulled.next,encode(pull_body(n),max_chunk()),failed_result()).unwrap();
        run_step.engine_calls==1 && pulled.engine_calls==0 && pulled.next.session.pending==None
        && record_rows(pulled.out)==selected(rows,n as int) && record_rows(again.out)==seq![]}),
{
    lemma_receive_default(run_body());lemma_receive_default(pull_body(n));
    assert(pull_body(n).take(5)=~=seq![0xb1u8,0x3fu8,0xa1u8,0x81u8,0x6eu8]);
    lemma_record_reader(selected(rows,n as int));reveal_with_fuel(record_rows,2);
}
pub proof fn theorem_small_chunk_empty_closes_before_queued_run(s:Session,result:EngineResult)
    requires s.phase!=Phase::Defunct,
    ensures ({let start=WireSession{receiver:empty_receiver(),session:s,open:true};
        let reset_step=advance(start,encode(seq![0xb0u8,0x0fu8],1),result).unwrap();
        let next=advance(reset_step.next,encode(run_body(),max_chunk()),result).unwrap();
        let blocked=advance(next.next,seq![],result).unwrap();
        !next.next.open && next.next.receiver.queue==seq![run_body()] && next.engine_calls==0
        && blocked.engine_calls==0 && !blocked.received && blocked.next.receiver.queue==seq![run_body()]}),
{
    theorem_small_chunk_reencoding_leaves_terminator();
    theorem_left_terminator_returns_empty_then_queues_next(run_body());
}
pub proof fn theorem_no_complete_message_retains_raw(s:Receive,arrival:Bytes)
    requires s.queue.len()==0,decode(s.buffer+arrival).bodies.len()==0,
    ensures receive(s,arrival).read==Read::NeedMore,receive(s,arrival).next.buffer==s.buffer+arrival,
{}
pub proof fn theorem_header_is_unsigned_16bit(raw:Bytes)
    requires raw.len()>=2,
    ensures length(raw)<=max_chunk(),
{}
pub proof fn theorem_positive_pull_is_prefix(s:Session,rows:Rows,n:int)
    requires s.pending==Some(rows),0<n<rows.len(),
    ensures record_rows(pull(s,n).out)==rows.take(n),
{lemma_record_reader(selected(rows,n));}
pub proof fn theorem_tiny_signed_pull_count()
    ensures pull_count(pull_body(0xff))==Some(-1),pull_count(pull_body(1))==Some(1),
        pull_count(pull_body(0))==Some(0),pull_count(seq![0xb1u8,0x3fu8,0xa0u8])==Some(-1),
{
    assert(pull_body(0xff).take(5)=~=seq![0xb1u8,0x3fu8,0xa1u8,0x81u8,0x6eu8]);
    assert(pull_body(1).take(5)=~=seq![0xb1u8,0x3fu8,0xa1u8,0x81u8,0x6eu8]);
    assert(pull_body(0).take(5)=~=seq![0xb1u8,0x3fu8,0xa1u8,0x81u8,0x6eu8]);
}
pub proof fn theorem_raw_error_string_decides_failure(s:Session,cols:Names,rows:Rows,error:Seq<char>)
    ensures run(s,EngineResult::Rows{columns:cols,rows,error:Some(seq![])}).state.pending==Some(rows),
        error.len()>0 ==> run(s,EngineResult::Rows{columns:cols,rows,error:Some(error)}).out==seq![Answer::Failure],
        run(s,EngineResult::Thrown).out==seq![Answer::Failure],
{}
pub proof fn theorem_noop_closes_wire_without_engine(s:Session,result:EngineResult)
    requires s.phase!=Phase::Defunct,
    ensures ({let start=WireSession{receiver:empty_receiver(),session:s,open:true};
        let noop=advance(start,end(),result).unwrap();let blocked=advance(noop.next,encode(run_body(),max_chunk()),result).unwrap();
        !noop.next.open && noop.next.session==s && noop.engine_calls==0 && blocked.engine_calls==0 && !blocked.received}),
{theorem_empty_chunk_is_emitted();}
pub proof fn theorem_noop_coalesced_closes_with_queued_run(s:Session,result:EngineResult)
    requires s.phase!=Phase::Defunct,
    ensures ({let start=WireSession{receiver:empty_receiver(),session:s,open:true};
        let noop=advance(start,end()+encode(run_body(),max_chunk()),result).unwrap();
        !noop.next.open && noop.engine_calls==0 && noop.next.receiver.queue==seq![run_body()]}),
{
    theorem_left_terminator_returns_empty_then_queues_next(run_body());
    assert(seq![]+(end()+encode(run_body(),max_chunk()))=~=end()+encode(run_body(),max_chunk()));
}
pub proof fn theorem_coalesced_small_chunks_still_deliver_queued_run(s:Session,cols:Names,rows:Rows)
    requires s.phase!=Phase::Defunct,cols.len()<3,
    ensures ({let start=WireSession{receiver:empty_receiver(),session:s,open:true};
        let r=advance(start,encode(seq![0xb0u8,0x0fu8],1)+encode(run_body(),max_chunk()),EngineResult::Rows{columns:cols,rows,error:None}).unwrap();
        let q=advance(r.next,seq![],EngineResult::Rows{columns:cols,rows,error:None}).unwrap();
        r.next.open && r.next.receiver.queue==seq![run_body()] && !q.received && q.engine_calls==1 && q.next.session.pending==Some(rows)}),
{
    lemma_scan_encoded_prefix(seq![0xb0u8,0x0fu8],1,seq![],encode(run_body(),max_chunk()));
    theorem_single_default_frame(run_body());
    assert(seq![]+seq![0xb0u8,0x0fu8]==seq![0xb0u8,0x0fu8]);
    assert((seq![seq![0xb0u8,0x0fu8]]+seq![run_body()]).drop_first()=~=seq![run_body()]);
}
}
