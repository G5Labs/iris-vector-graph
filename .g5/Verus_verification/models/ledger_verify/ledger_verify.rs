// Verify: canonical projection of the tables, comparison with the replayed history, and adoption.
// As-built transcription at product 3eaa79cf (iteration 60; repaired in the iteration-60 repair after review 60).
//
// Deciding sources: replay.py read_canonical (nodes by ID across graphs; a node also exists through a label row or a
// non-reserved property row; reserved properties left out; an edge row whose qualifier `temporal` is the JSON boolean
// true left out; other qualifier values compared as text), _drop_temporal_marked (a replay statement whose qualifier
// `temporal` is the TEXT "true" left out), compare (entries from replayed to canonical: a node or relationship only in
// the tables gives its existence and every label/property/qualifier; one only in the history gives its deletion alone;
// one on both sides gives the attribute differences), _adoption_items + LedgerGenesis.Adopt (the entries become
// records), GraphState.apply (a node or relationship deletion removes its attributes), verify (equal when there are no
// entries; adopts only when asked and there are entries). LedgerApply.QualsJson / changeset._str_value: the ledger
// stores every qualifier as text (a Python True becomes "true").
//
// Repair (review 60 FE-1, FE-2): the tables' marker (JSON boolean) and the replay's marker (text "true") are separate
// rules, so a relationship whose `temporal` qualifier is the text "true" is in the tables but never in the replay:
// verify diverges for it whatever the history, and no adoption closes it. Canonical node existence now includes label
// and property rows, so every canonical view is well formed (the `wf(b)` premise is discharged for the tables side).
//
// Premises: quiescent inputs (no writer between the record read and the table read; q-led-006); the replay side is the
// fold of the recorded history (reconstruction/ledger_content models), with one comparable relationship per tuple;
// Adopt records the items it is given and the replayed fold of an adoption revision applies them (ledger_content
// `theorem_adoption_*`); the drop rule then runs again on every later verify (`redrop`).
use vstd::prelude::*;

verus! {

pub type Tup = (int, int, int, int);  // source, predicate, target, graph

/// One comparable fact: a node or relationship's existence, or one of their attributes.
pub enum Fact { Node(int), Label(int, int), Prop(int, int), Rel(Tup), Qual(Tup, int) }

/// The entity a fact belongs to (its existence fact); None for existence facts.
pub open spec fn owner(f: Fact) -> Option<Fact> {
    match f {
        Fact::Label(n, _) => Some(Fact::Node(n)),
        Fact::Prop(n, _) => Some(Fact::Node(n)),
        Fact::Qual(t, _) => Some(Fact::Rel(t)),
        _ => None,
    }
}

/// A comparable view (GraphState.as_comparable) as a total function: fact → value (0 for existence and labels), None
/// when absent. Qualifier values are text.
pub type View = spec_fn(Fact) -> Option<int>;

/// An entry list keyed by fact: None = no entry; Some(x) = an entry whose canonical-side value is x.
pub type Delta = spec_fn(Fact) -> Option<Option<int>>;

pub open spec fn agree(a: View, b: View) -> bool {
    forall|f: Fact| #[trigger] a(f) == b(f)
}

/// Every attribute's entity is present.
pub open spec fn wf(v: View) -> bool {
    forall|f: Fact| #[trigger] v(f) is Some && owner(f) is Some ==> v(owner(f)->Some_0) is Some
}

/// compare(replayed, canonical): one entry per differing fact, except the attributes of an entity that only the history
/// still has (its deletion entry stands for them). Entry value = the canonical side's value (None = absent).
pub open spec fn emitted(a: View, b: View, f: Fact) -> bool {
    a(f) != b(f) && !(owner(f) is Some && a(owner(f)->Some_0) is Some && b(owner(f)->Some_0) is None)
}

pub open spec fn compare(a: View, b: View) -> Delta {
    |f: Fact| if emitted(a, b, f) { Some(b(f)) } else { None }
}

pub open spec fn no_entries(d: Delta) -> bool {
    forall|f: Fact| #[trigger] d(f) is None
}

/// The adoption revision folded on top of the history: each entry sets or removes its fact; deleting an entity
/// removes its attributes (GraphState.apply of delete_node / delete_rel).
pub open spec fn adopted_get(a: View, d: Delta, f: Fact) -> Option<int> {
    if d(f) is Some {
        d(f)->Some_0
    } else if owner(f) is Some && d(owner(f)->Some_0) is Some && d(owner(f)->Some_0)->Some_0 is None {
        None
    } else {
        a(f)
    }
}

pub open spec fn adopt(a: View, d: Delta) -> View {
    |f: Fact| adopted_get(a, d, f)
}

pub enum Result { Equal, Diverges }

pub struct Report { pub result: Result, pub adoption: bool }

/// replay.verify: equal when compare finds nothing; an adoption revision only when asked and needed.
pub open spec fn verify(a: View, b: View, adopt_asked: bool) -> Report {
    let empty = no_entries(compare(a, b));
    Report { result: if empty { Result::Equal } else { Result::Diverges }, adoption: adopt_asked && !empty }
}

// =============================================================== the two temporal-marker rules

/// Qualifier key `temporal`, and the texts "true" / "false" (abstract text codes).
pub open spec fn k_temporal() -> int { 0 }
pub open spec fn t_true() -> int { 1 }
pub open spec fn t_false() -> int { 2 }

/// A qualifier value as the rdf_edges.qualifiers JSON holds it: a JSON boolean, or any other value (string, number,
/// object, list), which read_canonical turns into text.
pub enum QVal { Bool(bool), Text(int) }

/// read_canonical's conversion: a boolean becomes "true"/"false"; anything else its text.
pub open spec fn text_of(v: QVal) -> int {
    match v { QVal::Bool(b) => if b { t_true() } else { t_false() }, QVal::Text(x) => x }
}

/// The TABLES' rule (read_canonical): the row is left out when `temporal` is the JSON boolean true.
pub open spec fn table_marked(q: Map<int, QVal>) -> bool {
    q.contains_key(k_temporal()) && q[k_temporal()] == QVal::Bool(true)
}

/// The REPLAY's rule (_drop_temporal_marked): the statement is left out when `temporal` is the text "true".
pub open spec fn replay_marked(q: Map<int, int>) -> bool {
    q.contains_key(k_temporal()) && q[k_temporal()] == t_true()
}

/// LedgerApply.QualsJson: a ledger commit stores the statement's qualifiers in the row as text, key for key.
pub open spec fn stores_as_text(row: Map<int, QVal>, q: Map<int, int>) -> bool {
    &&& forall|k: int| #[trigger] row.contains_key(k) <==> q.contains_key(k)
    &&& forall|k: int| #[trigger] q.contains_key(k) ==> row[k] == QVal::Text(q[k])
}

// =============================================================== canonical projection (read_canonical)

/// Raw table rows: node rows carry a graph; property rows include reserved keys; edge rows carry their qualifier JSON.
pub struct Tables {
    pub node_rows: Set<(int, int)>,          // (id, graph)
    pub label_rows: Set<(int, int)>,         // (id, label)
    pub prop_rows: Map<(int, int), int>,     // (id, key) -> value
    pub edge_rows: Map<Tup, Map<int, QVal>>, // tuple -> stored qualifiers
}

/// Reserved property keys `id` and `__graph`, abstracted as -1 and -2.
pub open spec fn reserved(k: int) -> bool { k == -1 || k == -2 }

/// A node exists in the tables' view when it has a node row in any graph, a label row, or a non-reserved property row
/// (read_canonical's `setdefault`; a reserved property is skipped before it).
pub open spec fn canon_node(t: Tables, n: int) -> bool {
    (exists|g: int| #[trigger] t.node_rows.contains((n, g)))
    || (exists|l: int| #[trigger] t.label_rows.contains((n, l)))
    || (exists|k: int| #[trigger] t.prop_rows.contains_key((n, k)) && !reserved(k))
}

pub open spec fn canon_get(t: Tables, f: Fact) -> Option<int> {
    match f {
        Fact::Node(n) => if canon_node(t, n) { Some(0) } else { None },
        Fact::Label(n, l) => if t.label_rows.contains((n, l)) { Some(0) } else { None },
        Fact::Prop(n, k) => if !reserved(k) && t.prop_rows.contains_key((n, k)) { Some(t.prop_rows[(n, k)]) } else { None },
        Fact::Rel(r) => if t.edge_rows.contains_key(r) && !table_marked(t.edge_rows[r]) { Some(0) } else { None },
        Fact::Qual(r, k) => if t.edge_rows.contains_key(r) && !table_marked(t.edge_rows[r]) && t.edge_rows[r].contains_key(k) {
            Some(text_of(t.edge_rows[r][k])) } else { None },
    }
}

pub open spec fn canonical(t: Tables) -> View {
    |f: Fact| canon_get(t, f)
}

// =============================================================== replay side (_drop_temporal_marked, as_comparable)

/// The replay side keyed by statement: statement id -> (tuple, text qualifiers). Statement IDs are not compared.
pub type Stmts = Map<int, (Tup, Map<int, int>)>;

pub open spec fn live_id(s: Stmts, r: Tup, id: int) -> bool {
    s.contains_key(id) && s[id].0 == r && !replay_marked(s[id].1)
}

pub open spec fn live_stmt(s: Stmts, r: Tup) -> bool {
    exists|id: int| #[trigger] live_id(s, r, id)
}

/// The relationship facts of the replay after the drop rule: a tuple is present when a statement on it survives the
/// drop; its qualifiers are that statement's.
pub open spec fn replay_rel_get(s: Stmts, f: Fact) -> Option<int> {
    match f {
        Fact::Rel(r) => if live_stmt(s, r) { Some(0) } else { None },
        Fact::Qual(r, k) => if live_stmt(s, r) {
            let id = choose|id: int| live_id(s, r, id);
            if s[id].1.contains_key(k) { Some(s[id].1[k]) } else { None }
        } else { None },
        _ => None,
    }
}

/// The replayed comparable view: node facts from the fold `nv`, relationship facts from the surviving statements.
pub open spec fn replay_view(nv: View, s: Stmts) -> View {
    |f: Fact| match f {
        Fact::Rel(_) => replay_rel_get(s, f),
        Fact::Qual(_, _) => replay_rel_get(s, f),
        _ => nv(f),
    }
}

/// A view the drop rule has run on: no relationship carries temporal text "true".
pub open spec fn dropped(v: View) -> bool {
    forall|r: Tup| #[trigger] v(Fact::Qual(r, k_temporal())) != Some(t_true())
}

/// The tables hold no relationship whose temporal qualifier reads as text "true" (the scope of adoption closing).
pub open spec fn no_text_marker(b: View) -> bool {
    forall|r: Tup| #[trigger] b(Fact::Qual(r, k_temporal())) != Some(t_true())
}

/// The next verify's replay of history + adoption: the fold applies the entries (adopt), then the drop rule runs again
/// and leaves out every relationship whose temporal qualifier text is "true", with its qualifiers.
pub open spec fn redrop(v: View) -> View {
    |f: Fact| match f {
        Fact::Rel(r) => if v(Fact::Qual(r, k_temporal())) == Some(t_true()) { None } else { v(f) },
        Fact::Qual(r, _) => if v(Fact::Qual(r, k_temporal())) == Some(t_true()) { None } else { v(f) },
        _ => v(f),
    }
}

pub open spec fn replay_after_adoption(a: View, d: Delta) -> View {
    redrop(adopt(a, d))
}

// =============================================================== theorems

/// Equal exactly when the two views agree (for well-formed views).
pub proof fn theorem_equal_iff_views_agree(a: View, b: View)
    requires wf(a), wf(b),
    ensures (verify(a, b, false).result == Result::Equal) <==> agree(a, b),
{
    if verify(a, b, false).result == Result::Equal {
        assert forall|f: Fact| #[trigger] a(f) == b(f) by {
            if a(f) != b(f) {
                if owner(f) is Some && a(owner(f)->Some_0) is Some && b(owner(f)->Some_0) is None {
                    let o = owner(f)->Some_0;
                    assert(owner(o) is None) by { assert(o is Node || o is Rel); }
                    assert(emitted(a, b, o));
                    assert(compare(a, b)(o) is Some);
                } else {
                    assert(emitted(a, b, f));
                    assert(compare(a, b)(f) is Some);
                }
            }
        }
    } else {
        if agree(a, b) {
            assert forall|f: Fact| #[trigger] compare(a, b)(f) is None by {
                assert(a(f) == b(f));
            }
        }
    }
}

/// Every canonical view is well formed: a label, property or qualifier implies its node or relationship (FE-2: a label
/// or property row with no node row still makes the node).
pub proof fn lemma_canonical_wf(t: Tables)
    ensures wf(canonical(t)),
{
    let b = canonical(t);
    assert forall|f: Fact| #[trigger] b(f) is Some && owner(f) is Some implies b(owner(f)->Some_0) is Some by {
        match f {
            Fact::Label(n, l) => { assert(t.label_rows.contains((n, l))); assert(canon_node(t, n)); }
            Fact::Prop(n, k) => { assert(t.prop_rows.contains_key((n, k)) && !reserved(k)); assert(canon_node(t, n)); }
            _ => {}
        }
    }
}

/// A property row on an ID with no node row (a post-commit property, an orphan row) makes the node in the tables'
/// view: against a history without that node, verify reports the node's existence and the property, as the product
/// does. A reserved property alone makes no node.
pub proof fn theorem_orphan_property_reports_node(t: Tables, n: int, k: int, a: View)
    requires t.prop_rows.contains_key((n, k)), !reserved(k), a(Fact::Node(n)) is None, a(Fact::Prop(n, k)) is None,
    ensures
        compare(a, canonical(t))(Fact::Node(n)) == Some(Some(0int)),
        compare(a, canonical(t))(Fact::Prop(n, k)) == Some(Some(t.prop_rows[(n, k)])),
        canonical(Tables { node_rows: Set::empty(), label_rows: Set::empty(), prop_rows: Map::empty().insert((n, -1int), 7int), ..t })(Fact::Node(n)) is None,
{
    assert(t.prop_rows.contains_key((n, k)) && !reserved(k));
    assert(canon_node(t, n));
    let t0 = Tables { node_rows: Set::empty(), label_rows: Set::empty(), prop_rows: Map::empty().insert((n, -1int), 7int), ..t };
    assert(!canon_node(t0, n)) by {
        assert forall|g: int| !(#[trigger] t0.node_rows.contains((n, g))) by {}
        assert forall|l: int| !(#[trigger] t0.label_rows.contains((n, l))) by {}
        assert forall|k2: int| !(#[trigger] t0.prop_rows.contains_key((n, k2)) && !reserved(k2)) by {
            if t0.prop_rows.contains_key((n, k2)) { assert(k2 == -1); }
        }
    }
}

pub proof fn lemma_adopt_agrees(a: View, b: View)
    requires wf(a), wf(b),
    ensures forall|f: Fact| #[trigger] adopt(a, compare(a, b))(f) == b(f),
{
    let d = compare(a, b);
    let r = adopt(a, d);
    assert forall|f: Fact| #[trigger] r(f) == b(f) by {
        assert(r(f) == adopted_get(a, d, f));
        if d(f) is Some {
        } else if owner(f) is Some && d(owner(f)->Some_0) is Some && d(owner(f)->Some_0)->Some_0 is None {
            let o = owner(f)->Some_0;
            assert(b(o) is None);
            if b(f) is Some { assert(b(o) is Some); }
        } else {
            if a(f) != b(f) {
                let o = owner(f)->Some_0;
                assert(owner(o) is None) by { assert(o is Node || o is Rel); }
                assert(emitted(a, b, o));
            }
        }
    }
}

/// Adoption closes the difference WHEN no relationship of the tables carries temporal text "true": the replay of
/// history + adoption revision (drop rule applied again) gives exactly the canonical view, so the next verify is equal.
/// Narrowed in the repair: without `no_text_marker(b)` the claim is false (see the next two theorems).
pub proof fn theorem_adoption_closes_the_difference(a: View, b: View)
    requires wf(a), wf(b), no_text_marker(b),
    ensures
        agree(replay_after_adoption(a, compare(a, b)), b),
        verify(replay_after_adoption(a, compare(a, b)), b, false).result == Result::Equal,
{
    lemma_adopt_agrees(a, b);
    let v = adopt(a, compare(a, b));
    let r = replay_after_adoption(a, compare(a, b));
    assert forall|f: Fact| #[trigger] r(f) == b(f) by {
        match f {
            Fact::Rel(t) => { assert(v(Fact::Qual(t, k_temporal())) == b(Fact::Qual(t, k_temporal()))); assert(v(f) == b(f)); }
            Fact::Qual(t, _) => { assert(v(Fact::Qual(t, k_temporal())) == b(Fact::Qual(t, k_temporal()))); assert(v(f) == b(f)); }
            _ => { assert(v(f) == b(f)); }
        }
    }
    assert forall|f: Fact| #[trigger] compare(r, b)(f) is None by {
        assert(r(f) == b(f));
    }
}

/// The two marker rules: a row whose temporal qualifier is the JSON boolean true is left out of the tables, but the
/// same row with the TEXT "true" is kept; a statement whose temporal qualifier is the text "true" is left out of the
/// replay, and one with any other text (e.g. "yes") is kept. So a direct temporal write (JSON true, no statement)
/// leaves verify equal, while a relationship stored with temporal text "true" is in the tables only.
pub proof fn theorem_temporal_marked_rows_left_out(t: Tables, r: Tup, q: Map<int, QVal>, s: Stmts, p: Map<int, int>, id: int, y: int)
    requires !t.edge_rows.contains_key(r), forall|i: int| #[trigger] s.contains_key(i) ==> s[i].0 != r, y != t_true(),
    ensures
        canonical(Tables { edge_rows: t.edge_rows.insert(r, q.insert(k_temporal(), QVal::Bool(true))), ..t })(Fact::Rel(r)) is None,
        canonical(Tables { edge_rows: t.edge_rows.insert(r, q.insert(k_temporal(), QVal::Text(t_true()))), ..t })(Fact::Rel(r)) is Some,
        replay_rel_get(s.insert(id, (r, p.insert(k_temporal(), t_true()))), Fact::Rel(r)) is None,
        replay_rel_get(s.insert(id, (r, p.insert(k_temporal(), y))), Fact::Rel(r)) is Some,
{
    let qt = q.insert(k_temporal(), QVal::Text(t_true()));
    assert(!table_marked(qt)) by { assert(qt[k_temporal()] == QVal::Text(t_true())); }
    let s1 = s.insert(id, (r, p.insert(k_temporal(), t_true())));
    assert(!live_stmt(s1, r)) by {
        assert forall|i: int| !(#[trigger] live_id(s1, r, i)) by {
            if i != id && s1.contains_key(i) { assert(s.contains_key(i)); }
        }
    }
    let s2 = s.insert(id, (r, p.insert(k_temporal(), y)));
    assert(live_id(s2, r, id));
}

/// The replay side never carries temporal text "true": the drop rule removed every such statement.
pub proof fn lemma_replay_view_dropped(nv: View, s: Stmts)
    ensures dropped(replay_view(nv, s)),
{
    let a = replay_view(nv, s);
    assert forall|r: Tup| #[trigger] a(Fact::Qual(r, k_temporal())) != Some(t_true()) by {
        if live_stmt(s, r) {
            let id = choose|id: int| live_id(s, r, id);
            assert(live_id(s, r, id));
            assert(!replay_marked(s[id].1));
        }
    }
}

/// A relationship stored with temporal text "true" makes every verify diverge, whatever the history and however many
/// adoptions it holds: the tables keep the row (not the JSON-true marker), the replay drops every statement carrying
/// that text. Every verify(adopt=True) therefore writes another adoption revision (review 60 FE-1, bug-led-013).
pub proof fn theorem_text_marker_never_equal(t: Tables, nv: View, s: Stmts, r: Tup, asked: bool)
    requires t.edge_rows.contains_key(r), t.edge_rows[r].contains_key(k_temporal()),
        t.edge_rows[r][k_temporal()] == QVal::Text(t_true()),
    ensures
        verify(replay_view(nv, s), canonical(t), asked).result == Result::Diverges,
        verify(replay_view(nv, s), canonical(t), true).adoption,
        compare(replay_view(nv, s), canonical(t))(Fact::Qual(r, k_temporal())) == Some(Some(t_true())),
{
    let a = replay_view(nv, s);
    let b = canonical(t);
    let f = Fact::Qual(r, k_temporal());
    lemma_replay_view_dropped(nv, s);
    assert(a(f) != Some(t_true()));
    assert(!table_marked(t.edge_rows[r]));
    assert(b(f) == Some(t_true()));
    assert(b(Fact::Rel(r)) is Some);
    assert(emitted(a, b, f));
    assert(compare(a, b)(f) is Some);
}

/// The same at the view level of the adoption: after adopting a text-"true" relationship, the next replay drops it
/// again, so the next verify still diverges on it (and adopts again when asked).
pub proof fn theorem_adoption_never_closes_a_text_marker(a: View, b: View, r: Tup)
    requires wf(a), wf(b), b(Fact::Qual(r, k_temporal())) == Some(t_true()),
    ensures
        replay_after_adoption(a, compare(a, b))(Fact::Rel(r)) is None,
        b(Fact::Rel(r)) is Some,
        verify(replay_after_adoption(a, compare(a, b)), b, false).result == Result::Diverges,
        dropped(replay_after_adoption(a, compare(a, b))),
{
    lemma_adopt_agrees(a, b);
    let v = adopt(a, compare(a, b));
    let a2 = replay_after_adoption(a, compare(a, b));
    assert(v(Fact::Qual(r, k_temporal())) == b(Fact::Qual(r, k_temporal())));
    assert(b(Fact::Rel(r)) is Some) by { assert(owner(Fact::Qual(r, k_temporal())) == Some(Fact::Rel(r))); }
    assert(emitted(a2, b, Fact::Rel(r)));
    assert(compare(a2, b)(Fact::Rel(r)) is Some);
    assert forall|x: Tup| #[trigger] a2(Fact::Qual(x, k_temporal())) != Some(t_true()) by {}
}

/// A ledger commit stores its qualifiers as text: with `temporal` = "true" (or a Python True, which `_str_value`
/// turns into "true") the committed relationship is in the tables and not in the replay; with any other text (e.g.
/// "yes") it is on both sides.
pub proof fn theorem_marker_rules_differ(row: Map<int, QVal>, q: Map<int, int>, t: Tables, r: Tup, id: int)
    requires stores_as_text(row, q), q.contains_key(k_temporal()), t.edge_rows.contains_key(r), t.edge_rows[r] == row,
    ensures
        canonical(t)(Fact::Rel(r)) is Some,
        canonical(t)(Fact::Qual(r, k_temporal())) == Some(q[k_temporal()]),
        q[k_temporal()] == t_true() ==> replay_rel_get(Map::<int, (Tup, Map<int, int>)>::empty().insert(id, (r, q)), Fact::Rel(r)) is None,
        q[k_temporal()] != t_true() ==> replay_rel_get(Map::<int, (Tup, Map<int, int>)>::empty().insert(id, (r, q)), Fact::Rel(r)) is Some,
{
    assert(row.contains_key(k_temporal()));
    assert(row[k_temporal()] == QVal::Text(q[k_temporal()]));
    assert(!table_marked(row));
    let s = Map::<int, (Tup, Map<int, int>)>::empty().insert(id, (r, q));
    if q[k_temporal()] == t_true() {
        assert forall|i: int| !(#[trigger] live_id(s, r, i)) by {}
    } else {
        assert(live_id(s, r, id));
    }
}

pub open spec fn view_a(m: int, k2: int, v2: int) -> View {
    |f: Fact| match f {
        Fact::Node(x) => if x == m { Some(0int) } else { None },
        Fact::Prop(x, k) => if x == m && k == k2 { Some(v2) } else { None },
        _ => None,
    }
}

pub open spec fn view_b(n: int, l: int, k1: int, v: int) -> View {
    |f: Fact| match f {
        Fact::Node(x) => if x == n { Some(0int) } else { None },
        Fact::Label(x, y) => if x == n && y == l { Some(0int) } else { None },
        Fact::Prop(x, k) => if x == n && k == k1 { Some(v) } else { None },
        _ => None,
    }
}

/// An unrecorded node with a label and a property gives its existence, label and property entries; an unrecorded
/// deletion of a recorded node gives its deletion entry alone.
pub proof fn theorem_entries_for_created_and_deleted_nodes(n: int, l: int, k: int, v: int, m: int, k2: int, v2: int)
    requires n != m,
    ensures ({
        let d = compare(view_a(m, k2, v2), view_b(n, l, k, v));
        &&& d(Fact::Node(n)) == Some(Some(0int)) && d(Fact::Label(n, l)) == Some(Some(0int)) && d(Fact::Prop(n, k)) == Some(Some(v))
        &&& d(Fact::Node(m)) == Some(None::<int>)
        &&& d(Fact::Prop(m, k2)) is None
    }),
{
}

/// No adoption revision when the views agree, even when adoption is asked; verify without adopt never adopts.
pub proof fn theorem_adoption_only_when_needed(a: View, b: View)
    ensures
        agree(a, b) ==> !verify(a, b, true).adoption,
        !verify(a, b, false).adoption,
{
    if agree(a, b) {
        assert forall|f: Fact| #[trigger] compare(a, b)(f) is None by {
            assert(a(f) == b(f));
        }
    }
}

/// Nodes are matched by ID across graphs: the same ID held only in a named graph counts as the node.
pub proof fn theorem_node_identity_ignores_graph(t: Tables, n: int, g: int, h: int)
    requires t.node_rows.contains((n, g)),
    ensures
        canonical(t)(Fact::Node(n)) is Some,
        canonical(Tables { node_rows: t.node_rows.insert((n, h)), ..t })(Fact::Node(n)) is Some,
        canonical(Tables { node_rows: Set::empty().insert((n, h)), label_rows: Set::empty(), prop_rows: Map::empty(), ..t })(Fact::Node(n)) is Some,
{
    let t2 = Tables { node_rows: t.node_rows.insert((n, h)), ..t };
    assert(t2.node_rows.contains((n, g)));
    assert(canon_get(t2, Fact::Node(n)) is Some);
    assert(canon_get(t, Fact::Node(n)) is Some);
    let t3 = Tables { node_rows: Set::empty().insert((n, h)), label_rows: Set::empty(), prop_rows: Map::empty(), ..t };
    assert(t3.node_rows.contains((n, h)));
}

/// Reserved properties are left out of the canonical view.
pub proof fn theorem_reserved_properties_left_out(t: Tables, n: int)
    ensures canonical(t)(Fact::Prop(n, -1)) is None, canonical(t)(Fact::Prop(n, -2)) is None,
{
}

/// Statement IDs are not compared: the same tuple under two different statement IDs gives the same view.
pub proof fn theorem_statement_ids_not_compared(r: Tup, q: Map<int, int>, i: int, j: int)
    requires !replay_marked(q),
    ensures
        replay_rel_get(Map::<int, (Tup, Map<int, int>)>::empty().insert(i, (r, q)), Fact::Rel(r))
            == replay_rel_get(Map::<int, (Tup, Map<int, int>)>::empty().insert(j, (r, q)), Fact::Rel(r)),
{
    let s1 = Map::<int, (Tup, Map<int, int>)>::empty().insert(i, (r, q));
    let s2 = Map::<int, (Tup, Map<int, int>)>::empty().insert(j, (r, q));
    assert(live_id(s1, r, i));
    assert(live_id(s2, r, j));
}

} // verus!
