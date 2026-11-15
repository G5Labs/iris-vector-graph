// IVG rebuilt-store freshness: a store is current only when it carries a build stamp equal to the live token.
// Verus model, consolidated uplift (2026-11-14). Product baseline 3eaa79cf. As-built transcription of
//   iris_vector_graph/freshness.py   Freshness._read_int :45-52, token :54-57, built_from :66-68, is_current :70-72,
//                                    stale_stores :74-77
//   iris_src/src/Graph/KG/TraversalKHop.cls  Fresh :237-243 (the run-time reader of the two-hop counts)
// It does not verify the product's bodies; bindings are in NOTES.md.
//
// Run:  $VERUS_BIN freshness_stamp.rs --crate-type=lib --num-threads 4 --triggers-mode silent
use vstd::prelude::*;

verus! {

/// A global node as the host reads it: no value ($Data # 2 = 0, including a node with children only), the empty
/// string, or a canonical integer.
pub enum Val {
    Unset,
    Empty,
    Int(int),
}

/// Freshness._read_int: "the integer at name(sub), or None while it is unset or empty".
pub open spec fn read_int(v: Val) -> Option<int> {
    match v {
        Val::Unset => None,
        Val::Empty => None,
        Val::Int(i) => Some(i),
    }
}

/// Freshness.token: the token, or 0 while it is unset.
pub open spec fn token(t: Val) -> int {
    match read_int(t) {
        None => 0,
        Some(i) => i,
    }
}

/// Freshness.built_from: the stamp, or None ("not known") if never stamped.
pub open spec fn built_from(s: Val) -> Option<int> {
    read_int(s)
}

/// Freshness.is_current: `self.built_from(store) == self.token()`; in Python None == 0 is False.
pub open spec fn is_current(s: Val, t: Val) -> bool {
    built_from(s) == Some(token(t))
}

/// Freshness.stale_stores: the stores, in the order given, whose stamp is not the token.
pub open spec fn stale_stores(stamps: Seq<Val>, t: Val) -> Seq<Val>
    decreases stamps.len(),
{
    if stamps.len() == 0 {
        Seq::empty()
    } else {
        let rest = stale_stores(stamps.drop_last(), t);
        if built_from(stamps.last()) != Some(token(t)) { rest.push(stamps.last()) } else { rest }
    }
}

/// TraversalKHop.Fresh: `($Data(^IVG.BuiltFrom(pStore)) # 2) && (^IVG.BuiltFrom(pStore) = +$Get(^KG("__version")))`.
/// `=` compares text: an empty stamp is not "0"; a canonical integer stamp equals the token's canonical text exactly
/// when the numbers are equal.
pub open spec fn os_fresh(s: Val, t: Val) -> bool {
    match s {
        Val::Unset => false,
        Val::Empty => false,
        Val::Int(i) => i == token(t),
    }
}

/// The rule: current exactly when stamped and the stamp equals the live token.
pub proof fn theorem_is_current_iff_stamped_equal(s: Val, t: Val)
    ensures is_current(s, t) <==> (s is Int && s->0 == token(t)),
{
}

/// M09, first outcome: a store never stamped (or stamped with nothing) is stale, even while the token is zero or unset.
pub proof fn theorem_unstamped_stale_at_zero(t: Val)
    requires token(t) == 0,
    ensures
        !is_current(Val::Unset, t),
        !is_current(Val::Empty, t),
        !os_fresh(Val::Unset, t),
        !os_fresh(Val::Empty, t),
{
}

/// M09, second outcome: a store stamped at zero is current while the token is zero, unset or empty.
pub proof fn theorem_stamped_zero_current()
    ensures
        is_current(Val::Int(0), Val::Unset),
        is_current(Val::Int(0), Val::Empty),
        is_current(Val::Int(0), Val::Int(0)),
        !is_current(Val::Int(0), Val::Int(1)),
        os_fresh(Val::Int(0), Val::Unset),
{
}

/// The Python module and the ObjectScript reader decide alike.
pub proof fn theorem_python_agrees_with_objectscript(s: Val, t: Val)
    ensures is_current(s, t) == os_fresh(s, t),
{
}

/// stale_stores lists exactly the stores that are not current, in the order given.
pub proof fn theorem_stale_stores_exact(stamps: Seq<Val>, t: Val)
    ensures
        forall|v: Val| stale_stores(stamps, t).contains(v) ==> !is_current(v, t),
        stale_stores(stamps, t).len() <= stamps.len(),
        (forall|i: int| 0 <= i < stamps.len() ==> !is_current(#[trigger] stamps[i], t)) ==> stale_stores(stamps, t) == stamps,
    decreases stamps.len(),
{
    if stamps.len() > 0 {
        theorem_stale_stores_exact(stamps.drop_last(), t);
        let r = stale_stores(stamps.drop_last(), t);
        if forall|i: int| 0 <= i < stamps.len() ==> !is_current(#[trigger] stamps[i], t) {
            assert forall|i: int| 0 <= i < stamps.drop_last().len() implies !is_current(#[trigger] stamps.drop_last()[i], t) by {
                assert(stamps.drop_last()[i] == stamps[i]);
            }
            assert(r == stamps.drop_last());
            assert(stamps.drop_last().push(stamps.last()) =~= stamps);
        }
        assert forall|v: Val| stale_stores(stamps, t).contains(v) implies !is_current(v, t) by {
            if v != stamps.last() || is_current(stamps.last(), t) {
                if stale_stores(stamps, t).contains(v) && !r.contains(v) {
                    let j = choose|j: int| 0 <= j < stale_stores(stamps, t).len() && stale_stores(stamps, t)[j] == v;
                    assert(j == r.len());
                }
            }
        }
    }
}

/// The legitimate path: stamp, then current; a write moves the token, then stale.
pub proof fn witness_stamp_then_write()
    ensures is_current(Val::Int(3), Val::Int(3)), !is_current(Val::Int(3), Val::Int(4)),
{
}

} // verus!
