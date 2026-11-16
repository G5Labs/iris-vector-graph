"""Actual pure Python literal converter vs retained moving lexical admission; no DB/network."""
from pathlib import Path
import datetime, hashlib, json, socket, sys, time

R=Path(__file__).resolve().parents[4]
H=Path(__file__).resolve().parent
D=H/'review-rdf-moving-1'
started=time.monotonic()
sockets=[]
def deny(*args,**kwargs):
    sockets.append(repr(args));raise AssertionError('No network is authorized')
socket.socket.connect=deny
socket.socket.connect_ex=deny
sys.path.insert(0,str(R))
from iris_vector_graph._engine._rdf_utils import _to_literal
from rdflib import XSD

def moving_plain(s):
    return not s or ('a'<=s[0]<='z' or 'A'<=s[0]<='Z') and s.lower() not in ('nan','inf','infinity')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
model=(D/'lexical.rs').read_text()
original='lower(s)!=t("nan") && lower(s)!=t("inf") && lower(s)!=t("infinity")'
assert original in model,'This witness is for the exact retained original moving predicate.'
cases=[]
for raw in ['nan ','inf ','Infinity ','hello','true','false']:
    got=_to_literal(raw)
    cases.append(dict(raw=raw,moving_plain=moving_plain(raw),actual_text=str(got),actual_datatype=str(got.datatype) if got.datatype else None,actual_python_type=type(got.value).__name__,actual_is_decimal=got.datatype==XSD.decimal,disposition='moving admission misclassifies a Python-float spelling' if moving_plain(raw) and got.datatype==XSD.decimal else 'ordinary neighboring classification'))
assert all(cases[i]['moving_plain'] and cases[i]['actual_is_decimal'] for i in range(3))
assert not sockets
inputs=json.loads((D/'before.json').read_text())
out=dict(verdict='MOVING_LEXICAL_ADMISSION_MISMATCH_CONFIRMED',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cases=cases,inputs=inputs,elapsed_s=time.monotonic()-started,socket_calls=len(sockets),native_calls=0,git_calls=0,product_bug_claim=False,scope='Exact retained early moving lexical predicate, compared to actual pinned pure _to_literal. Not a final candidate assessment or an API refusal; full float/whitespace lexical behavior remains outside the desired bounded ordinary proof unless modeled.')
(H/'review-rdf-lexical-probe.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
