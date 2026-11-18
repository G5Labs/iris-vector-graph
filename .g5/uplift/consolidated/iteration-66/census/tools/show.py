import csv,sys
csv.field_size_limit(10**9)
p='.g5/Verus_verification/census/obligations.tsv'
rows=list(csv.DictReader(open(p,newline='',encoding='utf-8'),delimiter='\t'))
for a in sys.argv[1:]:
    for r in rows:
        if r['id']==a or (a.endswith('#') and r['id'].startswith(a)):
            print('=====',r['id'])
            for k,v in r.items():
                if k!='id': print(f'  {k}: {v}')
