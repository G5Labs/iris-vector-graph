"""Shared fixture helpers for iteration 65 (namespace I65*, container ivg-cov-20261118-a-iris only)."""
import json, subprocess, sys
NAME = "ivg-cov-20261118-a-iris"
OK_TAIL = 'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!'

def iris(script, ns="%SYS", timeout=300):
    return subprocess.run(["docker", "exec", "-i", NAME, "iris", "session", "IRIS", "-U", ns],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=timeout).stdout

def recreate(ns):
    assert ns.startswith("I65")
    out = iris(f'Set ns="{ns}", dir="/usr/irissys/mgr/{ns.lower()}/"\n'
               'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
               'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
               'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n'
               'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
               'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
               'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } '
               + OK_TAIL)
    assert "RESULT OK" in out, out

KEYED = ["out", "in", "gen", "degc", "degw", "label", "prop", "deg2p", "deg2p_exact", "tout", "tin", "bucket", "tagg",
         "edgeprop", "tlast"]
WHOLE = ['^NKG', '^KG("labelset")', '^KG("deg2p_exact_merged")', '^ArnoKG', '^IVG.Ledger("stmt")', '^IVG.Ledger("tuple")',
         '^IVG.Ledger("rec")', '^BM25Idx', '^IVF', '^PLAID', '^VecIdx', '^IVG.GraphMode', '^IVG.TemporalStructural',
         '^IVG.AlgoCache', '^IVG.AdjNoLock', '^EmbedQueue', '^IVG.FHIRGraph', '^IVG.BuiltFrom']

def globals_counts(ns, keys):
    """ObjectScript $Query counts of every observed global subtree (an observer independent of the Eraser)."""
    lines = ['Set o={}']
    # inline counter
    def cnt(ref, label):
        return (f'Set r=$Name({ref}),n=0,q=r If $Data(@r)#2 {{ Set n=1 }} '
                f'For {{ Set q=$Query(@q) Quit:q=""  Quit:$Name(@q,$QLength(r))\'=r  Set n=n+1 }} Do o.%Set("{label}",n)')
    for k in keys:
        ks = "0" if k == 0 else '"' + k + '"'
        for s in KEYED:
            lines.append(cnt(f'^KG("{s}",{ks})', f'{s}@{k}'))
        for g in ("^IVG.GraphMode", "^IVG.TemporalStructural", "^IVG.AlgoCache", "^IVG.AdjNoLock"):
            lines.append(cnt(f'{g}({ks})', f'{g[1:]}@{k}'))
    for w in WHOLE:
        lines.append(cnt(w, w.replace('"', "'")))
    lines.append('Do o.%Set("version",$Get(^KG("__version"))) Do o.%Set("nkg_invalidated",$Get(^NKG("$meta","invalidated"))) '
                 'Do o.%Set("ledger_head",$Get(^IVG.Ledger("head")))')
    # statements by graph name
    lines.append('Set sg={},i="" For { Set i=$Order(^IVG.Ledger("stmt",i)) Quit:i=""  Set row=$Get(^IVG.Ledger("stmt",i)) '
                 'Set gg=$ListGet(row,4) Do sg.%Set("g:"_gg,sg.%Get("g:"_gg)+1) } Do o.%Set("stmt_by_graph",sg)')
    lines.append('Write "JSON:",o.%ToJSON(),!')
    out = iris(" ".join(l if l.endswith(" ") else l + "\n" for l in lines), ns)
    for line in out.splitlines():
        if "JSON:" in line:
            return json.loads(line.split("JSON:", 1)[1])
    raise RuntimeError(out[-2000:])
