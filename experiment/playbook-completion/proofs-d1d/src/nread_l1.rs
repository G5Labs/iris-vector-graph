//! Module 09, L1 part 2: a native read against the SQL path (spec 253): its answer, who may run it, shadow mode, and
//! what it sees of another writer's open transaction.
//!
//! Sources: spec 253 FR-002 (specs/253-native-cypher-executor/spec.md:100: a native result equals the SQL path's) and
//! NAT-B1.11 (two different relationships in one match are never taken as the same one); FR-003 (:102: ^KG is read only
//! where the adjacency index keeps it) and NAT-I1 (labels are read from ^KG only where each label write keeps it); FR-011
//! (:124-127: the executor checks SELECT on the graph tables, "cached per process and user"); US1 / FR-006 (:30, :107: a
//! shadow mode fails on any difference) with HD-0902's working answer (a native exception in shadow mode is a failed
//! comparison); HD-0903's working answer and docs/USER_GUIDE.md:260-262 (a read, native or SQL, sees what an open
//! transaction of another connection has written, and loses it on rollback).
//!
//! **Intent status.** FR-011 is intent-undecided (HD-0901, F-0908): the later maintainer statement R280 and
//! docs/ADMIN_GUIDE.md:565-570 make the database resource the native boundary. The contract here is FR-011 as written,
//! in its weaker cached form (HD-0901's P1': a native read by process p of user u needs a check that passed for (p, u),
//! now or earlier); under R280 the executor need not check and the corresponding control shows only the gap with
//! FR-011. HD-0902's working answer is an assumption (status assumption, intent/HD-0902.md).
//!
//! Abstraction (explicit): one pattern, `MATCH (a)-[:T]->(h)<-[:T]-(c)` over relationships into one hub (each an
//! integer id): its answer is the set of ordered pairs of distinct relationships (`pairs`); one label read (the
//! (node, label) rows); users and processes are integers; `held` is the set of users holding SELECT on the four tables.
//!
//! Business rules: **a native answer is the SQL path's** (pairs of distinct relationships; the label rows); **a native
//! read by (p, u) runs only after a check that found u's SELECT** (FR-011, cached per process and user); **a shadow-mode
//! answer was compared** (native answered and agreed); **a read sees another writer's open transaction's rows and loses
//! them on its rollback** (HD-0903).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub struct NR1 {
    pub rels: Set<int>,
    pub snap: Option<Set<int>>,
    pub held: Set<int>,
    pub chk: Set<(int, int)>,
    pub labs: Set<(int, int)>,
}

pub enum NRL1 {
    TBegin,
    TAdd { e: int },
    TCommit,
    TRollback,
    Grant { u: int },
    Revoke { u: int },
    LWrite { n: int, l: int },
    NRead { p: int, u: int, ans: ISet<(int, int)> },
    NLabels { p: int, u: int, ans: Set<(int, int)> },
    NRefuse { p: int, u: int },
    Shadow { p: int, u: int, ans: Option<ISet<(int, int)>>, compared: bool },
    SqlRead { u: int, ans: Option<ISet<(int, int)>> },
}

/// The SQL path's answer: ordered pairs of distinct relationships into the hub.
pub open spec fn pairs(rels: Set<int>) -> ISet<(int, int)> {
    ISet::new(|x: (int, int)| rels.contains(x.0) && rels.contains(x.1) && x.0 != x.1)
}
/// FR-011, cached per process and user: a check for (p, u) passed earlier, or passes now.
pub open spec fn authorized(s: NR1, p: int, u: int) -> bool { s.chk.contains((p, u)) || s.held.contains(u) }
/// The check's cache after a native read (it may record the check that passed now).
pub open spec fn checked(s: NR1, p: int, u: int, t: NR1) -> bool { t == s || t == (NR1 { chk: s.chk.insert((p, u)), ..s }) }

pub struct NrL1;

impl Contract for NrL1 {
    type S = NR1;
    type L = NRL1;

    open spec fn init(s: NR1) -> bool {
        s.rels == Set::<int>::empty() && s.snap is None && s.chk == Set::<(int, int)>::empty() && s.labs == Set::<(int, int)>::empty()
    }

    open spec fn next(s: NR1, l: NRL1, t: NR1) -> bool {
        match l {
            NRL1::TBegin => s.snap is None && t == (NR1 { snap: Some(s.rels), ..s }),
            NRL1::TAdd { e } => s.snap is Some && t == (NR1 { rels: s.rels.insert(e), ..s }),
            NRL1::TCommit => s.snap is Some && t == (NR1 { snap: None, ..s }),
            NRL1::TRollback => s.snap is Some && t == (NR1 { rels: s.snap->Some_0, snap: None, ..s }),
            NRL1::Grant { u } => t == (NR1 { held: s.held.insert(u), ..s }),
            NRL1::Revoke { u } => t == (NR1 { held: s.held.remove(u), ..s }),
            NRL1::LWrite { n, l } => t == (NR1 { labs: s.labs.insert((n, l)), ..s }),
            NRL1::NRead { p, u, ans } => authorized(s, p, u) && ans == pairs(s.rels) && checked(s, p, u, t),
            NRL1::NLabels { p, u, ans } => authorized(s, p, u) && ans == s.labs && checked(s, p, u, t),
            NRL1::NRefuse { p, u } => t == s,
            NRL1::Shadow { p, u, ans, compared } =>
                t == s && match ans { Some(x) => compared && s.held.contains(u) && x == pairs(s.rels), None => true },
            NRL1::SqlRead { u, ans } =>
                t == s && match ans { Some(x) => s.held.contains(u) && x == pairs(s.rels), None => !s.held.contains(u) },
        }
    }
}

impl SafeContract for NrL1 {
    open spec fn inv(s: NR1) -> bool { true }
    proof fn init_safe(s: NR1) {}
    proof fn step_safe(s: NR1, l: NRL1, t: NR1) {}
}

/// FR-002 / NAT-B1.11: from one state, a native answer and a SQL-path answer are equal.
pub proof fn theorem_native_answer_is_the_sql_answer(s: NR1, p: int, u: int, x: ISet<(int, int)>, t: NR1, y: ISet<(int, int)>, t2: NR1)
    requires NrL1::next(s, NRL1::NRead { p, u, ans: x }, t), NrL1::next(s, NRL1::SqlRead { u, ans: Some(y) }, t2),
    ensures x == y,
{
}

/// FR-011 (P1'): a native read by (p, u) ran after a check that passed for (p, u), now or earlier.
pub proof fn theorem_native_read_needs_a_passed_check(s: NR1, p: int, u: int, x: ISet<(int, int)>, t: NR1)
    requires NrL1::next(s, NRL1::NRead { p, u, ans: x }, t),
    ensures s.chk.contains((p, u)) || s.held.contains(u),
{
}

/// HD-0902: a shadow-mode answer was compared.
pub proof fn theorem_shadow_answer_was_compared(s: NR1, p: int, u: int, x: ISet<(int, int)>, c: bool, t: NR1)
    requires NrL1::next(s, NRL1::Shadow { p, u, ans: Some(x), compared: c }, t),
    ensures c, x == pairs(s.rels),
{
}

/// HD-0903 / F-0909: while another connection's transaction is open, a native read sees the relationship it added;
/// after its rollback the relationship is gone.
pub proof fn theorem_open_transaction_is_seen_and_rolled_back(s: NR1, e: int, t: NR1, p: int, u: int, x: ISet<(int, int)>,
                                                              t2: NR1, f: int, t3: NR1)
    requires
        s.snap is Some, !s.snap->Some_0.contains(e),
        NrL1::next(s, NRL1::TAdd { e }, t),
        NrL1::next(t, NRL1::NRead { p, u, ans: x }, t2),
        NrL1::next(t2, NRL1::TRollback, t3),
    ensures
        t.rels.contains(e), x == pairs(t.rels), !t3.rels.contains(e),
{
}

} // verus!
