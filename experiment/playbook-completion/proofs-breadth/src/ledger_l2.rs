//! Module 11 (ledger), L2: the algorithmic machine over the stored layout at pin 3eaa79cf, its refinement of L1 for
//! every step, its invariant, and the broken-implementation controls.
//!
//! State (production names):
//! - `meta`        `^IVG.Ledger("meta","state"|"strict")`                                     Ledger.cls:3, 252-383
//! - `g.head`      `^IVG.Ledger("head")` (also the name of the head lock)                      Ledger.cls:4, 440, 556
//! - `g.rec`       `^IVG.Ledger("rec", seq, ord)`                                              Ledger.cls:7, 534-536
//! - `g.revrow`    the `Graph_KG.ledger_revisions` row (Seq, RevisionId, OpCount, IdempotencyKey) Ledger.cls:537-555
//! - `g.id_by_seq` `^IVG.Ledger("idBySeq", seq)`; `g.rev_by_id` `^IVG.Ledger("revById", id)`   Ledger.cls:5, 557-558
//! - `g.idem`      `^IVG.Ledger("idem", key) = $LB(seq, fingerprint)`                          Ledger.cls:10, 457-474, 525
//! - `g.sx`        `^IVG.Ledger("stmt", id)`, `("tuple", s, p, o, g) = id` (live only), `("stmtNext")`
//!                 maintained per record by create_rel / delete_rel                     Ledger.cls:8-9, LedgerApply.cls:160-171
//! - `stats.ok`    `Graph_KG.ledger_stats` CommitsOk (WriteRevision, Ledger.cls:559-566); `stats.rej` one refusal
//!                 counter that `LedgerStats.Bump` raises after a refused or replayed commit or a guard refusal
//! - `rows`        the governed content tables
//! - `txn`         a commit nested in a caller's open transaction (4.7.0, Ledger.cls:388-410): the revision and its
//!                 writes are written, the head lock is held until the caller ends (an unlock inside a transaction
//!                 waits), and the caller's commit keeps them or its rollback restores every before-image
//! - `gcache`, `probe_fails` one engine's LedgerGuard cache and whether its probe can run (guard.py:20-80)
//! - `copies`      a Bump's opened copy of the stats row (%OpenId takes no lock; LedgerStats.cls:65-88)
//! - `drift`       ghost: keys written outside the ledger
//!
//! Steps are transactions (each holds the head lock where the code takes it). **Design**: the reviewed design per the
//! working answers. HD-0801 alternative (b) and HD-1103 option (c): every governed engine write reads strict mode at
//! write time and fails closed when the probe cannot run; every engine writer is guarded (F-1108 remedy); the
//! eraser behind bulk_delete_adjacency takes the head lock (HD-1201). F-1102 remedy: each counter is one atomic
//! increment of its own field and the commit counter is counted in the commit's own transaction. Commit, replay and
//! nesting are the pin's. Controls (Cargo features) put back the pin's behaviour one decision at a time.
//!
//! Modelling premises (PROOFS.md P-L1..P-L6): a revision id is fresh (GUID); the genesis records exactly the governed
//! rows; a governed write waits for the row locks of an open nested commit; Disable waits while a nested commit holds
//! the head lock (the pin's Disable takes no head lock: a premise the pin violates); an applied changeset's records
//! are its operations (failed operations, kinds, adoption and post-commit properties are not modelled).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::ledger_l1::*;

verus! {

// ------------------------------------------------------------------------------------------------ the layout

pub struct RevRow { pub id: Id, pub nops: nat, pub key: Option<IKey> }

/// `^IVG.Ledger("stmt", id) = $LB(s, p, o, graph, createdSeq, deletedSeq)`.
pub struct Stmt { pub k: K, pub created: nat, pub deleted: Option<nat> }

pub struct SIdx { pub stmt: Map<nat, Stmt>, pub tuple: Map<K, nat>, pub next: nat }

pub struct Glob {
    pub head: nat,
    pub rec: Map<(nat, nat), Op>,
    pub revrow: Map<nat, RevRow>,
    pub id_by_seq: Map<nat, Id>,
    pub rev_by_id: Map<Id, nat>,
    pub idem: Map<IKey, (nat, Fp)>,
    pub sx: SIdx,
}

pub struct Meta { pub state: LState, pub strict: bool }

pub struct Stats { pub ok: nat, pub rej: nat }

/// A commit's arguments (pMetaJson: fingerprint, expected_head, idempotency_key) and the new revision's id.
pub struct CArgs { pub recs: Seq<Op>, pub key: Option<IKey>, pub fp: Fp, pub exp: Option<Id>, pub id: Id }

/// An open caller transaction holding a nested commit: the before-images (ledger globals, the stats counter, the
/// rows the changeset touched).
pub struct Txn { pub pre: Glob, pub pre_ok: nat, pub pre_rows: Map<K, V>, pub a: CArgs }

/// Governed engine writers: the engine API (create_node, ...), Cypher writes (module 08, same guard), and
/// bulk_delete_adjacency (Graph.KG.Eraser.EraseEdges: deletes the edge rows and their statement entries).
pub enum Wr { Api, Cypher, BulkDeleteAdj }

pub struct LS2 {
    pub meta: Meta,
    pub g: Glob,
    pub stats: Stats,
    pub rows: Map<K, V>,
    pub txn: Option<Txn>,
    pub gcache: Option<Meta>,
    pub probe_fails: bool,
    pub copies: Map<nat, Stats>,
    pub drift: Set<K>,
}

pub enum L2Label {
    Enable { strict: bool, id: Id, recs: Seq<Op>, busy: bool },
    Disable,
    SetStrict { on: bool },
    /// A commit outside any caller transaction (its own TSTART/TCOMMIT).
    Commit { a: CArgs, out: COut },
    /// A commit nested in a caller's open transaction (4.7.0); refused nested commits are `Commit` refusals.
    CommitNested { a: CArgs },
    /// The caller's commit (`keep`) or rollback of a transaction holding a nested commit.
    CallerEnd { keep: bool, a: CArgs, seq: nat },
    /// The guard's cache expires and the engine probes Graph.KG.Ledger.Meta again (guard.py:38-59).
    GuardProbe,
    /// The environment: the guard's probe starts or stops failing.
    ProbeFails { on: bool },
    /// A governed engine write; `landed` when the guard lets it through.
    EngineWrite { w: Wr, k: K, v: Option<V>, landed: bool },
    /// LedgerStats.Bump by process p: %OpenId of the stats row, then its %Save.
    BumpRead { p: nat },
    BumpSave { p: nat },
}

// ------------------------------------------------------------------------------------------------ statement index

pub open spec fn stmt_op(x: SIdx, seq: nat, op: Op) -> SIdx {
    if !op.k.edge { x } else {
        match op.v {
            Some(_) => if x.tuple.contains_key(op.k) { x } else {
                SIdx {
                    stmt: x.stmt.insert(x.next, Stmt { k: op.k, created: seq, deleted: None }),
                    tuple: x.tuple.insert(op.k, x.next),
                    next: x.next + 1,
                }
            },
            None => if x.tuple.contains_key(op.k) {
                SIdx {
                    stmt: x.stmt.insert(x.tuple[op.k], Stmt { deleted: Some(seq), ..x.stmt[x.tuple[op.k]] }),
                    tuple: x.tuple.remove(op.k),
                    next: x.next,
                }
            } else { x },
        }
    }
}

pub open spec fn stmt_fold(x: SIdx, seq: nat, rs: Seq<Op>) -> SIdx
    decreases rs.len()
{
    if rs.len() == 0 { x } else { stmt_op(stmt_fold(x, seq, rs.drop_last()), seq, rs.last()) }
}

/// Every live tuple entry names its own open statement; statement ids are below stmtNext.
pub open spec fn sidx_ok(x: SIdx) -> bool {
    &&& forall|k: K| #[trigger] x.tuple.contains_key(k) ==>
            x.tuple[k] < x.next && x.stmt.contains_key(x.tuple[k]) && x.stmt[x.tuple[k]].k == k
            && x.stmt[x.tuple[k]].deleted is None
    &&& forall|i: nat| #[trigger] x.stmt.contains_key(i) ==> i < x.next
}

/// Outside d, an edge has a live statement entry iff it is live in m.
pub open spec fn live_ok(x: SIdx, m: Map<K, V>, d: Set<K>) -> bool {
    forall|k: K| #![trigger x.tuple.contains_key(k)] #![trigger val(m, k)]
        k.edge && !d.contains(k) ==> (x.tuple.contains_key(k) <==> val(m, k) is Some)
}

proof fn lemma_stmt_op_ok(x: SIdx, seq: nat, op: Op)
    requires sidx_ok(x),
    ensures sidx_ok(stmt_op(x, seq, op)),
{
    let y = stmt_op(x, seq, op);
    if op.k.edge {
        if op.v is Some {
            if !x.tuple.contains_key(op.k) {
                assert(!x.stmt.contains_key(x.next));
                assert forall|k: K| #[trigger] y.tuple.contains_key(k) implies
                    y.tuple[k] < y.next && y.stmt.contains_key(y.tuple[k]) && y.stmt[y.tuple[k]].k == k
                    && y.stmt[y.tuple[k]].deleted is None by {
                    if k != op.k {
                        assert(x.tuple.contains_key(k));
                        assert(x.tuple[k] != x.next);
                    }
                }
            }
        } else if x.tuple.contains_key(op.k) {
            let i = x.tuple[op.k];
            assert forall|k: K| #[trigger] y.tuple.contains_key(k) implies
                y.tuple[k] < y.next && y.stmt.contains_key(y.tuple[k]) && y.stmt[y.tuple[k]].k == k
                && y.stmt[y.tuple[k]].deleted is None by {
                assert(k != op.k);
                assert(x.tuple.contains_key(k));
                assert(x.stmt[x.tuple[k]].k == k);
                assert(x.stmt[i].k == op.k);
                assert(x.tuple[k] != i);
            }
        }
    }
}

proof fn lemma_stmt_op_live(x: SIdx, m: Map<K, V>, d: Set<K>, seq: nat, op: Op)
    requires live_ok(x, m, d),
    ensures live_ok(stmt_op(x, seq, op), apply_op(m, op), d),
{
    let y = stmt_op(x, seq, op);
    let m2 = apply_op(m, op);
    assert forall|k: K| k.edge && !d.contains(k) implies (#[trigger] y.tuple.contains_key(k) <==> val(m2, k) is Some) by {
        lemma_val_apply_op(m, op, k);
        assert(x.tuple.contains_key(k) <==> val(m, k) is Some);
    }
}

proof fn lemma_fold_ok(x: SIdx, seq: nat, rs: Seq<Op>)
    requires sidx_ok(x),
    ensures sidx_ok(stmt_fold(x, seq, rs)),
    decreases rs.len(),
{
    if rs.len() > 0 {
        lemma_fold_ok(x, seq, rs.drop_last());
        lemma_stmt_op_ok(stmt_fold(x, seq, rs.drop_last()), seq, rs.last());
    }
}

proof fn lemma_fold_live(x: SIdx, m: Map<K, V>, d: Set<K>, seq: nat, rs: Seq<Op>)
    requires live_ok(x, m, d),
    ensures live_ok(stmt_fold(x, seq, rs), apply_recs(m, rs), d),
    decreases rs.len(),
{
    if rs.len() > 0 {
        lemma_fold_live(x, m, d, seq, rs.drop_last());
        lemma_stmt_op_live(stmt_fold(x, seq, rs.drop_last()), apply_recs(m, rs.drop_last()), d, seq, rs.last());
    }
}

proof fn lemma_live_mono(x: SIdx, m: Map<K, V>, d1: Set<K>, d2: Set<K>)
    requires live_ok(x, m, d1), d1.subset_of(d2),
    ensures live_ok(x, m, d2),
{
    assert forall|k: K| k.edge && !d2.contains(k) implies (#[trigger] x.tuple.contains_key(k) <==> val(m, k) is Some) by {
        assert(!d1.contains(k));
    }
}

// ------------------------------------------------------------------------------------------------ commit on the layout

/// WriteRevision's records `^IVG.Ledger("rec", seq, 1..n)`, set one by one (Ledger.cls:534-536).
pub open spec fn rec_put(rec: Map<(nat, nat), Op>, seq: nat, rs: Seq<Op>) -> Map<(nat, nat), Op>
    decreases rs.len()
{
    if rs.len() == 0 { rec } else { rec_put(rec, seq, rs.drop_last()).insert((seq, rs.len()), rs.last()) }
}

proof fn lemma_rec_put(rec: Map<(nat, nat), Op>, seq: nat, rs: Seq<Op>, p: (nat, nat))
    ensures
        rec_put(rec, seq, rs).contains_key(p) <==> (rec.contains_key(p) || (p.0 == seq && 1 <= p.1 <= rs.len())),
        (p.0 == seq && 1 <= p.1 <= rs.len()) ==> rec_put(rec, seq, rs)[p] == rs[p.1 - 1],
        !(p.0 == seq && 1 <= p.1 <= rs.len()) && rec.contains_key(p) ==> rec_put(rec, seq, rs)[p] == rec[p],
    decreases rs.len(),
{
    if rs.len() > 0 {
        let rd = rs.drop_last();
        lemma_rec_put(rec, seq, rd, p);
        assert(rs.last() == rs[rs.len() - 1]);
        if p.0 == seq && 1 <= p.1 < rs.len() { assert(rd[p.1 - 1] == rs[p.1 - 1]); }
    }
}

proof fn lemma_rec_put_all(rec: Map<(nat, nat), Op>, seq: nat, rs: Seq<Op>)
    ensures
        forall|p: (nat, nat)| #[trigger] rec_put(rec, seq, rs).contains_key(p) <==>
            (rec.contains_key(p) || (p.0 == seq && 1 <= p.1 <= rs.len())),
        forall|p: (nat, nat)| (p.0 == seq && 1 <= p.1 <= rs.len()) ==> #[trigger] rec_put(rec, seq, rs)[p] == rs[p.1 - 1],
        forall|p: (nat, nat)| !(p.0 == seq && 1 <= p.1 <= rs.len()) && rec.contains_key(p) ==>
            #[trigger] rec_put(rec, seq, rs)[p] == rec[p],
{
    assert forall|p: (nat, nat)| #[trigger] rec_put(rec, seq, rs).contains_key(p) <==>
        (rec.contains_key(p) || (p.0 == seq && 1 <= p.1 <= rs.len())) by { lemma_rec_put(rec, seq, rs, p); }
    assert forall|p: (nat, nat)| (p.0 == seq && 1 <= p.1 <= rs.len()) implies #[trigger] rec_put(rec, seq, rs)[p] == rs[p.1 - 1] by {
        lemma_rec_put(rec, seq, rs, p);
    }
    assert forall|p: (nat, nat)| !(p.0 == seq && 1 <= p.1 <= rs.len()) && rec.contains_key(p) implies
        #[trigger] rec_put(rec, seq, rs)[p] == rec[p] by { lemma_rec_put(rec, seq, rs, p); }
}

/// CommitInTxn step 4-5 (Ledger.cls:500-528) and WriteRevision (Ledger.cls:532-566) on the ledger globals.
pub open spec fn commit_glob(g: Glob, a: CArgs) -> Glob {
    let seq = (g.head + 1) as nat;
    Glob {
        head: seq,
        rec: rec_put(g.rec, seq, a.recs),
        revrow: g.revrow.insert(seq, RevRow { id: a.id, nops: a.recs.len(), key: a.key }),
        id_by_seq: g.id_by_seq.insert(seq, a.id),
        rev_by_id: g.rev_by_id.insert(a.id, seq),
        idem: match a.key { Some(k) => g.idem.insert(k, (seq, a.fp)), None => g.idem },
        sx: stmt_fold(g.sx, seq, a.recs),
    }
}

/// CommitInTxn's checks on the layout (Ledger.cls:440-498): state, `("idem", key)`, `("revById", exp)` and
/// `("idBySeq", head)`, size.
pub open spec fn out2(m: Meta, g: Glob, a: CArgs) -> COut {
    if m.state is Never { COut::Refused(Reason::NotEnabled) }
    else if m.state is Disabled { COut::Refused(Reason::Disabled) }
    else if a.key is Some && g.idem.contains_key(a.key->0) {
        if g.idem[a.key->0].1 == a.fp { COut::Replayed(g.idem[a.key->0].0) } else { COut::Refused(Reason::IdemConflict) }
    }
    else if a.exp is Some && !g.rev_by_id.contains_key(a.exp->0) { COut::Refused(Reason::UnknownHead) }
    else if a.exp is Some && a.exp->0 != g.id_by_seq[g.head] { COut::Refused(Reason::StaleHead) }
    else if a.recs.len() == 0 { COut::Refused(Reason::Empty) }
    else { COut::Applied((g.head + 1) as nat) }
}

pub open spec fn lay_recs(g: Glob, n: nat) -> Seq<Op> {
    Seq::new(g.revrow[n].nops, |j: int| g.rec[(n, (j + 1) as nat)])
}

pub open spec fn lay_rev(g: Glob, n: nat) -> Rev {
    Rev { id: g.id_by_seq[n], recs: lay_recs(g, n), key: g.revrow[n].key }
}

/// The history the layout holds: revision seq i+1 read from its globals and revision row.
pub open spec fn lay_hist(g: Glob) -> Seq<Rev> {
    Seq::new(g.head, |i: int| lay_rev(g, (i + 1) as nat))
}

// ------------------------------------------------------------------------------------------------ layout invariant

pub open spec fn lay_meta(m: Meta, g: Glob) -> bool {
    &&& m.state is Never ==> g.head == 0 && (forall|k: K| !(#[trigger] g.sx.tuple.contains_key(k)))
    &&& !(m.state is Never) ==> g.head >= 1
}

pub open spec fn lay_dom(g: Glob) -> bool {
    &&& forall|n: nat| #[trigger] g.revrow.contains_key(n) <==> 1 <= n <= g.head
    &&& forall|n: nat| #[trigger] g.id_by_seq.contains_key(n) <==> 1 <= n <= g.head
    &&& forall|n: nat, o: nat| #[trigger] g.rec.contains_key((n, o)) <==> (1 <= n <= g.head && 1 <= o <= g.revrow[n].nops)
}

pub open spec fn lay_ids(g: Glob) -> bool {
    &&& forall|n: nat| #![trigger g.id_by_seq[n]] 1 <= n <= g.head ==>
            g.revrow[n].id == g.id_by_seq[n] && g.rev_by_id.contains_key(g.id_by_seq[n]) && g.rev_by_id[g.id_by_seq[n]] == n
    &&& forall|i: Id| #[trigger] g.rev_by_id.contains_key(i) ==>
            1 <= g.rev_by_id[i] <= g.head && g.id_by_seq[g.rev_by_id[i]] == i
}

pub open spec fn lay_idem(g: Glob) -> bool {
    &&& forall|k: IKey| #[trigger] g.idem.contains_key(k) ==>
            1 <= g.idem[k].0 <= g.head && g.revrow[g.idem[k].0].key == Some(k)
    &&& forall|n: nat| #![trigger g.revrow[n]] 1 <= n <= g.head && g.revrow[n].key is Some ==>
            g.idem.contains_key(g.revrow[n].key->0) && g.idem[g.revrow[n].key->0].0 == n
}

/// The layout is coherent: a revision row exists iff its id maps and its records exist; ids and retry keys are
/// bound both ways; statement entries are coherent and, outside d, match the replay of the recorded history.
pub open spec fn layout(m: Meta, g: Glob, d: Set<K>) -> bool {
    &&& lay_meta(m, g)
    &&& lay_dom(g)
    &&& lay_ids(g)
    &&& lay_idem(g)
    &&& sidx_ok(g.sx)
    &&& live_ok(g.sx, replay(lay_hist(g)), d)
}

proof fn lemma_lay_hist_len(g: Glob)
    ensures lay_hist(g).len() == g.head,
{
}

proof fn lemma_lay_hist_sx(g: Glob, sx: SIdx)
    ensures lay_hist(Glob { sx, ..g }) == lay_hist(g),
{
    let g2 = Glob { sx, ..g };
    assert forall|i: int| 0 <= i < g.head implies #[trigger] lay_hist(g2)[i] == lay_hist(g)[i] by {
        assert(lay_recs(g2, (i + 1) as nat) =~= lay_recs(g, (i + 1) as nat));
    }
    assert(lay_hist(g2) =~= lay_hist(g));
}

proof fn lemma_is_rev(g: Glob, e: Id)
    requires lay_dom(g), lay_ids(g),
    ensures g.rev_by_id.contains_key(e) <==> is_rev(lay_hist(g), e),
{
    let h = lay_hist(g);
    if g.rev_by_id.contains_key(e) {
        let n = g.rev_by_id[e];
        assert(g.id_by_seq[n] == e);
        let i = n - 1;
        assert(h[i] == lay_rev(g, n));
        assert(h[i].id == e);
    }
    if is_rev(h, e) {
        let i = choose|i: int| 0 <= i < h.len() && (#[trigger] h[i]).id == e;
        let n = (i + 1) as nat;
        assert(h[i] == lay_rev(g, n));
        assert(g.id_by_seq[n] == e);
        assert(g.rev_by_id.contains_key(g.id_by_seq[n]));
    }
}

/// CommitInTxn's checks on the layout give L1's answer on the history the layout holds.
proof fn lemma_out_matches(m: Meta, g: Glob, d: Set<K>, a: CArgs)
    requires layout(m, g, d),
    ensures
        out2(m, g, a) == out1(m.state, lay_hist(g), g.idem, a.recs, a.key, a.fp, a.exp),
        g.rev_by_id.contains_key(a.id) <==> is_rev(lay_hist(g), a.id),
{
    let h = lay_hist(g);
    lemma_is_rev(g, a.id);
    if a.exp is Some { lemma_is_rev(g, a.exp->0); }
    if !(m.state is Never) {
        assert(h.last() == lay_rev(g, g.head));
        assert(h.last().id == g.id_by_seq[g.head]);
    }
}

proof fn lemma_commit_hist(g: Glob, a: CArgs)
    requires lay_dom(g),
    ensures lay_hist(commit_glob(g, a)) == lay_hist(g).push(Rev { id: a.id, recs: a.recs, key: a.key }),
{
    let g2 = commit_glob(g, a);
    let seq = (g.head + 1) as nat;
    let r = Rev { id: a.id, recs: a.recs, key: a.key };
    lemma_rec_put_all(g.rec, seq, a.recs);
    assert forall|i: int| 0 <= i < g.head implies #[trigger] lay_hist(g2)[i] == lay_hist(g)[i] by {
        let n = (i + 1) as nat;
        assert(n != seq);
        assert(g2.revrow[n] == g.revrow[n]);
        assert forall|j: int| 0 <= j < g.revrow[n].nops implies #[trigger] lay_recs(g2, n)[j] == lay_recs(g, n)[j] by {
            assert(g.rec.contains_key((n, (j + 1) as nat)));
        }
        assert(lay_recs(g2, n) =~= lay_recs(g, n));
    }
    assert forall|j: int| 0 <= j < a.recs.len() implies #[trigger] lay_recs(g2, seq)[j] == a.recs[j] by {}
    assert(lay_recs(g2, seq) =~= a.recs);
    assert(lay_hist(g2)[g.head as int] == r);
    assert(lay_hist(g2) =~= lay_hist(g).push(r));
}

proof fn lemma_commit_dom_ids(g: Glob, a: CArgs)
    requires lay_dom(g), lay_ids(g), !g.rev_by_id.contains_key(a.id),
    ensures lay_dom(commit_glob(g, a)), lay_ids(commit_glob(g, a)),
{
    let g2 = commit_glob(g, a);
    let seq = (g.head + 1) as nat;
    lemma_rec_put_all(g.rec, seq, a.recs);
    assert forall|n: nat, o: nat| #[trigger] g2.rec.contains_key((n, o)) <==> (1 <= n <= g2.head && 1 <= o <= g2.revrow[n].nops) by {
        if n == seq {
            assert(!g.rec.contains_key((n, o)));
        } else if 1 <= n <= g.head {
            assert(g2.revrow[n] == g.revrow[n]);
        } else {
            assert(!g.rec.contains_key((n, o)));
        }
    }
    assert forall|n: nat| #![trigger g2.id_by_seq[n]] 1 <= n <= g2.head implies
        g2.revrow[n].id == g2.id_by_seq[n] && g2.rev_by_id.contains_key(g2.id_by_seq[n]) && g2.rev_by_id[g2.id_by_seq[n]] == n by {
        if n != seq {
            assert(g.rev_by_id.contains_key(g.id_by_seq[n]));
            assert(g.id_by_seq[n] != a.id);
        }
    }
    assert forall|i: Id| #[trigger] g2.rev_by_id.contains_key(i) implies
        1 <= g2.rev_by_id[i] <= g2.head && g2.id_by_seq[g2.rev_by_id[i]] == i by {
        if i != a.id {
            assert(g.rev_by_id.contains_key(i));
            assert(g.rev_by_id[i] != seq);
        }
    }
}

proof fn lemma_commit_idem(g: Glob, a: CArgs)
    requires lay_dom(g), lay_idem(g), a.key is None || !g.idem.contains_key(a.key->0),
    ensures lay_idem(commit_glob(g, a)),
{
    let g2 = commit_glob(g, a);
    let seq = (g.head + 1) as nat;
    assert forall|k: IKey| #[trigger] g2.idem.contains_key(k) implies
        1 <= g2.idem[k].0 <= g2.head && g2.revrow[g2.idem[k].0].key == Some(k) by {
        if a.key != Some(k) {
            assert(g.idem.contains_key(k));
            assert(g.idem[k].0 != seq);
        }
    }
    assert forall|n: nat| #![trigger g2.revrow[n]] 1 <= n <= g2.head && g2.revrow[n].key is Some implies
        g2.idem.contains_key(g2.revrow[n].key->0) && g2.idem[g2.revrow[n].key->0].0 == n by {
        if n != seq {
            assert(g2.revrow[n] == g.revrow[n]);
            let k = g.revrow[n].key->0;
            assert(g.idem.contains_key(k));
            assert(a.key != Some(k));
        }
    }
}

/// A commit that passes CommitInTxn's checks keeps the layout coherent.
proof fn lemma_commit_layout(m: Meta, g: Glob, d: Set<K>, a: CArgs)
    requires
        lay_dom(g), lay_ids(g), lay_idem(g), sidx_ok(g.sx), live_ok(g.sx, replay(lay_hist(g)), d),
        !g.rev_by_id.contains_key(a.id), a.key is None || !g.idem.contains_key(a.key->0),
        !(m.state is Never),
    ensures
        layout(m, commit_glob(g, a), d),
        lay_hist(commit_glob(g, a)) == lay_hist(g).push(Rev { id: a.id, recs: a.recs, key: a.key }),
{
    let g2 = commit_glob(g, a);
    let seq = (g.head + 1) as nat;
    lemma_commit_hist(g, a);
    lemma_commit_dom_ids(g, a);
    lemma_commit_idem(g, a);
    lemma_fold_ok(g.sx, seq, a.recs);
    lemma_replay_push(lay_hist(g), Rev { id: a.id, recs: a.recs, key: a.key });
    lemma_fold_live(g.sx, replay(lay_hist(g)), d, seq, a.recs);
}

// ------------------------------------------------------------------------------------------------ rollback images

/// The rows after a rollback of a transaction whose changeset touched the keys of rs: each touched row gets its
/// before-image back (from pre), every other row stays as other transactions left it.
pub open spec fn restore(rows: Map<K, V>, pre: Map<K, V>, rs: Seq<Op>) -> Map<K, V> {
    Map::new(rows.dom().union(pre.dom()).filter(|k: K| if touches(rs, k) { pre.contains_key(k) } else { rows.contains_key(k) }),
             |k: K| if touches(rs, k) { pre[k] } else { rows[k] })
}

proof fn lemma_val_restore(rows: Map<K, V>, pre: Map<K, V>, rs: Seq<Op>, k: K)
    ensures val(restore(rows, pre, rs), k) == if touches(rs, k) { val(pre, k) } else { val(rows, k) },
{
    let d = rows.dom().union(pre.dom()).filter(|k: K| if touches(rs, k) { pre.contains_key(k) } else { rows.contains_key(k) });
    assert(restore(rows, pre, rs).dom() == d);
    assert(d.contains(k) == (if touches(rs, k) { pre.contains_key(k) } else { rows.contains_key(k) }));
}

proof fn lemma_restore_pre(rows: Map<K, V>, rs: Seq<Op>)
    ensures restore(apply_recs(rows, rs), rows, rs) == rows,
{
    let r2 = restore(apply_recs(rows, rs), rows, rs);
    assert forall|k: K| #[trigger] val(r2, k) == val(rows, k) by {
        lemma_val_restore(apply_recs(rows, rs), rows, rs, k);
        if !touches(rs, k) { lemma_apply_untouched(rows, rs, k); }
    }
    lemma_val_ext(r2, rows);
}

// ------------------------------------------------------------------------------------------------ guard and stats

pub open spec fn strict_on(m: Meta) -> bool { m.state is Enabled && m.strict }

/// Whether the strict-mode guard refuses a governed write by writer w.
pub open spec fn refuses(s: LS2, w: Wr) -> bool {
    if cfg!(feature = "control_f1108_unguarded_bulk_delete") && w is BulkDeleteAdj {
        // F-1108 (as built): bulk_delete_adjacency calls no guard (nodes_edges.py:2301-2339)
        false
    } else if cfg!(feature = "control_f0801_fail_open") {
        // F-0801 / LED-B11.3 (as built): a probe that cannot run reads as never-enabled (guard.py:55-56)
        !s.probe_fails && strict_on(s.meta)
    } else if cfg!(feature = "control_f0801_ttl_cache") {
        // F-0801 (as built): within its 5 s TTL the guard answers from the meta it cached (guard.py:38-41)
        match s.gcache { Some(c) => strict_on(c), None => s.probe_fails || strict_on(s.meta) }
    } else {
        // reviewed: read strict mode at write time, fail closed
        s.probe_fails || strict_on(s.meta)
    }
}

/// What the guard's probe caches (as built: ABSENT when the probe fails, guard.py:55-58).
pub open spec fn probe_view(s: LS2) -> Meta {
    if s.probe_fails { Meta { state: LState::Never, strict: false } } else { s.meta }
}

/// Bump's save. Reviewed: one atomic increment of its own counter. Control F-C1101 (as built): %Save of the whole
/// row from the copy %OpenId opened, which waits for the row lock a caller transaction holds (LedgerStats.cls:65-88).
pub open spec fn bump_save(cur: Stats, copy: Stats) -> Stats {
    if cfg!(feature = "control_fc1101_stats_whole_row") { Stats { ok: copy.ok, rej: copy.rej + 1 } }
    else { Stats { ok: cur.ok, rej: cur.rej + 1 } }
}

pub open spec fn bump_may_save(s: LS2) -> bool {
    if cfg!(feature = "control_fc1101_stats_whole_row") { s.txn is None } else { true }
}

// ------------------------------------------------------------------------------------------------ the machine

pub open spec fn glob0() -> Glob {
    Glob {
        head: 0, rec: Map::empty(), revrow: Map::empty(), id_by_seq: Map::empty(), rev_by_id: Map::empty(),
        idem: Map::empty(), sx: SIdx { stmt: Map::empty(), tuple: Map::empty(), next: 1 },
    }
}

pub open spec fn init2(s: LS2) -> bool {
    &&& s.meta == Meta { state: LState::Never, strict: false }
    &&& s.g == glob0()
    &&& s.stats == Stats { ok: 0, rej: 0 }
    &&& s.rows == Map::<K, V>::empty()
    &&& s.txn is None
    &&& s.gcache is None
    &&& !s.probe_fails
    &&& s.copies == Map::<nat, Stats>::empty()
    &&& s.drift == Set::<K>::empty()
}

pub open spec fn genesis_args(recs: Seq<Op>, id: Id) -> CArgs { CArgs { recs, key: None, fp: 0, exp: None, id } }

pub open spec fn applied(s: LS2, a: CArgs) -> LS2 {
    LS2 { g: commit_glob(s.g, a), stats: Stats { ok: s.stats.ok + 1, ..s.stats }, rows: apply_recs(s.rows, a.recs), ..s }
}

pub open spec fn write_ok(s: LS2, w: Wr, k: K, v: Option<V>) -> bool {
    &&& w is BulkDeleteAdj ==> s.txn is None && v is None && k.edge
    &&& s.txn is Some ==> !touches(s.txn->0.a.recs, k)
}

pub open spec fn engine_write(s: LS2, w: Wr, k: K, v: Option<V>) -> LS2 {
    LS2 {
        rows: apply_op(s.rows, Op { k, v }),
        drift: s.drift.insert(k),
        g: if w is BulkDeleteAdj { Glob { sx: SIdx { tuple: s.g.sx.tuple.remove(k), ..s.g.sx }, ..s.g } } else { s.g },
        ..s
    }
}

pub open spec fn step2(s: LS2, l: L2Label, t: LS2) -> bool {
    match l {
        L2Label::Enable { strict, id, recs, busy } =>
            if busy { t == s } else {
                &&& s.txn is None
                &&& match s.meta.state {
                        LState::Never => apply_recs(Map::empty(), recs) == s.rows && t == LS2 {
                            meta: Meta { state: LState::Enabled, strict },
                            g: commit_glob(s.g, genesis_args(recs, id)),
                            stats: Stats { ok: s.stats.ok + 1, ..s.stats },
                            drift: Set::empty(),
                            ..s },
                        LState::Disabled => t == LS2 { meta: Meta { state: LState::Enabled, strict }, ..s },
                        LState::Enabled => t == s,
                    }
            },
        L2Label::Disable =>
            s.txn is None && t == if s.meta.state is Enabled { LS2 { meta: Meta { state: LState::Disabled, ..s.meta }, ..s } } else { s },
        L2Label::SetStrict { on } =>
            t == if s.meta.state is Never { s } else { LS2 { meta: Meta { strict: on, ..s.meta }, ..s } },
        L2Label::Commit { a, out } =>
            if out == COut::Refused(Reason::Busy) { t == s } else {
                &&& s.txn is None
                &&& out == out2(s.meta, s.g, a)
                &&& out is Applied ==> !s.g.rev_by_id.contains_key(a.id)
                &&& t == if out is Applied { applied(s, a) } else { s }
            },
        L2Label::CommitNested { a } => {
            &&& s.txn is None
            &&& out2(s.meta, s.g, a) is Applied
            &&& !s.g.rev_by_id.contains_key(a.id)
            &&& t == LS2 { txn: Some(Txn { pre: s.g, pre_ok: s.stats.ok, pre_rows: s.rows, a }), ..applied(s, a) }
        },
        L2Label::CallerEnd { keep, a, seq } => {
            &&& s.txn is Some && s.txn->0.a == a && seq == s.txn->0.pre.head + 1
            &&& t == if keep { LS2 { txn: None, ..s } } else {
                    LS2 { g: s.txn->0.pre, stats: Stats { ok: s.txn->0.pre_ok, ..s.stats },
                          rows: restore(s.rows, s.txn->0.pre_rows, s.txn->0.a.recs), txn: None, ..s } }
        },
        L2Label::GuardProbe => t == LS2 { gcache: Some(probe_view(s)), ..s },
        L2Label::ProbeFails { on } => t == LS2 { probe_fails: on, ..s },
        L2Label::EngineWrite { w, k, v, landed } => {
            &&& landed == !refuses(s, w)
            &&& landed ==> write_ok(s, w, k, v)
            &&& t == if landed { engine_write(s, w, k, v) } else { s }
        },
        L2Label::BumpRead { p } => t == LS2 { copies: s.copies.insert(p, s.stats), ..s },
        L2Label::BumpSave { p } =>
            s.copies.contains_key(p) && bump_may_save(s)
            && t == LS2 { stats: bump_save(s.stats, s.copies[p]), copies: s.copies.remove(p), ..s },
    }
}

// ------------------------------------------------------------------------------------------------ the invariant

pub open spec fn txn_ok(s: LS2, x: Txn) -> bool {
    &&& layout(s.meta, x.pre, s.drift)
    &&& x.pre_ok == x.pre.head
    &&& s.meta.state is Enabled
    &&& out2(s.meta, x.pre, x.a) == COut::Applied((x.pre.head + 1) as nat)
    &&& !x.pre.rev_by_id.contains_key(x.a.id)
    &&& s.g == commit_glob(x.pre, x.a)
    &&& forall|k: K| touches(x.a.recs, k) ==>
            #[trigger] val(s.rows, k) == val(apply_recs(restore(s.rows, x.pre_rows, x.a.recs), x.a.recs), k)
}

pub open spec fn inv2(s: LS2) -> bool {
    &&& layout(s.meta, s.g, s.drift)
    &&& s.stats.ok == s.g.head
    &&& s.txn is Some ==> txn_ok(s, s.txn->0)
}

pub struct L2;

impl Contract for L2 {
    type S = LS2;
    type L = L2Label;
    open spec fn init(s: LS2) -> bool { init2(s) }
    /// Steps from states satisfying the invariant; `theorem_raw_executions_refine` shows every execution of `step2`
    /// from `init2` is an execution of this contract.
    open spec fn next(s: LS2, l: L2Label, t: LS2) -> bool { inv2(s) && step2(s, l, t) }
}

/// The unconstrained step relation (no invariant in the guard).
pub struct Raw2;

impl Contract for Raw2 {
    type S = LS2;
    type L = L2Label;
    open spec fn init(s: LS2) -> bool { init2(s) }
    open spec fn next(s: LS2, l: L2Label, t: LS2) -> bool { step2(s, l, t) }
}

// ------------------------------------------------------------------------------------------------ the abstraction

/// The committed ledger globals, rows and commit counter: an open nested commit is not yet visible to L1.
pub open spec fn cg(s: LS2) -> Glob { match s.txn { Some(x) => x.pre, None => s.g } }
pub open spec fn crows(s: LS2) -> Map<K, V> { match s.txn { Some(x) => restore(s.rows, x.pre_rows, x.a.recs), None => s.rows } }
pub open spec fn cok(s: LS2) -> nat { match s.txn { Some(x) => x.pre_ok, None => s.stats.ok } }

pub open spec fn abs11(s: LS2) -> S1 {
    S1 { st: s.meta.state, strict: s.meta.strict, hist: lay_hist(cg(s)), idem: cg(s).idem, rows: crows(s),
         drift: s.drift, ok: cok(s) }
}

pub open spec fn lab11(l: L2Label) -> Option<L1Label> {
    match l {
        L2Label::Enable { strict, id, recs, busy } => Some(L1Label::Enable { strict, id, recs, busy }),
        L2Label::Disable => Some(L1Label::Disable),
        L2Label::SetStrict { on } => Some(L1Label::SetStrict { on }),
        L2Label::Commit { a, out } =>
            Some(L1Label::Commit { recs: a.recs, key: a.key, fp: a.fp, exp: a.exp, id: a.id, out }),
        L2Label::CommitNested { a } => None,
        L2Label::CallerEnd { keep, a, seq } => if keep {
            Some(L1Label::Commit { recs: a.recs, key: a.key, fp: a.fp, exp: a.exp, id: a.id, out: COut::Applied(seq) })
        } else { None },
        L2Label::GuardProbe => None,
        L2Label::ProbeFails { on } => None,
        L2Label::EngineWrite { w, k, v, landed } =>
            if landed { Some(L1Label::GovWrite { k, v }) } else { Some(L1Label::GovRefused) },
        L2Label::BumpRead { p } => None,
        L2Label::BumpSave { p } => None,
    }
}

// ------------------------------------------------------------------------------------------------ refinement, per step

proof fn lemma_genesis(s: LS2, strict: bool, id: Id, recs: Seq<Op>)
    requires inv2(s), s.txn is None, s.meta.state is Never,
    ensures
        layout(Meta { state: LState::Enabled, strict }, commit_glob(s.g, genesis_args(recs, id)), Set::empty()),
        lay_hist(commit_glob(s.g, genesis_args(recs, id))) == seq![Rev { id, recs, key: None }],
        commit_glob(s.g, genesis_args(recs, id)).idem == s.g.idem,
        s.g.head == 0,
{
    let g = s.g;
    let a = genesis_args(recs, id);
    let r = Rev { id, recs, key: None };
    assert(lay_hist(g) =~= Seq::<Rev>::empty());
    assert(replay(lay_hist(g)) == Map::<K, V>::empty());
    assert forall|i: Id| !g.rev_by_id.contains_key(i) by {
        if g.rev_by_id.contains_key(i) { assert(1 <= g.rev_by_id[i] <= g.head); }
    }
    assert(live_ok(g.sx, replay(lay_hist(g)), Set::<K>::empty())) by {
        assert forall|k: K| k.edge && !Set::<K>::empty().contains(k) implies
            (#[trigger] g.sx.tuple.contains_key(k) <==> val(replay(lay_hist(g)), k) is Some) by {}
    }
    lemma_commit_layout(Meta { state: LState::Enabled, strict }, g, Set::empty(), a);
    assert(Seq::<Rev>::empty().push(r) =~= seq![r]);
}

proof fn lemma_commit_refines(s: LS2, a: CArgs, out: COut)
    requires inv2(s), step2(s, L2Label::Commit { a, out }, applied(s, a)), out is Applied,
    ensures
        L1::next(abs11(s), L1Label::Commit { recs: a.recs, key: a.key, fp: a.fp, exp: a.exp, id: a.id, out }, abs11(applied(s, a))),
        inv2(applied(s, a)),
{
    let t = applied(s, a);
    lemma_out_matches(s.meta, s.g, s.drift, a);
    lemma_commit_layout(s.meta, s.g, s.drift, a);
    lemma_lay_hist_len(s.g);
    assert(abs11(t) == commit1(abs11(s), a.recs, a.key, a.fp, a.id));
}

proof fn lemma_nested_refines(s: LS2, a: CArgs, t: LS2)
    requires inv2(s), step2(s, L2Label::CommitNested { a }, t),
    ensures abs11(t) == abs11(s), inv2(t),
{
    let x = t.txn->0;
    lemma_out_matches(s.meta, s.g, s.drift, a);
    lemma_commit_layout(s.meta, s.g, s.drift, a);
    lemma_restore_pre(s.rows, a.recs);
    assert(crows(t) == s.rows);
    assert forall|k: K| touches(a.recs, k) implies
        #[trigger] val(t.rows, k) == val(apply_recs(restore(t.rows, x.pre_rows, a.recs), a.recs), k) by {}
    assert(txn_ok(t, x));
}

proof fn lemma_caller_end_refines(s: LS2, keep: bool, a: CArgs, seq: nat, t: LS2)
    requires inv2(s), step2(s, L2Label::CallerEnd { keep, a, seq }, t),
    ensures step_or_stutter::<L1>(abs11(s), lab11(L2Label::CallerEnd { keep, a, seq }), abs11(t)), inv2(t),
{
    let x = s.txn->0;
    if keep {
        lemma_out_matches(s.meta, x.pre, s.drift, a);
        lemma_commit_hist(x.pre, a);
        lemma_lay_hist_len(x.pre);
        let cr = restore(s.rows, x.pre_rows, a.recs);
        assert forall|k: K| #[trigger] val(s.rows, k) == val(apply_recs(cr, a.recs), k) by {
            if !touches(a.recs, k) {
                lemma_apply_untouched(cr, a.recs, k);
                lemma_val_restore(s.rows, x.pre_rows, a.recs, k);
            }
        }
        lemma_val_ext(s.rows, apply_recs(cr, a.recs));
        assert(abs11(t) == commit1(abs11(s), a.recs, a.key, a.fp, a.id));
    } else {
        assert(abs11(t) == abs11(s));
    }
}

proof fn lemma_engine_write_refines(s: LS2, w: Wr, k: K, v: Option<V>)
    requires inv2(s), step2(s, L2Label::EngineWrite { w, k, v, landed: true }, engine_write(s, w, k, v)),
    ensures
        L1::next(abs11(s), L1Label::GovWrite { k, v }, abs11(engine_write(s, w, k, v))),
        inv2(engine_write(s, w, k, v)),
{
    let t = engine_write(s, w, k, v);
    let op = Op { k, v };
    // the guard let the write through: strict mode is off (the controls fail here)
    assert(!strict_on(s.meta));
    // the ledger globals' history is unchanged (bulk delete changes only the statement entries)
    if w is BulkDeleteAdj {
        lemma_lay_hist_sx(s.g, t.g.sx);
        let x = t.g.sx;
        assert(sidx_ok(x)) by {
            assert forall|k2: K| #[trigger] x.tuple.contains_key(k2) implies
                x.tuple[k2] < x.next && x.stmt.contains_key(x.tuple[k2]) && x.stmt[x.tuple[k2]].k == k2
                && x.stmt[x.tuple[k2]].deleted is None by {
                assert(s.g.sx.tuple.contains_key(k2));
            }
        }
        assert(live_ok(x, replay(lay_hist(t.g)), t.drift)) by {
            assert forall|k2: K| k2.edge && !t.drift.contains(k2) implies
                (#[trigger] x.tuple.contains_key(k2) <==> val(replay(lay_hist(t.g)), k2) is Some) by {
                assert(s.g.sx.tuple.contains_key(k2) <==> val(replay(lay_hist(s.g)), k2) is Some);
            }
        }
    } else {
        lemma_live_mono(s.g.sx, replay(lay_hist(s.g)), s.drift, t.drift);
    }
    match s.txn {
        None => {
            assert(abs11(t) == S1 { rows: apply_op(abs11(s).rows, op), drift: abs11(s).drift.insert(k), ..abs11(s) });
        }
        Some(x) => {
            assert(!(w is BulkDeleteAdj));
            assert(!touches(x.a.recs, k));
            let rt = restore(t.rows, x.pre_rows, x.a.recs);
            let rs0 = restore(s.rows, x.pre_rows, x.a.recs);
            assert forall|k2: K| #[trigger] val(rt, k2) == val(apply_op(rs0, op), k2) by {
                lemma_val_restore(t.rows, x.pre_rows, x.a.recs, k2);
                lemma_val_restore(s.rows, x.pre_rows, x.a.recs, k2);
                lemma_val_apply_op(s.rows, op, k2);
                lemma_val_apply_op(rs0, op, k2);
            }
            lemma_val_ext(rt, apply_op(rs0, op));
            assert(abs11(t) == S1 { rows: apply_op(abs11(s).rows, op), drift: abs11(s).drift.insert(k), ..abs11(s) });
            lemma_live_mono(x.pre.sx, replay(lay_hist(x.pre)), s.drift, t.drift);
            assert forall|k2: K| touches(x.a.recs, k2) implies
                #[trigger] val(t.rows, k2) == val(apply_recs(rt, x.a.recs), k2) by {
                lemma_val_apply_op(s.rows, op, k2);
                lemma_val_restore(t.rows, x.pre_rows, x.a.recs, k2);
                lemma_val_restore(s.rows, x.pre_rows, x.a.recs, k2);
                lemma_apply_local(rt, rs0, x.a.recs, k2);
            }
            assert(txn_ok(t, x));
        }
    }
}

proof fn lemma_step_refines(s: LS2, l: L2Label, t: LS2)
    requires inv2(s), step2(s, l, t),
    ensures step_or_stutter::<L1>(abs11(s), lab11(l), abs11(t)),
{
    match l {
        L2Label::Enable { strict, id, recs, busy } => {
            if !busy && s.meta.state is Never {
                lemma_genesis(s, strict, id, recs);
                assert(abs11(t) == S1 { st: LState::Enabled, strict, hist: seq![Rev { id, recs, key: None }],
                    drift: Set::empty(), ok: abs11(s).ok + 1, ..abs11(s) });
            }
        }
        L2Label::Disable => {}
        L2Label::SetStrict { on } => {}
        L2Label::Commit { a, out } => {
            if out != COut::Refused(Reason::Busy) {
                lemma_out_matches(s.meta, s.g, s.drift, a);
                if out is Applied { lemma_commit_refines(s, a, out); }
            }
        }
        L2Label::CommitNested { a } => { lemma_nested_refines(s, a, t); }
        L2Label::CallerEnd { keep, a, seq } => { lemma_caller_end_refines(s, keep, a, seq, t); }
        L2Label::GuardProbe => {}
        L2Label::ProbeFails { on } => {}
        L2Label::EngineWrite { w, k, v, landed } => {
            if landed { lemma_engine_write_refines(s, w, k, v); }
        }
        L2Label::BumpRead { p } => {}
        L2Label::BumpSave { p } => {
            // reviewed: the save changes only its own counter (control F-C1101 fails here)
            assert(abs11(t) == abs11(s));
        }
    }
}

proof fn lemma_step_inv(s: LS2, l: L2Label, t: LS2)
    requires inv2(s), step2(s, l, t),
    ensures inv2(t),
{
    match l {
        L2Label::Enable { strict, id, recs, busy } => {
            if !busy && s.meta.state is Never { lemma_genesis(s, strict, id, recs); }
        }
        L2Label::Disable => {}
        L2Label::SetStrict { on } => {
            if let Some(x) = s.txn { assert(txn_ok(t, x)); }
        }
        L2Label::Commit { a, out } => {
            if out != COut::Refused(Reason::Busy) && out is Applied { lemma_commit_refines(s, a, out); }
        }
        L2Label::CommitNested { a } => { lemma_nested_refines(s, a, t); }
        L2Label::CallerEnd { keep, a, seq } => { lemma_caller_end_refines(s, keep, a, seq, t); }
        L2Label::GuardProbe => { if let Some(x) = s.txn { assert(txn_ok(t, x)); } }
        L2Label::ProbeFails { on } => { if let Some(x) = s.txn { assert(txn_ok(t, x)); } }
        L2Label::EngineWrite { w, k, v, landed } => {
            if landed { lemma_engine_write_refines(s, w, k, v); }
        }
        L2Label::BumpRead { p } => { if let Some(x) = s.txn { assert(txn_ok(t, x)); } }
        L2Label::BumpSave { p } => {
            // reviewed: the commit counter still equals the head (control F-C1101 fails here)
            assert(t.stats.ok == t.g.head);
            if let Some(x) = s.txn { assert(txn_ok(t, x)); }
        }
    }
}

impl Refines<L1> for L2 {
    open spec fn abs(s: LS2) -> S1 { abs11(s) }
    open spec fn lab(l: L2Label) -> Option<L1Label> { lab11(l) }

    proof fn init_refines(s: LS2) {
        assert(lay_hist(s.g) =~= Seq::<Rev>::empty());
    }

    proof fn step_refines(s: LS2, l: L2Label, t: LS2) {
        lemma_step_refines(s, l, t);
    }
}

impl SafeContract for L2 {
    open spec fn inv(s: LS2) -> bool { inv2(s) }

    proof fn init_safe(s: LS2) {
        assert(lay_hist(s.g) =~= Seq::<Rev>::empty());
        assert(replay(lay_hist(s.g)) == Map::<K, V>::empty());
    }

    proof fn step_safe(s: LS2, l: L2Label, t: LS2) {
        lemma_step_inv(s, l, t);
    }
}

// ------------------------------------------------------------------------------------------------ theorems

proof fn lemma_raw_inv_at(states: Seq<LS2>, labels: Seq<L2Label>, k: int)
    requires execution::<Raw2>(states, labels), 0 <= k < states.len(),
    ensures inv2(states[k]),
    decreases k,
{
    if k == 0 { L2::init_safe(states[0]); } else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step_inv(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, is an execution of the L2
/// contract, and its abstraction is an L1 execution (each step one L1 step or a stutter) whose every state satisfies
/// L1's business invariants.
pub proof fn theorem_raw_executions_refine(states: Seq<LS2>, labels: Seq<L2Label>)
    requires execution::<Raw2>(states, labels),
    ensures
        execution::<L2>(states, labels),
        abstract_execution::<L1>(Seq::new(states.len(), |i: int| abs11(states[i])),
                                 Seq::new(labels.len(), |i: int| lab11(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv2(#[trigger] states[i]) && inv1(abs11(states[i])),
{
    assert forall|i: int| 0 <= i < states.len() implies inv2(#[trigger] states[i]) by {
        lemma_raw_inv_at(states, labels, i);
    }
    assert(execution::<L2>(states, labels));
    trace_refines::<L2, L1>(states, labels);
    refinement_preserves_safety::<L2, L1>(states, labels);
    let ps = Seq::new(states.len(), |i: int| abs11(states[i]));
    let pl = Seq::new(labels.len(), |i: int| lab11(labels[i]));
    assert(ps =~= Seq::new(states.len(), |i: int| <L2 as Refines<L1>>::abs(states[i])));
    assert(pl =~= Seq::new(labels.len(), |i: int| <L2 as Refines<L1>>::lab(labels[i])));
}

/// On the layout: a revision row exists iff its id maps exist and iff its records `("rec", seq, 1..OpCount)` exist;
/// no record exists for a seq above the head. Together with `theorem_raw_executions_refine` and L1's
/// `theorem_revision_iff_recorded`, this is FR-047 for the reviewed model.
pub proof fn theorem_layout_revision_iff_records(s: LS2, n: nat)
    requires inv2(s),
    ensures
        s.g.revrow.contains_key(n) <==> s.g.id_by_seq.contains_key(n),
        s.g.revrow.contains_key(n) <==> (n >= 1 && s.g.rec.contains_key((n, 1)) || n >= 1 && n <= s.g.head && s.g.revrow[n].nops == 0),
        n > s.g.head ==> forall|o: nat| !(#[trigger] s.g.rec.contains_key((n, o))),
{
}

/// The live statement index matches the recorded history: outside the keys written around the ledger, an edge has a
/// `("tuple", ...)` entry iff it is live in the replay of the revisions, and that entry names its open statement.
pub proof fn theorem_statements_match_records(s: LS2, k: K)
    requires inv2(s), k.edge, !s.drift.contains(k),
    ensures
        s.g.sx.tuple.contains_key(k) <==> val(replay(lay_hist(s.g)), k) is Some,
        s.g.sx.tuple.contains_key(k) ==> s.g.sx.stmt[s.g.sx.tuple[k]].k == k && s.g.sx.stmt[s.g.sx.tuple[k]].deleted is None,
{
}

} // verus!
