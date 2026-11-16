"""Check every staged .g5 file/link against raw worktree bytes without filters."""
import hashlib,json,os,stat,subprocess,sys,time
from pathlib import Path
start=time.monotonic();R=Path.cwd();items=subprocess.check_output(['git','ls-files','--stage','-z','--','.g5']).split(b'\0');bad=[];count=links=size=0
for item in items:
 if not item:continue
 head,rawpath=item.split(b'\t',1);mode,oid,stage=head.decode().split();path=os.fsdecode(rawpath);p=R/path
 if stage!='0':bad.append(dict(path=path,reason='unmerged index stage'));continue
 if mode=='120000':
  if not p.is_symlink():bad.append(dict(path=path,reason='expected symlink'));continue
  data=os.fsencode(os.readlink(p));links+=1
 else:
  if not p.is_file() or p.is_symlink():bad.append(dict(path=path,reason='expected regular file'));continue
  data=p.read_bytes()
 digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();count+=1;size+=len(data)
 if digest!=oid:bad.append(dict(path=path,reason='staged blob differs from raw worktree bytes',staged=oid,raw=digest))
out=dict(verdict='PASS_EXACT_STAGED_BYTES' if not bad else 'FAILED',checked=count,symlinks=links,raw_bytes=size,mismatches=bad,elapsed_s=time.monotonic()-start,scope='Every index .g5 entry as of this check; raw Git blob identity, no text filters. No product/native/model execution or unassessed external inputs. Output is not self-hashed.')
if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(out,indent=2)+'\n')
summary={k:out[k] for k in ['verdict','checked','symlinks','raw_bytes','elapsed_s']}
summary['mismatches']=len(bad)
print(json.dumps(summary))
raise SystemExit(1 if bad else 0)
