"""Preserve exact independent scratch model/results in the sealed foundation."""
import hashlib,json,shutil
from pathlib import Path
R=Path.cwd();O=R/'.g5/uplift/consolidated/iteration-10';records=[]
items=[('cost-review-replay-start.json','weighted_cost','cost81'),('cost-review-attempt83-validation.json','weighted_cost','cost83'),('cost-review-validation.json','weighted_cost','cost88'),('ppr-review-validation.json','ppr_walk','ppr103')]
for origin,fam,label in items:
 d=json.loads((O/origin).read_text());scratch=Path(d['scratch']);dest=O/'independent-review-artifacts'/label
 for part in ['models','results']:
  source=scratch/'.g5/Verus_verification'/part/fam
  if not source.exists():continue
  for p in source.rglob('*'):
   if not p.is_file() or '__pycache__' in p.parts:continue
   q=dest/part/fam/p.relative_to(source);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
   h=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(q.read_bytes()).hexdigest()==h
   records.append(dict(original=str(p),preserved=str(q.relative_to(R)),sha256=h))
 # Source81/83 kernels may import the unchanged JSON kernel; retain exact source.
 p=scratch/'.g5/Verus_verification/models/weighted_paths/weighted_paths.rs'
 if fam=='weighted_cost' and p.exists():
  q=dest/'models/weighted_paths/weighted_paths.rs';q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);records.append(dict(original=str(p),preserved=str(q.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(O/'independent-review-artifacts.json').write_text(json.dumps(dict(files=records,count=len(records),scope='Exact independent scratch candidate inputs and all family receipts/raw logs, including superseded81/83 and initial PPR failures. Original absolute receipt paths are preserved. These copies are archival, not registered active models or new runs.'),indent=2)+'\n');print(json.dumps(dict(preserved_files=len(records))))
