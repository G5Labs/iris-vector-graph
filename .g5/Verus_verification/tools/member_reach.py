#!/usr/bin/env python3
"""Deterministic named production member census and behavior binding locators.

Python classes/functions/methods outside function bodies, identity path+qualified
name, conditional redeclarations deduplicated. ObjectScript named methods/queries/
triggers. Roots iris_vector_graph/ and iris_src/. SQL has no comparable named-member
unit; api/, src/, scripts/ are outside this historical scoped frame, reported openly.
Resolution establishes a scoped locator; semantic audit and role completeness are
reported separately. --revision reads that whole foundation/product snapshot.
"""
import argparse,ast,collections,csv,io,json,re,subprocess
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
PIN='3eaa79cf77d3e0a879b2cced634cf2729d81499e'
ROOTS=['iris_vector_graph/','iris_src/']
def git(*args):return subprocess.check_output(['git','-C',str(REPO),*args],text=True)
def census():
    members={}
    for path in git('ls-tree','-r','--name-only',PIN,'--',*ROOTS).splitlines():
        if not path.endswith(('.py','.cls')):continue
        s=git('show',PIN+':'+path)
        if path.endswith('.py'):
            def walk(node,prefix=''):
                for n in ast.iter_child_nodes(node):
                    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                        name=prefix+n.name;key=path+'::'+name
                        item=members.setdefault(key,{'path':path,'symbol':name,'kind':'class' if isinstance(n,ast.ClassDef) else 'function','lines':[]})
                        item['lines'].append(n.lineno)
                        if isinstance(n,ast.ClassDef):walk(n,name+'.')
                    else:walk(n,prefix)
            walk(ast.parse(s))
        else:
            for m in re.finditer(r'^(ClassMethod|Method|Query|Trigger)\s+([A-Za-z%][A-Za-z0-9]*)',s,re.M):
                key=path+'::'+m[2]
                item=members.setdefault(key,{'path':path,'symbol':m[2],'kind':m[1],'lines':[]})
                item['lines'].append(s[:m.start()].count('\n')+1)
    return members
def main():
    a=argparse.ArgumentParser();a.add_argument('--revision');a.add_argument('--out',required=True);args=a.parse_args()
    def read(p):return git('show',args.revision+':'+p) if args.revision else (REPO/p).read_text()
    members=census();v='.g5/Verus_verification/'
    families={r['family_id']:r['status'] for r in csv.DictReader(io.StringIO(read(v+'families.tsv')),delimiter='\t')}
    bound=collections.defaultdict(list);rejected=[]
    for r in csv.DictReader(io.StringIO(read(v+'crosswalk/decision-links.tsv')),delimiter='\t'):
        key=r['path']+'::'+r['symbol'];item=r['formal item'];fp,_,fn=item.partition('::')
        family=r['family'].replace('P-proofs-','playbook-proofs-')
        reason=None
        if key not in members:reason='outside named frame/supporting input'
        elif len(members[key]['lines'])!=1:reason='ambiguous conditional declaration'
        elif not families.get(family,'').startswith('active'):reason='inactive family'
        elif r['relation'] not in ('models','proves','witnesses') or not fn:reason='citation/observation only'
        else:
            try:resolved=len(re.findall(r'\bfn\s+'+re.escape(fn)+r'\b',read(fp)))==1
            except (FileNotFoundError,subprocess.CalledProcessError):resolved=False
            if not resolved:reason='unresolved formal declaration'
        if reason:rejected.append({'member':key,'reason':reason});continue
        bound[key].append(r)
    groups=collections.defaultdict(list)
    for key,m in members.items():
        if key not in bound:
            subsystem='/'.join(m['path'].split('/')[:2])
            groups[subsystem].append(key)
    summary={'product_pin':PIN,'foundation_revision':args.revision or 'working tree','roots':ROOTS,
        'unit':'named Python class/function/method outside function bodies; ObjectScript ClassMethod/Method/Query/Trigger; path::qualified-name, conditional redeclarations once',
        'denominator':len(members),'resolvable_active_behavior_bindings':len(bound),
        'direct_executable_body_verified':0,
        'qualification':'Scoped active declaration bindings with source-side role/grade; resolution is a locator. Semantic sample and expected-role audit remain separate, no whole-method claim.',
        'unlinked_by_subsystem':{k:len(v) for k,v in sorted(groups.items())},
        'conditional_redeclarations':{k:m['lines'] for k,m in members.items() if len(m['lines'])>1},
        'outside_frame':['api/','src/','scripts/','tests/','sql/ statement files (not named members)','local functions/classes within function bodies'],
        'historical_bridge':'4129 scoped members and 93 exact declaration pairs at iteration3 are locators. Historical citation+mapping union335 is not a behavior binding numerator.'}
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'census.json').write_text(json.dumps(members,indent=2)+'\n')
    (out/'bindings.json').write_text(json.dumps(bound,indent=2)+'\n')
    (out/'unlinked.json').write_text(json.dumps(dict(sorted(groups.items())),indent=2)+'\n')
    (out/'rejected.json').write_text(json.dumps(rejected,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
