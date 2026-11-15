//! Module 10 (graph algorithms and traversal) models at pin 3eaa79cf.
//!
//! Five small machines over the abstracted real state the algorithms read. Every as-built design that reproduces a
//! finding is paired with a reviewed design (decisions.md working answers HD-1001, HD-1004 and the findings' remedies)
//! expected to pass, at least one control (a mutant of the reviewed design the checker must catch) and positive
//! witnesses (key states reachable, written as "never reaches X" and expected to be violated) or an AG EF goal.
//!
//! # Machine `cache`: the shared result cache (ALG-I4, ALG-B2.19, ALG-B16.2, ALG-B16.10, ALG-B16.11)
//!
//! Real state: `^IVG.AlgoCache(graphKey, algorithm, paramHash) = $LB(token, payload)` (iris_src/src/Graph/KG/AlgoCache.cls:1-13,
//! Put :45-50); the token is `^KG("__version")` (AlgoCache.cls:17-21), raised by `$Increment` on adjacency writes
//! (Adjacency.cls Put/PutShadow/Remove, e.g. :131-136) and never by a node written without an edge (F-1004).
//! `Lookup` reads the token and the entry in one call (AlgoCache.cls:27-36); on a miss the store computes and `Put`s
//! under the token read by Lookup (iris_vector_graph/stores/iris_sql_store.py:921-983).
//! - PPR's key holds the seeds and settings only (iris_sql_store.py:2248-2258) (F-1004).
//! - Global PageRank's key holds the node table's token `COUNT(*):MAX(%ID)` read by the engine BEFORE the cache
//!   lookup (_engine/algorithms.py:179-193, :784-792; iris_sql_store.py:2362-2378), and the edgeless nodes are read
//!   on a miss only, at compute time (R313). `COUNT:MAX` is not monotonic: deleting the newest node returns it to an
//!   earlier value.
//! Abstraction: base nodes a (id 1) and b (id 2) with an edge a->b that writers toggle; extra edgeless nodes x (the
//! PPR seed) and z, each given a fresh id at creation (ids never reused). Answers: PPR from [x] is "x scored" or {}
//! (an edgeless seed scores 1.0); global PageRank is the set of present extra nodes and the edge flag. Two callers
//! run Start (PageRank reads the node token) -> Lookup -> Compute -> Put, interleaved with writers. Bounds: at most
//! three calls in all, two edge writes, one erase; ids up to 5 (PPR checks) or 4 (PageRank checks: x and z once each).
//! Node deletes go through `Graph.KG.Eraser.EraseNodeIds`, whose `InvalidateDerived` raises the token and kills the
//! whole cache (Eraser.cls:1038-1053); creating a node without an edge moves nothing (both observed live,
//! b-10-live-cache).
//! Designs: `AsBuilt`; `Reviewed` (F-1004 remedy and ALG-B16.2 applied to nodes: every node create/delete raises a
//! monotonic node token by $Increment, read with the adjacency token inside Lookup and stored in the entry; a hit
//! needs both); `ControlNoBumpOnCreate` (Reviewed, but a node create does not raise the node token);
//! `ControlSilentDelete` (as built, but a delete raises no token: the R313 `COUNT:MAX` key then admits an ABA, so the
//! as-built PageRank key is sound only because deletes raise the adjacency token).
//! Property P_HIT (action, ALG-I4/ALG-B16.11/ALG-B2.19): an answer served from the cache equals a fresh computation
//! on some state the call overlapped (from its start to the lookup): linearizability, so a write that lands after a
//! call began may or may not be reflected.
//!
//! # Machine `nkg`: the interned snapshot and its readers (ALG-B12.4-12.7, ALG-B7, ALG-B7.4, ALG-I3, SYS-I8, SYS-I2)
//!
//! Real state: edges in `^KG("out", g, ...)` per graph; `^NKG(-1, ...)` graph-blind (ALG-D7); marks
//! `^NKG("$meta","invalidated")` (erase) and `("stale")` (a named graph lost its last edge, ALG-B12.5); built =
//! `^NKG("$NI")` non-empty. Writers: ordinary Put interns into ^NKG once built (ALG-B12.6); `Adjacency.PutShadow`
//! (a temporal edge's structural shadow) writes ^KG and the token but neither interns nor marks
//! (Adjacency.cls:111-140) (F-1005). TemporalIndex.InsertEdge takes that branch only when the adjacency functional index
//! is not declared (TemporalIndex.cls:104-112); with it declared (the default after initialize_schema) a temporal edge
//! asserts a structural row whose index interns into ^NKG like an ordinary Put (observed live, b-10-live-nkg-f1005), so
//! `PutTemporal` models the unindexed branch; erase marks invalidated; sync rebuilds ^NKG from ^KG, all graphs merged
//! (_engine/schema.py:2859-2922, TraversalBuild.BuildNKG). `EnsureNKG` (TraversalBuild.cls:399-424) rebuilds only on
//! a mark and never compares `^NKG("$meta","builtFrom")` with the token.
//! Edges: e0 = default a->b (ordinary), e1 = default a->c (temporal shadow), e2 = named graph a->d (ordinary; same id
//! a). Readers: an engine centrality method (named edges -> Python walk of the default graph, else EnsureNKG then
//! ^NKG, unbuilt -> Python walk; ALG-B5.11/5.19, ALG-B12.9); a snapshot procedure (refuses with named edges or no
//! snapshot; ALG-B7, ALG-B7.4); the random walk `NKGAccel.RandomWalkJson` (NKGAccelTraversal.cls:187-222: ^NKG with
//! no graph check and no EnsureNKG) (F-1002); a ^KG reader of the default graph (PageRank).
//! Designs: `AsBuilt`; `Reviewed` (PutShadow marks the snapshot stale, F-1005 remedy; the random walk walks the
//! default graph's ^KG, HD-1001 option (a)); `ControlEnsureIgnoresStale` (Reviewed, but EnsureNKG ignores the stale
//! mark); `ControlWalkMerged` (Reviewed, but the walk reads ^NKG unchecked).
//! Properties (action): P_FRESH (ALG-B12.7/SYS-I8: a reader that answers from the snapshot answers the default graph's
//! current edges, or it refuses/says stale) and P_SCOPE (ALG-I3/SYS-I2: a default-graph answer holds no named-graph
//! edge). AG EF: the snapshot can always become current again.
//!
//! # Machine `routes`: one answer whatever route runs (ALG-I1, ALG-I3, ALG-B14.7, HD-1001, HD-1004)
//!
//! Real state: the Arno library absent or loaded (its reader scope for a default-graph call is not known: P-1004 is
//! open and the sources disagree, F-1001, so the model admits both `DefaultOnly` and `Merged`); a proof-record entry
//! accepted or not (arno_readers.route, iris_vector_graph/arno_readers.py:257-280; no named-graph probe, unlike BFS
//! `_only_default_graph`, iris_sql_store.py:1842-1858); named graph edges present or not; n default-graph nodes.
//! Global PageRank: native reader lists every node (iris_sql_store.py:2396-2399), the owner at most CAP rows
//! (PageRank.cls:506-520; CAP = 10,000 scaled to 2 here) (F-1003). random_walk: [] without the library
//! (_engine/algorithms.py:658-678) (F-1002), ^NKG merged with it.
//! Designs: `AsBuilt`; `Reviewed` (route native only when no named graph has edges, as BFS does; one uncapped result
//! contract on both routes, HD-1004 objective; random walk in ObjectScript over the default graph, HD-1001 (a));
//! `ControlRouteNoProbe` (Reviewed without the named-graph probe); `ControlOwnerCap` (Reviewed with the owner cap).
//! Property P_SAME (action): the answer equals the reference answer (default graph, every node; ALG-I1, ALG-I3).
//!
//! # Machine `walk`: graph scope of walks (F-1008 VarLength every-graph mode, F-1009 khop seed check; ALG-I2/I3)
//!
//! Real state: graph 0 holds a->x and x->w, graph 1 holds x->y and the node z (shared id x). `VarLength.Setup` with `pAll = 1`
//! puts every graph key in pGraphs and `Adjacent` reads a node's edges in every graph (VarLength.cls:44-51,
//! :126-148); the translator passes `gall = 1` for a start that is not a correlated column
//! (iris_vector_graph/cypher/translator.py:15404-15431). `khop` walks graph 0 (BFSFastJson(seed, "", ...)) but checks
//! the seed in every graph (_engine/algorithms.py:600-626).
//! Designs: `AsBuilt`; `Reviewed` (every-graph mode walks each graph separately: the first hop fixes the graph; khop
//! checks the seed in graph 0); `ControlResetAtShared` (Reviewed, but the fixed graph is dropped at a node several
//! graphs share). Properties: P_ONE_GRAPH (a path's edges all belong to one graph; CONTEXT.md:38-43) and
//! P_KHOP_SCOPE (a default-graph khop answers only default-graph nodes).
//!
//! # Machine `degree`: parallel edges in degree centrality (F-1007)
//!
//! Real state: `DegreeCentralityJson` counts out-degree with `Adj.Degree` (the keyed triple's "#" multiplicity) and
//! in-degree by $Order over `^KG("in", g, node, p, s)`, one per source (Centrality.cls:88-139; the "#" count lives
//! only under ^KG("out"), Adjacency.cls:203-206, :255). Edges: k parallel a->b (multigraph mode) and one c->b.
//! Designs: `AsBuilt`; `Reviewed` (in-degree from the out mirror's multiplicity); `ControlDistinctOut` (Reviewed,
//! but out-degree counts distinct targets). Invariant I_HANDSHAKE (CONTEXT.md:103-108: parallel edges each count):
//! the out-degrees and the in-degrees each sum to the number of edges.
use breadth_b::*;
use explorer::*;

// ============================================================================================ cache
mod cache {
    use explorer::*;

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Design { AsBuilt, Reviewed, ControlNoBumpOnCreate, ControlSilentDelete }

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Alg { Ppr, Pr }

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Ans { Ppr(bool), Pr(u8, bool) }

    pub type NTok = (u8, u8); // COUNT(*), MAX(%ID)

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Key { Ppr, Pr(Option<NTok>) }

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Phase {
        Idle,
        /// `seen`: ghost bitmask of the fresh answers of every state since the call started (linearization points)
        Started { alg: Alg, ntok: NTok, seen: u16 },
        Missed { alg: Alg, ntok: NTok, ver: u8, nver: u8 },
        Computed { alg: Alg, ntok: NTok, ver: u8, nver: u8, ans: Ans },
    }

    #[derive(Clone, Debug, PartialEq, Eq, Hash)]
    pub struct S {
        pub edge: bool,
        pub x: Option<u8>,
        pub z: Option<u8>,
        pub z_made: bool,
        pub next_id: u8,
        pub ver: u8,  // ^KG("__version")
        pub nver: u8, // reviewed: monotonic node token
        pub cache: Vec<(Key, u8, u8, Ans)>, // sorted by key; (key, token, node token, answer)
        pub callers: [Phase; 2],
        pub calls: [u8; 2],
        pub edge_writes: u8,
        pub erases: u8,
    }

    #[derive(Clone, Copy, Debug)]
    pub enum A {
        WriteEdge, CreateX, DeleteX, CreateZ, DeleteZ, EraseGraph,
        Start(usize, Alg), Lookup(usize), Compute(usize), Put(usize),
    }

    pub struct M { pub design: Design, pub algs: Vec<Alg>, pub max_id: u8 }

    pub fn ntok(s: &S) -> NTok {
        let count = 2 + s.x.is_some() as u8 + s.z.is_some() as u8;
        let max = [Some(2u8), s.x, s.z].iter().flatten().copied().max().unwrap();
        (count, max)
    }

    pub fn code(a: Ans) -> u16 {
        match a { Ans::Ppr(b) => b as u16, Ans::Pr(m, e) => 2 + (m as u16) * 2 + e as u16 }
    }

    pub fn fresh(s: &S, alg: Alg) -> Ans {
        match alg {
            Alg::Ppr => Ans::Ppr(s.x.is_some()),
            Alg::Pr => Ans::Pr((s.x.is_some() as u8) | ((s.z.is_some() as u8) << 1), s.edge),
        }
    }

    impl M {
        fn key(&self, alg: Alg, nt: NTok) -> Key {
            match (alg, self.design) {
                (Alg::Ppr, _) => Key::Ppr,
                (Alg::Pr, Design::AsBuilt | Design::ControlSilentDelete) => Key::Pr(Some(nt)),
                (Alg::Pr, _) => Key::Pr(None),
            }
        }
        /// Some(answer) when Lookup would hit in state s for caller phase Started{alg, ntok}.
        pub fn hit(&self, s: &S, alg: Alg, nt: NTok) -> Option<Ans> {
            let k = self.key(alg, nt);
            let e = s.cache.iter().find(|e| e.0 == k)?;
            let node_ok = match self.design { Design::AsBuilt | Design::ControlSilentDelete => true, _ => e.2 == s.nver };
            if e.1 == s.ver && node_ok { Some(e.3) } else { None }
        }
        /// A node write. Every delete goes through Graph.KG.Eraser.EraseNodeIds, whose InvalidateDerived raises
        /// ^KG("__version") (ArnoAccel.BumpVersion) and kills ^IVG.AlgoCache (Eraser.cls:1038-1053, ArnoAccel.cls:299-302;
        /// observed live: b-10-live-cache, an edgeless delete moved the token by 2); a create without an edge moves no
        /// token (observed live). `ControlSilentDelete` removes the delete's bump to show the R313 key depends on it.
        fn node_write(&self, u: &mut S, delete: bool) {
            if delete && self.design != Design::ControlSilentDelete { u.ver += 1; u.cache.clear(); }
            match self.design {
                Design::AsBuilt | Design::ControlSilentDelete => {}
                Design::Reviewed => u.nver += 1,
                Design::ControlNoBumpOnCreate => if delete { u.nver += 1 },
            }
        }
    }

    impl Model for M {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> {
            vec![S { edge: true, x: None, z: None, z_made: false, next_id: 3, ver: 1, nver: 0, cache: vec![],
                     callers: [Phase::Idle, Phase::Idle], calls: [0, 0], edge_writes: 0, erases: 0 }]
        }
        fn actions(&self, _: &S) -> Vec<A> {
            let mut v = vec![A::WriteEdge, A::CreateX, A::DeleteX, A::CreateZ, A::DeleteZ, A::EraseGraph];
            for c in 0..2 {
                for &al in &self.algs { v.push(A::Start(c, al)); }
                v.push(A::Lookup(c)); v.push(A::Compute(c)); v.push(A::Put(c));
            }
            v
        }
        fn next(&self, s: &S, a: &A) -> Option<S> {
            let mut u = s.clone();
            match *a {
                A::WriteEdge => {
                    if s.edge_writes >= 2 { return None; }
                    u.edge = !s.edge; u.ver += 1; u.edge_writes += 1;
                }
                A::CreateX => {
                    if s.x.is_some() || s.next_id > self.max_id { return None; }
                    u.x = Some(s.next_id); u.next_id += 1; self.node_write(&mut u, false);
                }
                A::DeleteX => {
                    s.x?; u.x = None; self.node_write(&mut u, true);
                }
                A::CreateZ => {
                    if s.z_made || s.next_id > self.max_id { return None; }
                    u.z = Some(s.next_id); u.next_id += 1; u.z_made = true; self.node_write(&mut u, false);
                }
                A::DeleteZ => { s.z?; u.z = None; self.node_write(&mut u, true); }
                A::EraseGraph => {
                    // Eraser: rows and adjacency go, the graph's cache entries are killed (AlgoCache.InvalidateGraph,
                    // ALG-B16.10); its adjacency writes raise the token.
                    if s.erases >= 1 { return None; }
                    u.erases += 1; u.edge = false; u.x = None; u.z = None; u.cache.clear(); u.ver += 1;
                    self.node_write(&mut u, true);
                }
                A::Start(c, al) => {
                    // at most three calls in all (two callers); the node token matters only where it keys the entry
                    if s.callers[c] != Phase::Idle || s.calls[0] + s.calls[1] >= 3 { return None; }
                    u.calls[c] += 1;
                    let nt = if matches!(self.design, Design::AsBuilt | Design::ControlSilentDelete) && al == Alg::Pr { ntok(s) } else { (0, 0) };
                    u.callers[c] = Phase::Started { alg: al, ntok: nt, seen: 1 << code(fresh(s, al)) };
                }
                A::Lookup(c) => {
                    let Phase::Started { alg, ntok: nt, .. } = s.callers[c] else { return None };
                    u.callers[c] = match self.hit(s, alg, nt) {
                        Some(_) => Phase::Idle,
                        None => Phase::Missed { alg, ntok: nt, ver: s.ver, nver: s.nver },
                    };
                }
                A::Compute(c) => {
                    let Phase::Missed { alg, ntok: nt, ver, nver } = s.callers[c] else { return None };
                    u.callers[c] = Phase::Computed { alg, ntok: nt, ver, nver, ans: fresh(s, alg) };
                }
                A::Put(c) => {
                    // (Put writes only the cache; no answer changes)
                    let Phase::Computed { alg, ntok: nt, ver, nver, ans } = s.callers[c] else { return None };
                    let k = self.key(alg, nt);
                    u.cache.retain(|e| e.0 != k);
                    u.cache.push((k, ver, nver, ans));
                    u.cache.sort_by_key(|e| match e.0 { Key::Ppr => (0u8, 0u8, 0u8), Key::Pr(None) => (1, 0, 0), Key::Pr(Some((a, b))) => (2, a, b) });
                    u.callers[c] = Phase::Idle;
                }
            }
            if matches!(a, A::WriteEdge | A::CreateX | A::DeleteX | A::CreateZ | A::DeleteZ | A::EraseGraph) {
                let snapshot = u.clone();
                for p in u.callers.iter_mut() {
                    if let Phase::Started { alg, seen, .. } = p { *seen |= 1 << code(fresh(&snapshot, *alg)); }
                }
            }
            Some(u)
        }
        fn always_possibly(&self) -> Vec<Invariant<S>> {
            vec![invariant("callers can always finish", |s: &S| s.callers.iter().all(|p| *p == Phase::Idle))]
        }
    }

    pub const P_HIT: &str = "a cached answer served equals a fresh computation of a state the call overlapped (ALG-I4, ALG-B16.11, ALG-B2.19)";

    pub fn props(design: Design) -> Vec<ActionProperty<S, A>> {
        let m = M { design, algs: vec![], max_id: 0 };
        vec![action_property(P_HIT, move |s: &S, a: &A, _t: &S| {
            if let A::Lookup(c) = *a {
                if let Phase::Started { alg, ntok: nt, seen } = s.callers[c] {
                    // linearizable: the served answer is the fresh answer of some state the call overlapped
                    if let Some(ans) = m.hit(s, alg, nt) { return (seen | (1 << code(fresh(s, alg)))) & (1 << code(ans)) != 0; }
                }
            }
            true
        })]
    }

    /// The model with its property attached.
    pub struct Checked { pub m: M }
    impl Model for Checked {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> { self.m.init_states() }
        fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
        fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
        fn action_properties(&self) -> Vec<ActionProperty<S, A>> { props(self.m.design) }
        fn always_possibly(&self) -> Vec<Invariant<S>> { self.m.always_possibly() }
    }
}

// ============================================================================================ nkg
mod nkg {
    use explorer::*;

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Design { AsBuilt, Reviewed, ControlEnsureIgnoresStale, ControlWalkMerged }

    // edge bits: E0 default a->b (ordinary), E1 default a->c (temporal shadow), E2 named a->d
    pub const E0: u8 = 1;
    pub const E1: u8 = 2;
    pub const E2: u8 = 4;
    pub const DEFAULT: u8 = E0 | E1;

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Answer { Edges(u8), Refused }

    #[derive(Clone, Debug, PartialEq, Eq, Hash)]
    pub struct S {
        pub kg: u8,
        pub nkg: u8,
        pub built: bool,
        pub invalidated: bool,
        pub stale: bool,
        pub writes: u8,
        pub last: Option<(R, Answer)>, // ghost: the last read and its answer
    }

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum R { Centrality, SnapshotProc, RandomWalk, KgReader }

    #[derive(Clone, Copy, Debug)]
    pub enum A { PutDefault, RemoveDefault, PutTemporal, PutNamed, RemoveNamed, EraseNamed, Sync, Read(R) }

    pub struct M { pub design: Design }

    impl M {
        /// EnsureNKG (TraversalBuild.cls:399-424): rebuild on a mark; answers whether ^NKG is built.
        fn ensure(&self, u: &mut S) -> bool {
            let stale = u.stale && self.design != Design::ControlEnsureIgnoresStale;
            if u.built && !stale { return true; }
            if !u.invalidated && !stale { return false; }
            u.nkg = u.kg; u.built = true; u.invalidated = false; u.stale = false;
            true
        }
        fn read(&self, u: &mut S, r: R) -> Answer {
            let named = u.kg & E2 != 0;
            match r {
                R::KgReader => Answer::Edges(u.kg & DEFAULT),
                R::Centrality => {
                    if named { return Answer::Edges(u.kg & DEFAULT); } // Python walk of the default graph (ALG-B5.19)
                    if self.ensure(u) { Answer::Edges(u.nkg) } else { Answer::Edges(u.kg & DEFAULT) } // ALG-B12.9
                }
                R::SnapshotProc => {
                    if named { return Answer::Refused; } // RefuseMergedGraphs (ALG-B7)
                    if self.ensure(u) { Answer::Edges(u.nkg) } else { Answer::Refused } // "^NKG not built" (ALG-B7.4)
                }
                R::RandomWalk => match self.design {
                    // NKGAccelTraversal.RandomWalkJson: ^NKG when built, no graph check, no EnsureNKG; else the
                    // legacy unsharded ^KG("out", node) layout, which holds nothing in production.
                    Design::AsBuilt | Design::ControlWalkMerged => if u.built { Answer::Edges(u.nkg) } else { Answer::Edges(0) },
                    // HD-1001 (a): an ObjectScript walk of the default graph's ^KG
                    _ => Answer::Edges(u.kg & DEFAULT),
                },
            }
        }
    }

    impl Model for M {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> {
            vec![S { kg: E0, nkg: 0, built: false, invalidated: false, stale: false, writes: 0, last: None }]
        }
        fn actions(&self, _: &S) -> Vec<A> {
            vec![A::PutDefault, A::RemoveDefault, A::PutTemporal, A::PutNamed, A::RemoveNamed, A::EraseNamed, A::Sync,
                 A::Read(R::Centrality), A::Read(R::SnapshotProc), A::Read(R::RandomWalk), A::Read(R::KgReader)]
        }
        fn next(&self, s: &S, a: &A) -> Option<S> {
            let mut u = s.clone();
            u.last = None;
            let write = !matches!(a, A::Read(_) | A::Sync);
            if write { if s.writes >= 4 { return None; } u.writes += 1; }
            match *a {
                A::PutDefault => { if s.kg & E0 != 0 { return None; } u.kg |= E0; if s.built { u.nkg |= E0; } }
                A::RemoveDefault => { if s.kg & E0 == 0 { return None; } u.kg &= !E0; u.nkg &= !E0; }
                A::PutTemporal => {
                    if s.kg & E1 != 0 { return None; }
                    u.kg |= E1; // PutShadow: ^KG and the token only
                    if self.design != Design::AsBuilt && s.built { u.stale = true; }
                }
                A::PutNamed => { if s.kg & E2 != 0 { return None; } u.kg |= E2; if s.built { u.nkg |= E2; } }
                A::RemoveNamed => {
                    if s.kg & E2 == 0 { return None; }
                    // last named edge gone: stale when ^NKG is built and interns an end (Adjacency.cls:169-180, ALG-B12.5)
                    u.kg &= !E2; u.nkg &= !E2; if s.built { u.stale = true; }
                }
                A::EraseNamed => {
                    if s.kg & E2 == 0 { return None; }
                    // Eraser.InvalidateDerived (Eraser.cls:1038-1046): DropNKG, and mark invalidated when it was built
                    u.kg &= !E2; u.invalidated = s.built; u.nkg = 0; u.built = false;
                }
                A::Sync => { u.nkg = u.kg; u.built = true; u.invalidated = false; u.stale = false; }
                A::Read(r) => { let ans = self.read(&mut u, r); u.last = Some((r, ans)); }
            }
            Some(u)
        }
        fn always_possibly(&self) -> Vec<Invariant<S>> {
            vec![invariant("the snapshot can always become current", |s: &S| s.built && s.nkg == s.kg && !s.stale && !s.invalidated)]
        }
    }

    pub const P_FRESH: &str = "a snapshot reader answers the default graph's current edges or refuses (ALG-B12.7, SYS-I8)";
    pub const P_SCOPE: &str = "a default-graph answer holds no named-graph edge (ALG-I3, SYS-I2)";

    pub struct Checked { pub m: M, pub keep: Vec<&'static str>, pub witness: Option<(&'static str, fn(&S) -> bool)> }
    impl Model for Checked {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> { self.m.init_states() }
        fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
        fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
        fn invariants(&self) -> Vec<Invariant<S>> {
            match self.witness { Some((n, g)) => vec![invariant(n, move |s: &S| !g(s))], None => vec![] }
        }
        fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
            let mut v = vec![];
            if self.keep.contains(&P_FRESH) {
                v.push(action_property(P_FRESH, |_s: &S, _a: &A, t: &S| match t.last {
                    Some((_, Answer::Edges(e))) => e == t.kg & DEFAULT,
                    _ => true,
                }));
            }
            if self.keep.contains(&P_SCOPE) {
                v.push(action_property(P_SCOPE, |_s: &S, _a: &A, t: &S| match t.last {
                    Some((_, Answer::Edges(e))) => e & E2 == 0,
                    _ => true,
                }));
            }
            v
        }
        fn always_possibly(&self) -> Vec<Invariant<S>> {
            if self.keep.contains(&"progress") { self.m.always_possibly() } else { vec![] }
        }
    }
}

// ============================================================================================ routes
mod routes {
    use explorer::*;

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Design { AsBuilt, Reviewed, ControlRouteNoProbe, ControlOwnerCap }

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Lib { Absent, DefaultOnly, Merged }

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Alg { PageRank, RandomWalk }

    /// An answer: rows of default-graph nodes listed, and whether named-graph nodes are mixed in.
    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub struct Ans { pub rows: u8, pub named: bool }

    pub const CAP: u8 = 2; // PageRank.cls:506-520 stops at 10,000 rows; scaled

    #[derive(Clone, Debug, PartialEq, Eq, Hash)]
    pub struct S { pub lib: Lib, pub proven: bool, pub named: bool, pub n: u8, pub last: Option<(Alg, bool, Ans)> }

    #[derive(Clone, Copy, Debug)]
    pub enum A { Load(Lib), Unload, Prove, AddNode, AddNamedEdge, Call(Alg) }

    pub struct M { pub design: Design, pub algs: Vec<Alg>, pub max_n: u8, pub libs: bool }

    impl M {
        pub fn all(design: Design) -> Self { M { design, algs: vec![Alg::PageRank, Alg::RandomWalk], max_n: 3, libs: true } }
        fn native(&self, s: &S) -> bool {
            let loaded = s.lib != Lib::Absent;
            let probe = matches!(self.design, Design::Reviewed | Design::ControlOwnerCap);
            loaded && s.proven && !(probe && s.named)
        }
        fn answer(&self, s: &S, alg: Alg) -> (bool, Ans) {
            let native = self.native(s);
            match alg {
                Alg::PageRank => {
                    if native {
                        (true, Ans { rows: s.n, named: s.lib == Lib::Merged && s.named })
                    } else {
                        let capped = matches!(self.design, Design::AsBuilt | Design::ControlOwnerCap);
                        (false, Ans { rows: if capped { s.n.min(CAP) } else { s.n }, named: false })
                    }
                }
                Alg::RandomWalk => match self.design {
                    Design::AsBuilt => {
                        if s.lib != Lib::Absent { (true, Ans { rows: s.n, named: s.named }) } // ^NKG, every graph merged
                        else { (false, Ans { rows: 0, named: false }) } // [] without the library
                    }
                    _ => (false, Ans { rows: s.n, named: false }),
                },
            }
        }
    }

    impl Model for M {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> {
            vec![S { lib: Lib::Absent, proven: false, named: false, n: 1, last: None }]
        }
        fn actions(&self, _: &S) -> Vec<A> {
            let mut v = vec![A::Prove, A::AddNode, A::AddNamedEdge];
            if self.libs { v.extend([A::Load(Lib::DefaultOnly), A::Load(Lib::Merged), A::Unload]); }
            v.extend(self.algs.iter().map(|&a| A::Call(a)));
            v
        }
        fn next(&self, s: &S, a: &A) -> Option<S> {
            let mut u = s.clone();
            u.last = None;
            match *a {
                A::Load(l) => { if s.lib != Lib::Absent { return None; } u.lib = l; }
                A::Unload => { if s.lib == Lib::Absent { return None; } u.lib = Lib::Absent; }
                A::Prove => { if s.proven { return None; } u.proven = true; }
                A::AddNode => { if s.n >= self.max_n { return None; } u.n += 1; }
                A::AddNamedEdge => { if s.named { return None; } u.named = true; }
                A::Call(alg) => { let (nat, ans) = self.answer(s, alg); u.last = Some((alg, nat, ans)); }
            }
            Some(u)
        }
    }

    pub const P_SAME: &str = "every route answers the default graph's reference result (ALG-I1, ALG-I3, HD-1004)";

    /// The machine restricted to a library whose readers read only graph 0 (P-1004 as premised).
    pub struct DefaultOnlyLib(pub M);
    impl Model for DefaultOnlyLib {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> { self.0.init_states() }
        fn actions(&self, s: &S) -> Vec<A> { self.0.actions(s).into_iter().filter(|a| !matches!(a, A::Load(Lib::Merged))).collect() }
        fn next(&self, s: &S, a: &A) -> Option<S> { self.0.next(s, a) }
        fn action_properties(&self) -> Vec<ActionProperty<S, A>> { Checked { m: M { design: self.0.design, algs: vec![], max_n: 0, libs: false }, witness: None }.action_properties() }
    }

    pub struct Checked { pub m: M, pub witness: Option<(&'static str, fn(&S) -> bool)> }
    impl Model for Checked {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> { self.m.init_states() }
        fn actions(&self, s: &S) -> Vec<A> { self.m.actions(s) }
        fn next(&self, s: &S, a: &A) -> Option<S> { self.m.next(s, a) }
        fn invariants(&self) -> Vec<Invariant<S>> {
            match self.witness { Some((n, g)) => vec![invariant(n, move |s: &S| !g(s))], None => vec![] }
        }
        fn action_properties(&self) -> Vec<ActionProperty<S, A>> {
            vec![action_property(P_SAME, |s: &S, _a: &A, t: &S| match t.last {
                Some((_, _, ans)) => ans == Ans { rows: s.n, named: false },
                None => true,
            })]
        }
    }
}

// ============================================================================================ walk
mod walk {
    use explorer::*;

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Design { AsBuilt, Reviewed, ControlResetAtShared }

    // nodes: 0 = a (g0), 1 = x (g0 and g1), 2 = y (g1), 3 = z (g1 only), 4 = w (g0)
    pub const EDGES: [(u8, u8, u8); 3] = [(0, 0, 1), (1, 1, 2), (0, 1, 4)]; // (graph, src, dst)
    pub fn in_graph(g: u8, n: u8) -> bool { matches!((g, n), (0, 0) | (0, 1) | (0, 4) | (1, 1) | (1, 2) | (1, 3)) }

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Mode { Correlated, Every }

    #[derive(Clone, Debug, PartialEq, Eq, Hash)]
    pub struct S {
        pub at: Option<u8>,
        pub mode: Mode,
        pub fixed: Option<u8>, // reviewed: graph fixed by the first hop
        pub used: u8,          // bit per graph used by the path
        pub hops: u8,
        pub khop: Option<Vec<u8>>, // ghost: the last khop answer
        pub starts: u8,
    }

    #[derive(Clone, Copy, Debug)]
    pub enum A { Start(Mode), Hop(usize), Khop(u8) }

    pub struct M { pub design: Design }

    impl Model for M {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> {
            vec![S { at: None, mode: Mode::Every, fixed: None, used: 0, hops: 0, khop: None, starts: 0 }]
        }
        fn actions(&self, _: &S) -> Vec<A> {
            vec![A::Start(Mode::Correlated), A::Start(Mode::Every), A::Hop(0), A::Hop(1), A::Hop(2), A::Khop(0), A::Khop(3)]
        }
        fn next(&self, s: &S, a: &A) -> Option<S> {
            let mut u = s.clone();
            u.khop = None;
            match *a {
                A::Start(m) => {
                    if s.starts >= 2 { return None; }
                    u.starts += 1; u.at = Some(0); u.mode = m; u.used = 0; u.hops = 0;
                    u.fixed = if m == Mode::Correlated { Some(0) } else { None };
                }
                A::Hop(i) => {
                    let at = s.at?;
                    let (g, src, dst) = EDGES[i];
                    if src != at || s.hops >= 2 { return None; }
                    let allowed = match (self.design, s.mode) {
                        (_, Mode::Correlated) => g == 0, // the start's graph (n.node_id column, gall = 0)
                        (Design::AsBuilt, Mode::Every) => true, // Adjacent reads every graph at each hop
                        (_, Mode::Every) => s.fixed.is_none_or(|f| f == g),
                    };
                    if !allowed { return None; }
                    u.at = Some(dst); u.hops += 1; u.used |= 1 << g;
                    if self.design != Design::AsBuilt && s.mode == Mode::Every {
                        u.fixed = Some(g);
                        // control: the fixed graph is forgotten at a node several graphs share
                        if self.design == Design::ControlResetAtShared && in_graph(0, dst) && in_graph(1, dst) { u.fixed = None; }
                    }
                }
                A::Khop(seed) => {
                    // BFSFastJson(seed, "", ...) walks graph 0; a seed with no out-edge answers [seed] when it exists
                    let has_out0 = EDGES.iter().any(|e| e.0 == 0 && e.1 == seed);
                    let exists = match self.design { Design::AsBuilt => (0..2).any(|g| in_graph(g, seed)), _ => in_graph(0, seed) };
                    u.khop = Some(if has_out0 { vec![seed, 1] } else if exists { vec![seed] } else { vec![] });
                }
            }
            Some(u)
        }
        fn invariants(&self) -> Vec<Invariant<S>> {
            vec![
                invariant(P_ONE_GRAPH, |s: &S| s.used.count_ones() <= 1),
                invariant(P_KHOP_SCOPE, |s: &S| s.khop.as_ref().is_none_or(|v| v.iter().all(|&n| in_graph(0, n)))),
            ]
        }
    }

    pub const P_ONE_GRAPH: &str = "a walk's edges all belong to one graph (ALG-I2, CONTEXT.md:38-43)";
    pub const P_KHOP_SCOPE: &str = "a default-graph khop answers only default-graph nodes (ALG-I3)";
}

// ============================================================================================ degree
mod degree {
    use explorer::*;

    #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
    pub enum Design { AsBuilt, Reviewed, ControlDistinctOut }

    #[derive(Clone, Debug, PartialEq, Eq, Hash)]
    pub struct S { pub ab: u8, pub cb: bool }

    #[derive(Clone, Copy, Debug)]
    pub enum A { AddAB, DelAB, AddCB }

    pub struct M { pub design: Design }

    impl M {
        pub fn sums(&self, s: &S) -> (u8, u8, u8) {
            let edges = s.ab + s.cb as u8;
            let out_a = match self.design { Design::ControlDistinctOut => (s.ab > 0) as u8, _ => s.ab }; // Adj.Degree "#"
            let out = out_a + s.cb as u8;
            let in_b = match self.design {
                Design::AsBuilt => (s.ab > 0) as u8 + s.cb as u8, // $Order over ^KG("in", g, b, p, s): one per source
                _ => s.ab + s.cb as u8,
            };
            (out, in_b, edges)
        }
    }

    impl Model for M {
        type State = S;
        type Action = A;
        fn init_states(&self) -> Vec<S> { vec![S { ab: 0, cb: false }] }
        fn actions(&self, _: &S) -> Vec<A> { vec![A::AddAB, A::DelAB, A::AddCB] }
        fn next(&self, s: &S, a: &A) -> Option<S> {
            let mut u = s.clone();
            match a {
                A::AddAB => { if s.ab >= 3 { return None; } u.ab += 1; }
                A::DelAB => { if s.ab == 0 { return None; } u.ab -= 1; }
                A::AddCB => { if s.cb { return None; } u.cb = true; }
            }
            Some(u)
        }
        fn invariants(&self) -> Vec<Invariant<S>> {
            let m = M { design: self.design };
            vec![invariant(I_HANDSHAKE, move |s: &S| { let (o, i, e) = m.sums(s); o == e && i == e })]
        }
    }

    pub const I_HANDSHAKE: &str = "out-degrees and in-degrees each sum to the number of edges (parallel edges count)";
}

/// The as-built PageRank route with only the default-graph-only library variant (P-1004 as premised).
fn routes_default_only() -> routes::DefaultOnlyLib {
    routes::DefaultOnlyLib(routes::M { design: routes::Design::AsBuilt, algs: vec![routes::Alg::PageRank], max_n: routes::CAP, libs: true })
}

// ============================================================================================ checks
pub fn checks() -> Vec<(&'static str, Box<dyn Fn() -> Outcome>)> {
    use cache::{Alg, Checked as CC, Design as CD, M as CM, P_HIT};
    use nkg::{Checked as NC, Design as ND, M as NM, P_FRESH, P_SCOPE};
    use routes::{Checked as RC, Design as RD, M as RM, P_SAME};
    use walk::{Design as WD, M as WM, P_KHOP_SCOPE, P_ONE_GRAPH};
    use degree::{Design as DD, M as DM, I_HANDSHAKE};
    vec![
        // ---- cache
        check("m10-cache-as-built-ppr", || judge("m10-cache-as-built-ppr", "10", "cache", "as-built", Expect::Violation(P_HIT),
            "F-1004; ALG-B2.19, ALG-B16.11, ALG-I4",
            explore(&CC { m: CM { design: CD::AsBuilt, algs: vec![Alg::Ppr], max_id: 5 } }, limits()), show_debug)),
        check("m10-cache-as-built-pagerank", || judge("m10-cache-as-built-pagerank", "10", "cache", "as-built", Expect::Pass,
            "R313 node-token key (COUNT:MAX) for global PageRank holds within bounds because node deletes raise the token (live b-10-live-cache); ALG-I4, ALG-B1.12",
            explore(&CC { m: CM { design: CD::AsBuilt, algs: vec![Alg::Pr], max_id: 4 } }, limits()), show_debug)),
        check("m10-cache-reviewed-ppr", || judge("m10-cache-reviewed-ppr", "10", "cache", "reviewed", Expect::Pass,
            "F-1004 remedy (monotonic node token in Lookup and the entry); ALG-I4, ALG-B2.19, ALG-B16.11; AG EF callers finish",
            explore(&CC { m: CM { design: CD::Reviewed, algs: vec![Alg::Ppr], max_id: 5 } }, limits()), show_debug)),
        check("m10-cache-reviewed-pagerank", || judge("m10-cache-reviewed-pagerank", "10", "cache", "reviewed", Expect::Pass,
            "monotonic node token for PageRank too; ALG-I4, ALG-B16.2; AG EF callers finish",
            explore(&CC { m: CM { design: CD::Reviewed, algs: vec![Alg::Pr], max_id: 4 } }, limits()), show_debug)),
        check("m10-cache-control-no-bump-on-create", || judge("m10-cache-control-no-bump-on-create", "10", "cache", "control", Expect::Violation(P_HIT),
            "control: reviewed design whose node create does not raise the node token",
            explore(&CC { m: CM { design: CD::ControlNoBumpOnCreate, algs: vec![Alg::Ppr], max_id: 5 } }, limits()), show_debug)),
        check("m10-cache-control-silent-delete-pagerank", || judge("m10-cache-control-silent-delete-pagerank", "10", "cache", "control", Expect::Violation(P_HIT),
            "control: as built with a delete that raises no token: COUNT:MAX returns to an earlier value (ABA) and a stale PageRank is served",
            explore(&CC { m: CM { design: CD::ControlSilentDelete, algs: vec![Alg::Pr], max_id: 4 } }, limits()), show_debug)),
        check("m10-cache-positive-hit", || {
            let m = Only::new(CC { m: CM { design: CD::Reviewed, algs: vec![Alg::Pr], max_id: 4 } }, &[])
                .witness("never serves a cache hit after a node write", |s: &cache::S| s.nver >= 1 && s.calls.iter().sum::<u8>() >= 3
                    && s.callers.iter().all(|p| *p == cache::Phase::Idle) && s.cache.iter().any(|e| e.2 == s.nver && e.1 == s.ver));
            judge("m10-cache-positive-hit", "10", "cache", "positive", Expect::Violation("never serves a cache hit after a node write"),
                "sharpness: a current entry after a node write is reachable", explore(&m, limits()), show_debug)
        }),
        check("m10-cache-positive-stale-skip", || {
            let m = Only::new(CC { m: CM { design: CD::Reviewed, algs: vec![Alg::Ppr], max_id: 5 } }, &[])
                .witness("never holds an out-of-date PPR entry", |s: &cache::S| s.cache.iter().any(|e| e.3 != cache::fresh(s, Alg::Ppr)));
            judge("m10-cache-positive-stale-skip", "10", "cache", "positive", Expect::Violation("never holds an out-of-date PPR entry"),
                "sharpness: an out-of-date entry exists (and P_HIT shows it is never served)", explore(&m, limits()), show_debug)
        }),
        // ---- nkg
        check("m10-nkg-as-built-fresh", || judge("m10-nkg-as-built-fresh", "10", "nkg", "as-built", Expect::Violation(P_FRESH),
            "F-1005; ALG-B12.7, SYS-I8",
            explore(&NC { m: NM { design: ND::AsBuilt }, keep: vec![P_FRESH], witness: None }, limits()), show_debug)),
        check("m10-nkg-as-built-scope", || judge("m10-nkg-as-built-scope", "10", "nkg", "as-built", Expect::Violation(P_SCOPE),
            "F-1002 (random walk over merged ^NKG); ALG-I3, SYS-I2",
            explore(&NC { m: NM { design: ND::AsBuilt }, keep: vec![P_SCOPE], witness: None }, limits()), show_debug)),
        check("m10-nkg-reviewed", || judge("m10-nkg-reviewed", "10", "nkg", "reviewed", Expect::Pass,
            "F-1005 remedy (PutShadow marks stale) + HD-1001 (a); ALG-B12.7, ALG-I3; AG EF snapshot current",
            explore(&NC { m: NM { design: ND::Reviewed }, keep: vec![P_FRESH, P_SCOPE, "progress"], witness: None }, limits()), show_debug)),
        check("m10-nkg-control-ensure-ignores-stale", || judge("m10-nkg-control-ensure-ignores-stale", "10", "nkg", "control", Expect::Violation(P_FRESH),
            "control: EnsureNKG ignores the stale mark",
            explore(&NC { m: NM { design: ND::ControlEnsureIgnoresStale }, keep: vec![P_FRESH, P_SCOPE], witness: None }, limits()), show_debug)),
        check("m10-nkg-control-walk-merged", || judge("m10-nkg-control-walk-merged", "10", "nkg", "control", Expect::Violation(P_SCOPE),
            "control: the walk reads ^NKG unchecked",
            explore(&NC { m: NM { design: ND::ControlWalkMerged }, keep: vec![P_SCOPE], witness: None }, limits()), show_debug)),
        check("m10-nkg-positive-current-read", || judge("m10-nkg-positive-current-read", "10", "nkg", "positive",
            Expect::Violation("never answers a temporal edge from the snapshot"), "sharpness: after sync a snapshot reader sees the temporal edge",
            explore(&NC { m: NM { design: ND::Reviewed }, keep: vec![], witness: Some(("never answers a temporal edge from the snapshot",
                |s: &nkg::S| matches!(s.last, Some((nkg::R::Centrality, nkg::Answer::Edges(e))) if e & nkg::E1 != 0 && s.built))) }, limits()), show_debug)),
        check("m10-nkg-positive-refusal", || judge("m10-nkg-positive-refusal", "10", "nkg", "positive",
            Expect::Violation("never refuses a snapshot procedure"), "sharpness: ALG-B7 refusal reachable",
            explore(&NC { m: NM { design: ND::AsBuilt }, keep: vec![], witness: Some(("never refuses a snapshot procedure",
                |s: &nkg::S| matches!(s.last, Some((nkg::R::SnapshotProc, nkg::Answer::Refused))))) }, limits()), show_debug)),
        // ---- routes
        check("m10-routes-as-built-walk-empty", || judge("m10-routes-as-built-walk-empty", "10", "routes", "as-built", Expect::Violation(P_SAME),
            "F-1002 (random_walk answers [] without the library); ALG-I1",
            explore(&RC { m: RM { design: RD::AsBuilt, algs: vec![routes::Alg::RandomWalk], max_n: 1, libs: false }, witness: None }, limits()), show_debug)),
        check("m10-routes-as-built-pagerank-cap", || judge("m10-routes-as-built-pagerank-cap", "10", "routes", "as-built", Expect::Violation(P_SAME),
            "F-1003 (owner lists at most 10,000 rows, scaled to 2; native lists every node); ALG-B1.11, HD-1004",
            explore(&RC { m: RM { design: RD::AsBuilt, algs: vec![routes::Alg::PageRank], max_n: 3, libs: false }, witness: None }, limits()), show_debug)),
        check("m10-routes-as-built-pagerank-scope", || judge("m10-routes-as-built-pagerank-scope", "10", "routes", "as-built", Expect::Violation(P_SAME),
            "F-1001 (native route with named-graph edges; violation needs the merged-scope library variant, P-1004 open); ALG-I3, ALG-B14.7",
            explore(&RC { m: RM { design: RD::AsBuilt, algs: vec![routes::Alg::PageRank], max_n: routes::CAP, libs: true }, witness: None }, limits()), show_debug)),
        check("m10-routes-as-built-pagerank-scope-default-only-lib", || judge("m10-routes-as-built-pagerank-scope-default-only-lib", "10", "routes", "as-built", Expect::Pass,
            "F-1001 under P-1004 as premised (a library whose reader reads only graph 0): no violation; the outcome hinges on the open premise",
            explore(&routes_default_only(), limits()), show_debug)),
        check("m10-routes-reviewed", || judge("m10-routes-reviewed", "10", "routes", "reviewed", Expect::Pass,
            "HD-1004 objective, HD-1001 (a), BFS-style named-graph probe; ALG-I1, ALG-I3",
            explore(&RC { m: RM::all(RD::Reviewed), witness: None }, limits()), show_debug)),
        check("m10-routes-control-no-probe", || judge("m10-routes-control-no-probe", "10", "routes", "control", Expect::Violation(P_SAME),
            "control: route without the named-graph probe (caught only with a merged-scope library: P-1004 open)",
            explore(&RC { m: RM::all(RD::ControlRouteNoProbe), witness: None }, limits()), show_debug)),
        check("m10-routes-control-owner-cap", || judge("m10-routes-control-owner-cap", "10", "routes", "control", Expect::Violation(P_SAME),
            "control: reviewed routing with the owner's 10,000-row cap kept",
            explore(&RC { m: RM::all(RD::ControlOwnerCap), witness: None }, limits()), show_debug)),
        check("m10-routes-positive-native", || judge("m10-routes-positive-native", "10", "routes", "positive",
            Expect::Violation("never answers natively"), "sharpness: the native route is taken in the reviewed design",
            explore(&RC { m: RM::all(RD::Reviewed), witness: Some(("never answers natively", |s: &routes::S| matches!(s.last, Some((_, true, _))))) }, limits()), show_debug)),
        // ---- walk
        check("m10-walk-as-built-one-graph", || judge("m10-walk-as-built-one-graph", "10", "walk", "as-built", Expect::Violation(P_ONE_GRAPH),
            "F-1008 (and F-0818 at the translator); ALG-I2",
            explore(&Only::new(WM { design: WD::AsBuilt }, &[P_ONE_GRAPH]), limits()), show_debug)),
        check("m10-walk-as-built-khop", || judge("m10-walk-as-built-khop", "10", "walk", "as-built", Expect::Violation(P_KHOP_SCOPE),
            "F-1009; ALG-I3, ALG-B9.5",
            explore(&Only::new(WM { design: WD::AsBuilt }, &[P_KHOP_SCOPE]), limits()), show_debug)),
        check("m10-walk-reviewed", || judge("m10-walk-reviewed", "10", "walk", "reviewed", Expect::Pass,
            "F-1008/F-1009 remedies; ALG-I2, ALG-I3", explore(&WM { design: WD::Reviewed }, limits()), show_debug)),
        check("m10-walk-control-reset-at-shared", || judge("m10-walk-control-reset-at-shared", "10", "walk", "control", Expect::Violation(P_ONE_GRAPH),
            "control: the fixed graph is forgotten at a shared node", explore(&WM { design: WD::ControlResetAtShared }, limits()), show_debug)),
        check("m10-walk-positive-two-hops", || {
            let m = Only::new(WM { design: WD::Reviewed }, &[]).witness("never walks two hops", |s: &walk::S| s.hops == 2 && s.mode == walk::Mode::Every);
            judge("m10-walk-positive-two-hops", "10", "walk", "positive", Expect::Violation("never walks two hops"),
                "sharpness: a two-hop single-graph walk is reachable (shows the reviewed design is not vacuous)", explore(&m, limits()), show_debug)
        }),
        // ---- degree
        check("m10-degree-as-built", || judge("m10-degree-as-built", "10", "degree", "as-built", Expect::Violation(I_HANDSHAKE),
            "F-1007; ALG-B5.4", explore(&DM { design: DD::AsBuilt }, limits()), show_debug)),
        check("m10-degree-reviewed", || judge("m10-degree-reviewed", "10", "degree", "reviewed", Expect::Pass,
            "F-1007 remedy", explore(&DM { design: DD::Reviewed }, limits()), show_debug)),
        check("m10-degree-control-distinct-out", || judge("m10-degree-control-distinct-out", "10", "degree", "control", Expect::Violation(I_HANDSHAKE),
            "control: out-degree counts distinct targets", explore(&DM { design: DD::ControlDistinctOut }, limits()), show_debug)),
        check("m10-degree-positive-parallel", || {
            let m = Only::new(DM { design: DD::Reviewed }, &[]).witness("never holds three parallel edges", |s: &degree::S| s.ab == 3);
            judge("m10-degree-positive-parallel", "10", "degree", "positive", Expect::Violation("never holds three parallel edges"),
                "sharpness: parallel edges reachable", explore(&m, limits()), show_debug)
        }),
    ]
}
