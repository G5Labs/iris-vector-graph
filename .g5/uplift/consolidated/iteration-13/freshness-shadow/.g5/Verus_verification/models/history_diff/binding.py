"""Actual named diff and reconstruction readers; inspected server record fixture.

No IRIS execution. Deletion priors carry NodeSnapshotJson's real shape. Expected
continuous deltas come from endpoint states, independently of compute_diff.
"""
import inspect,itertools,json,sys,textwrap
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN=bc.import_pin()
import history_fixture as hf
from iris_vector_graph.ledger import replay as R

def rec(seq,op,prior=None,new=None,attr='',kind='node',id='n',ordinal=1):
    return R.MutationRecord(seq,ordinal,op,kind,id,attr,prior,new,None)

def seeded(ops):
    rs=[rec(1,'create_node',new=''),rec(1,'set_prop',new='1',attr='k',ordinal=2)]
    exists=True;value='1'
    for seq,op in enumerate(ops,2):
        if op=='create':
            if exists:return None
            rs.append(rec(seq,'create_node',new=''));exists=True;value=None
        elif op=='delete':
            if not exists:return None
            snapshot=json.dumps({'labels':[],'props':{'k':value} if value is not None else {}},sort_keys=True)
            rs.append(rec(seq,'delete_node',prior=snapshot));exists=False;value=None
        elif op=='remove':
            if not exists or value is None:return None
            rs.append(rec(seq,'remove_prop',prior=value,attr='k'));value=None
        else:
            if not exists:return None
            if value!=op:rs.append(rec(seq,'set_prop',prior=value,new=op,attr='k'))
            value=op
    return rs

def normalized(rs):
    s=R.reconstruct(rs,None)
    return {n:{'labels':sorted(v.labels),'props':v.props} for n,v in s.nodes.items()}

def compare(compute=None,change=False):
    old=R.compute_diff
    if compute:R.compute_diff=compute
    n=0;mism=[];continuous=0
    try:
        for size in range(5):
            for ops in itertools.product(['create','delete','remove','1','2','3'],repeat=size):
                rs=seeded(ops)
                if rs is None:continue
                g=hf.ledger(rs,100)
                for a,b in itertools.product(range(1,size+2),repeat=2):
                    f=g.diff(str(a),str(b));rev=g.diff(str(b),str(a))
                    if f.inverse().to_list()!=rev.to_list() or (a==b and f.to_list()):mism.append(['selector',ops,a,b])
                    lo,hi=sorted((a,b));span=[r for r in rs if lo<r.seq<=hi]
                    if not any(r.op in ('create_node','delete_node') for r in span):
                        start=normalized([r for r in rs if r.seq<=a]);end=normalized([r for r in rs if r.seq<=b])
                        before=start.get('n',{}).get('props',{}).get('k');after=end.get('n',{}).get('props',{}).get('k')
                        want=[] if before==after else [{'entity_kind':'node','entity_id':'n','attr':'prop:k','before':before,'after':after}]
                        got=f.to_list()
                        if change and continuous==0:got=[{'changed':True}]
                        if got!=want:mism.append(['endpoints',ops,a,b,got,want])
                        continuous+=1
                    n+=1
    finally:R.compute_diff=old
    return n,continuous,mism

def main():
    n,cont,mism=compare()
    scope=dict(vars(R));source=textwrap.dedent(inspect.getsource(R.compute_diff))
    exec(source.replace('if ak not in lc.attrs_before:', 'if True:'),scope)
    _,_,mut=compare(scope['compute_diff']);_,_,changed=compare(change=True)
    # Ordinary lifecycle neighbor: prior is in the existence snapshot. The old
    # empty-prior fixture is retained historically but cannot establish its claim.
    simple=seeded(['delete','create','2']);g=hf.ledger(simple,100)
    simple_rev=g.diff('4','1').to_list()
    assert json.loads(simple_rev[0]['after'])['props']['k']=='1'
    strong=seeded(['2','delete','create','3']);g=hf.ledger(strong,100)
    reverse=g.diff('5','1').to_list()
    assert g.reconstruct('1').nodes['n'].props['k']=='1'
    assert json.loads(reverse[0]['after'])['props']['k']=='2'
    assert reverse[-1]['after'] is None
    # Exact content rather than count: label/qualifier maps and named tuple read.
    rich=[rec(1,'create_node',new=''),rec(1,'add_label',new='',attr='L',ordinal=2),
          rec(1,'set_prop',new='1',attr='k',ordinal=3),
          rec(2,'create_rel',new=json.dumps({'s':'n','p':'R','o':'n','graph':'g'}),kind='rel',id='7'),
          rec(2,'set_qual',new='9',attr='w',kind='rel',id='7',ordinal=2),
          rec(3,'set_qual',prior='9',new='10',attr='w',kind='rel',id='7')]
    rg=hf.ledger(rich,100);state=rg.reconstruct('2')
    assert state.nodes['n'].labels=={'L'} and state.nodes['n'].props=={'k':'1'}
    assert state.statements['7'].tuple==('n','R','n','g') and state.statements['7'].quals=={'w':'9'}
    assert rg.diff('2','3').to_list()==[{'entity_kind':'rel','entity_id':'7','attr':'qual:w','before':'9','after':'10'}]
    detection={'last_prior_mutant':bool(mut),'changed_observation':bool(changed)}
    out=bc.write_receipt('history_diff',Path(__file__),{'verdict':'AGREES' if not mism and all(detection.values()) else 'DISAGREES',
        'comparisons':n,'continuous_endpoint_comparisons':cont,'mismatch_count':len(mism),'mismatches':mism[:5],
        'detection':detection,'simple_reverse_snapshot':simple_rev,'changed_before_delete_reverse':reverse,
        'original_endpoint':normalized(strong[:2]),'pin':bc.pin_identity(PIN),
        'domain':'all admitted single-node histories length 0..4 from 6 operations, every named endpoint pair; no-ops omitted; rich label/qualifier/tuple neighbor',
        'substituted':'SQL provider, revision IDs/meta, redaction guard, ObjectScript writer/snapshot; real GraphLedger.diff/reconstruct, SQL decoder, lifecycle fold and inverse execute'})
    d=json.loads(out.read_text())
    for f in ['iris_vector_graph/ledger/replay.py','iris_vector_graph/ledger/client.py','iris_src/src/Graph/KG/LedgerApply.cls',str(Path(hf.__file__).relative_to(bc.REPO))]:d['inputs'][f]=bc.sha(bc.REPO/f)
    out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(f"history_diff: {d['verdict']}; {n} named pairs, {cont} continuous endpoint checks; {out}")
    return int(d['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
