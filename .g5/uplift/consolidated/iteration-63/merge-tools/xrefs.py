import csv,sys,re
d=sys.argv[1]
rd=lambda f:list(csv.DictReader(open(f"{d}/{f}",encoding="utf-8"),delimiter="\t",quoting=csv.QUOTE_NONE))
O=rd("obligations.tsv");E=rd("excluded.tsv");B={r["block"]:r for r in rd("blocks.tsv")}
byb={}
for o in O: byb.setdefault(o["block"],[]).append(o)
new=[e for e in E if e["iteration"]=="63" and e["kind"]=="restatement"]
pairs=set()
for e in E:
    if e["kind"]!="restatement": continue
    ob=e["owner"].split("#")[0]
    if ob!=e["block"]: pairs.add((e["block"],ob))
print("MUTUAL block pairs (X excludes to Y and Y excludes to X):")
for a,b in sorted(pairs):
    if (b,a) in pairs and a<b: print("  ",a,"<->",b)
pages=lambda b:B[b]["page"].split("/")[-1]
print("\nBLOCK-OWNED new restatements whose owner is on a different page:")
for e in new:
    own=e["owner"]
    if "#" in own: continue
    if own in B and pages(own)!=pages(e["block"]):
        print(f"\n== {e['id']} [{e['locator'][:160]}] -> {own}")
        for o in byb.get(own,[]): print(f"     {o['id']} {o['grade']}: {o['statement'][:150]}")
