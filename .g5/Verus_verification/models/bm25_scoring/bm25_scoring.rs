// product 3eaa79cf: BM25 scoring and ranking (W59, iteration 53). Index statistics -> query terms -> score -> rank.
//   Tokenize (iris_src/src/Graph/KG/BM25Index.cls 56-91): lower-case, %iFind analyzer (a provider: the raw token
//     list), drop "" and the 77 stopwords of InitStopwords 41-50.
//   IndexDoc 178-207 (tf per distinct token, len = kept tokens, a document with no kept token is not indexed),
//     Build 97-175 (N, totalLen, k1, b stored; schema 2).
//   SearchCore 236-367: N = 0 or empty query -> []; schema 2 reads N, totalLen, df at search time (avgdl =
//     totalLen / N, idf = $ZLN((N - df + 0.5) / (df + 0.5) + 1)); schema 1 reads the idf Build stored; the common-term
//     cutoff 263-290 (skip df / N > f; when every known term is skipped keep the first lowest-df one; unknown terms
//     neither skipped nor kept); each query token occurrence adds idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len /
//     avgdl)) to every document of its posting list (292-325); rank by a 12-decimal key descending, then document id
//     ascending (327-360); the first k.
//   Readers: Search 215, SearchReport 221-234, SearchProc 621-624 <- SqlProcs.kgBM25 (SQL kg_BM25, after the
//     rdf_props SELECT check) <- the translator's CALL ivg.bm25.search (JSON_TABLE, score DOUBLE);
//     _engine/vector.py VectorMixin.bm25_search 1786-1838 (classMethodValue Search / SearchReport, then `_parse`: a
//     regex inserting "0" before ".<digit>" after ':', '[' or ',' anywhere in the raw answer, F-C0715).
// Reals: the TF/length factor is an exact rational for k1 = 3/2, b = 3/4; ln is a premise (P-LN: strictly increasing,
// positive above 1), so IDF is represented by its argument, an exact rational.
use vstd::prelude::*;

verus! {

// =============================================================== tokens and query terms
pub type Tok = int;

/// Tokenize's filter over the analyzer's raw tokens (the provider): a stopword is dropped, every other token is kept
/// in order, repeats included.
pub open spec fn kept(stop: spec_fn(Tok) -> bool, raw: Seq<Tok>) -> Seq<Tok> decreases raw.len() {
    if raw.len() == 0 { Seq::empty() } else {
        let r = kept(stop, raw.drop_last());
        if stop(raw.last()) { r } else { r.push(raw.last()) }
    }
}

/// The stored statistics a schema-2 search reads: N, totalLen, df per term, tf per (term, doc), len per doc.
pub struct Stats { pub n: int, pub total: int, pub df: spec_fn(Tok) -> int, pub tf: spec_fn(Tok, int) -> int, pub len: spec_fn(int) -> int }

/// The common-term cutoff, f = fnum / fden (0 is off). A known term (df > 0) is skipped when df / N > f.
pub open spec fn over(st: Stats, t: Tok, fnum: int, fden: int) -> bool {
    fnum > 0 && (st.df)(t) > 0 && (st.df)(t) * fden > fnum * st.n
}
pub open spec fn known(st: Stats, t: Tok) -> bool { (st.df)(t) > 0 }
/// Whether every known query term is over the cutoff (vacuously true when none is known).
pub open spec fn all_over(st: Stats, q: Seq<Tok>, fnum: int, fden: int) -> bool {
    forall|i: int| 0 <= i < q.len() && known(st, #[trigger] q[i]) ==> over(st, q[i], fnum, fden)
}
/// The first query term with the lowest df among the known ones (the `<` in SearchCore keeps the first).
pub open spec fn min_tok(st: Stats, q: Seq<Tok>) -> Option<Tok> decreases q.len() {
    if q.len() == 0 { None } else {
        let r = min_tok(st, q.drop_last());
        let t = q.last();
        if !known(st, t) { r } else {
            match r { None => Some(t), Some(m) => if (st.df)(t) < (st.df)(m) { Some(t) } else { Some(m) } }
        }
    }
}
/// Skipped: over the cutoff, except the fallback term when all known terms are over it.
pub open spec fn skipped(st: Stats, q: Seq<Tok>, fnum: int, fden: int, t: Tok) -> bool {
    over(st, t, fnum, fden) && !(all_over(st, q, fnum, fden) && min_tok(st, q) == Some(t))
}
/// The term occurrences that score: known and not skipped, each occurrence kept.
pub open spec fn scored(st: Stats, q: Seq<Tok>, fnum: int, fden: int, rest: Seq<Tok>) -> Seq<Tok> decreases rest.len() {
    if rest.len() == 0 { Seq::empty() } else {
        let r = scored(st, q, fnum, fden, rest.drop_last());
        let t = rest.last();
        if known(st, t) && !skipped(st, q, fnum, fden, t) { r.push(t) } else { r }
    }
}

// =============================================================== the score, as exact rationals
/// A non-negative rational num / den, den > 0.
pub struct Q { pub num: int, pub den: int }
pub open spec fn qz() -> Q { Q { num: 0, den: 1 } }
pub open spec fn qadd(a: Q, b: Q) -> Q { Q { num: a.num * b.den + b.num * a.den, den: a.den * b.den } }
pub open spec fn qlt(a: Q, b: Q) -> bool { a.num * b.den < b.num * a.den }
pub open spec fn qeq(a: Q, b: Q) -> bool { a.num * b.den == b.num * a.den }

/// tf * (k1 + 1) / (tf + k1 * (1 - b + b * len / avgdl)) with k1 = 3/2, b = 3/4, avgdl = total / n, multiplied out:
/// 20 tf T / (8 tf T + 3 T + 9 len n). SearchCore's parenthesised denominator (the 4.2.0 fix) is this value.
pub open spec fn tfpart(tf: int, len: int, total: int, n: int) -> Q {
    Q { num: 20 * tf * total, den: 8 * tf * total + 3 * total + 9 * len * n }
}
/// The IDF argument 1 + (N - df + 0.5) / (df + 0.5) = (2N + 2) / (2df + 1); IDF = ln of it (premise P-LN).
pub open spec fn idf_arg(n: int, df: int) -> Q { Q { num: 2 * n + 2, den: 2 * df + 1 } }

/// The weight one occurrence of a term adds to a document is idf(t) * tfpart; the idf is an input `w` per term
/// (ln of idf_arg under P-LN), and the factor `tfpart` is computed. A document outside the posting list gets nothing.
pub open spec fn occ(st: Stats, idf: spec_fn(Tok) -> Q, t: Tok, d: int) -> Q {
    if (st.tf)(t, d) > 0 {
        let a = idf(t); let f = tfpart((st.tf)(t, d), (st.len)(d), st.total, st.n);
        Q { num: a.num * f.num, den: a.den * f.den }
    } else { qz() }
}
pub open spec fn score(st: Stats, idf: spec_fn(Tok) -> Q, ts: Seq<Tok>, d: int) -> Q decreases ts.len() {
    if ts.len() == 0 { qz() } else { qadd(score(st, idf, ts.drop_last(), d), occ(st, idf, ts.last(), d)) }
}

// =============================================================== ranking
/// The order of the answer: a higher 12-decimal key first, then the lower document id. (Each (key, id) pair is a
/// distinct subscript, so no document is lost to a tie.)
pub open spec fn before(ka: int, a: int, kb: int, b: int) -> bool { ka > kb || (ka == kb && a < b) }

// =============================================================== schema 1 vs schema 2
/// The IDF argument a search uses: schema 2 from the statistics read now; schema 1 the argument Build stored.
pub open spec fn used_arg(schema: int, st: Stats, stored: spec_fn(Tok) -> Q, t: Tok) -> Q {
    if schema >= 2 { idf_arg(st.n, (st.df)(t)) } else { stored(t) }
}

// =============================================================== bm25_search's `_parse` (F-C0715)
pub open spec fn is_digit(c: char) -> bool { '0' <= c && c <= '9' }
pub open spec fn lead(c: char) -> bool { c == ':' || c == '[' || c == ',' }
/// re.sub(r'(?<=[:\[,])(\.\d)', r'0\1', raw), position by position: "0" goes before a '.' that follows ':', '[' or ','
/// and precedes a digit. `prev` is the character before s (a quote for an id inside the JSON answer).
pub open spec fn patch(prev: char, s: Seq<char>) -> Seq<char> decreases s.len() {
    if s.len() == 0 { s } else {
        let c = s[0];
        let ins = c == '.' && lead(prev) && s.len() > 1 && is_digit(s[1]);
        (if ins { seq!['0', c] } else { seq![c] }) + patch(c, s.drop_first())
    }
}

// =============================================================== theorems: terms
proof fn lemma_kept_len(stop: spec_fn(Tok) -> bool, raw: Seq<Tok>)
    ensures kept(stop, raw).len() <= raw.len(),
    decreases raw.len(),
{ if raw.len() > 0 { lemma_kept_len(stop, raw.drop_last()); } }

/// A query of stopwords only keeps no token, so SearchCore answers [] before reading any posting list.
pub proof fn theorem_stopword_query_empty(stop: spec_fn(Tok) -> bool, raw: Seq<Tok>)
    requires forall|i: int| 0 <= i < raw.len() ==> stop(#[trigger] raw[i]),
    ensures kept(stop, raw).len() == 0,
    decreases raw.len(),
{
    if raw.len() > 0 {
        assert forall|i: int| 0 <= i < raw.drop_last().len() implies stop(#[trigger] raw.drop_last()[i]) by { assert(raw.drop_last()[i] == raw[i]); }
        theorem_stopword_query_empty(stop, raw.drop_last());
        assert(stop(raw.last()));
    }
}

/// A non-stopword is kept each time it occurs: appending it to the query appends it to the kept tokens.
pub proof fn theorem_repeat_kept(stop: spec_fn(Tok) -> bool, raw: Seq<Tok>, t: Tok)
    requires !stop(t),
    ensures kept(stop, raw.push(t)) == kept(stop, raw).push(t), kept(stop, raw.push(t).push(t)) == kept(stop, raw).push(t).push(t),
{
    assert(raw.push(t).drop_last() =~= raw);
    assert(raw.push(t).push(t).drop_last() =~= raw.push(t));
}

/// With the cutoff off (f = 0) every known term occurrence scores, unknown ones never do.
pub proof fn theorem_cutoff_off_scores_known(st: Stats, q: Seq<Tok>, rest: Seq<Tok>)
    ensures scored(st, q, 0, 1, rest) =~= rest.filter(|t: Tok| (st.df)(t) > 0),
    decreases rest.len(),
{
    reveal(Seq::filter);
    if rest.len() > 0 {
        theorem_cutoff_off_scores_known(st, q, rest.drop_last());
        assert(!over(st, rest.last(), 0, 1));
    }
}

/// The cutoff skips a known term over it while another known query term is under it (B1f: `graph` 3/6 > 0.4 skipped,
/// `things` kept).
pub proof fn theorem_cutoff_skips_common_term(st: Stats, q: Seq<Tok>, fnum: int, fden: int, t: Tok, u: Tok)
    requires q.contains(u), known(st, u), !over(st, u, fnum, fden), over(st, t, fnum, fden),
    ensures skipped(st, q, fnum, fden, t), !skipped(st, q, fnum, fden, u),
{
    let j = choose|j: int| 0 <= j < q.len() && q[j] == u;
    assert(!all_over(st, q, fnum, fden)) by { assert(known(st, q[j]) && !over(st, q[j], fnum, fden)); }
}

proof fn lemma_min_tok_known(st: Stats, q: Seq<Tok>)
    ensures
        match min_tok(st, q) { Some(m) => known(st, m) && q.contains(m), None => forall|i: int| 0 <= i < q.len() ==> !known(st, #[trigger] q[i]) },
    decreases q.len(),
{
    if q.len() > 0 {
        lemma_min_tok_known(st, q.drop_last());
        match min_tok(st, q.drop_last()) {
            Some(m) => { let j = choose|j: int| 0 <= j < q.drop_last().len() && q.drop_last()[j] == m; assert(q[j] == m); assert(q[q.len() - 1] == q.last()); }
            None => {
                assert forall|i: int| 0 <= i < q.len() && i < q.len() - 1 implies !known(st, #[trigger] q[i]) by { assert(q.drop_last()[i] == q[i]); }
                assert(q[q.len() - 1] == q.last());
            }
        }
    }
}

/// When every known query term is over the cutoff, the lowest-df one still scores (B1g: the fallback), and it is a
/// known query term; a query whose terms are all unknown keeps none.
pub proof fn theorem_fallback_keeps_lowest_df(st: Stats, q: Seq<Tok>, fnum: int, fden: int)
    requires all_over(st, q, fnum, fden), exists|i: int| 0 <= i < q.len() && (st.df)(#[trigger] q[i]) > 0,
    ensures
        min_tok(st, q).is_some(),
        (st.df)(min_tok(st, q).unwrap()) > 0,
        !skipped(st, q, fnum, fden, min_tok(st, q).unwrap()),
{
    lemma_min_tok_known(st, q);
    let i = choose|i: int| 0 <= i < q.len() && (st.df)(#[trigger] q[i]) > 0;
    if min_tok(st, q).is_none() { assert(!known(st, q[i])); }
}

/// An unknown query term does not block the fallback: `zzz graph` with every known term over the cutoff still scores
/// `graph` (an unknown term is neither skipped nor the term kept).
pub proof fn theorem_fallback_ignores_unknown_terms(st: Stats, u: Tok, t: Tok, fnum: int, fden: int)
    requires (st.df)(u) == 0, (st.df)(t) > 0, over(st, t, fnum, fden),
    ensures !skipped(st, seq![u, t], fnum, fden, t),
{
    let q = seq![u, t];
    assert(q.drop_last() =~= seq![u]);
    assert(seq![u].drop_last() =~= Seq::<Tok>::empty());
    assert(min_tok(st, Seq::<Tok>::empty()) == None::<Tok>);
    assert(seq![u].last() == u);
    assert(!known(st, u));
    assert(min_tok(st, seq![u]) == min_tok(st, seq![u].drop_last()));
    assert(min_tok(st, seq![u]) == None::<Tok>);
    assert(q.last() == t);
    assert(min_tok(st, q) == Some(t));
    assert forall|i: int| 0 <= i < q.len() && known(st, #[trigger] q[i]) implies over(st, q[i], fnum, fden) by {
        if i == 0 { assert(q[0] == u); } else { assert(q[1] == t); }
    }
}

// =============================================================== theorems: score
/// A term the query repeats counts each time: the score of q + [t, t] is the score of q plus the occurrence twice.
pub proof fn theorem_repeat_adds_twice(st: Stats, idf: spec_fn(Tok) -> Q, ts: Seq<Tok>, t: Tok, d: int)
    ensures score(st, idf, ts.push(t).push(t), d) == qadd(qadd(score(st, idf, ts, d), occ(st, idf, t, d)), occ(st, idf, t, d)),
{
    assert(ts.push(t).push(t).drop_last() =~= ts.push(t));
    assert(ts.push(t).drop_last() =~= ts);
    assert(ts.push(t).push(t).last() == t);
    assert(ts.push(t).last() == t);
    assert(score(st, idf, ts.push(t), d) == qadd(score(st, idf, ts, d), occ(st, idf, t, d)));
    assert(score(st, idf, ts.push(t).push(t), d) == qadd(score(st, idf, ts.push(t), d), occ(st, idf, t, d)));
}

/// A term no document holds (df 0) is not scored, so the answer for `zzz graph` equals the answer for `graph` (B1h).
pub proof fn theorem_unknown_term_adds_nothing(st: Stats, q: Seq<Tok>, rest: Seq<Tok>, t: Tok, fnum: int, fden: int)
    requires (st.df)(t) == 0,
    ensures scored(st, q, fnum, fden, rest.push(t)) == scored(st, q, fnum, fden, rest),
{ assert(rest.push(t).drop_last() =~= rest); }

/// Length normalization (general): for the same tf in an index with T > 0, N > 0, a shorter document gets the larger
/// factor (USER_GUIDE: Bob's shorter bio scores higher).
pub proof fn theorem_shorter_document_scores_higher(tf: int, l1: int, l2: int, total: int, n: int)
    requires tf > 0, 0 < l1 < l2, total > 0, n > 0,
    ensures qlt(tfpart(tf, l2, total, n), tfpart(tf, l1, total, n)),
{
    let a = 20 * tf * total;
    let d1 = 8 * tf * total + 3 * total + 9 * l1 * n;
    let d2 = 8 * tf * total + 3 * total + 9 * l2 * n;
    assert(a > 0) by (nonlinear_arith) requires tf > 0, total > 0, a == 20 * tf * total;
    assert(d1 < d2) by (nonlinear_arith) requires l1 < l2, n > 0, d1 == 8 * tf * total + 3 * total + 9 * l1 * n, d2 == 8 * tf * total + 3 * total + 9 * l2 * n;
    assert(a * d1 < a * d2) by (nonlinear_arith) requires a > 0, d1 < d2;
}

/// More occurrences in the same document length give a larger factor, and the factor stays below k1 + 1 = 5/2
/// (saturation).
pub proof fn theorem_tf_raises_and_saturates(t1: int, t2: int, len: int, total: int, n: int)
    requires 0 < t1 < t2, len > 0, total > 0, n > 0,
    ensures qlt(tfpart(t1, len, total, n), tfpart(t2, len, total, n)), qlt(tfpart(t2, len, total, n), Q { num: 5, den: 2 }),
{
    let c = 3 * total + 9 * len * n;
    assert(c > 0) by (nonlinear_arith) requires total > 0, len > 0, n > 0, c == 3 * total + 9 * len * n;
    assert((20 * t1 * total) * (8 * t2 * total + c) < (20 * t2 * total) * (8 * t1 * total + c)) by (nonlinear_arith)
        requires t1 < t2, total > 0, c > 0;
    assert((20 * t2 * total) * 2 < 5 * (8 * t2 * total + c)) by (nonlinear_arith) requires c > 0;
}

/// The USER_GUIDE worked example: `beta` in "alpha beta beta" (tf 2, len 3) of an index with N 3, total 8: the factor
/// is 320/233 and the IDF argument 8/3 (ln 8/3 * 320/233 = 1.347).
pub proof fn theorem_worked_example()
    ensures tfpart(2, 3, 8, 3) == (Q { num: 320, den: 233 }), idf_arg(3, 1) == (Q { num: 8, den: 3 }),
{}

/// The IDF argument is above 1 for every df <= N, so (P-LN) every known term adds a positive weight, and it falls as
/// df rises: a rarer term weighs more.
pub proof fn theorem_idf_arg_positive_and_decreasing(n: int, d1: int, d2: int)
    requires 0 < d1 < d2 <= n,
    ensures qlt(Q { num: 1, den: 1 }, idf_arg(n, d2)), qlt(idf_arg(n, d2), idf_arg(n, d1)),
{
    assert((2 * n + 2) * (2 * d1 + 1) < (2 * n + 2) * (2 * d2 + 1)) by (nonlinear_arith) requires d1 < d2, n > 0;
}

// =============================================================== theorems: ranking, statistics, reader
/// The answer order is a strict total order on distinct documents: equal keys are ordered by id, so every tied
/// document keeps its place (B1e: d2, d5, d6 at one score; k 2 answers d2 and d5).
pub proof fn theorem_ties_by_id(ka: int, a: int, kb: int, b: int)
    requires a != b,
    ensures before(ka, a, kb, b) || before(kb, b, ka, a), !(before(ka, a, kb, b) && before(kb, b, ka, a)),
            ka == kb ==> (before(ka, a, kb, b) <==> a < b),
{}

/// Query-time IDF (search.bm25.query_time_idf): on schema 2 the IDF argument comes from the statistics read now, so
/// two indexes with the same N and df answer with the same IDF whatever was stored at build (B2a: an incremental
/// insert and a fresh build agree); on schema 1 the stored value decides.
pub proof fn theorem_schema2_reads_current_stats(st: Stats, s1: spec_fn(Tok) -> Q, s2: spec_fn(Tok) -> Q, t: Tok)
    ensures used_arg(2, st, s1, t) == used_arg(2, st, s2, t), used_arg(2, st, s1, t) == idf_arg(st.n, (st.df)(t)),
{}
/// Neighbor (schema 1): a stored IDF argument from an older N is what the search uses.
pub proof fn theorem_schema1_reads_stored(st: Stats, stored: spec_fn(Tok) -> Q, t: Tok)
    ensures used_arg(1, st, stored, t) == stored(t),
{}

proof fn lemma_patch_no_dot(prev: char, s: Seq<char>)
    requires forall|i: int| 0 <= i < s.len() ==> #[trigger] s[i] != '.',
    ensures patch(prev, s) == s,
    decreases s.len(),
{
    if s.len() > 0 {
        assert forall|i: int| 0 <= i < s.drop_first().len() implies #[trigger] s.drop_first()[i] != '.' by { assert(s.drop_first()[i] == s[i + 1]); }
        lemma_patch_no_dot(s[0], s.drop_first());
        assert(seq![s[0]] + s.drop_first() =~= s);
    }
}
/// F-C0715 (inherited, general neighbor): bm25_search returns an id without a '.' unchanged.
pub proof fn theorem_id_without_dot_kept(s: Seq<char>)
    requires forall|i: int| 0 <= i < s.len() ==> #[trigger] s[i] != '.',
    ensures patch('"', s) == s,
{ lemma_patch_no_dot('"', s); }
/// F-C0715: an id holding ":.5" comes back from bm25_search as ":0.5" (observed: "c:.5x" -> "c:0.5x"), while
/// CALL ivg.bm25.search reads the raw answer unchanged.
pub proof fn theorem_id_with_colon_dot_digit_rewritten()
    ensures patch('"', seq!['c', ':', '.', '5', 'x']) == seq!['c', ':', '0', '.', '5', 'x'],
            patch('"', seq!['c', ':', '.', '5', 'x']) != seq!['c', ':', '.', '5', 'x'],
{
    let s = seq!['c', ':', '.', '5', 'x'];
    assert(s.drop_first() =~= seq![':', '.', '5', 'x']);
    assert(seq![':', '.', '5', 'x'].drop_first() =~= seq!['.', '5', 'x']);
    assert(seq!['.', '5', 'x'].drop_first() =~= seq!['5', 'x']);
    assert(seq!['5', 'x'].drop_first() =~= seq!['x']);
    assert(seq!['x'].drop_first() =~= Seq::<char>::empty());
    assert(patch('x', Seq::<char>::empty()) =~= Seq::<char>::empty());
    assert(seq!['x'][0] == 'x');
    assert(patch('5', seq!['x']) =~= seq!['x'] + patch('x', Seq::<char>::empty()));
    assert(patch('5', seq!['x']) =~= seq!['x']);
    assert(patch('.', seq!['5', 'x']) =~= seq!['5', 'x']);
    assert(patch(':', seq!['.', '5', 'x']) =~= seq!['0', '.', '5', 'x']);
    assert(patch('c', seq![':', '.', '5', 'x']) =~= seq![':', '0', '.', '5', 'x']);
    assert(patch('"', s) =~= seq!['c', ':', '0', '.', '5', 'x']);
    assert(patch('"', s).len() == 6);
}

} // verus!
