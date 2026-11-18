import sys,re,glob,os
root=sys.argv[1]; ids=sys.argv[2:]
files=glob.glob(os.path.join(root,'.g5/ontology/**/*.g5.md'),recursive=True)
for bid in ids:
    for f in files:
        L=open(f).read().split('\n')
        for i,l in enumerate(L):
            if re.search(r'\[[ID] · '+re.escape(bid)+r'\]',l):
                out=[l]
                for m in L[i+1:]:
                    if m.startswith('<a id=') or m.startswith('#'): break
                    out.append(m)
                print('=====',bid,os.path.relpath(f,root),'line',i+1)
                print('\n'.join(out).rstrip())
                # metadata section
                for j,m in enumerate(L):
                    if m.strip()=='### '+bid:
                        k=j+1; md=[]
                        while k<len(L) and not L[k].startswith('#'): md.append(L[k]); k+=1
                        print('--- metadata ---'); print('\n'.join(md).strip())
