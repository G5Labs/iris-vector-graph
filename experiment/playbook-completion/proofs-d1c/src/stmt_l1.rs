//! Module 03, L1 part 2: a directly written edge and the ledger's statement for it (F-0303; WRT-B1.9; INV-stmt of
//! experiment/playbook-uplift/semantics/writesets.json; ERS-I2/ERS-I3).
//!
//! The ledger is enabled (not strict). State: each triple's live edge (`row[k]`, the lifetime of the row: a row created
//! again is a different edge), and the live statements (`stmts[id] = St { k, life }`: the edge lifetime each was
//! allocated for). Labels: a changeset create of a relationship (`LCreate`), a changeset op naming a relationship by
//! its tuple (`LUpdate`: update or upsert; an unrecorded live edge is given a statement), a changeset delete
//! (`LDelete`), engine.create_edge (`DCreate`) and engine.delete_edge (`DDelete`, and delete_node's per-edge step).
//!
//! Business rules: **no live statement outlives its content** (CONTEXT.md:198-205; INV-stmt): `DDelete` ends every
//! statement of the edge; **a statement names one edge lifetime** (WRT-B1.9: the history never joins two edges into
//! one statement): an op by tuple acts on the statement of the current edge, or gives it a new one. `inv1` (proved
//! inductive): every live statement names the live edge of its lifetime, and a triple has at most one live statement.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct St { pub k: int, pub life: nat }

pub struct SS1 {
    pub row: Map<int, nat>,
    pub next_life: nat,
    pub stmts: Map<nat, St>,
    pub next_stmt: nat,
}

pub enum SL1 {
    LCreate { k: int, id: nat },
    LUpdate { k: int, id: nat },
    LDelete { k: int, id: nat },
    DCreate { k: int },
    DDelete { k: int },
}

/// Statement `id` is live and names the current edge of `k`.
pub open spec fn names(s: SS1, id: nat, k: int) -> bool {
    s.row.contains_key(k) && s.stmts.contains_key(id) && s.stmts[id] == (St { k, life: s.row[k] })
}
pub open spec fn unnamed(s: SS1, k: int) -> bool { forall|j: nat| #[trigger] s.stmts.contains_key(j) ==> s.stmts[j].k != k }
pub open spec fn drop_stmts_of(stmts: Map<nat, St>, k: int) -> Map<nat, St> {
    Map::new(stmts.dom().filter(|j: nat| stmts[j].k != k), |j: nat| stmts[j])
}

pub struct StmtL1;

impl Contract for StmtL1 {
    type S = SS1;
    type L = SL1;

    open spec fn init(s: SS1) -> bool {
        s.row == Map::<int, nat>::empty() && s.stmts == Map::<nat, St>::empty() && s.next_life == 0 && s.next_stmt == 0
    }

    open spec fn next(s: SS1, l: SL1, t: SS1) -> bool {
        match l {
            SL1::LCreate { k, id } =>
                !s.row.contains_key(k) && id == s.next_stmt
                    && t == (SS1 { row: s.row.insert(k, s.next_life), next_life: s.next_life + 1,
                                   stmts: s.stmts.insert(id, St { k, life: s.next_life }), next_stmt: s.next_stmt + 1 }),
            SL1::LUpdate { k, id } =>
                s.row.contains_key(k) && if unnamed(s, k) {
                    id == s.next_stmt && t == (SS1 { stmts: s.stmts.insert(id, St { k, life: s.row[k] }), next_stmt: s.next_stmt + 1, ..s })
                } else {
                    names(s, id, k) && t == s
                },
            SL1::LDelete { k, id } =>
                names(s, id, k) && t == (SS1 { row: s.row.remove(k), stmts: s.stmts.remove(id), ..s }),
            SL1::DCreate { k } =>
                !s.row.contains_key(k) && t == (SS1 { row: s.row.insert(k, s.next_life), next_life: s.next_life + 1, ..s }),
            SL1::DDelete { k } =>
                s.row.contains_key(k) && t == (SS1 { row: s.row.remove(k), stmts: drop_stmts_of(s.stmts, k), ..s }),
        }
    }
}

/// INV-stmt: every live statement names the live edge of the lifetime it was allocated for.
pub open spec fn inv_named(s: SS1) -> bool {
    forall|j: nat| #[trigger] s.stmts.contains_key(j) ==> s.row.contains_key(s.stmts[j].k) && s.row[s.stmts[j].k] == s.stmts[j].life
}
/// A triple has at most one live statement.
pub open spec fn inv_one(s: SS1) -> bool {
    forall|i: nat, j: nat| #[trigger] s.stmts.contains_key(i) && #[trigger] s.stmts.contains_key(j) && s.stmts[i].k == s.stmts[j].k ==> i == j
}
pub open spec fn inv_fresh(s: SS1) -> bool {
    &&& forall|j: nat| #[trigger] s.stmts.contains_key(j) ==> j < s.next_stmt
    &&& forall|k: int| #[trigger] s.row.contains_key(k) ==> s.row[k] < s.next_life
}
pub open spec fn inv1(s: SS1) -> bool { inv_named(s) && inv_one(s) && inv_fresh(s) }

pub proof fn lemma_l1_safe(s: SS1, l: SL1, t: SS1)
    requires inv1(s), StmtL1::next(s, l, t),
    ensures inv1(t),
{
    match l {
        SL1::LCreate { k, id } => {
            assert forall|j: nat| #[trigger] t.stmts.contains_key(j) implies
                t.row.contains_key(t.stmts[j].k) && t.row[t.stmts[j].k] == t.stmts[j].life by {
                if j != id { assert(s.stmts.contains_key(j)); assert(s.stmts[j].k != k); }
            }
            assert forall|i: nat, j: nat| #[trigger] t.stmts.contains_key(i) && #[trigger] t.stmts.contains_key(j)
                && t.stmts[i].k == t.stmts[j].k implies i == j by {
                if i != id { assert(s.stmts.contains_key(i)); }
                if j != id { assert(s.stmts.contains_key(j)); }
            }
        }
        SL1::LUpdate { k, id } => {
            if unnamed(s, k) {
                assert forall|j: nat| #[trigger] t.stmts.contains_key(j) implies
                    t.row.contains_key(t.stmts[j].k) && t.row[t.stmts[j].k] == t.stmts[j].life by {
                    if j != id { assert(s.stmts.contains_key(j)); }
                }
                assert forall|i: nat, j: nat| #[trigger] t.stmts.contains_key(i) && #[trigger] t.stmts.contains_key(j)
                    && t.stmts[i].k == t.stmts[j].k implies i == j by {
                    if i != id { assert(s.stmts.contains_key(i)); }
                    if j != id { assert(s.stmts.contains_key(j)); }
                }
            }
        }
        SL1::LDelete { k, id } => {
            assert forall|j: nat| #[trigger] t.stmts.contains_key(j) implies
                t.row.contains_key(t.stmts[j].k) && t.row[t.stmts[j].k] == t.stmts[j].life by {
                assert(s.stmts.contains_key(j));
                assert(s.stmts[j].k != k);
            }
            assert forall|i: nat, j: nat| #[trigger] t.stmts.contains_key(i) && #[trigger] t.stmts.contains_key(j)
                && t.stmts[i].k == t.stmts[j].k implies i == j by {
                assert(s.stmts.contains_key(i) && s.stmts.contains_key(j));
            }
        }
        SL1::DCreate { k } => {
            assert forall|j: nat| #[trigger] t.stmts.contains_key(j) implies
                t.row.contains_key(t.stmts[j].k) && t.row[t.stmts[j].k] == t.stmts[j].life by {
                assert(s.stmts.contains_key(j));
            }
        }
        SL1::DDelete { k } => {
            let d = s.stmts.dom().filter(|j: nat| s.stmts[j].k != k);
            assert forall|j: nat| #[trigger] t.stmts.contains_key(j) implies
                t.row.contains_key(t.stmts[j].k) && t.row[t.stmts[j].k] == t.stmts[j].life by {
                assert(d.contains(j));
            }
            assert forall|i: nat, j: nat| #[trigger] t.stmts.contains_key(i) && #[trigger] t.stmts.contains_key(j)
                && t.stmts[i].k == t.stmts[j].k implies i == j by {
                assert(d.contains(i) && d.contains(j));
            }
            assert forall|j: nat| #[trigger] t.stmts.contains_key(j) implies j < t.next_stmt by {
                assert(d.contains(j));
            }
        }
    }
}

impl SafeContract for StmtL1 {
    open spec fn inv(s: SS1) -> bool { inv1(s) }
    proof fn init_safe(s: SS1) {}
    proof fn step_safe(s: SS1, l: SL1, t: SS1) { lemma_l1_safe(s, l, t); }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// INV-stmt (CONTEXT.md:198-205): a live statement names the triple's live edge, of the lifetime it was allocated for.
pub proof fn theorem_live_statement_names_live_edge(s: SS1, j: nat)
    requires inv1(s), s.stmts.contains_key(j),
    ensures s.row.contains_key(s.stmts[j].k), s.row[s.stmts[j].k] == s.stmts[j].life,
{
}

/// WRT-B1.9: a statement never changes the edge lifetime it names, and an edge created again (a new lifetime) is never
/// governed by a statement allocated for an earlier one.
pub proof fn theorem_statement_identity_is_stable(s: SS1, l: SL1, t: SS1, j: nat)
    requires inv1(s), StmtL1::next(s, l, t), s.stmts.contains_key(j), t.stmts.contains_key(j),
    ensures t.stmts[j] == s.stmts[j],
{
    match l {
        SL1::LCreate { k, id } => { assert(j < s.next_stmt); }
        SL1::LUpdate { k, id } => { assert(j < s.next_stmt); }
        SL1::DDelete { k } => { assert(s.stmts.dom().filter(|i: nat| s.stmts[i].k != k).contains(j)); }
        _ => {}
    }
}

/// INV-stmt: after a direct delete no live statement names the triple.
pub proof fn theorem_direct_delete_ends_the_statement(s: SS1, k: int, t: SS1)
    requires StmtL1::next(s, SL1::DDelete { k }, t),
    ensures unnamed(t, k),
{
    assert forall|j: nat| #[trigger] t.stmts.contains_key(j) implies t.stmts[j].k != k by {
        assert(s.stmts.dom().filter(|i: nat| s.stmts[i].k != k).contains(j));
    }
}

} // verus!
