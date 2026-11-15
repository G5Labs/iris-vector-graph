"""Seeded random schedules for the simulator (pure: no IRIS).

A schedule is two phases. Phase 1 builds and churns two or three tenants: ledger commits (nodes, relationships,
qualifiers, properties, deletes, post-commit properties, idempotency keys, retries with the same key and conflicting
reuses of a key), ledger-bypassing engine writes, erasures and redactions (bounded and unbounded), verify() and
reconstruct(). Phase 2 offboards one tenant (erase, then redact every target of it, resumed until complete) while
the other workers keep writing, some of them into the tenant being offboarded. A probe process may hold the ledger
head lock or an adjacency writer lock name; the driver may terminate a worker's IRIS process mid-operation.

Tenant shapes: "prefix" (ids 'acme|...' in the default graph) and "graph" (ids 'gamma|...', relationships in graph
'gamma_g'; its redaction is the documented two targets, redact('gamma_g') and redact(None, prefix='gamma')).
Every string a tenant's operations carry contains the tenant's name, so SC-001 can look for the name.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from iris_vector_graph.ledger import Changeset

TENANTS = [("acme", "prefix"), ("beta", "prefix"), ("gamma", "graph")]
POOL = 7          # ids per tenant, shared by all workers so that operations collide


def tenant(name: str, shape: str) -> Dict:
    return {"name": name, "shape": shape, "graph": f"{name}_g" if shape == "graph" else None}


def targets(t: Dict) -> List[Dict]:
    """The redaction targets that together cover a tenant (graph first, then its node ids)."""
    if t["shape"] == "graph":
        return [{"graph": t["graph"], "prefix": None}, {"graph": None, "prefix": t["name"]}]
    return [{"graph": None, "prefix": t["name"]}]


class Gen:
    def __init__(self, seed: int, phase2: bool = True) -> None:
        self.seed = seed
        self.r = random.Random(seed)
        r = self.r
        k = r.choice([2, 2, 3, 3, 3])
        picks = [TENANTS[0]] + r.sample(TENANTS[1:], k - 1) if k < 3 else list(TENANTS)
        self.tenants = [tenant(n, s) for n, s in picks]
        self.kill = r.random() < 0.45
        self.n_workers = r.choice([2, 3] if self.kill else [2, 3, 4])
        self.probe = r.random() < 0.5      # at most 4 workers + probe + driver = 6 connections
        self.sent: Dict[int, List[Dict]] = {}
        self.counter = 0
        self.phase2 = phase2

    # ---------------------------------------------------------------- helpers
    def pid(self, t: Dict) -> str:
        return f"{t['name']}|n{self.r.randrange(POOL)}"

    def meta(self, t: Dict, w: int, i: int) -> Dict:
        r = self.r
        self.counter += 1
        n = self.counter
        return {"actor": f"audit:sim:w{w}", "message": f"{t['name']} commit {self.seed}-{n}",
                "source": {"tenant": t["name"], "n": n}, "correlation_id": f"{t['name']}-corr-{w}",
                "key": f"{t['name']}-k-{self.seed}-{n}" if r.random() < 0.6 else None}

    def changeset(self, t: Dict, w: int, i: int, others: List[Dict]) -> Dict:
        r = self.r
        g = t["graph"]
        m = self.meta(t, w, i)
        cs = Changeset(actor=m["actor"], actor_type="ingest", auto_stub_missing_nodes=True)
        kind = r.choices(["nodes", "rels", "props", "qual", "delete_rel", "delete_node", "label", "span", "mixed"],
                         [14, 26, 10, 8, 8, 5, 4, 5, 10])[0]
        span_to = [o for o in others if o["shape"] == "prefix" and o is not t]
        if kind == "span" and (t["shape"] != "prefix" or not span_to):
            kind = "rels"
        a, b = self.pid(t), self.pid(t)
        while b == a:
            b = self.pid(t)
        sec = f"{t['name']}-secret-{self.seed}-{self.counter}"
        if kind == "nodes":
            ids = {self.pid(t) for _ in range(r.choice([1, 1, 2]))}
            for x in sorted(ids):
                if r.random() < 0.5:
                    cs.create_node(x, labels=["Person"], properties={"name": sec})
                else:
                    cs.upsert_node(x, labels=["Person"], properties={"name": sec})
        elif kind == "rels":
            for _ in range(r.choice([1, 1, 2])):
                if r.random() < 0.7:
                    cs.create_relationship(a, "KNOWS", b, graph=g,
                                           qualifiers={"note": f"{t['name']}-q-{self.counter}"} if r.random() < 0.5 else None)
                else:
                    cs.upsert_node(a)
                    cs.upsert_node(b)
                    cs.upsert_relationship(a, "KNOWS", b, graph=g, qualifiers={"note": f"{t['name']}-uq-{self.counter}"})
                a, b = b, self.pid(t)
                if a == b:
                    break
        elif kind == "props":
            cs.upsert_node(a)
            cs.set_property(a, "city", f"{t['name']}-city-{self.counter}")
        elif kind == "qual":
            cs.set_qualifier((a, "KNOWS", b, g), "note", f"{t['name']}-sq-{self.counter}")
        elif kind == "delete_rel":
            cs.delete_relationship((a, "KNOWS", b, g))
        elif kind == "delete_node":
            cs.delete_node(a, mode="detach")
        elif kind == "label":
            cs.upsert_node(a)
            cs.add_label(a, "Person")
        elif kind == "span":
            u = r.choice(span_to)
            cs.create_relationship(a, "KNOWS", f"{u['name']}|n{r.randrange(POOL)}")
        elif kind == "mixed":
            cs.upsert_node(a, labels=["Person"], properties={"name": sec})
            cs.create_relationship(a, "KNOWS", b, graph=g)
            cs.set_qualifier((a, "KNOWS", b, g), "note", f"{t['name']}-mq-{self.counter}")
        pcp = {a: {"audit": f"{t['name']}-pcp-{self.counter}"}} if r.random() < 0.15 else {}
        return {**m, "ops": cs.ops, "pcp": pcp, "tenant": t["name"], "variant": kind}

    def think(self) -> float:
        return round(self.r.choice([0, 0, 0.01, 0.03, 0.08, 0.15, 0.3]), 3)

    def redact_ops(self, t: Dict, bounded: Optional[bool] = None) -> List[Dict]:
        r = self.r
        out = []
        for tg in targets(t):
            b = r.choice([1, 2, 3, 5, 50, 2000])
            mb = 0 if (bounded is False or (bounded is None and r.random() < 0.6)) else r.choice([1, 2, 3])
            out.append({"kind": "redact", "tenant": t["name"], "graph": tg["graph"], "prefix": tg["prefix"],
                        "batch": b, "max_batches": mb, "think": self.think()})
        return out

    def erase_ops(self, t: Dict) -> List[Dict]:
        out = []
        if t["shape"] == "graph":
            out.append({"kind": "erase", "tenant": t["name"], "graph_erase": t["graph"], "think": self.think()})
        out.append({"kind": "erase", "tenant": t["name"], "prefix": t["name"] + "|", "graph": None,
                    "think": self.think()})
        return out

    def random_op(self, w: int, i: int, pool: List[Dict]) -> List[Dict]:
        r = self.r
        t = r.choice(pool)
        k = r.choices(["commit", "retry", "conflict", "direct", "erase", "redact", "verify", "reconstruct"],
                      [44, 7, 2, 10, 6, 9, 6, 6])[0]
        sent = self.sent.setdefault(w, [])
        if k in ("retry", "conflict"):
            keyed = [s for s in sent if s.get("key")]
            if not keyed:
                k = "commit"
            else:
                s = dict(r.choice(keyed))
                if k == "conflict":
                    s["ops"] = list(s["ops"]) + [{"op": "upsert_node", "id": f"{s['tenant']}|n{r.randrange(POOL)}"}]
                s["retry_of"] = s["key"]
                return [{"kind": "commit", "tenant": s["tenant"], "cs": s, "retry": k, "think": self.think()}]
        if k == "commit":
            s = self.changeset(t, w, i, self.tenants)
            sent.append(s)
            return [{"kind": "commit", "tenant": t["name"], "cs": s, "think": self.think()}]
        if k == "direct":
            g = t["graph"]
            fn = r.choice(["create_node", "create_edge", "create_edge", "delete_edge"])
            if fn == "create_node":
                args = {"id": f"{t['name']}|d{r.randrange(4)}", "labels": ["Person"],
                        "props": {"name": f"{t['name']}-direct-{self.seed}-{i}"}, "graph": g if r.random() < 0.5 else None}
            elif fn == "create_edge":
                a, b = self.pid(t), self.pid(t)
                args = {"s": a, "p": r.choice(["LINKS", "KNOWS"]), "o": b, "graph": g}
            else:
                a, b = self.pid(t), self.pid(t)
                args = {"s": a, "p": "KNOWS", "o": b, "graph": g}
            return [{"kind": "direct", "tenant": t["name"], "fn": fn, "args": args, "think": self.think()}]
        if k == "erase":
            return self.erase_ops(t)
        if k == "redact":
            return (self.erase_ops(t) if r.random() < 0.6 else []) + self.redact_ops(t)
        return [{"kind": k, "think": self.think()}]

    # ---------------------------------------------------------------- schedule
    def holds(self, n: int) -> List[Dict]:
        r = self.r
        out = []
        for _ in range(n):
            if r.random() < 0.5:
                out.append({"kind": "hold", "global": "^IVG.Ledger", "subs": ["head"],
                            "seconds": round(r.uniform(0.3, 2.5), 2), "think": round(r.uniform(0.2, 2.0), 2)})
            else:
                gs = [0] + [t["graph"] for t in self.tenants if t["graph"]]
                out.append({"kind": "hold", "global": "^IVG.AdjW", "subs": [r.choice(gs)],
                            "seconds": round(r.uniform(0.5, 6.0), 2), "think": round(r.uniform(0.2, 2.0), 2)})
        return out

    def schedule(self) -> Dict:
        r = self.r
        phases = []
        # phase 1: build-up and churn
        p1 = {}
        for w in range(self.n_workers):
            ops: List[Dict] = []
            n = r.randint(8, 16)
            i = 0
            while len(ops) < n:
                ops += self.random_op(w, i, self.tenants)
                i += 1
            p1[str(w)] = {"ops": ops}
        if self.probe:
            p1["9"] = {"ops": self.holds(r.randint(1, 4)), "probe": True}
        phases.append({"workers": p1, "kills": sorted(round(r.uniform(0.5, 8.0), 2) for _ in range(r.randint(1, 2)))
                       if self.kill else []})
        if self.phase2:
            off = r.choice(self.tenants)
            p2 = {}
            # the offboarding worker: erase, redact every target; again if a run did not complete
            ops: List[Dict] = []
            for _round in range(2):
                ops += self.erase_ops(off)
                bounded = r.random() < 0.35
                for _ in range(3 if bounded else 1):
                    ops += self.redact_ops(off, bounded=bounded)
            ops.append({"kind": "verify", "think": 0.0})
            p2["10"] = {"ops": ops, "offboard": off["name"]}
            for w in range(1, self.n_workers):
                wops: List[Dict] = []
                pool = [t for t in self.tenants if t is not off] or self.tenants
                n = r.randint(5, 10)
                i = 100
                while len(wops) < n:
                    use = self.tenants if r.random() < 0.3 else pool
                    wops += self.random_op(10 + w, i, use)
                    i += 1
                p2[str(10 + w)] = {"ops": wops}
            if self.probe:
                p2["19"] = {"ops": self.holds(r.randint(1, 3)), "probe": True}
            phases.append({"workers": p2, "offboard": off["name"],
                           "kills": [round(r.uniform(0.3, 5.0), 2)] if self.kill and r.random() < 0.5 else []})
        return {"seed": self.seed, "tenants": self.tenants, "phases": phases, "n_workers": self.n_workers,
                "probe": self.probe, "kill": self.kill}


RACE_SEED_BASE = 2000   # seeds >= this use the race templates; below it the general generator (unchanged)


class RaceGen(Gen):
    """Race templates: the same operation vocabulary, timed to overlap in the windows the audit's models name
    (two targets' runs at once; commits and bypass writes into a target being redacted; an erasure paused on the
    adjacency writer lock while commits land; readers across a redaction; retries after an erase; a killed or
    bounded redaction resumed). Which template runs is drawn from the seed; nothing is scripted to a known result."""

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        r = self.r
        self.tenants = [tenant(n, s) for n, s in TENANTS]
        self.template = r.choice(["dual-offboard", "commit-into-offboard", "erase-vs-commit", "reader-vs-redact",
                                  "retry-after-erase", "kill-redaction", "bounded-resume", "mixed"])
        self.kill = self.template in ("kill-redaction",) or r.random() < 0.15
        self.n_workers = 3
        self.probe = self.template == "erase-vs-commit" or r.random() < 0.3

    def build(self, w: int, n: int, pool: List[Dict]) -> List[Dict]:
        ops = []
        for i in range(n):
            t = pool[i % len(pool)]
            s = self.changeset(t, w, i, self.tenants)
            if self.r.random() < 0.5:
                s["ops"] = list(s["ops"])
            self.sent.setdefault(w, []).append(s)
            ops.append({"kind": "commit", "tenant": t["name"], "cs": s, "think": 0.0})
        return ops

    def burst(self, w: int, t: Dict, n: int, direct: float = 0.25) -> List[Dict]:
        r = self.r
        ops = []
        for i in range(n):
            if r.random() < direct:
                a, b = self.pid(t), self.pid(t)
                fn = r.choice(["create_node", "create_edge"])
                args = ({"id": f"{t['name']}|d{r.randrange(3)}", "labels": ["Person"],
                         "props": {"name": f"{t['name']}-direct-{self.seed}-{i}"}, "graph": None}
                        if fn == "create_node" else {"s": a, "p": "LINKS", "o": b, "graph": t["graph"]})
                ops.append({"kind": "direct", "tenant": t["name"], "fn": fn, "args": args,
                            "think": round(r.uniform(0, 0.05), 3)})
            else:
                s = self.changeset(t, w, i, self.tenants)
                self.sent.setdefault(w, []).append(s)
                ops.append({"kind": "commit", "tenant": t["name"], "cs": s, "think": round(r.uniform(0, 0.05), 3)})
        return ops

    def small_redact(self, t: Dict, max_batches: int = 0) -> List[Dict]:
        return [{"kind": "redact", "tenant": t["name"], "graph": tg["graph"], "prefix": tg["prefix"],
                 "batch": self.r.choice([1, 1, 2, 3]), "max_batches": max_batches, "think": 0.0} for tg in targets(t)]

    def schedule(self) -> Dict:
        r = self.r
        acme, beta, gamma = self.tenants
        setup = {"0": {"ops": self.build(0, 6, [acme, beta, gamma])},
                 "1": {"ops": self.build(1, 6, [gamma, acme, beta])},
                 "2": {"ops": self.build(2, 6, [beta, gamma, acme])}}
        phases = [{"workers": setup, "kills": []}]
        tp = self.template
        race: Dict[str, Dict] = {}
        kills: List[float] = []
        if tp == "dual-offboard":
            x, y = r.sample([acme, beta, gamma], 2)
            race["10"] = {"ops": self.erase_ops(x) + self.small_redact(x)}
            race["11"] = {"ops": self.erase_ops(y) + self.small_redact(y)}
            z = next(t for t in self.tenants if t not in (x, y))
            race["12"] = {"ops": self.burst(12, z, 6)}
        elif tp == "commit-into-offboard":
            x = r.choice(self.tenants)
            race["10"] = {"ops": self.erase_ops(x) + self.small_redact(x) + self.erase_ops(x) + self.small_redact(x)}
            race["11"] = {"ops": self.burst(11, x, 10, direct=0.0)}
            race["12"] = {"ops": self.burst(12, x, 8, direct=0.5)}
        elif tp == "erase-vs-commit":
            x = r.choice([gamma, acme])
            gk = x["graph"] if x["graph"] else 0
            race["19"] = {"ops": [{"kind": "hold", "global": "^IVG.AdjW", "subs": [gk],
                                   "seconds": round(r.uniform(1.0, 6.5), 2), "think": 0.0}], "probe": True}
            ers = self.erase_ops(x)
            for e in ers:
                e["think"] = 0.3
            race["10"] = {"ops": ers}
            race["11"] = {"ops": [dict(o, think=round(0.6 + r.uniform(0, 0.4), 3) if k == 0 else 0.05)
                                  for k, o in enumerate(self.burst(11, x, 6, direct=0.0))]}
            race["12"] = {"ops": self.burst(12, r.choice(self.tenants), 5)}
        elif tp == "reader-vs-redact":
            x = r.choice(self.tenants)
            race["10"] = {"ops": self.erase_ops(x) + self.small_redact(x)}
            race["11"] = {"ops": [{"kind": "reconstruct", "think": round(r.uniform(0, 0.04), 3)} for _ in range(8)]}
            race["12"] = {"ops": [{"kind": r.choice(["reconstruct", "verify"]), "think": round(r.uniform(0, 0.04), 3)}
                                  for _ in range(8)]}
        elif tp == "retry-after-erase":
            x = r.choice([acme, beta])
            keyed = []
            for i in range(4):
                s = self.changeset(x, 10, 200 + i, self.tenants)
                s["key"] = s["key"] or f"{x['name']}-k-{self.seed}-r{i}"
                s["pcp"] = {f"{x['name']}|n{i}": {"audit": f"{x['name']}-pcp-r{i}"}}
                s["ops"] = [{"op": "upsert_node", "id": f"{x['name']}|n{i}", "labels": ["Person"],
                             "props": {"name": f"{x['name']}-secret-r{i}"}}]
                keyed.append(s)
            first = [{"kind": "commit", "tenant": x["name"], "cs": s, "think": 0.0} for s in keyed]
            retry = [{"kind": "commit", "tenant": x["name"], "cs": dict(s, retry_of=s["key"]), "retry": "retry",
                      "think": round(r.uniform(0, 0.1), 3)} for s in keyed]
            race["10"] = {"ops": first + self.erase_ops(x) + self.small_redact(x) + self.erase_ops(x)
                          + self.small_redact(x)}
            race["11"] = {"ops": [dict(o, think=0.15) if k == 0 else o for k, o in enumerate(retry + retry)]}
            race["12"] = {"ops": self.burst(12, r.choice(self.tenants), 5)}
        elif tp == "kill-redaction":
            x = r.choice(self.tenants)
            race["10"] = {"ops": self.erase_ops(x) + self.small_redact(x) + self.small_redact(x)}
            race["11"] = {"ops": self.burst(11, r.choice([t for t in self.tenants if t is not x]), 6)}
            kills = [round(r.uniform(0.2, 1.5), 2)]
        elif tp == "bounded-resume":
            x = r.choice(self.tenants)
            ops = self.erase_ops(x)
            for _ in range(6):
                ops += self.small_redact(x, max_batches=1)
            race["10"] = {"ops": ops + [{"kind": "verify", "think": 0.0}]}
            race["11"] = {"ops": self.burst(11, r.choice([t for t in self.tenants if t is not x]), 6)}
            race["12"] = {"ops": [{"kind": "reconstruct", "think": 0.1} for _ in range(4)]}
        else:  # mixed: the general generator's random operations, three workers, short think times
            for w in (10, 11, 12):
                ops: List[Dict] = []
                while len(ops) < 10:
                    ops += self.random_op(w, len(ops), self.tenants)
                for o in ops:
                    o["think"] = round(r.uniform(0, 0.03), 3)
                race[str(w)] = {"ops": ops}
        if self.probe and "19" not in race:
            race["19"] = {"ops": self.holds(r.randint(1, 3)), "probe": True}
        if self.kill and not kills:
            kills = [round(r.uniform(0.3, 3.0), 2)]
        phases.append({"workers": race, "kills": kills, "template": tp})
        # settle: every tenant offboarded in turn, one worker, then verify
        off = []
        for t in self.tenants:
            if r.random() < 0.5:
                off += self.erase_ops(t) + self.small_redact(t)
        off.append({"kind": "verify", "think": 0.0})
        phases.append({"workers": {"20": {"ops": off}}, "kills": []})
        return {"seed": self.seed, "tenants": self.tenants, "phases": phases, "n_workers": self.n_workers,
                "probe": self.probe, "kill": self.kill, "template": tp}


def generate(seed: int) -> Dict:
    if seed >= RACE_SEED_BASE:
        return RaceGen(seed).schedule()
    return Gen(seed).schedule()


def truncate(plan: Dict, keep: int) -> Dict:
    """A prefix of the schedule: the first `keep` operations of every worker, phases in order (for shrinking)."""
    import copy
    p = copy.deepcopy(plan)
    left = keep
    for ph in p["phases"]:
        for w in sorted(ph["workers"], key=int):
            ops = ph["workers"][w]["ops"]
            take = max(0, min(len(ops), left))
            ph["workers"][w]["ops"] = ops[:take]
        left -= max((len(x["ops"]) for x in ph["workers"].values()), default=0)
    for ph in p["phases"]:
        ph["workers"] = {w: v for w, v in ph["workers"].items() if v["ops"]}
    p["phases"] = [ph for ph in p["phases"] if ph["workers"]]
    return p
