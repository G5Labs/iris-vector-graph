"""HD-0704 probe: is `__stop__` effectively reserved, and what does using it as an index name do?

Contract cited (pin 3eaa79cf):
- iris_src/src/Graph/KG/BM25Index.cls:626-627 (maintainer, 22e7ed4d, 4.6.0 R165): "^BM25Idx("__stop__") is the
  stopword list, not an index".
- docs/USER_GUIDE.md:885-891 and docs/API_REFERENCE.md:810 (bm25_build): 77 English stopwords are left out of documents
  and queries; `Graph.KG.BM25Index.InitStopwords` is the list.
Oracle (public engine API only: bm25_build / bm25_search / bm25_insert / bm25_drop / bm25_info):
- R1 "reserved" reading: bm25_build/bm25_insert/bm25_drop("__stop__") are refused, and afterwards the stopword node holds
  exactly the 77 words and an unrelated index tokenizes as before.
- R2 "unchecked" (as-built per source): the calls are accepted; Build("__stop__") writes index nodes (cfg, tf, df, doc,
  len) under the stopword node, which Tokenize then treats as stopwords ($Data(^BM25Idx("__stop__", tok))), so the
  documented 77-word list changes for every index; Drop("__stop__") deletes the stopword list.
Verdict: pass if R1 holds; fail if the documented stopword list / unrelated index tokenization changes (R2).
Data: graph `ia-0704`, ids `ia0704:*`, indexes `ia0704a`, `ia0704b`. ^BM25Idx("__stop__") is saved to ^IVGAuditIA0704
before and restored exactly afterwards (then the scratch global is killed).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

G = "ia-0704"
STOP = "__stop__"
DOCS = {
    "ia0704:n1": "doc review cfg memo",
    "ia0704:n2": "len tf df notes",
    "ia0704:n3": "plain zebra words",
}
INDEX_KEYS = ("cfg", "tf", "df", "doc", "len")


def stop_words(c):
    d = C.dump_global(c, "^BM25Idx", STOP)
    first = sorted({k[0] for k in d if k})
    return d, first


def try_call(label, fn):
    try:
        r = fn()
        C.obs(step=label, accepted=True, result=r)
        return True, r
    except Exception as e:  # noqa: BLE001
        C.obs(step=label, accepted=False, error=str(e)[:300])
        return False, None


def main() -> int:
    c = C.conn()
    e = C.engine(c)
    saved = C.dump_global(c, "^BM25Idx", STOP)
    C.restore_global(c, "^IVGAuditIA0704", saved)  # scratch copy (kept until the end)
    C.obs(step="saved_stop", nodes=len(saved), defined_before=bool(saved))
    failures = []
    try:
        for nid, text in DOCS.items():
            e.create_node(nid, labels=["IA0704"], properties={"name": text}, graph=G)
        e.bm25_build("ia0704a", ["name"], graph=G)
        before = {q: e.bm25_search("ia0704a", q, k=5) for q in ("doc", "len", "zebra")}
        d0, words0 = stop_words(c)
        C.obs(step="baseline", searches=before, stop_children=len(words0),
              index_keys_in_stop=[w for w in words0 if w in INDEX_KEYS])

        ok_build, _ = try_call("bm25_build(__stop__)", lambda: e.bm25_build(STOP, ["name"], graph=G))
        d1, words1 = stop_words(c)
        sub = {w: c.o.isDefined("^BM25Idx", STOP, w) for w in INDEX_KEYS}
        C.obs(step="after_build_stop", stop_children=len(words1), index_subtrees_in_stop=sub,
              stopword_like_children_added=sorted(set(words1) - set(words0)),
              list_=str(c.call("Graph.KG.BM25Index", "List")), info=e.bm25_info(STOP))
        if ok_build:
            failures.append("bm25_build('__stop__') accepted")

        # An unrelated index built afterwards: are the documented terms still indexed?
        e.bm25_build("ia0704b", ["name"], graph=G)
        after = {q: e.bm25_search("ia0704b", q, k=5) for q in ("doc", "len", "zebra")}
        ins = e.bm25_insert("ia0704a", "ia0704:n9", "doc len")
        C.obs(step="unrelated_index_after", searches=after, insert_doc_len_returned=ins,
              ia0704a_info=e.bm25_info("ia0704a"))
        lost = [q for q in ("doc", "len") if before[q] and not after[q]]
        if lost:
            failures.append(f"terms {lost} no longer indexed by an unrelated index")

        ok_drop, _ = try_call("bm25_drop(__stop__)", lambda: e.bm25_drop(STOP))
        C.obs(step="after_drop_stop", stop_defined=c.o.isDefined("^BM25Idx", STOP))
        if ok_drop and not c.o.isDefined("^BM25Idx", STOP):
            failures.append("bm25_drop('__stop__') deleted the stopword list")
        # The next tokenize re-creates it
        e.bm25_search("ia0704b", "zebra", k=1)
        d3, words3 = stop_words(c)
        C.obs(step="after_next_tokenize", stop_children=len(words3))

        ok_ins, _ = try_call("bm25_insert(__stop__)", lambda: e.bm25_insert(STOP, "ia0704:x", "hello zebra"))
        d4, words4 = stop_words(c)
        C.obs(step="after_insert_stop", stop_children=len(words4),
              index_subtrees_in_stop={w: c.o.isDefined("^BM25Idx", STOP, w) for w in INDEX_KEYS})
        if ok_ins:
            failures.append("bm25_insert('__stop__') accepted")
    finally:
        for name in ("ia0704a", "ia0704b"):
            try:
                e.bm25_drop(name)
            except Exception as ex:  # noqa: BLE001
                C.obs(cleanup_error=str(ex)[:200])
        e.erase_graph(G)
        back = C.dump_global(c, "^IVGAuditIA0704")
        C.restore_global(c, "^BM25Idx", back, STOP)
        c.o.kill("^IVGAuditIA0704")
        C.obs(step="restored", stop_nodes_now=len(C.dump_global(c, "^BM25Idx", STOP)), equal_to_saved=(
            C.dump_global(c, "^BM25Idx", STOP) == saved), scratch_left=c.o.isDefined("^IVGAuditIA0704"),
            graph_rows_left=c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", G))
        c.close()
    if failures:
        C.verdict("fail", "; ".join(failures))
    else:
        C.verdict("pass", "__stop__ refused by the public BM25 writers; stopword list unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
