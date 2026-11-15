//! Family tmp_mark (modules 03 and 05; findings F-0304, F-0505, F-0507; statements WRT-B4.11, TMP-T2.11,
//! TMP-B9.13; decision HD-0302, supported).
//!
//! Grouped across modules 03 and 05 because one invariant covers the distinct operations: ADR-0009's ownership rule
//! for the structural row of a triple (CONTEXT.md:66-73) — the row a temporal edge implies carries a marker
//! {"temporal": true} and goes when the triple's last timestamp goes; a row written explicitly is never removed by
//! the temporal side; HD-0302: "a temporal-backed structural row must survive direct deletion while its temporal
//! support remains" and explicit edges are preserved separately. The direct writers (module 03) and the temporal
//! writers and purges (module 05) all write that one row.
//!
//! One triple, adjacency index declared. State: the row (absent, or present with qualifiers Marked = JSON true,
//! Plain, or TemporalOne = {"temporal": 1} written by a caller), a ghost flag "an explicit write established this
//! row", and how many temporal edges (timestamps) the triple has (0..2).
//!
//! Operations:
//! - `CreateEdge(q)`: create_edge — guarded insert; on a duplicate it adopts a row marked with JSON true
//!   (`_adopt_temporal_row`, nodes_edges.py:1250-1304: `parsed.get("temporal") is True`), replacing the qualifiers.
//! - `StoreEdge(q)`: store_edge — INSERT, duplicate swallowed, no adoption (nodes_edges.py:2560-2581; F-0304).
//! - `TemporalInsert`: create_edge_temporal / InsertEdge -> WriteStores -> Adjacency.AssertTemporalRow
//!   (TemporalIndex.cls:100-111; Adjacency.cls:580-621): a marked row if the triple has none.
//! - `TemporalDelete`: DeleteTemporalEdge (TemporalIndex.cls:325-341): when the triple's last timestamp goes,
//!   RetractTemporalRow deletes the rows `IsTemporalMarked` accepts (Adjacency.cls:625-650, 735-748:
//!   `%Get("temporal") = 1`, true for JSON true, the number 1 and the string "1"; F-0505).
//! - `PurgeBefore`: purge_before over every timestamp — the triple's timestamps go and the row is retracted by the
//!   same predicate (TemporalIndex.cls purge -> RetractTemporalRows).
//! - `Purge`: TemporalIndex.Purge() = EraseAll (TemporalIndex.cls:379-391, 808-811): the temporal globals go, no row
//!   is retracted (F-0507).
//! - `DirectDelete`: delete_edge removes the row (explicit deletion is out of this invariant's scope; it only resets
//!   the ghost).
//!
//! Design flags (as built = all false): `adopt_on_store` (store_edge adopts a marked row as create_edge does),
//! `strict_marker` (one predicate, JSON true only, as LedgerGenesis.TemporalMarked and the adopt use, TMP-T2.11),
//! `purge_retracts` (Purge retires the marked rows it held up, TMP-B9.13). Reviewed = all true. Negative control:
//! the reviewed design whose create_edge adoption keeps the marker (the adopt step removed).
//!
//! Properties:
//! - `ADR-0009 explicit-survives` (action property): a temporal delete or purge never removes a row an explicit
//!   write established.
//! - `ADR-0009 marked-needs-time` (invariant): a marked row exists only while its triple has a timestamp.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Q { Marked, Plain, TemporalOne }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Fix { pub adopt_on_store: bool, pub strict_marker: bool, pub purge_retracts: bool, pub adopt_clears: bool }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S { pub row: Option<Q>, pub explicit: bool, pub ts: u8, pub ops: u8 }

#[derive(Clone, Debug)]
pub enum A { CreateEdge(Q), StoreEdge(Q), TemporalInsert, TemporalDelete, PurgeBefore, Purge, DirectDelete }

pub struct M { pub fix: Fix }

pub const EXPL: &str = "ADR-0009/HD-0302: a temporal delete or purge never removes an explicitly written edge";
pub const MARK: &str = "ADR-0009/TMP-B9.13: a marked row exists only while its triple has a timestamp";

impl M {
    fn marked(&self, q: Q) -> bool {
        match q { Q::Marked => true, Q::TemporalOne => !self.fix.strict_marker, Q::Plain => false }
    }
    fn retract(&self, u: &mut S) {
        if let Some(q) = u.row { if self.marked(q) { u.row = None; u.explicit = false; } }
    }
    fn adopt(&self, u: &mut S, q: Q) {
        // the adopt reads a JSON boolean true only (nodes_edges.py:1297)
        if u.row == Some(Q::Marked) {
            if self.fix.adopt_clears { u.row = Some(q); }
            u.explicit = true;
        }
    }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { vec![S { row: None, explicit: false, ts: 0, ops: 0 }] }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::CreateEdge(Q::Plain), A::CreateEdge(Q::TemporalOne), A::StoreEdge(Q::Plain), A::TemporalInsert,
             A::TemporalDelete, A::PurgeBefore, A::Purge, A::DirectDelete]
    }
    fn within_bounds(&self, s: &S) -> bool { s.ops < 5 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        u.ops += 1;
        match *a {
            A::CreateEdge(q) => {
                if s.row.is_none() { u.row = Some(q); u.explicit = true; } else { self.adopt(&mut u, q); }
            }
            A::StoreEdge(q) => {
                if s.row.is_none() { u.row = Some(q); u.explicit = true; }
                else if self.fix.adopt_on_store { self.adopt(&mut u, q); }
                else { u.explicit = true; } // the caller wrote it and was told it is stored
            }
            A::TemporalInsert => {
                if s.ts >= 2 { return None; }
                u.ts += 1;
                if s.row.is_none() { u.row = Some(Q::Marked); u.explicit = false; }
            }
            A::TemporalDelete => {
                if s.ts == 0 { return None; }
                u.ts -= 1;
                if u.ts == 0 { self.retract(&mut u); }
            }
            A::PurgeBefore => {
                if s.ts == 0 { return None; }
                u.ts = 0;
                self.retract(&mut u);
            }
            A::Purge => {
                u.ts = 0;
                if self.fix.purge_retracts { self.retract(&mut u); }
            }
            A::DirectDelete => { s.row?; u.row = None; u.explicit = false; }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant(MARK, |s: &S| s.row != Some(Q::Marked) || s.ts > 0)]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![action_property(EXPL, |s: &S, a: &A, t: &S| {
            if matches!(a, A::TemporalDelete | A::PurgeBefore | A::Purge) && s.explicit && s.row.is_some() {
                return t.row.is_some();
            }
            true
        })]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("03+05", "tmp_mark");
    let rv = Fix { adopt_on_store: true, strict_marker: true, purge_retracts: true, adopt_clears: true };
    let ab = M { fix: Fix { adopt_on_store: false, strict_marker: false, purge_retracts: false, adopt_clears: true } };
    let f0304 = M { fix: Fix { adopt_on_store: false, ..rv } };
    let f0505 = M { fix: Fix { strict_marker: false, ..rv } };
    let f0507 = M { fix: Fix { purge_retracts: false, ..rv } };
    let reviewed = M { fix: rv };
    let ctl = M { fix: Fix { adopt_clears: false, ..rv } };
    vec![
        check("tmp_mark-as-built-explicit", "03+05", fam, "as-built", "safety", Expect::Violation(EXPL), &Keep::action_props(&ab, &[EXPL])),
        check("tmp_mark-as-built-marked", "03+05", fam, "as-built", "safety", Expect::Violation(MARK), &Keep::invariants(&ab, &[MARK])),
        check("tmp_mark-as-built-F0304", "03", fam, "as-built", "safety", Expect::Violation(EXPL), &f0304),
        check("tmp_mark-as-built-F0505", "05", fam, "as-built", "safety", Expect::Violation(EXPL), &f0505),
        check("tmp_mark-as-built-F0507", "05", fam, "as-built", "safety", Expect::Violation(MARK), &f0507),
        check("tmp_mark-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &reviewed),
        check("tmp_mark-control-adopt-keeps-marker", md, fam, "control", "safety", Expect::Violation(EXPL), &ctl),
        reach("tmp_mark-reviewed-reach-adopted", md, fam, "reviewed", &reviewed,
              "never: an explicit write adopts a temporal edge's marked row",
              |s: &S| s.explicit && s.ts > 0 && s.row == Some(Q::Plain)),
        reach("tmp_mark-reviewed-reach-retracted", md, fam, "reviewed", &reviewed,
              "never: a marked row is retracted with its last timestamp",
              |s: &S| s.row.is_none() && s.ts == 0 && s.ops >= 2),
    ]
}
