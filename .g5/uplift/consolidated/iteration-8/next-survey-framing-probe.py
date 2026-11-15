"""Actual ordinary WebSocket message extraction; all buffers local, no app/session run."""
import asyncio,hashlib,json,os,socket,sys,time
from pathlib import Path
from unittest.mock import AsyncMock,patch
PIN=Path('/Users/ziniuw/runs/ivg-consolidated-20261114/pin');sys.path.insert(0,str(PIN));os.environ['BOLT_ENABLED']='0'
GUARD=patch.object(socket.socket,'connect',side_effect=AssertionError('no network in local framing probe'));CONNECT=GUARD.start()
from iris_vector_graph import bolt_server as bs
async def case(chunk):
    first=bs.bolt_message_bytes(bs.TAG_RESET);second=bs.bolt_message_bytes(bs.TAG_RUN,'RETURN 1',{}, {})
    frame1=bs.encode_message(first,max_chunk=chunk);frame2=bs.encode_message(second)
    assert bs.decode_messages(frame1)==[first] and bs.decode_messages(frame2)==[second]
    ws=AsyncMock();ws.receive_bytes=AsyncMock(side_effect=[frame1,frame2,RuntimeError('local fixture exhausted')])
    s=bs.BoltSession(ws,lambda:None);out=[]
    for _ in range(2):
        try:out.append({'body_hex':(await s._recv_message()).hex(),'buffer_hex':bytes(s._buf).hex()})
        except Exception as ex:out.append({'raised':type(ex).__name__,'message':str(ex)})
    return {'chunk_size':chunk,'first_body':first.hex(),'expected_second':second.hex(),'frames':[frame1.hex(),frame2.hex()],'observed':out,'preserved':len(out)==2 and out[0].get('body_hex')==first.hex() and out[1].get('body_hex')==second.hex()}
def main():
    start=time.monotonic()
    guard=CONNECT;cases=[asyncio.run(case(chunk)) for chunk in [65535,1,2,3]]
    assert cases[0]['preserved'] and not cases[1]['preserved'] and cases[2]['preserved'] and cases[3]['preserved']
    result={'cases':cases,'ordinary_codec_roundtrip_valid':True,'network_connect_calls':guard.call_count,'scope':'actual product encoder/stateless decoder and BoltSession._recv_message; two local AsyncMock WebSocket frames, no socket/listener/auth/database; source-derived potential defect, not a new formal proof','elapsed':time.monotonic()-start,'source_sha256':hashlib.sha256((PIN/'iris_vector_graph/bolt_server.py').read_bytes()).hexdigest()}
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'preserved_by_chunk':{x['chunk_size']:x['preserved'] for x in cases},'network':guard.call_count,'elapsed':result['elapsed']}))
if __name__=='__main__':main()
