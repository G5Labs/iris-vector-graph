//! Family wrt_ledger_stmt (module 03; finding F-0303; statement WRT-B1.9; invariant INV-stmt of
//! experiment/playbook-uplift/semantics/writesets.json, ERS-I2/ERS-I3).
//!
//! One triple t of the default graph, ledger enabled (not strict). State: whether t has a live edge row and which
//! row lifetime it is (a row created again is a different edge), the ledger's statement entries
//! ^IVG.Ledger("stmt", id) = $LB(s, p, o, g, createdSeq, deletedSeq) (here: the lifetime the statement was
//! allocated for, and whether deletedSeq is empty), and the tuple index ^IVG.Ledger("tuple", s, p, o, gkey) = id.
//!
//! Operations:
//! - `LedgerCreate`: a changeset create_relationship. FindEdge finds no row, so it inserts one and AllocStmt
//!   registers a new statement and points the tuple index at it (LedgerApply.cls:448-497, 159-168).
//! - `LedgerUpdate`: a changeset op naming the relationship by tuple (update / upsert; ResolveRef by tuple,
//!   LedgerApply.cls:185-204; OpCreateRel's merge path 470-479): the tuple index gives the statement it acts on;
//!   with no tuple entry it assigns a new statement to the live row ("assigned_stmt").
//! - `LedgerDelete`: delete by tuple: the row goes, the statement gets its deletedSeq, the tuple entry goes
//!   (LedgerApply.cls:676-683).
//! - `DirectDelete`: engine.delete_edge, a plain SQL DELETE (nodes_edges.py:1414-1433).
//! - `DirectCreate`: engine.create_edge, a plain guarded INSERT (nodes_edges.py:1205-1219).
//! - `DeleteNode`: engine.delete_node through Graph.KG.Eraser.EraseNodeIds, whose per-edge step kills the
//!   statement and the tuple entry with the row (Eraser.cls:660-677).
//!
//! Designs: `AsBuilt`; `Reviewed` — delete_edge goes through Eraser.EraseEdges as bulk_delete_adjacency does
//! (nodes_edges.py:2332-2335), killing the statement and the tuple entry with the row; `TupleOnly` (negative
//! control) — the reviewed route but killing only the tuple entry, not the statement.
//!
//! Properties: `INV-stmt` — every live statement names the live edge row of its lifetime ("no live statement
//! outlives its content", CONTEXT.md:198-205); `WRT-B1.9 identity` — an operation never attaches a statement to a
//! second edge lifetime (the finding's "the history joins two different edges into one statement").
use explorer::*;
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, TupleOnly }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Stmt { pub life: u8, pub live: bool, pub touched: Vec<u8> }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub row: Option<u8>,
    pub next_life: u8,
    pub stmts: BTreeMap<u8, Stmt>,
    pub tuple: Option<u8>,
    pub next_stmt: u8,
    pub ops: u8,
}

#[derive(Clone, Debug)]
pub enum A { LedgerCreate, LedgerUpdate, LedgerDelete, DirectDelete, DirectCreate, DeleteNode }

pub struct M { pub design: Design }

pub const STMT: &str = "INV-stmt: every live statement names the live edge row it was allocated for";
pub const IDENT: &str = "WRT-B1.9: no statement is attached to a second edge lifetime";

impl M {
    fn alloc(&self, u: &mut S, life: u8) -> u8 {
        let id = u.next_stmt;
        u.next_stmt += 1;
        u.stmts.insert(id, Stmt { life, live: true, touched: vec![life] });
        u.tuple = Some(id);
        id
    }
    fn erase_link(&self, u: &mut S, kill_stmt: bool) {
        if let Some(id) = u.tuple { if kill_stmt { u.stmts.remove(&id); } }
        u.tuple = None;
    }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { row: None, next_life: 0, stmts: BTreeMap::new(), tuple: None, next_stmt: 0, ops: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::LedgerCreate, A::LedgerUpdate, A::LedgerDelete, A::DirectDelete, A::DirectCreate, A::DeleteNode]
    }
    fn within_bounds(&self, s: &S) -> bool { s.ops < 5 }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        u.ops += 1;
        match a {
            A::LedgerCreate => {
                if s.row.is_some() { return None; } // relationship_exists
                let life = s.next_life; u.next_life += 1; u.row = Some(life);
                self.alloc(&mut u, life);
            }
            A::LedgerUpdate => {
                let life = s.row?;
                match s.tuple {
                    None => { self.alloc(&mut u, life); }
                    Some(id) => {
                        let st = u.stmts.get_mut(&id)?; // a killed statement: "statement is unknown", refused
                        if !st.live { return None; }
                        if !st.touched.contains(&life) { st.touched.push(life); }
                    }
                }
            }
            A::LedgerDelete => {
                let life = s.row?;
                let id = s.tuple?;
                let st = u.stmts.get_mut(&id)?;
                if !st.live { return None; }
                if !st.touched.contains(&life) { st.touched.push(life); }
                st.live = false; u.row = None; u.tuple = None;
            }
            A::DirectDelete => {
                s.row?;
                u.row = None;
                match self.design {
                    Design::AsBuilt => {}
                    Design::Reviewed => self.erase_link(&mut u, true),
                    Design::TupleOnly => self.erase_link(&mut u, false),
                }
            }
            A::DirectCreate => {
                if s.row.is_some() { return None; }
                let life = s.next_life; u.next_life += 1; u.row = Some(life);
            }
            A::DeleteNode => {
                s.row?;
                u.row = None;
                self.erase_link(&mut u, true);
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(STMT, |s: &S| s.stmts.values().all(|st| !st.live || s.row == Some(st.life))),
            invariant(IDENT, |s: &S| s.stmts.values().all(|st| st.touched.len() <= 1)),
        ]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let (md, fam) = ("03", "wrt_ledger_stmt");
    let ab = M { design: Design::AsBuilt };
    let rv = M { design: Design::Reviewed };
    let ct = M { design: Design::TupleOnly };
    vec![
        check("wrt_ledger_stmt-as-built-F0303-stmt", md, fam, "as-built", "safety", Expect::Violation(STMT), &Keep::invariants(&ab, &[STMT])),
        check("wrt_ledger_stmt-as-built-F0303-identity", md, fam, "as-built", "safety", Expect::Violation(IDENT), &Keep::invariants(&ab, &[IDENT])),
        check("wrt_ledger_stmt-reviewed", md, fam, "reviewed", "safety", Expect::Pass, &rv),
        check("wrt_ledger_stmt-control-tuple-only", md, fam, "control", "safety", Expect::Violation(STMT), &ct),
        reach("wrt_ledger_stmt-reviewed-reach-recreated-and-governed", md, fam, "reviewed", &rv,
              "never: an edge directly deleted and re-created is then governed by a new statement",
              |s: &S| s.row == Some(1) && s.stmts.values().any(|st| st.life == 1 && st.live)),
    ]
}
