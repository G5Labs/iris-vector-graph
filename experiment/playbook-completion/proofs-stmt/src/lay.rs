//! The layout of IVG's storage in a universe of the contract model (proofs-env2 `spec::U`), the abstraction `alpha`
//! from a contract state to the core Store contract's state (`proofs/src/store.rs`, imported unchanged), and the
//! statement-index invariant the erasure needs.
//!
//! Layout (pin 3eaa79cf; the correspondence lane's alpha, correspondence/CORRESPONDENCE.md section 2):
//! - a **governed row** (`CK::Gov`) is a row cell of Graph_KG.nodes, rdf_labels, rdf_props or rdf_edges; its Store key
//!   is (graph, id, edge) (`key_of`), its graph the row's COALESCE(graph_id, '') (`gr`);
//! - a **tuple entry** (`CK::Tuple`) is the global cell `^IVG.Ledger("tuple", s, p, o, graphKey)` of an edge key
//!   (Ledger.cls:9); `StoreS.stmts` is the set of keys whose tuple entry is defined;
//! - a **statement entry** (`CK::Stmt`) is `^IVG.Ledger("stmt", id) = $LB(s, p, o, graph, created, deleted)`
//!   (Ledger.cls:8, LedgerApply.cls:164). Its value is interned (`Val::Str(i)`); `dec[i]` is what EraseLedgerFor
//!   computes from it with `$ListGet` (Eraser.cls:1129, 1139): the graph and the tuple cell it names. `$LIST` is outside
//!   the Verus subset (X2-LIST, proofs-env2 PROOFS.md section 6): `dec` is a parameter of every theorem, constrained
//!   only by `lay_ok` (the tuple cell named lies in the graph named), premise ST-LIST.
use vstd::prelude::*;
use ivg_proofs_env2::spec::*;
use ivg_core_proofs::vocab::{Key, Tgt, member, outside};
use ivg_core_proofs::store::*;

verus! {

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum CK { Other, Gov, Stmt, Tuple }

/// Per cell: its kind, graph, Store id and whether it is an edge's; per interned string: its statement decoding.
pub struct Lay {
    pub kind: Seq<CK>,
    pub gr: Seq<int>,
    pub id: Seq<int>,
    pub edge: Seq<bool>,
    pub dec: Seq<Option<(int, usize)>>,
}

pub open spec fn key_of(ly: Lay, c: int) -> Key { Key { g: ly.gr[c], id: ly.id[c], edge: ly.edge[c] } }

pub open spec fn is_gov(u: U, ly: Lay, c: int) -> bool { 0 <= c < u.n() && ly.kind[c] == CK::Gov }

pub open spec fn is_tup(u: U, ly: Lay, c: int) -> bool { 0 <= c < u.n() && ly.kind[c] == CK::Tuple }

pub open spec fn is_stm(u: U, ly: Lay, c: int) -> bool { 0 <= c < u.n() && ly.kind[c] == CK::Stmt }

/// The ledger cells the head lock protects in this layout (the region R of proofs-env2's head-lock theorems).
pub open spec fn is_led(u: U, ly: Lay, c: int) -> bool { is_tup(u, ly, c) || is_stm(u, ly, c) }

pub open spec fn odg(o: Option<(int, usize)>) -> int { match o { Some(x) => x.0, None => 0 } }

pub open spec fn odc(o: Option<(int, usize)>) -> usize { match o { Some(x) => x.1, None => 0 } }

/// EraseLedgerFor's reading of a statement value (Eraser.cls:1129, 1139): its graph and the tuple cell it names.
pub open spec fn decv(ly: Lay, v: Val) -> Option<(int, usize)> {
    match v {
        Val::Str(i) => if (i as int) < ly.dec.len() { ly.dec[i as int] } else { None },
        _ => None,
    }
}

/// Every table of the universe exists (the contract's X-DDL is outside the subset: tables are static).
pub open spec fn tables_exist(u: U) -> bool {
    forall|t: int| 0 <= t < u.texists.len() ==> #[trigger] u.texists[t]
}

pub open spec fn lay_ok(u: U, ly: Lay) -> bool {
    &&& wf_univ(u)
    &&& u.n() <= usize::MAX
    &&& tables_exist(u)
    &&& ly.kind.len() == u.n()
    &&& ly.gr.len() == u.n()
    &&& ly.id.len() == u.n()
    &&& ly.edge.len() == u.n()
    // governed rows are rows; ledger cells are globals that cover no other cell (leaves)
    &&& forall|c: int| #[trigger] is_gov(u, ly, c) ==> u.is_row[c]
    &&& forall|c: int| #[trigger] is_led(u, ly, c) ==> is_glob(u, c)
    &&& forall|c: int, j: int| is_led(u, ly, c) && 0 <= j < u.n() && j != c ==> !#[trigger] covers(u, c, j)
    // a tuple entry is an edge's
    &&& forall|c: int| #[trigger] is_tup(u, ly, c) ==> ly.edge[c]
    // distinct governed rows have distinct Store keys
    &&& forall|c1: int, c2: int| #[trigger] is_gov(u, ly, c1) && #[trigger] is_gov(u, ly, c2) && key_of(ly, c1) == key_of(ly, c2) ==> c1 == c2
    // ST-LIST: a decoded statement names a tuple entry of the graph it names
    &&& forall|i: int| 0 <= i < ly.dec.len() && (#[trigger] ly.dec[i]) is Some ==>
            is_tup(u, ly, odc(ly.dec[i]) as int) && ly.gr[odc(ly.dec[i]) as int] == odg(ly.dec[i])
}

// ------------------------------------------------------------------------------------------------ statement index

/// Statement entry j names tuple cell c (EraseLedgerFor would kill c for it).
pub open spec fn named(u: U, ly: Lay, gv: Seq<Option<Val>>, j: int, c: int) -> bool {
    &&& is_stm(u, ly, j)
    &&& gv[j] is Some
    &&& gv[j]->Some_0 != Val::Empty
    &&& decv(ly, gv[j]->Some_0) is Some
    &&& odc(decv(ly, gv[j]->Some_0)) as int == c
}

/// Every defined tuple entry is named by a defined statement entry (AllocStmt writes both, LedgerApply.cls:162-165;
/// the correspondence lane's stmt/tuple bijection, checked on every trace).
pub open spec fn sx_ok(u: U, ly: Lay, gv: Seq<Option<Val>>) -> bool {
    forall|c: int| #[trigger] is_tup(u, ly, c) && gv[c] is Some ==> exists|j: int| #[trigger] named(u, ly, gv, j, c)
}

// ------------------------------------------------------------------------------------------------ alpha

pub open spec fn vint(v: Val) -> int {
    match v { Val::Num(n) => n as int, Val::Str(i) => i as int, _ => 0 }
}

/// Governed rows defined at cells j.. as a Store map.
pub open spec fn rows_from(u: U, ly: Lay, gv: Seq<Option<Val>>, j: nat) -> Map<Key, int>
    decreases u.n() - j
{
    if j >= u.n() {
        Map::empty()
    } else {
        let m = rows_from(u, ly, gv, j + 1);
        if is_gov(u, ly, j as int) && gv[j as int] is Some { m.insert(key_of(ly, j as int), vint(gv[j as int]->Some_0)) } else { m }
    }
}

/// Defined tuple entries at cells j.. as Store statement keys.
pub open spec fn stmts_from(u: U, ly: Lay, gv: Seq<Option<Val>>, j: nat) -> Set<Key>
    decreases u.n() - j
{
    if j >= u.n() {
        Set::empty()
    } else {
        let m = stmts_from(u, ly, gv, j + 1);
        if is_tup(u, ly, j as int) && gv[j as int] is Some { m.insert(key_of(ly, j as int)) } else { m }
    }
}

/// The abstraction to the core Store contract (proofs/src/store.rs): rows, statement index; `e` the open erasure,
/// which the handler theorems supply from the program point (it is not in storage).
pub open spec fn alpha(u: U, ly: Lay, gv: Seq<Option<Val>>, e: Option<Tgt>) -> StoreS {
    StoreS { rows: rows_from(u, ly, gv, 0), stmts: stmts_from(u, ly, gv, 0), erasing: e }
}

/// EraseGraph's target: every key of graph g.
pub open spec fn tg(g: int) -> Tgt { |k: Key| k.g == g }

// ------------------------------------------------------------------------------------------------ alpha lemmas

pub proof fn lemma_rows_from(u: U, ly: Lay, gv: Seq<Option<Val>>, j: nat, k: Key)
    requires lay_ok(u, ly), gv.len() == u.n(),
    ensures
        rows_from(u, ly, gv, j).contains_key(k) <==>
            exists|c: int| j <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && gv[c] is Some,
        forall|c: int| j <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && gv[c] is Some ==>
            rows_from(u, ly, gv, j)[k] == vint(gv[c]->Some_0),
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_rows_from(u, ly, gv, j + 1, k);
        let m = rows_from(u, ly, gv, j + 1);
        if is_gov(u, ly, j as int) && gv[j as int] is Some && key_of(ly, j as int) == k {
            assert forall|c: int| j <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && gv[c] is Some implies
                rows_from(u, ly, gv, j)[k] == vint(gv[c]->Some_0) by {
                assert(c == j as int);
            }
        } else {
            if rows_from(u, ly, gv, j).contains_key(k) {
                let c = choose|c: int| j + 1 <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && gv[c] is Some;
                assert(j <= c);
            }
            if exists|c: int| j <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && gv[c] is Some {
                let c = choose|c: int| j <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && gv[c] is Some;
                assert(c != j as int);
                assert(j + 1 <= c);
            }
        }
    }
}

pub proof fn lemma_stmts_from(u: U, ly: Lay, gv: Seq<Option<Val>>, j: nat, k: Key)
    requires lay_ok(u, ly), gv.len() == u.n(),
    ensures
        stmts_from(u, ly, gv, j).contains(k) <==>
            exists|c: int| j <= c && #[trigger] is_tup(u, ly, c) && key_of(ly, c) == k && gv[c] is Some,
    decreases u.n() - j,
{
    if j < u.n() {
        lemma_stmts_from(u, ly, gv, j + 1, k);
        if is_tup(u, ly, j as int) && gv[j as int] is Some && key_of(ly, j as int) == k {
        } else {
            if stmts_from(u, ly, gv, j).contains(k) {
                let c = choose|c: int| j + 1 <= c && #[trigger] is_tup(u, ly, c) && key_of(ly, c) == k && gv[c] is Some;
                assert(j <= c);
            }
            if exists|c: int| j <= c && #[trigger] is_tup(u, ly, c) && key_of(ly, c) == k && gv[c] is Some {
                let c = choose|c: int| j <= c && #[trigger] is_tup(u, ly, c) && key_of(ly, c) == k && gv[c] is Some;
                assert(c != j as int);
                assert(j + 1 <= c);
            }
        }
    }
}

/// Governed rows equal on every governed cell: the same Store rows.
pub proof fn lemma_rows_same(u: U, ly: Lay, a: Seq<Option<Val>>, b: Seq<Option<Val>>)
    requires lay_ok(u, ly), a.len() == u.n(), b.len() == u.n(),
        forall|c: int| #[trigger] is_gov(u, ly, c) ==> b[c] == a[c],
    ensures rows_from(u, ly, b, 0) == rows_from(u, ly, a, 0),
{
    let ra = rows_from(u, ly, a, 0);
    let rb = rows_from(u, ly, b, 0);
    assert forall|k: Key| #[trigger] rb.contains_key(k) == ra.contains_key(k) by {
        lemma_rows_from(u, ly, a, 0, k);
        lemma_rows_from(u, ly, b, 0, k);
        if rb.contains_key(k) {
            let c = choose|c: int| 0 <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && b[c] is Some;
            assert(a[c] is Some);
        }
        if ra.contains_key(k) {
            let c = choose|c: int| 0 <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && a[c] is Some;
            assert(b[c] is Some);
        }
    }
    assert forall|k: Key| #[trigger] rb.contains_key(k) implies rb[k] == ra[k] by {
        lemma_rows_from(u, ly, a, 0, k);
        lemma_rows_from(u, ly, b, 0, k);
        let c = choose|c: int| 0 <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && b[c] is Some;
        assert(a[c] is Some);
    }
    assert(rb.dom() =~= ra.dom());
    assert(rb =~= ra);
}

/// Governed rows of graph g gone, every other governed row unchanged: Store's `outside(rows, tg(g))`.
pub proof fn lemma_rows_outside(u: U, ly: Lay, a: Seq<Option<Val>>, b: Seq<Option<Val>>, g: int)
    requires lay_ok(u, ly), a.len() == u.n(), b.len() == u.n(),
        forall|c: int| #[trigger] is_gov(u, ly, c) ==> b[c] == (if ly.gr[c] == g { None::<Val> } else { a[c] }),
    ensures rows_from(u, ly, b, 0) == outside(rows_from(u, ly, a, 0), tg(g)),
{
    let ra = rows_from(u, ly, a, 0);
    let rb = rows_from(u, ly, b, 0);
    let ro = outside(ra, tg(g));
    assert forall|k: Key| #[trigger] rb.contains_key(k) == ro.contains_key(k) by {
        lemma_rows_from(u, ly, a, 0, k);
        lemma_rows_from(u, ly, b, 0, k);
        if rb.contains_key(k) {
            let c = choose|c: int| 0 <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && b[c] is Some;
            assert(ly.gr[c] != g);
            assert(a[c] is Some);
            assert(ra.contains_key(k));
            assert(!member(tg(g), k));
        }
        if ro.contains_key(k) {
            assert(ra.contains_key(k));
            assert(!member(tg(g), k));
            let c = choose|c: int| 0 <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && a[c] is Some;
            assert(ly.gr[c] == k.g);
            assert(b[c] is Some);
        }
    }
    assert forall|k: Key| #[trigger] rb.contains_key(k) implies rb[k] == ro[k] by {
        lemma_rows_from(u, ly, a, 0, k);
        lemma_rows_from(u, ly, b, 0, k);
        let c = choose|c: int| 0 <= c && #[trigger] is_gov(u, ly, c) && key_of(ly, c) == k && b[c] is Some;
        assert(ly.gr[c] != g);
        assert(a[c] is Some);
        assert(ro[k] == ra[k]);
    }
    assert(rb.dom() =~= ro.dom());
    assert(rb =~= ro);
}

/// Tuple entries equal on every tuple cell: the same Store statement index.
pub proof fn lemma_stmts_same(u: U, ly: Lay, a: Seq<Option<Val>>, b: Seq<Option<Val>>)
    requires lay_ok(u, ly), a.len() == u.n(), b.len() == u.n(),
        forall|c: int| #[trigger] is_tup(u, ly, c) ==> b[c] == a[c],
    ensures stmts_from(u, ly, b, 0) == stmts_from(u, ly, a, 0),
{
    let sa = stmts_from(u, ly, a, 0);
    let sb = stmts_from(u, ly, b, 0);
    assert forall|k: Key| #[trigger] sb.contains(k) == sa.contains(k) by {
        lemma_stmts_from(u, ly, a, 0, k);
        lemma_stmts_from(u, ly, b, 0, k);
        if sb.contains(k) {
            let c = choose|c: int| 0 <= c && #[trigger] is_tup(u, ly, c) && key_of(ly, c) == k && b[c] is Some;
            assert(a[c] is Some);
        }
        if sa.contains(k) {
            let c = choose|c: int| 0 <= c && #[trigger] is_tup(u, ly, c) && key_of(ly, c) == k && a[c] is Some;
            assert(b[c] is Some);
        }
    }
    assert(sb =~= sa);
}

/// Tuple entries of graph g gone, the others unchanged: Store's `stmts.filter(not in tg(g))`.
pub proof fn lemma_stmts_clean(u: U, ly: Lay, a: Seq<Option<Val>>, b: Seq<Option<Val>>, g: int)
    requires lay_ok(u, ly), a.len() == u.n(), b.len() == u.n(),
        forall|c: int| #[trigger] is_tup(u, ly, c) ==> b[c] == (if ly.gr[c] == g { None::<Val> } else { a[c] }),
    ensures stmts_from(u, ly, b, 0) == stmts_from(u, ly, a, 0).filter(|k: Key| !member(tg(g), k)),
{
    let sa = stmts_from(u, ly, a, 0);
    let sb = stmts_from(u, ly, b, 0);
    let sf = sa.filter(|k: Key| !member(tg(g), k));
    assert forall|k: Key| #[trigger] sb.contains(k) == sf.contains(k) by {
        lemma_stmts_from(u, ly, a, 0, k);
        lemma_stmts_from(u, ly, b, 0, k);
        if sb.contains(k) {
            let c = choose|c: int| 0 <= c && #[trigger] is_tup(u, ly, c) && key_of(ly, c) == k && b[c] is Some;
            assert(ly.gr[c] != g);
            assert(a[c] is Some);
            assert(sa.contains(k));
            assert(!member(tg(g), k));
        }
        if sf.contains(k) {
            assert(sa.contains(k));
            assert(!member(tg(g), k));
            let c = choose|c: int| 0 <= c && #[trigger] is_tup(u, ly, c) && key_of(ly, c) == k && a[c] is Some;
            assert(ly.gr[c] == k.g);
            assert(b[c] is Some);
        }
    }
    assert(sb =~= sf);
}

} // verus!
