"""§3.6 frame per statement-shape class: the oracle side (pure functions, no IRIS).

Input: the IRIS journal records one action's server process wrote (traces/journal.py records_since, pid-filtered,
AUDITD's database), the namespace's storage map, the action's declared write stores (from footprints/NN.json or
correspondence/correspondence.json, normalized here, never widened) and the action's key specification (the values
its arguments determine: node ids, edge endpoints, graph ids for graph-scoped actions, index names, prefixes).

(a) store level: every journaled global node belongs to a store (journal.store_of) that the declaration names, at
    root granularity (sql:<schema.table> or global:^Root); a first-subscript difference against a sub-store
    declaration (global:^KG("out")) is reported as a declaration gap, not as an excursion.
(b) key level: every journaled global node is under the action's keys:
    - SQL data node (^t<hash>.1(rowid), class storage ^...D(id)): the row's stored $list (new value for SET, old
      value for KILL; either for an UPDATE) holds one of the keys as a whole element -> the row is owned; a
      long-column node (rowid, column) of an owned row is the row's own;
    - SQL index node: one subscript equals an owned row id of that table, or one string subscript equals a key; an
      index-internal node (all subscripts integers or one-character tags: bitmap chunks, extent bitmaps, iFind word
      counters) is accepted only for a table in which the action owns a row;
    - the table's row-id counter (the data global's root node);
    - any other global node: a string subscript equals a key (or starts with a 'prefix:' key), or its value holds a
      key as a whole $list element / JSON string, or it matches one of the action's declared counter patterns
      (each cited: graph version stamps, ledger head/stmtNext, generation counters).
    Derived keys: an owned rdf_edges row adds its s and o_id; an owned node/label/property row adds its node id
    (the adjacency, label and property index nodes of those rows are then under key).
Each record is also classified into a statement-shape class (sql-insert, sql-update, sql-delete, sql-rowid-counter,
sql-index, global-set, global-increment, global-kill, bitmap) for coverage.
"""
from __future__ import annotations

import base64
import fnmatch
import json
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------------------------- parsing helpers


def parse_node(g: str) -> Tuple[str, List]:
    """'^KG("out","g1","a",3)' -> ('^KG', ['out','g1','a',3]). Extended references ^["^^dir"]X are reduced."""
    if g.startswith('^["'):
        g = "^" + g[g.index("]") + 1:]
    if "(" not in g:
        return g, []
    root, rest = g.split("(", 1)
    rest = rest[:-1] if rest.endswith(")") else rest
    subs: List = []
    i, n = 0, len(rest)
    while i < n:
        if rest[i] == '"':
            j, buf = i + 1, []
            while j < n:
                if rest[j] == '"':
                    if j + 1 < n and rest[j + 1] == '"':
                        buf.append('"')
                        j += 2
                        continue
                    break
                buf.append(rest[j])
                j += 1
            subs.append("".join(buf))
            i = j + 1
        else:
            j = i
            while j < n and rest[j] != ",":
                j += 1
            tok = rest[i:j].strip()
            if tok:
                try:
                    subs.append(int(tok))
                except ValueError:
                    try:
                        subs.append(float(tok))
                    except ValueError:
                        subs.append(tok)
            i = j
        while i < n and rest[i] in ", ":
            i += 1
    return root, subs


def decode_lb(b: Optional[bytes]) -> Optional[List]:
    """Decode an IRIS $list (strings, integers; other types as raw bytes). None if b is not a well-formed $list."""
    if b is None:
        return None
    out, i, n = [], 0, len(b)
    try:
        while i < n:
            ln = b[i]
            hdr = 1
            if ln == 0:
                ln = int.from_bytes(b[i + 1:i + 3], "little")
                hdr = 3
                if ln == 0:
                    ln = int.from_bytes(b[i + 3:i + 7], "little")
                    hdr = 7
                total = hdr + ln          # long form: the length counts type byte + data
                typ = b[i + hdr]
                data = b[i + hdr + 1:i + total]
            else:
                total = ln
                if ln == 1:
                    out.append(None)
                    i += 1
                    continue
                typ = b[i + 1]
                data = b[i + 2:i + total]
            if total <= 0 or i + total > n:
                return None
            if typ == 1:
                out.append(data.decode("latin-1"))
            elif typ == 2:
                out.append(data.decode("utf-16-le", errors="replace"))
            elif typ == 4:
                out.append(int.from_bytes(data, "little") if data else 0)
            elif typ == 5:
                out.append(int.from_bytes(data, "little", signed=True) if data else -1)
            else:
                out.append(data)
            i += total
    except Exception:  # noqa: BLE001
        return None
    return out


def value_strings(v64: Optional[str]) -> Set[str]:
    """Whole values a stored value carries: its $list string/int elements, the value itself, JSON string leaves."""
    if v64 is None:
        return set()
    b = base64.b64decode(v64)
    out: Set[str] = set()
    lb = decode_lb(b)
    if lb is not None:
        for x in lb:
            if isinstance(x, (str, int)):
                out.add(str(x))
                if isinstance(x, str) and x[:1] in "[{":
                    out |= _json_leaves(x)
    s = b.decode("latin-1")
    out.add(s)
    if s[:1] in "[{":
        out |= _json_leaves(s)
    return out


def _json_leaves(s: str) -> Set[str]:
    try:
        obj = json.loads(s)
    except Exception:  # noqa: BLE001
        return set()
    out: Set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                out.add(str(k))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif o is not None:
            out.add(str(o))
    walk(obj)
    return out


# ---------------------------------------------------------------------------------------------- stores


def table_globals(smap: Dict[str, str]) -> Dict[str, Tuple[str, str]]:
    """prefix -> (table, kind) where kind is 'hashed' (^t52S.XCFT. : .1 data) or 'class' (^Pkg.ClsD / ^Pkg.ClsI)."""
    out = {}
    for prefix, table in smap.items():
        out[prefix] = (table, "hashed" if prefix.endswith(".") else "class")
    return out


def sql_role(root: str, smap: Dict[str, str]):
    """(table, role) for a SQL storage global root: role data | index | stream; None if not a table's global."""
    for prefix, table in smap.items():
        if prefix.endswith("."):
            if (root + ".").startswith(prefix):
                suffix = root[len(prefix):]
                return table, ("data" if suffix == "1" else "index")
        elif root == prefix:
            if prefix.endswith("D"):
                return table, "data"
            if prefix.endswith("S"):
                return table, "stream"
            return table, "index"
    return None


def store_of(node: str, smap: Dict[str, str]) -> str:
    root, _ = parse_node(node)
    r = sql_role(root, smap)
    return ("sql:" + r[0]) if r else ("global:" + root)


def norm_decl(stores: Iterable[str]) -> Dict[str, Set[Optional[str]]]:
    """Declared stores -> {root store: {first subscripts declared or None for the whole store}}."""
    out: Dict[str, Set[Optional[str]]] = {}
    for s in stores:
        s = s.strip()
        if s.startswith("sql:"):
            t = s[4:].split()[0]
            if "." not in t:
                t = "Graph_KG." + t
            out.setdefault("sql:" + t.lower(), set()).add(None)
            continue
        if s.startswith("global:"):
            s = s[7:]
        m = re.match(r'(\^[%\w.]+)(?:\("?([^",)]*)"?)?', s)
        if not m:
            continue
        root, sub = m.group(1), m.group(2)
        out.setdefault("global:" + root, set()).add(sub if sub else None)
    return out


def store_key(store: str) -> str:
    return store.lower() if store.startswith("sql:") else store


# ---------------------------------------------------------------------------------------------- classification

# structural tags of IRIS index globals observed in AUDITD's journal: iFind ("P", rowid, ..), ("W", word, chunk),
# ("L", chunk, ..); HNSW ("G", level/entry, ..), ("G", "Ver"); everything else in those nodes is an integer
INDEX_TAGS = {"P", "W", "L", "G", "Ver"}
CATALOG = {"^oddTSQL", "^oddDEF", "^oddCOM", "^oddSQL", "^oddDEP", "^oddEXT", "^oddMAP", "^rINDEXSQL"}
EDGE_NODE_POS = {"graph_kg.rdf_edges": (1, 3), "graph_kg.nodes": (0,), "graph_kg.rdf_labels": (1,),
                 "graph_kg.rdf_props": (1,)}  # $list positions (0-based) of node-id columns, observed layout


def klass(r: Dict, role, bracketed: bool = False) -> str:
    t = r["t"]
    if t.startswith("BitSET"):
        return "bitmap"
    if role is not None:
        table, kind = role
        if kind == "data":
            _, subs = parse_node(r["g"])
            if not subs:
                return "sql-rowid-counter"
            if t.startswith(("KILL", "ZKILL")):
                return "sql-delete"
            return "sql-update" if r["o"] is not None else "sql-insert"
        return "sql-index"
    if t.startswith(("KILL", "ZKILL")):
        return "global-kill"
    if t.startswith("SET") and not r["x"] and bracketed:
        return "global-increment"   # IRIS journals $Increment inside a transaction as a non-transactional SET (observed)
    return "global-set"


def _norm(s) -> str:
    return str(s).strip().upper()


def key_match(sub, keys: Set[str], prefixes: Set[str], int_keys: Set[int]) -> bool:
    if isinstance(sub, int):
        return sub in int_keys
    s = str(sub)
    if s in keys or _norm(s) in {_norm(k) for k in keys}:
        return True
    return any(s.startswith(p) or _norm(s).startswith(_norm(p)) for p in prefixes)


def check(records: List[Dict], smap: Dict[str, str], declared: Iterable[str], keys: Iterable[str],
          counters: Iterable[Tuple[str, str]] = (), int_keys: Iterable[int] = (), any_key: bool = False,
          row_lookup=None, owned_tables: Iterable[str] = (), interned: Optional[Dict[int, str]] = None,
          whole_kills: Iterable[Tuple[str, str]] = (), ddl_catalog: bool = False) -> Dict:
    """Frame check of one action. keys: exact values or 'prefix:<p>'. counters: (regex over the node text, reason).
    any_key: a whole-store action (rebuild/erase-all): the key-level check is replaced by 'every node's key strings
    are among keys' only if keys is non-empty, otherwise skipped (reported)."""
    decl = norm_decl(declared)
    keyset = {k for k in keys if not k.startswith("prefix:")}
    prefixes = {k[7:] for k in keys if k.startswith("prefix:")}
    ints = set(int_keys)
    cpat = [(re.compile(p), why) for p, why in counters]
    otables = {t.lower() if "." in t else ("graph_kg." + t).lower() for t in owned_tables}
    wk = dict(whole_kills)
    cat_owned: Set = set()          # ^oddTSQL(id) entries whose stored text names a key (the DDL's table)
    if ddl_catalog:
        for r in records:
            if not r.get("g"):
                continue
            rt, ss = parse_node(r["g"])
            if rt in CATALOG and ss:
                if any(key_match(v, set(keys), set(), set()) or any(str(k) in v for k in keys if len(str(k)) > 8)
                       for v in value_strings(r["n"]) | value_strings(r["o"])):
                    cat_owned.add(ss[0])
    inside, depth = set(), {}
    for r in records:                       # transaction brackets per process (BeginTrans .. CommitTrans)
        t = r.get("t", "")
        if t == "BeginTrans":
            depth[r["p"]] = 1
        elif t == "CommitTrans" or t.startswith("RollbackTrans"):
            depth[r["p"]] = 0
        elif r.get("g") and depth.get(r["p"]):
            inside.add(r["a"])
    recs = [r for r in records if r.get("g")]
    roles = {id(r): sql_role(parse_node(r["g"])[0], smap) for r in recs}
    # pass 1: owned rows (data nodes whose stored row holds one of the action's own keys); derived node-id keys of
    # owned rows (an edge's endpoints) widen only the global-node and index-key rules, never row ownership
    owned: Dict[str, Set[int]] = {}
    derived: Set[str] = set()
    for r in recs:
        role = roles[id(r)]
        if not role or role[1] != "data":
            continue
        _, subs = parse_node(r["g"])
        if not subs:
            continue
        vals = value_strings(r["n"]) | value_strings(r["o"])
        if any(key_match(v, keyset, prefixes, set()) for v in vals):
            owned.setdefault(role[0], set()).add(subs[0])   # (rowid) or (rowid, column) for a long column
            raw = r["n"] or r["o"]
            lb = decode_lb(base64.b64decode(raw)) if raw else None
            for p in EDGE_NODE_POS.get(role[0].lower(), ()):
                if lb and p < len(lb) and isinstance(lb[p], str) and lb[p] not in keyset:
                    derived.add(lb[p])
    # a long-column node (rowid, column) written without its row's main node (an UPDATE of that column): the row's
    # identity is read from the row's current main node (row_lookup(root, rowid) -> base64 of the stored $list)
    if row_lookup is not None:
        for r in recs:
            role = roles[id(r)]
            if not role or role[1] != "data":
                continue
            root, subs = parse_node(r["g"])
            if len(subs) >= 2 and subs[0] not in owned.get(role[0], set()):
                v = row_lookup(root, subs[0])
                if v is not None and any(key_match(x, keyset, prefixes, set()) for x in value_strings(v)):
                    owned.setdefault(role[0], set()).add(subs[0])
    keyset = keyset | derived
    main_written = set()
    for r in recs:
        rl = roles[id(r)]
        if rl and rl[1] == "data":
            _, ss = parse_node(r["g"])
            if len(ss) == 1:
                main_written.add((rl[0], ss[0]))
    out_store, out_key, gaps, classes = [], [], set(), {}
    for r in recs:
        role = roles[id(r)]
        node = r["g"]
        root, subs = parse_node(node)
        store = ("sql:" + role[0]) if role else ("global:" + root)
        c = klass(r, role, r["a"] in inside)
        if c == "sql-insert" and role and role[1] == "data" and len(subs) >= 2 and (role[0], subs[0]) not in main_written:
            c = "sql-update"            # a long-column node of a row whose main node this window did not write
        classes[c] = classes.get(c, 0) + 1
        # (a) store level
        sk = store_key(store)
        if sk not in decl:
            for pat in decl:
                if "*" in pat and fnmatch.fnmatch(sk, pat.lower() if pat.startswith("sql:") else pat):
                    sk = pat
                    break
        if sk not in decl and ddl_catalog and root in CATALOG:
            c = "sql-ddl-catalog"
            classes[c] = classes.get(c, 0) + 1
        elif sk not in decl:
            out_store.append({"node": node[:160], "store": store, "class": c})
        elif not role and None not in decl[sk] and subs and str(subs[0]) not in decl[sk]:
            gaps.add(f"{root}({subs[0]!r}) not among declared sub-stores {sorted(x for x in decl[sk] if x)}")
        # (b) key level
        why = None
        if root == "^NKG" and interned:
            subs = [interned.get(x, x) if (i > 0 and isinstance(x, int) and x > 0) else x for i, x in enumerate(subs)]
        if role and role[0].lower() in otables:
            why = "node of a table the action's scope owns (route of its graph)"
        elif role:
            table, kind = role
            if kind == "data":
                if not subs:
                    why = "rowid-counter"
                elif subs[0] in owned.get(table, set()):
                    why = "owned-row" if len(subs) == 1 else "owned-row column node"
            else:
                if any(isinstance(s, int) and s in owned.get(table, set()) for s in subs):
                    why = "index-of-owned-row"
                elif any(key_match(s, keyset, prefixes, set()) for s in subs if isinstance(s, str) and len(s) > 1):
                    why = "index-key"
                elif owned.get(table) and all(isinstance(s, int) or s in INDEX_TAGS for s in subs):
                    why = "index-internal-of-owned-table"
        else:
            if any(key_match(s, keyset, prefixes, ints) for s in subs if not (isinstance(s, str) and len(s) == 0)):
                why = "subscript-key"
            else:
                for p, reason in cpat:
                    if p.search(node):
                        why = "counter: " + reason
                        break
                if why is None:
                    vals = value_strings(r["n"]) | value_strings(r["o"])
                    if any(key_match(v, keyset, prefixes, set()) for v in vals):
                        why = "value-key"
        if why is None and r["t"].startswith(("KILL", "ZKILL")) and root in wk:
            why = "declared whole-store kill: " + wk[root]
        if why is None and root in CATALOG and subs and subs[0] in cat_owned:
            why = "catalog entry of the DDL statement's own table"
        if why is None and role:
            for p, reason in cpat:
                if p.search(node):
                    why = "counter: " + reason
                    break
        if why is None and any_key:
            why = "whole-store action"
        if why is None:
            out_key.append({"node": node[:160], "store": store, "class": c, "t": r["t"],
                            "n": (base64.b64decode(r["n"])[:80].decode("latin-1") if r["n"] else None),
                            "o": (base64.b64decode(r["o"])[:80].decode("latin-1") if r["o"] else None)})
    stores = sorted({("sql:" + roles[id(r)][0]) if roles[id(r)] else "global:" + parse_node(r["g"])[0] for r in recs})
    return {"records": len(recs), "stores": stores, "classes": classes,
            "store_excursions": out_store, "key_excursions": out_key[:40], "key_excursion_count": len(out_key),
            "declaration_gaps": sorted(gaps), "owned_rows": {k: len(v) for k, v in owned.items()},
            "derived_keys": sorted(derived)[:20],
            "store_ok": not out_store, "key_ok": not out_key}


def self_test() -> Dict:
    """Offline self-test on synthetic journal records (hashed table ^tX.A. = Graph_KG.nodes)."""
    def lb(*xs):
        b = b""
        for x in xs:
            e = x.encode()
            b += bytes([len(e) + 2, 1]) + e
        return base64.b64encode(b).decode()
    smap = {"^tX.A.": "Graph_KG.nodes"}
    base = [{"a": 1001, "p": "1", "g": "^tX.A.1", "t": "SET", "x": False, "n": base64.b64encode(b"2").decode(), "o": None},
            {"a": 1002, "p": "1", "g": "^tX.A.1(2)", "t": "SET", "x": True, "n": lb("a", "g1"), "o": None},
            {"a": 1003, "p": "1", "g": "^tX.A.2(1)", "t": "BitSET", "x": True, "n": None, "o": None},
            {"a": 1004, "p": "1", "g": '^tX.A.3("a","g1",2)', "t": "SET", "x": True, "n": None, "o": None},
            {"a": 1005, "p": "1", "g": '^KG("label","g1","L","a")', "t": "SET", "x": True, "n": None, "o": None},
            {"a": 1006, "p": "1", "g": '^KG("__version")', "t": "SET", "x": False, "n": None, "o": None}]
    decl = ["sql:Graph_KG.nodes", "global:^KG"]
    cnt = [(r'^\^KG\("__version"\)$', "graph version stamp")]
    ok = check(base, smap, decl, ["a"], cnt)
    seeded_store = check(base + [{"a": 1007, "p": "1", "g": "^IVGAuditDFrmX(1)", "t": "SET", "x": True, "n": None, "o": None}],
                         smap, decl, ["a"], cnt)
    seeded_key = check(base + [{"a": 1008, "p": "1", "g": "^tX.A.1(3)", "t": "SET", "x": True, "n": lb("b", "g1"), "o": None},
                               {"a": 1009, "p": "1", "g": '^tX.A.3("b","g1",3)', "t": "SET", "x": True, "n": None, "o": None},
                               {"a": 1010, "p": "1", "g": '^KG("label","g1","L","b")', "t": "SET", "x": True, "n": None, "o": None}],
                       smap, decl, ["a"], cnt)
    prefix_ok = check(base, smap, decl, ["prefix:a"], cnt)
    res = {"conforming_passes": ok["store_ok"] and ok["key_ok"],
           "seeded_store_excursion_flagged": (not seeded_store["store_ok"]) and seeded_store["key_ok"] is False,
           "seeded_key_excursion_flagged": seeded_key["store_ok"] and seeded_key["key_excursion_count"] == 3,
           "prefix_key_passes": prefix_ok["key_ok"]}
    res["pass"] = all(res.values())
    return res


if __name__ == "__main__":
    print(json.dumps(self_test(), indent=1))
