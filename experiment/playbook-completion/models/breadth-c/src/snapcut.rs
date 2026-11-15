//! M4: `save_snapshot` against concurrent writers: is an archive a state of the namespace at one moment?
//! (HD-1802, SNP-Q1.17; module 18).
//!
//! Abstract state: two stores, the nodes table (node a always, node b optional) and the edges table (edge a->b
//! optional), each with what is visible to a reader; a writer process that creates b and a->b in one transaction
//! (node first, then edge: an edge's endpoints first, iris_vector_graph/_engine/nodes_edges.py create_edge) and then
//! commits or rolls back, or deletes them (edge first, then node); and the exporter, which reads the nodes table and
//! then the edges table.
//!
//! As built at 3eaa79cf: `save_snapshot` runs one `SELECT *` per table in sequence and walks each global with
//! `nextSubscript`/`get`, in no transaction and under no lock (iris_vector_graph/_engine/snapshot.py:864-1034); IRIS
//! SQL's default isolation reads uncommitted rows and global reads are always uncommitted (SYS-P2), so a reader sees a
//! writer's rows before its commit and still sees them if it rolls back.
//! Reviewed (decisions.md HD-1802): the quiet-writer premise made a protocol: the exporter holds an exclusive export
//! gate for the whole save, and every writer transaction holds the gate shared from its first write to its end.
//!
//! Properties:
//! - `the archive is a committed state`: a finished archive equals a committed state of the namespace (a state with no
//!   transaction open) that held at some moment during the save;
//! - `the archive has no dangling edge`: every archived edge's endpoints are archived;
//! - always possibly: the save finishes;
//! - witness: a save that runs while a writer commits still produces an archive.
use explorer::*;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Reviewed, ControlWriterSkipsGate }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum W { Idle, CreatedNode, CreatedEdge, DeletedEdge, DeletedNode }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum X { Idle, Started, NodesRead, Done }

/// A state of the two stores: (node b present, edge a->b present). Node a is always present.
pub type Db = (bool, bool);

fn idx(d: Db) -> u8 { (u8::from(d.0) << 1) | u8::from(d.1) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    /// what a reader sees now (uncommitted included)
    pub cur: Db,
    /// the committed state (what remains if the open transaction rolls back)
    pub committed: Db,
    pub w: W,
    pub x: X,
    /// archived nodes (node b) and edges (edge a->b), once read
    pub arch_node_b: bool,
    pub arch_edge: bool,
    /// bit idx(db): a committed state that held at some moment since the save began
    pub seen: u8,
    pub gate_export: bool,
    pub gate_writer: bool,
    pub writer_txns: u8,
    pub saves: u8,
    /// ghost (witness only): a writer committed its create of b and a->b
    pub created_committed: bool,
}

#[derive(Clone, Debug)]
pub enum A {
    /// the writer begins a transaction and writes its first row
    WriterFirst { create: bool },
    WriterSecond,
    WriterEnd { commit: bool },
    SaveStart,
    SaveReadNodes,
    SaveReadEdges,
}

pub struct M { pub design: Design }

impl M {
    fn writer_uses_gate(&self) -> bool { self.design == Design::Reviewed }
    fn exporter_uses_gate(&self) -> bool { matches!(self.design, Design::Reviewed | Design::ControlWriterSkipsGate) }
}

impl Model for M {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        [(false, false), (true, true)].into_iter().map(|d| S { cur: d, committed: d, w: W::Idle, x: X::Idle,
            arch_node_b: false, arch_edge: false, seen: 0, gate_export: false, gate_writer: false, writer_txns: 0,
            saves: 0, created_committed: false }).collect()
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::WriterFirst { create: true }, A::WriterFirst { create: false }, A::WriterSecond,
             A::WriterEnd { commit: true }, A::WriterEnd { commit: false }, A::SaveStart, A::SaveReadNodes,
             A::SaveReadEdges]
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let mut t = s.clone();
        match a {
            A::WriterFirst { create } => {
                if s.w != W::Idle || s.writer_txns >= 2 { return None; }
                if self.writer_uses_gate() && s.gate_export { return None; }
                if *create {
                    if s.cur.0 { return None; }
                    t.cur.0 = true;
                    t.w = W::CreatedNode;
                } else {
                    if !s.cur.1 { return None; }
                    t.cur.1 = false;
                    t.w = W::DeletedEdge;
                }
                t.gate_writer = self.writer_uses_gate();
                t.writer_txns += 1;
            }
            A::WriterSecond => {
                match s.w {
                    W::CreatedNode => { t.cur.1 = true; t.w = W::CreatedEdge; }
                    W::DeletedEdge => { t.cur.0 = false; t.w = W::DeletedNode; }
                    _ => return None,
                }
            }
            A::WriterEnd { commit } => {
                if !matches!(s.w, W::CreatedEdge | W::DeletedNode | W::CreatedNode | W::DeletedEdge) { return None; }
                if *commit {
                    if !matches!(s.w, W::CreatedEdge | W::DeletedNode) { return None; }
                    t.committed = s.cur;
                    if s.w == W::CreatedEdge { t.created_committed = true; }
                } else {
                    t.cur = s.committed; // TROLLBACK undoes every write of the transaction
                }
                t.w = W::Idle;
                t.gate_writer = false;
                if matches!(s.x, X::Started | X::NodesRead) { t.seen |= 1 << idx(t.committed); }
            }
            A::SaveStart => {
                if s.x != X::Idle || s.saves >= 1 { return None; }
                if self.exporter_uses_gate() && s.gate_writer { return None; }
                t.gate_export = self.exporter_uses_gate();
                t.x = X::Started;
                t.saves += 1;
                t.seen = 1 << idx(s.committed);
            }
            A::SaveReadNodes => {
                if s.x != X::Started { return None; }
                t.arch_node_b = s.cur.0;
                t.x = X::NodesRead;
            }
            A::SaveReadEdges => {
                if s.x != X::NodesRead { return None; }
                t.arch_edge = s.cur.1;
                t.x = X::Done;
                t.gate_export = false;
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant("the archive is a committed state", |s: &S|
                s.x != X::Done || s.seen & (1 << idx((s.arch_node_b, s.arch_edge))) != 0),
            invariant("the archive has no dangling edge", |s: &S| s.x != X::Done || !s.arch_edge || s.arch_node_b),
        ]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant("the save finishes", |s: &S| s.x == X::Done)]
    }
}

pub struct Witness { pub m: M }
impl Model for Witness {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> { self.m.init_states() }
    fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
    fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![invariant("a save after a committed create archives it whole", |s: &S|
            !(s.x == X::Done && s.created_committed && (s.arch_node_b, s.arch_edge) == (true, true)))]
    }
}

pub fn show(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps; init committed={:?}:\n", c.property, c.kind,
                          c.steps.len(), c.init.committed);
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<30} visible(b,a->b)={:?} committed={:?} writer={:?} save={:?} archive(b,a->b)=({},{})\n",
                        i + 1, format!("{:?}", a), s.cur, s.committed, s.w, s.x, s.arch_node_b, s.arch_edge);
    }
    out
}
