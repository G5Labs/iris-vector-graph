"""Read the retained mode-off fixture before replacing it with a valid multi fixture."""
import hashlib,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
h=runpy.run_path(str(REPO/'.g5/Verus_verification/models/temporal_restore/binding.py'))
c=h['connect']();e=h['IRISGraphEngine'](c,embedding_dimension=8);n=e._iris_obj()
g=n.classMethodValue('Graph.KG.GraphKey','ForIndex','wp9:multi')
out={'container':h['NAME'],'identity_checked':True,'graph':'wp9:multi','graph_key':g,
     'is_multi':n.classMethodValue('Graph.KG.GraphMode','IsMulti','wp9:multi'),
     'raw_mode':n.get('^IVG.GraphMode',g),'points':[]}
for direction,a,b in [('out','wp9:s','wp9:t'),('in','wp9:t','wp9:s')]:
    for suffix in [[],[0],[5],['#']]:
        out['points'].append({'direction':direction,'suffix':suffix,'value':n.get('^KG',direction,g,a,'R',b,*suffix)})
out['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
Path(__file__).with_suffix('.json').write_text(json.dumps(out,indent=2,default=str)+'\n');c.close()
print(json.dumps(out,default=str))
