"""Trace-only subprocess audit and socket guard for exact ordinary scratch runs."""
from pathlib import Path
import json,os,runpy,socket,sys
from unittest.mock import patch
log=Path(os.environ['REVIEW_SUBPROCESS_LOG']);allowed_prefixes=('3eaa79cf77d3e0a879b2cced634cf2729d81499e:','198365a3e726bac66d5c67901a1b86e2238cbc47:')
def audit(event,args):
 if event!='subprocess.Popen':return
 executable,argv,cwd,env=args;argv=[str(x) for x in argv] if isinstance(argv,(list,tuple)) else [str(argv)]
 row={'executable':str(executable),'argv':argv,'cwd':str(cwd) if cwd else None}
 if argv and Path(argv[0]).name=='git':
  command=argv[1:]
  if command[:1]==['-C']:command=command[2:]
  op=command[0] if command else '';tail=command[1:]
  permitted=(op in ('rev-parse','show') and len(tail)==1 and tail[0].startswith(allowed_prefixes)) or (op=='hash-object' and len(tail)==1 and not tail[0].startswith('-') and Path(tail[0]).resolve().is_relative_to(Path(os.environ['IVG_PIN_DIR']).resolve()))
  row['git_read_only_permitted']=permitted
  with log.open('a') as f:f.write(json.dumps(row)+'\n')
  if not permitted:raise AssertionError('outside authorized fixed-source Git identity operation')
 else:
  with log.open('a') as f:f.write(json.dumps(row)+'\n')
sys.addaudithook(audit)
sys.argv=sys.argv[1:]
with patch.object(socket.socket,'connect',side_effect=AssertionError('independent ordinary review forbids sockets')) as guard:
 try:runpy.run_path(sys.argv[0],run_name='__main__')
 finally:print('REVIEW_OUTER_SOCKET_CONNECT_CALLS',guard.call_count)
