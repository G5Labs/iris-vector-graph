"""Frozen F13 raw-tag neighbor: scratch helper correspondence only, no product/native."""
import hashlib,importlib.util,json,math,socket,time
from fractions import Fraction as F
from pathlib import Path
from unittest.mock import patch
H=Path(__file__).resolve().parent;R=H.parents[3];M=H/'review-fraction-scratch/.g5/Verus_verification/models/weighted_fraction'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
start=time.perf_counter()
with patch.object(socket.socket,'connect',side_effect=AssertionError('tag probe no sockets')) as guard:
 sp=load('review_fraction_source',M/'source_ports.py');km=load('review_fraction_integer',M/'kernel_model.py')
 raw={(0,'g','s','R','t'):F(1),(1,'g','t','R','s'):F(1),(2,'g','s','R','t'):F(1,4)};cap=F(2)
 D=math.prod([x.denominator for x in raw.values()]+[cap.denominator]);encoded={a:x.numerator*(D//x.denominator) for a,x in raw.items()};C=cap.numerator*(D//cap.denominator)
 source_json=sp.json_search(raw,lambda x:x,'s','t',cap,0,'both',set(),'g');kernel_json=km.json_search(encoded,'s','t',C,0,'both',set(),'g')
 source_cost=sp.cost_search(raw,lambda x:x,'s','t',cap,0,'both',set(),'g');kernel_cost=km.cost_search(encoded,'s','t',C,0,'both',set(),'g')
 observed={'source_json':str(source_json['answer']),'decoded_kernel_json':str(F(kernel_json['answer'],D)),'source_cost':str(source_cost['answer']),'decoded_kernel_cost':str(F(kernel_cost['answer'],D)),'helper_selected_tag2_both':km.selected((2,'g','s','R','t'),'g','both',set())}
 assert source_json['answer']==source_cost['answer']==F(1) and F(kernel_json['answer'],D)==F(1,4) and F(kernel_cost['answer'],D)==F(1) and observed['helper_selected_tag2_both']
 assert guard.call_count==0
out={'status':'FROZEN_F13_HELPER_COUNTERNEIGHBOR','observed':observed,'raw_rows':[(a,str(v)) for a,v in raw.items()],'derived_D':D,'cap':str(cap),'elapsed_s':time.perf_counter()-start,'socket_calls':0,'native_calls':0,'inputs':{str(p.relative_to(R)):sha(p) for p in [M/'source_ports.py',M/'kernel_model.py',M/'weighted_fraction.rs',H/'review-fraction-expectations.md',Path(__file__)]},'scope':'New formal selected/tag guard and actual source loops exclude tag2. Frozen immutable helper selected() allows every tag under both; JSON helper/oracle can accept tag2 while physical ports/Cost helper skip it. Existing public binding raw() worlds contain only0/1; their finite pass is not refuted, and no product/native bug inferred. This is a same-panel correspondence-helper gap, not a new arbitrary sampling draw.'}
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
