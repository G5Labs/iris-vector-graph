import sys, json, time; sys.path.insert(0,'/tmp/review-50-52/probe'); import rt
c=rt.connect(); e=rt.eng(c)
T0=time.strftime("%H%M%S"); P=f"rv52_{T0}_"; G=f"rv52h{T0}"; T=1_700_000_100
out={}
def obs(k,f):
    try: out[k]=f()
    except Exception as x: out[k]=f"EXC {type(x).__name__}: {str(x)[:160]}"
obs("nested_1", lambda: e.intern_label_set({"rv52": {"b": 1}}))
obs("nested_2", lambda: e.intern_label_set({"rv52": {"b": 1}}))
obs("nested_resolve", lambda: e.resolve_label_set(out["nested_1"]) if not str(out["nested_1"]).startswith("EXC") else None)
obs("list_1", lambda: e.intern_label_set({"rv52": [1, 2]}))
obs("list_2", lambda: e.intern_label_set({"rv52": [1, 2]}))
e.create_edge_temporal(P+"s","P",P+"t",timestamp=T+5,graph=G)
e.create_edge_temporal(P+"s","Q",P+"u",timestamp=T+6,graph=G)
obs("distinct_src_pred_empty", lambda: e.get_distinct_count(P+"s","",T,T+299,graph=G))
obs("distinct_src_empty_pred_P", lambda: e.get_distinct_count("","P",T,T+299,graph=G))
obs("agg_src_empty", lambda: e.get_temporal_aggregate("","P","count",T,T+299,graph=G))
obs("agg_pred_empty", lambda: e.get_temporal_aggregate(P+"s","","count",T,T+299,graph=G))
obs("groups_pred_empty", lambda: e.get_bucket_groups("",T,T+299,source_prefix=P,graph=G))
print(json.dumps(out, indent=1, default=str)); json.dump(out, open("p51b-out.json","w"), indent=1, default=str)
