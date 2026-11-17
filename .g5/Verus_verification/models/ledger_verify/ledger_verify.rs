// Verify: canonical projection of the tables, comparison with the replayed history, and adoption.
// As-built transcription at product 3eaa79cf (iteration 60).
//
// Deciding sources: replay.py read_canonical (nodes by ID across graphs, reserved properties left out, temporal-marked
// edge rows left out, statement IDs looked up only for naming), _drop_temporal_marked (the same rule on the replay side),
// compare (entries from replayed to canonical: a node or relationship only in the tables gives its existence and every
// label/property/qualifier; one only in the history gives its deletion alone; one on both sides gives the attribute
// differences), _adoption_items + LedgerGenesis.Adopt (the entries become records), GraphState.apply (a node or
// relationship deletion removes its attributes), verify (equal when there are no entries; adopts only when asked and
// there are entries).
//
// Premises: quiescent inputs (no writer between the record read and the table read; q-led-006); the replay side is the
// fold of the recorded history (reconstruction/ledger_content models); Adopt records the items it is given and the
// replayed fold of an adoption revision applies them (ledger_content `theorem_adoption_*`).
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
/// when absent.
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

/// The adoption revision replayed on top of the history: each entry sets or removes its fact; deleting an entity
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

// =============================================================== canonical projection (read_canonical)

/// Raw table rows: node rows carry a graph; property rows include reserved keys; edge rows carry the temporal marker.
pub struct Tables {
    pub node_rows: Set<(int, int)>,          // (id, graph)
    pub label_rows: Set<(int, int)>,         // (id, label)
    pub prop_rows: Map<(int, int), int>,     // (id, key) -> value
    pub edge_rows: Map<Tup, (bool, Map<int, int>)>, // tuple -> (temporal marker, qualifiers)
}

/// Reserved property keys `id` and `__graph`, abstracted as -1 and -2.
pub open spec fn reserved(k: int) -> bool { k == -1 || k == -2 }

pub open spec fn canon_get(t: Tables, f: Fact) -> Option<int> {
    match f {
        Fact::Node(n) => if exists|g: int| t.node_rows.contains((n, g)) { Some(0) } else { None },
        Fact::Label(n, l) => if t.label_rows.contains((n, l)) { Some(0) } else { None },
        Fact::Prop(n, k) => if !reserved(k) && t.prop_rows.contains_key((n, k)) { Some(t.prop_rows[(n, k)]) } else { None },
        Fact::Rel(r) => if t.edge_rows.contains_key(r) && !t.edge_rows[r].0 { Some(0) } else { None },
        Fact::Qual(r, k) => if t.edge_rows.contains_key(r) && !t.edge_rows[r].0 && t.edge_rows[r].1.contains_key(k) {
            Some(t.edge_rows[r].1[k]) } else { None },
    }
}

pub open spec fn canonical(t: Tables) -> View {
    |f: Fact| canon_get(t, f)
}

/// The replay side keyed by statement: statement id -> (tuple, temporal marker, qualifiers). _drop_temporal_marked
/// removes marked statements; the comparable view keys relationships by tuple (statement IDs are not compared).
pub type Stmts = Map<int, (Tup, bool, Map<int, int>)>;

pub open spec fn live_stmt(s: Stmts, r: Tup) -> bool {
    exists|id: int| #[trigger] s.contains_key(id) && s[id].0 == r && !s[id].1
}

pub open spec fn replay_rel_get(s: Stmts, f: Fact) -> Option<int> {
    match f {
        Fact::Rel(r) => if live_stmt(s, r) { Some(0) } else { None },
        _ => None,
    }
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

/// Adoption closes the difference: replaying the adoption revision on the history gives exactly the canonical view,
/// so the next verify is equal.
pub proof fn theorem_adoption_closes_the_difference(a: View, b: View)
    requires wf(a), wf(b),
    ensures
        agree(adopt(a, compare(a, b)), b),
        verify(adopt(a, compare(a, b)), b, false).result == Result::Equal,
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
    assert forall|f: Fact| #[trigger] compare(r, b)(f) is None by {
        assert(r(f) == b(f));
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
{
    let t2 = Tables { node_rows: t.node_rows.insert((n, h)), ..t };
    assert(t2.node_rows.contains((n, g)));
    assert(canon_get(t2, Fact::Node(n)) is Some);
    assert(canon_get(t, Fact::Node(n)) is Some);
}

/// Reserved properties are left out of the canonical view.
pub proof fn theorem_reserved_properties_left_out(t: Tables, n: int)
    ensures canonical(t)(Fact::Prop(n, -1)) is None, canonical(t)(Fact::Prop(n, -2)) is None,
{
}

/// A temporal edge's marked row is left out of the tables' view, and a marked statement out of the replay side, so a
/// direct temporal write between recorded nodes leaves verify equal; the same row unmarked is a governed relationship.
pub proof fn theorem_temporal_marked_rows_left_out(t: Tables, r: Tup, q: Map<int, int>, s: Stmts, id: int)
    requires !t.edge_rows.contains_key(r), forall|i: int| #[trigger] s.contains_key(i) ==> s[i].0 != r,
    ensures
        canonical(Tables { edge_rows: t.edge_rows.insert(r, (true, q)), ..t })(Fact::Rel(r)) is None,
        canonical(Tables { edge_rows: t.edge_rows.insert(r, (false, q)), ..t })(Fact::Rel(r)) is Some,
        replay_rel_get(s.insert(id, (r, true, q)), Fact::Rel(r)) is None,
        replay_rel_get(s.insert(id, (r, false, q)), Fact::Rel(r)) is Some,
{
    let s1 = s.insert(id, (r, true, q));
    assert(!live_stmt(s1, r)) by {
        assert forall|i: int| #[trigger] s1.contains_key(i) && s1[i].0 == r implies s1[i].1 by {
            if i != id { assert(s.contains_key(i)); }
        }
    }
    let s2 = s.insert(id, (r, false, q));
    assert(s2.contains_key(id) && s2[id].0 == r && !s2[id].1);
}

/// Statement IDs are not compared: the same tuple under two different statement IDs gives the same view.
pub proof fn theorem_statement_ids_not_compared(r: Tup, q: Map<int, int>, i: int, j: int)
    ensures
        replay_rel_get(Map::<int, (Tup, bool, Map<int, int>)>::empty().insert(i, (r, false, q)), Fact::Rel(r))
            == replay_rel_get(Map::<int, (Tup, bool, Map<int, int>)>::empty().insert(j, (r, false, q)), Fact::Rel(r)),
{
    let s1 = Map::<int, (Tup, bool, Map<int, int>)>::empty().insert(i, (r, false, q));
    let s2 = Map::<int, (Tup, bool, Map<int, int>)>::empty().insert(j, (r, false, q));
    assert(s1.contains_key(i) && s1[i].0 == r && !s1[i].1);
    assert(s2.contains_key(j) && s2[j].0 == r && !s2[j].1);
}

} // verus!
