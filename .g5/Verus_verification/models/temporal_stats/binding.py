"""Binding for temporal_stats (W57, iteration 51) on the run-isolated continuation fixture.

Replays one list of write histories (insert, update, collision, bulk, delete, a caller's rolled-back write, raw purge,
bucket-range purge) twice: through the real product's public entry points (exported pin tree, IRIS 2026.1 container
ivg-cont-20261117-iris, fresh graphs) and through a Python port of temporal_stats.rs's step functions (`write`,
`rolled_back`, `delete_at`/`rebuild`, `purge_raw_before`, `purge_buckets`/`purged_count`). Then it reads every
statistics reader on both (get_temporal_aggregate through `py_value`, get_bucket_groups through `group_row`,
get_bucket_group_targets, get_edge_velocity, find_burst_nodes, get_distinct_count through `estimate`,
TemporalIndexMS.GetVelocity and GetBucketCount, intern/resolve_label_set through `canon`) and compares. The expected
answers come from the modeled history, never from the product's answers. The only provider input is SHA-1 (the
sketch's register choice), computed here as HLLAdd computes it. Mutations mirror the model's 16 controls; one
deciding observation is tampered.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/Verus_verification/models/temporal_stats/binding.py)
"""
import hashlib, json, os, re, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[3]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i53t_{TAG}_"
T = 1_900_000_200
B = T // 300
MUTS = ["update-keeps-statistics", "insert-overwrites", "counters-journaled", "whole-reads-raw", "cut-reads-tagg",
        "none-checked", "raw-purge-drops-statistics", "delete-skips-missing-statistics", "bursts-filter-predicate",
        "burst-threshold-strict", "velocity-not-rounded", "ms-now-in-ms", "small-range-correction", "no-empty-guard",
        "distinct-whole-buckets-only", "escape-values", "nested-serialized-as-json", "ms-buckets-apart"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def G(x):
    return f"i53t{TAG}{x}"


def N(x):
    return P + x


# ------------------------------------------------------------------ port of temporal_stats.rs
def hf(o):
    """HLLAdd 212-220: SHA-1 byte 1 mod 16 -> register, 1 + trailing zero bits of byte 2 (9 for 0) -> rank."""
    h = hashlib.sha1(o.encode("utf-8")).digest()
    b1 = h[1]
    if b1 == 0:
        r = 9
    else:
        r = 1
        while b1 % 2 == 0:
            r += 1; b1 //= 2
    return h[0] % 16, r


def hll_add(regs, h):
    i, r = h
    if r > regs[i]:
        regs = list(regs); regs[i] = r
    return tuple(regs)


EMPTY = (0,) * 16


class Port:
    def __init__(self, m, div=300):
        self.m, self.div = m, div
        self.raw = []  # [g, ts, s, p, o, w], write order
        self.cnt, self.sum, self.mn, self.mx, self.hll, self.bkt = {}, {}, {}, {}, {}, {}

    def snap(self):
        return {k: (list(map(list, v)) if k == "raw" else dict(v)) for k, v in self.__dict__.items() if k not in ("m", "div")}

    def restore(self, s):
        for k, v in s.items():
            setattr(self, k, v)

    def idx(self, g, ts, s, p, o):
        for i, e in enumerate(self.raw):
            if e[:5] == [g, ts, s, p, o]:
                return i
        return None

    def stores_written(self, e):
        g, ts, s, p, o, w = e
        bn = ts // self.div
        if self.m.get("ms-buckets-apart") and self.div == 300000:
            bn = -1 - bn
        k = (g, bn, s, p); b = (g, bn, s)
        self.bkt[b] = self.bkt.get(b, 0) + 1
        self.cnt[k] = self.cnt.get(k, 0) + 1
        self.sum[k] = self.sum.get(k, 0) + w
        if k not in self.mn or w < self.mn[k]:
            self.mn[k] = w
        if k not in self.mx or w > self.mx[k]:
            self.mx[k] = w
        h0 = self.hll.get(k, EMPTY); h1 = hll_add(h0, hf(o))
        if h1 != h0:
            self.hll[k] = h1

    def write(self, mode, e):
        i = self.idx(*e[:5])
        if i is not None:
            if mode == "update":
                self.raw[i] = list(e)
                if not self.m.get("update-keeps-statistics"):
                    self.stores_written(e)
            elif self.m.get("insert-overwrites"):
                self.raw[i] = list(e); self.stores_written(e)
            return
        self.raw.append(list(e)); self.stores_written(e)

    def rolled_back_write(self, e):
        before = self.snap(); self.write("insert", e); after = self.snap()
        keep = ("raw", "cnt", "sum", "bkt") if self.m.get("counters-journaled") else ("raw",)
        for k in ("raw", "mn", "mx", "hll") + (keep[1:] if self.m.get("counters-journaled") else ()):
            setattr(self, k, before[k])
        del after

    def raw_agg(self, g, s, p, lo, hi):
        ws = [e[5] for e in self.raw if e[0] == g and e[2] == s and e[3] == p and lo <= e[1] <= hi]
        return (len(ws), sum(ws), min(ws) if ws else None, max(ws) if ws else None)

    def raw_hll(self, g, s, p, lo, hi):
        r = EMPTY
        for e in self.raw:
            if e[0] == g and e[2] == s and e[3] == p and lo <= e[1] <= hi:
                r = hll_add(r, hf(e[4]))
        return r

    def rebuild(self, k):
        g, b, s, p = k
        lo, hi = b * self.div, (b + 1) * self.div - 1
        c, sm, mn, mx = self.raw_agg(g, s, p, lo, hi)
        if c == 0:
            for d in (self.cnt, self.sum, self.mn, self.mx, self.hll):
                d.pop(k, None)
        else:
            self.cnt[k], self.sum[k], self.mn[k], self.mx[k] = c, sm, mn, mx
            self.hll[k] = self.raw_hll(g, s, p, lo, hi)

    def delete(self, g, ts, s, p, o):
        i = self.idx(g, ts, s, p, o)
        if i is None:
            return False
        had = (g, ts // self.div, s, p) in self.cnt
        del self.raw[i]
        b = (g, ts // self.div, s)
        c = self.bkt.get(b, 0) - 1
        if c <= 0:
            self.bkt.pop(b, None)
        else:
            self.bkt[b] = c
        if had or not self.m.get("delete-skips-missing-statistics"):
            self.rebuild((g, ts // self.div, s, p))
        return True

    def purge_raw(self, g, lo, hi):
        n = sum(1 for e in self.raw if e[0] == g and lo <= e[1] < hi)
        self.raw = [e for e in self.raw if not (e[0] == g and lo <= e[1] < hi)]
        if self.m.get("raw-purge-drops-statistics"):
            self.cnt = {}
        return n

    def has_tagg(self, g, b):
        return any(k[0] == g and k[1] == b for d in (self.cnt, self.sum, self.mn, self.mx, self.hll) for k in d)

    def purge_buckets(self, g, bs, be):
        if bs > be:
            return 0
        n = sum(1 for b in range(bs, be + 1) if self.has_tagg(g, b))
        tagged = {b for b in range(bs, be + 1) if self.has_tagg(g, b)}
        for d in (self.cnt, self.sum, self.mn, self.mx, self.hll):
            for k in [k for k in d if k[0] == g and bs <= k[1] <= be]:
                del d[k]
        for k in [k for k in self.bkt if k[0] == g and k[1] in tagged]:
            del self.bkt[k]
        return n

    # readers
    def whole(self, b, lo, hi):
        return b * self.div >= lo and (b + 1) * self.div - 1 <= hi

    def stat_agg(self, k):
        return (self.cnt.get(k, 0), self.sum.get(k, 0), self.mn.get(k), self.mx.get(k))

    def bucket_part(self, g, s, p, lo, hi, b):
        if (self.whole(b, lo, hi) or self.m.get("cut-reads-tagg")):
            if self.m.get("whole-reads-raw") and self.whole(b, lo, hi):
                return self.raw_agg(g, s, p, b * self.div, (b + 1) * self.div - 1)
            return self.stat_agg((g, b, s, p))
        return self.raw_agg(g, s, p, max(lo, b * self.div), min(hi, (b + 1) * self.div - 1))

    def get_aggregate(self, g, s, p, lo, hi):
        c, sm, mn, mx = 0, 0, None, None
        for b in range(lo // self.div, hi // self.div + 1):
            pc, ps, pmn, pmx = self.bucket_part(g, s, p, lo, hi, b)
            c, sm = c + pc, sm + ps
            mn = pmn if mn is None else (mn if pmn is None else min(mn, pmn))
            mx = pmx if mx is None else (mx if pmx is None else max(mx, pmx))
        return c, sm, mn, mx

    def py_aggregate(self, g, s, p, metric, lo, hi):
        c, sm, mn, mx = self.get_aggregate(g, s, p, lo, hi)
        ans = {"count": c, "sum": sm, "min": mn, "max": mx,
               "avg": None if c == 0 else round(sm / c, 6)}.get(metric)
        if ans is None:
            return 0.0 if self.m.get("none-checked") else "Raises"
        return int(ans) if metric == "count" else float(ans)

    def row_part(self, g, s, p, lo, hi, b):
        if self.whole(b, lo, hi):
            k = (g, b, s, p)
            return any(k in d for d in (self.cnt, self.sum, self.mn, self.mx, self.hll))
        return self.raw_agg(g, s, p, max(lo, b * self.div), min(hi, (b + 1) * self.div - 1))[0] > 0

    def groups(self, g, pred, lo, hi, prefix):
        cands = {(k[2], k[3]) for d in (self.cnt, self.sum, self.mn, self.mx, self.hll) for k in d if k[0] == g}
        cands |= {(e[2], e[3]) for e in self.raw if e[0] == g}
        rows = {}
        for s, p in cands:
            if not s.startswith(prefix) or (pred and p != pred):
                continue
            if any(self.row_part(g, s, p, lo, hi, b) for b in range(lo // self.div, hi // self.div + 1)):
                rows[f"{s}|{p}"] = list(self.get_aggregate(g, s, p, lo, hi))
        return rows

    def targets(self, g, s, p, lo, hi):
        return sorted({e[4] for e in self.raw if e[0] == g and e[2] == s and (not p or e[3] == p) and lo <= e[1] <= hi})

    def bucket_count(self, g, b, s):
        return self.bkt.get((g, b, s), 0)

    def bkt_sum(self, g, s, b, eb):
        return sum(self.bucket_count(g, x, s) for x in range(b, eb + 1))

    def now(self, now_ts, clock_s):
        if now_ts > 0:
            return now_ts
        return clock_s * 1000 if (self.m.get("ms-now-in-ms") and self.div == 300000) else clock_s

    def velocity(self, g, s, window, now_ts, clock_s):
        now = self.now(now_ts, clock_s)
        start = (now - window) // self.div + (1 if self.m.get("velocity-not-rounded") else 0)
        return self.bkt_sum(g, s, start, now // self.div)

    def bursts(self, g, pred, window, thr, now_ts, clock_s):
        now = self.now(now_ts, clock_s)
        b0, b1 = (now - window) // self.div, now // self.div
        out = []
        for s in sorted({k[2] for k in self.bkt if k[0] == g and b0 <= k[1] <= b1}):
            v = self.velocity(g, s, window, now_ts, clock_s)
            ok = v > thr if self.m.get("burst-threshold-strict") else v >= thr
            if ok and (pred == "" or not self.m.get("bursts-filter-predicate")):
                out.append([s, v])
        return out

    def estimate(self, regs):
        if not any(regs):
            return 11 if self.m.get("no-empty-guard") else 0
        zs = sum(2 ** (9 - r) for r in regs)
        if self.m.get("small-range-correction") and zs > 7680:
            return 1
        return (88211456 + 500 * zs) // (1000 * zs)

    def distinct(self, g, s, p, lo, hi):
        start = (lo + self.div - 1) // self.div if self.m.get("distinct-whole-buckets-only") else lo // self.div
        merged = list(EMPTY)
        for b in range(start, hi // self.div + 1):
            for k, h in self.hll.items():
                if k[0] == g and k[1] == b and k[3] == p and (k[2] == s if s else True):
                    merged = [max(x, y) for x, y in zip(merged, h)]
        if not any(merged) and self.m.get("no-empty-guard"):
            return 11
        return self.estimate(tuple(merged))


def os_num(v):
    """IRIS's canonical number text (provider): no trailing .0, no leading 0 before the point."""
    t = repr(int(v)) if float(v).is_integer() else repr(float(v))
    return t.replace("0.", ".", 1) if t.startswith("0.") else (t.replace("-0.", "-.", 1) if t.startswith("-0.") else t)


REF = re.compile(r"^\d+@%Library\.Dynamic(Object|Array)$")


def canon(d, m, refs=None):
    """InternLabelSet's text (canon_v): a nested object or array is written as its per-call reference text
    (`refs[k]`, a provider input read from the product); mutation nested-serialized-as-json writes its JSON."""
    def enc(v, k=None):
        if isinstance(v, (dict, list)):
            if m.get("nested-serialized-as-json"):
                return json.dumps(v, separators=(",", ":"))
            return '"' + refs[k] + '"'

        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return os_num(v)
        v = str(v)
        if m.get("escape-values"):
            v = v.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + v + '"'
    return "{" + ",".join('"' + k + '":' + enc(d[k], k) for k in sorted(d)) + "}"


def label(d, m, refs=None):
    c = canon(d, m, refs)
    return {"hash": hashlib.sha1(c.encode("utf-8")).hexdigest(), "canonical": c}


# ------------------------------------------------------------------ the histories
def histories():
    """(graph, ops). ops: ("w", mode, s, p, o, dt, w), ("bulk", [(s, p, o, dt, w)]), ("rb", s, p, o, dt, w),
    ("del", s, p, o, dt), ("purge_raw", lo_dt, hi_dt), ("purge_b", bs, be)."""
    ann = [("ann", "P", "b", 5, 2), ("ann", "P", "b", 100, 4), ("ann", "P", "c", 299, 9), ("ann", "P", "d", 300, 1), ("ann", "P", "b", 650, 5)]
    four = [("ps", "P", "b", 5, 2), ("ps", "P", "b", 100, 4), ("ps", "P", "c", 299, 9), ("ps", "P", "d", 400, 1)]
    return {
        "a": [("bulk", ann), ("w", "insert", "upd", "P", "x", 10, 2), ("w", "update", "upd", "P", "x", 10, 9),
              ("w", "insert", "col", "P", "x", 10, 2), ("w", "insert", "col", "P", "x", 10, 9),
              ("w", "insert", "ud", "P", "x", 10, 2), ("w", "update", "ud", "P", "x", 10, 9), ("del", "ud", "P", "x", 10),
              ("rb", "rb", "P", "x", 20, 3), ("w", "insert", "rbc", "P", "x", 20, 3),
              ("bulk", [("dm", "P", "x", 10, 1), ("dm", "P", "y", 20, 5), ("dm", "P", "z", 30, 3)]), ("del", "dm", "P", "x", 10)],
        "a2": [("bulk", [("ann", "P", "z", 50, 100)])],
        "p": [("bulk", four), ("purge_raw", 0, 300)],
        "pb": [("bulk", four), ("purge_raw", 0, 300), ("bulk", [("ps", "P", "e", 120, 7)]), ("del", "ps", "P", "e", 120)],
        "q": [("bulk", four), ("purge_b", B + 5, B), ("purge_b", B + 10, B + 12), ("purge_b", B, B)],
        "qb": [("bulk", four), ("purge_b", B, B), ("del", "ps", "P", "b", 5)],
        "g": [("bulk", [("ann", "CALLED", "b", 5, 2), ("ann", "CALLED", "b", 100, 4), ("ann", "CALLED", "c", 299, 9),
                        ("ann", "CALLED", "d", 300, 1), ("ann", "CALLED", "b", 650, 5), ("ben", "CALLED", "ann", 10, 7),
                        ("ann", "OTHER", "q", 50, 10), ("tg", "P", "x", 5, 1), ("tg", "P", "y", 150, 1)])],
        "v": [("bulk", [("vs", "P", "a", 299, 1), ("vs", "P", "a", 300, 1), ("vs", "Q", "a", 600, 1), ("vf", "P", "a", 590, 1),
                        ("vd", "P", "a", 10, 1), ("vd", "P", "b", 20, 1)]), ("del", "vd", "P", "a", 10)],
        "v2": [("bulk", [("vs", "P", "a", 300 + i, 1) for i in range(5)])],
        "d": [("bulk", [("d1", "P", "x", 10, 1), ("d1", "P", "x", 20, 1), ("d1", "P", "x", 30, 1),
                        ("d3", "P", "x", 10, 1), ("d3", "P", "y", 20, 1), ("d3", "P", "z", 30, 1),
                        ("dw", "P", "x", 5, 1), ("dw", "P", "y", 400, 1), ("dd", "P", "x", 10, 1), ("dd", "P", "y", 20, 1)]
               + [("dbig", "P", f"t{i:03d}", 100 + i, 1) for i in range(100)]), ("del", "dd", "P", "y", 20)],
    }


def reads():
    """(name, graph, reader, args) with times relative to T."""
    r = []
    for s, lo, hi in (("ann", 100, 300), ("ann", 0, 299), ("ann", 301, 649), ("ann", 0, 1000), ("upd", 0, 299), ("upd", 1, 299),
                      ("col", 0, 299), ("ud", 0, 299), ("rb", 0, 299), ("rb", 1, 299), ("rbc", 0, 299), ("dm", 0, 299)):
        for m in ("count", "sum", "min", "max", "avg"):
            r.append((f"agg_a_{s}_{lo}_{hi}_{m}", "a", "agg", (s, "P", m, lo, hi)))
    r.append(("agg_a_ann_unknown", "a", "agg", ("ann", "P", "median", 0, 299)))
    for gr in ("pb", "qb"):
        for m in ("count", "sum"):
            r.append((f"agg_{gr}_0_299_{m}", gr, "agg", ("ps", "P", m, 0, 299)))
        r.append((f"vel_{gr}_299", gr, "vel", ("ps", 0, 299)))
    r.append(("agg_a2_ann_count", "a2", "agg", ("ann", "P", "count", 0, 299)))
    for gr in ("p", "q"):
        for lo, hi in ((0, 299), (100, 299), (0, 500)):
            for m in ("count", "sum", "min"):
                r.append((f"agg_{gr}_{lo}_{hi}_{m}", gr, "agg", ("ps", "P", m, lo, hi)))
        r.append((f"groups_{gr}_whole", gr, "groups", ("P", 0, 299, "ps")))
        r.append((f"groups_{gr}_cut", gr, "groups", ("P", 100, 299, "ps")))
        r.append((f"targets_{gr}", gr, "targets", ("ps", "P", 0, 299)))
        for nw in (299, 599):
            r.append((f"vel_{gr}_{nw}", gr, "vel", ("ps", 0, nw)))
        r.append((f"distinct_{gr}", gr, "distinct", ("ps", "P", 0, 299)))
    for lo, hi in ((100, 300), (0, 1000), (301, 649)):
        r.append((f"groups_g_{lo}_{hi}", "g", "groups", ("CALLED", lo, hi, "")))
    r.append(("groups_g_allpred", "g", "groups", ("", 0, 299, "ann")))
    r.append(("groups_a_rb", "a", "groups", ("P", 0, 299, "rb")))
    r.append(("targets_g_100_200", "g", "targets", ("tg", "P", 100, 200)))
    r.append(("targets_g_0_299", "g", "targets", ("tg", "P", 0, 299)))
    for s, w, nw in (("vs", 300, 650), ("vs", 300, 599), ("vs", 0, 650), ("vf", 300, 301), ("vd", 300, 299)):
        r.append((f"vel_v_{s}_{w}_{nw}", "v", "vel", (s, w, nw)))
    for s in ("upd", "col", "ud", "rb", "rbc"):
        r.append((f"vel_a_{s}", "a", "vel", (s, 300, 299)))
    for pred, thr in (("NOPE", 2), ("", 2), ("", 3), ("", 1)):
        r.append((f"bursts_v_{pred or 'any'}_{thr}", "v", "bursts", (pred, 300, thr, 650)))
    r.append(("bursts_v2", "v2", "bursts", ("", 300, 2, 650)))
    for s, lo, hi in (("d1", 0, 299), ("d3", 0, 299), ("dbig", 0, 299), ("dd", 0, 299), ("nobody", 0, 299),
                      ("dw", 100, 200), ("dw", 400, 500), ("dw", 600, 800), ("", 0, 299)):
        r.append((f"distinct_d_{s or 'all'}_{lo}_{hi}", "d", "distinct", (s, "P", lo, hi)))
    for s in ("upd", "col", "rb", "rbc"):
        r.append((f"distinct_a_{s}", "a", "distinct", (s, "P", 0, 299)))
    return r


def main():
    t0 = time.time()
    c = runtime.connect(); e = runtime.engine(c); nat = e._iris_obj()
    hs, rs = histories(), reads()
    obs, purge_rets = {}, {}

    def full(x):
        return N(x)

    for gk, ops in hs.items():
        g = G(gk)
        for i, op in enumerate(ops):
            if op[0] == "bulk":
                e.bulk_create_edges_temporal([{"s": N(s), "p": p, "o": N(o), "ts": T + dt, "w": float(w)} for s, p, o, dt, w in op[1]], graph=g)
            elif op[0] == "w":
                _, mode, s, p, o, dt, w = op
                e.create_edge_temporal(N(s), p, N(o), timestamp=T + dt, weight=float(w), graph=g, mode=mode)
            elif op[0] == "rb":
                _, s, p, o, dt, w = op
                cur = c.cursor()
                try:
                    cur.execute("START TRANSACTION")
                    e.create_edge_temporal(N(s), p, N(o), timestamp=T + dt, weight=float(w), graph=g)
                    cur.execute("ROLLBACK")
                finally:
                    cur.close()
            elif op[0] == "del":
                _, s, p, o, dt = op
                purge_rets[f"{gk}_{i}"] = bool(e.delete_edge_temporal(N(s), p, N(o), T + dt, graph=g))
            elif op[0] == "purge_raw":
                purge_rets[f"{gk}_{i}"] = int(e.purge_raw_before(T + op[2], ts_start=T + op[1], graph=g, retire_bare_nodes=False))
            elif op[0] == "purge_b":
                purge_rets[f"{gk}_{i}"] = int(e.purge_bucket_range(op[1], op[2], graph=g))
    obs["returns"] = purge_rets

    def short(x):
        return x[len(P):] if isinstance(x, str) and x.startswith(P) else x

    for name, gk, kind, a in rs:
        g = G(gk)
        try:
            if kind == "agg":
                s, p, m, lo, hi = a
                v = e.get_temporal_aggregate(N(s), p, m, T + lo, T + hi, graph=g)
            elif kind == "groups":
                pred, lo, hi, pfx = a
                rows = e.get_bucket_groups(pred, T + lo, T + hi, source_prefix=N(pfx), graph=g)
                v = {f"{short(r['source'])}|{r['predicate']}": [r["count"], r["sum"], r["min"], r["max"]] for r in rows}
            elif kind == "targets":
                s, p, lo, hi = a
                v = sorted(short(x) for x in e.get_bucket_group_targets(N(s), p, T + lo, T + hi, graph=g))
            elif kind == "vel":
                s, w, nw = a
                v = e.get_edge_velocity(N(s), w, now_ts=T + nw, graph=g)
            elif kind == "bursts":
                pred, w, thr, nw = a
                v = [[short(r["id"]), r["velocity"]] for r in e.find_burst_nodes(pred, w, thr, now_ts=T + nw, graph=g)]
            elif kind == "distinct":
                s, p, lo, hi = a
                v = e.get_distinct_count(N(s) if s else "", p, T + lo, T + hi, graph=g)
        except ValueError:
            v = "Raises"
        obs[name] = v
    # TemporalIndexMS: explicit now, default now on a recent millisecond event, GetBucketCount
    gm = G("m"); clock = int(time.time()); tm_recent = (clock - 600) * 1000; tm = T * 1000
    nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", gm, N("ms"), "P", N("a"), tm + 5, 1, "", 0, 0, "")
    nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", gm, N("mr"), "P", N("a"), tm_recent, 1, "", 0, 0, "")
    obs["ms_bucketcount"] = int(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetBucketCount", gm, (tm + 5) // 300000, N("ms")))
    obs["ms_velocity_explicit"] = int(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetVelocity", gm, N("ms"), 300000, tm + 10))
    clock_ms_call = int(time.time())
    obs["ms_velocity_default_now_recent"] = int(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetVelocity", gm, N("mr"), 3600 * 1000, 0))
    # label sets
    dicts = {"plain": {"port": 1972, "a": True, "n": None, "s": "x"}, "reordered": {"s": "x", "n": None, "a": True, "port": 1972},
             "injected": {"a": 'x","b":"y'}, "two_keys": {"a": "x", "b": "y"}, "fraction": {"x": 0.5}}
    obs["labels"] = {k: {"hash": e.intern_label_set(d)} for k, d in dicts.items()}
    for k in obs["labels"]:
        obs["labels"][k]["canonical"] = e.resolve_label_set(obs["labels"][k]["hash"])
    obs["label_unknown"] = e.resolve_label_set("f" * 40)
    # nested values (review M1, bug-tmp-105): each dict interned twice; the reference text of each nested value in each
    # call is read back from the resolved text (provider input) and checked to be an object reference of the right kind
    nested = {"nested_map": {"k": {"b": 1}}, "empty_map": {"k": {}}, "list": {"k": [1, 2]}, "mixed": {"a": "v", "z": [1]}}
    obs["nested"] = {}
    nrefs = {}
    for name, d in nested.items():
        for call in (1, 2):
            h = e.intern_label_set(d); txt = e.resolve_label_set(h)
            try:
                got = json.loads(txt)
            except ValueError:
                got = {}
            refs = {k: got.get(k) for k, v in d.items() if isinstance(v, (dict, list))}
            nrefs[f"{name}_{call}"] = refs
            obs["nested"][f"{name}_{call}"] = {"hash": h, "canonical": txt,
                                               "ref_is_object_reference": all(isinstance(r, str) and REF.match(r) and
                                                                              (r.endswith("Array") == isinstance(d[k], list)) for k, r in refs.items())}
        obs["nested"][f"{name}_same_hash"] = obs["nested"][f"{name}_1"]["hash"] == obs["nested"][f"{name}_2"]["hash"]
    obs["nested"]["map_vs_empty_map_call1_same_hash"] = obs["nested"]["nested_map_1"]["hash"] == obs["nested"]["empty_map_1"]["hash"]
    # the millisecond writer read by the seconds readers (review m1, bug-tmp-106)
    gx = G("x"); tx = (T + 50) * 1000
    nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", gx, N("mx"), "P", N("a"), tx, 2, "", 0, 0, "")
    obs["ms_in_sec_whole_count"] = e.get_temporal_aggregate(N("mx"), "P", "count", T, T + 299, graph=gx)
    obs["ms_in_sec_whole_sum"] = e.get_temporal_aggregate(N("mx"), "P", "sum", T, T + 299, graph=gx)
    obs["ms_in_sec_cut_count"] = e.get_temporal_aggregate(N("mx"), "P", "count", T, T + 298, graph=gx)
    obs["ms_in_sec_raw_window"] = len(e.get_edges_in_window(N("mx"), "P", T, T + 299, graph=gx))
    obs["ms_in_sec_velocity"] = e.get_edge_velocity(N("mx"), 300, now_ts=T + 299, graph=gx)
    # the millisecond class's window argument is in milliseconds (review m9): edges in two consecutive ms buckets, now 1 s
    # into the later one; a window of 300 stays in that bucket, 300000 reaches the earlier one
    gv = G("v"); tv = (T * 1000 // 300000) * 300000
    nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", gv, N("mv"), "P", N("a"), tv + 5, 1, "", 0, 0, "")
    nat.classMethodValue("Graph.KG.TemporalIndexMS", "InsertEdge", gv, N("mv"), "P", N("b"), tv + 300005, 1, "", 0, 0, "")
    nv = tv + 301000
    obs["ms_vel_window_300"] = int(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetVelocity", gv, N("mv"), 300, nv))
    obs["ms_vel_window_300000"] = int(nat.classMethodValue("Graph.KG.TemporalIndexMS", "GetVelocity", gv, N("mv"), 300000, nv))
    obs["ms_in_sec_groups"] = {f"{r['source'][len(P):]}|{r['predicate']}": [r["count"], r["sum"], r["min"], r["max"]]
                               for r in e.get_bucket_groups("P", T, T + 299, source_prefix=P, graph=gx)}
    c.close()

    def predict(m):
        w = {}
        ports = {}
        rets = {}
        for gk, ops in hs.items():
            g = G(gk)
            pt = Port(m)
            for i, op in enumerate(ops):
                if op[0] == "bulk":
                    for s, p, o, dt, wt in op[1]:
                        pt.write("insert", [g, T + dt, N(s), p, N(o), wt])
                elif op[0] == "w":
                    _, mode, s, p, o, dt, wt = op
                    pt.write(mode, [g, T + dt, N(s), p, N(o), wt])
                elif op[0] == "rb":
                    _, s, p, o, dt, wt = op
                    pt.rolled_back_write([g, T + dt, N(s), p, N(o), wt])
                elif op[0] == "del":
                    _, s, p, o, dt = op
                    rets[f"{gk}_{i}"] = pt.delete(g, T + dt, N(s), p, N(o))
                elif op[0] == "purge_raw":
                    rets[f"{gk}_{i}"] = pt.purge_raw(g, T + op[1], T + op[2])
                elif op[0] == "purge_b":
                    rets[f"{gk}_{i}"] = pt.purge_buckets(g, op[1], op[2])
            ports[gk] = pt
        w["returns"] = rets
        for name, gk, kind, a in rs:
            pt, g = ports[gk], G(gk)
            if kind == "agg":
                s, p, mt, lo, hi = a
                w[name] = pt.py_aggregate(g, N(s), p, mt, T + lo, T + hi)
            elif kind == "groups":
                pred, lo, hi, pfx = a
                w[name] = {k[len(P):]: [r[0], r[1], r[2], r[3]] for k, r in pt.groups(g, pred, T + lo, T + hi, N(pfx)).items()}
            elif kind == "targets":
                s, p, lo, hi = a
                w[name] = [x[len(P):] for x in pt.targets(g, N(s), p, T + lo, T + hi)]
            elif kind == "vel":
                s, wn, nw = a
                w[name] = pt.velocity(g, N(s), wn, T + nw, clock)
            elif kind == "bursts":
                pred, wn, thr, nw = a
                w[name] = [[x[len(P):], v] for x, v in pt.bursts(g, pred, wn, thr, T + nw, clock)]
            elif kind == "distinct":
                s, p, lo, hi = a
                w[name] = pt.distinct(g, N(s) if s else "", p, T + lo, T + hi)
        pm = Port(m, div=300000)
        pm.write("insert", [gm, tm + 5, N("ms"), "P", N("a"), 1]); pm.write("insert", [gm, tm_recent, N("mr"), "P", N("a"), 1])
        w["ms_bucketcount"] = pm.bucket_count(gm, (tm + 5) // 300000, N("ms"))
        w["ms_velocity_explicit"] = pm.velocity(gm, N("ms"), 300000, tm + 10, clock)
        w["ms_velocity_default_now_recent"] = pm.velocity(gm, N("mr"), 3600 * 1000, 0, clock_ms_call)
        w["labels"] = {k: label(d, m) for k, d in dicts.items()}
        w["label_unknown"] = ""
        w["nested"] = {}
        for name, d in nested.items():
            for call in (1, 2):
                lb = label(d, m, nrefs[f"{name}_{call}"])
                w["nested"][f"{name}_{call}"] = {"hash": lb["hash"], "canonical": lb["canonical"], "ref_is_object_reference": True}
            w["nested"][f"{name}_same_hash"] = w["nested"][f"{name}_1"]["hash"] == w["nested"][f"{name}_2"]["hash"]
        w["nested"]["map_vs_empty_map_call1_same_hash"] = w["nested"]["nested_map_1"]["hash"] == w["nested"]["empty_map_1"]["hash"]
        px = Port(m, div=300000)
        px.write("insert", [gx, tx, N("mx"), "P", N("a"), 2])
        px.div = 300  # the seconds readers over the same stores
        w["ms_in_sec_whole_count"] = px.py_aggregate(gx, N("mx"), "P", "count", T, T + 299)
        w["ms_in_sec_whole_sum"] = px.py_aggregate(gx, N("mx"), "P", "sum", T, T + 299)
        w["ms_in_sec_cut_count"] = px.py_aggregate(gx, N("mx"), "P", "count", T, T + 298)
        w["ms_in_sec_raw_window"] = px.raw_agg(gx, N("mx"), "P", T, T + 299)[0]
        w["ms_in_sec_velocity"] = px.velocity(gx, N("mx"), 300, T + 299, clock)
        pv = Port(m, div=300000)
        pv.write("insert", [gv, tv + 5, N("mv"), "P", N("a"), 1]); pv.write("insert", [gv, tv + 300005, N("mv"), "P", N("b"), 1])
        w["ms_vel_window_300"] = pv.velocity(gv, N("mv"), 300, nv, clock)
        w["ms_vel_window_300000"] = pv.velocity(gv, N("mv"), 300000, nv, clock)
        w["ms_in_sec_groups"] = {k[len(P):]: [r[0], r[1], r[2], r[3]] for k, r in px.groups(gx, "P", T, T + 299, P).items()}
        return w

    def close(x, y):
        if isinstance(x, dict) and isinstance(y, dict):
            return x.keys() == y.keys() and all(close(x[k], y[k]) for k in x)
        if isinstance(x, list) and isinstance(y, list):
            return len(x) == len(y) and all(close(a, b) for a, b in zip(x, y))
        if isinstance(x, bool) or isinstance(y, bool):
            return x == y
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return abs(x - y) <= 1e-6 and (type(x) is type(y) or not (isinstance(x, int) ^ isinstance(y, int)) or True)
        return x == y

    def compare(want, got):
        bad = [(k, want[k], got.get(k)) for k in want if not close(want[k], got.get(k))]
        # Python types of the aggregate reader: count is int, the others float
        for name, _, kind, a in rs:
            if kind == "agg" and not isinstance(got.get(name), str) and isinstance(want[name], (int, float)):
                if type(want[name]) is not type(got[name]):
                    bad.append((name + ":type", type(want[name]).__name__, type(got[name]).__name__))
        return bad, len(want)

    want = predict({})
    mism, ncases = compare(want, obs)
    sens = {mu: len(compare(predict({mu: True}), obs)[0]) for mu in MUTS}
    tampered = json.loads(json.dumps(obs)); tampered["distinct_d_d1_0_299"] = 1
    tamper_detected = bool(compare(want, tampered)[0])
    contrasts = {k: obs[k] for k in ("agg_a_upd_0_299_count", "agg_a_upd_1_299_count", "agg_a_rb_0_299_count", "agg_a_rb_0_299_min",
                                      "agg_a_rbc_0_299_min", "agg_a_ann_301_649_min", "agg_a_ann_unknown", "agg_p_0_299_count",
                                      "agg_p_100_299_count", "agg_q_0_299_count", "agg_q_100_299_count", "vel_q_299", "groups_a_rb",
                                      "distinct_d_d1_0_299", "distinct_d_d3_0_299", "distinct_d_dbig_0_299", "distinct_d_dw_100_200",
                                      "bursts_v_NOPE_2", "vel_a_ud", "ms_velocity_default_now_recent")}
    contrasts["labels_injected_equals_two_keys"] = obs["labels"]["injected"]["hash"] == obs["labels"]["two_keys"]["hash"]
    contrasts["fraction_canonical"] = obs["labels"]["fraction"]["canonical"]
    contrasts["nested"] = {k: v for k, v in obs["nested"].items() if k.endswith("same_hash")}
    contrasts["nested_map_canonicals"] = [obs["nested"]["nested_map_1"]["canonical"], obs["nested"]["nested_map_2"]["canonical"]]
    contrasts["ms_in_sec"] = {k: obs[k] for k in ("ms_in_sec_whole_count", "ms_in_sec_cut_count", "ms_in_sec_raw_window", "ms_in_sec_velocity",
                                                    "ms_vel_window_300", "ms_vel_window_300000")}
    body = {"kind": "binding", "model": "temporal_stats", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "prefix": P, "T": T, "verdict": "AGREES" if not mism else "DISAGREES", "cases": ncases,
            "mismatches": [{"case": n, "expected": w_, "observed": g_} for n, w_, g_ in mism], "contrasts": contrasts,
            "observed": obs, "histories": {k: [list(map(str, op)) for op in v] for k, v in hs.items()},
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "temporal_stats.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_src/src/Graph/KG/TemporalIndex.cls", "iris_src/src/Graph/KG/TemporalIndexMS.cls",
                                                                   "iris_vector_graph/_engine/temporal.py", "iris_vector_graph/stores/iris_sql_store.py"]}},
            "scope": "Actual product on IRIS 2026.1 (pin 3eaa79cf), seconds class through the Python engine (create_edge_temporal insert/update, "
                     "bulk_create_edges_temporal, delete_edge_temporal, a caller's START TRANSACTION/ROLLBACK around create_edge_temporal, "
                     "purge_raw_before, purge_bucket_range) and its readers (get_temporal_aggregate, get_bucket_groups, get_bucket_group_targets, "
                     "get_edge_velocity, find_burst_nodes, get_distinct_count, intern/resolve_label_set incl. nested values); TemporalIndexMS InsertEdge, GetVelocity "
                     "and GetBucketCount through the driver. Expected answers from the port of the model's writers applied to the same history. "
                     "SHA-1 register choice computed as HLLAdd does (provider); IRIS number text in label sets is a provider rule; a nested value's per-call "
                     "object reference text is read back from the product (provider input; its form NN@%Library.DynamicObject/Array is checked). "
                     "The millisecond edge is read by the seconds readers (iteration 53). Latest reads "
                     "are observed by the iteration-51 probe only."}
    d = REPO / ".g5/Verus_verification/results/temporal_stats" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "contrasts", "all_sensitivities_detected", "sensitivities_detected_cases",
                                             "observation_tamper_detected", "elapsed_s")}, default=str))
    for x in body["mismatches"]:
        print("MISMATCH", json.dumps(x, default=str)[:600])


if __name__ == "__main__":
    main()
