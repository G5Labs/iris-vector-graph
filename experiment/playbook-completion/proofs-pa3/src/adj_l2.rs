//! Module 04 (adjacency), L2: the algorithmic machine over the stored layout at pin 3eaa79cf, its refinement of
//! `adj_l1` for every step, its invariant, and the broken-implementation controls.
//!
//! State (production names):
//! - `out`     `^KG("out", g, s, p, o)` present (dirty view: uncommitted entries are visible, P-0002)  Adjacency.cls:5-7
//! - `gen`     `^KG("gen", g, s)`, absent reads 0 (Adj.cls:63); `$Increment` survives a rollback (P-0401)
//! - `degc`    `^KG("degc", g, s, $c(1)) = $LB(gen, count)`                                       Adj.cls:9-10
//! - `nolock`  `^IVG.AdjNoLock(g)` defined (a writer went on without the lock, Adjacency.cls:52-70)
//! - `w`       adjacency writer transactions (Put / Remove of one edge; the row hook or a caller), each holding the
//!             shared lock `^IVG.AdjW(g)#"S"` to its end (an unlock in a transaction waits, P-0003) unless `!got`
//! - `r`       Degree calls in flight (Adj.cls:51-91): read gen, look up degc, probe `^IVG.AdjW(g)#"E":0`, count,
//!             check (probe granted, no AdjNoLock, gen unchanged), store, re-check
//! - `e`       Eraser.EraseGraph(g) transactions: TSTART (`ELock`), the rdf_edges DELETE of g's rows (`ERows`,
//!             Eraser.cls:217-219; row locks, P-1201), then RemoveGraph (Adjacency.cls:428-445), commit or rollback.
//!             The row DELETE's own adjacency effect (the functional index) is not modelled: RemoveGraph kills all
//!             of g's adjacency anyway (a namespace without the row hook)
//! - `b`       a rebuild (TraversalBuild.BuildKG: BeginRebuild's lock on the parent `^IVG.AdjW`, RemoveAll, fill)
//! - `rows`    the committed edge rows, i.e. the committed adjacency
//!
//! A rollback restores the before-image of every node the transaction set or killed and nothing else (P-0408).
//!
//! **Design** (the reviewed design, HD-0401 working answer and F-C0401 remedy): every writer steps the generation
//! before it changes `out` (and again after, as built); RemoveGraph steps the generation of every source of the graph
//! before it kills `out`, `degc` and `AdjNoLock`, and never kills `gen`; a rebuild steps every generation before
//! RemoveAll's kills and never kills `gen`; at most one rebuild runs (HD-0402 working answer). Controls put back the
//! pin's order or kill, one decision at a time.
//!
//! **Lane proofs-pa3 (proof debt D-13)**: the breadth crate's premise P-A3 (an eraser of g overlaps no writer of g) is
//! removed. Writers and erasers of one graph interleave under the locks the code takes: the eraser's DELETE waits for
//! every open writer of g (each holds the row lock of the row it inserts or deletes) and a writer waits for the row
//! lock of a row that DELETE removed; nothing stops a writer that inserts a NEW row of g after the DELETE. The
//! reviewed design adds guard R04-5: EraseGraph takes `^IVG.AdjW(g)` exclusively before its DELETE and holds it to
//! its end (waiting for writers that hold it shared), and a writer of g waits for it instead of writing lock-less
//! while an eraser holds it. Control `control_fc1202_erase_unguarded` puts back the pin (RemoveGraph's lock is
//! shared and comes after the DELETE): a writer of g may start after the DELETE and its committed edge loses its
//! adjacency entry (F-C1202).
//!
//! Modelling premises (PROOFS.md): one edge per writer transaction; no two open writers on one edge (row lock); a
//! rebuild overlaps no writer or eraser (the pin's shared locks do not enforce it); a generation step of a whole graph
//! is atomic; the rebuild's fill is one step; readers run outside the writers' transactions; parallel-edge
//! multiplicity is not modelled; two erasers of one graph do not overlap.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::adj_l1::*;

verus! {

// ------------------------------------------------------------------------------------------------ the layout

pub enum WKind { Put, Remove }
pub enum WPh { Locked, Pre, Wrote, Post }
/// A writer transaction on edge x; `got`: the shared writer lock was granted; `had`: the entry existed before.
pub struct WP { pub x: X, pub kind: WKind, pub got: bool, pub ph: WPh, pub had: bool }

pub enum RPh { Gen, Looked, Probed, Counted, Checked, Stored }
pub struct RP { pub k: KS, pub tgen: nat, pub got: bool, pub n: nat, pub ph: RPh }

pub enum EPh { Locked, Deleted, Stepped, OutKilled, Killed }
/// An EraseGraph(g) transaction: `del` the edge rows its DELETE removed, and the before-images a rollback restores.
pub struct EP { pub g: int, pub ph: EPh, pub del: Set<X>, pub pre_out: Set<X>, pub pre_degc: Map<KS, (nat, nat)>,
                pub pre_gen: spec_fn(KS) -> nat, pub pre_nolock: bool }

pub enum BPh { Begun, Stepped, Killed, Filled }
pub struct BP { pub ph: BPh, pub pre_out: Set<X>, pub pre_degc: Map<KS, (nat, nat)>, pub pre_gen: spec_fn(KS) -> nat,
                pub pre_nolock: Set<int> }

pub struct AS2 {
    pub out: Set<X>,
    pub gen: spec_fn(KS) -> nat,
    pub degc: Map<KS, (nat, nat)>,
    pub nolock: Set<int>,
    pub w: Map<nat, WP>,
    pub r: Map<nat, RP>,
    pub e: Map<nat, EP>,
    pub b: Option<BP>,
    pub rows: Set<X>,
}

pub enum AL2 {
    WLock { p: nat, x: X, kind: WKind, got: bool },
    WPre { p: nat },
    WOut { p: nat },
    WPost { p: nat },
    WCommit { p: nat, x: X, add: bool },
    WAbort { p: nat },
    RStart { p: nat, k: KS },
    /// `hit`: the answer and whether its generation is still the source's current one.
    RLookup { p: nat, k: KS, hit: Option<(nat, bool)> },
    RProbe { p: nat },
    RCount { p: nat },
    RCheck { p: nat },
    RStore { p: nat },
    RRecheck { p: nat },
    ELock { q: nat, g: int },
    /// The rdf_edges DELETE of g's rows (Eraser.cls:217-219).
    ERows { q: nat },
    EStep { q: nat },
    EKillOut { q: nat },
    EKill { q: nat },
    ECommit { q: nat, g: int, del: Set<X> },
    EAbort { q: nat },
    BBegin,
    BStep,
    BKill,
    BFill,
    BCommit,
    BAbort,
}

// ------------------------------------------------------------------------------------------------ helpers

pub open spec fn gen_bump(gen: spec_fn(KS) -> nat, k0: KS) -> spec_fn(KS) -> nat {
    |k: KS| if k == k0 { (gen(k) + 1) as nat } else { gen(k) }
}
pub open spec fn gen_step_graph(gen: spec_fn(KS) -> nat, g: int) -> spec_fn(KS) -> nat {
    |k: KS| if k.0 == g { (gen(k) + 1) as nat } else { gen(k) }
}
pub open spec fn gen_step_all(gen: spec_fn(KS) -> nat) -> spec_fn(KS) -> nat { |k: KS| (gen(k) + 1) as nat }
pub open spec fn gen_kill_graph(gen: spec_fn(KS) -> nat, g: int) -> spec_fn(KS) -> nat {
    |k: KS| if k.0 == g { 0nat } else { gen(k) }
}
pub open spec fn gen_zero() -> spec_fn(KS) -> nat { |k: KS| 0nat }
pub open spec fn gen_restore_graph(gen: spec_fn(KS) -> nat, pre: spec_fn(KS) -> nat, g: int) -> spec_fn(KS) -> nat {
    |k: KS| if k.0 == g { pre(k) } else { gen(k) }
}

pub open spec fn out_minus(m: Set<X>, g: int) -> Set<X> { m.filter(|y: X| y.0 != g) }
pub open spec fn out_in(m: Set<X>, g: int) -> Set<X> { m.filter(|y: X| y.0 == g) }
pub open spec fn degc_minus(m: Map<KS, (nat, nat)>, g: int) -> Map<KS, (nat, nat)> {
    Map::new(m.dom().filter(|k: KS| k.0 != g), |k: KS| m[k])
}
pub open spec fn degc_in(m: Map<KS, (nat, nat)>, g: int) -> Map<KS, (nat, nat)> {
    Map::new(m.dom().filter(|k: KS| k.0 == g), |k: KS| m[k])
}

pub open spec fn wrote(w: WP) -> bool { w.ph is Wrote || w.ph is Post }
pub open spec fn e_killed(e: EP) -> bool { e.ph is OutKilled || e.ph is Killed }
pub open spec fn b_killed(b: BP) -> bool { b.ph is Killed || b.ph is Filled }
pub open spec fn probed(r: RP) -> bool { r.ph is Probed || r.ph is Counted }
pub open spec fn counted(r: RP) -> bool { r.ph is Counted || r.ph is Checked }
/// A cache entry carrying its source's current generation.
pub open spec fn cur2(d: Map<KS, (nat, nat)>, gen: spec_fn(KS) -> nat, k: KS) -> bool { d.contains_key(k) && d[k].0 == gen(k) }

/// `^IVG.AdjW(g)` is held (shared) by a writer with the lock, an eraser of g, or a rebuild (parent name).
pub open spec fn held(s: AS2, g: int) -> bool {
    ||| exists|p: nat| #[trigger] s.w.contains_key(p) && s.w[p].got && s.w[p].x.0 == g
    ||| exists|q: nat| #[trigger] s.e.contains_key(q) && s.e[q].g == g
    ||| s.b is Some
}

pub open spec fn no_writer_on(s: AS2, g: int) -> bool { forall|p: nat| #[trigger] s.w.contains_key(p) ==> s.w[p].x.0 != g }
pub open spec fn no_eraser_on(s: AS2, g: int) -> bool { forall|q: nat| #[trigger] s.e.contains_key(q) ==> s.e[q].g != g }
/// No writer of g holds `^IVG.AdjW(g)` (shared).
pub open spec fn no_locked_writer_on(s: AS2, g: int) -> bool {
    forall|p: nat| #[trigger] s.w.contains_key(p) && s.w[p].got ==> s.w[p].x.0 != g
}
/// No open eraser's DELETE holds the row lock of x (P-1201: a writer of that row waits).
pub open spec fn row_free(s: AS2, x: X) -> bool { forall|q: nat| #[trigger] s.e.contains_key(q) ==> !s.e[q].del.contains(x) }
/// The eraser is past RemoveGraph's first step (it has moved the generation, or as built killed out).
pub open spec fn e_past(e: EP) -> bool { !(e.ph is Locked) && !(e.ph is Deleted) }

pub open spec fn fc0401() -> bool { cfg!(feature = "control_fc0401_write_before_gen") }
pub open spec fn hd0401e() -> bool { cfg!(feature = "control_hd0401_erase_kills_gen") }
pub open spec fn hd0401b() -> bool { cfg!(feature = "control_hd0401_rebuild_kills_gen") }
/// Control F-C1202 (as built): EraseGraph takes no lock before its DELETE and RemoveGraph's `^IVG.AdjW(g)#"S"`
/// excludes no writer (Eraser.cls:47-261, Adjacency.cls:428-445): writers of g wait only for row locks.
pub open spec fn fc1202() -> bool { cfg!(feature = "control_fc1202_erase_unguarded") }

// ------------------------------------------------------------------------------------------------ the machine

pub open spec fn init2(s: AS2) -> bool {
    &&& s.out == s.rows
    &&& s.degc == Map::<KS, (nat, nat)>::empty()
    &&& s.nolock == Set::<int>::empty()
    &&& s.w == Map::<nat, WP>::empty()
    &&& s.r == Map::<nat, RP>::empty()
    &&& s.e == Map::<nat, EP>::empty()
    &&& s.b is None
}

pub open spec fn setw(s: AS2, p: nat, w: WP) -> AS2 { AS2 { w: s.w.insert(p, w), ..s } }
pub open spec fn setr(s: AS2, p: nat, r: RP) -> AS2 { AS2 { r: s.r.insert(p, r), ..s } }
pub open spec fn sete(s: AS2, q: nat, e: EP) -> AS2 { AS2 { e: s.e.insert(q, e), ..s } }
pub open spec fn setb(s: AS2, b: BP) -> AS2 { AS2 { b: Some(b), ..s } }

pub open spec fn step2(s: AS2, l: AL2, t: AS2) -> bool {
    match l {
        // ---- writers: Adjacency.Put / Remove in their transaction (Adjacency.cls:76-160)
        AL2::WLock { p, x, kind, got } => {
            &&& !s.w.contains_key(p) && s.b is None
            // reviewed (R04-5): a writer of g waits while an eraser of g holds ^IVG.AdjW(g) exclusively (no lock-less
            // write into a graph being erased); as built: only the row lock of a row an open DELETE removed
            &&& if fc1202() { row_free(s, x) } else { no_eraser_on(s, x.0) }
            &&& forall|p2: nat| #[trigger] s.w.contains_key(p2) ==> s.w[p2].x != x
            &&& t == AS2 { w: s.w.insert(p, WP { x, kind, got, ph: WPh::Locked, had: false }),
                           nolock: if got { s.nolock } else { s.nolock.insert(x.0) }, ..s }
        },
        AL2::WPre { p } => {
            &&& !fc0401() && s.w.contains_key(p) && s.w[p].ph is Locked
            &&& t == AS2 { gen: gen_bump(s.gen, ks(s.w[p].x)), ..setw(s, p, WP { ph: WPh::Pre, ..s.w[p] }) }
        },
        AL2::WOut { p } => {
            &&& s.w.contains_key(p) && (if fc0401() { s.w[p].ph is Locked } else { s.w[p].ph is Pre })
            &&& t == AS2 { out: if s.w[p].kind is Put { s.out.insert(s.w[p].x) } else { s.out.remove(s.w[p].x) },
                           ..setw(s, p, WP { ph: WPh::Wrote, had: s.out.contains(s.w[p].x), ..s.w[p] }) }
        },
        AL2::WPost { p } => {
            &&& s.w.contains_key(p) && s.w[p].ph is Wrote
            &&& t == AS2 { gen: if s.w[p].kind is Put || s.w[p].had { gen_bump(s.gen, ks(s.w[p].x)) } else { s.gen },
                           ..setw(s, p, WP { ph: WPh::Post, ..s.w[p] }) }
        },
        AL2::WCommit { p, x, add } => {
            &&& s.w.contains_key(p) && s.w[p].ph is Post && s.w[p].x == x && add == (s.w[p].kind is Put)
            &&& t == AS2 { rows: if add { s.rows.insert(x) } else { s.rows.remove(x) }, w: s.w.remove(p), ..s }
        },
        AL2::WAbort { p } => {
            &&& s.w.contains_key(p)
            &&& t == AS2 { out: if wrote(s.w[p]) { if s.w[p].had { s.out.insert(s.w[p].x) } else { s.out.remove(s.w[p].x) } } else { s.out },
                           w: s.w.remove(p), ..s }
        },
        // ---- readers: Graph.KG.Adj.Degree (Adj.cls:51-91)
        AL2::RStart { p, k } =>
            !s.r.contains_key(p) && t == setr(s, p, RP { k, tgen: (s.gen)(k), got: false, n: 0, ph: RPh::Gen }),
        AL2::RLookup { p, k, hit } => {
            &&& s.r.contains_key(p) && s.r[p].ph is Gen && s.r[p].k == k
            &&& if s.degc.contains_key(k) && s.degc[k].0 == s.r[p].tgen {
                    hit == Some((s.degc[k].1, s.r[p].tgen == (s.gen)(k))) && t == AS2 { r: s.r.remove(p), ..s }
                } else {
                    hit is None && t == setr(s, p, RP { ph: RPh::Looked, ..s.r[p] })
                }
        },
        AL2::RProbe { p } =>
            s.r.contains_key(p) && s.r[p].ph is Looked
            && t == setr(s, p, RP { ph: RPh::Probed, got: !held(s, s.r[p].k.0), ..s.r[p] }),
        AL2::RCount { p } =>
            s.r.contains_key(p) && s.r[p].ph is Probed
            && t == setr(s, p, RP { ph: RPh::Counted, n: deg(s.out, s.r[p].k), ..s.r[p] }),
        AL2::RCheck { p } => {
            &&& s.r.contains_key(p) && s.r[p].ph is Counted
            &&& if s.r[p].got && !s.nolock.contains(s.r[p].k.0) && (s.gen)(s.r[p].k) == s.r[p].tgen {
                    t == setr(s, p, RP { ph: RPh::Checked, ..s.r[p] })
                } else { t == AS2 { r: s.r.remove(p), ..s } }
        },
        AL2::RStore { p } =>
            s.r.contains_key(p) && s.r[p].ph is Checked
            && t == AS2 { degc: s.degc.insert(s.r[p].k, (s.r[p].tgen, s.r[p].n)), ..setr(s, p, RP { ph: RPh::Stored, ..s.r[p] }) },
        AL2::RRecheck { p } =>
            s.r.contains_key(p) && s.r[p].ph is Stored
            && t == AS2 { degc: if (s.gen)(s.r[p].k) != s.r[p].tgen { s.degc.remove(s.r[p].k) } else { s.degc },
                          r: s.r.remove(p), ..s },
        // ---- erasers: Eraser.EraseGraph's transaction: TSTART, rdf_edges DELETE, Adjacency.RemoveGraph
        //      (Eraser.cls:47-261, Adjacency.cls:428-445)
        AL2::ELock { q, g } =>
            !s.e.contains_key(q) && s.b is None && no_eraser_on(s, g)
            // reviewed (R04-5): the exclusive ^IVG.AdjW(g) waits for every writer of g holding it shared;
            // as built: TSTART takes no lock
            && (fc1202() || no_locked_writer_on(s, g))
            && t == sete(s, q, EP { g, ph: EPh::Locked, del: Set::empty(), pre_out: Set::empty(), pre_degc: Map::empty(),
                                    pre_gen: s.gen, pre_nolock: false }),
        AL2::ERows { q } =>
            // the DELETE waits for every open writer of g (each holds its row's lock, P-1201) and removes g's rows
            s.e.contains_key(q) && s.e[q].ph is Locked && no_writer_on(s, s.e[q].g)
            && t == sete(s, q, EP { ph: EPh::Deleted, del: out_in(s.rows, s.e[q].g), ..s.e[q] }),
        AL2::EStep { q } =>
            !hd0401e() && s.e.contains_key(q) && s.e[q].ph is Deleted
            && t == AS2 { gen: gen_step_graph(s.gen, s.e[q].g), ..sete(s, q, EP { ph: EPh::Stepped, ..s.e[q] }) },
        AL2::EKillOut { q } =>
            hd0401e() && s.e.contains_key(q) && s.e[q].ph is Deleted
            && t == AS2 { out: out_minus(s.out, s.e[q].g),
                          ..sete(s, q, EP { ph: EPh::OutKilled, pre_out: out_in(s.out, s.e[q].g), ..s.e[q] }) },
        AL2::EKill { q } => {
            &&& s.e.contains_key(q)
            &&& if hd0401e() {
                    // as built: Kill ^KG("gen", g), ^KG("degc", g), ^IVG.AdjNoLock(g) after the out kill
                    s.e[q].ph is OutKilled && t == AS2 {
                        gen: gen_kill_graph(s.gen, s.e[q].g), degc: degc_minus(s.degc, s.e[q].g),
                        nolock: s.nolock.remove(s.e[q].g),
                        ..sete(s, q, EP { ph: EPh::Killed, pre_gen: s.gen, pre_degc: degc_in(s.degc, s.e[q].g),
                                          pre_nolock: s.nolock.contains(s.e[q].g), ..s.e[q] }) }
                } else {
                    s.e[q].ph is Stepped && t == AS2 {
                        out: out_minus(s.out, s.e[q].g), degc: degc_minus(s.degc, s.e[q].g),
                        nolock: s.nolock.remove(s.e[q].g),
                        ..sete(s, q, EP { ph: EPh::Killed, pre_out: out_in(s.out, s.e[q].g),
                                          pre_degc: degc_in(s.degc, s.e[q].g), pre_nolock: s.nolock.contains(s.e[q].g),
                                          ..s.e[q] }) }
                }
        },
        AL2::ECommit { q, g, del } =>
            s.e.contains_key(q) && s.e[q].ph is Killed && s.e[q].g == g && s.e[q].del == del
            && t == AS2 { rows: s.rows.difference(del), e: s.e.remove(q), ..s },
        AL2::EAbort { q } => {
            &&& s.e.contains_key(q)
            &&& t == AS2 {
                    out: if e_killed(s.e[q]) { s.out.union(s.e[q].pre_out) } else { s.out },
                    degc: if s.e[q].ph is Killed { s.degc.union_prefer_right(s.e[q].pre_degc) } else { s.degc },
                    nolock: if s.e[q].ph is Killed && s.e[q].pre_nolock { s.nolock.insert(s.e[q].g) } else { s.nolock },
                    gen: if hd0401e() && s.e[q].ph is Killed { gen_restore_graph(s.gen, s.e[q].pre_gen, s.e[q].g) } else { s.gen },
                    e: s.e.remove(q),
                    ..s }
        },
        // ---- rebuild: TraversalBuild.BuildKG (BeginRebuild, RemoveAll, FillEdge, EndRebuild; Adjacency.cls:446-830)
        AL2::BBegin =>
            s.b is None && (forall|p: nat| !#[trigger] s.w.contains_key(p)) && (forall|q: nat| !#[trigger] s.e.contains_key(q))
            && t == setb(s, BP { ph: BPh::Begun, pre_out: Set::empty(), pre_degc: Map::empty(), pre_gen: s.gen,
                                 pre_nolock: Set::empty() }),
        AL2::BStep =>
            !hd0401b() && s.b is Some && s.b->0.ph is Begun
            && t == AS2 { gen: gen_step_all(s.gen), ..setb(s, BP { ph: BPh::Stepped, ..s.b->0 }) },
        AL2::BKill =>
            s.b is Some && (if hd0401b() { s.b->0.ph is Begun } else { s.b->0.ph is Stepped })
            && t == AS2 { out: Set::empty(), degc: Map::empty(), nolock: Set::empty(),
                          gen: if hd0401b() { gen_zero() } else { s.gen },
                          ..setb(s, BP { ph: BPh::Killed, pre_out: s.out, pre_degc: s.degc, pre_gen: s.gen,
                                         pre_nolock: s.nolock, ..s.b->0 }) },
        AL2::BFill =>
            s.b is Some && s.b->0.ph is Killed && t == AS2 { out: s.rows, ..setb(s, BP { ph: BPh::Filled, ..s.b->0 }) },
        AL2::BCommit => s.b is Some && s.b->0.ph is Filled && t == AS2 { b: None, ..s },
        AL2::BAbort => {
            &&& s.b is Some
            &&& t == if b_killed(s.b->0) {
                    AS2 { out: s.b->0.pre_out, degc: s.degc.union_prefer_right(s.b->0.pre_degc),
                          nolock: s.nolock.union(s.b->0.pre_nolock),
                          gen: if hd0401b() { s.b->0.pre_gen } else { s.gen }, b: None, ..s }
                } else { AS2 { b: None, ..s } }
        },
    }
}

// ------------------------------------------------------------------------------------------------ the invariant

pub open spec fn inv_procs(s: AS2) -> bool {
    &&& forall|p1: nat, p2: nat| #![trigger s.w.contains_key(p1), s.w.contains_key(p2)]
            s.w.contains_key(p1) && s.w.contains_key(p2) && p1 != p2 ==> s.w[p1].x != s.w[p2].x
    // P-A3 is no longer a premise: under guard R04-5 a writer of g coexists with an eraser of g only while the eraser
    // has not passed TSTART and the writer is a lock-less one already in flight (`theorem_pa3_from_guard`)
    &&& forall|p: nat, q: nat| #![trigger s.w.contains_key(p), s.e.contains_key(q)]
            s.w.contains_key(p) && s.e.contains_key(q) && s.w[p].x.0 == s.e[q].g ==> s.e[q].ph is Locked && !s.w[p].got
    &&& forall|q1: nat, q2: nat| #![trigger s.e.contains_key(q1), s.e.contains_key(q2)]
            s.e.contains_key(q1) && s.e.contains_key(q2) && q1 != q2 ==> s.e[q1].g != s.e[q2].g
    &&& s.b is Some ==> (forall|p: nat| !#[trigger] s.w.contains_key(p)) && (forall|q: nat| !#[trigger] s.e.contains_key(q))
}

/// An eraser past its DELETE removed exactly the committed rows of its graph, and they stay its graph's rows.
pub open spec fn del_ok(s: AS2, q: nat) -> bool {
    &&& forall|y: X| #[trigger] s.e[q].del.contains(y) ==> y.0 == s.e[q].g
    &&& !(s.e[q].ph is Locked) ==>
            forall|y: X| #![trigger s.rows.contains(y)] #![trigger s.e[q].del.contains(y)]
                y.0 == s.e[q].g ==> (s.rows.contains(y) <==> s.e[q].del.contains(y))
}
pub open spec fn inv_del(s: AS2) -> bool { forall|q: nat| #[trigger] s.e.contains_key(q) ==> del_ok(s, q) }

/// A writer without the lock has marked its graph in ^IVG.AdjNoLock.
pub open spec fn inv_lockless(s: AS2) -> bool {
    forall|p: nat| #[trigger] s.w.contains_key(p) && !s.w[p].got ==> s.nolock.contains(s.w[p].x.0)
}

pub open spec fn inv_wrote(s: AS2) -> bool {
    forall|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) ==>
        s.out.contains(s.w[p].x) == (s.w[p].kind is Put) && s.rows.contains(s.w[p].x) == s.w[p].had
}

pub open spec fn claimed(s: AS2, x: X) -> bool {
    ||| exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == x
    ||| exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == x.0
    ||| s.b is Some && b_killed(s.b->0)
}

/// The visible adjacency differs from the committed rows only where an open transaction wrote.
pub open spec fn inv_claimed(s: AS2) -> bool {
    forall|x: X| #![trigger s.out.contains(x)] #![trigger s.rows.contains(x)]
        s.out.contains(x) != s.rows.contains(x) ==> claimed(s, x)
}

pub open spec fn inv_e_out(s: AS2) -> bool {
    forall|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) ==> {
        &&& forall|x: X| #![trigger s.out.contains(x)] #![trigger s.rows.contains(x)] #![trigger s.e[q].pre_out.contains(x)]
                x.0 == s.e[q].g ==> !s.out.contains(x) && (s.rows.contains(x) == s.e[q].pre_out.contains(x))
        &&& forall|x: X| #[trigger] s.e[q].pre_out.contains(x) ==> x.0 == s.e[q].g
    }
}

pub open spec fn inv_b_out(s: AS2) -> bool {
    s.b is Some && b_killed(s.b->0) ==> {
        &&& s.b->0.pre_out == s.rows
        &&& s.b->0.ph is Killed ==> s.out == Set::<X>::empty()
        &&& s.b->0.ph is Filled ==> s.out == s.rows
    }
}

pub open spec fn inv_gen(s: AS2) -> bool {
    &&& forall|p: nat| #[trigger] s.r.contains_key(p) ==> s.r[p].tgen <= (s.gen)(s.r[p].k)
    &&& forall|k: KS| #[trigger] s.degc.contains_key(k) ==> s.degc[k].0 <= (s.gen)(k)
}

pub open spec fn e_quiet(s: AS2, g: int) -> bool {
    &&& forall|q: nat| #[trigger] s.e.contains_key(q) && s.e[q].g == g ==> !e_past(s.e[q])
    &&& s.b is Some ==> s.b->0.ph is Begun
}

pub open spec fn w_quiet(s: AS2, k: KS) -> bool {
    forall|p: nat| #[trigger] s.w.contains_key(p) && ks(s.w[p].x) == k ==> s.w[p].ph is Locked
}

/// A reader whose probe was granted (or whose check passed) and whose generation is still current has seen no
/// eraser or rebuild past its lock.
pub open spec fn inv_re(s: AS2) -> bool {
    forall|p: nat| #[trigger] s.r.contains_key(p) && (probed(s.r[p]) && s.r[p].got || s.r[p].ph is Checked)
        && s.r[p].tgen == (s.gen)(s.r[p].k) ==> e_quiet(s, s.r[p].k.0)
}

/// ... and, with no AdjNoLock mark (or once its check passed), no writer of its source past its lock, and a count
/// taken since equals the committed degree.
pub open spec fn inv_rw(s: AS2) -> bool {
    forall|p: nat| #[trigger] s.r.contains_key(p)
        && (probed(s.r[p]) && s.r[p].got && !s.nolock.contains(s.r[p].k.0) || s.r[p].ph is Checked)
        && s.r[p].tgen == (s.gen)(s.r[p].k) ==>
        w_quiet(s, s.r[p].k) && (counted(s.r[p]) ==> s.r[p].n == deg(s.rows, s.r[p].k))
}

/// A writer, eraser or rebuild past its lock has moved the generation: no entry of its sources is current.
pub open spec fn inv_cur(s: AS2) -> bool {
    &&& forall|p: nat| #[trigger] s.w.contains_key(p) && !(s.w[p].ph is Locked) ==> !cur2(s.degc, s.gen, ks(s.w[p].x))
    &&& forall|q: nat, k: KS| #![trigger s.e.contains_key(q), s.degc.contains_key(k)]
            s.e.contains_key(q) && e_past(s.e[q]) && k.0 == s.e[q].g ==> !cur2(s.degc, s.gen, k)
    &&& s.b is Some && !(s.b->0.ph is Begun) ==> forall|k: KS| !#[trigger] cur2(s.degc, s.gen, k)
}

/// The entries a rollback would restore are stale.
pub open spec fn inv_pre(s: AS2) -> bool {
    &&& forall|q: nat, k: KS| #![trigger s.e.contains_key(q), s.e[q].pre_degc.contains_key(k)]
            s.e.contains_key(q) && s.e[q].ph is Killed && s.e[q].pre_degc.contains_key(k) ==>
            k.0 == s.e[q].g && s.e[q].pre_degc[k].0 < (s.gen)(k)
    &&& s.b is Some && b_killed(s.b->0) ==>
            forall|k: KS| #[trigger] s.b->0.pre_degc.contains_key(k) ==> s.b->0.pre_degc[k].0 < (s.gen)(k)
}

/// The reviewed design never reaches the as-built eraser phase.
pub open spec fn inv_design(s: AS2) -> bool {
    forall|q: nat| #[trigger] s.e.contains_key(q) && s.e[q].ph is OutKilled ==> hd0401e()
}

pub open spec fn inv04(s: AS2) -> bool {
    &&& inv_design(s)
    &&& inv_procs(s)
    &&& inv_del(s)
    &&& inv_lockless(s)
    &&& inv_wrote(s)
    &&& inv_claimed(s)
    &&& inv_e_out(s)
    &&& inv_b_out(s)
    &&& inv_gen(s)
    &&& inv_re(s)
    &&& inv_rw(s)
    &&& inv_cur(s)
    &&& inv_pre(s)
}

pub struct AdjL2;

impl Contract for AdjL2 {
    type S = AS2;
    type L = AL2;
    open spec fn init(s: AS2) -> bool { init2(s) }
    open spec fn next(s: AS2, l: AL2, t: AS2) -> bool { inv04(s) && step2(s, l, t) }
}

pub struct AdjRaw;

impl Contract for AdjRaw {
    type S = AS2;
    type L = AL2;
    open spec fn init(s: AS2) -> bool { init2(s) }
    open spec fn next(s: AS2, l: AL2, t: AS2) -> bool { step2(s, l, t) }
}

// ------------------------------------------------------------------------------------------------ the abstraction

pub open spec fn abs04(s: AS2) -> AS1 { AS1 { adj: s.rows, ep: s.gen, cache: s.degc } }

pub open spec fn lab04(l: AL2) -> Option<AL1> {
    match l {
        AL2::WLock { p, x, kind, got } => None,
        AL2::WPre { p } => Some(AL1::Advance),
        AL2::WOut { p } => None,
        AL2::WPost { p } => Some(AL1::Advance),
        AL2::WCommit { p, x, add } => Some(AL1::Commit { x, add }),
        AL2::WAbort { p } => None,
        AL2::RStart { p, k } => None,
        AL2::RLookup { p, k, hit } => match hit { Some(h) => if h.1 { Some(AL1::Hit { k, n: h.0 }) } else { None }, None => None },
        AL2::RProbe { p } => None,
        AL2::RCount { p } => None,
        AL2::RCheck { p } => None,
        AL2::RStore { p } => Some(AL1::Cache),
        AL2::RRecheck { p } => Some(AL1::Cache),
        AL2::ELock { q, g } => None,
        AL2::ERows { q } => None,
        AL2::EStep { q } => Some(AL1::Advance),
        AL2::EKillOut { q } => None,
        AL2::EKill { q } => Some(AL1::Cache),
        AL2::ECommit { q, g, del } => Some(AL1::EraseGraph { g, del }),
        AL2::EAbort { q } => Some(AL1::Cache),
        AL2::BBegin => None,
        AL2::BStep => Some(AL1::Advance),
        AL2::BKill => Some(AL1::Cache),
        AL2::BFill => None,
        AL2::BCommit => None,
        AL2::BAbort => Some(AL1::Cache),
    }
}

// ------------------------------------------------------------------------------------------------ lemmas

/// Where nothing is claimed, the visible adjacency of a source is its committed adjacency.
proof fn lemma_count_committed(s: AS2, k: KS)
    requires inv_claimed(s), w_quiet(s, k), e_quiet(s, k.0),
    ensures deg(s.out, k) == deg(s.rows, k),
{
    assert forall|x: X| #[trigger] s.out.filter(of_src(k)).contains(x) == s.rows.filter(of_src(k)).contains(x) by {
        if ks(x) == k && s.out.contains(x) != s.rows.contains(x) {
            assert(claimed(s, x));
            if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == x {
                let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == x;
                assert(s.w[p].ph is Locked);
            }
            if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == x.0 {
                let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == x.0;
                assert(!e_past(s.e[q]));
            }
        }
    }
    assert(s.out.filter(of_src(k)) =~= s.rows.filter(of_src(k)));
}

/// x is not claimed when no writer of x has written, no eraser of its graph has killed and no rebuild has killed.
proof fn lemma_unclaimed(s: AS2, x: X)
    requires
        inv_claimed(s),
        forall|p: nat| #[trigger] s.w.contains_key(p) && s.w[p].x == x ==> !wrote(s.w[p]),
        forall|q: nat| #[trigger] s.e.contains_key(q) && s.e[q].g == x.0 ==> !e_killed(s.e[q]),
        s.b is Some ==> !b_killed(s.b->0),
    ensures s.out.contains(x) == s.rows.contains(x),
{
    if s.out.contains(x) != s.rows.contains(x) {
        assert(claimed(s, x));
        if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == x {
            let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == x;
        }
        if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == x.0 {
            let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == x.0;
        }
    }
}

// ---- guard R04-5 (lane proofs-pa3, proof debt D-13)

/// The reviewed eraser holds `^IVG.AdjW(g)` exclusively from before its row DELETE to its commit or rollback: a writer
/// of g does not start while an eraser of g is open (it waits instead of writing lock-less), and the eraser's lock is
/// granted only when no writer of g holds the shared lock. This is where P-A3 was a premise in the breadth crate; here
/// it is a design element. Control F-C1202 (as built: EraseGraph takes no lock before its DELETE, RemoveGraph's lock
/// is shared, Eraser.cls:47-261, Adjacency.cls:428-445) fails here.
proof fn lemma_erase_guard(s: AS2, l: AL2, t: AS2)
    requires step2(s, l, t),
    ensures
        match l {
            AL2::WLock { p, x, kind, got } => no_eraser_on(s, x.0),
            AL2::ELock { q, g } => no_locked_writer_on(s, g),
            _ => true,
        },
{
    assert(match l {
        AL2::WLock { p, x, kind, got } => no_eraser_on(s, x.0),
        AL2::ELock { q, g } => no_locked_writer_on(s, g),
        _ => true,
    });
}

// ---- writers

proof fn lemma_wlock(s: AS2, p: nat, x: X, kind: WKind, got: bool, t: AS2)
    requires inv04(s), step2(s, AL2::WLock { p, x, kind, got }, t),
    ensures inv04(t), abs04(t) == abs04(s),
{
    lemma_erase_guard(s, AL2::WLock { p, x, kind, got }, t);
    let nw = WP { x, kind, got, ph: WPh::Locked, had: false };
    assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && p2 != p implies t.w[p2] == s.w[p2] by {}
    assert(inv_procs(t)) by {
        assert forall|p1: nat, p2: nat| #![trigger t.w.contains_key(p1), t.w.contains_key(p2)]
            t.w.contains_key(p1) && t.w.contains_key(p2) && p1 != p2 implies t.w[p1].x != t.w[p2].x by {
            if p1 == p { assert(s.w.contains_key(p2)); } else if p2 == p { assert(s.w.contains_key(p1)); }
            else { assert(s.w.contains_key(p1) && s.w.contains_key(p2)); }
        }
        assert forall|p2: nat, q: nat| #![trigger t.w.contains_key(p2), t.e.contains_key(q)]
            t.w.contains_key(p2) && t.e.contains_key(q) && t.w[p2].x.0 == t.e[q].g implies t.e[q].ph is Locked && !t.w[p2].got by {
            if p2 != p { assert(s.w.contains_key(p2)); }
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(claimed(s, y));
            if exists|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y {
                let p2 = choose|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y;
                assert(t.w.contains_key(p2) && wrote(t.w[p2]) && t.w[p2].x == y);
            }
            if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0 {
                let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0;
                assert(t.e.contains_key(q));
            }
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            assert(s.r.contains_key(p2));
            assert(w_quiet(s, s.r[p2].k));
            assert forall|p3: nat| #[trigger] t.w.contains_key(p3) && ks(t.w[p3].x) == t.r[p2].k implies t.w[p3].ph is Locked by {
                if p3 != p { assert(s.w.contains_key(p3)); }
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !(t.w[p2].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p2].x)) by {
            assert(p2 != p);
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_lockless(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !t.w[p2].got implies t.nolock.contains(t.w[p2].x.0) by {
            if p2 != p { assert(s.w.contains_key(p2)); }
        }
    }
    assert(inv_wrote(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && wrote(t.w[p2]) implies
            t.out.contains(t.w[p2].x) == (t.w[p2].kind is Put) && t.rows.contains(t.w[p2].x) == t.w[p2].had by {
            assert(p2 != p);
            assert(s.w.contains_key(p2));
        }
    }
}

proof fn lemma_wpre(s: AS2, p: nat, t: AS2)
    requires inv04(s), step2(s, AL2::WPre { p }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::WPre { p }), abs04(t)),
{
    let wp = s.w[p];
    let k0 = ks(wp.x);
    assert forall|k: KS| #[trigger] (t.gen)(k) >= (s.gen)(k) by {}
    assert forall|p2: nat| #[trigger] t.w.contains_key(p2) implies s.w.contains_key(p2) && (p2 != p ==> t.w[p2] == s.w[p2]) by {}
    assert(inv_procs(t)) by {
        assert forall|p1: nat, p2: nat| #![trigger t.w.contains_key(p1), t.w.contains_key(p2)]
            t.w.contains_key(p1) && t.w.contains_key(p2) && p1 != p2 implies t.w[p1].x != t.w[p2].x by {
            assert(s.w.contains_key(p1) && s.w.contains_key(p2));
        }
        assert forall|p2: nat, q: nat| #![trigger t.w.contains_key(p2), t.e.contains_key(q)]
            t.w.contains_key(p2) && t.e.contains_key(q) && t.w[p2].x.0 == t.e[q].g implies t.e[q].ph is Locked && !t.w[p2].got by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_lockless(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !t.w[p2].got implies t.nolock.contains(t.w[p2].x.0) by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_wrote(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && wrote(t.w[p2]) implies
            t.out.contains(t.w[p2].x) == (t.w[p2].kind is Put) && t.rows.contains(t.w[p2].x) == t.w[p2].had by {
            assert(p2 != p);
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(claimed(s, y));
            if exists|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y {
                let p2 = choose|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y;
                assert(p2 != p);
                assert(t.w.contains_key(p2) && wrote(t.w[p2]) && t.w[p2].x == y);
            }
            if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0 {
                let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0;
                assert(t.e.contains_key(q));
            }
        }
    }
    assert(inv_gen(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) implies t.r[p2].tgen <= (t.gen)(t.r[p2].k) by {}
        assert forall|k: KS| #[trigger] t.degc.contains_key(k) implies t.degc[k].0 <= (t.gen)(k) by {}
    }
    assert(inv_re(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && (probed(t.r[p2]) && t.r[p2].got || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies e_quiet(t, t.r[p2].k.0) by {
            assert(t.r[p2].k != k0);
            assert(s.r[p2].tgen == (s.gen)(s.r[p2].k));
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            assert(t.r[p2].k != k0);
            assert(s.r[p2].tgen == (s.gen)(s.r[p2].k));
            assert(w_quiet(s, s.r[p2].k));
            assert forall|p3: nat| #[trigger] t.w.contains_key(p3) && ks(t.w[p3].x) == t.r[p2].k implies t.w[p3].ph is Locked by {
                assert(s.w.contains_key(p3));
                assert(p3 != p);
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !(t.w[p2].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p2].x)) by {
            if p2 != p { assert(s.w.contains_key(p2)); assert(!cur2(s.degc, s.gen, ks(s.w[p2].x))); }
            else if t.degc.contains_key(k0) { assert(s.degc[k0].0 <= (s.gen)(k0)); }
        }
        assert forall|q: nat, k: KS| #![trigger t.e.contains_key(q), t.degc.contains_key(k)]
            t.e.contains_key(q) && e_past(t.e[q]) && k.0 == t.e[q].g implies !cur2(t.degc, t.gen, k) by {
            assert(s.w.contains_key(p) && s.e.contains_key(q));
            assert(k != k0);
        }
    }
    assert(inv_pre(t)) by {
        assert forall|q: nat, k: KS| #![trigger t.e.contains_key(q), t.e[q].pre_degc.contains_key(k)]
            t.e.contains_key(q) && t.e[q].ph is Killed && t.e[q].pre_degc.contains_key(k) implies
            k.0 == t.e[q].g && t.e[q].pre_degc[k].0 < (t.gen)(k) by {}
    }
}

proof fn lemma_wout(s: AS2, p: nat, t: AS2)
    requires inv04(s), step2(s, AL2::WOut { p }, t),
    ensures inv04(t), abs04(t) == abs04(s),
{
    let wp = s.w[p];
    let x = wp.x;
    let k0 = ks(x);
    assert forall|p2: nat| #[trigger] t.w.contains_key(p2) implies s.w.contains_key(p2) && (p2 != p ==> t.w[p2] == s.w[p2]) by {}
    // the entry was unclaimed: visible == committed before the write
    assert(s.out.contains(x) == s.rows.contains(x)) by {
        assert forall|p2: nat| #[trigger] s.w.contains_key(p2) && s.w[p2].x == x implies !wrote(s.w[p2]) by {
            if p2 != p { assert(s.w.contains_key(p) && s.w.contains_key(p2)); }
        }
        assert forall|q: nat| #[trigger] s.e.contains_key(q) && s.e[q].g == x.0 implies !e_killed(s.e[q]) by {
            assert(s.w.contains_key(p) && s.e.contains_key(q));
        }
        lemma_unclaimed(s, x);
    }
    assert(inv_procs(t)) by {
        assert forall|p1: nat, p2: nat| #![trigger t.w.contains_key(p1), t.w.contains_key(p2)]
            t.w.contains_key(p1) && t.w.contains_key(p2) && p1 != p2 implies t.w[p1].x != t.w[p2].x by {
            assert(s.w.contains_key(p1) && s.w.contains_key(p2));
        }
        assert forall|p2: nat, q: nat| #![trigger t.w.contains_key(p2), t.e.contains_key(q)]
            t.w.contains_key(p2) && t.e.contains_key(q) && t.w[p2].x.0 == t.e[q].g implies t.e[q].ph is Locked && !t.w[p2].got by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_lockless(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !t.w[p2].got implies t.nolock.contains(t.w[p2].x.0) by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_wrote(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && wrote(t.w[p2]) implies
            t.out.contains(t.w[p2].x) == (t.w[p2].kind is Put) && t.rows.contains(t.w[p2].x) == t.w[p2].had by {
            if p2 != p {
                assert(s.w.contains_key(p2));
                assert(s.w.contains_key(p) && s.w.contains_key(p2));
                assert(s.w[p2].x != x);
            }
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            if y == x {
                assert(t.w.contains_key(p) && wrote(t.w[p]) && t.w[p].x == y);
            } else {
                assert(claimed(s, y));
                if exists|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y {
                    let p2 = choose|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y;
                    assert(p2 != p);
                    assert(t.w.contains_key(p2) && wrote(t.w[p2]) && t.w[p2].x == y);
                }
                if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0 {
                    let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0;
                    assert(t.e.contains_key(q));
                }
            }
        }
    }
    assert(inv_e_out(t)) by {
        assert forall|q: nat| #[trigger] t.e.contains_key(q) && e_killed(t.e[q]) implies {
            &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q].pre_out.contains(y)]
                    y.0 == t.e[q].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q].pre_out.contains(y))
            &&& forall|y: X| #[trigger] t.e[q].pre_out.contains(y) ==> y.0 == t.e[q].g
        } by {
            assert(s.w.contains_key(p) && s.e.contains_key(q));
            assert(x.0 != s.e[q].g);
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            assert(w_quiet(s, s.r[p2].k));
            assert forall|p3: nat| #[trigger] t.w.contains_key(p3) && ks(t.w[p3].x) == t.r[p2].k implies t.w[p3].ph is Locked by {
                assert(s.w.contains_key(p3));
                // the writer p was past its lock: no current reader of its source passed this way (control F-C0401 fails here)
                if p3 == p { assert(s.w[p].ph is Locked); }
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !(t.w[p2].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p2].x)) by {
            assert(s.w.contains_key(p2));
            // the writer had stepped the generation before its write (control F-C0401 fails here)
            assert(!(s.w[p2].ph is Locked));
        }
    }
}

proof fn lemma_wpost(s: AS2, p: nat, t: AS2)
    requires inv04(s), step2(s, AL2::WPost { p }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::WPost { p }), abs04(t)),
{
    let wp = s.w[p];
    let k0 = ks(wp.x);
    assert forall|k: KS| #[trigger] (t.gen)(k) >= (s.gen)(k) by {}
    assert forall|k: KS| k != k0 implies #[trigger] (t.gen)(k) == (s.gen)(k) by {}
    assert forall|p2: nat| #[trigger] t.w.contains_key(p2) implies s.w.contains_key(p2) && (p2 != p ==> t.w[p2] == s.w[p2]) by {}
    assert(inv_procs(t)) by {
        assert forall|p1: nat, p2: nat| #![trigger t.w.contains_key(p1), t.w.contains_key(p2)]
            t.w.contains_key(p1) && t.w.contains_key(p2) && p1 != p2 implies t.w[p1].x != t.w[p2].x by {
            assert(s.w.contains_key(p1) && s.w.contains_key(p2));
        }
        assert forall|p2: nat, q: nat| #![trigger t.w.contains_key(p2), t.e.contains_key(q)]
            t.w.contains_key(p2) && t.e.contains_key(q) && t.w[p2].x.0 == t.e[q].g implies t.e[q].ph is Locked && !t.w[p2].got by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_lockless(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !t.w[p2].got implies t.nolock.contains(t.w[p2].x.0) by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_wrote(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && wrote(t.w[p2]) implies
            t.out.contains(t.w[p2].x) == (t.w[p2].kind is Put) && t.rows.contains(t.w[p2].x) == t.w[p2].had by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(claimed(s, y));
            if exists|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y {
                let p2 = choose|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y;
                assert(t.w.contains_key(p2) && wrote(t.w[p2]) && t.w[p2].x == y);
            }
            if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0 {
                let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0;
                assert(t.e.contains_key(q));
            }
        }
    }
    assert(inv_gen(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) implies t.r[p2].tgen <= (t.gen)(t.r[p2].k) by {}
        assert forall|k: KS| #[trigger] t.degc.contains_key(k) implies t.degc[k].0 <= (t.gen)(k) by {}
    }
    assert(inv_re(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && (probed(t.r[p2]) && t.r[p2].got || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies e_quiet(t, t.r[p2].k.0) by {
            if t.r[p2].k == k0 && (t.gen)(k0) != (s.gen)(k0) {} else { assert(s.r[p2].tgen == (s.gen)(s.r[p2].k)); }
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            if t.r[p2].k == k0 && (t.gen)(k0) != (s.gen)(k0) {} else {
                assert(s.r[p2].tgen == (s.gen)(s.r[p2].k));
                assert(w_quiet(s, s.r[p2].k));
                assert forall|p3: nat| #[trigger] t.w.contains_key(p3) && ks(t.w[p3].x) == t.r[p2].k implies t.w[p3].ph is Locked by {
                    assert(s.w.contains_key(p3));
                }
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !(t.w[p2].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p2].x)) by {
            assert(s.w.contains_key(p2));
            assert(!cur2(s.degc, s.gen, ks(s.w[p2].x)));
            if ks(t.w[p2].x) == k0 && t.degc.contains_key(k0) { assert(s.degc[k0].0 <= (s.gen)(k0)); }
        }
        assert forall|q: nat, k: KS| #![trigger t.e.contains_key(q), t.degc.contains_key(k)]
            t.e.contains_key(q) && e_past(t.e[q]) && k.0 == t.e[q].g implies !cur2(t.degc, t.gen, k) by {
            assert(s.w.contains_key(p) && s.e.contains_key(q));
            assert(k != k0);
        }
    }
    assert(inv_pre(t)) by {
        assert forall|q: nat, k: KS| #![trigger t.e.contains_key(q), t.e[q].pre_degc.contains_key(k)]
            t.e.contains_key(q) && t.e[q].ph is Killed && t.e[q].pre_degc.contains_key(k) implies
            k.0 == t.e[q].g && t.e[q].pre_degc[k].0 < (t.gen)(k) by {}
    }
}

proof fn lemma_wcommit(s: AS2, p: nat, x: X, add: bool, t: AS2)
    requires inv04(s), step2(s, AL2::WCommit { p, x, add }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::WCommit { p, x, add }), abs04(t)),
{
    let k0 = ks(x);
    // no eraser of x's graph is past its DELETE while the writer is open: the rows the DELETEs removed stay as they were
    assert(inv_del(t)) by {
        assert forall|q: nat| #[trigger] t.e.contains_key(q) implies del_ok(t, q) by {
            assert(s.e.contains_key(q)); assert(del_ok(s, q));
            if !(s.e[q].ph is Locked) { assert(s.w.contains_key(p) && s.e.contains_key(q)); assert(x.0 != s.e[q].g); }
        }
    }
    assert(!cur2(s.degc, s.gen, k0));
    assert forall|p2: nat| #[trigger] t.w.contains_key(p2) implies s.w.contains_key(p2) && p2 != p && t.w[p2] == s.w[p2] by {}
    assert(inv_procs(t)) by {
        assert forall|p1: nat, p2: nat| #![trigger t.w.contains_key(p1), t.w.contains_key(p2)]
            t.w.contains_key(p1) && t.w.contains_key(p2) && p1 != p2 implies t.w[p1].x != t.w[p2].x by {
            assert(s.w.contains_key(p1) && s.w.contains_key(p2));
        }
        assert forall|p2: nat, q: nat| #![trigger t.w.contains_key(p2), t.e.contains_key(q)]
            t.w.contains_key(p2) && t.e.contains_key(q) && t.w[p2].x.0 == t.e[q].g implies t.e[q].ph is Locked && !t.w[p2].got by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_lockless(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !t.w[p2].got implies t.nolock.contains(t.w[p2].x.0) by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_wrote(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && wrote(t.w[p2]) implies
            t.out.contains(t.w[p2].x) == (t.w[p2].kind is Put) && t.rows.contains(t.w[p2].x) == t.w[p2].had by {
            assert(s.w.contains_key(p2));
            assert(s.w.contains_key(p) && s.w.contains_key(p2));
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(y != x);
            assert(claimed(s, y));
            if exists|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y {
                let p2 = choose|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y;
                assert(t.w.contains_key(p2) && wrote(t.w[p2]) && t.w[p2].x == y);
            }
            if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0 {
                let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0;
                assert(t.e.contains_key(q));
            }
        }
    }
    assert(inv_e_out(t)) by {
        assert forall|q: nat| #[trigger] t.e.contains_key(q) && e_killed(t.e[q]) implies {
            &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q].pre_out.contains(y)]
                    y.0 == t.e[q].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q].pre_out.contains(y))
            &&& forall|y: X| #[trigger] t.e[q].pre_out.contains(y) ==> y.0 == t.e[q].g
        } by {
            assert(s.w.contains_key(p) && s.e.contains_key(q));
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            assert(w_quiet(s, s.r[p2].k));
            assert(t.r[p2].k != k0) by { if t.r[p2].k == k0 { assert(s.w[p].ph is Locked); } }
            lemma_deg_other(s.rows, x, t.r[p2].k);
            assert forall|p3: nat| #[trigger] t.w.contains_key(p3) && ks(t.w[p3].x) == t.r[p2].k implies t.w[p3].ph is Locked by {
                assert(s.w.contains_key(p3));
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !(t.w[p2].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p2].x)) by {
            assert(s.w.contains_key(p2));
        }
    }
}

proof fn lemma_wabort(s: AS2, p: nat, t: AS2)
    requires inv04(s), step2(s, AL2::WAbort { p }, t),
    ensures inv04(t), abs04(t) == abs04(s),
{
    let wp = s.w[p];
    let x = wp.x;
    assert forall|p2: nat| #[trigger] t.w.contains_key(p2) implies s.w.contains_key(p2) && p2 != p && t.w[p2] == s.w[p2] by {}
    assert(t.out.contains(x) == t.rows.contains(x)) by {
        if !wrote(wp) {
            assert forall|p2: nat| #[trigger] s.w.contains_key(p2) && s.w[p2].x == x implies !wrote(s.w[p2]) by {
                if p2 != p { assert(s.w.contains_key(p) && s.w.contains_key(p2)); }
            }
            assert forall|q: nat| #[trigger] s.e.contains_key(q) && s.e[q].g == x.0 implies !e_killed(s.e[q]) by {
                assert(s.w.contains_key(p) && s.e.contains_key(q));
            }
            lemma_unclaimed(s, x);
        }
    }
    assert(inv_procs(t)) by {
        assert forall|p1: nat, p2: nat| #![trigger t.w.contains_key(p1), t.w.contains_key(p2)]
            t.w.contains_key(p1) && t.w.contains_key(p2) && p1 != p2 implies t.w[p1].x != t.w[p2].x by {
            assert(s.w.contains_key(p1) && s.w.contains_key(p2));
        }
        assert forall|p2: nat, q: nat| #![trigger t.w.contains_key(p2), t.e.contains_key(q)]
            t.w.contains_key(p2) && t.e.contains_key(q) && t.w[p2].x.0 == t.e[q].g implies t.e[q].ph is Locked && !t.w[p2].got by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_lockless(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !t.w[p2].got implies t.nolock.contains(t.w[p2].x.0) by {
            assert(s.w.contains_key(p2));
        }
    }
    assert(inv_wrote(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && wrote(t.w[p2]) implies
            t.out.contains(t.w[p2].x) == (t.w[p2].kind is Put) && t.rows.contains(t.w[p2].x) == t.w[p2].had by {
            assert(s.w.contains_key(p2));
            assert(s.w.contains_key(p) && s.w.contains_key(p2));
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(y != x);
            assert(claimed(s, y));
            if exists|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y {
                let p2 = choose|p2: nat| #[trigger] s.w.contains_key(p2) && wrote(s.w[p2]) && s.w[p2].x == y;
                assert(t.w.contains_key(p2) && wrote(t.w[p2]) && t.w[p2].x == y);
            }
            if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0 {
                let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0;
                assert(t.e.contains_key(q));
            }
        }
    }
    assert(inv_e_out(t)) by {
        assert forall|q: nat| #[trigger] t.e.contains_key(q) && e_killed(t.e[q]) implies {
            &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q].pre_out.contains(y)]
                    y.0 == t.e[q].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q].pre_out.contains(y))
            &&& forall|y: X| #[trigger] t.e[q].pre_out.contains(y) ==> y.0 == t.e[q].g
        } by {
            assert(s.w.contains_key(p) && s.e.contains_key(q));
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            assert(w_quiet(s, s.r[p2].k));
            assert forall|p3: nat| #[trigger] t.w.contains_key(p3) && ks(t.w[p3].x) == t.r[p2].k implies t.w[p3].ph is Locked by {
                assert(s.w.contains_key(p3));
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !(t.w[p2].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p2].x)) by {
            assert(s.w.contains_key(p2));
        }
    }
}

// ---- readers

proof fn lemma_reader_frame(s: AS2, p: nat, t: AS2)
    requires
        inv04(s),
        t == (AS2 { r: t.r, degc: t.degc, ..s }),
        forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p ==> s.r.contains_key(p2) && t.r[p2] == s.r[p2],
    ensures
        inv_procs(t), inv_lockless(t), inv_wrote(t), inv_claimed(t), inv_e_out(t), inv_b_out(t),
{
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(claimed(s, y));
        }
    }
}

proof fn lemma_rstart(s: AS2, p: nat, k: KS, t: AS2)
    requires inv04(s), step2(s, AL2::RStart { p, k }, t),
    ensures inv04(t), abs04(t) == abs04(s),
{
    lemma_reader_frame(s, p, t);
    assert(inv_gen(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) implies t.r[p2].tgen <= (t.gen)(t.r[p2].k) by {
            if p2 != p { assert(s.r.contains_key(p2)); }
        }
    }
    assert(inv_re(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && (probed(t.r[p2]) && t.r[p2].got || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies e_quiet(t, t.r[p2].k.0) by {
            assert(p2 != p);
            assert(s.r.contains_key(p2));
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            assert(p2 != p);
            assert(s.r.contains_key(p2));
            assert(w_quiet(s, s.r[p2].k));
        }
    }
}

/// Reader steps that change only the reader's own record (and possibly remove it): the reader-indexed invariants
/// hold for every other reader as before.
proof fn lemma_reader_others(s: AS2, p: nat, t: AS2)
    requires
        inv04(s), t == (AS2 { r: t.r, ..s }),
        forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p ==> s.r.contains_key(p2) && t.r[p2] == s.r[p2],
    ensures
        forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p ==> t.r[p2].tgen <= (t.gen)(t.r[p2].k),
        forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p && (probed(t.r[p2]) && t.r[p2].got || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) ==> e_quiet(t, t.r[p2].k.0),
        forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) ==>
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)),
{
    assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p && (probed(t.r[p2]) && t.r[p2].got || t.r[p2].ph is Checked)
        && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies e_quiet(t, t.r[p2].k.0) by {
        assert(s.r.contains_key(p2));
    }
    assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p
        && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
        && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
        w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
        assert(s.r.contains_key(p2));
        assert(w_quiet(s, s.r[p2].k));
    }
}

proof fn lemma_reader_step(s: AS2, l: AL2, t: AS2)
    requires
        inv04(s), step2(s, l, t),
        l is RLookup || l is RProbe || l is RCount || l is RCheck,
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(l), abs04(t)),
{
    let p = match l { AL2::RLookup { p, .. } => p, AL2::RProbe { p } => p, AL2::RCount { p } => p, AL2::RCheck { p } => p, _ => 0 };
    let rp = s.r[p];
    let k = rp.k;
    assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p implies s.r.contains_key(p2) && t.r[p2] == s.r[p2] by {}
    lemma_reader_frame(s, p, t);
    lemma_reader_others(s, p, t);
    assert(inv_gen(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) implies t.r[p2].tgen <= (t.gen)(t.r[p2].k) by {
            assert(s.r.contains_key(p2));
        }
    }
    if t.r.contains_key(p) {
        let r2 = t.r[p];
        assert(r2.k == k && r2.tgen == rp.tgen);
        assert(inv_re(t)) by {
            assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && (probed(t.r[p2]) && t.r[p2].got || t.r[p2].ph is Checked)
                && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies e_quiet(t, t.r[p2].k.0) by {
                if p2 == p {
                    if l is RProbe {
                        // the probe was granted: no eraser of g and no rebuild holds the lock
                        assert forall|q: nat| #[trigger] t.e.contains_key(q) && t.e[q].g == k.0 implies !e_past(t.e[q]) by {
                            assert(held(s, k.0));
                        }
                        if t.b is Some { assert(held(s, k.0)); }
                    }
                }
            }
        }
        assert(inv_rw(t)) by {
            assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
                && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
                && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
                w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
                if p2 == p {
                    if l is RProbe {
                        // granted and no AdjNoLock: no writer of g at all
                        assert forall|p3: nat| #[trigger] t.w.contains_key(p3) && ks(t.w[p3].x) == k implies t.w[p3].ph is Locked by {
                            if t.w[p3].got { assert(held(s, k.0)); } else { assert(s.nolock.contains(s.w[p3].x.0)); }
                        }
                    } else if l is RCount {
                        assert(w_quiet(s, k));
                        assert(e_quiet(s, k.0));
                        lemma_count_committed(s, k);
                    } else {
                        assert(w_quiet(s, k));
                    }
                }
            }
        }
    } else {
        assert(inv_re(t));
        assert(inv_rw(t));
    }
    assert(inv_cur(t));
    assert(inv_pre(t));
}

proof fn lemma_rstore(s: AS2, p: nat, t: AS2)
    requires inv04(s), step2(s, AL2::RStore { p }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::RStore { p }), abs04(t)),
{
    let rp = s.r[p];
    let k = rp.k;
    assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p implies s.r.contains_key(p2) && t.r[p2] == s.r[p2] by {}
    lemma_reader_frame(s, p, t);
    assert(inv_gen(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) implies t.r[p2].tgen <= (t.gen)(t.r[p2].k) by {
            assert(s.r.contains_key(p2));
        }
        assert forall|k2: KS| #[trigger] t.degc.contains_key(k2) implies t.degc[k2].0 <= (t.gen)(k2) by {}
    }
    let cur_store = rp.tgen == (s.gen)(k);
    if cur_store {
        assert(w_quiet(s, k) && rp.n == deg(s.rows, k));
        assert(e_quiet(s, k.0));
    }
    assert(inv_re(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && (probed(t.r[p2]) && t.r[p2].got || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies e_quiet(t, t.r[p2].k.0) by {
            assert(p2 != p);
            assert(s.r.contains_key(p2));
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            assert(p2 != p);
            assert(s.r.contains_key(p2));
            assert(w_quiet(s, s.r[p2].k));
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !(t.w[p2].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p2].x)) by {
            assert(!cur2(s.degc, s.gen, ks(s.w[p2].x)));
            if ks(t.w[p2].x) == k && cur_store { assert(s.w[p2].ph is Locked); }
        }
        assert forall|q: nat, k2: KS| #![trigger t.e.contains_key(q), t.degc.contains_key(k2)]
            t.e.contains_key(q) && e_past(t.e[q]) && k2.0 == t.e[q].g implies !cur2(t.degc, t.gen, k2) by {
            if k2 == k && cur_store { assert(!e_past(s.e[q])); } else if k2 != k { assert(!cur2(s.degc, s.gen, k2)); }
        }
        if t.b is Some && !(t.b->0.ph is Begun) {
            assert forall|k2: KS| !#[trigger] cur2(t.degc, t.gen, k2) by {
                if k2 == k && cur_store { assert(s.b->0.ph is Begun); } else if k2 != k { assert(!cur2(s.degc, s.gen, k2)); }
            }
        }
    }
    assert(inv_pre(t));
    assert(abs04(t) == AS1 { cache: abs04(t).cache, ..abs04(s) });
    assert forall|k2: KS| #[trigger] t.degc.contains_key(k2) && !(s.degc.contains_key(k2) && s.degc[k2] == t.degc[k2])
        implies entry_ok(s.rows, s.gen, k2, t.degc[k2]) by {}
}

proof fn lemma_rrecheck(s: AS2, p: nat, t: AS2)
    requires inv04(s), step2(s, AL2::RRecheck { p }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::RRecheck { p }), abs04(t)),
{
    assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && p2 != p implies s.r.contains_key(p2) && t.r[p2] == s.r[p2] by {}
    lemma_reader_frame(s, p, t);
    assert(inv_gen(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) implies t.r[p2].tgen <= (t.gen)(t.r[p2].k) by {
            assert(s.r.contains_key(p2));
        }
    }
    assert(inv_re(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2) && (probed(t.r[p2]) && t.r[p2].got || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies e_quiet(t, t.r[p2].k.0) by {
            assert(s.r.contains_key(p2));
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p2: nat| #[trigger] t.r.contains_key(p2)
            && (probed(t.r[p2]) && t.r[p2].got && !t.nolock.contains(t.r[p2].k.0) || t.r[p2].ph is Checked)
            && t.r[p2].tgen == (t.gen)(t.r[p2].k) implies
            w_quiet(t, t.r[p2].k) && (counted(t.r[p2]) ==> t.r[p2].n == deg(t.rows, t.r[p2].k)) by {
            assert(s.r.contains_key(p2));
            assert(w_quiet(s, s.r[p2].k));
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p2: nat| #[trigger] t.w.contains_key(p2) && !(t.w[p2].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p2].x)) by {
            assert(!cur2(s.degc, s.gen, ks(s.w[p2].x)));
        }
        assert forall|q: nat, k2: KS| #![trigger t.e.contains_key(q), t.degc.contains_key(k2)]
            t.e.contains_key(q) && e_past(t.e[q]) && k2.0 == t.e[q].g implies !cur2(t.degc, t.gen, k2) by {
            assert(!cur2(s.degc, s.gen, k2));
        }
        if t.b is Some && !(t.b->0.ph is Begun) {
            assert forall|k2: KS| !#[trigger] cur2(t.degc, t.gen, k2) by { assert(!cur2(s.degc, s.gen, k2)); }
        }
    }
    assert(abs04(t) == AS1 { cache: abs04(t).cache, ..abs04(s) });
}

// ---- erasers

proof fn lemma_elock(s: AS2, q: nat, g: int, t: AS2)
    requires inv04(s), step2(s, AL2::ELock { q, g }, t),
    ensures inv04(t), abs04(t) == abs04(s),
{
    lemma_erase_guard(s, AL2::ELock { q, g }, t);
    assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && q2 != q implies s.e.contains_key(q2) && t.e[q2] == s.e[q2] by {}
    assert(inv_del(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies del_ok(t, q2) by {
            if q2 != q { assert(s.e.contains_key(q2)); }
        }
    }
    assert(inv_procs(t)) by {
        assert forall|p: nat, q2: nat| #![trigger t.w.contains_key(p), t.e.contains_key(q2)]
            t.w.contains_key(p) && t.e.contains_key(q2) && t.w[p].x.0 == t.e[q2].g implies t.e[q2].ph is Locked && !t.w[p].got by {
            if q2 != q { assert(s.w.contains_key(p) && s.e.contains_key(q2)); } else { assert(s.w.contains_key(p)); }
        }
        assert forall|q1: nat, q2: nat| #![trigger t.e.contains_key(q1), t.e.contains_key(q2)]
            t.e.contains_key(q1) && t.e.contains_key(q2) && q1 != q2 implies t.e[q1].g != t.e[q2].g by {
            if q1 != q && q2 != q { assert(s.e.contains_key(q1) && s.e.contains_key(q2)); }
            else if q1 == q { assert(s.e.contains_key(q2)); } else { assert(s.e.contains_key(q1)); }
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(claimed(s, y));
            if exists|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0 {
                let q2 = choose|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0;
                assert(t.e.contains_key(q2) && t.e[q2] == s.e[q2]);
            }
            if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y {
                let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y;
                assert(t.w.contains_key(p));
            }
        }
    }
    assert(inv_e_out(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && e_killed(t.e[q2]) implies {
            &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                    y.0 == t.e[q2].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y))
            &&& forall|y: X| #[trigger] t.e[q2].pre_out.contains(y) ==> y.0 == t.e[q2].g
        } by {
            assert(q2 != q);
            assert(s.e.contains_key(q2));
        }
    }
    assert(inv_re(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
            assert(e_quiet(s, s.r[p].k.0));
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && t.e[q2].g == t.r[p].k.0 implies !e_past(t.e[q2]) by {
                if q2 != q { assert(s.e.contains_key(q2)); }
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.degc.contains_key(k)]
            t.e.contains_key(q2) && e_past(t.e[q2]) && k.0 == t.e[q2].g implies !cur2(t.degc, t.gen, k) by {
            assert(q2 != q);
            assert(s.e.contains_key(q2));
        }
    }
    assert(inv_pre(t)) by {
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.e[q2].pre_degc.contains_key(k)]
            t.e.contains_key(q2) && t.e[q2].ph is Killed && t.e[q2].pre_degc.contains_key(k) implies
            k.0 == t.e[q2].g && t.e[q2].pre_degc[k].0 < (t.gen)(k) by {
            assert(q2 != q);
            assert(s.e.contains_key(q2));
        }
    }
}

/// The rdf_edges DELETE of g's rows: it waits for every open writer of g and records the rows it removes; nothing
/// visible changes until the commit (the committed rows, out, gen and degc stay as they were).
proof fn lemma_erows(s: AS2, q: nat, t: AS2)
    requires inv04(s), step2(s, AL2::ERows { q }, t),
    ensures inv04(t), abs04(t) == abs04(s),
{
    let g = s.e[q].g;
    assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies s.e.contains_key(q2) && (q2 != q ==> t.e[q2] == s.e[q2]) by {}
    assert(inv_procs(t)) by {
        assert forall|p: nat, q2: nat| #![trigger t.w.contains_key(p), t.e.contains_key(q2)]
            t.w.contains_key(p) && t.e.contains_key(q2) && t.w[p].x.0 == t.e[q2].g implies t.e[q2].ph is Locked && !t.w[p].got by {
            if q2 != q { assert(s.w.contains_key(p) && s.e.contains_key(q2)); } else { assert(s.w.contains_key(p)); }
        }
        assert forall|q1: nat, q2: nat| #![trigger t.e.contains_key(q1), t.e.contains_key(q2)]
            t.e.contains_key(q1) && t.e.contains_key(q2) && q1 != q2 implies t.e[q1].g != t.e[q2].g by {
            assert(s.e.contains_key(q1) && s.e.contains_key(q2));
        }
    }
    assert(inv_del(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies del_ok(t, q2) by {
            if q2 != q { assert(s.e.contains_key(q2)); assert(del_ok(s, q2)); }
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(claimed(s, y));
            if exists|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0 {
                let q2 = choose|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0;
                assert(q2 != q);
                assert(t.e.contains_key(q2) && t.e[q2] == s.e[q2]);
            }
            if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y {
                let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y;
                assert(t.w.contains_key(p));
            }
        }
    }
    assert(inv_e_out(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && e_killed(t.e[q2]) implies {
            &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                    y.0 == t.e[q2].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y))
            &&& forall|y: X| #[trigger] t.e[q2].pre_out.contains(y) ==> y.0 == t.e[q2].g
        } by {
            assert(q2 != q);
            assert(s.e.contains_key(q2));
        }
    }
    assert(inv_re(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
            assert(e_quiet(s, s.r[p].k.0));
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && t.e[q2].g == t.r[p].k.0 implies !e_past(t.e[q2]) by {
                assert(s.e.contains_key(q2));
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.degc.contains_key(k)]
            t.e.contains_key(q2) && e_past(t.e[q2]) && k.0 == t.e[q2].g implies !cur2(t.degc, t.gen, k) by {
            assert(q2 != q);
            assert(s.e.contains_key(q2));
        }
    }
    assert(inv_pre(t)) by {
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.e[q2].pre_degc.contains_key(k)]
            t.e.contains_key(q2) && t.e[q2].ph is Killed && t.e[q2].pre_degc.contains_key(k) implies
            k.0 == t.e[q2].g && t.e[q2].pre_degc[k].0 < (t.gen)(k) by {
            assert(q2 != q);
            assert(s.e.contains_key(q2));
        }
    }
}

proof fn lemma_estep(s: AS2, q: nat, t: AS2)
    requires inv04(s), step2(s, AL2::EStep { q }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::EStep { q }), abs04(t)),
{
    let g = s.e[q].g;
    assert forall|k: KS| #[trigger] (t.gen)(k) >= (s.gen)(k) by {}
    assert forall|k: KS| k.0 != g implies #[trigger] (t.gen)(k) == (s.gen)(k) by {}
    assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies s.e.contains_key(q2) && (q2 != q ==> t.e[q2] == s.e[q2]) by {}
    assert(inv_del(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies del_ok(t, q2) by {
            assert(s.e.contains_key(q2)); assert(del_ok(s, q2));
        }
    }
    assert(inv_procs(t)) by {
        assert forall|p: nat, q2: nat| #![trigger t.w.contains_key(p), t.e.contains_key(q2)]
            t.w.contains_key(p) && t.e.contains_key(q2) && t.w[p].x.0 == t.e[q2].g implies t.e[q2].ph is Locked && !t.w[p].got by {
            assert(s.w.contains_key(p) && s.e.contains_key(q2));
        }
        assert forall|q1: nat, q2: nat| #![trigger t.e.contains_key(q1), t.e.contains_key(q2)]
            t.e.contains_key(q1) && t.e.contains_key(q2) && q1 != q2 implies t.e[q1].g != t.e[q2].g by {
            assert(s.e.contains_key(q1) && s.e.contains_key(q2));
        }
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(claimed(s, y));
            if exists|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0 {
                let q2 = choose|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0;
                assert(q2 != q);
                assert(t.e.contains_key(q2) && t.e[q2] == s.e[q2]);
            }
            if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y {
                let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y;
                assert(t.w.contains_key(p));
            }
        }
    }
    assert(inv_e_out(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && e_killed(t.e[q2]) implies {
            &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                    y.0 == t.e[q2].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y))
            &&& forall|y: X| #[trigger] t.e[q2].pre_out.contains(y) ==> y.0 == t.e[q2].g
        } by {
            assert(q2 != q);
            assert(s.e.contains_key(q2));
        }
    }
    assert(inv_gen(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) implies t.r[p].tgen <= (t.gen)(t.r[p].k) by {}
        assert forall|k: KS| #[trigger] t.degc.contains_key(k) implies t.degc[k].0 <= (t.gen)(k) by {}
    }
    assert(inv_re(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
            assert(t.r[p].k.0 != g);
            assert(e_quiet(s, s.r[p].k.0));
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && t.e[q2].g == t.r[p].k.0 implies !e_past(t.e[q2]) by {
                assert(q2 != q);
                assert(s.e.contains_key(q2));
            }
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p)
            && (probed(t.r[p]) && t.r[p].got && !t.nolock.contains(t.r[p].k.0) || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies
            w_quiet(t, t.r[p].k) && (counted(t.r[p]) ==> t.r[p].n == deg(t.rows, t.r[p].k)) by {
            assert(t.r[p].k.0 != g);
            assert(w_quiet(s, s.r[p].k));
        }
    }
    assert(inv_cur(t)) by {
        assert forall|p: nat| #[trigger] t.w.contains_key(p) && !(t.w[p].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p].x)) by {
            assert(s.w.contains_key(p) && s.e.contains_key(q));
            assert(!cur2(s.degc, s.gen, ks(s.w[p].x)));
        }
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.degc.contains_key(k)]
            t.e.contains_key(q2) && e_past(t.e[q2]) && k.0 == t.e[q2].g implies !cur2(t.degc, t.gen, k) by {
            if q2 == q {
                if t.degc.contains_key(k) { assert(s.degc[k].0 <= (s.gen)(k)); }
            } else {
                assert(s.e.contains_key(q2) && s.e.contains_key(q));
                assert(!cur2(s.degc, s.gen, k));
            }
        }
    }
    assert(inv_pre(t)) by {
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.e[q2].pre_degc.contains_key(k)]
            t.e.contains_key(q2) && t.e[q2].ph is Killed && t.e[q2].pre_degc.contains_key(k) implies
            k.0 == t.e[q2].g && t.e[q2].pre_degc[k].0 < (t.gen)(k) by {
            assert(q2 != q);
            assert(s.e.contains_key(q2));
        }
    }
}

/// The as-built RemoveGraph's first kill (only with control HD-0401, erase): `Kill ^KG("out", g)` before any
/// generation step. A proof attempt of the invariant: it fails where a reader of g whose probe was granted before
/// this eraser's lock still holds the current generation (F-0401), and where an entry of g is still current.
proof fn lemma_ekillout(s: AS2, q: nat, t: AS2)
    requires inv04(s), step2(s, AL2::EKillOut { q }, t),
    ensures inv04(t), abs04(t) == abs04(s),
{
    let g = s.e[q].g;
    assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies s.e.contains_key(q2) && (q2 != q ==> t.e[q2] == s.e[q2]) by {}
    assert forall|p: nat| #[trigger] s.w.contains_key(p) implies s.w[p].x.0 != g by { assert(s.w.contains_key(p) && s.e.contains_key(q)); }
    assert(inv_del(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies del_ok(t, q2) by {
            assert(s.e.contains_key(q2)); assert(del_ok(s, q2));
        }
    }
    assert(s.b is None);
    assert forall|y: X| y.0 == g implies #[trigger] s.out.contains(y) == s.rows.contains(y) by {
        assert forall|q2: nat| #[trigger] s.e.contains_key(q2) && s.e[q2].g == y.0 implies !e_killed(s.e[q2]) by {
            if q2 != q { assert(s.e.contains_key(q2) && s.e.contains_key(q)); }
        }
        lemma_unclaimed(s, y);
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            if y.0 == g {
                assert(t.e.contains_key(q) && e_killed(t.e[q]) && t.e[q].g == y.0);
            } else {
                assert(claimed(s, y));
                if exists|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0 {
                    let q2 = choose|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0;
                    assert(t.e.contains_key(q2) && t.e[q2] == s.e[q2]);
                }
                if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y {
                    let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y;
                    assert(t.w.contains_key(p));
                }
            }
        }
    }
    assert(inv_re(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
            assert(e_quiet(s, s.r[p].k.0));
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && t.e[q2].g == t.r[p].k.0 implies !e_past(t.e[q2]) by {
                assert(s.e.contains_key(q2));
                // the eraser leaves its lock phase without moving a generation (control HD-0401 fails here)
                assert(t.e[q2] == s.e[q2]);
            }
        }
    }
    assert(inv_cur(t)) by {
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.degc.contains_key(k)]
            t.e.contains_key(q2) && e_past(t.e[q2]) && k.0 == t.e[q2].g implies !cur2(t.degc, t.gen, k) by {
            // an entry of g may still carry its source's current generation (control HD-0401 fails here)
            assert(s.e.contains_key(q2) && e_past(s.e[q2]));
        }
    }
}

proof fn lemma_ekill(s: AS2, q: nat, t: AS2)
    requires inv04(s), step2(s, AL2::EKill { q }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::EKill { q }), abs04(t)),
{
    // An L1 Cache step keeps every generation. Control HD-0401 (erase) fails here: RemoveGraph kills ^KG("gen", g).
    assert(t.gen == s.gen);
    if !hd0401e() {
        let g = s.e[q].g;
        let e2 = t.e[q];
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies s.e.contains_key(q2) && (q2 != q ==> t.e[q2] == s.e[q2]) by {}
        assert forall|p: nat| #[trigger] s.w.contains_key(p) implies s.w[p].x.0 != g by { assert(s.w.contains_key(p) && s.e.contains_key(q)); }
        assert(inv_del(t)) by {
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies del_ok(t, q2) by {
                assert(s.e.contains_key(q2)); assert(del_ok(s, q2));
            }
        }
        assert(s.b is None);
        // every entry of g was unclaimed: visible == committed
        assert forall|y: X| y.0 == g implies #[trigger] s.out.contains(y) == s.rows.contains(y) by {
            assert forall|q2: nat| #[trigger] s.e.contains_key(q2) && s.e[q2].g == y.0 implies !e_killed(s.e[q2]) by {
                if q2 != q { assert(s.e.contains_key(q2) && s.e.contains_key(q)); }
            }
            lemma_unclaimed(s, y);
        }
        assert(inv_procs(t)) by {
            assert forall|p: nat, q2: nat| #![trigger t.w.contains_key(p), t.e.contains_key(q2)]
                t.w.contains_key(p) && t.e.contains_key(q2) && t.w[p].x.0 == t.e[q2].g implies t.e[q2].ph is Locked && !t.w[p].got by {
                assert(s.w.contains_key(p) && s.e.contains_key(q2));
            }
            assert forall|q1: nat, q2: nat| #![trigger t.e.contains_key(q1), t.e.contains_key(q2)]
                t.e.contains_key(q1) && t.e.contains_key(q2) && q1 != q2 implies t.e[q1].g != t.e[q2].g by {
                assert(s.e.contains_key(q1) && s.e.contains_key(q2));
            }
        }
        assert(inv_lockless(t)) by {
            assert forall|p: nat| #[trigger] t.w.contains_key(p) && !t.w[p].got implies t.nolock.contains(t.w[p].x.0) by {}
        }
        assert(inv_wrote(t)) by {
            assert forall|p: nat| #[trigger] t.w.contains_key(p) && wrote(t.w[p]) implies
                t.out.contains(t.w[p].x) == (t.w[p].kind is Put) && t.rows.contains(t.w[p].x) == t.w[p].had by {}
        }
        assert(inv_claimed(t)) by {
            assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
                t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
                if y.0 == g {
                    assert(t.e.contains_key(q) && e_killed(t.e[q]) && t.e[q].g == y.0);
                } else {
                    assert(claimed(s, y));
                    if exists|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0 {
                        let q2 = choose|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0;
                        assert(q2 != q);
                        assert(t.e.contains_key(q2) && t.e[q2] == s.e[q2]);
                    }
                    if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y {
                        let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y;
                        assert(t.w.contains_key(p));
                    }
                }
            }
        }
        assert(inv_e_out(t)) by {
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && e_killed(t.e[q2]) implies {
                &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                        y.0 == t.e[q2].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y))
                &&& forall|y: X| #[trigger] t.e[q2].pre_out.contains(y) ==> y.0 == t.e[q2].g
            } by {
                if q2 != q {
                    assert(s.e.contains_key(q2));
                    assert(s.e.contains_key(q2) && s.e.contains_key(q));
                    assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                        y.0 == t.e[q2].g implies !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y)) by {
                        assert(s.e[q2].g != g);
                    }
                } else {
                    assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                        y.0 == t.e[q2].g implies !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y)) by {
                        assert(s.out.contains(y) == s.rows.contains(y));
                    }
                }
            }
        }
        assert(inv_gen(t)) by {
            assert forall|k: KS| #[trigger] t.degc.contains_key(k) implies t.degc[k].0 <= (t.gen)(k) by {}
        }
        assert(inv_re(t)) by {
            assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
                && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
                assert(e_quiet(s, s.r[p].k.0));
                assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && t.e[q2].g == t.r[p].k.0 implies !e_past(t.e[q2]) by {
                    assert(s.e.contains_key(q2));
                }
            }
        }
        assert(inv_rw(t)) by {
            assert forall|p: nat| #[trigger] t.r.contains_key(p)
                && (probed(t.r[p]) && t.r[p].got && !t.nolock.contains(t.r[p].k.0) || t.r[p].ph is Checked)
                && t.r[p].tgen == (t.gen)(t.r[p].k) implies
                w_quiet(t, t.r[p].k) && (counted(t.r[p]) ==> t.r[p].n == deg(t.rows, t.r[p].k)) by {
                if t.r[p].k.0 == g {
                    // a reader of g whose generation is current never had its probe granted past this eraser's step
                    assert(s.r[p].tgen == (s.gen)(s.r[p].k));
                    if probed(s.r[p]) && s.r[p].got || s.r[p].ph is Checked { assert(e_quiet(s, g)); assert(!e_past(s.e[q])); }
                } else {
                    assert(w_quiet(s, s.r[p].k));
                }
            }
        }
        assert(inv_cur(t)) by {
            assert forall|p: nat| #[trigger] t.w.contains_key(p) && !(t.w[p].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p].x)) by {
                assert(!cur2(s.degc, s.gen, ks(s.w[p].x)));
            }
            assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.degc.contains_key(k)]
                t.e.contains_key(q2) && e_past(t.e[q2]) && k.0 == t.e[q2].g implies !cur2(t.degc, t.gen, k) by {
                if q2 != q {
                    assert(s.e.contains_key(q2));
                    assert(!cur2(s.degc, s.gen, k));
                }
            }
        }
        assert(inv_pre(t)) by {
            assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.e[q2].pre_degc.contains_key(k)]
                t.e.contains_key(q2) && t.e[q2].ph is Killed && t.e[q2].pre_degc.contains_key(k) implies
                k.0 == t.e[q2].g && t.e[q2].pre_degc[k].0 < (t.gen)(k) by {
                if q2 == q {
                    assert(s.degc.contains_key(k) && k.0 == g);
                    assert(!cur2(s.degc, s.gen, k));
                    assert(s.degc[k].0 <= (s.gen)(k));
                } else {
                    assert(s.e.contains_key(q2));
                }
            }
        }
        assert(abs04(t) == AS1 { cache: abs04(t).cache, ..abs04(s) });
        assert forall|k: KS| #[trigger] t.degc.contains_key(k) && !(s.degc.contains_key(k) && s.degc[k] == t.degc[k])
            implies entry_ok(s.rows, s.gen, k, t.degc[k]) by {}
    }
}

proof fn lemma_ecommit(s: AS2, q: nat, g: int, del: Set<X>, t: AS2)
    requires inv04(s), step2(s, AL2::ECommit { q, g, del }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::ECommit { q, g, del }), abs04(t)),
{
    assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies s.e.contains_key(q2) && q2 != q && t.e[q2] == s.e[q2] by {}
    assert forall|p: nat| #[trigger] s.w.contains_key(p) implies s.w[p].x.0 != g by { assert(s.w.contains_key(p) && s.e.contains_key(q)); }
    assert(del_ok(s, q));
    // the DELETE removed every committed row of g, and none was added since (guard R04-5): the commit leaves g empty
    assert(t.rows =~= s.rows.filter(|y: X| y.0 != g)) by {
        assert forall|y: X| #[trigger] t.rows.contains(y) == s.rows.filter(|y: X| y.0 != g).contains(y) by {
            if y.0 == g { if s.rows.contains(y) { assert(s.e[q].del.contains(y)); } }
            else { assert(!s.e[q].del.contains(y)); }
        }
    }
    assert(inv_del(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies del_ok(t, q2) by {
            assert(s.e.contains_key(q2) && s.e.contains_key(q));
            assert(del_ok(s, q2));
            assert(s.e[q2].g != g);
        }
    }
    assert forall|src: int| !#[trigger] cur1(abs04(s), (g, src)) by {
        assert(s.e.contains_key(q) && e_past(s.e[q]) && (g, src).0 == s.e[q].g);
        if s.degc.contains_key((g, src)) { assert(!cur2(s.degc, s.gen, (g, src))); }
    }
    assert(inv_procs(t)) by {
        assert forall|p: nat, q2: nat| #![trigger t.w.contains_key(p), t.e.contains_key(q2)]
            t.w.contains_key(p) && t.e.contains_key(q2) && t.w[p].x.0 == t.e[q2].g implies t.e[q2].ph is Locked && !t.w[p].got by {
            assert(s.w.contains_key(p) && s.e.contains_key(q2));
        }
        assert forall|q1: nat, q2: nat| #![trigger t.e.contains_key(q1), t.e.contains_key(q2)]
            t.e.contains_key(q1) && t.e.contains_key(q2) && q1 != q2 implies t.e[q1].g != t.e[q2].g by {
            assert(s.e.contains_key(q1) && s.e.contains_key(q2));
        }
    }
    assert(inv_wrote(t)) by {
        assert forall|p: nat| #[trigger] t.w.contains_key(p) && wrote(t.w[p]) implies
            t.out.contains(t.w[p].x) == (t.w[p].kind is Put) && t.rows.contains(t.w[p].x) == t.w[p].had by {}
    }
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            if y.0 == g {
                assert(!s.out.contains(y));
            } else {
                assert(claimed(s, y));
                if exists|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0 {
                    let q2 = choose|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0;
                    assert(q2 != q);
                    assert(t.e.contains_key(q2) && t.e[q2] == s.e[q2]);
                }
                if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y {
                    let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y;
                    assert(t.w.contains_key(p));
                }
            }
        }
    }
    assert(inv_e_out(t)) by {
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && e_killed(t.e[q2]) implies {
            &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                    y.0 == t.e[q2].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y))
            &&& forall|y: X| #[trigger] t.e[q2].pre_out.contains(y) ==> y.0 == t.e[q2].g
        } by {
            assert(s.e.contains_key(q2));
            assert(s.e.contains_key(q2) && s.e.contains_key(q));
        }
    }
    assert(inv_re(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
            assert(e_quiet(s, s.r[p].k.0));
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && t.e[q2].g == t.r[p].k.0 implies !e_past(t.e[q2]) by {
                assert(s.e.contains_key(q2));
            }
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p)
            && (probed(t.r[p]) && t.r[p].got && !t.nolock.contains(t.r[p].k.0) || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies
            w_quiet(t, t.r[p].k) && (counted(t.r[p]) ==> t.r[p].n == deg(t.rows, t.r[p].k)) by {
            assert(w_quiet(s, s.r[p].k));
            if t.r[p].k.0 == g {
                assert(probed(s.r[p]) && s.r[p].got || s.r[p].ph is Checked);
                assert(e_quiet(s, g));
                assert(!e_past(s.e[q]));
            }
            lemma_deg_graph(s.rows, g, t.r[p].k);
        }
    }
    assert(inv_cur(t)) by {
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.degc.contains_key(k)]
            t.e.contains_key(q2) && e_past(t.e[q2]) && k.0 == t.e[q2].g implies !cur2(t.degc, t.gen, k) by {
            assert(s.e.contains_key(q2));
        }
    }
    assert(inv_pre(t)) by {
        assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.e[q2].pre_degc.contains_key(k)]
            t.e.contains_key(q2) && t.e[q2].ph is Killed && t.e[q2].pre_degc.contains_key(k) implies
            k.0 == t.e[q2].g && t.e[q2].pre_degc[k].0 < (t.gen)(k) by {
            assert(s.e.contains_key(q2));
        }
    }
}

proof fn lemma_eabort(s: AS2, q: nat, t: AS2)
    requires inv04(s), step2(s, AL2::EAbort { q }, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::EAbort { q }), abs04(t)),
{
    // An L1 Cache step keeps every generation. Control HD-0401 (erase) fails here: the rollback restores the killed ^KG("gen", g).
    assert(t.gen == s.gen);
    if !hd0401e() {
        let e0 = s.e[q];
        let g = e0.g;
        assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies s.e.contains_key(q2) && q2 != q && t.e[q2] == s.e[q2] by {}
        // a rollback from TSTART (Locked) may meet lock-less writers of g; past its DELETE no writer of g is open
        assert forall|p: nat| #[trigger] s.w.contains_key(p) && !(e0.ph is Locked) implies s.w[p].x.0 != g by {
            assert(s.w.contains_key(p) && s.e.contains_key(q));
        }
        assert(inv_del(t)) by {
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) implies del_ok(t, q2) by {
                assert(s.e.contains_key(q2)); assert(del_ok(s, q2));
            }
        }
        assert(s.b is None);
        assert(!(e0.ph is OutKilled));
        assert(inv_procs(t)) by {
            assert forall|p: nat, q2: nat| #![trigger t.w.contains_key(p), t.e.contains_key(q2)]
                t.w.contains_key(p) && t.e.contains_key(q2) && t.w[p].x.0 == t.e[q2].g implies t.e[q2].ph is Locked && !t.w[p].got by {
                assert(s.w.contains_key(p) && s.e.contains_key(q2));
            }
            assert forall|q1: nat, q2: nat| #![trigger t.e.contains_key(q1), t.e.contains_key(q2)]
                t.e.contains_key(q1) && t.e.contains_key(q2) && q1 != q2 implies t.e[q1].g != t.e[q2].g by {
                assert(s.e.contains_key(q1) && s.e.contains_key(q2));
            }
        }
        assert(inv_lockless(t)) by {
            assert forall|p: nat| #[trigger] t.w.contains_key(p) && !t.w[p].got implies t.nolock.contains(t.w[p].x.0) by {}
        }
        assert(inv_wrote(t)) by {
            assert forall|p: nat| #[trigger] t.w.contains_key(p) && wrote(t.w[p]) implies
                t.out.contains(t.w[p].x) == (t.w[p].kind is Put) && t.rows.contains(t.w[p].x) == t.w[p].had by {
                if e_killed(e0) { assert(!e0.pre_out.contains(t.w[p].x)); }
            }
        }
        assert(inv_claimed(t)) by {
            assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
                t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
                if y.0 == g && e_killed(e0) {
                    assert(!s.out.contains(y) && s.rows.contains(y) == e0.pre_out.contains(y));
                } else {
                    if e_killed(e0) { assert(!e0.pre_out.contains(y)); }
                    assert(claimed(s, y));
                    if exists|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0 {
                        let q2 = choose|q2: nat| #[trigger] s.e.contains_key(q2) && e_killed(s.e[q2]) && s.e[q2].g == y.0;
                        assert(q2 != q);
                        assert(t.e.contains_key(q2) && t.e[q2] == s.e[q2]);
                    }
                    if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y {
                        let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y;
                        assert(t.w.contains_key(p));
                    }
                }
            }
        }
        assert(inv_e_out(t)) by {
            assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && e_killed(t.e[q2]) implies {
                &&& forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                        y.0 == t.e[q2].g ==> !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y))
                &&& forall|y: X| #[trigger] t.e[q2].pre_out.contains(y) ==> y.0 == t.e[q2].g
            } by {
                assert(s.e.contains_key(q2));
                assert(s.e.contains_key(q2) && s.e.contains_key(q));
                assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)] #![trigger t.e[q2].pre_out.contains(y)]
                    y.0 == t.e[q2].g implies !t.out.contains(y) && (t.rows.contains(y) == t.e[q2].pre_out.contains(y)) by {
                    if e_killed(e0) { assert(!e0.pre_out.contains(y)); }
                }
            }
        }
        assert(inv_gen(t)) by {
            assert forall|k: KS| #[trigger] t.degc.contains_key(k) implies t.degc[k].0 <= (t.gen)(k) by {
                if e0.ph is Killed && e0.pre_degc.contains_key(k) {} else {}
            }
        }
        assert(inv_re(t)) by {
            assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
                && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
                assert(e_quiet(s, s.r[p].k.0));
                assert forall|q2: nat| #[trigger] t.e.contains_key(q2) && t.e[q2].g == t.r[p].k.0 implies !e_past(t.e[q2]) by {
                    assert(s.e.contains_key(q2));
                }
            }
        }
        assert(inv_rw(t)) by {
            assert forall|p: nat| #[trigger] t.r.contains_key(p)
                && (probed(t.r[p]) && t.r[p].got && !t.nolock.contains(t.r[p].k.0) || t.r[p].ph is Checked)
                && t.r[p].tgen == (t.gen)(t.r[p].k) implies
                w_quiet(t, t.r[p].k) && (counted(t.r[p]) ==> t.r[p].n == deg(t.rows, t.r[p].k)) by {
                assert(w_quiet(s, s.r[p].k));
            }
        }
        assert(inv_cur(t)) by {
            assert forall|p: nat| #[trigger] t.w.contains_key(p) && !(t.w[p].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p].x)) by {
                assert(!cur2(s.degc, s.gen, ks(s.w[p].x)));
            }
            assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.degc.contains_key(k)]
                t.e.contains_key(q2) && e_past(t.e[q2]) && k.0 == t.e[q2].g implies !cur2(t.degc, t.gen, k) by {
                assert(s.e.contains_key(q2));
                assert(s.e.contains_key(q2) && s.e.contains_key(q));
                assert(!cur2(s.degc, s.gen, k));
                if e0.ph is Killed && e0.pre_degc.contains_key(k) { assert(k.0 == g); }
            }
        }
        assert(inv_pre(t)) by {
            assert forall|q2: nat, k: KS| #![trigger t.e.contains_key(q2), t.e[q2].pre_degc.contains_key(k)]
                t.e.contains_key(q2) && t.e[q2].ph is Killed && t.e[q2].pre_degc.contains_key(k) implies
                k.0 == t.e[q2].g && t.e[q2].pre_degc[k].0 < (t.gen)(k) by {
                assert(s.e.contains_key(q2));
            }
        }
        assert(abs04(t) == AS1 { cache: abs04(t).cache, ..abs04(s) });
        assert forall|k: KS| #[trigger] t.degc.contains_key(k) && !(s.degc.contains_key(k) && s.degc[k] == t.degc[k])
            implies entry_ok(s.rows, s.gen, k, t.degc[k]) by {
            // a restored entry is stale: the eraser stepped the generation before it killed (control HD-0401 fails here)
            assert(e0.ph is Killed && e0.pre_degc.contains_key(k));
        }
    }
}

// ---- rebuild

proof fn lemma_bstep_or_begin(s: AS2, l: AL2, t: AS2)
    requires inv04(s), step2(s, l, t), l is BBegin || l is BStep,
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(l), abs04(t)),
{
    assert forall|k: KS| #[trigger] (t.gen)(k) >= (s.gen)(k) by {}
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
            assert(claimed(s, y));
            if exists|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y {
                let p = choose|p: nat| #[trigger] s.w.contains_key(p) && wrote(s.w[p]) && s.w[p].x == y;
                assert(t.w.contains_key(p));
            }
            if exists|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0 {
                let q = choose|q: nat| #[trigger] s.e.contains_key(q) && e_killed(s.e[q]) && s.e[q].g == y.0;
                assert(t.e.contains_key(q));
            }
        }
    }
    assert(inv_gen(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) implies t.r[p].tgen <= (t.gen)(t.r[p].k) by {}
        assert forall|k: KS| #[trigger] t.degc.contains_key(k) implies t.degc[k].0 <= (t.gen)(k) by {}
    }
    assert(inv_re(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
            if l is BBegin { assert(e_quiet(s, s.r[p].k.0)); }
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p)
            && (probed(t.r[p]) && t.r[p].got && !t.nolock.contains(t.r[p].k.0) || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies
            w_quiet(t, t.r[p].k) && (counted(t.r[p]) ==> t.r[p].n == deg(t.rows, t.r[p].k)) by {
            assert(w_quiet(s, s.r[p].k));
        }
    }
    assert(inv_cur(t)) by {
        if l is BStep {
            assert forall|k: KS| !#[trigger] cur2(t.degc, t.gen, k) by {
                if t.degc.contains_key(k) { assert(s.degc[k].0 <= (s.gen)(k)); }
            }
        }
    }
}

proof fn lemma_bkill(s: AS2, t: AS2)
    requires inv04(s), step2(s, AL2::BKill, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::BKill), abs04(t)),
{
    // An L1 Cache step keeps every generation. Control HD-0401 (rebuild) fails here: RemoveAll kills ^KG("gen").
    assert(t.gen == s.gen);
    if !hd0401b() {
        assert forall|y: X| #[trigger] s.out.contains(y) == s.rows.contains(y) by { lemma_unclaimed(s, y); }
        assert(s.out =~= s.rows);
        assert(inv_claimed(t)) by {
            assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
                t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {}
        }
        assert(inv_gen(t)) by {
            assert forall|k: KS| #[trigger] t.degc.contains_key(k) implies t.degc[k].0 <= (t.gen)(k) by {}
        }
        assert(inv_re(t));
        assert(inv_rw(t)) by {
            assert forall|p: nat| #[trigger] t.r.contains_key(p)
                && (probed(t.r[p]) && t.r[p].got && !t.nolock.contains(t.r[p].k.0) || t.r[p].ph is Checked)
                && t.r[p].tgen == (t.gen)(t.r[p].k) implies
                w_quiet(t, t.r[p].k) && (counted(t.r[p]) ==> t.r[p].n == deg(t.rows, t.r[p].k)) by {
                assert(e_quiet(s, s.r[p].k.0));
            }
        }
        assert(inv_pre(t)) by {
            assert forall|k: KS| #[trigger] t.b->0.pre_degc.contains_key(k) implies t.b->0.pre_degc[k].0 < (t.gen)(k) by {
                assert(!cur2(s.degc, s.gen, k));
            }
        }
        assert(abs04(t) == AS1 { cache: abs04(t).cache, ..abs04(s) });
    }
}

proof fn lemma_bfill_commit(s: AS2, l: AL2, t: AS2)
    requires inv04(s), step2(s, l, t), l is BFill || l is BCommit,
    ensures inv04(t), abs04(t) == abs04(s),
{
    assert(inv_claimed(t)) by {
        assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
            t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {}
    }
    assert(inv_re(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
            assert(e_quiet(s, s.r[p].k.0));
        }
    }
    assert(inv_rw(t)) by {
        assert forall|p: nat| #[trigger] t.r.contains_key(p)
            && (probed(t.r[p]) && t.r[p].got && !t.nolock.contains(t.r[p].k.0) || t.r[p].ph is Checked)
            && t.r[p].tgen == (t.gen)(t.r[p].k) implies
            w_quiet(t, t.r[p].k) && (counted(t.r[p]) ==> t.r[p].n == deg(t.rows, t.r[p].k)) by {
            assert(e_quiet(s, s.r[p].k.0));
        }
    }
    assert(inv_cur(t));
}

proof fn lemma_babort(s: AS2, t: AS2)
    requires inv04(s), step2(s, AL2::BAbort, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(AL2::BAbort), abs04(t)),
{
    // An L1 Cache step keeps every generation. Control HD-0401 (rebuild) fails here: the rollback restores the killed ^KG("gen").
    assert(t.gen == s.gen);
    if !hd0401b() {
        let b = s.b->0;
        if b_killed(b) {
            assert(t.out == s.rows);
            assert(inv_claimed(t)) by {
                assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
                    t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {}
            }
            assert(inv_gen(t)) by {
                assert forall|k: KS| #[trigger] t.degc.contains_key(k) implies t.degc[k].0 <= (t.gen)(k) by {}
            }
        } else {
            assert(inv_claimed(t)) by {
                assert forall|y: X| #![trigger t.out.contains(y)] #![trigger t.rows.contains(y)]
                    t.out.contains(y) != t.rows.contains(y) implies claimed(t, y) by {
                    assert(claimed(s, y));
                }
            }
        }
        assert(inv_re(t)) by {
            assert forall|p: nat| #[trigger] t.r.contains_key(p) && (probed(t.r[p]) && t.r[p].got || t.r[p].ph is Checked)
                && t.r[p].tgen == (t.gen)(t.r[p].k) implies e_quiet(t, t.r[p].k.0) by {
                assert(e_quiet(s, s.r[p].k.0));
            }
        }
        assert(inv_rw(t)) by {
            assert forall|p: nat| #[trigger] t.r.contains_key(p)
                && (probed(t.r[p]) && t.r[p].got && !t.nolock.contains(t.r[p].k.0) || t.r[p].ph is Checked)
                && t.r[p].tgen == (t.gen)(t.r[p].k) implies
                w_quiet(t, t.r[p].k) && (counted(t.r[p]) ==> t.r[p].n == deg(t.rows, t.r[p].k)) by {
                assert(e_quiet(s, s.r[p].k.0));
                assert(w_quiet(s, s.r[p].k));
            }
        }
        assert(inv_cur(t)) by {
            assert forall|p: nat| #[trigger] t.w.contains_key(p) && !(t.w[p].ph is Locked) implies !cur2(t.degc, t.gen, ks(t.w[p].x)) by {}
        }
        assert(abs04(t) == AS1 { cache: abs04(t).cache, ..abs04(s) });
        assert forall|k: KS| #[trigger] t.degc.contains_key(k) && !(s.degc.contains_key(k) && s.degc[k] == t.degc[k])
            implies entry_ok(s.rows, s.gen, k, t.degc[k]) by {
            // a restored entry is stale: the rebuild stepped every generation before it killed (control HD-0401 fails here)
            assert(b_killed(b) && b.pre_degc.contains_key(k));
        }
    }
}

// ------------------------------------------------------------------------------------------------ refinement

proof fn lemma_step(s: AS2, l: AL2, t: AS2)
    requires inv04(s), step2(s, l, t),
    ensures inv04(t), step_or_stutter::<AdjL1>(abs04(s), lab04(l), abs04(t)),
{
    match l {
        AL2::WLock { p, x, kind, got } => { lemma_wlock(s, p, x, kind, got, t); }
        AL2::WPre { p } => { lemma_wpre(s, p, t); }
        AL2::WOut { p } => { lemma_wout(s, p, t); }
        AL2::WPost { p } => { lemma_wpost(s, p, t); }
        AL2::WCommit { p, x, add } => { lemma_wcommit(s, p, x, add, t); }
        AL2::WAbort { p } => { lemma_wabort(s, p, t); }
        AL2::RStart { p, k } => { lemma_rstart(s, p, k, t); }
        AL2::RLookup { p, k, hit } => { lemma_reader_step(s, l, t); }
        AL2::RProbe { p } => { lemma_reader_step(s, l, t); }
        AL2::RCount { p } => { lemma_reader_step(s, l, t); }
        AL2::RCheck { p } => { lemma_reader_step(s, l, t); }
        AL2::RStore { p } => { lemma_rstore(s, p, t); }
        AL2::RRecheck { p } => { lemma_rrecheck(s, p, t); }
        AL2::ELock { q, g } => { lemma_elock(s, q, g, t); }
        AL2::ERows { q } => { lemma_erows(s, q, t); }
        AL2::EStep { q } => { lemma_estep(s, q, t); }
        AL2::EKillOut { q } => { lemma_ekillout(s, q, t); }
        AL2::EKill { q } => { lemma_ekill(s, q, t); }
        AL2::ECommit { q, g, del } => { lemma_ecommit(s, q, g, del, t); }
        AL2::EAbort { q } => { lemma_eabort(s, q, t); }
        AL2::BBegin => { lemma_bstep_or_begin(s, l, t); }
        AL2::BStep => { lemma_bstep_or_begin(s, l, t); }
        AL2::BKill => { lemma_bkill(s, t); }
        AL2::BFill => { lemma_bfill_commit(s, l, t); }
        AL2::BCommit => { lemma_bfill_commit(s, l, t); }
        AL2::BAbort => { lemma_babort(s, t); }
    }
}

impl Refines<AdjL1> for AdjL2 {
    open spec fn abs(s: AS2) -> AS1 { abs04(s) }
    open spec fn lab(l: AL2) -> Option<AL1> { lab04(l) }

    proof fn init_refines(s: AS2) {}

    proof fn step_refines(s: AS2, l: AL2, t: AS2) { lemma_step(s, l, t); }
}

impl SafeContract for AdjL2 {
    open spec fn inv(s: AS2) -> bool { inv04(s) }

    proof fn init_safe(s: AS2) {
        assert(inv_claimed(s)) by {
            assert forall|y: X| #![trigger s.out.contains(y)] #![trigger s.rows.contains(y)]
                s.out.contains(y) != s.rows.contains(y) implies claimed(s, y) by {}
        }
    }

    proof fn step_safe(s: AS2, l: AL2, t: AS2) { lemma_step(s, l, t); }
}

// ------------------------------------------------------------------------------------------------ theorems

proof fn lemma_raw_inv_at(states: Seq<AS2>, labels: Seq<AL2>, k: int)
    requires execution::<AdjRaw>(states, labels), 0 <= k < states.len(),
    ensures inv04(states[k]),
    decreases k,
{
    if k == 0 { AdjL2::init_safe(states[0]); } else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant and its abstraction is an
/// L1 execution whose every state satisfies L1's business invariant.
pub proof fn theorem_raw_executions_refine(states: Seq<AS2>, labels: Seq<AL2>)
    requires execution::<AdjRaw>(states, labels),
    ensures
        execution::<AdjL2>(states, labels),
        abstract_execution::<AdjL1>(Seq::new(states.len(), |i: int| abs04(states[i])),
                                    Seq::new(labels.len(), |i: int| lab04(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv04(#[trigger] states[i]) && inv1(abs04(states[i])),
{
    assert forall|i: int| 0 <= i < states.len() implies inv04(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<AdjL2>(states, labels));
    trace_refines::<AdjL2, AdjL1>(states, labels);
    refinement_preserves_safety::<AdjL2, AdjL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| abs04(states[i])) =~= Seq::new(states.len(), |i: int| <AdjL2 as Refines<AdjL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| lab04(labels[i])) =~= Seq::new(labels.len(), |i: int| <AdjL2 as Refines<AdjL1>>::lab(labels[i])));
}

/// ADJ-I5.9 on the layout: with no transaction open, a `^KG("degc")` entry carrying its source's current
/// `^KG("gen")` holds the out-degree of the committed rows, which is then also the count of `^KG("out")`.
pub proof fn theorem_quiescent_cache_is_committed_degree(s: AS2, k: KS)
    requires
        inv04(s), inv1(abs04(s)), cur2(s.degc, s.gen, k),
        forall|p: nat| !#[trigger] s.w.contains_key(p), forall|q: nat| !#[trigger] s.e.contains_key(q), s.b is None,
    ensures s.degc[k].1 == deg(s.rows, k), deg(s.out, k) == deg(s.rows, k),
{
    assert(abs04(s).cache.contains_key(k));
    assert(entry_ok(s.rows, s.gen, k, s.degc[k]));
    lemma_count_committed(s, k);
}

/// P-A3 is a proved consequence of guard R04-5, not a premise: a writer of g and an eraser of g are open together only
/// while the eraser has not passed TSTART and the writer is a lock-less one already in flight (its row then blocks
/// the eraser's DELETE); past its DELETE an eraser of g has no writer of g, new rows included.
pub proof fn theorem_pa3_from_guard(s: AS2, p: nat, q: nat)
    requires inv04(s), s.w.contains_key(p), s.e.contains_key(q), s.w[p].x.0 == s.e[q].g,
    ensures s.e[q].ph is Locked, !s.w[p].got,
{
}

/// The reviewed erase is complete: when it commits, no committed edge row of its graph is left (every row of g
/// committed at that point is one its DELETE removed).
pub proof fn theorem_guarded_erase_removes_graph(s: AS2, q: nat, g: int, del: Set<X>, t: AS2, y: X)
    requires inv04(s), step2(s, AL2::ECommit { q, g, del }, t), y.0 == g,
    ensures !t.rows.contains(y),
{
    assert(del_ok(s, q));
    if s.rows.contains(y) { assert(s.e[q].del.contains(y)); }
}

} // verus!
