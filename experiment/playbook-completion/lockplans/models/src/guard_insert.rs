//! Family guard_insert (modules 08 and 17; gate 3.5-lockplans): two writers check-then-insert one key without a lock.
//!
//! As built at 3eaa79cf the guarded writers take no lock of their own on the key:
//! - 08: Cypher CREATE of a node, `INSERT ... SELECT ... WHERE NOT EXISTS` on nodes / rdf_labels / rdf_props
//!   (iris_vector_graph/cypher/translator.py:9699-9756), of an edge between matched nodes `INSERT ... SELECT DISTINCT
//!   ... WHERE NOT EXISTS` (translator.py:10345-10360); a refused INSERT (-119) fails the whole query, which rolls back
//!   (F-0805, _write_txn.py).
//! - 17: IRISGraphStore.write_nodes `INSERT ... VALUES` with a -119 refusal skipped as "the row is already there"
//!   (iris_sql_store.py:755-761, 1214-1251; _write_txn.is_duplicate :46-49); write_edges guarded endpoint inserts and
//!   the edge INSERT with -119 skipped (:1253-1303).
//! IRIS semantics used (iris-contract/CONTRACT.md): E-VIS (:31) a SQL SELECT, the NOT EXISTS guard included, sees
//! another transaction's uncommitted row; E-UNIQUE (:45) an INSERT of a key another open transaction inserted fails at
//! once with -119; a rollback removes the transaction's rows. The shared ^IVG.AdjW(graph) lock of the edge functional
//! index never excludes another writer (Adjacency.cls:25, 61-74).
//!
//! Abstraction: one key k (a node id, or an edge (s, p, o, graph)); its row is absent or (owner, committed?). Each of
//! two writers runs one transaction: `Guard` (reads whether any row is visible), then `Insert` when it saw none
//! (refused when a row appeared meanwhile), then `Dep` (its own dependent row: B's label/property of the node, which
//! has no foreign key in rdf_props, schema.py:411-418), then ends with `Commit` or `Abort` (a caller's ROLLBACK, CYP-B6.2,
//! or a later step's failure). At most one writer aborts.
//!
//! Designs:
//! - `AsBuilt08`: refusal fails the writer (whole query rolled back, error answered).
//! - `AsBuilt17`: refusal skipped (answered ok).
//! - `Reviewed`: an exclusive lock on the key taken before the guard and held to transaction end (e.g. a LOCK on
//!   ^IVG.Key(graph, key) released by the commit, as the head lock is in Ledger.cls:440-444, 404); the guard then sees
//!   only committed rows. Refusal handled as 08.
//! - `ControlEarlyRelease` (negative control): the reviewed lock released right after the insert statement, before
//!   the transaction ends; the explorer must find the lost write.
//!
//! Properties (checked once both writers have ended):
//! - `LOST`: a writer that answered ok (committed) leaves its key row committed.
//! - `ORPHAN`: no committed dependent row without its committed key row (rdf_props / rdf_labels without the node).
//! - `REFUSAL` (serializability of answers; diagnostic, not a defect claim): no writer is refused on the key, since
//!   every serial order of the two creates succeeds.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt08, AsBuilt17, Reviewed, ControlEarlyRelease }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Ph { Start, Guarded(bool), Done1, Deps, Committed, Aborted, Failed }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    /// the key row: None, or Some((owner, committed))
    pub row: Option<(u8, bool)>,
    /// each writer's dependent row: None, or Some(committed)
    pub dep: [Option<bool>; 2],
    pub w: [Ph; 2],
    pub inserted: [bool; 2],
    pub refused: [bool; 2],
    pub lock: Option<u8>,
    pub aborts: u8,
}

#[derive(Clone, Debug)]
pub enum A { Guard(u8), Insert(u8), Dep(u8), Commit(u8), Abort(u8) }

pub struct M { pub design: Design, pub allow_abort: bool }

pub const LOST: &str = "LOST: a writer that answered ok leaves its key row committed";
pub const ORPHAN: &str = "ORPHAN: no committed dependent row without its committed key row";
pub const REFUSAL: &str = "REFUSAL: no writer is refused on the key (serial orders both succeed)";

fn ended(p: Ph) -> bool { matches!(p, Ph::Committed | Ph::Aborted | Ph::Failed) }

impl M {
    fn locking(&self) -> bool { matches!(self.design, Design::Reviewed | Design::ControlEarlyRelease) }

    /// undo writer i's uncommitted work (rollback)
    fn undo(s: &mut S, i: u8) {
        if let Some((o, false)) = s.row { if o == i { s.row = None; } }
        if s.dep[i as usize] == Some(false) { s.dep[i as usize] = None; }
        if s.lock == Some(i) { s.lock = None; }
    }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        vec![S { row: None, dep: [None; 2], w: [Ph::Start; 2], inserted: [false; 2], refused: [false; 2], lock: None,
                 aborts: 0 }]
    }
    fn actions(&self, _: &S) -> Vec<A> {
        let mut v = vec![];
        for i in 0..2 { v.extend([A::Guard(i), A::Insert(i), A::Dep(i), A::Commit(i), A::Abort(i)]); }
        v
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut u = s.clone();
        match *a {
            A::Guard(i) => {
                if s.w[i as usize] != Ph::Start { return None; }
                if self.locking() {
                    if s.lock.is_some() && s.lock != Some(i) { return None; } // waits
                    u.lock = Some(i);
                }
                // E-VIS: any row is visible, committed or not
                u.w[i as usize] = Ph::Guarded(s.row.is_some());
            }
            A::Insert(i) => {
                let Ph::Guarded(saw) = s.w[i as usize] else { return None };
                if !saw {
                    if s.row.is_some() {
                        // E-UNIQUE: refused at once (-119); 17 skips it as a duplicate and answers ok, the others fail
                        match self.design {
                            Design::AsBuilt17 => {}
                            _ => {
                                M::undo(&mut u, i);
                                u.refused[i as usize] = true;
                                u.w[i as usize] = Ph::Failed;
                                return Some(u);
                            }
                        }
                    } else {
                        u.row = Some((i, false));
                        u.inserted[i as usize] = true;
                    }
                }
                if self.design == Design::ControlEarlyRelease && s.lock == Some(i) { u.lock = None; }
                u.w[i as usize] = Ph::Done1;
            }
            A::Dep(i) => {
                if s.w[i as usize] != Ph::Done1 { return None; }
                u.dep[i as usize] = Some(false);
                u.w[i as usize] = Ph::Deps;
            }
            A::Commit(i) => {
                if s.w[i as usize] != Ph::Deps { return None; }
                if let Some((o, false)) = s.row { if o == i { u.row = Some((i, true)); } }
                if s.dep[i as usize] == Some(false) { u.dep[i as usize] = Some(true); }
                if s.lock == Some(i) { u.lock = None; }
                u.w[i as usize] = Ph::Committed;
            }
            A::Abort(i) => {
                if !self.allow_abort || s.aborts >= 1 { return None; }
                if !matches!(s.w[i as usize], Ph::Done1 | Ph::Deps) { return None; }
                M::undo(&mut u, i);
                u.aborts += 1;
                u.w[i as usize] = Ph::Aborted;
            }
        }
        Some(u)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(LOST, |s: &S| {
                !(ended(s.w[0]) && ended(s.w[1])) || (0..2).all(|i| s.w[i] != Ph::Committed || matches!(s.row, Some((_, true))))
            }),
            invariant(ORPHAN, |s: &S| {
                !(ended(s.w[0]) && ended(s.w[1])) || (0..2).all(|i| s.dep[i] != Some(true) || matches!(s.row, Some((_, true))))
            }),
            invariant(REFUSAL, |s: &S| !s.refused[0] && !s.refused[1]),
        ]
    }
}

pub fn checks() -> Vec<crate::harness::Outcome> {
    use crate::harness::*;
    let fam = "guard_insert";
    let ab08 = M { design: Design::AsBuilt08, allow_abort: true };
    let ab17 = M { design: Design::AsBuilt17, allow_abort: true };
    let ab08_noabort = M { design: Design::AsBuilt08, allow_abort: false };
    let ab17_noabort = M { design: Design::AsBuilt17, allow_abort: false };
    let rv = M { design: Design::Reviewed, allow_abort: true };
    let ct = M { design: Design::ControlEarlyRelease, allow_abort: true };
    vec![
        check("guard_insert-08-as-built-lost", "08", fam, "as-built", "safety", Expect::Violation(LOST), &Keep::invariants(&ab08, &[LOST])),
        check("guard_insert-08-as-built-orphan", "08", fam, "as-built", "safety", Expect::Violation(ORPHAN), &Keep::invariants(&ab08, &[ORPHAN])),
        check("guard_insert-08-as-built-refusal", "08", fam, "as-built", "safety", Expect::Violation(REFUSAL), &Keep::invariants(&ab08_noabort, &[REFUSAL])),
        check("guard_insert-08-as-built-no-rollback-lost", "08", fam, "as-built", "safety", Expect::Pass, &Keep::invariants(&ab08_noabort, &[LOST, ORPHAN])),
        check("guard_insert-17-as-built-lost", "17", fam, "as-built", "safety", Expect::Violation(LOST), &Keep::invariants(&ab17, &[LOST])),
        check("guard_insert-17-as-built-orphan", "17", fam, "as-built", "safety", Expect::Violation(ORPHAN), &Keep::invariants(&ab17, &[ORPHAN])),
        check("guard_insert-17-as-built-no-rollback", "17", fam, "as-built", "safety", Expect::Pass, &Keep::invariants(&ab17_noabort, &[LOST, ORPHAN, REFUSAL])),
        check("guard_insert-reviewed", "08", fam, "reviewed", "safety", Expect::Pass, &Keep::invariants(&rv, &[LOST, ORPHAN, REFUSAL])),
        check("guard_insert-control-early-release", "08", fam, "control", "safety", Expect::Violation(LOST), &Keep::invariants(&ct, &[LOST])),
        reach("guard_insert-reviewed-reach-both-committed", "08", fam, "reviewed", &rv, "never: both writers commit with the key row committed",
              |s: &S| s.w == [Ph::Committed, Ph::Committed] && matches!(s.row, Some((_, true)))),
        reach("guard_insert-reviewed-reach-survivor-inserts", "08", fam, "reviewed", &rv, "never: after one writer aborts the other inserts the key",
              |s: &S| s.aborts == 1 && s.w.contains(&Ph::Committed) && matches!(s.row, Some((_, true)))),
        reach("guard_insert-08-as-built-reach-skip-on-uncommitted", "08", fam, "as-built", &ab08, "never: a writer's guard sees an uncommitted row of the other",
              |s: &S| (0..2).any(|i| s.w[i] == Ph::Guarded(true) && matches!(s.row, Some((o, false)) if o as usize != i))),
    ]
}
