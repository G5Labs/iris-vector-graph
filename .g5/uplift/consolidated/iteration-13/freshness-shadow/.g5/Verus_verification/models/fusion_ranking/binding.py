"""Real Python rank producer, fusion and detailed top-k consumer; IRIS legs substituted.
Hand mathematical oracle mirrors the Verus rank/score specs. It is unverified.
"""
import inspect,itertools,json,logging,math,sys,textwrap
from fractions import Fraction
from pathlib import Path
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_vector_graph import fusion as F


def scores(lists,c=60):
    out={}
    for rows in lists:
        seen=set()
        for i,(id,_) in enumerate(rows,1):
            if id in seen:continue
            seen.add(id);out[id]=out.get(id,Fraction())+Fraction(1,c+i)
    return out


def agrees(got,want):
    return set(dict(got))==set(want) and len(got)==len(want) and all(math.isclose(v,float(want[id]),rel_tol=1e-13) for id,v in got) and all(got[i][1]>=got[i+1][1] for i in range(len(got)-1))


def compare(fn=None,change=False):
    choices=[('a',-9),('a',999),('b',-9),('b',999)]
    lists=[list(xs) for n in range(4) for xs in itertools.product(choices,repeat=n)]
    mism=[];n=0
    for a,b,c in itertools.product(lists,lists,[1,60]):
        got=(fn or F.RRFFusion.fuse_results)([a,b],c);want=scores([a,b],c)
        if change and n==0:got=[('wrong',1)]
        if not agrees(got,want):mism.append({'a':a,'b':b,'c':c,'got':got,'want':{id:float(x) for id,x in want.items()}})
        n+=1
    return n,mism


class Providers:
    def __init__(self,v,t,g):self.replies=[v,t,g];self.calls=[]
    def ask(self,mode,*a,**kw):
        self.calls.append((mode,a,kw));r=self.replies[mode]
        if r=='error':raise RuntimeError('provider-failure')
        return r
    def kg_KNN_VEC(self,*a,**kw):return self.ask(0,*a,**kw)
    def kg_TXT(self,*a,**kw):return self.ask(1,*a,**kw)
    def kg_NEIGHBORHOOD_EXPANSION(self,*a,**kw):return self.ask(2,*a,**kw)


def journey():
    options=[None,'error',[],[('a',1),('b',900)]];graph=[[], 'error',[{'target':'b','confidence':800},{'target':'b','confidence':200}]]
    n=0;mism=[]
    for v,t,g,k in itertools.product(options,options,graph,[1,2]):
        if v is None and t is None:continue
        p=Providers(v,t,g);wrapper=F.HybridSearchFusion(p)
        try:got=wrapper.multi_modal_search(query_vector='[1]' if v is not None else None,query_text='q' if t is not None else None,k=k,graph='fixture');error=False
        except RuntimeError:got=[];error=True
        lists=[];modes=[]
        for mode,rows in [('vector',v),('text',t)]:
            if rows is not None and rows!='error':lists.append(rows);modes.append(mode)
        expected_error=t=='error'
        seeds={id for rows in lists for id,_ in rows[:k]}
        if not expected_error and seeds and g!='error':
            lists.append([] if g==[] else [('b',.8)]);modes.append('graph')
        want=scores(lists)
        good=error==expected_error
        if not error:
            returned=[(r['entity_id'],r['fusion_score']) for r in got]
            # Ties have no promised order, including at a k cutoff.
            allowed=sorted(want.values(),reverse=True)[:k]
            good &= len(returned)==len(allowed) and all(math.isclose(s,float(want[id]),rel_tol=1e-13) for id,s in returned)
            good &= all(math.isclose(r['fusion_score'],float(s),rel_tol=1e-13) and r['rank']==i+1 for i,(r,s) in enumerate(zip(got,allowed)))
            for r in got:
                good &= [m['mode'] for m in r['search_modes']]==modes
                for detail,rows in zip(r['search_modes'],lists):
                    first=next(((j+1,s) for j,(id,s) in enumerate(rows) if id==r['entity_id']),(None,0.0))
                    good &= (detail['rank'],detail['score'])==first
        good &= all(call[2]['graph']=='fixture' for call in p.calls)
        if not good:mism.append({'v':v,'t':t,'g':g,'k':k,'got':got,'error':error,'modes':modes})
        n+=1
    # Chosen observable pair, not just the normalized rank helper.
    p=Providers([('a',1),('b',1000)],None,[])
    one=F.HybridSearchFusion(p).multi_modal_search(query_vector='[1]',k=1)[0]['entity_id']
    p=Providers([('a',1),('b',1000)],[('b',-1000)],[])
    two=F.HybridSearchFusion(p).multi_modal_search(query_vector='[1]',query_text='q',k=1)[0]['entity_id']
    assert [one,two]==['a','b']
    return n,mism


def main():
    n,mism=compare();_,changed=compare(change=True)
    src=textwrap.dedent(inspect.getsource(F.RRFFusion.fuse_results));scope=dict(vars(F))
    assert src.count('break')==1
    exec(src.replace('@staticmethod\n','').replace('break','pass'),scope);_,mut=compare(scope['fuse_results'])
    j,errors=journey();detection={'last_rank_product_mutant':bool(mut),'changed_deciding_observation':bool(changed)}
    pin=bc.pin_identity(PIN_DIR);pin['files_equal_pin_blobs']['iris_vector_graph/fusion.py']=bc.sha(PIN_DIR/'iris_vector_graph/fusion.py')==bc.sha(bc.REPO/'iris_vector_graph/fusion.py');pin['all_equal'] &= all(pin['files_equal_pin_blobs'].values())
    out=bc.write_receipt('fusion_ranking',Path(__file__),{'verdict':'AGREES' if not mism and not errors and all(detection.values()) and pin['all_equal'] else 'DISAGREES',
        'comparisons':n,'journeys':j,'mismatch_count':len(mism)+len(errors),'mismatches':mism[:3]+errors[:3],'detection':detection,'pin':pin,
        'domain':'two lists, each length 0..3, IDs a/b and raw scores -9/999, c 1/60; wrapper provider rows/empty/error/not requested, graph expansion duplicate targets, k 1/2',
        'substituted':'IRIS vector/text/graph providers; actual first-rank producer, RRF helper, leg failure catches, graph max confidence, detailed consumer and top-k execute',
        'limits':'Verus proves mathematical scores and the strict pair winner, not Python floating point or general sort; graph expansion detail is observed only'})
    data=json.loads(out.read_text());data['inputs']['iris_vector_graph/fusion.py']=bc.sha(PIN_DIR/'iris_vector_graph/fusion.py')
    out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    print(f"fusion_ranking: {data['verdict']}; {n} rank cases + {j} journeys; {data['mismatch_count']} mismatches; {detection}; {out}")
    return int(data['verdict']!='AGREES')
if __name__=='__main__':raise SystemExit(main())
