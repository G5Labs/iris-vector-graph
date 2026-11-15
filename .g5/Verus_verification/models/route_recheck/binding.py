#!/usr/bin/env python3
"""Real NativeRoute from pin, actual timed-trial producer followed through held calls and next_path.
Clock timings are synthetic allowed inputs; no SQL/native answer equality or performance claim.
"""
from __future__ import annotations
import itertools
import logging
import json
import subprocess
import sys
from pathlib import Path
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"tools"))
import binding_common as bc
PIN_DIR=bc.import_pin()
from iris_vector_graph.cypher.native_route import NativeRoute

def held(choice,recheck,cls=NativeRoute):
    r=cls(small_ms=50,recheck=recheck,drift=None)
    for _ in range(40):
        p=r.next_path(); r.record(p,1.0 if p=="native" else (0.5 if choice=="sql" else 2.0))
        if r.choice is not None: break
    assert r.choice==choice
    return r

def compare(cls=NativeRoute,mutate_observation=False):
    mism=[]; n=0
    for choice,recheck,failed,wrong in itertools.product(("native","sql"),(None,0,1,2,5,20),(False,True),(False,True)):
        r=held(choice,recheck,cls)
        if failed: r.sql_failed(); choice="native"
        for i in range(25):
            if r._trial: break # the selected contract stops at trial reset, medians/drift not proved
            before=r._since; p=("sql" if choice=="native" else "native") if wrong else choice
            r.record(p,1.0)
            since=before if wrong or failed else before+1
            trial=bool(recheck and since>=recheck and not(wrong or failed))
            want_next="native" if trial else choice
            n+=1
            got=(r._since,r._trial,r.next_path())
            if mutate_observation and n==1: got=(r._since,not r._trial,r.next_path())
            if got!=(since,trial,want_next):
                mism.append({"choice":choice,"recheck":recheck,"failed":failed,"wrong_path":wrong,"i":i,
                             "got":[r._since,r._trial,r.next_path()],"want":[since,trial,want_next]})
                break
    return n,mism

class NeverRechecks(NativeRoute):
    def _held_run(self,path,ms):
        old=self.recheck; self.recheck=None
        try: super()._held_run(path,ms)
        finally: self.recheck=old

def main():
    n,mism=compare(); _,bad=compare(NeverRechecks)
    # Trial routing neighbors from raw counters, independent of _decide's answer.
    for native_ms,sql_runs,last in itertools.product(range(4),range(3),(None,"native","sql")):
        r=NativeRoute(50); r._ms["native"]=[1.0]*native_ms; r._runs["sql"]=sql_runs; r._last=last
        want="native" if native_ms<2 else "sql" if sql_runs==0 else "native" if last=="sql" else "sql"
        n+=1
        if r.next_path()!=want: mism.append({"trial":[native_ms,sql_runs,last],"want":want,"got":r.next_path()})
    pin=bc.pin_identity(PIN_DIR); p="iris_vector_graph/cypher/native_route.py"
    want=subprocess.check_output(["git","-C",str(bc.REPO),"rev-parse",f"{bc.PIN}:{p}"],text=True).strip()
    have=subprocess.check_output(["git","hash-object",str(PIN_DIR/p)],text=True).strip()
    pin["files_equal_pin_blobs"][p]=want==have; pin["all_equal"] &= want==have
    _,changed=compare(mutate_observation=True)
    detection={"permanent_route_mutant":bool(bad),"changed_trial_flag":bool(changed)}
    verdict="AGREES" if not mism and all(detection.values()) and pin["all_equal"] else "DISAGREES"
    out=bc.write_receipt("route_recheck",Path(__file__),{"verdict":verdict,"comparisons":n,"mismatches":mism[:20],
        "mismatch_count":len(mism),"detection":detection,"pin":pin,
        "real":"NativeRoute initial trials, record/_held_run, _start_trial, next_path, sql_failed",
        "scope":"positive held timing inputs; drift disabled; no live SQL, native query or answer-equivalence claim"})
    d=json.loads(out.read_text()); d["inputs"][p]=bc.sha(bc.REPO/p); out.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    print(f"route_recheck: {verdict}, {n} comparisons, {len(mism)} mismatches; {out}")
    return 0 if verdict=="AGREES" else 1
if __name__=="__main__": raise SystemExit(main())
