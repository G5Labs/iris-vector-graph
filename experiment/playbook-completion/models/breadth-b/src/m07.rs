//! Module 07 (text search and fusion) models at pin 3eaa79cf.
//!
//! # Machine `bm25`: the writers of one BM25 index
//!
//! Abstracted real state: one index name of `^BM25Idx` (iris_src/src/Graph/KG/BM25Index.cls:6-18):
//! - header `cfg N`, `cfg totalLen`, `cfg schema` (absent = 1), `cfg graph` (recorded or absent), `cfg upgrading`;
//!   schema 1's stored `idf` (`idf` flag);
//! - per document: postings `tf(term, doc)` (a token mask), `len(doc)`, token record `doc(doc)`; per term `df`;
//! - the write lock `Lock +^BM25Idx(name,"lock"):timeout` (:403-410), owned by at most one process.
//! Documents: 0 and 1 are the graph's corpus (what Build reads, :123-157), 2 is an extra document a writer inserts.
//! Tokens: two (t0, t1). Doc 0 = {t0,t1} len 2, doc 1 = {t1} len 1, doc 2 = {t0} len 1.
//!
//! Processes (each at most a bounded number of operations):
//! - Build (:97-175): `Kill ^BM25Idx(name)` (:99), one `IndexDoc` per corpus document (:178-204, tf, df+1, doc,
//!   len), then the header (:160-170, schema last); no lock, no transaction (journal-validated: 106 records, all
//!   outside a transaction, footprints/07.json). `Empty` builds over properties no node has: they index 0 documents
//!   and the index handle then raises IndexNotBuiltError (iris_vector_graph/_engine/vector.py:299-310), a refusal.
//!   A build may stop (crash) at any point.
//! - Writer: Insert of doc 2 (:442-493) and Delete of doc 0 (:496-514): RequireWritable (:385-394), LockWrite
//!   (or a timeout refusal, :403-410), RequireWritable again, then the body in one transaction (atomic here, as
//!   TSTART/TCOMMIT under the lock make it; journal-validated), RemoveDoc (:416-437) with `$Get(..,0)` defaults.
//! - Drop (:587-591): `Kill ^BM25Idx(name)`, no lock.
//! - Upgrade (:526-581): flag first, then the lock (or a timeout that clears the flag, :534-539), then one pass that
//!   recomputes df, doc, N, totalLen from the postings, flips schema to 2 and removes idf.
//!
//! Designs:
//! - `AsBuilt`: as above.
//! - `Quiesced`: as built, under the operator premise of HD-0701 option (c): no writer starts while a build runs.
//! - `Reviewed` (decisions.md HD-0701 working answer: serialize index modifications and publish a complete BM25
//!   generation or return unavailable, including Build, Drop, Insert, Delete and crash; F-0704 remedy: check the
//!   property list and row count before killing): Build takes the write lock for its whole run, writes a shadow
//!   generation, publishes it in one step and releases the lock; a crash releases the lock (IRIS releases a dead
//!   process's locks) and discards the shadow; an `Empty` build is refused before it changes anything; Drop takes
//!   the lock.
//! - `ControlNoLock`: Reviewed, but Build does not take the lock (a mutant the checker must catch).
//! - `ControlLateRefusal`: Reviewed, but the empty-corpus refusal is decided after the old index was cleared.
//!
//! Invariants (ontology/07-text-search.md): TXT-I1 (df is the count of documents holding the word; token records
//! match), TXT-I2 (N and totalLen match the stored documents), TXT-I3 (schema 2 holds no idf), TXT-X2 (a refused
//! build leaves the old index as it was; ghost). Action property TXT-I5 / TXT-B1.11 / TXT-B7.1 (two writers never
//! change one index at the same time: a step that changes index content is never taken while another process holds
//! the lock or is running a build). Progress (AG EF): the index can always settle (no operation in flight, I1-I3).
//!
//! # Machine `leg`: which BM25 index answers for which graph
//!
//! Abstracted real state: up to three BM25 indexes, each holding one graph's documents (D = default graph, A = a
//! named graph) and a recorded graph that is present (Build, :165-168) or absent (an index a first Insert created,
//! :461-466, or one built before 4.0.0). `Info` answers `graph: ""` when the subscript is absent (:612), which the
//! engine reads as the recorded graph (`_index_graph`, iris_vector_graph/_engine/vector.py:164-185).
//! Queries: engine fusion for graph g (`_fusion_leg_index`, vector.py:187-226), Cypher `ivg.bm25.search` with and
//! without `USE GRAPH` (`_index_graph_rows`, iris_vector_graph/cypher/translator.py:3125-3142: returns early under
//! a graph context), and `ivg.retrieve` under USE GRAPH (translator.py:3248-3292: reads `bm25_name` unchecked).
//! - `AsBuilt`: as above (F-0705, F-0707).
//! - `Reviewed` (HD-0703: never consult another graph's index; F-0705 remedy: Info answers null for an absent
//!   graph; F-0707 remedy: compare the recorded graph with the graph context and refuse a mismatch or an unknown).
//! - `ControlNoScopeCheck`: Reviewed without the USE GRAPH comparison.
//! Action properties: TXT-I7 / SYS-I2 (a scoped answer holds only that graph's nodes), TXT-B8.3 (rows of an index
//! are never labelled with a graph they do not belong to).
use breadth_b::*;
use explorer::*;

// =====================================================================================================================
// Machine bm25
// =====================================================================================================================

const ND: usize = 3;
const MASK: [u8; ND] = [0b11, 0b10, 0b01];
const LEN: [i8; ND] = [2, 1, 1];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Design { AsBuilt, Quiesced, Reviewed, ControlNoLock, ControlLateRefusal }

impl Design {
    fn build_locks(self) -> bool { matches!(self, Design::Reviewed | Design::ControlLateRefusal) }
    fn shadow(self) -> bool { matches!(self, Design::Reviewed | Design::ControlNoLock | Design::ControlLateRefusal) }
    fn early_refusal(self) -> bool { matches!(self, Design::Reviewed | Design::ControlNoLock) }
    fn drop_locks(self) -> bool { matches!(self, Design::Reviewed | Design::ControlNoLock | Design::ControlLateRefusal) }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, Default)]
pub struct Idx {
    pub n: Option<i8>,
    pub total: Option<i8>,
    pub schema: Option<u8>,
    pub graph: bool,
    pub upgrading: bool,
    pub idf: bool,
    pub post: [u8; ND],
    pub len: [i8; ND],
    pub doc: [u8; ND],
    pub df: [i8; 2],
}

impl Idx {
    /// Everything but the upgrade flag: the index's content.
    fn content(&self) -> Idx { Idx { upgrading: false, ..self.clone() } }
    fn exists(&self) -> bool { self.n.is_some() }
    fn schema(&self) -> u8 { self.schema.unwrap_or(1) }
    fn i1(&self) -> bool {
        if !(self.exists() && self.schema == Some(2)) { return true; }
        (0..2).all(|t| self.df[t] == (0..ND).filter(|&d| self.post[d] & (1 << t) != 0).count() as i8)
            && (0..ND).all(|d| self.doc[d] == self.post[d])
    }
    fn i2(&self) -> bool {
        if !(self.exists() && self.schema == Some(2)) { return true; }
        self.n == Some((0..ND).filter(|&d| self.len[d] > 0).count() as i8)
            && self.total == Some((0..ND).map(|d| self.len[d]).sum::<i8>())
    }
    fn i3(&self) -> bool { self.schema != Some(2) || !self.idf }
    fn index_doc(&mut self, d: usize) {
        self.post[d] |= MASK[d];
        for t in 0..2 { if MASK[d] & (1 << t) != 0 { self.df[t] += 1; } }
        self.doc[d] = MASK[d];
        self.len[d] = LEN[d];
    }
    /// RemoveDoc (BM25Index.cls:416-437): driven by the token record; N and totalLen with $Get(.., 0) defaults.
    fn remove_doc(&mut self, d: usize) {
        if self.len[d] == 0 && self.doc[d] == 0 { return; }
        let old = self.len[d];
        let rec = self.doc[d];
        for t in 0..2 {
            if rec & (1 << t) != 0 {
                self.post[d] &= !(1 << t);
                self.df[t] = (self.df[t] - 1).max(0);
            }
        }
        self.doc[d] = 0;
        self.len[d] = 0;
        self.n = Some(self.n.unwrap_or(0) - 1);
        self.total = Some(self.total.unwrap_or(0) - old);
    }
    fn require_writable(&self) -> bool { !(self.exists() && (self.upgrading || self.schema() < 2)) }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum BKind { Corpus, Empty }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Op { Ins, Del }
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Who { B, W, D, U }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum BPc { Idle, Running { kind: BKind, next: u8, n: i8, total: i8 }, Done, Crashed }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct S {
    pub vis: Idx,
    pub shadow: Option<Idx>,
    pub lock: Option<Who>,
    pub b: BPc,
    pub builds: u8,
    pub snap: Option<Idx>,
    pub refused_changed: bool,
    pub w: Option<Op>,
    pub wops: u8,
    pub d: u8,
    pub drops: u8,
    pub u: u8,
    pub ups: u8,
}

#[derive(Clone, Debug)]
pub enum A {
    BuildStart(BKind), BuildIndex, BuildFinish, BuildCrash,
    WBegin(Op), WTimeout(Op), WBody,
    DropAll, DropLock, DropBody,
    UpFlag, UpLock, UpTimeout, UpBody,
}

fn who(a: &A) -> Who {
    match a {
        A::BuildStart(_) | A::BuildIndex | A::BuildFinish | A::BuildCrash => Who::B,
        A::WBegin(_) | A::WTimeout(_) | A::WBody => Who::W,
        A::DropAll | A::DropLock | A::DropBody => Who::D,
        _ => Who::U,
    }
}

/// Processes in the middle of an operation on the index content (lock holders and a running build).
fn busy(s: &S) -> Vec<Who> {
    let mut v = vec![];
    if matches!(s.b, BPc::Running { .. }) { v.push(Who::B); }
    if let Some(h) = s.lock { if !v.contains(&h) { v.push(h); } }
    v
}

pub struct Bm25 { pub design: Design, /** restrict the initial states to one (0 missing, 1 schema 2, 2 schema 1) */ pub start: Option<usize> }

fn corpus_len(k: BKind) -> u8 { if k == BKind::Corpus { 2 } else { 0 } }

impl Model for Bm25 {
    type State = S;
    type Action = A;
    fn init_states(&self) -> Vec<S> {
        let base = S { vis: Idx::default(), shadow: None, lock: None, b: BPc::Idle, builds: 0, snap: None,
                       refused_changed: false, w: None, wops: 0, d: 0, drops: 0, u: 0, ups: 0 };
        // an existing schema 2 index holding doc 0 (built earlier for the graph)
        let mut s2 = Idx { n: Some(1), total: Some(2), schema: Some(2), graph: true, ..Idx::default() };
        s2.index_doc(0);
        // an existing schema 1 index holding doc 0: postings, len, idf and N; no df, no token records
        let mut s1 = Idx { n: Some(1), total: Some(2), schema: None, graph: false, idf: true, ..Idx::default() };
        s1.post[0] = MASK[0];
        s1.len[0] = LEN[0];
        let all = vec![base.clone(), S { vis: s2, ..base.clone() }, S { vis: s1, ..base }];
        match self.start { Some(i) => vec![all[i].clone()], None => all }
    }
    fn actions(&self, _: &S) -> Vec<A> {
        vec![A::BuildStart(BKind::Corpus), A::BuildStart(BKind::Empty), A::BuildIndex, A::BuildFinish, A::BuildCrash,
             A::WBegin(Op::Ins), A::WBegin(Op::Del), A::WTimeout(Op::Ins), A::WTimeout(Op::Del), A::WBody,
             A::DropAll, A::DropLock, A::DropBody, A::UpFlag, A::UpLock, A::UpTimeout, A::UpBody]
    }
    fn next(&self, s: &S, a: &A) -> Option<S> {
        let dsn = self.design;
        let mut t = s.clone();
        let building = matches!(s.b, BPc::Running { .. });
        match a {
            A::BuildStart(kind) => {
                if s.b != BPc::Idle || s.builds >= 1 { return None; }
                // HD-0701 option (c): the operator never runs a build beside another writer
                if dsn == Design::Quiesced && (s.w.is_some() || s.d != 0 || s.u != 0) { return None; }
                t.builds += 1;
                if *kind == BKind::Empty && dsn.early_refusal() {
                    t.b = BPc::Done; // refused before anything is written
                    return Some(t);
                }
                if dsn.build_locks() {
                    if s.lock.is_some() { return None; } // waits
                    t.lock = Some(Who::B);
                }
                if *kind == BKind::Empty { t.snap = Some(s.vis.content()); }
                if dsn.shadow() { t.shadow = Some(Idx::default()); } else { t.vis = Idx::default(); }
                t.b = BPc::Running { kind: *kind, next: 0, n: 0, total: 0 };
            }
            A::BuildIndex => {
                let BPc::Running { kind, next, n, total } = s.b.clone() else { return None };
                if next >= corpus_len(kind) { return None; }
                let d = next as usize;
                if dsn.shadow() { t.shadow.as_mut().unwrap().index_doc(d); } else { t.vis.index_doc(d); }
                t.b = BPc::Running { kind, next: next + 1, n: n + 1, total: total + LEN[d] };
            }
            A::BuildFinish => {
                let BPc::Running { kind, next, n, total } = s.b.clone() else { return None };
                if next < corpus_len(kind) { return None; }
                if dsn.shadow() {
                    let mut g = t.shadow.take().unwrap();
                    g.n = Some(n); g.total = Some(total); g.graph = true; g.schema = Some(2);
                    if kind == BKind::Empty {
                        // ControlLateRefusal: the refusal comes after the old generation was replaced
                        t.vis = g;
                    } else {
                        t.vis = g;
                    }
                } else {
                    t.vis.n = Some(n); t.vis.total = Some(total); t.vis.graph = true; t.vis.schema = Some(2);
                }
                if t.lock == Some(Who::B) { t.lock = None; }
                if kind == BKind::Empty {
                    // the engine raises IndexNotBuiltError: a refused command
                    if let Some(sn) = &t.snap { if t.vis.content() != *sn { t.refused_changed = true; } }
                    t.snap = None;
                }
                t.b = BPc::Done;
            }
            A::BuildCrash => {
                if !building { return None; }
                t.b = BPc::Crashed;
                t.shadow = None;
                t.snap = None;
                if t.lock == Some(Who::B) { t.lock = None; }
            }
            A::WBegin(op) => {
                if s.w.is_some() || s.wops >= 2 { return None; }
                if dsn == Design::Quiesced && building { return None; }
                if *op == Op::Del && !s.vis.exists() { t.wops += 1; return Some(t); } // Delete answers 0
                if !s.vis.require_writable() { t.wops += 1; return Some(t); } // refused
                if s.lock.is_some() { return None; } // waits
                t.lock = Some(Who::W);
                t.w = Some(*op);
            }
            A::WTimeout(op) => {
                if s.w.is_some() || s.wops >= 2 || s.lock.is_none() { return None; }
                if dsn == Design::Quiesced && building { return None; }
                if *op == Op::Del && !s.vis.exists() { return None; }
                if !s.vis.require_writable() { return None; }
                t.wops += 1; // refused, nothing changed (TXT-X7)
            }
            A::WBody => {
                let Some(op) = s.w else { return None };
                t.w = None;
                t.wops += 1;
                t.lock = None;
                if !s.vis.require_writable() { return Some(t); }
                match op {
                    Op::Ins => {
                        if !t.vis.exists() {
                            t.vis.n = Some(0); t.vis.total = Some(0); t.vis.schema = Some(2); // :461-466, no graph
                        }
                        t.vis.remove_doc(2);
                        t.vis.index_doc(2);
                        t.vis.n = Some(t.vis.n.unwrap() + 1);
                        t.vis.total = Some(t.vis.total.unwrap_or(0) + LEN[2]);
                    }
                    Op::Del => { t.vis.remove_doc(0); }
                }
            }
            A::DropAll => {
                if dsn.drop_locks() || s.drops >= 1 { return None; }
                if dsn == Design::Quiesced && building { return None; }
                t.vis = Idx::default();
                t.drops += 1;
            }
            A::DropLock => {
                if !dsn.drop_locks() || s.drops >= 1 || s.d != 0 || s.lock.is_some() { return None; }
                t.lock = Some(Who::D);
                t.d = 1;
            }
            A::DropBody => {
                if s.d != 1 { return None; }
                t.vis = Idx::default();
                t.lock = None;
                t.d = 0;
                t.drops += 1;
            }
            A::UpFlag => {
                if s.u != 0 || s.ups >= 1 { return None; }
                if dsn == Design::Quiesced && building { return None; }
                if !s.vis.exists() || (s.vis.schema() >= 2 && !s.vis.upgrading) { t.ups += 1; return Some(t); }
                t.vis.upgrading = true;
                t.u = 1;
            }
            A::UpLock => {
                if s.u != 1 || s.lock.is_some() { return None; }
                t.lock = Some(Who::U);
                t.u = 2;
            }
            A::UpTimeout => {
                if s.u != 1 || s.lock.is_none() { return None; }
                t.vis.upgrading = false;
                t.u = 0;
                t.ups += 1;
            }
            A::UpBody => {
                if s.u != 2 { return None; }
                let v = &mut t.vis;
                v.df = [0, 0];
                v.doc = [0; ND];
                for d in 0..ND {
                    for tk in 0..2 {
                        if v.post[d] & (1 << tk) != 0 { v.df[tk] += 1; v.doc[d] |= 1 << tk; }
                    }
                }
                v.n = Some((0..ND).filter(|&d| v.len[d] > 0).count() as i8);
                v.total = Some((0..ND).map(|d| v.len[d]).sum());
                v.schema = Some(2);
                v.idf = false;
                v.upgrading = false;
                t.lock = None;
                t.u = 0;
                t.ups += 1;
            }
        }
        Some(t)
    }
    fn invariants(&self) -> Vec<Invariant<S>> {
        vec![
            invariant(I1, |s: &S| s.vis.i1()),
            invariant(I2, |s: &S| s.vis.i2()),
            invariant(I3, |s: &S| s.vis.i3()),
            invariant(X2, |s: &S| !s.refused_changed),
        ]
    }
    fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
        vec![action_property(I5, |s: &S, a: &A, t: &S| {
            if s.vis.content() == t.vis.content() { return true; }
            let me = who(a);
            busy(s).iter().all(|&q| q == me)
        })]
    }
    fn always_possibly(&self) -> Vec<Invariant<S>> {
        vec![invariant(SETTLE, |s: &S| {
            !matches!(s.b, BPc::Running { .. }) && s.w.is_none() && s.d == 0 && s.u == 0
                && s.vis.i1() && s.vis.i2() && s.vis.i3()
        })]
    }
}

pub const I1: &str = "TXT-I1 each word's document frequency is the count of documents that hold it";
pub const I2: &str = "TXT-I2 the document count and total length match the stored documents";
pub const I3: &str = "TXT-I3 a schema 2 index holds no saved word weights";
pub const X2: &str = "TXT-X2 a refused build leaves the old index as it was";
pub const I5: &str = "TXT-I5 two writers never change one BM25 index at the same time";
pub const SETTLE: &str = "AG EF the index can always settle with no operation in flight and I1-I3 true";
const W_COMPLETE: &str = "witness: never a published complete index of the corpus";
const W_INSERT_AFTER: &str = "witness: never an insert that waited for a build and landed in its generation";
const W_CRASH_SAFE: &str = "witness: never a crashed build followed by a consistent index that holds the inserted doc";

fn complete(s: &S) -> bool {
    s.vis.n == Some(2) && s.vis.len[0] > 0 && s.vis.len[1] > 0 && s.vis.graph && s.vis.i1() && s.vis.i2()
        && s.vis.schema == Some(2) && s.b == BPc::Done
}
fn insert_after(s: &S) -> bool {
    s.vis.n == Some(3) && (0..ND).all(|d| s.vis.len[d] > 0) && s.vis.i1() && s.vis.i2() && s.b == BPc::Done
}
fn crash_safe(s: &S) -> bool { s.b == BPc::Crashed && s.vis.len[2] > 0 && s.vis.i1() && s.vis.i2() && s.w.is_none() }

// =====================================================================================================================
// Machine leg
// =====================================================================================================================

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum LDesign { AsBuilt, Reviewed, ControlNoScopeCheck }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum G { D, A }

/// One BM25 index: whose documents it holds and the graph it records (None = subscript absent).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct LIdx { pub holds: G, pub recorded: Option<G> }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Q { Fusion(G), CypherScoped(G, u8), CypherAll(u8), Retrieve(G, u8) }

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct LS {
    pub idx: [Option<LIdx>; 3],
    /// last answer: (query, rows' true graph, graph the rows were labelled with); None = refused or nothing
    pub last: Option<(Q, Option<G>, Option<G>)>,
    pub ops: u8,
}

#[derive(Clone, Debug)]
pub enum LA { Build(u8, G), InsertCreate(u8, G), Drop(u8), Ask(Q) }

pub struct Leg { pub design: LDesign, /** only engine fusion queries (no Cypher calls) */ pub fusion_only: bool }

impl Leg {
    /// The graph the engine thinks an index covers (`_index_graph`): as built, Info's "" for an absent subscript.
    fn seen(&self, i: &LIdx) -> Option<G> {
        match (self.design, i.recorded) {
            (_, Some(g)) => Some(g),
            (LDesign::AsBuilt, None) => Some(G::D),
            (_, None) => None,
        }
    }
}

impl Model for Leg {
    type State = LS;
    type Action = LA;
    fn init_states(&self) -> Vec<LS> {
        // with and without an index built before graphs were recorded (it holds the default graph's documents)
        vec![LS { idx: [None, None, None], last: None, ops: 0 },
             LS { idx: [Some(LIdx { holds: G::D, recorded: None }), None, None], last: None, ops: 0 }]
    }
    fn actions(&self, _: &LS) -> Vec<LA> {
        let mut v = vec![];
        for k in 0..3u8 {
            for g in [G::D, G::A] {
                v.push(LA::Build(k, g));
                v.push(LA::InsertCreate(k, g));
                if !self.fusion_only {
                    v.push(LA::Ask(Q::CypherScoped(g, k)));
                    v.push(LA::Ask(Q::Retrieve(g, k)));
                }
            }
            v.push(LA::Drop(k));
            if !self.fusion_only { v.push(LA::Ask(Q::CypherAll(k))); }
        }
        v.push(LA::Ask(Q::Fusion(G::D)));
        v.push(LA::Ask(Q::Fusion(G::A)));
        v
    }
    fn next(&self, s: &LS, a: &LA) -> Option<LS> {
        let mut t = s.clone();
        t.last = None;
        match a {
            LA::Build(k, g) => {
                if s.ops >= 3 { return None; }
                t.idx[*k as usize] = Some(LIdx { holds: *g, recorded: Some(*g) });
                t.ops += 1;
            }
            LA::InsertCreate(k, g) => {
                if s.ops >= 3 || s.idx[*k as usize].is_some() { return None; }
                t.idx[*k as usize] = Some(LIdx { holds: *g, recorded: None });
                t.ops += 1;
            }
            LA::Drop(k) => {
                if s.ops >= 3 || s.idx[*k as usize].is_none() { return None; }
                t.idx[*k as usize] = None;
                t.ops += 1;
            }
            LA::Ask(q) => {
                let ans = match *q {
                    Q::Fusion(g) => {
                        // first index whose (seen) graph is g, in registry order; as built, else an unknown one
                        let own = s.idx.iter().flatten().find(|i| self.seen(i) == Some(g));
                        let unknown = s.idx.iter().flatten().find(|i| self.seen(i).is_none());
                        match (own, unknown, self.design) {
                            (Some(i), _, _) => Some((i.holds, g)),
                            (None, Some(i), LDesign::AsBuilt) => Some((i.holds, g)),
                            _ => None,
                        }
                    }
                    Q::CypherScoped(g, k) | Q::Retrieve(g, k) => {
                        let i = s.idx[k as usize]?;
                        match self.design {
                            LDesign::Reviewed if self.seen(&i) != Some(g) => None, // refused
                            _ => Some((i.holds, g)),
                        }
                    }
                    Q::CypherAll(k) => {
                        let i = s.idx[k as usize]?;
                        match self.seen(&i) {
                            Some(lbl) => Some((i.holds, lbl)),
                            None => None, // refused: rows' graph unknown (TXT-X12)
                        }
                    }
                };
                t.last = ans.map(|(h, l)| (*q, Some(h), Some(l)));
            }
        }
        Some(t)
    }
    fn action_properties(&self) -> Vec<ActionProperty<LS, LA>> {
        vec![
            action_property(L_SCOPE, |_: &LS, _: &LA, t: &LS| match t.last {
                Some((Q::Fusion(g), Some(h), _)) | Some((Q::CypherScoped(g, _), Some(h), _)) | Some((Q::Retrieve(g, _), Some(h), _)) => h == g,
                _ => true,
            }),
            action_property(L_LABEL, |_: &LS, _: &LA, t: &LS| match t.last {
                Some((_, Some(h), Some(l))) => h == l,
                _ => true,
            }),
        ]
    }
}

pub const L_SCOPE: &str = "TXT-I7 a scoped BM25 answer holds only that graph's nodes";
pub const L_LABEL: &str = "TXT-B8.3 rows of an index are never labelled with a graph they do not belong to";
const L_W_SCOPED: &str = "witness: never a scoped fusion answer for the named graph from its own index";

fn show_bm25(c: &Counterexample<S, A>) -> String {
    let mut out = format!("counterexample for '{}' ({:?}), {} steps:\n  init: {}\n", c.property, c.kind, c.steps.len(), brief(&c.init));
    for (i, (a, s)) in c.steps.iter().enumerate() {
        out += &format!("  {:>2}. {:<22} {}\n", i + 1, format!("{:?}", a), brief(s));
    }
    out
}

fn brief(s: &S) -> String {
    let v = &s.vis;
    format!("N={:?} total={:?} schema={:?} graph={} up={} idf={} post={:?} len={:?} doc={:?} df={:?} | lock={:?} b={:?} w={:?} d={} u={} refused_changed={}",
            v.n, v.total, v.schema, v.graph, v.upgrading, v.idf, v.post, v.len, v.doc, v.df, s.lock, s.b, s.w, s.d, s.u, s.refused_changed)
}

pub fn checks() -> Vec<(&'static str, Box<dyn Fn() -> Outcome>)> {
    let m = "bm25";
    vec![
        check("m07-bm25-as-built-I2", move || judge("m07-bm25-as-built-I2", "07", m, "as-built", Expect::Violation(I2),
            "F-0701; TXT-I2, TXT-B1.11, HD-0701", explore(&Only::new(Bm25 { design: Design::AsBuilt, start: None }, &[I2]), limits()), show_bm25)),
        check("m07-bm25-as-built-I5", move || judge("m07-bm25-as-built-I5", "07", m, "as-built", Expect::Violation(I5),
            "F-0701; TXT-I5, TXT-B1.11, TXT-B7.1", explore(&Only::new(Bm25 { design: Design::AsBuilt, start: None }, &[I5]), limits()), show_bm25)),
        check("m07-bm25-as-built-X2", move || judge("m07-bm25-as-built-X2", "07", m, "as-built", Expect::Violation(X2),
            "F-0704; TXT-X2, SYS-I3", explore(&Only::new(Bm25 { design: Design::AsBuilt, start: None }, &[X2]), limits()), show_bm25)),
        check("m07-bm25-as-built-X2-existing", move || judge("m07-bm25-as-built-X2-existing", "07", m, "as-built", Expect::Violation(X2),
            "F-0704 from an existing schema 2 index (the live repro's shape)",
            explore(&Only::new(Bm25 { design: Design::AsBuilt, start: Some(1) }, &[X2]), limits()), show_bm25)),
        check("m07-bm25-as-built-settle", move || judge("m07-bm25-as-built-settle", "07", m, "as-built", Expect::Violation(SETTLE),
            "F-0701 progress: once corrupted the index cannot settle without a rebuild",
            explore(&Only::new(Bm25 { design: Design::AsBuilt, start: None }, &[SETTLE]), limits()), show_bm25)),
        check("m07-bm25-as-built-quiesced-crash", move || judge("m07-bm25-as-built-quiesced-crash", "07", m, "as-built",
            Expect::Violation(I2), "F-0701 (a stopped Build); HD-0701 option (c) premise alone",
            explore(&Only::new(Bm25 { design: Design::Quiesced, start: None }, &[I2]), limits()), show_bm25)),
        check("m07-bm25-reviewed", move || judge("m07-bm25-reviewed", "07", m, "reviewed", Expect::Pass,
            "HD-0701 reviewed: TXT-I1, I2, I3, X2, I5, AG EF settle", explore(&Bm25 { design: Design::Reviewed, start: None }, limits()), show_bm25)),
        check("m07-bm25-control-nolock", move || judge("m07-bm25-control-nolock", "07", m, "control", Expect::Violation(I5),
            "mutant: reviewed Build without the write lock", explore(&Bm25 { design: Design::ControlNoLock, start: None }, limits()), show_bm25)),
        check("m07-bm25-control-late-refusal", move || judge("m07-bm25-control-late-refusal", "07", m, "control", Expect::Violation(X2),
            "mutant: reviewed, empty-corpus refusal decided after the old generation is replaced",
            explore(&Bm25 { design: Design::ControlLateRefusal, start: None }, limits()), show_bm25)),
        check("m07-bm25-positive-complete", move || judge("m07-bm25-positive-complete", "07", m, "positive", Expect::Violation(W_COMPLETE),
            "sharpness: the reviewed design publishes a complete index",
            explore(&Only::new(Bm25 { design: Design::Reviewed, start: None }, &[]).witness(W_COMPLETE, complete), limits()), show_bm25)),
        check("m07-bm25-positive-insert-after-build", move || judge("m07-bm25-positive-insert-after-build", "07", m, "positive",
            Expect::Violation(W_INSERT_AFTER), "sharpness: an insert serialized after a build lands",
            explore(&Only::new(Bm25 { design: Design::Reviewed, start: None }, &[]).witness(W_INSERT_AFTER, insert_after), limits()), show_bm25)),
        check("m07-bm25-positive-crash-then-insert", move || judge("m07-bm25-positive-crash-then-insert", "07", m, "positive",
            Expect::Violation(W_CRASH_SAFE), "sharpness: after a crashed build the reviewed index takes an insert consistently",
            explore(&Only::new(Bm25 { design: Design::Reviewed, start: None }, &[]).witness(W_CRASH_SAFE, crash_safe), limits()), show_bm25)),
        check("m07-leg-as-built-scope", || judge("m07-leg-as-built-scope", "07", "leg", "as-built", Expect::Violation(L_SCOPE),
            "F-0705, F-0707; TXT-I7, SYS-I2", explore(&Only::new(Leg { design: LDesign::AsBuilt, fusion_only: false }, &[L_SCOPE]), limits()), show_debug)),
        check("m07-leg-as-built-label", || judge("m07-leg-as-built-label", "07", "leg", "as-built", Expect::Violation(L_LABEL),
            "F-0705; TXT-B8.3", explore(&Only::new(Leg { design: LDesign::AsBuilt, fusion_only: false }, &[L_LABEL]), limits()), show_debug)),
        check("m07-leg-as-built-fusion-unknown", || judge("m07-leg-as-built-fusion-unknown", "07", "leg", "as-built", Expect::Violation(L_SCOPE),
            "F-0705: engine fusion only; an insert-created index is taken as the default graph's",
            explore(&Only::new(Leg { design: LDesign::AsBuilt, fusion_only: true }, &[L_SCOPE]), limits()), show_debug)),
        check("m07-leg-reviewed", || judge("m07-leg-reviewed", "07", "leg", "reviewed", Expect::Pass,
            "HD-0703 reviewed: TXT-I7, TXT-B8.3", explore(&Leg { design: LDesign::Reviewed, fusion_only: false }, limits()), show_debug)),
        check("m07-leg-control-no-scope-check", || judge("m07-leg-control-no-scope-check", "07", "leg", "control", Expect::Violation(L_SCOPE),
            "mutant: reviewed without the USE GRAPH comparison", explore(&Leg { design: LDesign::ControlNoScopeCheck, fusion_only: false }, limits()), show_debug)),
        check("m07-leg-positive-scoped", || judge("m07-leg-positive-scoped", "07", "leg", "positive", Expect::Violation(L_W_SCOPED),
            "sharpness: the reviewed design answers a scoped fusion from the graph's own index",
            explore(&Only::new(Leg { design: LDesign::Reviewed, fusion_only: false }, &[]).witness(L_W_SCOPED,
                |s: &LS| matches!(s.last, Some((Q::Fusion(G::A), Some(G::A), Some(G::A))))), limits()), show_debug)),
    ]
}
