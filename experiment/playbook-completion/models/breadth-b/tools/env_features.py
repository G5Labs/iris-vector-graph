#!/usr/bin/env python3
"""Union of the IRIS engine features modules 07..11 rely on (modules/NN.json env_features), for the orchestrator's
IRIS environment contract (§3.2 coverage). Writes models/breadth-b/env_features.json: one entry per module feature,
grouped under a normalized key, with every module and source line that relies on it. Read-only over the inputs."""
import json, re
from pathlib import Path
C = Path(__file__).resolve().parents[3]
out = {}
for m in ["07", "08", "09", "10", "11"]:
    md = json.loads((C / f"modules/{m}.json").read_text())
    for f in md.get("env_features", []):
        name = str(f.get("feature", "")).strip()
        key = re.sub(r"[^a-z0-9$^%|+]+", " ", name.lower()).strip()[:60]
        e = out.setdefault(key, {"feature": name, "modules": [], "uses": []})
        if m not in e["modules"]:
            e["modules"].append(m)
        e["uses"].append({"module": m, "used_for": f.get("used_for"), "source": f.get("source"),
                          **({"contract": f["contract"]} if "contract" in f else {}),
                          **({"in_contract": f["in_contract"]} if "in_contract" in f else {})})
CATS = [("transactions", r"tstart|tcommit|trollback|\$tlevel|transaction|rollback|savepoint|commit"),
        ("locks", r"\block\b|row lock|lock table|escalat"),
        ("increment-counters", r"\$i(ncrement)?\b|counter"),
        ("isolation-visibility", r"isolation|uncommitted|visib|read committed|%nolock"),
        ("process-private-temp", r"\^\|\||process-private|iris\.temp|iristemp"),
        ("global-order-collation", r"\$order|\$query|\$data|collation|subscript|\$list|\$piece|global"),
        ("json", r"json|dynamic(object|array)"),
        ("sql-ddl-schema", r"ddl|create (table|index|function|procedure)|alter|unique index|-119|foreign key|%dictionary|sqlproc|functional ?index|index"),
        ("sql-runtime", r"\bsql\b|sqlcode|%sql|dbapi|top |order by|%find|like"),
        ("compile-codegen", r"compile|%system\.obj|class (re)?compiled|loadstream"),
        ("jobs-workers", r"\bjob\b|workmgr|worker|background|%sys\.task"),
        ("text-ifind", r"ifind|tokeniz|analyze"),
        ("embedded-python-callout", r"python|gref|\$zf|callout"),
        ("hash-crypto-time", r"zcrc|sha|encryption|guid|\$h|\$z(timestamp|datetime)|random"),
        ("objects-streams", r"%persistent|%openid|%save|stream|%onbefore|%ondelete|rejectupdate|trigger|%killextent"),
        ("security-privilege", r"privilege|security|role|%native|resource"),
        ("rest-native-api", r"rest|%csp|native api|classmethodvalue|createiris")]
for e in out.values():
    txt = (e["feature"] + " " + " ".join(str(u.get("used_for", "")) for u in e["uses"])).lower()
    e["categories"] = [c for c, rx in CATS if re.search(rx, txt)] or ["other"]
cat_index = {}
for e in out.values():
    for c in e["categories"]:
        d = cat_index.setdefault(c, {"modules": set(), "features": 0})
        d["modules"].update(e["modules"]); d["features"] += 1
cat_index = {c: {"modules": sorted(v["modules"]), "features": v["features"]} for c, v in sorted(cat_index.items())}
items = sorted(out.values(), key=lambda e: (-len(e["modules"]), e["feature"].lower()))
doc = {"_doc": __doc__, "inputs": [f"experiment/playbook-completion/modules/{m}.json" for m in ["07", "08", "09", "10", "11"]],
       "count_module_features": sum(len(e["uses"]) for e in items), "count_distinct": len(items),
       "categories": cat_index, "features": items}
(C / "models/breadth-b/env_features.json").write_text(json.dumps(doc, indent=1) + "\n")
print(f"{doc['count_module_features']} module features, {len(items)} distinct after name normalization")
