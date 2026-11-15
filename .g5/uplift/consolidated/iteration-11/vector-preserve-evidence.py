"""Read-only inventory + byte-exact deduplicated preservation of vector evidence.
No model/tests/product/native/Git operations. Originals are never moved or rewritten.
"""
from pathlib import Path
import collections,datetime,hashlib,json,shutil
REPO=Path('/Users/ziniuw/Desktop/projects/G5-benchmark/iris-vector-graph')
ITER=REPO/'.g5/uplift/consolidated/iteration-11'
MODEL=REPO/'.g5/Verus_verification/models/vector_admission'
RESULTS=REPO/'.g5/Verus_verification/results/vector_admission'
RUN=Path('/Users/ziniuw/runs/ivg-iteration11-vector-20261115/verus/vector_admission')
STORE=ITER/'vector-preserved-evidence'
MANIFEST=ITER/'vector-preserved-evidence.json'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def label(p):
 try:return str(p.relative_to(REPO))
 except ValueError:return str(p)
def relevant(p):return p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.rs','.py','.md','.json','.log','.txt')
def descendants(root):return sorted(p for p in root.rglob('*') if relevant(p)) if root.exists() else []
# All relevant vector/reviewer files already under11 are canonical first choices.
existing=[]
for child in sorted(ITER.iterdir()):
 if child.name.startswith(('vector-','review-vector')) and child not in (STORE,MANIFEST,Path(__file__).resolve()):
  existing.extend(descendants(child) if child.is_dir() else ([child] if relevant(child) else []))
by_hash=collections.defaultdict(list)
for p in existing:by_hash[digest(p)].append(p)
# These exact source snapshots, receipts and logs are elsewhere in .g5 or the owned run directory.
originals=sorted(set(descendants(MODEL)+descendants(RESULTS)+descendants(RUN)))
entries=[];copies=[]
for src in originals:
 h=digest(src);n=src.stat().st_size
 if by_hash[h]:
  dest=by_hash[h][0];status='already_preserved_under_iteration11'
 else:
  dest=STORE/'objects'/h[:2]/(h+'__'+src.name)
  dest.parent.mkdir(parents=True,exist_ok=True)
  created=not dest.exists()
  if not created:assert digest(dest)==h,(src,dest)
  else:shutil.copyfile(src,dest)
  assert digest(dest)==h and src.stat().st_size==dest.stat().st_size
  by_hash[h].append(dest)
  if created:copies.append(dict(source=label(src),preserved=label(dest),sha256=h,bytes=n))
  status='new_byte_exact_deduplicated_copy' if created else 'already_in_task_evidence_store'
 entries.append(dict(original=label(src),sha256=h,bytes=n,preserved=label(dest),status=status))
# Describe every already-present exact reviewer vector artifact without duplicating its tree.
review_files=[]
for p in existing:
 if p.name.startswith('review-vector') or any(x.startswith('review-vector') for x in p.relative_to(ITER).parts):
  review_files.append(dict(path=label(p),sha256=digest(p),bytes=p.stat().st_size))
builder_files=[dict(path=label(p),sha256=digest(p),bytes=p.stat().st_size) for p in existing if not any(x.startswith('review-vector') for x in p.relative_to(ITER).parts)]
# Receipt input digests reveal which historical exact inputs are recoverable from actual bytes.
# Never claim that a later file or a reconstruction from diagnostic snippets is the missing original.
all_receipts=sorted(set([p for p in originals+existing if p.name=='receipt.json']))
refs=collections.defaultdict(list)
for rp in all_receipts:
 try:d=json.loads(rp.read_text())
 except (ValueError,UnicodeError):continue
 for name,h in d.get('inputs',{}).items():
  if '/models/vector_admission/' in name or name.endswith('/binding_common.py'):
   refs[(name,h)].append(label(rp))
coverage=[];unavailable=[]
for (name,h),receipts in sorted(refs.items()):
 matches=by_hash.get(h,[])
 # Shared current helper is allowed read-only; preserve it if neither scratch has its exact bytes.
 if not matches:
  p=REPO/name
  if p.is_file() and digest(p)==h:
   dest=STORE/'objects'/h[:2]/(h+'__'+p.name);dest.parent.mkdir(parents=True,exist_ok=True)
   if not dest.exists():shutil.copyfile(p,dest)
   assert digest(dest)==h;by_hash[h].append(dest);matches=[dest];copies.append(dict(source=label(p),preserved=label(dest),sha256=h,bytes=p.stat().st_size))
 item=dict(input=name,sha256=h,receipt_references=receipts,exact_bytes_available=bool(matches),preserved_paths=[label(p) for p in matches])
 coverage.append(item)
 if not matches:unavailable.append(item)
# Assert the preservation pass itself did not alter any inventoried source or existing reviewer artifact.
for row in entries:
 p=REPO/row['original'] if not Path(row['original']).is_absolute() else Path(row['original'])
 assert p.is_file() and digest(p)==row['sha256'],row['original']
for row in review_files+builder_files:assert digest(REPO/row['path'])==row['sha256'],row['path']
store_files=[dict(path=label(p),sha256=digest(p),bytes=p.stat().st_size) for p in descendants(STORE)]
summary=dict(preserved_unique_store_objects=len(store_files),preserved_store_bytes=sum(x['bytes'] for x in store_files),existing_builder_files=len(builder_files),original_files=len(entries),reviewer_existing_files=len(review_files),new_unique_copies=len(copies),new_bytes=sum(x['bytes'] for x in copies),receipt_input_versions=len(coverage),available_exact_input_versions=sum(x['exact_bytes_available'] for x in coverage),unavailable_exact_input_versions=len(unavailable))
body=dict(status='PRESERVED_AVAILABLE_EXACT_EVIDENCE',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Vector builder/reviewer V1/V2 and intermediate attempt evidence only; no new tests, model edits, Git, native or shared-file changes.',summary=summary,method='Hash inventory of exact existing bytes; reuse matching files already under iteration11; copy only absent content hashes into content-addressed objects. Originals never moved/rewritten. Byte hashes and lengths checked after each copy; original inventory rechecked after pass.',script=dict(path=label(Path(__file__).resolve()),sha256=digest(Path(__file__).resolve())),inventory_roots=[label(p) for p in [MODEL,RESULTS,RUN]],reviewer_roots_already_under11=[label(ITER/p) for p in ['review-vector-scratch','review-vector-v2-scratch','review-vector-ttl-challenge-inputs']],builder_snapshot_groups={p.name:[label(x) for x in descendants(p)] for p in RESULTS.iterdir() if p.is_dir() and (p.name.startswith('attempt') or p.name=='frozen-v1')},original_inventory=entries,new_copies=copies,existing_builder_inventory=builder_files,existing_reviewer_inventory=review_files,preserved_store_inventory=store_files,receipt_input_coverage=coverage,unavailable_originals=unavailable,unavailability_explanation='An unavailable row means no exact byte sequence matching that historical receipt input digest was found in the current model, preserved69/76/module-target/V1 snapshots, builder control snapshots/run logs, explicit binding-attempt copies, or exact V1/V2 reviewer scratch trees. Earlier live candidate files were edited before a full source snapshot was saved. Their original receipt/input digest and raw diagnostics remain preserved, but later files are not substituted and original source is not invented from diagnostics. Environment providers (pinned Verus executable, Python executable/sitepackages) are named/versioned by receipts, not newly copied source artifacts. Root will additionally archive whole .g5; this manifest does not claim missing bytes were recovered.',verification='All original inventoried files and all listed already-present reviewer files retained their initial SHA256 after the preservation pass.')
MANIFEST.write_text(json.dumps(body,indent=2)+'\n')
print(json.dumps(summary))
print(str(MANIFEST))
