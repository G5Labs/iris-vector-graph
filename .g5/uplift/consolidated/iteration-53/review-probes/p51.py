import sys, json, time; sys.path.insert(0,'/tmp/review-50-52/probe'); import rt
c=rt.connect(); e=rt.eng(c)
T0=time.strftime("%H%M%S"); P=f"rv52_{T0}_"; G=f"rv52g{T0}"
T=1_700_000_100  # bucket-aligned? 1700000100 % 300 == 0
assert T % 300 == 0
out={"prefix":P,"graph":G,"cases":{}}
def obs(k,f):
    try: out["cases"][k]=f()
    except Exception as x: out["cases"][k]=f"EXC {type(x).__name__}: {str(x)[:200]}"
n=lambda s: P+s
# bug-tmp-103: one target, three targets, 40 targets
e.create_edge_temporal(n("s1"),"P",n("t0"),timestamp=T+5,graph=G)
obs("distinct_1", lambda: e.get_distinct_count(n("s1"),"P",T,T+299,graph=G))
for i in range(3): e.create_edge_temporal(n("s3"),"P",n(f"t{i}"),timestamp=T+10+i,graph=G)
obs("distinct_3", lambda: e.get_distinct_count(n("s3"),"P",T,T+299,graph=G))
for i in range(40): e.create_edge_temporal(n("s40"),"P",n(f"u{i}"),timestamp=T+20+i,graph=G)
obs("distinct_40", lambda: e.get_distinct_count(n("s40"),"P",T,T+299,graph=G))
obs("distinct_empty", lambda: e.get_distinct_count(n("nobody"),"P",T,T+299,graph=G))
# same target repeated 5 times -> distinct 1
for i in range(5): e.create_edge_temporal(n("srep"),"P",n("same"),timestamp=T+30+i,graph=G)
obs("distinct_repeat5", lambda: e.get_distinct_count(n("srep"),"P",T,T+299,graph=G))
# cut window: target outside window in the same bucket
obs("distinct_cut_outside", lambda: e.get_distinct_count(n("s1"),"P",T+100,T+200,graph=G))
obs("count_cut_outside", lambda: e.get_temporal_aggregate(n("s1"),"P","count",T+100,T+200,graph=G))
# E5: ms class writes into same ^KG with ms ts; seconds reader at same wall clock
iris=e._iris_obj()
G2=f"rv52m{T0}"
obs("ms_insert", lambda: str(iris.classMethodValue("Graph.KG.TemporalIndexMS","InsertEdge",G2,n("ms"),"P",n("x"),(T+50)*1000,3.0,"",0,0,"")))
obs("sec_count_whole_bucket_over_ms_edge", lambda: e.get_temporal_aggregate(n("ms"),"P","count",T,T+299,graph=G2))
obs("sec_count_cut_window", lambda: e.get_temporal_aggregate(n("ms"),"P","count",T,T+298,graph=G2))
obs("sec_edges_in_window", lambda: e.get_edges_in_window(n("ms"),"P",T,T+299,graph=G2))
obs("sec_velocity", lambda: e.get_edge_velocity(n("ms"),window_seconds=300,now_ts=T+100,graph=G2))
obs("ms_aggregate_in_ms", lambda: str(iris.classMethodValue("Graph.KG.TemporalIndexMS","GetAggregate",G2,n("ms"),"P","count",T*1000,(T+300)*1000-1)))
obs("sec_groups", lambda: e.get_bucket_groups("P",T,T+299,source_prefix=P,graph=G2))
json.dump(out, open("/tmp/review-50-52/probe/p51-out.json","w"), indent=1, default=str)
for k,v in out["cases"].items(): print(k, json.dumps(v, default=str)[:220])
