"""Mechanical sweep for merged obligation rows (iteration 66, review-1 R1-CB-05).
Flags a row when its statement or cases column shows signs of several separately-failing outcomes.
Deterministic; reads .g5/Verus_verification/census/obligations.tsv (run from the repository root).
Usage: python3 sweep.py [obligations.tsv] > flagged.tsv"""
import csv, re, sys
csv.field_size_limit(10**9)
p = sys.argv[1] if len(sys.argv) > 1 else '.g5/Verus_verification/census/obligations.tsv'
rows = list(csv.DictReader(open(p, encoding='utf-8', newline=''), delimiter='\t', quoting=csv.QUOTE_NONE))
SKIP = ('query.native', 'query.shadow', 'query.compiled', 'erasure.', 'search.erasure', 'algorithms.cache.erasure',
        'structure.degree.cache.erase')
ENTRY = re.compile(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b|\b[A-Z][a-zA-Z]+\.[A-Z][a-zA-Z]+\b|\b\w+\(\)')
def flags(r):
    s, c = r['statement'], r['cases']
    f = []
    if ';' in s: f.append('S1:semicolon-clauses')
    if re.search(r'\brefus', s, re.I) and re.search(r'\bnative\b|\bdirect\b|\bObjectScript\b', s): f.append('S2:refusal+native')
    if re.search(r'\bwhile\b|\bwhereas\b|\bbut\b|\botherwise\b', s): f.append('S3:contrast-clause')
    ents = set(ENTRY.findall(s))
    if len(ents) >= 3 or re.search(r'\b\w+/\w+(?:/\w+)+', s): f.append('S4:several-entry-points')
    if s.count(',') >= 3 and ' and ' in s: f.append('S5:enumeration>=3')
    if c.count(';') >= 2: f.append('C1:cases>=3-separated')
    return f
out = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
out.writerow(['id', 'grade', 'flags', 'statement'])
n = 0
for r in rows:
    if r['id'].startswith(SKIP): continue
    f = flags(r)
    if len(f) >= 2 or 'S2:refusal+native' in f or 'S1:semicolon-clauses' in f:
        out.writerow([r['id'], r['grade'], ','.join(f), r['statement']]); n += 1
print(f'# flagged {n} of {sum(1 for r in rows if not r["id"].startswith(SKIP))} rows', file=sys.stderr)
