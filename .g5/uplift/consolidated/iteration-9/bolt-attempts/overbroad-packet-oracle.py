"""Ordinary full session/handshake traces, in-process transports, zero sockets.
Read-only engine adapter supplies one scalar row; no auth, DB or network claim.
"""
import asyncio,hashlib,inspect,json,os,socket,struct,sys,textwrap,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN))
os.environ['IVG_API_KEY']='';os.environ['IVG_READ_ONLY']='0';os.environ['BOLT_ENABLED']='0'
from iris_vector_graph import bolt_server as bs
HELLO=bs.bolt_message_bytes(bs.TAG_HELLO,{'user_agent':'g5 ordinary framing'})
RUN=bs.bolt_message_bytes(bs.TAG_RUN,'RETURN 1',{}, {})
PULL=bs.bolt_message_bytes(bs.TAG_PULL,{'n':-1});BYE=bs.bolt_message_bytes(bs.TAG_GOODBYE)
HANDSHAKE=bs.BOLT_MAGIC+struct.pack('>IIII',bs.BOLT_44,0,0,0)

def actual_consumed(buf):
    i=0;complete=0
    while i+2<=len(buf):
        size=int.from_bytes(buf[i:i+2],'big');i+=2
        if i+size>len(buf):break
        i+=size
        if size==0:complete=i
    return complete

class WS:
    scope={'subprotocols':[]}
    def __init__(self,frames):self.frames=list(frames);self.sent=[];self.closes=0;self.received=0
    async def accept(self,**kw):pass
    async def close(self):self.closes+=1
    async def send_bytes(self,data):self.sent.append(data)
    async def receive_bytes(self):
        if not self.frames:raise EOFError('local transport exhausted')
        self.received+=1;return self.frames.pop(0)

class Writer:
    def __init__(self):self.sent=[];self.closed=False
    def write(self,b):self.sent.append(b)
    async def drain(self):pass
    def close(self):self.closed=True
    async def wait_closed(self):pass

def variants():
    recvsrc=textwrap.dedent(inspect.getsource(bs.BoltSession._recv_message))
    old='consumed = 0\n            for msg in msgs:\n                consumed += len(encode_message(msg))'
    assert recvsrc.count(old)==1
    ns=dict(vars(bs));ns['actual_consumed']=actual_consumed
    exec(recvsrc.replace(old,'consumed = actual_consumed(self._buf)'),ns);recv=ns['_recv_message']
    runsrc=textwrap.dedent(inspect.getsource(bs.BoltSession.run));assert runsrc.count('if not msg_bytes:')==1
    exec(runsrc.replace('if not msg_bytes:','if msg_bytes is None:'),ns)
    return recv,ns['run']

async def case(transport,fragmented,noop,coalesced,fix):
    calls=[]
    def execute(query,parameters):calls.append((query,parameters));return SimpleNamespace(columns=['1'],rows=[[1]],bolt_column_types=['scalar'],error=None)
    engine=SimpleNamespace(execute_cypher=execute)
    bodies=[bs.encode_message(HELLO,max_chunk=1 if fragmented else 65535)]
    if noop:bodies.append(b'\0\0')
    bodies.extend(bs.encode_message(x) for x in [RUN,PULL,BYE])
    if transport=='ws':
        ws=WS([HANDSHAKE]+([b''.join(bodies)] if coalesced else bodies));session=bs.BoltSession(ws,lambda:engine)
        recv,run=variants()
        if fix in ['recv','both']:session._recv_message=recv.__get__(session)
        if fix in ['loop','both']:session.run=run.__get__(session)
        await session.run();sent=ws.sent;closed=ws.closes>0;unread=len(ws.frames)
    else:
        reader=asyncio.StreamReader();reader.feed_data(HANDSHAKE+b''.join(bodies));reader.feed_eof();writer=Writer()
        session=bs.TcpBoltSession(reader,writer,lambda:engine);await session.run();sent=writer.sent;closed=writer.closed;unread=None
    msgs=[m for frame in sent[1:] for m in bs.decode_messages(frame)]
    tags=[m[1] for m in msgs if len(m)>=2]
    records=[bs.PackStream.unpack(m,2)[0] for m in msgs if len(m)>=2 and m[1]==bs.TAG_RECORD]
    success=sent[0]==struct.pack('>I',bs.BOLT_44) and calls==[('RETURN 1',{})] and records==[[1]] and session.state==bs.BoltState.DEFUNCT
    return dict(transport=transport,fragmented_hello=fragmented,noop=noop,coalesced=coalesced,method_copy=fix,query_calls=calls,records=records,tags=tags,state=session.state.name,closed=closed,unread_frames=unread,remaining_hex=bytes(session._buf).hex(),ordinary_result_preserved=success)

def main():
    start=time.monotonic();cases=[]
    with patch.object(socket.socket,'connect',side_effect=AssertionError('no network')) as guard:
        for fix in ['none','recv','loop','both']:
            for fragmented,noop in [(False,False),(True,False),(False,True),(True,True)]:
                for coalesced in [False,True]:cases.append(asyncio.run(case('ws',fragmented,noop,coalesced,fix)))
        for fragmented,noop in [(False,False),(True,False),(False,True),(True,True)]:cases.append(asyncio.run(case('tcp',fragmented,noop,False,'none')))
        assert guard.call_count==0
    for c in cases:
        expected=True if c['transport']=='tcp' else (not c['fragmented_hello'] or c['method_copy'] in ['recv','both']) and (not c['noop'] or c['method_copy'] in ['loop','both'])
        assert c['ordinary_result_preserved']==expected,c
    result={'cases':cases,'case_count':len(cases),'network_connect_calls':guard.call_count,'elapsed':time.monotonic()-start,
        'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),PIN/'iris_vector_graph/bolt_server.py']},
        'scope':'Actual product ordinary WS and TCP session run/handshake/receive/dispatch/RUN/PULL/scalar record; Async local WS and StreamReader/writer transports, one-row engine adapter. No listener, actual socket, authentication scenario or native provider. Method copies are proposed localized repairs only, never product edits.',
        'primary_protocol':'https://neo4j.com/docs/bolt/current/bolt/message/'}
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'all_expected':True,'network':guard.call_count,'elapsed':result['elapsed']}))
if __name__=='__main__':main()
