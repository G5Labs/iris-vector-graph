"""Re-search (review-1 'stale grades'): rows graded before iteration 65 (excluding the native/erasure-owned prefixes)
whose block, statement, cases or gap name a behaviour the iteration-62 native_admission or iteration-65 erasure_stores
models represent. Mechanical keyword match; each candidate is then judged by hand (research-decisions.tsv)."""
import csv, re, sys
csv.field_size_limit(10**9)
rows = list(csv.DictReader(open(sys.argv[1], newline='', encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
SKIP = ('query.native', 'query.shadow', 'query.compiled', 'erasure.', 'search.erasure', 'algorithms.cache.erasure',
        'structure.degree.cache.erase')
KW = {
 'erasure_stores': r"\berase|\berasure|delete_node|delete_nodes|drop_graph|bulk_delete|delete_edge\b|delete_by_prefix|nodes_by_prefix|EraseGraph|Eraser|reifier.{0,30}delet|delet.{0,30}reifier|\^NKG|AlgoCache|AdjNoLock|watermark.{0,20}reset|from_connect",
 'native_admission': r"\bnative executor|native_cypher|IVG_NATIVE|Exec\.Run|\bshadow\b|native_route|route trial|\bnatively\b|native path|native and SQL|_try_native|plan_query|REVOKE|executor version|DropAll|compiled plan",
}
out = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
out.writerow(['id', 'iteration', 'grade', 'model', 'statement'])
for r in rows:
    if r['id'].startswith(SKIP): continue
    try: it = int(r['iteration'])
    except ValueError: it = 0
    if it >= 65: continue
    text = ' '.join([r['block'], r['statement'], r['cases'], r['gap']])
    for m, kw in KW.items():
        if re.search(kw, text, re.I):
            out.writerow([r['id'], r['iteration'], r['grade'], m, r['statement']])
