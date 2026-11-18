import sys,csv
root=sys.argv[1]; ids=sys.argv[2:]
csv.field_size_limit(10**9)
for fn in ['obligations.tsv','excluded.tsv']:
    R=list(csv.reader(open(root+'/.g5/Verus_verification/census/'+fn),delimiter='\t',quoting=csv.QUOTE_NONE))
    h=R[0]
    for r in R[1:]:
        if r[0].split('#')[0] in ids:
            print('-----',fn,r[0])
            for k,v in zip(h[1:],r[1:]):
                print(f'  {k}: {v}')
