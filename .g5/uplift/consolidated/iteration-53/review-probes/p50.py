import sys, json, time; sys.path.insert(0,'/tmp/review-50-52/probe'); import rt
c=rt.connect(); e=rt.eng(c)
T=time.strftime("%H%M%S"); P=f"rv52_{T}_"; L=f"RV52{T}"
out={"prefix":P,"cases":{}}
def case(k,q,params=None): out["cases"][k]={"q":q,"params":params,"r":rt.run(e,q,params)}
case("setup", f"CREATE (n:{L} {{id:'{P}c', l:[1,2,3], s1:'1', i1:1}})")
# bug-cyp-126
case("idx_null_row", "WITH [1,2,3] AS l UNWIND [null] AS i RETURN l[i]")
case("idx_null_prop", f"MATCH (n {{id:'{P}c'}}) RETURN n.l[null]")
case("idx_null_prop_missing", f"MATCH (n {{id:'{P}c'}}) RETURN n.l[n.nope]")
case("idx_null_lit", "RETURN [1,2,3][null]")
case("idx_null_param", "WITH [1,2,3] AS l RETURN l[$i]", {"i": None})
# bug-cyp-127
case("case_prop_str_when_num", f"MATCH (n {{id:'{P}c'}}) RETURN CASE n.s1 WHEN 1 THEN 'num' WHEN '1' THEN 'str' ELSE 'other' END")
case("case_prop_num_when_str", f"MATCH (n {{id:'{P}c'}}) RETURN CASE n.i1 WHEN '1' THEN 'str' ELSE 'other' END")
case("case_generic", f"MATCH (n {{id:'{P}c'}}) RETURN CASE WHEN n.s1 = 1 THEN 'num' ELSE 'other' END")
case("case_param_test", "RETURN CASE $t WHEN 1 THEN 'num' ELSE 'other' END", {"t": "1"})
case("case_lit_lit", "RETURN CASE '1' WHEN 1 THEN 'num' ELSE 'other' END")
case("eq_prop", f"MATCH (n {{id:'{P}c'}}) RETURN n.s1 = 1")
# item 5 relationship param
case("rel_param", f"CREATE (a:{L}A {{id:'{P}a'}})-[r:RP{T} {{k: $k, lit: 1}}]->(b:{L}A {{id:'{P}b'}})", {"k": 5})
case("rel_param_read", f"MATCH (a {{id:'{P}a'}})-[r:RP{T}]->(b) RETURN r.k, r.lit, keys(r)")
json.dump(out, open(f"/tmp/review-50-52/probe/p50-out.json","w"), indent=1, default=str)
for k,v in out["cases"].items(): print(k, json.dumps(v["r"], default=str)[:200])
