//! M-09 Graph key and tenant scope (AX-02), generic over `ScopePolicy` / `ScopeObject`.
//!
//! The machine is the semantics lane's `models/semantics/src/scope.rs` (read at commit b0433157; unchanged at the
//! semantics lane's commit 50911c4a) restated without its bound on writes (3): two graphs (0 the default graph,
//! 1 a named graph) and two node ids (0, 1) with overlapping ids (spec 230: nodes unique on (graph_id, node_id));
//! the content of (graph g, id i) is `content[2 g + i]` (0 absent; the explorer's 2x2 array, flattened). Names:
//! "" (0), "acme" (1), "0" (2), "\x01" (3). The key of a name (GraphKey.cls:51-77): a validated entry refuses "0"
//! and control characters; an unvalidated entry (nodes_edges.py:968-1015, F-0202) maps "0" onto the default graph's
//! key 0 and other unvalidated names to a third key (2) that holds no modelled content. Reads: `Scoped` (the graph's
//! own content), `JoinAny` (an id's data taken from any graph that has it: F-0206, F-1507, F-1701), `Merged` (an
//! all-graphs walk that crosses graphs: F-0818..F-0820, F-1002, F-1008). Deletes: `Scoped`, `EveryGraph` (delete by
//! id in every graph: F-1503). Target predicates for the target "default graph, no prefix": erase and liveness
//! select graph 0's ids; the record match is graph-blind for node records (F-1304, F-1305, F-1105).
//! Names are 0..3, ids 0..1, graphs 0..1 as in the explorer; a written value may be any nat (the explorer writes 2).
//! A name that is refused changes nothing (the explorer's step only counts the write against its bound).
//!
//! Laws (MECHANISMS.md M-09): M09-L1 (invariant) distinct accepted names have distinct keys; M09-L2 (action) a read
//! answers its graph's own content, an all-graphs read the union of the per-graph answers; M09-L3 (action) a write
//! or delete to g changes no other graph; M09-L4 (invariant) the erase, liveness and record-match predicates of a
//! target select the same (graph, id) pairs.
//!
//! Obligations (design rules on the instance's scope policy): L1 every entry validates the name before deriving its
//! key; L2 every read answers from its own graph only (an all-graphs read is the per-graph answers side by side);
//! L3 a delete addresses (graph, id), never an id in every graph; L4 the record match is scoped by graph like the
//! erase and the liveness check.
use vstd::prelude::*;
use crate::exec::*;

verus! {

pub enum KeyPol { Validated, Unvalidated, IgnoresName }
pub enum ReadPol { Scoped, JoinAny, Merged }
pub enum DelPol { Scoped, EveryGraph }

pub struct ScCfg { pub key: KeyPol, pub read: ReadPol, pub del: DelPol, pub match_blind: bool }

pub struct ScS { pub content: Seq<nat>, pub accepted: Set<nat>, pub keys: Seq<nat>, pub last_ok: bool }

pub enum ScA { Write(nat, nat, nat), Delete(nat, nat), Read(nat, nat), AllRead(nat) }

pub trait ScopePolicy: Sized {
    spec fn cfg() -> ScCfg;
}

/// The explorer's initial state: graph 0 holds id 0 (value 1); graph 1 holds ids 0 (value 2) and 1 (value 1).
pub open spec fn scope_s0() -> ScS {
    ScS { content: seq![1nat, 0nat, 2nat, 1nat], accepted: Set::empty(), keys: seq![9nat, 9nat, 9nat, 9nat], last_ok: true }
}

pub open spec fn idx(g: nat, i: nat) -> int { (2 * g + i) as int }
pub open spec fn cell(s: ScS, g: nat, i: nat) -> nat { s.content[idx(g, i)] }
pub open spec fn other(g: nat) -> nat { if g == 0 { 1 } else { 0 } }
pub open spec fn max(a: nat, b: nat) -> nat { if a >= b { a } else { b } }

/// The key a name maps to (GraphKey.cls:51-77), or None when the entry refuses the name.
pub open spec fn key_of(c: ScCfg, name: nat) -> Option<nat> {
    match c.key {
        KeyPol::IgnoresName => Some(0),
        _ => {
            if name == 0 { Some(0) }
            else if name == 1 { Some(1) }
            else {
                match c.key {
                    KeyPol::Unvalidated => if name == 2 { Some(0) } else { Some(2) },
                    _ => None,
                }
            }
        },
    }
}

/// The answer of a read of (g, i) under the read policy.
pub open spec fn answer(c: ScCfg, s: ScS, g: nat, i: nat) -> nat {
    match c.read {
        ReadPol::Scoped => cell(s, g, i),
        ReadPol::JoinAny => if cell(s, g, i) != 0 { cell(s, g, i) } else { cell(s, other(g), i) },
        ReadPol::Merged => max(cell(s, 0, i), cell(s, 1, i)),
    }
}

pub open spec fn scope_step<O: ScopePolicy>(s: ScS, a: ScA) -> Option<ScS> {
    let c = O::cfg();
    if s.content.len() != 4 || s.keys.len() != 4 { None } else {
    match a {
        ScA::Write(name, i, v) => {
            if name >= 4 || i >= 2 { None }
            else {
                match key_of(c, name) {
                    None => Some(s),
                    Some(k) => Some(ScS {
                        accepted: s.accepted.insert(name),
                        keys: s.keys.update(name as int, k),
                        content: if k < 2 { s.content.update(idx(k, i), v) } else { s.content },
                        ..s
                    }),
                }
            }
        },
        ScA::Delete(g, i) => {
            if g >= 2 || i >= 2 || cell(s, g, i) == 0 { None }
            else {
                let u = s.content.update(idx(g, i), 0);
                Some(ScS { content: if c.del is EveryGraph { u.update(idx(other(g), i), 0) } else { u }, ..s })
            }
        },
        ScA::Read(g, i) => {
            if g >= 2 || i >= 2 { None } else { Some(ScS { last_ok: answer(c, s, g, i) == cell(s, g, i), ..s }) }
        },
        ScA::AllRead(i) => {
            if i >= 2 { None }
            else {
                let m = max(cell(s, 0, i), cell(s, 1, i));
                let ok = match c.read { ReadPol::Merged => m == cell(s, 0, i) && m == cell(s, 1, i), _ => true };
                Some(ScS { last_ok: ok, ..s })
            }
        },
    }
    }
}

pub struct ScopeM<O> { pub o: O }

impl<O: ScopePolicy> Machine for ScopeM<O> {
    type S = ScS;
    type A = ScA;
    open spec fn init(s: ScS) -> bool { s == scope_s0() }
    open spec fn step(s: ScS, a: ScA) -> Option<ScS> { scope_step::<O>(s, a) }
}

// ------------------------------------------------------------------------------------------------ laws

/// M09-L1 (invariant): distinct accepted names have distinct keys.
pub open spec fn law_l1(s: ScS) -> bool {
    forall|a: nat, b: nat| a < 4 && b < 4 && a != b && #[trigger] s.accepted.contains(a) && #[trigger] s.accepted.contains(b)
        ==> s.keys[a as int] != s.keys[b as int]
}

/// M09-L2 (action): a read answers its own graph (an all-graphs read: the per-graph answers).
pub open spec fn law_l2(s: ScS, a: ScA, t: ScS) -> bool {
    match a { ScA::Read(_, _) | ScA::AllRead(_) => t.last_ok, _ => true }
}

pub open spec fn graph_same(s: ScS, t: ScS, g: nat) -> bool {
    cell(t, g, 0) == cell(s, g, 0) && cell(t, g, 1) == cell(s, g, 1)
}

/// M09-L3 (action): a delete in g leaves the other graph; a write changes at most one graph.
pub open spec fn law_l3(s: ScS, a: ScA, t: ScS) -> bool {
    match a {
        ScA::Delete(g, _) => graph_same(s, t, other(g)),
        ScA::Write(_, _, _) => graph_same(s, t, 0) || graph_same(s, t, 1),
        _ => true,
    }
}

/// M09-L4 (invariant): for the target "default graph, no prefix" the erase, liveness and record-match predicates
/// select the same graphs (erase and liveness select graph 0; the record match is graph-blind when `match_blind`).
/// The predicates do not depend on the state, so the law is a property of the instance.
pub open spec fn law_l4<O: ScopePolicy>(s: ScS) -> bool {
    predicates_agree(0, O::cfg().match_blind) && predicates_agree(1, O::cfg().match_blind)
}

/// Graph g: erase selects it iff g = 0, liveness iff g = 0, the record match iff g = 0 or the match is graph-blind.
pub open spec fn predicates_agree(g: nat, blind: bool) -> bool {
    let erase = g == 0;
    let live = g == 0;
    let mtch = blind || g == 0;
    erase == live && live == mtch
}

// ------------------------------------------------------------------------------------------------ obligations

pub open spec fn obl_l1<O: ScopePolicy>() -> bool { O::cfg().key is Validated }
pub open spec fn obl_l2<O: ScopePolicy>() -> bool { O::cfg().read is Scoped }
pub open spec fn obl_l3<O: ScopePolicy>() -> bool { O::cfg().del is Scoped }
pub open spec fn obl_l4<O: ScopePolicy>() -> bool { !O::cfg().match_blind }

pub trait ScopeObject: ScopePolicy {
    proof fn discharge_l1() ensures obl_l1::<Self>();
    proof fn discharge_l2() ensures obl_l2::<Self>();
    proof fn discharge_l3() ensures obl_l3::<Self>();
    proof fn discharge_l4() ensures obl_l4::<Self>();
}

// ------------------------------------------------------------------------------------------------ generic lemmas

/// Every policy: an accepted name carries the key its entry derives for it.
pub open spec fn inv_keys<O: ScopePolicy>(s: ScS) -> bool {
    &&& s.content.len() == 4 && s.keys.len() == 4
    &&& forall|n: nat| #[trigger] s.accepted.contains(n) ==> n < 4 && key_of(O::cfg(), n) is Some && s.keys[n as int] == key_of(O::cfg(), n)->0
}

pub proof fn lemma_keys_step<O: ScopePolicy>(s: ScS, a: ScA)
    requires inv_keys::<O>(s), scope_step::<O>(s, a) is Some,
    ensures inv_keys::<O>(scope_step::<O>(s, a)->0),
{
    let u = scope_step::<O>(s, a)->0;
    if let ScA::Write(name, i, v) = a {
        if key_of(O::cfg(), name) is Some {
            assert forall|n: nat| #[trigger] u.accepted.contains(n) implies
                n < 4 && key_of(O::cfg(), n) is Some && u.keys[n as int] == key_of(O::cfg(), n)->0 by {
                if n != name { assert(s.accepted.contains(n)); }
            }
        }
    }
}

pub proof fn lemma_l1_of_inv<O: ScopePolicy>(s: ScS)
    requires obl_l1::<O>(), inv_keys::<O>(s),
    ensures law_l1(s),
{
    assert forall|a: nat, b: nat| a < 4 && b < 4 && a != b && #[trigger] s.accepted.contains(a) && #[trigger] s.accepted.contains(b)
        implies s.keys[a as int] != s.keys[b as int] by {
        assert(key_of(O::cfg(), a) is Some && key_of(O::cfg(), b) is Some);
    }
}

pub proof fn lemma_l2_step<O: ScopePolicy>(s: ScS, a: ScA)
    requires obl_l2::<O>(), scope_step::<O>(s, a) is Some,
    ensures law_l2(s, a, scope_step::<O>(s, a)->0),
{
}

pub proof fn lemma_l3_step<O: ScopePolicy>(s: ScS, a: ScA)
    requires obl_l3::<O>(), scope_step::<O>(s, a) is Some,
    ensures law_l3(s, a, scope_step::<O>(s, a)->0),
{
    let u = scope_step::<O>(s, a)->0;
    match a {
        ScA::Write(name, i, v) => {
            match key_of(O::cfg(), name) {
                Some(k) => {
                    if k < 2 {
                        assert(graph_same(s, u, other(k)));
                        if k == 0 { assert(graph_same(s, u, 1)); } else { assert(graph_same(s, u, 0)); }
                    } else {
                        assert(u.content == s.content);
                    }
                },
                None => {},
            }
        },
        ScA::Delete(g, i) => {
            assert(graph_same(s, u, other(g)));
        },
        _ => {},
    }
}

pub proof fn lemma_l4<O: ScopePolicy>(s: ScS)
    requires obl_l4::<O>(),
    ensures law_l4::<O>(s),
{
}

// ------------------------------------------------------------------------------------------------ theorems

pub proof fn theorem_keys<O: ScopePolicy>(s0: ScS, ls: Seq<ScA>, t: ScS)
    requires reached::<ScopeM<O>>(s0, ls, t),
    ensures inv_keys::<O>(t),
{
    let inv = |s: ScS| inv_keys::<O>(s);
    assert forall|x: ScS, a: ScA| inv(x) && (#[trigger] ScopeM::<O>::step(x, a)) is Some implies inv(ScopeM::<O>::step(x, a)->0) by {
        lemma_keys_step::<O>(x, a);
    }
    lemma_reached_inv::<ScopeM<O>>(inv, s0, ls, t);
}

pub proof fn theorem_l1<O: ScopePolicy>(s0: ScS, ls: Seq<ScA>, t: ScS)
    requires obl_l1::<O>(), reached::<ScopeM<O>>(s0, ls, t),
    ensures law_l1(t),
{
    theorem_keys::<O>(s0, ls, t);
    lemma_l1_of_inv::<O>(t);
}

pub proof fn theorem_l2<O: ScopePolicy>(s: ScS, a: ScA)
    requires obl_l2::<O>(), scope_step::<O>(s, a) is Some,
    ensures law_l2(s, a, scope_step::<O>(s, a)->0),
{
    lemma_l2_step::<O>(s, a);
}

pub proof fn theorem_l3<O: ScopePolicy>(s: ScS, a: ScA)
    requires obl_l3::<O>(), scope_step::<O>(s, a) is Some,
    ensures law_l3(s, a, scope_step::<O>(s, a)->0),
{
    lemma_l3_step::<O>(s, a);
}

pub proof fn theorem_l4<O: ScopePolicy>(s0: ScS, ls: Seq<ScA>, t: ScS)
    requires obl_l4::<O>(), reached::<ScopeM<O>>(s0, ls, t),
    ensures law_l4::<O>(t),
{
    lemma_l4::<O>(t);
}

/// The mechanism's theorem, once for every object.
pub proof fn theorem_scope<O: ScopeObject>(s0: ScS, ls: Seq<ScA>, t: ScS, a: ScA)
    requires reached::<ScopeM<O>>(s0, ls, t),
    ensures
        law_l1(t),
        law_l4::<O>(t),
        scope_step::<O>(t, a) is Some ==> law_l2(t, a, scope_step::<O>(t, a)->0) && law_l3(t, a, scope_step::<O>(t, a)->0),
{
    O::discharge_l1();
    O::discharge_l2();
    O::discharge_l3();
    O::discharge_l4();
    theorem_l1::<O>(s0, ls, t);
    theorem_l4::<O>(s0, ls, t);
    if scope_step::<O>(t, a) is Some {
        theorem_l2::<O>(t, a);
        theorem_l3::<O>(t, a);
    }
}

} // verus!
