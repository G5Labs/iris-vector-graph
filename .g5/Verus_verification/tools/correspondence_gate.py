#!/usr/bin/env python3
"""Separate proof-input reuse from product correspondence reuse, conservatively.

capture RECEIPT records the current formal inputs/tool binaries and every production
file/name in the scoped source roots. check RECEIPT [--root DISPOSABLE_COPY] reports
proof stale separately from correspondence stale. Any added/renamed/removed file,
member or writer in these roots reopens all product bindings, even when proofs reuse.
Full-file hashes catch unbound local functions, dispatch registrations and imports.
External providers/configuration remain named premises, not captured live state.
"""
import argparse,hashlib,json,os
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inputs(root):
    product={str(p.relative_to(root)):sha(p) for d in ['iris_vector_graph','iris_src'] for p in (root/d).rglob('*') if p.is_file() and p.suffix in ['.py','.cls','.sql']}
    formal={str(p.relative_to(root)):sha(p) for p in (root/'.g5/Verus_verification/models').rglob('*') if p.is_file() and (p.suffix=='.rs' or p.name=='model.json')}
    for p in (root/'.g5/Verus_verification/models').glob('*/binding.py'):
        product[str(p.relative_to(root))]=sha(p)
    for n in ['tools/binding_common.py']:
        p=root/'.g5/Verus_verification'/n;product[str(p.relative_to(root))]=sha(p)
    p=root/'.g5/Verus_verification/run_verus.py';formal[str(p.relative_to(root))]=sha(p)
    for n in ['SOURCE.json','SOURCE-consolidated.json']:
        p=root/'.g5/Verus_verification'/n;formal[str(p.relative_to(root))]=sha(p)
    for n in ['verus','z3']:
        p=Path(os.environ.get('VERUS_BIN',str(Path.home()/'.cache/g5-verification/0.2026.10.04.426d8b0/verus-arm64-macos/verus'))).parent/n
        formal['external:'+str(p)]=sha(p) if p.is_file() else None
    return {'product':product,'formal':formal}
def changes(old,new):return sorted(k for k in old.keys()|new.keys() if old.get(k)!=new.get(k))
def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=['capture','check']);a.add_argument('receipt');a.add_argument('--root',type=Path,default=REPO);args=a.parse_args()
    now=inputs(args.root);p=Path(args.receipt)
    if args.action=='capture':
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(now,indent=2)+'\n');print('CAPTURED');return 0
    old=json.loads(p.read_text());pc=changes(old['product'],now['product']);fc=changes(old['formal'],now['formal'])
    print(json.dumps({'proof':'STALE_ALL' if fc else 'REUSABLE_INPUTS','correspondence':'STALE_ALL' if pc or fc else 'REUSABLE_INPUTS','changed_product':pc,'changed_formal':fc,'scope':'all scoped model bindings; full file/name manifest discovers competing/new writers; no provider freshness claim'},indent=2))
    return int(bool(pc or fc))
if __name__=='__main__':raise SystemExit(main())
