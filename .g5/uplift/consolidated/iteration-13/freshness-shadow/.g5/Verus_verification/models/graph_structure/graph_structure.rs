// IVG graph scope and structural storage — Verus model (initial uplift, worker B-structure, 2026-11-13).
//
// Product baseline 3eaa79cf. This file is a model and a transcription of the product's ObjectScript
// and Python; it does not verify those bodies. Each L2 operation names the product lines it
// transcribes; NOTES.md holds the binding table, premises, trust inventory and findings.
//
// Sections
//   §1  graph keys: GraphKey.Validate / ForIndex / ForLedger / ForName (O1; ADR-0001, ADR-0003)
//   §2  degree served from a generation-validated cache (O3; ADR-0010, ADR-0012; F2)
//   §3  parallel edges: the keyed adjacency layout and LedgerApply.DeleteRelInternal (O5; spec 234,
//       spec 252; F3)
//   §4  the algorithm-cache token rule (O4; CONTEXT.md Graph-Version Token; F1)
//
// Layers: L1 rules are stated independently of the code (layout, served == recount, injective keys,
// cache answer == answer over current content); L2 transcribes the as-built mechanism with its
// commit/rollback boundaries; theorems prove L2 implements L1 under named premises, witnesses are
// concrete traces where it does not, and the repaired variants are proved where a repair is proposed.
//
// Run:  $VERUS_BIN graph_structure.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;

verus! {

// ============================================================================ §1 graph keys (O1)

pub type Name = Seq<char>;

/// IRIS's $ZStrip(x, "*C") control class. PREMISE P-CTRL (IRIS behaviour, not verified here): C0
/// controls 0..31, DEL 127 and the C1 range 128..159. Every proof in §1 uses only that '\u{1}' and
/// '\u{0}' are in the class and '0' is not; the C1 range matters only to the Python-mirror witness.
pub open spec fn is_ctrl(c: char) -> bool {
    (c as u32) < 32 || (127 <= (c as u32) && (c as u32) <= 159)
}

/// _validate.validate_graph_name's control test: ord(c) < 32 or ord(c) == 127 (_validate.py:47).
pub open spec fn py_ctrl(c: char) -> bool {
    (c as u32) < 32 || (c as u32) == 127
}

pub open spec fn contains_ctrl(s: Seq<char>) -> bool {
    exists|i: int| 0 <= i < s.len() && is_ctrl(#[trigger] s[i])
}

pub open spec fn py_contains_ctrl(s: Seq<char>) -> bool {
    exists|i: int| 0 <= i < s.len() && py_ctrl(#[trigger] s[i])
}

/// GraphKey.Canonical: $Translate(pGraph, $Char(0), "") (GraphKey.cls:82-85) — every NUL removed.
pub open spec fn strip_nul(n: Seq<char>) -> Seq<char>
    decreases n.len(),
{
    if n.len() == 0 {
        n
    } else {
        let r = strip_nul(n.drop_last());
        if n.last() == '\0' { r } else { r.push(n.last()) }
    }
}

pub open spec fn canonical(n: Name) -> Name {
    strip_nul(n)
}

/// L1 normalization (GraphKey.cls:34-37, ADR-0003, _validate.py:31-32): $Char(0) is a transport artifact
/// of IRIS SQL and is the ONLY character removed; every other character is part of the name. Stated with
/// vstd's Seq::filter, independently of the transcription `strip_nul`, so a canonicalization that
/// removes more (ADR-0003's table wording `$ZStrip(graphId, "*C")`) is detected (review R1-4, Check A).
pub open spec fn nul_free(n: Name) -> Name {
    n.filter(|c: char| c != '\0')
}

/// L1: two names denote the same graph exactly when they differ only by NUL characters.
pub open spec fn l1_same_graph(n1: Name, n2: Name) -> bool {
    nul_free(n1) == nul_free(n2)
}

pub open spec fn zero_name() -> Name { seq!['0'] }

pub open spec fn ledger_default_text() -> Seq<char> { seq!['\u{1}'] }

/// GraphKey.Validate (GraphKey.cls:38-48): canonicalize, refuse "0", refuse any control character.
pub open spec fn valid(n: Name) -> bool {
    let c = canonical(n);
    &&& c != zero_name()
    &&& !contains_ctrl(c)
}

/// _validate.validate_graph_name (_validate.py:19-53): the Python mirror.
pub open spec fn py_valid(n: Name) -> bool {
    let c = canonical(n);
    &&& c != zero_name()
    &&& !py_contains_ctrl(c)
}

// ---------------------------------------------------------------------------- IRIS subscripts

/// An IRIS global subscript. A string that is a canonical number IS that number as a subscript
/// (ADR-0003:42-48): ^KG("out","0",...) and ^KG("out",0,...) are the same node. `Num` carries the
/// canonical text of the number; PREMISE P-CANON: canonical numeric text is unique per number
/// (two different canonical strings are different numbers), which is what "canonical" means.
pub enum Sub {
    Num(Seq<char>),
    Str(Seq<char>),
}

/// Which strings other than "0" are canonical numbers ("1", "-1", ".5", ...): left abstract, so
/// every result below holds for any such set. Trust inventory: uninterp, no axiom.
pub uninterp spec fn other_canonical_number(s: Seq<char>) -> bool;

pub open spec fn canonical_number(s: Seq<char>) -> bool {
    s == zero_name() || other_canonical_number(s)
}

/// A string used as a subscript.
pub open spec fn sub_of(s: Seq<char>) -> Sub {
    if canonical_number(s) { Sub::Num(s) } else { Sub::Str(s) }
}

/// The integer 0 used as a subscript (ForIndex's default-graph key).
pub open spec fn int_zero() -> Sub { Sub::Num(zero_name()) }

// ---------------------------------------------------------------------------- the derivations (L2)

/// GraphKey.ForIndex (GraphKey.cls:51-56): None = $$$ThrowOnError (refused before any write).
pub open spec fn for_index(n: Name) -> Option<Sub> {
    if !valid(n) {
        None
    } else if canonical(n).len() == 0 {
        Some(int_zero())
    } else {
        Some(sub_of(canonical(n)))
    }
}

/// GraphKey.ForLedger (GraphKey.cls:72-77): the default graph is $Char(1).
pub open spec fn for_ledger(n: Name) -> Option<Sub> {
    if !valid(n) {
        None
    } else if canonical(n).len() == 0 {
        Some(sub_of(ledger_default_text()))
    } else {
        Some(sub_of(canonical(n)))
    }
}

/// GraphKey.ForName (GraphKey.cls:65-69): the SQL graph_id spelling ('' = default graph).
pub open spec fn for_name(n: Name) -> Option<Name> {
    if !valid(n) { None } else { Some(canonical(n)) }
}

// ---------------------------------------------------------------------------- canonicalization lemmas

pub proof fn lemma_strip_nul_add(a: Seq<char>, b: Seq<char>)
    ensures
        strip_nul(a + b) == strip_nul(a) + strip_nul(b),
    decreases b.len(),
{
    if b.len() == 0 {
        assert(a + b =~= a);
        assert(strip_nul(b) =~= Seq::<char>::empty());
        assert(strip_nul(a) + strip_nul(b) =~= strip_nul(a));
    } else {
        let ab = a + b;
        assert(ab.drop_last() =~= a + b.drop_last());
        assert(ab.last() == b.last());
        lemma_strip_nul_add(a, b.drop_last());
        if b.last() == '\0' {
        } else {
            assert(strip_nul(a) + strip_nul(b.drop_last()).push(b.last())
                =~= (strip_nul(a) + strip_nul(b.drop_last())).push(b.last()));
        }
    }
}

pub proof fn lemma_strip_nul_single(c: char)
    ensures
        strip_nul(seq![c]) == (if c == '\0' { Seq::<char>::empty() } else { seq![c] }),
{
    let s = seq![c];
    assert(s.drop_last() =~= Seq::<char>::empty());
    assert(strip_nul(s.drop_last()) =~= Seq::<char>::empty());
    if c != '\0' {
        assert(Seq::<char>::empty().push(c) =~= seq![c]);
    }
}

/// Canonical removes NUL wherever it stands.
pub proof fn lemma_strip_nul_insert(a: Seq<char>, b: Seq<char>)
    ensures
        strip_nul(a + seq!['\0'] + b) == strip_nul(a + b),
{
    lemma_strip_nul_add(a + seq!['\0'], b);
    lemma_strip_nul_add(a, seq!['\0']);
    lemma_strip_nul_single('\0');
    lemma_strip_nul_add(a, b);
    assert(strip_nul(a) + Seq::<char>::empty() =~= strip_nul(a));
}

/// The transcription's canonicalization is exactly the L1 normalization (NUL removed, nothing else).
pub proof fn lemma_canonical_is_nul_free(n: Name)
    ensures
        canonical(n) == nul_free(n),
    decreases n.len(),
{
    reveal(Seq::filter);
    if n.len() > 0 {
        lemma_canonical_is_nul_free(n.drop_last());
    }
}

pub proof fn lemma_sub_of_injective(s1: Seq<char>, s2: Seq<char>)
    ensures
        sub_of(s1) == sub_of(s2) ==> s1 == s2,
{
}

pub proof fn lemma_ctrl_one()
    ensures
        contains_ctrl(ledger_default_text()),
        !contains_ctrl(zero_name()),
        canonical(zero_name()) == zero_name(),
        canonical(ledger_default_text()) == ledger_default_text(),
{
    assert(is_ctrl(ledger_default_text()[0]));
    lemma_strip_nul_single('0');
    lemma_strip_nul_single('\u{1}');
    assert(!is_ctrl('0'));
}

// ---------------------------------------------------------------------------- L1 obligations, proved

/// O1(a) — each derivation is a function of the graph (the canonical name): two spellings of one
/// graph (NUL padding) get one key in every store.
pub proof fn theorem_key_is_function_of_graph(n1: Name, n2: Name)
    requires
        canonical(n1) == canonical(n2),
    ensures
        for_index(n1) == for_index(n2),
        for_ledger(n1) == for_ledger(n2),
        for_name(n1) == for_name(n2),
{
}

/// O1(b) — NUL is stripped, wherever it stands; the name made of NUL is the default graph.
pub proof fn theorem_nul_is_stripped(a: Name, b: Name)
    ensures
        for_index(a + seq!['\0'] + b) == for_index(a + b),
        for_ledger(a + seq!['\0'] + b) == for_ledger(a + b),
        for_index(seq!['\0']) == Some(int_zero()),
        for_index(seq!['\0']) == for_index(Seq::<char>::empty()),
{
    lemma_strip_nul_insert(a, b);
    lemma_strip_nul_single('\0');
    assert(strip_nul(Seq::<char>::empty()) =~= Seq::<char>::empty());
    assert(!contains_ctrl(Seq::<char>::empty()));
    assert(Seq::<char>::empty() != zero_name()) by { assert(zero_name().len() == 1); }
}

/// O1(c) — the reserved name "0" and every control character are refused (before any write: the
/// derivation throws). $Char(1), the ledger's own sentinel, is the case ADR-0003 names.
pub proof fn theorem_refusals(n: Name)
    ensures
        for_index(zero_name()) is None,
        for_ledger(zero_name()) is None,
        for_name(zero_name()) is None,
        for_index(ledger_default_text()) is None,
        for_ledger(ledger_default_text()) is None,
        contains_ctrl(canonical(n)) ==> for_index(n) is None && for_ledger(n) is None && for_name(n) is None,
        canonical(n) == zero_name() ==> for_index(n) is None && for_ledger(n) is None,
{
    lemma_ctrl_one();
}

/// O1(d) — ForIndex is injective on graphs: one ^KG key never names two graphs.
pub proof fn theorem_index_key_injective(n1: Name, n2: Name)
    requires
        for_index(n1) is Some,
        for_index(n1) == for_index(n2),
    ensures
        canonical(n1) == canonical(n2),
        l1_same_graph(n1, n2),
{
    lemma_canonical_is_nul_free(n1);
    lemma_canonical_is_nul_free(n2);
    let c1 = canonical(n1);
    let c2 = canonical(n2);
    if c1.len() == 0 && c2.len() != 0 {
        // int_zero() == sub_of(c2) forces c2 == "0", which valid() refused
        lemma_sub_of_injective(zero_name(), c2);
        assert(sub_of(zero_name()) == int_zero());
    } else if c1.len() != 0 && c2.len() == 0 {
        lemma_sub_of_injective(zero_name(), c1);
        assert(sub_of(zero_name()) == int_zero());
    } else if c1.len() != 0 && c2.len() != 0 {
        lemma_sub_of_injective(c1, c2);
    } else {
        assert(c1 =~= c2);
    }
}

/// O1(d) — ForLedger is injective on graphs.
pub proof fn theorem_ledger_key_injective(n1: Name, n2: Name)
    requires
        for_ledger(n1) is Some,
        for_ledger(n1) == for_ledger(n2),
    ensures
        canonical(n1) == canonical(n2),
        l1_same_graph(n1, n2),
{
    lemma_canonical_is_nul_free(n1);
    lemma_canonical_is_nul_free(n2);
    let c1 = canonical(n1);
    let c2 = canonical(n2);
    lemma_ctrl_one();
    if c1.len() == 0 && c2.len() != 0 {
        lemma_sub_of_injective(ledger_default_text(), c2);
        // c2 == $Char(1) would contain a control character
        assert(c2 == ledger_default_text() ==> contains_ctrl(c2));
    } else if c1.len() != 0 && c2.len() == 0 {
        lemma_sub_of_injective(ledger_default_text(), c1);
        assert(c1 == ledger_default_text() ==> contains_ctrl(c1));
    } else if c1.len() != 0 && c2.len() != 0 {
        lemma_sub_of_injective(c1, c2);
    } else {
        assert(c1 =~= c2);
    }
}

/// O1(d) — ForName is injective on graphs (trivially: it is the canonical name).
pub proof fn theorem_name_injective(n1: Name, n2: Name)
    requires
        for_name(n1) is Some,
        for_name(n1) == for_name(n2),
    ensures
        canonical(n1) == canonical(n2),
        l1_same_graph(n1, n2),
{
    lemma_canonical_is_nul_free(n1);
    lemma_canonical_is_nul_free(n2);
}

/// O1(e) — the default graph's key differs from every named graph's key, in both stores.
pub proof fn theorem_default_key_is_unique(n: Name)
    requires
        valid(n),
        canonical(n).len() > 0,
    ensures
        for_index(n) != for_index(Seq::<char>::empty()),
        for_ledger(n) != for_ledger(Seq::<char>::empty()),
{
    assert(strip_nul(Seq::<char>::empty()) =~= Seq::<char>::empty());
    assert(!contains_ctrl(Seq::<char>::empty()));
    assert(Seq::<char>::empty() != zero_name()) by { assert(zero_name().len() == 1); }
    if for_index(n) == for_index(Seq::<char>::empty()) {
        theorem_index_key_injective(Seq::<char>::empty(), n);
    }
    if for_ledger(n) == for_ledger(Seq::<char>::empty()) {
        theorem_ledger_key_injective(Seq::<char>::empty(), n);
    }
}

/// O1(f) — ADR-0003 / CONTEXT.md:57-58: a key of one store used on the other never reads ANOTHER
/// graph's data. A ledger key equals an index key only for the same named graph (where both forms
/// are the name); the default graph's key in either store matches no key of the other store, so a
/// default-graph lookup with the wrong form reads nothing (the OpCreateRel defect ADR-0003 records:
/// edges written at ^KG("out", $Char(1), ...) where no reader walks).
pub proof fn theorem_cross_store_key_reads_nothing_foreign(n1: Name, n2: Name)
    requires
        for_index(n1) is Some,
        for_ledger(n2) is Some,
        for_index(n1) == for_ledger(n2),
    ensures
        canonical(n1) == canonical(n2),
        l1_same_graph(n1, n2),
        canonical(n1).len() > 0,
{
    lemma_canonical_is_nul_free(n1);
    lemma_canonical_is_nul_free(n2);
    let c1 = canonical(n1);
    let c2 = canonical(n2);
    lemma_ctrl_one();
    assert(sub_of(zero_name()) == int_zero());
    if c1.len() == 0 {
        if c2.len() == 0 {
            // int 0 vs $Char(1)
            lemma_sub_of_injective(zero_name(), ledger_default_text());
            assert(zero_name()[0] != ledger_default_text()[0]);
        } else {
            lemma_sub_of_injective(zero_name(), c2);
        }
    } else {
        if c2.len() == 0 {
            lemma_sub_of_injective(c1, ledger_default_text());
            assert(c1 == ledger_default_text() ==> contains_ctrl(c1));
        } else {
            lemma_sub_of_injective(c1, c2);
        }
    }
}

/// Corollary used by the consumers: the default graph's index key is never a ledger key and its
/// ledger key is never an index key.
pub proof fn theorem_default_keys_never_cross(n: Name)
    requires
        valid(n),
    ensures
        for_index(Seq::<char>::empty()) != for_ledger(n),
        for_ledger(Seq::<char>::empty()) != for_index(n),
{
    assert(strip_nul(Seq::<char>::empty()) =~= Seq::<char>::empty());
    assert(!contains_ctrl(Seq::<char>::empty()));
    assert(Seq::<char>::empty() != zero_name()) by { assert(zero_name().len() == 1); }
    if for_index(Seq::<char>::empty()) == for_ledger(n) {
        theorem_cross_store_key_reads_nothing_foreign(Seq::<char>::empty(), n);
    }
    if for_ledger(Seq::<char>::empty()) == for_index(n) {
        theorem_cross_store_key_reads_nothing_foreign(n, Seq::<char>::empty());
    }
}

/// O1(g), concrete and independent of `canonical`'s proof: a name that differs from "a" by a control
/// character other than NUL is never given "a"'s key — it is refused (as built) rather than merged. A
/// normalization that strips controls (ADR-0003:14's table wording) merges them and fails here.
pub proof fn theorem_control_names_never_merge() {
    let a: Name = seq!['a'];
    let a1: Name = seq!['a', '\u{1}'];
    let a85: Name = seq!['a', '\u{85}'];
    reveal_with_fuel(strip_nul, 3);
    assert(canonical(a) =~= a);
    assert(!contains_ctrl(a)) by {
        assert forall|i: int| 0 <= i < a.len() implies !is_ctrl(#[trigger] a[i]) by { assert(i == 0); }
    }
    assert(a != zero_name()) by { assert(a[0] != zero_name()[0]); }
    assert(for_index(a) is Some && for_ledger(a) is Some);
    if valid(a1) {
        assert(canonical(a1) =~= a1);
        assert(is_ctrl(a1[1]));
        assert(contains_ctrl(canonical(a1)));
    }
    if valid(a85) {
        assert(canonical(a85) =~= a85);
        assert(is_ctrl(a85[1]));
        assert(contains_ctrl(canonical(a85)));
    }
    assert(for_index(a1) != for_index(a));
    assert(for_ledger(a1) != for_ledger(a));
    assert(for_index(a85) != for_index(a));
}

/// Witness (open question Q4): the Python mirror admits a name GraphKey refuses. Under P-CTRL,
/// "\u{85}" (NEL, a C1 control) passes validate_graph_name and then makes ForIndex throw inside
/// IRIS, possibly inside a functional-index callback; the two validators disagree.
pub proof fn witness_python_mirror_admits_c1_control() {
    let n: Name = seq!['\u{85}'];
    lemma_strip_nul_single('\u{85}');
    assert(canonical(n) == n);
    assert(is_ctrl(n[0]));
    assert(contains_ctrl(canonical(n)));
    assert(!py_ctrl(n[0]));
    assert(!py_contains_ctrl(canonical(n))) by {
        assert forall|i: int| 0 <= i < canonical(n).len() implies !py_ctrl(#[trigger] canonical(n)[i]) by {
            assert(i == 0);
        }
    }
    assert(n != zero_name()) by { assert(n[0] != zero_name()[0]); }
    assert(py_valid(n));
    assert(for_index(n) is None);
}

/// The SQL graph_id a writer binds for a caller's graph name (None = refused before any write).
///   as built, create_edge: `graph_index_key(graph)` validates (nodes_edges.py:1197), then the INSERT binds
///   `gid = graph or ""` — the RAW name (1213); the duplicate guard compares COALESCE(graph_id, '') with it.
///   The row's index callback then keys ^KG by ForIndex(row graph_id) (Adjacency.cls:482), the canonical name.
pub open spec fn sql_gid_create_edge(n: Name) -> Option<Name> {
    if !valid(n) { None } else { Some(n) }
}

/// Proposal: bind ForName(name) (GraphKey.cls:65-69), as Graph.KG.Eraser already does.
pub open spec fn sql_gid_repaired(n: Name) -> Option<Name> {
    for_name(n)
}

/// L1 (review R1-4; CONTEXT.md:27-36 "every ... edge belongs to exactly one graph"; ADR-0003 "both derive
/// from the name"): every store spells a graph by the same canonical name — a writer's SQL graph_id is
/// ForName(name) — so two names share an index key exactly when their rows share a SQL graph.
pub open spec fn binding_ok(n: Name, gid: Option<Name>) -> bool {
    gid == for_name(n)
}

pub proof fn theorem_repaired_binding_one_graph_in_every_store(n1: Name, n2: Name)
    requires
        valid(n1),
        valid(n2),
    ensures
        binding_ok(n1, sql_gid_repaired(n1)),
        (for_index(n1) == for_index(n2)) == (sql_gid_repaired(n1) == sql_gid_repaired(n2)),
{
    if for_index(n1) == for_index(n2) {
        theorem_index_key_injective(n1, n2);
    }
    if sql_gid_repaired(n1) == sql_gid_repaired(n2) {
        theorem_key_is_function_of_graph(n1, n2);
    }
}

/// Witness (R1-4 / Q5, OBSERVED natively: graph_structure_keys K4). "g" and "g" + NUL are one index graph
/// but two SQL graphs under create_edge's raw binding: binding_ok fails, and the duplicate guard admits a
/// second row whose index entry is the same node; delete_edge(graph="g") then kills the entry the
/// "g"+NUL row still needs, and verify_graph("g") cannot see that row (its predicate is the canonical name).
pub proof fn witness_raw_sql_name_splits_one_index_graph() {
    let g: Name = seq!['g'];
    let gp: Name = seq!['g', '\0'];
    lemma_strip_nul_insert(g, Seq::<char>::empty());
    assert(g + seq!['\0'] + Seq::<char>::empty() =~= gp);
    assert(g + Seq::<char>::empty() =~= g);
    theorem_nul_is_stripped(g, Seq::<char>::empty());
    assert(for_index(gp) == for_index(g));
    assert(gp != g) by { assert(gp.len() != g.len()); }
    assert(canonical(gp) == canonical(g));
    reveal_with_fuel(strip_nul, 2);
    assert(canonical(g) =~= g);
    assert(!contains_ctrl(g)) by {
        assert forall|i: int| 0 <= i < g.len() implies !is_ctrl(#[trigger] g[i]) by { assert(i == 0); }
    }
    assert(g != zero_name()) by { assert(g[0] != zero_name()[0]); }
    assert(valid(gp));
    assert(sql_gid_create_edge(gp) != sql_gid_create_edge(g));
    assert(!binding_ok(gp, sql_gid_create_edge(gp)));
}

// ============================================================================ §2 degree cache (O3)
//
// One graph g, one source s, the all-predicate key $Char(1) (a per-predicate key is the same
// protocol over a subset of the entries). Every other source is independent: gen and degc are per
// source and no step below reads another source's.

/// ^KG("degc", g, s, key) = $ListBuild(gen, count). `epoch` exists only in the repaired variant.
pub struct Entry {
    pub gen: nat,
    pub epoch: nat,
    pub n: int,
}

/// One writer transaction on s (a caller's WriteTxn level, Eraser's TSTART, a Ledger commit).
pub struct Wtx {
    /// the change this transaction made to the out entries of s, visible to every process now
    /// (IRIS globals are read-uncommitted) and taken back by its rollback
    pub delta: int,
    /// it has called an Adjacency writer (and so WriterLock)
    pub wrote: bool,
    /// it holds ^IVG.AdjW(g)#"S"; inside a transaction the unlock waits for commit/rollback
    pub locked: bool,
    /// journaled pre-images of a Kill it made (first one wins at rollback): ^KG("gen", g, s) and
    /// ^KG("degc", g, s, key). $Increment is never journaled for rollback.
    pub undo_gen: Option<nat>,
    pub undo_degc: Option<Option<Entry>>,
}

/// Adj.Degree's program counter after step 1 missed (Adj.cls:63-67).
pub enum Pc {
    /// gen read (63), probe next (68-72)
    Probe,
    /// count next (73)
    Count,
    /// the store test next (75)
    Check,
    /// the Set next (77)
    Set,
    /// the post-store re-read next (78-80)
    ReRead,
}

pub struct Rd {
    pub pc: Pc,
    pub tgen: nat,
    pub tepoch: nat,
    pub got: bool,
    pub n: int,
}

pub struct DS {
    /// what Adj.Count(g, s) answers now (Adj.cls:110-133, "#" multiplicity included)
    pub vis: int,
    /// +$Get(^KG("gen", g, s)): absent reads as 0
    pub gen: nat,
    /// repaired variant only: a counter that is never killed and only moves by $Increment
    pub epoch: nat,
    /// ^KG("__version"), used only by the intent notes' S1 variant (generations drawn from it)
    pub token: nat,
    pub degc: Option<Entry>,
    /// $Data(^IVG.AdjNoLock(g))
    pub nolock: bool,
    pub ws: Map<nat, Wtx>,
    pub rs: Map<nat, Rd>,
}

/// Switches. `probe`, `gen_check`, `nolock_check`, `bump` are the as-built mechanism (each is
/// removed by one control). `epoch_stamp` is the repair. `quiet_kills` is PREMISE P-QUIET (a
/// kill of s happens only while no Degree call on s is between its gen read and its end).
/// `kill_in_tx` enables a kill inside a transaction that may roll back (route 2).
pub struct DV {
    pub probe: bool,
    pub gen_check: bool,
    pub nolock_check: bool,
    pub bump: bool,
    pub epoch_stamp: bool,
    pub quiet_kills: bool,
    pub kill_in_tx: bool,
    /// intent notes' S1 as written: `Set ^KG("gen",g,s) = $Increment(^KG("__version"))` in place of
    /// `$Increment(^KG("gen",g,s))` — a Set, so a rollback restores the pre-image
    pub set_gen: bool,
    /// review Check B's repair: an erase $Increments ^KG("gen", g, s) (and kills degc) instead of killing
    /// gen, so a generation never repeats; $Increment is not undone by a rollback either
    pub kill_bumps: bool,
}

pub enum DA {
    /// TSTART of a writer (no lock yet: WriterLock is taken by the first Adjacency write)
    Begin { w: nat },
    /// one Adjacency write on s inside w: Put (Adjacency.cls:86-93), Remove (150-158), PutKeyed
    /// (233-262), RemoveKeyed (291-315), RowUpdate keyed (523-530, d = 0). WriterLock (61-73):
    /// shared lock in 5 s, else ^IVG.AdjNoLock(g) is $Incremented and the write goes on.
    Write { w: nat, d: int, granted: bool },
    Commit { w: nat },
    /// TROLLBACK: the out entries come back, every $Increment stays
    Rollback { w: nat },
    /// a committed erase of s (review R1-8/R1-10 route list): RemoveSource (Adjacency.cls:373-377: Kill
    /// out, gen, degc) from delete_node (Eraser.EraseIdSet 547) and from the purge's retire_bare_nodes
    /// (Eraser.ForgetNodes 1320-1327); RemoveGraph (erase_graph, Eraser.cls:234; Adjacency.cls:435-440) and
    /// RemoveAll (sync()/BuildKG, %BuildIndices' PurgeIndex AdjIndex.cls:29-32; Adjacency.cls:459-465) also
    /// clear AdjNoLock; the non-indexed snapshot restore kills gen/degc (snapshot.py:1688-1691)
    KillCommitted { clears_nolock: bool },
    /// RemoveSource inside a transaction that is still open (Eraser.EraseIdSet 484-628, 547)
    KillInTx { w: nat, granted: bool },
    Start { r: nat },
    Probe { r: nat },
    Count { r: nat },
    Check { r: nat },
    Set { r: nat },
    ReRead { r: nat },
}

pub open spec fn current(s: DS, e: Entry, v: DV) -> bool {
    e.gen == s.gen && (!v.epoch_stamp || e.epoch == s.epoch)
}

/// Adj.Degree step 1 (Adj.cls:63-67) and Adj.Cached (93-106): the cached answer, if any.
pub open spec fn served(s: DS, v: DV) -> Option<int> {
    match s.degc {
        Some(e) => if current(s, e, v) { Some(e.n) } else { None },
        None => None,
    }
}

pub open spec fn same(s: DS, r: Rd, v: DV) -> bool {
    r.tgen == s.gen && (!v.epoch_stamp || r.tepoch == s.epoch)
}

pub open spec fn any_locked(s: DS) -> bool {
    exists|w: nat| s.ws.contains_key(w) && #[trigger] s.ws[w].locked
}

pub open spec fn no_wrote(s: DS) -> bool {
    forall|w: nat| s.ws.contains_key(w) ==> !(#[trigger] s.ws[w]).wrote
}

pub open spec fn no_writer(s: DS) -> bool {
    forall|w: nat| !(#[trigger] s.ws.contains_key(w))
}

pub open spec fn no_reader(s: DS) -> bool {
    forall|r: nat| !(#[trigger] s.rs.contains_key(r))
}

pub open spec fn others_not_wrote(s: DS, w: nat) -> bool {
    forall|w2: nat| s.ws.contains_key(w2) && w2 != w ==> !(#[trigger] s.ws[w2]).wrote
}

pub open spec fn dstep(s: DS, a: DA, v: DV) -> Option<DS> {
    match a {
        DA::Begin { w } =>
            if s.ws.contains_key(w) {
                None
            } else {
                Some(DS { ws: s.ws.insert(w, Wtx { delta: 0, wrote: false, locked: false, undo_gen: None, undo_degc: None }), ..s })
            },
        DA::Write { w, d, granted } =>
            if !s.ws.contains_key(w) {
                None
            } else {
                let t = s.ws[w];
                let locked = t.locked || granted;
                if v.set_gen {
                    Some(DS {
                        vis: s.vis + d,
                        gen: s.token + 1,
                        token: s.token + 1,
                        nolock: s.nolock || !locked,
                        ws: s.ws.insert(w, Wtx {
                            delta: t.delta + d,
                            wrote: true,
                            locked,
                            undo_gen: if t.undo_gen is None { Some(s.gen) } else { t.undo_gen },
                            ..t
                        }),
                        ..s
                    })
                } else {
                    Some(DS {
                        vis: s.vis + d,
                        gen: if v.bump { s.gen + 1 } else { s.gen },
                        nolock: s.nolock || !locked,
                        ws: s.ws.insert(w, Wtx { delta: t.delta + d, wrote: true, locked, ..t }),
                        ..s
                    })
                }
            },
        DA::Commit { w } =>
            if !s.ws.contains_key(w) { None } else { Some(DS { ws: s.ws.remove(w), ..s }) },
        DA::Rollback { w } =>
            if !s.ws.contains_key(w) {
                None
            } else {
                let t = s.ws[w];
                Some(DS {
                    vis: s.vis - t.delta,
                    gen: match t.undo_gen { Some(g0) => g0, None => s.gen },
                    degc: match t.undo_degc { Some(d0) => d0, None => s.degc },
                    ws: s.ws.remove(w),
                    ..s
                })
            },
        DA::KillCommitted { clears_nolock } =>
            if !no_writer(s) || (v.quiet_kills && !no_reader(s)) {
                None
            } else {
                Some(DS {
                    vis: 0,
                    gen: if v.kill_bumps { s.gen + 1 } else { 0 },
                    epoch: s.epoch + 1,
                    degc: None,
                    nolock: if clears_nolock { false } else { s.nolock },
                    ..s
                })
            },
        DA::KillInTx { w, granted } =>
            if !v.kill_in_tx || !s.ws.contains_key(w) || !others_not_wrote(s, w) || (v.quiet_kills && !no_reader(s)) {
                None
            } else {
                let t = s.ws[w];
                let locked = t.locked || granted;
                Some(DS {
                    vis: 0,
                    gen: if v.kill_bumps { s.gen + 1 } else { 0 },
                    epoch: s.epoch + 1,
                    degc: None,
                    nolock: s.nolock || !locked,
                    ws: s.ws.insert(w, Wtx {
                        delta: t.delta - s.vis,
                        wrote: true,
                        locked,
                        undo_gen: if t.undo_gen is None && !v.kill_bumps { Some(s.gen) } else { t.undo_gen },
                        undo_degc: if t.undo_degc is None { Some(s.degc) } else { t.undo_degc },
                    }),
                    ..s
                })
            },
        DA::Start { r } =>
            if s.rs.contains_key(r) || served(s, v) is Some {
                None  // a hit changes nothing; `served` is its answer
            } else {
                Some(DS { rs: s.rs.insert(r, Rd { pc: Pc::Probe, tgen: s.gen, tepoch: s.epoch, got: false, n: 0 }), ..s })
            },
        DA::Probe { r } =>
            if !s.rs.contains_key(r) || !(s.rs[r].pc is Probe) {
                None
            } else {
                // Lock +^IVG.AdjW(g)#"E":0 — fails while any other process holds the shared lock
                let got = if v.probe { !any_locked(s) } else { true };
                Some(DS { rs: s.rs.insert(r, Rd { pc: Pc::Count, got, ..s.rs[r] }), ..s })
            },
        DA::Count { r } =>
            if !s.rs.contains_key(r) || !(s.rs[r].pc is Count) {
                None
            } else {
                Some(DS { rs: s.rs.insert(r, Rd { pc: Pc::Check, n: s.vis, ..s.rs[r] }), ..s })
            },
        DA::Check { r } =>
            if !s.rs.contains_key(r) || !(s.rs[r].pc is Check) {
                None
            } else {
                let rd = s.rs[r];
                // If tGot && '$Data(^IVG.AdjNoLock(g)) && (+$Get(^KG("gen", g, s)) = tGen)
                if rd.got && (!v.nolock_check || !s.nolock) && (!v.gen_check || same(s, rd, v)) {
                    Some(DS { rs: s.rs.insert(r, Rd { pc: Pc::Set, ..rd }), ..s })
                } else {
                    Some(DS { rs: s.rs.remove(r), ..s })
                }
            },
        DA::Set { r } =>
            if !s.rs.contains_key(r) || !(s.rs[r].pc is Set) {
                None
            } else {
                let rd = s.rs[r];
                Some(DS {
                    degc: Some(Entry { gen: rd.tgen, epoch: rd.tepoch, n: rd.n }),
                    rs: s.rs.insert(r, Rd { pc: Pc::ReRead, ..rd }),
                    ..s
                })
            },
        DA::ReRead { r } =>
            if !s.rs.contains_key(r) || !(s.rs[r].pc is ReRead) {
                None
            } else {
                let rd = s.rs[r];
                Some(DS { degc: if !same(s, rd, v) { None } else { s.degc }, rs: s.rs.remove(r), ..s })
            },
    }
}

// ---------------------------------------------------------------------------- variants

/// The as-built mechanism under PREMISE P-QUIET; route-2 kills (inside a transaction that rolls
/// back) are outside this variant.
pub open spec fn dv_as_built() -> DV {
    DV { probe: true, gen_check: true, nolock_check: true, bump: true, epoch_stamp: false, quiet_kills: true, kill_in_tx: false, set_gen: false, kill_bumps: false }
}

/// The product as it runs: no premise on when a kill happens.
pub open spec fn dv_product() -> DV {
    DV { probe: true, gen_check: true, nolock_check: true, bump: true, epoch_stamp: false, quiet_kills: false, kill_in_tx: true, set_gen: false, kill_bumps: false }
}

/// Proposed repair: every kill of gen/degc first $Increments a counter that is never killed, and
/// a cache entry carries that counter's value beside gen (stored and compared together).
pub open spec fn dv_repaired() -> DV {
    DV { probe: true, gen_check: true, nolock_check: true, bump: true, epoch_stamp: true, quiet_kills: false, kill_in_tx: false, set_gen: false, kill_bumps: false }
}

/// Review Check B's repair: erases bump the generation instead of killing it.
pub open spec fn dv_kill_bumps() -> DV {
    DV { probe: true, gen_check: true, nolock_check: true, bump: true, epoch_stamp: false, quiet_kills: false, kill_in_tx: false, set_gen: false, kill_bumps: true }
}

pub open spec fn dv_kill_bumps_tx() -> DV {
    DV { probe: true, gen_check: true, nolock_check: true, bump: true, epoch_stamp: false, quiet_kills: false, kill_in_tx: true, set_gen: false, kill_bumps: true }
}

pub open spec fn dv_repaired_tx() -> DV {
    DV { probe: true, gen_check: true, nolock_check: true, bump: true, epoch_stamp: true, quiet_kills: false, kill_in_tx: true, set_gen: false, kill_bumps: false }
}

// ---------------------------------------------------------------------------- invariant

/// stamp (ae, ag) is not newer than (be, bg)
pub open spec fn le(v: DV, ae: nat, ag: nat, be: nat, bg: nat) -> bool {
    if v.epoch_stamp { ae < be || (ae == be && ag <= bg) } else { ag <= bg }
}

pub open spec fn writers_ok(s: DS) -> bool {
    forall|w: nat| #[trigger] s.ws.contains_key(w) ==> {
        let t = s.ws[w];
        &&& (!t.wrote ==> t.delta == 0 && !t.locked)
        &&& (t.wrote && !t.locked ==> s.nolock)
        &&& t.undo_gen is None
        &&& t.undo_degc is None
    }
}

pub open spec fn cache_ok(s: DS, v: DV) -> bool {
    match s.degc {
        Some(e) => {
            &&& le(v, e.epoch, e.gen, s.epoch, s.gen)
            &&& (current(s, e, v) ==> e.n == s.vis && no_wrote(s))
        },
        None => true,
    }
}

pub open spec fn readers_ok(s: DS, v: DV) -> bool {
    forall|r: nat| #[trigger] s.rs.contains_key(r) ==> {
        let rd = s.rs[r];
        &&& le(v, rd.tepoch, rd.tgen, s.epoch, s.gen)
        &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s, rd, v) && !s.nolock ==> no_wrote(s))
        &&& (rd.pc is Check && rd.got && same(s, rd, v) && !s.nolock ==> rd.n == s.vis)
        &&& (rd.pc is Set && same(s, rd, v) ==> !s.nolock && rd.n == s.vis && no_wrote(s))
    }
}

pub open spec fn dinv(s: DS, v: DV) -> bool {
    writers_ok(s) && cache_ok(s, v) && readers_ok(s, v)
}

pub open spec fn dinit(s: DS) -> bool {
    no_writer(s) && no_reader(s) && s.degc is None && !s.nolock
}

/// The variants the proof covers: the as-built mechanism under P-QUIET, and the repair without it.
pub open spec fn covered(v: DV) -> bool {
    &&& v.probe && v.gen_check && v.nolock_check && v.bump && !v.kill_in_tx && !v.set_gen
    &&& (v.quiet_kills || v.epoch_stamp || v.kill_bumps)
}

pub proof fn lemma_dinit(s: DS, v: DV)
    requires
        dinit(s),
    ensures
        dinv(s, v),
{
}

/// L1 (ADR-0012:12-17, "the cache is derived: Kill it and every answer is still right"): a cached
/// degree served by Degree/Cached equals what a recount answers at that moment.
pub proof fn theorem_served_equals_recount(s: DS, v: DV)
    requires
        dinv(s, v),
    ensures
        served(s, v) is Some ==> served(s, v)->Some_0 == s.vis,
{
}

pub proof fn lemma_begin(s: DS, v: DV, w: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Begin { w }, v) is Some,
    ensures
        dinv(dstep(s, DA::Begin { w }, v)->Some_0, v),
{
    let a = DA::Begin { w };
    let s2 = dstep(s, a, v)->Some_0;
    assert(writers_ok(s2)) by {
        assert forall|x: nat| #[trigger] s2.ws.contains_key(x) implies {
            let t = s2.ws[x];
            &&& (!t.wrote ==> t.delta == 0 && !t.locked)
            &&& (t.wrote && !t.locked ==> s2.nolock)
            &&& t.undo_gen is None
            &&& t.undo_degc is None
        } by {
            if x != w { assert(s.ws.contains_key(x)); }
        }
    }
    assert(no_wrote(s) ==> no_wrote(s2)) by {
        if no_wrote(s) {
            assert forall|x: nat| s2.ws.contains_key(x) implies !(#[trigger] s2.ws[x]).wrote by {
                if x != w { assert(s.ws.contains_key(x)); }
            }
        }
    }
    assert(readers_ok(s2, v)) by {
        assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies {
            let rd = s2.rs[r];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(r));
        }
    }

}

pub proof fn lemma_write(s: DS, v: DV, w: nat, d: int, granted: bool)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Write { w, d, granted }, v) is Some,
    ensures
        dinv(dstep(s, DA::Write { w, d, granted }, v)->Some_0, v),
{
    let a = DA::Write { w, d, granted };
    let s2 = dstep(s, a, v)->Some_0;
    let t = s.ws[w];
    assert(writers_ok(s2)) by {
        assert forall|x: nat| #[trigger] s2.ws.contains_key(x) implies {
            let t2 = s2.ws[x];
            &&& (!t2.wrote ==> t2.delta == 0 && !t2.locked)
            &&& (t2.wrote && !t2.locked ==> s2.nolock)
            &&& t2.undo_gen is None
            &&& t2.undo_degc is None
        } by {
            if x != w { assert(s.ws.contains_key(x)); }
        }
    }
    // the bump makes every stamp strictly older than (epoch, gen)
    assert(cache_ok(s2, v)) by {
        match s.degc {
            Some(e) => {
                assert(le(v, e.epoch, e.gen, s.epoch, s.gen));
                assert(!current(s2, e, v));
            },
            None => {},
        }
    }
    assert(readers_ok(s2, v)) by {
        assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies {
            let rd = s2.rs[r];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(r));
            let rd = s.rs[r];
            assert(le(v, rd.tepoch, rd.tgen, s.epoch, s.gen));
            assert(!same(s2, rd, v));
        }
    }

}

pub proof fn lemma_commit(s: DS, v: DV, w: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Commit { w }, v) is Some,
    ensures
        dinv(dstep(s, DA::Commit { w }, v)->Some_0, v),
{
    let a = DA::Commit { w };
    let s2 = dstep(s, a, v)->Some_0;
    assert(no_wrote(s) ==> no_wrote(s2)) by {
        if no_wrote(s) {
            assert forall|x: nat| s2.ws.contains_key(x) implies !(#[trigger] s2.ws[x]).wrote by {
                assert(s.ws.contains_key(x));
            }
        }
    }
    assert(writers_ok(s2)) by {
        assert forall|x: nat| #[trigger] s2.ws.contains_key(x) implies {
            let t2 = s2.ws[x];
            &&& (!t2.wrote ==> t2.delta == 0 && !t2.locked)
            &&& (t2.wrote && !t2.locked ==> s2.nolock)
            &&& t2.undo_gen is None
            &&& t2.undo_degc is None
        } by {
            assert(s.ws.contains_key(x));
        }
    }
    assert(readers_ok(s2, v)) by {
        assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies {
            let rd = s2.rs[r];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(r));
        }
    }

}

pub proof fn lemma_rollback(s: DS, v: DV, w: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Rollback { w }, v) is Some,
    ensures
        dinv(dstep(s, DA::Rollback { w }, v)->Some_0, v),
{
    let a = DA::Rollback { w };
    let s2 = dstep(s, a, v)->Some_0;
    let t = s.ws[w];
    assert(t.undo_gen is None && t.undo_degc is None);
    // a writer that wrote cannot coexist with a current entry or a reader that may still store
    assert(no_wrote(s) ==> t.delta == 0) by {
        if no_wrote(s) { assert(!s.ws[w].wrote); }
    }
    assert(no_wrote(s) ==> no_wrote(s2)) by {
        if no_wrote(s) {
            assert forall|x: nat| s2.ws.contains_key(x) implies !(#[trigger] s2.ws[x]).wrote by {
                assert(s.ws.contains_key(x));
            }
        }
    }
    assert(writers_ok(s2)) by {
        assert forall|x: nat| #[trigger] s2.ws.contains_key(x) implies {
            let t2 = s2.ws[x];
            &&& (!t2.wrote ==> t2.delta == 0 && !t2.locked)
            &&& (t2.wrote && !t2.locked ==> s2.nolock)
            &&& t2.undo_gen is None
            &&& t2.undo_degc is None
        } by {
            assert(s.ws.contains_key(x));
        }
    }
    assert(readers_ok(s2, v)) by {
        assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies {
            let rd = s2.rs[r];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(r));
        }
    }

}

pub proof fn lemma_killcommitted(s: DS, v: DV, clears_nolock: bool)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::KillCommitted { clears_nolock }, v) is Some,
    ensures
        dinv(dstep(s, DA::KillCommitted { clears_nolock }, v)->Some_0, v),
{
    let a = DA::KillCommitted { clears_nolock };
    let s2 = dstep(s, a, v)->Some_0;
    assert(writers_ok(s2)) by {
        assert forall|x: nat| #[trigger] s2.ws.contains_key(x) implies false by {
            assert(!s.ws.contains_key(x));
        }
    }
    assert(readers_ok(s2, v)) by {
        assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies {
            let rd = s2.rs[r];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(r));
            // P-QUIET excludes this case in the as-built variant; each repair moves the stamp forward
            let rd = s.rs[r];
            assert(le(v, rd.tepoch, rd.tgen, s.epoch, s.gen));
            assert(!same(s2, rd, v));
        }
    }

}

pub proof fn lemma_killintx(s: DS, v: DV, w: nat, granted: bool)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::KillInTx { w, granted }, v) is Some,
    ensures
        dinv(dstep(s, DA::KillInTx { w, granted }, v)->Some_0, v),
{
    let a = DA::KillInTx { w, granted };
    let s2 = dstep(s, a, v)->Some_0;
    assert(false);

}

pub proof fn lemma_start(s: DS, v: DV, r: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Start { r }, v) is Some,
    ensures
        dinv(dstep(s, DA::Start { r }, v)->Some_0, v),
{
    let a = DA::Start { r };
    let s2 = dstep(s, a, v)->Some_0;
    assert(readers_ok(s2, v)) by {
        assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies {
            let rd = s2.rs[x];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            if x != r { assert(s.rs.contains_key(x)); }
        }
    }

}

pub proof fn lemma_probe(s: DS, v: DV, r: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Probe { r }, v) is Some,
    ensures
        dinv(dstep(s, DA::Probe { r }, v)->Some_0, v),
{
    let a = DA::Probe { r };
    let s2 = dstep(s, a, v)->Some_0;
    assert(readers_ok(s2, v)) by {
        assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies {
            let rd = s2.rs[x];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(x));
            if x == r {
                let rd = s2.rs[x];
                if rd.got && !s2.nolock {
                    // no other process holds the shared lock; a writer that wrote without it set AdjNoLock
                    assert forall|w: nat| s2.ws.contains_key(w) implies !(#[trigger] s2.ws[w]).wrote by {
                        assert(!s.ws[w].locked);
                    }
                }
            }
        }
    }

}

pub proof fn lemma_count(s: DS, v: DV, r: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Count { r }, v) is Some,
    ensures
        dinv(dstep(s, DA::Count { r }, v)->Some_0, v),
{
    let a = DA::Count { r };
    let s2 = dstep(s, a, v)->Some_0;
    assert(readers_ok(s2, v)) by {
        assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies {
            let rd = s2.rs[x];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(x));
        }
    }

}

pub proof fn lemma_check(s: DS, v: DV, r: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Check { r }, v) is Some,
    ensures
        dinv(dstep(s, DA::Check { r }, v)->Some_0, v),
{
    let a = DA::Check { r };
    let s2 = dstep(s, a, v)->Some_0;
    assert(readers_ok(s2, v)) by {
        assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies {
            let rd = s2.rs[x];
            &&& le(v, rd.tepoch, rd.tgen, s2.epoch, s2.gen)
            &&& ((rd.pc is Count || rd.pc is Check) && rd.got && same(s2, rd, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd.pc is Check && rd.got && same(s2, rd, v) && !s2.nolock ==> rd.n == s2.vis)
            &&& (rd.pc is Set && same(s2, rd, v) ==> !s2.nolock && rd.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(x));
        }
    }

}

pub proof fn lemma_set(s: DS, v: DV, r: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::Set { r }, v) is Some,
    ensures
        dinv(dstep(s, DA::Set { r }, v)->Some_0, v),
{
    let a = DA::Set { r };
    let s2 = dstep(s, a, v)->Some_0;
    let rd = s.rs[r];
    assert(cache_ok(s2, v)) by {
        assert(le(v, rd.tepoch, rd.tgen, s.epoch, s.gen));
    }
    assert(readers_ok(s2, v)) by {
        assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies {
            let rd2 = s2.rs[x];
            &&& le(v, rd2.tepoch, rd2.tgen, s2.epoch, s2.gen)
            &&& ((rd2.pc is Count || rd2.pc is Check) && rd2.got && same(s2, rd2, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd2.pc is Check && rd2.got && same(s2, rd2, v) && !s2.nolock ==> rd2.n == s2.vis)
            &&& (rd2.pc is Set && same(s2, rd2, v) ==> !s2.nolock && rd2.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(x));
        }
    }

}

pub proof fn lemma_reread(s: DS, v: DV, r: nat)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, DA::ReRead { r }, v) is Some,
    ensures
        dinv(dstep(s, DA::ReRead { r }, v)->Some_0, v),
{
    let a = DA::ReRead { r };
    let s2 = dstep(s, a, v)->Some_0;
    assert(readers_ok(s2, v)) by {
        assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies {
            let rd2 = s2.rs[x];
            &&& le(v, rd2.tepoch, rd2.tgen, s2.epoch, s2.gen)
            &&& ((rd2.pc is Count || rd2.pc is Check) && rd2.got && same(s2, rd2, v) && !s2.nolock ==> no_wrote(s2))
            &&& (rd2.pc is Check && rd2.got && same(s2, rd2, v) && !s2.nolock ==> rd2.n == s2.vis)
            &&& (rd2.pc is Set && same(s2, rd2, v) ==> !s2.nolock && rd2.n == s2.vis && no_wrote(s2))
        } by {
            assert(s.rs.contains_key(x));
        }
    }

}

pub proof fn lemma_dstep_preserves(s: DS, a: DA, v: DV)
    requires
        covered(v),
        dinv(s, v),
        dstep(s, a, v) is Some,
    ensures
        dinv(dstep(s, a, v)->Some_0, v),
{
    match a {
        DA::Begin { w } => lemma_begin(s, v, w),
        DA::Write { w, d, granted } => lemma_write(s, v, w, d, granted),
        DA::Commit { w } => lemma_commit(s, v, w),
        DA::Rollback { w } => lemma_rollback(s, v, w),
        DA::KillCommitted { clears_nolock } => lemma_killcommitted(s, v, clears_nolock),
        DA::KillInTx { w, granted } => lemma_killintx(s, v, w, granted),
        DA::Start { r } => lemma_start(s, v, r),
        DA::Probe { r } => lemma_probe(s, v, r),
        DA::Count { r } => lemma_count(s, v, r),
        DA::Check { r } => lemma_check(s, v, r),
        DA::Set { r } => lemma_set(s, v, r),
        DA::ReRead { r } => lemma_reread(s, v, r),
    }
}

/// O3, as built: under P-QUIET the four-step reader protocol with the writer lock, the
/// AdjNoLock marker and the generation keeps every served degree equal to a recount, for any
/// number of writers (commit or rollback, lockless or not) and readers.
pub proof fn theorem_as_built_cache_sound(s: DS, a: DA)
    requires
        dinv(s, dv_as_built()),
        dstep(s, a, dv_as_built()) is Some,
    ensures
        dinv(dstep(s, a, dv_as_built())->Some_0, dv_as_built()),
        served(dstep(s, a, dv_as_built())->Some_0, dv_as_built()) is Some
            ==> served(dstep(s, a, dv_as_built())->Some_0, dv_as_built())->Some_0 == dstep(s, a, dv_as_built())->Some_0.vis,
{
    lemma_dstep_preserves(s, a, dv_as_built());
}

/// The repair needs no premise on when a committed kill happens.
pub proof fn theorem_repaired_cache_sound(s: DS, a: DA)
    requires
        dinv(s, dv_repaired()),
        dstep(s, a, dv_repaired()) is Some,
    ensures
        dinv(dstep(s, a, dv_repaired())->Some_0, dv_repaired()),
        served(dstep(s, a, dv_repaired())->Some_0, dv_repaired()) is Some
            ==> served(dstep(s, a, dv_repaired())->Some_0, dv_repaired())->Some_0 == dstep(s, a, dv_repaired())->Some_0.vis,
{
    lemma_dstep_preserves(s, a, dv_repaired());
}

/// Review Check B's repair needs no premise on when a committed erase happens either, and keeps the
/// product's entry format ($ListBuild(gen, count)).
pub proof fn theorem_kill_bump_cache_sound(s: DS, a: DA)
    requires
        dinv(s, dv_kill_bumps()),
        dstep(s, a, dv_kill_bumps()) is Some,
    ensures
        dinv(dstep(s, a, dv_kill_bumps())->Some_0, dv_kill_bumps()),
        served(dstep(s, a, dv_kill_bumps())->Some_0, dv_kill_bumps()) is Some
            ==> served(dstep(s, a, dv_kill_bumps())->Some_0, dv_kill_bumps())->Some_0 == dstep(s, a, dv_kill_bumps())->Some_0.vis,
{
    lemma_dstep_preserves(s, a, dv_kill_bumps());
}

// ---------------------------------------------------------------------------- witnesses

pub open spec fn s_two_edges() -> DS {
    DS { vis: 2, gen: 2, epoch: 0, token: 2, degc: None, nolock: false, ws: Map::empty(), rs: Map::empty() }
}

/// The ABA schedule (F2 route 1). Reader R: Degree(g, s) misses at gen 2 and counts 2. Before it
/// reaches the store test: delete_node(s) commits (RemoveSource kills gen and degc), create_edge(s,
/// p, c) commits (gen 1), delete_edge(s, p, c) commits (gen 2). R's test and its re-read both see
/// gen 2 and it stores (2, 2); every later Degree(g, s) answers 2 while s has no out entry.
pub open spec fn aba_trace(v: DV) -> DS {
    let s0 = s_two_edges();
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Probe { r: 1 }, v)->Some_0;
    let s3 = dstep(s2, DA::Count { r: 1 }, v)->Some_0;
    let s4 = dstep(s3, DA::KillCommitted { clears_nolock: false }, v)->Some_0;
    let s5 = dstep(s4, DA::Begin { w: 1 }, v)->Some_0;
    let s6 = dstep(s5, DA::Write { w: 1, d: 1, granted: true }, v)->Some_0;
    let s7 = dstep(s6, DA::Commit { w: 1 }, v)->Some_0;
    let s8 = dstep(s7, DA::Begin { w: 2 }, v)->Some_0;
    let s9 = dstep(s8, DA::Write { w: 2, d: -1, granted: true }, v)->Some_0;
    let s10 = dstep(s9, DA::Commit { w: 2 }, v)->Some_0;
    let s11 = dstep(s10, DA::Check { r: 1 }, v)->Some_0;
    s11
}

pub proof fn witness_aba_delete_and_recreate_serves_stale_degree() {
    let v = dv_product();
    let s0 = s_two_edges();
    assert(served(s0, v) is None);
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    assert(s1.rs[1].tgen == 2);
    let s2 = dstep(s1, DA::Probe { r: 1 }, v)->Some_0;
    assert(!any_locked(s1));
    assert(s2.rs[1].got);
    let s3 = dstep(s2, DA::Count { r: 1 }, v)->Some_0;
    assert(s3.rs[1].n == 2);
    assert(no_writer(s3));
    let s4 = dstep(s3, DA::KillCommitted { clears_nolock: false }, v)->Some_0;
    assert(s4.gen == 0 && s4.vis == 0 && s4.degc is None);
    let s5 = dstep(s4, DA::Begin { w: 1 }, v)->Some_0;
    let s6 = dstep(s5, DA::Write { w: 1, d: 1, granted: true }, v)->Some_0;
    let s7 = dstep(s6, DA::Commit { w: 1 }, v)->Some_0;
    assert(s7.gen == 1 && s7.vis == 1);
    assert(s7.ws =~= Map::<nat, Wtx>::empty());
    let s8 = dstep(s7, DA::Begin { w: 2 }, v)->Some_0;
    let s9 = dstep(s8, DA::Write { w: 2, d: -1, granted: true }, v)->Some_0;
    let s10 = dstep(s9, DA::Commit { w: 2 }, v)->Some_0;
    assert(s10.gen == 2 && s10.vis == 0 && !s10.nolock);
    assert(s10.rs[1].pc is Check && s10.rs[1].got && s10.rs[1].tgen == 2 && s10.rs[1].n == 2);
    let s11 = dstep(s10, DA::Check { r: 1 }, v)->Some_0;
    assert(s11.rs[1].pc is Set);
    let s12 = dstep(s11, DA::Set { r: 1 }, v)->Some_0;
    let s13 = dstep(s12, DA::ReRead { r: 1 }, v)->Some_0;
    assert(s13.degc == Some(Entry { gen: 2, epoch: 0, n: 2 }));
    assert(s13.gen == 2);
    assert(served(s13, v) == Some(2int));
    assert(s13.vis == 0);
}

/// The same schedule under the repair: the kill moved the epoch, so R does not store.
pub proof fn witness_repair_refuses_the_aba_store() {
    let v = dv_repaired();
    let s0 = s_two_edges();
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Probe { r: 1 }, v)->Some_0;
    assert(!any_locked(s1));
    let s3 = dstep(s2, DA::Count { r: 1 }, v)->Some_0;
    assert(no_writer(s3));
    let s4 = dstep(s3, DA::KillCommitted { clears_nolock: false }, v)->Some_0;
    let s5 = dstep(s4, DA::Begin { w: 1 }, v)->Some_0;
    let s6 = dstep(s5, DA::Write { w: 1, d: 1, granted: true }, v)->Some_0;
    let s7 = dstep(s6, DA::Commit { w: 1 }, v)->Some_0;
    assert(s7.ws =~= Map::<nat, Wtx>::empty());
    let s8 = dstep(s7, DA::Begin { w: 2 }, v)->Some_0;
    let s9 = dstep(s8, DA::Write { w: 2, d: -1, granted: true }, v)->Some_0;
    let s10 = dstep(s9, DA::Commit { w: 2 }, v)->Some_0;
    assert(s10.gen == 2 && s10.epoch == 1 && s10.rs[1].tepoch == 0);
    let s11 = dstep(s10, DA::Check { r: 1 }, v)->Some_0;
    assert(!s11.rs.contains_key(1));
    assert(s11.degc is None);
    assert(served(s11, v) is None);
}

/// P-QUIET is what the as-built proof needs: the as-built variant refuses the kill while R is in
/// flight (the schedule above is outside it).
pub proof fn witness_quiet_premise_excludes_the_aba() {
    let v = dv_as_built();
    let s0 = s_two_edges();
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    assert(s1.rs.contains_key(1));
    assert(dstep(s1, DA::KillCommitted { clears_nolock: false }, v) is None);
}

pub open spec fn s_cached_zero() -> DS {
    DS { vis: 0, gen: 2, epoch: 0, token: 2, degc: Some(Entry { gen: 2, epoch: 0, n: 0 }), nolock: false, ws: Map::empty(), rs: Map::empty() }
}

/// F2 route 2 (model only; reachability open, see NOTES): s has no out entry and a current
/// entry (2, 0). W1 erases s in a transaction (RemoveSource kills gen and degc, journaled); W2
/// writes an out entry of s and commits (gen restarts at 1); W1 rolls back, which restores gen 2
/// and the entry (2, 0) over W2's increment. The entry is current and wrong, with no reader race.
pub proof fn witness_rolled_back_kill_restores_stale_entry() {
    let v = dv_product();
    let s0 = s_cached_zero();
    assert(served(s0, v) == Some(0int));
    let s1 = dstep(s0, DA::Begin { w: 1 }, v)->Some_0;
    assert(others_not_wrote(s1, 1));
    assert(no_reader(s1));
    let s2 = dstep(s1, DA::KillInTx { w: 1, granted: true }, v)->Some_0;
    assert(s2.gen == 0 && s2.degc is None);
    assert(s2.ws[1].undo_gen == Some(2nat));
    let s3 = dstep(s2, DA::Begin { w: 2 }, v)->Some_0;
    let s4 = dstep(s3, DA::Write { w: 2, d: 1, granted: true }, v)->Some_0;
    let s5 = dstep(s4, DA::Commit { w: 2 }, v)->Some_0;
    assert(s5.vis == 1 && s5.gen == 1);
    assert(s5.ws.contains_key(1) && s5.ws[1].delta == 0);
    let s6 = dstep(s5, DA::Rollback { w: 1 }, v)->Some_0;
    assert(s6.gen == 2 && s6.vis == 1);
    assert(s6.degc == Some(Entry { gen: 2, epoch: 0, n: 0 }));
    assert(served(s6, v) == Some(0int));
}

/// Under the epoch repair the restored entry carries an old epoch and is not served.
pub proof fn witness_repair_ignores_restored_entry() {
    let v = dv_repaired_tx();
    let s0 = s_cached_zero();
    let s1 = dstep(s0, DA::Begin { w: 1 }, v)->Some_0;
    assert(others_not_wrote(s1, 1));
    let s2 = dstep(s1, DA::KillInTx { w: 1, granted: true }, v)->Some_0;
    let s3 = dstep(s2, DA::Begin { w: 2 }, v)->Some_0;
    let s4 = dstep(s3, DA::Write { w: 2, d: 1, granted: true }, v)->Some_0;
    let s5 = dstep(s4, DA::Commit { w: 2 }, v)->Some_0;
    assert(s5.ws.contains_key(1));
    let s6 = dstep(s5, DA::Rollback { w: 1 }, v)->Some_0;
    assert(s6.epoch == 1);
    assert(served(s6, v) is None);
}

/// Why the probe exists (ADR-0012:23-26): with the probe removed, a reader that counts an
/// uncommitted entry stores it under the post-write generation, and the writer's rollback (which
/// moves no generation) leaves a current, wrong entry. Same schedule as the spike's failing case.
pub proof fn witness_without_probe_rollback_poisons() {
    let v = DV { probe: false, gen_check: true, nolock_check: true, bump: true, epoch_stamp: false, quiet_kills: true, kill_in_tx: false, set_gen: false, kill_bumps: false };
    let s0 = s_two_edges();
    let s1 = dstep(s0, DA::Begin { w: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Write { w: 1, d: 1, granted: true }, v)->Some_0;
    assert(s2.gen == 3 && s2.vis == 3 && s2.ws[1].locked);
    let s3 = dstep(s2, DA::Start { r: 1 }, v)->Some_0;
    let s4 = dstep(s3, DA::Probe { r: 1 }, v)->Some_0;
    let s5 = dstep(s4, DA::Count { r: 1 }, v)->Some_0;
    let s6 = dstep(s5, DA::Check { r: 1 }, v)->Some_0;
    assert(s6.rs[1].pc is Set);
    let s7 = dstep(s6, DA::Set { r: 1 }, v)->Some_0;
    let s8 = dstep(s7, DA::ReRead { r: 1 }, v)->Some_0;
    assert(s8.ws.contains_key(1));
    let s9 = dstep(s8, DA::Rollback { w: 1 }, v)->Some_0;
    assert(s9.vis == 2 && s9.gen == 3);
    assert(served(s9, v) == Some(3int));
}

/// The same schedule as built: the writer holds the shared lock, the probe fails, nothing is stored.
pub proof fn witness_probe_refuses_uncommitted_count() {
    let v = dv_as_built();
    let s0 = s_two_edges();
    let s1 = dstep(s0, DA::Begin { w: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Write { w: 1, d: 1, granted: true }, v)->Some_0;
    let s3 = dstep(s2, DA::Start { r: 1 }, v)->Some_0;
    assert(s3.ws.contains_key(1) && s3.ws[1].locked);
    assert(any_locked(s3));
    let s4 = dstep(s3, DA::Probe { r: 1 }, v)->Some_0;
    assert(!s4.rs[1].got);
    let s5 = dstep(s4, DA::Count { r: 1 }, v)->Some_0;
    let s6 = dstep(s5, DA::Check { r: 1 }, v)->Some_0;
    assert(!s6.rs.contains_key(1));
    assert(s6.degc is None);
}

/// The intent notes' S1 (draw each generation from the never-killed token with a Set) is not a
/// repair: a Set inside a transaction is undone by its rollback, so two writers on s, the second
/// committing and the first rolling back, put the pre-image back over the committed generation and
/// revive an entry stamped with it. Here s has no out entry and a current entry (2, 0); W1 adds an
/// edge (gen := 3, pre-image 2), W2 adds an edge and commits (gen := 4), W1 rolls back (gen := 2):
/// the entry (2, 0) is current while s has one out entry. The $Increment the product uses is what
/// makes an over-bump harmless (ADR-0012:23-24); the epoch repair keeps it.
pub proof fn witness_s1_set_generation_is_undone_by_rollback() {
    let v = DV { probe: true, gen_check: true, nolock_check: true, bump: true, epoch_stamp: false, quiet_kills: true, kill_in_tx: false, set_gen: true, kill_bumps: false };
    let s0 = s_cached_zero();
    assert(served(s0, v) == Some(0int));
    let s1 = dstep(s0, DA::Begin { w: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Write { w: 1, d: 1, granted: true }, v)->Some_0;
    assert(s2.gen == 3 && s2.ws[1].undo_gen == Some(2nat));
    let s3 = dstep(s2, DA::Begin { w: 2 }, v)->Some_0;
    let s4 = dstep(s3, DA::Write { w: 2, d: 1, granted: true }, v)->Some_0;
    let s5 = dstep(s4, DA::Commit { w: 2 }, v)->Some_0;
    assert(s5.gen == 4 && s5.vis == 2);
    assert(s5.ws.contains_key(1));
    let s6 = dstep(s5, DA::Rollback { w: 1 }, v)->Some_0;
    assert(s6.gen == 2 && s6.vis == 1);
    assert(served(s6, v) == Some(0int));
}

/// R1-10 (review Check B2): the gen-absent route. NON-INDEXED namespaces only: BuildKG's FillEdge
/// (Adjacency.cls:826-830) and the non-indexed restore (snapshot.py:1688-1691) leave out entries with
/// no ^KG("gen", g, s), which reads as 0; an indexed rebuild goes through %BuildIndices -> Put and bumps.
/// R reads gen 0, probes, counts 2; ONE committed erase of s (delete_node, retire_bare_nodes' ForgetNodes,
/// erase_graph, a PurgeIndex/RemoveAll) leaves gen 0 again; R's test and re-read both see 0 and it stores
/// (0, 2), served while s has no out entry.
pub proof fn witness_gen0_erase_alone_serves_stale_degree() {
    let v = dv_product();
    let s0 = DS { vis: 2, gen: 0, epoch: 0, token: 0, degc: None, nolock: false, ws: Map::empty(), rs: Map::empty() };
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Probe { r: 1 }, v)->Some_0;
    assert(!any_locked(s1));
    let s3 = dstep(s2, DA::Count { r: 1 }, v)->Some_0;
    assert(no_writer(s3));
    let s4 = dstep(s3, DA::KillCommitted { clears_nolock: false }, v)->Some_0;
    let s5 = dstep(s4, DA::Check { r: 1 }, v)->Some_0;
    assert(s5.rs[1].pc is Set);
    let s6 = dstep(s5, DA::Set { r: 1 }, v)->Some_0;
    let s7 = dstep(s6, DA::ReRead { r: 1 }, v)->Some_0;
    assert(served(s7, v) == Some(2int));
    assert(s7.vis == 0);
}

pub proof fn witness_gen0_epoch_repair_refuses() {
    let v = dv_repaired();
    let s0 = DS { vis: 2, gen: 0, epoch: 0, token: 0, degc: None, nolock: false, ws: Map::empty(), rs: Map::empty() };
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Probe { r: 1 }, v)->Some_0;
    assert(!any_locked(s1));
    let s3 = dstep(s2, DA::Count { r: 1 }, v)->Some_0;
    let s4 = dstep(s3, DA::KillCommitted { clears_nolock: false }, v)->Some_0;
    let s5 = dstep(s4, DA::Check { r: 1 }, v)->Some_0;
    assert(!s5.rs.contains_key(1));
    assert(served(s5, v) is None);
}

pub proof fn witness_gen0_kill_bump_refuses() {
    let v = dv_kill_bumps();
    let s0 = DS { vis: 2, gen: 0, epoch: 0, token: 0, degc: None, nolock: false, ws: Map::empty(), rs: Map::empty() };
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Probe { r: 1 }, v)->Some_0;
    assert(!any_locked(s1));
    let s3 = dstep(s2, DA::Count { r: 1 }, v)->Some_0;
    let s4 = dstep(s3, DA::KillCommitted { clears_nolock: false }, v)->Some_0;
    assert(s4.gen == 1);
    let s5 = dstep(s4, DA::Check { r: 1 }, v)->Some_0;
    assert(!s5.rs.contains_key(1));
    assert(served(s5, v) is None);
}

/// Route 1 (delete + re-create) under the bump-instead-of-kill repair: the erase moved gen to 3, the
/// re-creation to 5, so R (tGen 2) does not store.
pub proof fn witness_kill_bump_refuses_the_aba_store() {
    let v = dv_kill_bumps();
    let s0 = s_two_edges();
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Probe { r: 1 }, v)->Some_0;
    assert(!any_locked(s1));
    let s3 = dstep(s2, DA::Count { r: 1 }, v)->Some_0;
    assert(no_writer(s3));
    let s4 = dstep(s3, DA::KillCommitted { clears_nolock: false }, v)->Some_0;
    let s5 = dstep(s4, DA::Begin { w: 1 }, v)->Some_0;
    let s6 = dstep(s5, DA::Write { w: 1, d: 1, granted: true }, v)->Some_0;
    let s7 = dstep(s6, DA::Commit { w: 1 }, v)->Some_0;
    assert(s7.ws =~= Map::<nat, Wtx>::empty());
    let s8 = dstep(s7, DA::Begin { w: 2 }, v)->Some_0;
    let s9 = dstep(s8, DA::Write { w: 2, d: -1, granted: true }, v)->Some_0;
    let s10 = dstep(s9, DA::Commit { w: 2 }, v)->Some_0;
    assert(s10.gen == 5);
    let s11 = dstep(s10, DA::Check { r: 1 }, v)->Some_0;
    assert(!s11.rs.contains_key(1));
    assert(served(s11, v) is None);
}

/// Route 2 under the bump-instead-of-kill repair: the erase's $Increment is not journaled, so its rollback
/// restores the old entry (2, 0) but not an old generation; the entry is not served.
pub proof fn witness_kill_bump_ignores_restored_entry() {
    let v = dv_kill_bumps_tx();
    let s0 = s_cached_zero();
    let s1 = dstep(s0, DA::Begin { w: 1 }, v)->Some_0;
    assert(others_not_wrote(s1, 1));
    let s2 = dstep(s1, DA::KillInTx { w: 1, granted: true }, v)->Some_0;
    assert(s2.gen == 3 && s2.ws[1].undo_gen is None);
    let s3 = dstep(s2, DA::Begin { w: 2 }, v)->Some_0;
    let s4 = dstep(s3, DA::Write { w: 2, d: 1, granted: true }, v)->Some_0;
    let s5 = dstep(s4, DA::Commit { w: 2 }, v)->Some_0;
    assert(s5.ws.contains_key(1));
    let s6 = dstep(s5, DA::Rollback { w: 1 }, v)->Some_0;
    assert(s6.gen == 4 && s6.degc == Some(Entry { gen: 2, epoch: 0, n: 0 }));
    assert(served(s6, v) is None);
}

/// A valid outcome survives: with no writer in flight a miss stores and the next call is served
/// from the cache (the cache is used, not merely never wrong).
pub proof fn witness_quiet_reader_fills_and_hits() {
    let v = dv_as_built();
    let s0 = s_two_edges();
    let s1 = dstep(s0, DA::Start { r: 1 }, v)->Some_0;
    let s2 = dstep(s1, DA::Probe { r: 1 }, v)->Some_0;
    assert(!any_locked(s1));
    let s3 = dstep(s2, DA::Count { r: 1 }, v)->Some_0;
    let s4 = dstep(s3, DA::Check { r: 1 }, v)->Some_0;
    assert(s4.rs[1].pc is Set);
    let s5 = dstep(s4, DA::Set { r: 1 }, v)->Some_0;
    let s6 = dstep(s5, DA::ReRead { r: 1 }, v)->Some_0;
    assert(served(s6, v) == Some(2int));
}

// ============================================================================ §3 parallel edges (O5)
//
// One triple (g, s, p, o) of a graph. Rows are the triple's rdf_edges rows in graph g, by ekey.
// Weights are not represented (the leaf's value, FR-004's "lowest ekey" weight and F11 are out of
// scope); what is represented is which nodes exist, which is what neighbours and degree read.

/// ^KG("out", g, s, p, o) and its subtree (the "in" mirror is written symmetrically by every
/// operation below and is not repeated).
pub struct Tri {
    /// the leaf ^KG("out", g, s, p, o) has a value
    pub leaf: bool,
    /// children ^KG("out", g, s, p, o, ekey)
    pub kids: Set<int>,
    /// ^KG("out", g, s, p, o, "#")
    pub hash: Option<nat>,
}

pub open spec fn empty_tri() -> Tri { Tri { leaf: false, kids: Set::empty(), hash: None } }
pub open spec fn bare_leaf() -> Tri { Tri { leaf: true, kids: Set::empty(), hash: None } }

/// $Data(^KG("out", g, s, p, o)) > 0: the neighbour o is visible to every $Order reader.
pub open spec fn present(t: Tri) -> bool {
    t.leaf || !t.kids.is_empty() || t.hash is Some
}

/// Adj.Count's contribution of this triple (Adj.cls:114-122): "#" when it exists, else 1.
pub open spec fn contrib(t: Tri) -> nat {
    if !present(t) { 0 } else { match t.hash { Some(n) => n, None => 1 } }
}

/// L1 (spec 234 FR-004 and Clarifications 2026-09-26; spec 252 FR-001/FR-003; ADR-0010): in a
/// multigraph-mode graph the triple's entry is a function of its live rows — nothing for none, a
/// bare leaf for one (byte-identical to Put), leaf + one child per ekey + "#" = n for n >= 2.
pub open spec fn layout(rows: Set<int>) -> Tri {
    if rows.len() == 0 {
        empty_tri()
    } else if rows.len() == 1 {
        bare_leaf()
    } else {
        Tri { leaf: true, kids: rows, hash: Some(rows.len()) }
    }
}

/// Adjacency.Put on this triple (Adjacency.cls:87-88): sets the leaf.
pub open spec fn put(t: Tri) -> Tri { Tri { leaf: true, ..t } }

/// Adjacency.Remove (Adjacency.cls:152-153): Kill of the leaf node takes its whole subtree.
pub open spec fn remove(t: Tri) -> Tri { empty_tri() }

/// Adjacency.PutKeyed (Adjacency.cls:210-269) for the row with ekey e; `rows` are the triple's
/// rows as the callback's SQL sees them (the new row is already written; OtherEdgeKeys excludes e).
pub open spec fn put_keyed(t: Tri, rows: Set<int>, e: int) -> Tri {
    if !present(t) {
        put(t)                                             // 220-222
    } else {
        let has_hash = t.hash is Some;                     // 224
        let others = rows.remove(e);                       // 231 OtherEdgeKeys
        if !has_hash && others.len() == 0 {
            put(t)                                         // 234-237 weight refresh
        } else {
            let kids1 = if !has_hash { t.kids.union(others) } else { t.kids };   // 239-250
            let kids2 = kids1.insert(e);                   // 251-253
            Tri { leaf: true, kids: kids2, hash: Some(kids2.len()) }   // 255 KeyCount, 257 SetLeafFromLowest
        }
    }
}

/// Adjacency.RemoveKeyed (Adjacency.cls:275-321) for the row with ekey e; `rows` are the rows
/// after the delete.
pub open spec fn remove_keyed(t: Tri, rows: Set<int>, e: int) -> Tri {
    if t.hash is None {
        if rows.remove(e).len() > 0 { t } else { remove(t) }     // 281-287
    } else if !t.kids.contains(e) {
        t                                                         // 290
    } else {
        let kids1 = t.kids.remove(e);                             // 292-293
        if kids1.len() > 1 {
            Tri { leaf: t.leaf, kids: kids1, hash: Some(kids1.len()) }   // 296-299 (+ SetLeafFromLowest)
        } else if kids1.len() == 1 {
            Tri { leaf: true, kids: Set::empty(), hash: None }    // 303-311: the survivor becomes the leaf
        } else {
            Tri { leaf: t.leaf, kids: kids1, hash: None }         // 311
        }
    }
}

/// Adjacency.RowPut / RowRemove (Adjacency.cls:477-501): the functional index callbacks.
pub open spec fn row_put(t: Tri, rows: Set<int>, e: int, multi: bool) -> Tri {
    if multi { put_keyed(t, rows, e) } else { put(t) }
}

pub open spec fn row_remove(t: Tri, rows: Set<int>, e: int, multi: bool) -> Tri {
    if multi { remove_keyed(t, rows, e) } else { remove(t) }
}

/// LedgerApply.DeleteRelInternal (LedgerApply.cls:652-693) for the row FindEdge picked (ekey e):
/// DELETE by %ID (678) — with the index declared, the row's DeleteIndex callback runs RowRemove —
/// then `If $Data(^KG("out", tGKey, pS, pP, pO)) Do Adjacency.Remove(...)` (688-689).
pub open spec fn delete_rel_as_built(t: Tri, rows: Set<int>, e: int, multi: bool, indexed: bool) -> Tri {
    let rows2 = rows.remove(e);
    let t1 = if indexed { row_remove(t, rows2, e, multi) } else { t };
    if present(t1) { remove(t1) } else { t1 }
}

/// Proposal S4 + keyed: skip the extra Remove when the index already ran (as OpCreateRel does at
/// LedgerApply.cls:508), and in a non-indexed namespace remove by ekey in a multigraph.
pub open spec fn delete_rel_repaired(t: Tri, rows: Set<int>, e: int, multi: bool, indexed: bool) -> Tri {
    let rows2 = rows.remove(e);
    if indexed {
        row_remove(t, rows2, e, multi)
    } else if multi {
        remove_keyed(t, rows2, e)
    } else if present(t) {
        remove(t)
    } else {
        t
    }
}

// ---------------------------------------------------------------------------- lemmas

pub proof fn lemma_contrib_layout(rows: Set<int>)
    requires
    ensures
        contrib(layout(rows)) == rows.len(),
        present(layout(rows)) == (rows.len() > 0),
{
    if rows.len() >= 2 {
        assert(layout(rows).hash is Some);
    } else if rows.len() == 0 {
        assert(!present(layout(rows))) by {
            assert(Set::<int>::empty().is_empty());
        }
    }
}

pub proof fn lemma_len1_is_single(rows: Set<int>, e: int)
    requires
        rows.len() == 1,
        rows.contains(e),
    ensures
        rows == set![e],
{
    let r2 = rows.remove(e);
    assert(r2.len() == 0);
    assert(r2 =~= Set::<int>::empty()) by {
        if exists|x: int| r2.contains(x) {
            let x = choose|x: int| r2.contains(x);
            vstd::set_lib::lemma_set_empty_equivalency_len(r2);
        }
    }
    assert forall|x: int| rows.contains(x) <==> x == e by {
        if rows.contains(x) && x != e {
            assert(r2.contains(x));
        }
    }
    assert(rows =~= set![e]);
}

/// O2/O5 — WITH THE INDEX DECLARED (Adjacency.Indexed(): idx_edges_adj is the functional Graph.KG.AdjIndex,
/// Adjacency.cls:540-557) the index callback for an insert keeps the keyed layout (multigraph mode, one
/// writer). Without it no callback runs, and only the engine's own writers keep ^KG (CONTEXT.md:93-95).
pub proof fn lemma_row_put_keeps_layout(rows: Set<int>, e: int)
    requires
        !rows.contains(e),
    ensures
        row_put(layout(rows), rows.insert(e), e, true) == layout(rows.insert(e)),
{
    let t = layout(rows);
    let rows2 = rows.insert(e);
    assert(rows2.len() == rows.len() + 1);
    assert(rows2.remove(e) =~= rows);
    if rows.len() == 0 {
        assert(!present(t)) by { assert(Set::<int>::empty().is_empty()); }
        assert(put(t) =~= bare_leaf());
    } else if rows.len() == 1 {
        let a = choose|a: int| rows.contains(a);
        assert(rows.contains(a)) by {
            if !exists|a: int| rows.contains(a) {
                assert(rows =~= Set::<int>::empty());
            }
        }
        assert(present(t));
        let kids2 = Set::<int>::empty().union(rows).insert(e);
        assert(kids2 =~= rows2);
        assert(put_keyed(t, rows2, e) == Tri { leaf: true, kids: kids2, hash: Some(kids2.len()) });
    } else {
        assert(present(t));
        assert(rows.insert(e) =~= rows2);
    }
}

/// O2/O5 — WITH THE INDEX DECLARED, the index callback for a delete keeps the keyed layout: deleting one
/// parallel edge leaves the others' adjacency and degree (spec 252 FR-001 in multigraph mode).
pub proof fn lemma_row_remove_keeps_layout(rows: Set<int>, e: int)
    requires
        rows.contains(e),
    ensures
        row_remove(layout(rows), rows.remove(e), e, true) == layout(rows.remove(e)),
{
    let t = layout(rows);
    let rows2 = rows.remove(e);
    assert(rows2.len() == rows.len() - 1);
    if rows.len() == 1 {
        lemma_len1_is_single(rows, e);
        assert(rows2 =~= Set::<int>::empty());
        assert(rows2.remove(e) =~= Set::<int>::empty());
        assert(remove_keyed(t, rows2, e) == remove(t));
        assert(layout(rows2) == empty_tri());
    } else {
        assert(rows.len() >= 2);
        assert(t.kids == rows);
        assert(t.kids.remove(e) =~= rows2);
        if rows2.len() > 1 {
        } else {
            assert(rows2.len() == 1);
        }
    }
}

/// The degree consequence of the lemma above (index declared).
pub proof fn theorem_index_delete_keeps_parallel_edges(rows: Set<int>, e: int)
    requires
        rows.contains(e),
        rows.len() >= 2,
    ensures
        present(row_remove(layout(rows), rows.remove(e), e, true)),
        contrib(row_remove(layout(rows), rows.remove(e), e, true)) == rows.len() - 1,
{
    lemma_row_remove_keeps_layout(rows, e);
    lemma_contrib_layout(rows.remove(e));
}

/// A row delete that bypasses the engine (raw SQL DELETE, Cypher DELETE): with the index declared the row's
/// DeleteIndex callback runs RowRemove (AdjIndex.cls:23-26); without it nothing touches ^KG.
pub open spec fn sql_row_delete(t: Tri, rows: Set<int>, e: int, multi: bool, indexed: bool) -> Tri {
    if indexed { row_remove(t, rows.remove(e), e, multi) } else { t }
}

/// Qualifier made explicit (review R1-13): L1 "the index is a function of the rows after every committed
/// change by any path" is a property of a namespace WITH THE INDEX DECLARED.
pub proof fn theorem_declared_index_sql_delete_keeps_layout(rows: Set<int>, e: int)
    requires
        rows.contains(e),
    ensures
        sql_row_delete(layout(rows), rows, e, true, true) == layout(rows.remove(e)),
{
    lemma_row_remove_keeps_layout(rows, e);
}

/// ... and does not hold without it: a raw SQL delete of a namespace's only row leaves its entry (Drift by
/// design in an undeclared namespace, CONTEXT.md:93-95). Every §3 result other than the delete_rel ones is
/// therefore scoped to the declared index.
pub proof fn witness_undeclared_index_sql_delete_leaves_entry() {
    let rows = set![0int];
    assert(rows.remove(0) =~= Set::<int>::empty());
    let t = sql_row_delete(layout(rows), rows, 0, true, false);
    assert(present(t));
    assert(!present(layout(rows.remove(0)))) by { lemma_contrib_layout(rows.remove(0)); }
}

/// O5 L1 for the ledger path, proved for the proposal: delete_rel of one relationship leaves the
/// layout of the remaining rows, in indexed and non-indexed namespaces, mode on or off (mode off:
/// one row per triple, the FR-003 premise).
pub proof fn theorem_repaired_delete_rel_keeps_layout(rows: Set<int>, e: int, multi: bool, indexed: bool)
    requires
        rows.contains(e),
        multi || rows.len() == 1,
    ensures
        delete_rel_repaired(layout(rows), rows, e, multi, indexed) == layout(rows.remove(e)),
{
    lemma_row_remove_keeps_layout(rows, e);
    if !multi {
        lemma_len1_is_single(rows, e);
        assert(rows.remove(e) =~= Set::<int>::empty());
        assert(present(layout(rows)));
    }
}

/// F3 (CONFIRMED-BY-PROOF-OF-MODEL): as built, delete_rel of one of two parallel edges in an
/// indexed namespace leaves the surviving row with no adjacency entry: the index collapses the
/// triple to a bare leaf for the survivor, and line 689 then removes that leaf.
pub proof fn witness_ledger_delete_rel_drops_survivor_indexed() {
    let rows = set![0int, 1int];
    let t = layout(rows);
    assert(rows.len() == 2) by {
        assert(set![0int].insert(1int) =~= rows);
        assert(set![0int].len() == 1);
    }
    let rows2 = rows.remove(0);
    assert(rows2 =~= set![1int]);
    assert(rows2.len() == 1);
    lemma_row_remove_keeps_layout(rows, 0);
    let t1 = row_remove(t, rows2, 0, true);
    assert(t1 == bare_leaf());
    let t2 = delete_rel_as_built(t, rows, 0, true, true);
    assert(t2 == empty_tri());
    assert(!present(t2) && contrib(t2) == 0);
    // L1 asks for the survivor's bare leaf: one neighbour, degree 1
    lemma_contrib_layout(rows2);
    assert(contrib(layout(rows2)) == 1);
}

/// F3 in a non-indexed namespace: the extra Remove kills leaf, children and "#" together.
pub proof fn witness_ledger_delete_rel_drops_survivors_non_indexed() {
    let rows = set![0int, 1int, 2int];
    assert(rows.len() == 3) by {
        assert(set![0int].insert(1int) =~= set![0int, 1int]);
        assert(set![0int, 1int].insert(2int) =~= rows);
        assert(set![0int].len() == 1);
    }
    let t = layout(rows);
    let t2 = delete_rel_as_built(t, rows, 1, true, false);
    assert(present(t));
    assert(t2 == empty_tri());
    let rows2 = rows.remove(1);
    assert(rows2.len() == 2);
    lemma_contrib_layout(rows2);
    assert(contrib(layout(rows2)) == 2);
    assert(contrib(t2) == 0);
}

/// A valid outcome survives the as-built code: deleting the only edge of a triple (mode off or
/// on) removes it, as L1 requires.
pub proof fn witness_ledger_delete_rel_single_edge_is_right() {
    let rows = set![0int];
    assert(rows.len() == 1);
    assert(rows.remove(0) =~= Set::<int>::empty());
    lemma_row_remove_keeps_layout(rows, 0);
    assert(delete_rel_as_built(layout(rows), rows, 0, true, true) == layout(rows.remove(0)));
    assert(delete_rel_as_built(layout(rows), rows, 0, false, true) == layout(rows.remove(0)));
    assert(delete_rel_as_built(layout(rows), rows, 0, false, false) == layout(rows.remove(0)));
}

// ============================================================================ §4 algorithm cache token (O4, F1)
//
// Scope (review R1-13): `Add` moves the token on every content change. That holds for every row write only
// WITH THE INDEX DECLARED (spec 252 FR-004: every index change moves the token). Without it a raw SQL or
// Cypher write moves neither ^KG nor the token, and the cache answers stale by design (CONTEXT.md:93-95).
//
// One graph, one (algorithm, parameter hash) key of ^IVG.AlgoCache. The graph's content is the set
// of edges every process can read now (read-uncommitted); an answer is a function of that set, so
// the model takes the set itself as the answer (the most discriminating answer). Writers add fresh
// edges (deletion is symmetric and omitted).

pub struct AR {
    /// the token AlgoCache.Lookup read on its miss (AlgoCache.cls:29, iris_sql_store.py:958-959)
    pub ttok: nat,
    pub computed: bool,
    pub ans: Set<nat>,
}

pub struct AS {
    pub content: Set<nat>,
    /// ^KG("__version"): moved by $Increment only, never taken back by a rollback
    pub token: nat,
    /// ^IVG.AlgoCache(gKey, alg, hash) = $LB(token, payload)
    pub entry: Option<(nat, Set<nat>)>,
    /// the edges each open writer transaction added (visible, uncommitted)
    pub ws: Map<nat, Set<nat>>,
    pub rs: Map<nat, AR>,
}

/// `bump_after_rollback`: the repair BuildKG already applies to itself (TraversalBuild.cls:160-162)
/// extended to every rollback path (Txn.Undo 49-58, the Eraser and Ledger catches).
pub struct AV {
    pub bump_after_rollback: bool,
}

pub enum AA {
    Begin { w: nat },
    /// a write inside w: the row and its index entry, then $Increment(^KG("__version"))
    /// (e.g. Adjacency.Put, Adjacency.cls:87-92)
    Add { w: nat, e: nat },
    Commit { w: nat },
    Rollback { w: nat },
    /// AlgoCache.Lookup's miss: the token is read and handed back to Put later
    Miss { r: nat },
    /// the algorithm runs over the content it can read
    Compute { r: nat },
    /// AlgoCache.Put(…, token from the miss, payload) (AlgoCache.cls:46-51; iris_sql_store.py:970-976)
    Store { r: nat },
}

/// AlgoCache.Lookup's hit (AlgoCache.cls:32-34).
pub open spec fn a_served(s: AS) -> Option<Set<nat>> {
    match s.entry {
        Some(p) => if p.0 == s.token { Some(p.1) } else { None },
        None => None,
    }
}

pub open spec fn astep(s: AS, a: AA, v: AV) -> Option<AS> {
    match a {
        AA::Begin { w } =>
            if s.ws.contains_key(w) { None } else { Some(AS { ws: s.ws.insert(w, Set::empty()), ..s }) },
        AA::Add { w, e } =>
            if !s.ws.contains_key(w) || s.content.contains(e) {
                None
            } else {
                Some(AS {
                    content: s.content.insert(e),
                    token: s.token + 1,
                    ws: s.ws.insert(w, s.ws[w].insert(e)),
                    ..s
                })
            },
        AA::Commit { w } =>
            if !s.ws.contains_key(w) { None } else { Some(AS { ws: s.ws.remove(w), ..s }) },
        AA::Rollback { w } =>
            if !s.ws.contains_key(w) {
                None
            } else {
                Some(AS {
                    content: s.content.difference(s.ws[w]),
                    token: if v.bump_after_rollback { s.token + 1 } else { s.token },
                    ws: s.ws.remove(w),
                    ..s
                })
            },
        AA::Miss { r } =>
            if s.rs.contains_key(r) || a_served(s) is Some {
                None
            } else {
                Some(AS { rs: s.rs.insert(r, AR { ttok: s.token, computed: false, ans: Set::empty() }), ..s })
            },
        AA::Compute { r } =>
            if !s.rs.contains_key(r) || s.rs[r].computed {
                None
            } else {
                Some(AS { rs: s.rs.insert(r, AR { computed: true, ans: s.content, ..s.rs[r] }), ..s })
            },
        AA::Store { r } =>
            if !s.rs.contains_key(r) || !s.rs[r].computed {
                None
            } else {
                Some(AS { entry: Some((s.rs[r].ttok, s.rs[r].ans)), rs: s.rs.remove(r), ..s })
            },
    }
}

pub open spec fn ainv(s: AS) -> bool {
    &&& match s.entry {
        Some(p) => p.0 <= s.token && (p.0 == s.token ==> p.1 == s.content),
        None => true,
    }
    &&& forall|r: nat| #[trigger] s.rs.contains_key(r) ==>
            s.rs[r].ttok <= s.token && (s.rs[r].computed && s.rs[r].ttok == s.token ==> s.rs[r].ans == s.content)
}

pub proof fn lemma_a_init(s: AS)
    requires
        s.entry is None,
        forall|r: nat| !(#[trigger] s.rs.contains_key(r)),
    ensures
        ainv(s),
{
}

pub open spec fn av_repaired() -> AV { AV { bump_after_rollback: true } }
pub open spec fn av_as_built() -> AV { AV { bump_after_rollback: false } }

/// O4 L1 (CONTEXT.md:116-119, "a cached algorithm result is valid only while the token it was
/// computed under is current"; ADR-0012:23-25): an answer served from the cache is the answer
/// over the content readable now. Proved for the repair; the as-built rule fails (witness below).
pub proof fn theorem_repaired_algo_cache_sound(s: AS, a: AA)
    requires
        ainv(s),
        astep(s, a, av_repaired()) is Some,
    ensures
        ainv(astep(s, a, av_repaired())->Some_0),
        a_served(astep(s, a, av_repaired())->Some_0) is Some
            ==> a_served(astep(s, a, av_repaired())->Some_0)->Some_0 == astep(s, a, av_repaired())->Some_0.content,
{
    let v = av_repaired();
    let s2 = astep(s, a, v)->Some_0;
    match a {
        AA::Begin { w } => {
            assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies
                s2.rs[r].ttok <= s2.token && (s2.rs[r].computed && s2.rs[r].ttok == s2.token ==> s2.rs[r].ans == s2.content) by {
                assert(s.rs.contains_key(r));
            }
        },
        AA::Add { w, e } => {
            assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies
                s2.rs[r].ttok <= s2.token && (s2.rs[r].computed && s2.rs[r].ttok == s2.token ==> s2.rs[r].ans == s2.content) by {
                assert(s.rs.contains_key(r));
            }
        },
        AA::Commit { w } => {
            assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies
                s2.rs[r].ttok <= s2.token && (s2.rs[r].computed && s2.rs[r].ttok == s2.token ==> s2.rs[r].ans == s2.content) by {
                assert(s.rs.contains_key(r));
            }
        },
        AA::Rollback { w } => {
            assert forall|r: nat| #[trigger] s2.rs.contains_key(r) implies
                s2.rs[r].ttok <= s2.token && (s2.rs[r].computed && s2.rs[r].ttok == s2.token ==> s2.rs[r].ans == s2.content) by {
                assert(s.rs.contains_key(r));
            }
        },
        AA::Miss { r } => {
            assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies
                s2.rs[x].ttok <= s2.token && (s2.rs[x].computed && s2.rs[x].ttok == s2.token ==> s2.rs[x].ans == s2.content) by {
                if x != r { assert(s.rs.contains_key(x)); }
            }
        },
        AA::Compute { r } => {
            assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies
                s2.rs[x].ttok <= s2.token && (s2.rs[x].computed && s2.rs[x].ttok == s2.token ==> s2.rs[x].ans == s2.content) by {
                assert(s.rs.contains_key(x));
            }
        },
        AA::Store { r } => {
            assert(s.rs.contains_key(r));
            assert forall|x: nat| #[trigger] s2.rs.contains_key(x) implies
                s2.rs[x].ttok <= s2.token && (s2.rs[x].computed && s2.rs[x].ttok == s2.token ==> s2.rs[x].ans == s2.content) by {
                assert(s.rs.contains_key(x));
            }
        },
    }
}

pub open spec fn a_s0() -> AS {
    AS { content: Set::empty(), token: 7, entry: None, ws: Map::empty(), rs: Map::empty() }
}

/// F1 (CONFIRMED-BY-PROOF-OF-MODEL): W adds edge 1 (token 7 -> 8, uncommitted); R misses at 8,
/// computes over the uncommitted edge and stores under 8; W rolls back; the entry is current and
/// answers a graph that never committed, until any later write moves the token.
pub proof fn witness_rolled_back_write_poisons_algo_cache() {
    let v = av_as_built();
    let s0 = a_s0();
    let s1 = astep(s0, AA::Begin { w: 1 }, v)->Some_0;
    let s2 = astep(s1, AA::Add { w: 1, e: 1 }, v)->Some_0;
    assert(s2.token == 8 && s2.content == set![1nat]) by {
        assert(Set::<nat>::empty().insert(1nat) =~= set![1nat]);
    }
    let s3 = astep(s2, AA::Miss { r: 1 }, v)->Some_0;
    let s4 = astep(s3, AA::Compute { r: 1 }, v)->Some_0;
    let s5 = astep(s4, AA::Store { r: 1 }, v)->Some_0;
    assert(s5.ws.contains_key(1));
    let s6 = astep(s5, AA::Rollback { w: 1 }, v)->Some_0;
    assert(s6.content =~= Set::<nat>::empty());
    assert(s6.token == 8);
    assert(a_served(s6) == Some(set![1nat]));
    assert(a_served(s6)->Some_0 != s6.content) by {
        assert(set![1nat].contains(1nat));
    }
}

/// Under the repair the same schedule leaves the entry stale.
pub proof fn witness_bump_after_rollback_refuses_the_poison() {
    let v = av_repaired();
    let s0 = a_s0();
    let s1 = astep(s0, AA::Begin { w: 1 }, v)->Some_0;
    let s2 = astep(s1, AA::Add { w: 1, e: 1 }, v)->Some_0;
    let s3 = astep(s2, AA::Miss { r: 1 }, v)->Some_0;
    let s4 = astep(s3, AA::Compute { r: 1 }, v)->Some_0;
    let s5 = astep(s4, AA::Store { r: 1 }, v)->Some_0;
    let s6 = astep(s5, AA::Rollback { w: 1 }, v)->Some_0;
    assert(s6.token == 9);
    assert(a_served(s6) is None);
}

} // verus!
