"""Actual metadata writer/SQL/parser/public handler on guarded task-owned IRIS."""
import ast,hashlib,json,runpy,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
helper=REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'
h=runpy.run_path(str(helper));binding=REPO/'.g5/Verus_verification/models/procedure_results/binding.py'
# Extract only the pure independent oracle; never import the SQLite adapter.
tree=ast.parse(binding.read_text());node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='expect')
ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(binding),'exec'),ns);expect=ns['expect']
def main():
    c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);e.ledger.disable();e.erase_all();results=[];mism=[]
    cases=[('all',True,None),('eqA',True,None),('eqC',True,None),('all',False,None),('all',False,'l'),('all',True,'l'),('unsupported',True,None),('missing',True,None)]
    for populated in [False,True]:
        if populated:
            assert e.create_node('proc:a',labels=['A'])
            e.bulk_create_nodes([{'id':'proc:b','labels':['B']},{'id':'proc:c','labels':['A']}],graph='proc_other')
        labels=['A','B','A'] if populated else []
        for kind,ret,order in cases:
            q='CALL db.labels() YIELD label AS l'
            if kind=='eqA':q+=" WHERE l = 'A'"
            if kind=='eqC':q+=" WHERE l = 'C'"
            if kind=='unsupported':q+=" WHERE l STARTS WITH 'A'"
            if kind=='missing':q+=' WHERE l = $wanted'
            if ret:q+=' RETURN l'
            if order:q+=' ORDER BY '+order
            wanted=expect(labels,'l',kind,ret,order,0,None)
            try:
                r=e.execute_cypher(q,{},raise_on_error=True);got={'columns':r.columns,'rows':r.rows,'error':r.error}
            except ValueError as ex:got={'refused':True,'message':str(ex)}
            ok=all(got.get(k)==v for k,v in wanted.items());results.append({'populated':populated,'query':q,'expected':wanted,'got':got,'agrees':ok})
            if not ok:mism.append(q)
        extra=[(f'CALL db.labels() YIELD absent AS {alias} RETURN {alias}',expect(labels,alias,'all',True,None,0,None,source='absent')) for alias in ['label','l']]
        for q,wanted in [("CALL db.labels() YIELD label WITH label WHERE label='B' RETURN label",expect(labels,'label','eqC',True,None,0,None)),('CALL db.labels() YIELD label MATCH (n:X) RETURN label',{'refused':True}),*extra]:
            if 'WITH' in q:wanted={'columns':['label'],'rows':[['B']] if populated else [],'error':None}
            try:
                r=e.execute_cypher(q,{},raise_on_error=True);got={'columns':r.columns,'rows':r.rows,'error':r.error}
            except ValueError as ex:got={'refused':True,'message':str(ex)}
            ok=all(got.get(k)==v for k,v in wanted.items());results.append({'populated':populated,'query':q,'expected':wanted,'got':got,'agrees':ok})
            if not ok:mism.append(q)
    out={'verdict':'AGREES' if not mism else 'DISAGREES','comparisons':len(results),'mismatches':mism,'cases':results,'container':h['NAME'],'identity_checked':True,
        'scope':'actual default single/named bulk writers -> unscoped SQL DISTINCT metadata -> parser/filter/projection/tail/public reader; empty and nonempty normal/refused neighbors. Not all SQLite panel repeated, no generic procedure/numeric/Unicode/concurrency claim.',
        'inputs':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [helper,binding,Path(__file__)]}}
    Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'verdict':out['verdict'],'comparisons':len(results),'mismatches':mism}));c.close();assert not mism
if __name__=='__main__':main()
