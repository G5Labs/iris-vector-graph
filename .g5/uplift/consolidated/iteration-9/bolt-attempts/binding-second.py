"""Actual pinned bytes/codec/session with local AsyncMock and StreamReader ports.
No listener, socket, database, authentication or native runtime is exercised.
"""
from __future__ import annotations
import asyncio,copy,hashlib,inspect,itertools,json,logging,os,socket,struct,sys,textwrap,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
NETWORK=patch.object(socket.socket,'connect',side_effect=AssertionError('bolt binding forbids network'))
CONNECT=NETWORK.start();os.environ['BOLT_ENABLED']='0';os.environ.pop('IVG_API_KEY',None);os.environ.pop('IVG_READ_ONLY',None)
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN=bc.import_pin()
from iris_vector_graph import bolt_server as bs
from iris_vector_graph.result import IVGResult

def scan(raw):
    """Independent raw header/payload scan, returns bodies and actual boundary."""
    offset=0;current=b'';out=[];used=0
    while offset+2<=len(raw):
        n=raw[offset]*256+raw[offset+1];offset+=2
        if n==0:out.append(current);current=b'';used=offset
        elif offset+n>len(raw):break
        else:current+=raw[offset:offset+n];offset+=n
    return out,used
def wire(body,limit=65535):
    assert 0<limit<=65535
    return b''.join(len(body[i:i+limit]).to_bytes(2,'big')+body[i:i+limit] for i in range(0,len(body),limit))+b'\0\0'
def pack(v):
    """Small independent PackStream value oracle; graph/custom values excluded."""
    if v is None:return b'\xc0'
    if type(v) is bool:return b'\xc3' if v else b'\xc2'
    if type(v) is int:
        if -16<=v<=127:return bytes([v&255])
        for size,tag in [(1,0xc8),(2,0xc9),(4,0xca),(8,0xcb)]:
            if -(2**(8*size-1))<=v<2**(8*size-1):return bytes([tag])+v.to_bytes(size,'big',signed=True)
        raise ValueError('oracle integer64 fragment')
    if type(v) is float:return b'\xc1'+struct.pack('>d',v)
    if type(v) is str:
        b=v.encode();n=len(b)
        h=bytes([0x80+n]) if n<=15 else b'\xd0'+bytes([n]) if n<=255 else b'\xd1'+n.to_bytes(2,'big')
        return h+b
    if isinstance(v,(list,tuple)):
        n=len(v);h=bytes([0x90+n]) if n<=15 else b'\xd4'+bytes([n]);return h+b''.join(pack(x) for x in v)
    if isinstance(v,dict):
        n=len(v);h=bytes([0xa0+n]) if n<=15 else b'\xd8'+bytes([n]);return h+b''.join(pack(str(k))+pack(x) for k,x in v.items())
    raise ValueError('outside typed codec fragment: '+type(v).__name__)
def body(tag,*fields):return bytes([0xb0|len(fields),tag])+b''.join(pack(v) for v in fields)
RUN=body(bs.TAG_RUN,'RETURN v',{},{});RESET=body(bs.TAG_RESET);BYE=body(bs.TAG_GOODBYE)
def pull(n):return body(bs.TAG_PULL,{'n':n})
def typed(v):
    if isinstance(v,(list,tuple)):return [typed(x) for x in v]
    if isinstance(v,dict):return {str(k):typed(x) for k,x in v.items()}
    return [type(v).__name__,v]
def raw_info(b):return {'length':len(b),'sha256':hashlib.sha256(b).hexdigest(),'head':b[:48].hex(),'tail':b[-16:].hex()}

def receive_reference(frames,reads):
    buf=b'';queue=[];at=0;out=[]
    for _ in range(reads):
        while True:
            if queue:
                msg=queue.pop(0);out.append({'body':msg,'buffer':buf,'queue':list(queue),'receives':at});break
            if at==len(frames):out.append({'eof':True,'buffer':buf,'queue':list(queue),'receives':at+1});return out
            buf+=frames[at];at+=1;msgs,used=scan(buf)
            if msgs:
                cut=sum(len(wire(m)) for m in msgs);buf=buf[cut:];queue=msgs[1:]
                out.append({'body':msgs[0],'buffer':buf,'queue':list(queue),'receives':at,'used':used,'cut':cut});break
    return out
class EndFrame(RuntimeError):pass
async def receive_actual(frames,reads,method=None):
    ws=AsyncMock();ws.receive_bytes=AsyncMock(side_effect=[*frames,EndFrame('finite fixture exhausted')])
    s=bs.BoltSession(ws,lambda:None);out=[]
    if method:s._recv_message=method.__get__(s,bs.BoltSession)
    for _ in range(reads):
        try:
            msg=await s._recv_message();out.append({'body':msg,'buffer':bytes(s._buf),'queue':list(s._msg_queue),'receives':ws.receive_bytes.call_count})
        except EndFrame:out.append({'eof':True,'buffer':bytes(s._buf),'queue':list(s._msg_queue),'receives':ws.receive_bytes.call_count});break
    return out
def received_equal(got,want):return [{k:v for k,v in r.items() if k not in ('used','cut')} for r in want]==got
def frame_cases():
    cases=[]
    for chunks,layout in itertools.product(itertools.product([1,2,3,65535],repeat=2),['separate','coalesced','bytes','split']):
        a,b=[wire(x,k) for x,k in zip([RESET,RUN],chunks)]
        frames=[a,b] if layout=='separate' else [a+b] if layout=='coalesced' else [bytes([x]) for x in a+b] if layout=='bytes' else [a[:1],a[1:]+b[:3],b[3:]]
        cases.append((f'chunks{chunks}-{layout}',frames,4))
    for n in [0,1,2,127,255,256,300,65535,65536]:
        b=bytes([0xff])*n
        for limit in [1 if n<301 else 65535,65535]:
            w=wire(b,limit);cases.append((f'width{n}-{limit}',[w],2))
    for name,frames in [('header',[b'\x00']),('payload',[b'\x00\x03a']),('no-end',[b'\x00\x01a']),
        ('complete-partial',[wire(RESET)+b'\x00',wire(RUN)]),('noop-run',[b'\0\0',wire(RUN)]),
        ('leading-noop-coalesced',[b'\0\0'+wire(RUN)]),('empty-frame',[b'',wire(RESET)])]:cases.append((name,frames,4))
    return cases

class Engine:
    def __init__(self,profiles):
        self.profiles=profiles;self.calls=[];self.tx=[];self.factory_calls=0
        self.conn=SimpleNamespace(commit=lambda:self.tx.append('commit'),rollback=lambda:self.tx.append('rollback'),cursor=lambda:self.tx.append('cursor'))
    def execute_cypher(self,q,parameters=None):
        i=len(self.calls);self.calls.append((q,parameters));p=self.profiles[min(i,len(self.profiles)-1)]
        if p.get('throw'):raise RuntimeError('named query provider failure')
        return IVGResult(columns=p.get('columns',['v']),rows=copy.deepcopy(p.get('rows',[])),error=p.get('error'),bolt_column_types=p.get('types') or [])
def decoded_output(ws):
    messages=[];record_wires=[]
    for call in ws.send_bytes.call_args_list:
        raw=call.args[0]
        for message in bs.decode_messages(raw):
            tag=message[1];field=bs.PackStream.unpack(message,2)[0] if len(message)>2 else None
            messages.append({'tag':tag,'field':field})
            if tag==bs.TAG_RECORD:record_wires.append(raw)
    return messages,record_wires
def project_messages(messages):
    out=[]
    for m in messages:
        tag=m['tag'];f=m['field']
        if tag==bs.TAG_RECORD:out.append({'kind':'record','row':typed(f)})
        elif tag==bs.TAG_FAILURE:out.append({'kind':'failure'})
        elif tag==bs.TAG_IGNORED:out.append({'kind':'ignored'})
        elif tag==bs.TAG_SUCCESS:
            out.append({'kind':'run','fields':f['fields']} if 'fields' in f else {'kind':'summary','has_more':f.get('has_more')})
    return out
def command_reference(s,b,profiles,index):
    """Raw body/tag/tiny PULL field -> source-shaped state/out; no product helper."""
    s=copy.deepcopy(s);out=[]
    if len(b)<2:return s,out,index
    tag=b[1]
    if s['phase']=='FAILED':
        if tag==bs.TAG_RESET:s.update(phase='READY',pending=None,columns=None,types=None);out=[{'kind':'summary','has_more':None}]
        elif tag==bs.TAG_GOODBYE:s['phase']='DEFUNCT'
        else:out=[{'kind':'ignored'}]
        return s,out,index
    if tag==bs.TAG_RUN:
        assert b==RUN;p=profiles[min(index,len(profiles)-1)];index+=1
        if p.get('error') or p.get('throw'):s.update(phase='FAILED',pending=None);out=[{'kind':'failure'}]
        else:
            cols=p.get('columns',['v']);s.update(phase='STREAMING',pending=copy.deepcopy(p.get('rows',[])),types=p.get('types') or ['scalar']*len(cols));out=[{'kind':'run','fields':cols}]
    elif tag==bs.TAG_PULL:
        n=-1 if b==body(bs.TAG_PULL,{}) else (b[5] if b[5]<=127 else b[5]-256)
        if s['pending'] is not None:
            rows=s['pending'][:n] if n>0 else s['pending'];out=[{'kind':'record','row':typed(r)} for r in rows]
            s.update(pending=None,columns=None,types=None)
        out.append({'kind':'summary','has_more':None});s['phase']='READY'
    elif tag in [bs.TAG_RESET,bs.TAG_ROLLBACK]:s.update(phase='READY',pending=None,columns=None,types=None);out=[{'kind':'summary','has_more':None}]
    elif tag==bs.TAG_DISCARD:s.update(phase='READY',pending=None,columns=None);out=[{'kind':'summary','has_more':None}]
    elif tag==bs.TAG_COMMIT:s['phase']='READY';out=[{'kind':'summary','has_more':None}]
    elif tag==bs.TAG_BEGIN:out=[{'kind':'summary','has_more':None}]
    elif tag==bs.TAG_GOODBYE:s['phase']='DEFUNCT'
    return s,out,index
async def session_actual(bodies,profiles,method=None,owner=None):
    ws=AsyncMock();e=Engine(profiles);s=bs.BoltSession(ws,lambda:e);s.state=bs.BoltState.READY;s._authenticated=True
    if method:setattr(s,owner,method.__get__(s,bs.BoltSession))
    expected={'phase':'READY','pending':None,'columns':None,'types':None};index=0;want=[];steps=[];okay=True
    for b in bodies:
        expected,out,index=command_reference(expected,b,profiles,index);want.extend(out)
        await s._dispatch(b)
        messages,record_wires=decoded_output(ws)
        actual={'phase':s.state.value,'pending':s._pending_result,'columns':s._pending_columns,'types':s._pending_col_types}
        good=actual==expected and project_messages(messages)==want
        record_values=[m['field'] for m in messages if m['tag']==bs.TAG_RECORD]
        good &= record_wires==[wire(body(bs.TAG_RECORD,r)) for r in record_values]
        okay &= good;steps.append({'tag':b[1] if len(b)>1 else None,'state':copy.deepcopy(actual),'agrees':bool(good)})
    return {'agrees':bool(okay and len(e.calls)==index and not e.tx),'steps':steps,'output':project_messages(messages),'expected':want,'engine_calls':e.calls,'transaction_calls':e.tx,'record_wires':[raw_info(w) for w in record_wires]}
def session_cases():
    profiles=[{'rows':[[1],[2],[3]]},{'rows':[]},{'rows':[[7]],'error':'folded failure'},{'throw':True}]
    cases=[]
    for p,n,middle in itertools.product(profiles,[-1,0,1,2,3,4],[None,bs.TAG_COMMIT,bs.TAG_ROLLBACK,bs.TAG_DISCARD,bs.TAG_RESET]):
        bodies=[RUN]+([] if middle is None else [body(middle,{}) if middle==bs.TAG_DISCARD else body(middle)])+[pull(n),pull(1)]
        cases.append((f'result-{profiles.index(p)}-pull{n}-middle{middle}',bodies,[p]))
    for error in [{'error':'folded failure'},{'throw':True}]:
        cases.append(('failed-gate-reset',[RUN,pull(1),body(bs.TAG_ROLLBACK),RUN,RESET,RUN,pull(-1)],[error,{'rows':[[29]]}]))
    values=[None,True,False,-17,-16,0,29,127,128,32768,2**31,2**63-1,1.5,'[1]','{"x":1}','1e5','é',[1,True,None],{'x':[1,'a']},[] ,{}]
    for value in values:cases.append(('typed-'+repr(value),[RUN,pull(-1)],[{'rows':[[value]]}]))
    for a,b in itertools.product([[],[[1]],[[1],[2]]],repeat=2):cases.append(('replace',[RUN,RUN,pull(1),pull(-1)],[{'rows':a},{'rows':b}]))
    for middle in [bs.TAG_COMMIT,bs.TAG_ROLLBACK]:cases.append(('explicit-transaction',[body(bs.TAG_BEGIN,{}),RUN,body(middle),pull(-1)],[{'rows':[[1]]}]))
    return cases

async def websocket_run(frames,profiles):
    handshake=bs.BOLT_MAGIC+struct.pack('>IIII',bs.BOLT_44,0,0,0);ws=AsyncMock();ws.scope={'subprotocols':[]}
    ws.receive_bytes=AsyncMock(side_effect=[handshake,*frames,EndFrame('fixture exhausted')]);e=Engine(profiles);s=bs.BoltSession(ws,lambda:e)
    await s.run();messages,record_wires=decoded_output(SimpleNamespace(send_bytes=SimpleNamespace(call_args_list=ws.send_bytes.call_args_list[1:])))
    expected={'phase':'READY','pending':None,'columns':None,'types':None};index=0;want=[];closed_by_empty=False
    received=receive_reference(frames,20)
    for item in received:
        if item.get('eof'):break
        b=item['body']
        if not b:closed_by_empty=True;break
        expected,out,index=command_reference(expected,b,profiles,index);want.extend(out)
        if expected['phase']=='DEFUNCT':break
    actual={'phase':s.state.value,'pending':s._pending_result,'columns':s._pending_columns,'types':s._pending_col_types}
    return {'agrees':actual==expected and project_messages(messages)==want and len(e.calls)==index and not e.tx and ws.close.call_count>=1,
        'output':project_messages(messages),'expected':want,'state':actual,'engine_calls':e.calls,'closed_by_empty':closed_by_empty,
        'buffer':raw_info(bytes(s._buf)),'queue':[x.hex() for x in s._msg_queue]}
async def tcp_noop():
    reader=asyncio.StreamReader();writer=AsyncMock();written=[];writer.write=lambda b:written.append(b);writer.close=lambda:None
    reader.feed_data(bs.BOLT_MAGIC+struct.pack('>IIII',bs.BOLT_44,0,0,0)+b'\0\0'+wire(RUN)+wire(pull(-1))+wire(BYE));reader.feed_eof()
    e=Engine([{'rows':[[1]]}]);s=bs.TcpBoltSession(reader,writer,lambda:e);await s.run()
    out=[]
    for w in written[1:]:
        for b in bs.decode_messages(w):out.append({'tag':b[1],'field':bs.PackStream.unpack(b,2)[0] if len(b)>2 else None})
    return {'agrees':len(e.calls)==1 and [m['field'] for m in out if m['tag']==bs.TAG_RECORD]==[[1]],'output':project_messages(out),'engine_calls':e.calls,'scope':'actual in-process StreamReader/AsyncMock writer, no TCP socket'}
def mutant(owner,name,find,replace,extra=None):
    src=textwrap.dedent(inspect.getsource(getattr(owner,name)));assert src.count(find)==1,(name,find)
    ns=dict(vars(bs));ns.update(extra or {});exec(src.replace(find,replace),ns);return ns[name]

def main():
    t=time.monotonic();mism=[];framing=[];sessions=[];journeys=[]
    for name,frames,reads in frame_cases():
        want=receive_reference(frames,reads);got=asyncio.run(receive_actual(frames,reads));good=received_equal(got,want)
        # Both real product stateless decoder and stateful reader are bound.
        decoder=all(bs.decode_messages(b)==scan(b)[0] for b in frames)
        framing.append({'name':name,'agrees':good and decoder,'frames':[raw_info(b) for b in frames],'reads':[{'body':r.get('body',b'').hex() if len(r.get('body',b''))<100 else raw_info(r['body']),'eof':r.get('eof',False),'buffer':raw_info(r['buffer']),'queue_len':len(r['queue']),'receives':r['receives']} for r in got]})
        if not good or not decoder:mism.append({'framing':name})
    for name,bodies,profiles in session_cases():
        result=asyncio.run(session_actual(bodies,profiles));sessions.append({'name':name,**result})
        if not result['agrees']:mism.append({'session':name,'result':result})
    for chunk,layout in itertools.product([1,2,3,65535],['separate','coalesced','split']):
        frames=[wire(RESET,chunk),wire(RUN),wire(pull(1)),wire(BYE)]
        if layout=='coalesced':frames=[b''.join(frames)]
        if layout=='split':frames=[bytes([x]) for x in b''.join(frames)]
        result=asyncio.run(websocket_run(frames,[{'rows':[[1],[2],[3]]}]))
        journeys.append({'chunk':chunk,'layout':layout,**result})
        if not result['agrees']:mism.append({'journey':str((chunk,layout)),**result})
    noop=asyncio.run(websocket_run([b'\0\0',wire(RUN),wire(pull(-1)),wire(BYE)],[{'rows':[[1]]}]))
    tcp=asyncio.run(tcp_noop());assert noop['closed_by_empty'] and not noop['engine_calls'] and tcp['agrees']
    detection={}
    fn=mutant(bs.BoltSession,'_recv_message','self._buf = self._buf[consumed:]','self._buf = self._buf[actual_boundary(bytes(self._buf)):] ',{'actual_boundary':lambda b:scan(b)[1]})
    frames=[wire(RESET,1),wire(RUN)];want=receive_reference(frames,2);base=asyncio.run(receive_actual(frames,2));bad=asyncio.run(receive_actual(frames,2,fn))
    detection['actual-reencoded-cut-corrected']=received_equal(base,want) and not received_equal(bad,want)
    src=textwrap.dedent(inspect.getsource(bs._decode_messages_stateless));find="chunk_len = struct.unpack('>H', raw[offset:offset+2])[0]";assert src.count(find)==1;ns=dict(vars(bs));exec(src.replace(find,'chunk_len = raw[offset+1]'),ns)
    raw=wire(b'x'*300);detection['actual-decoder-high-byte-lost']=bs.decode_messages(raw)==scan(raw)[0] and ns['_decode_messages_stateless'](raw)!=scan(raw)[0]
    checks=[('pull-slice-removed','_handle_pull','if n > 0:','if False:',[RUN,pull(1)]),
        ('pull-suffix-retained','_handle_pull','self._pending_result = None','self._pending_result = self._pending_result[len(rows):]',[RUN,pull(1),pull(1)]),
        ('commit-clears-rows','_dispatch','elif tag == TAG_COMMIT:\n            await self._send_message(TAG_SUCCESS, {})','elif tag == TAG_COMMIT:\n            self._pending_result = None\n            await self._send_message(TAG_SUCCESS, {})',[RUN,body(bs.TAG_COMMIT),pull(-1)]),
        ('failed-gate-removed','_dispatch','if self.state == BoltState.FAILED:','if False:',[RUN,pull(1)]),
        ('reset-keeps-rows','_handle_reset','self._pending_result = None','pass',[RUN,RESET,pull(-1)]),
        ('folded-error-ignored','_handle_run','if getattr(result, "error", None):','if False:',[RUN,pull(-1)])]
    for name,owner,find,replace,bodies in checks:
        fn=mutant(bs.BoltSession,owner,find,replace);profile={'rows':[[1],[2],[3]],**({'error':'folded'} if name in ['failed-gate-removed','folded-error-ignored'] else {})}
        good=asyncio.run(session_actual(bodies,[profile]));bad=asyncio.run(session_actual(bodies,[profile],fn,owner));detection['actual-'+name]=good['agrees'] and not bad['agrees']
    sample=asyncio.run(session_actual([RUN,pull(-1)],[{'rows':[[29]]}]))
    altered=copy.deepcopy(sample['output']);next(x for x in altered if x['kind']=='record')['row']=typed(['29'])
    detection['altered-final-record-rejected']=sample['output']==sample['expected'] and altered!=sample['expected']
    verdict='AGREES' if not mism and all(detection.values()) and CONNECT.call_count==0 else 'DISAGREES'
    out=bc.write_receipt('bolt_stream',Path(__file__),{'verdict':verdict,'framing_cases':len(framing),'session_cases':len(sessions),'wire_journeys':len(journeys),'mismatch_count':len(mism),'mismatches':mism[:5],
        'framing':framing,'sessions':sessions,'journeys':journeys,'noop_websocket':noop,'noop_tcp_adapter':tcp,'detection':detection,'blocked_socket_calls':CONNECT.call_count,'elapsed':time.monotonic()-t,
        'pin':bc.pin_identity(PIN),'scope':'actual encoder/stateless decoder/WS reader/dispatch/RUN pending writer/PULL record bytes and final reader; local AsyncMock/StreamReader, no network/listener/database. Engine result is named provider; arbitrary PackStream/graph object/transport failures and transaction persistence unproved.'})
    d=json.loads(out.read_text());d['inputs'][str((HERE/'model.json').relative_to(bc.REPO))]=bc.sha(HERE/'model.json')
    for name in ['iris_vector_graph/bolt_server.py','iris_vector_graph/result.py']:d['inputs'][name]=bc.sha(PIN/name)
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps({'verdict':verdict,'framing':len(framing),'sessions':len(sessions),'journeys':len(journeys),'mismatches':mism[:2],'detection':detection,'elapsed':time.monotonic()-t,'receipt':str(out)},default=str));return int(verdict!='AGREES')
if __name__=='__main__':raise SystemExit(main())
