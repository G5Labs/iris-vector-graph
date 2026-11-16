// IVG ledger erasure, redaction and replay — Verus model (initial uplift, 2026-11-13).
//
// Product baseline 3eaa79cf. Bindings (L3) are listed in ../../coverage.md and in the
// comments that name a product operation. This file is a model and a transcription;
// it does not verify the product's ObjectScript or Python bodies.
//
// Layers
//   L1  business rules from ADR-0004, ADR-0013, spec 256 (spec.md, plan.md) and CONTEXT.md.
//   L2  the as-built mechanism of Graph.KG.LedgerRedact / Ledger / Eraser / replay.py.
//   Refinement lemmas connect L2 to L1 and name every premise they need.
//
// Run:  $VERUS_BIN redaction.rs --crate-type=lib --num-threads 8
use vstd::prelude::*;

verus! {

// ============================================================================ identifiers

pub type Id = Seq<char>;

/// LedgerRedact.HasPrefix: $Extract(id, 1, $Length(m)) = m
pub open spec fn has_prefix(id: Id, m: Id) -> bool {
    m.len() <= id.len() && id.subrange(0, m.len() as int) == m
}

/// The tail test in LedgerRedact.MatchString:
/// $Extract(p, ($Length(p) - $Length(sep)) + 1, *) = sep
pub open spec fn ends_with(p: Id, sep: Id) -> bool {
    sep.len() <= p.len() && p.subrange(p.len() - sep.len(), p.len() as int) == sep
}

/// LedgerRedact.MatchString(prefix, separator)
pub open spec fn match_string(prefix: Id, sep: Id) -> Id {
    if prefix.len() == 0 {
        Seq::empty()
    } else if ends_with(prefix, sep) {
        prefix
    } else {
        prefix + sep
    }
}

/// L1 (spec 256 US1, CONTEXT.md "Redaction"): a prefix target selects exactly the ids that start
/// with the prefix followed by the separator. Proved: every id the match string selects carries
/// the separator right after the prefix (so "acme" never selects "acme-health|...").
pub proof fn lemma_match_string_has_separator_boundary(prefix: Id, sep: Id, id: Id)
    requires
        prefix.len() > 0,
        sep.len() > 0,
        !ends_with(prefix, sep),
        has_prefix(id, match_string(prefix, sep)),
    ensures
        has_prefix(id, prefix),
        id.subrange(prefix.len() as int, (prefix.len() + sep.len()) as int) == sep,
{
    let m = prefix + sep;
    assert(match_string(prefix, sep) == m);
    assert(id.subrange(0, m.len() as int) == m);
    assert(id.subrange(0, prefix.len() as int) =~= m.subrange(0, prefix.len() as int));
    assert(m.subrange(0, prefix.len() as int) =~= prefix);
    assert(id.subrange(prefix.len() as int, (prefix.len() + sep.len()) as int)
        =~= m.subrange(prefix.len() as int, m.len() as int));
    assert(m.subrange(prefix.len() as int, m.len() as int) =~= sep);
}

/// A prefix that already ends with the separator is the same target as without it.
pub proof fn lemma_match_string_not_doubled(prefix: Id, sep: Id)
    requires
        prefix.len() > 0,
        sep.len() > 0,
        !ends_with(prefix, sep),
    ensures
        match_string(prefix + sep, sep) == match_string(prefix, sep),
{
    let p2 = prefix + sep;
    assert(p2.subrange(p2.len() - sep.len(), p2.len() as int) =~= sep);
    assert(ends_with(p2, sep));
}

/// The concrete case from spec 256 / the e2e fixture: "acme" does not select "acme-health|1".
pub proof fn lemma_acme_does_not_select_acme_health() {
    let acme: Id = seq!['a', 'c', 'm', 'e'];
    let bar: Id = seq!['|'];
    let id: Id = seq!['a', 'c', 'm', 'e', '-', 'h', '|', '1'];
    assert(!ends_with(acme, bar)) by {
        assert(acme.subrange(3, 4)[0] == 'e');
        assert(bar[0] == '|');
    }
    assert(match_string(acme, bar) =~= seq!['a', 'c', 'm', 'e', '|']);
    assert(id.subrange(0, 5) =~= seq!['a', 'c', 'm', 'e', '-']);
    assert(id.subrange(0, 5)[4] != match_string(acme, bar)[4]);
    assert(!has_prefix(id, match_string(acme, bar)));
}

// ============================================================================ records

/// The op of a ledger record (Graph.KG.LedgerApply.Rec, LedgerRedact.Final).
pub enum Op {
    CreateNode,
    DeleteNode,
    AddLabel,
    RemoveLabel,
    SetProp,
    RemoveProp,
    CreateRel,
    DeleteRel,
    SetQual,
    RemoveQual,
    CreateTemporal,
    /// the record of a redaction revision: $LB("redact", "revision", seq, ...)
    Redact,
}

pub open spec fn is_node_op(op: Op) -> bool {
    match op {
        Op::CreateNode | Op::DeleteNode | Op::AddLabel | Op::RemoveLabel | Op::SetProp
        | Op::RemoveProp => true,
        _ => false,
    }
}

pub open spec fn is_qual_op(op: Op) -> bool {
    op == Op::SetQual || op == Op::RemoveQual
}

/// A record that still holds its content: $LB(op, kind, entityId, attr, prior, new, graph, flags).
pub struct Live {
    pub op: Op,
    /// node id (node records), statement id (relationship records)
    pub id: Id,
    pub stmt: nat,
    /// endpoints carried in the record's tuple JSON (create_rel, delete_rel, create_temporal_edge);
    /// None when the tuple cannot be parsed (TupleEnds answers "")
    pub ends: Option<(Id, Id)>,
    /// field 7; "" for the default graph. Node records always carry "" (LedgerApply: graph-blind).
    pub graph: Id,
    /// attr, prior, new and flags: everything else the record holds
    pub payload: int,
    pub flags: int,
}

/// $LB("redacted", sha256(CanonicalRecord), flags, op, entityKind)
pub enum Rec {
    Live(Live),
    Tomb { digest: int, op: Op, flags: int },
}

/// sha256 of Graph.KG.Ledger.CanonicalRecord(seq, ordinal) — the canonical JSON includes seq and
/// ordinal, so the digest depends on the record's position as well as its content. Uninterpreted:
/// the model needs only that it is a function of the original record and its position.
pub uninterp spec fn digest_of(l: Live, pos: nat) -> int;

pub open spec fn tomb(l: Live, pos: nat) -> Rec {
    Rec::Tomb { digest: digest_of(l, pos), op: l.op, flags: l.flags }
}

// ============================================================================ targets and matching

/// A redaction target: a graph name ("" is the default graph) and a match string (possibly "").
pub struct Target {
    pub g: Id,
    pub m: Id,
}

pub enum Tri {
    Yes,
    No,
    Unknown,
}

/// What LedgerRedact.Matches can know about a qualifier record's statement:
///   redacting — ^IVG.Ledger("redacting","stmt",id): statements whose create/delete this run tombstoned
///   ends      — ^||IVG.RedactStmt (PrePass over create_rel/delete_rel records of the target graph)
///               merged with the live ^IVG.Ledger("stmt") map
pub struct Know {
    pub redacting: Set<nat>,
    pub ends: Map<nat, (Id, Id)>,
}

pub open spec fn ends_hit(e: (Id, Id), m: Id) -> bool {
    has_prefix(e.0, m) || has_prefix(e.1, m)
}

/// LedgerRedact.Matches (1 / 0 / -1).
pub open spec fn matches(r: Rec, t: Target, k: Know) -> Tri {
    match r {
        Rec::Tomb { .. } => Tri::No,
        Rec::Live(l) => {
            if l.op == Op::Redact {
                Tri::No
            } else if l.graph != t.g {
                Tri::No
            } else if t.m.len() == 0 {
                Tri::Yes
            } else if is_node_op(l.op) {
                if has_prefix(l.id, t.m) { Tri::Yes } else { Tri::No }
            } else if l.op == Op::CreateRel || l.op == Op::DeleteRel || l.op == Op::CreateTemporal {
                match l.ends {
                    Some(e) => if ends_hit(e, t.m) { Tri::Yes } else { Tri::No },
                    None => Tri::Unknown,
                }
            } else if k.redacting.contains(l.stmt) {
                Tri::Yes
            } else if k.ends.contains_key(l.stmt) {
                if ends_hit(k.ends[l.stmt], t.m) { Tri::Yes } else { Tri::No }
            } else {
                Tri::Unknown
            }
        },
    }
}

/// L1 (spec 256 plan "Target"): the record describes the target's content. `truth` gives every
/// statement's real endpoints (fixed when ^IVG.Ledger("stmt") allocated it).
pub open spec fn belongs(r: Rec, t: Target, truth: Map<nat, (Id, Id)>) -> bool {
    matches(r, t, Know { redacting: Set::empty(), ends: truth }) == Tri::Yes
}

/// Premise P_ends: what the redaction can know agrees with the truth, and covers every qualifier
/// record of the target graph. `redacting` only holds statements of the target.
pub open spec fn agrees(t: Target, k: Know, truth: Map<nat, (Id, Id)>) -> bool {
    &&& forall|x: nat| #[trigger] k.ends.contains_key(x) ==> truth.contains_key(x) && k.ends[x] == truth[x]
    &&& forall|x: nat| #[trigger] k.redacting.contains(x) ==> truth.contains_key(x) && ends_hit(truth[x], t.m)
}

pub open spec fn knows_enough(recs: Seq<Rec>, t: Target, k: Know, truth: Map<nat, (Id, Id)>) -> bool {
    &&& agrees(t, k, truth)
    &&& forall|i: int| 0 <= i < recs.len() ==> #[trigger] qual_needs(recs[i], t, k)
    &&& forall|i: int| 0 <= i < recs.len() ==> #[trigger] tuple_parses(recs[i])
}

pub open spec fn qual_needs(r: Rec, t: Target, k: Know) -> bool {
    match r {
        Rec::Live(l) => (is_qual_op(l.op) && l.graph == t.g && t.m.len() > 0) ==> (k.redacting.contains(l.stmt)
            || k.ends.contains_key(l.stmt)),
        Rec::Tomb { .. } => true,
    }
}

pub open spec fn tuple_parses(r: Rec) -> bool {
    match r {
        Rec::Live(l) => (l.op == Op::CreateRel || l.op == Op::DeleteRel || l.op == Op::CreateTemporal) ==> l.ends.is_some(),
        Rec::Tomb { .. } => true,
    }
}

/// Under P_ends the as-built test agrees with L1 and never answers Unknown.
pub proof fn lemma_matches_refines_belongs(r: Rec, t: Target, k: Know, truth: Map<nat, (Id, Id)>)
    requires
        agrees(t, k, truth),
        qual_needs(r, t, k),
        tuple_parses(r),
        // every statement of a qualifier record of the target graph is in the truth map
        match r { Rec::Live(l) => is_qual_op(l.op) ==> truth.contains_key(l.stmt), Rec::Tomb{..} => true },
    ensures
        matches(r, t, k) != Tri::Unknown,
        (matches(r, t, k) == Tri::Yes) == belongs(r, t, truth),
{
}

// ============================================================================ history

/// One position of the ledger: ^IVG.Ledger("rec", seq, ordinal). `pos` is a flattened index;
/// `rev[pos]` is the revision seq that owns it.
pub open spec fn redact_at(recs: Seq<Rec>, t: Target, k: Know, i: int) -> Rec {
    match recs[i] {
        Rec::Live(l) => if matches(recs[i], t, k) == Tri::Yes { tomb(l, i as nat) } else { recs[i] },
        Rec::Tomb { .. } => recs[i],
    }
}

/// The batches' combined effect on positions [lo, hi) (LedgerRedact.BatchInLock + Tombstone).
pub open spec fn redact_range(recs: Seq<Rec>, t: Target, k: Know, lo: int, hi: int) -> Seq<Rec> {
    Seq::new(recs.len(), |i: int| if lo <= i < hi { redact_at(recs, t, k, i) } else { recs[i] })
}

/// L1 effect of one complete redaction on the record store.
pub open spec fn redact_all(recs: Seq<Rec>, t: Target, k: Know) -> Seq<Rec> {
    redact_range(recs, t, k, 0, recs.len() as int)
}

/// Shape: every revision and record position stays (ADR-0013 "keeping the history's shape").
pub proof fn lemma_shape_kept(recs: Seq<Rec>, t: Target, k: Know, lo: int, hi: int)
    ensures
        redact_range(recs, t, k, lo, hi).len() == recs.len(),
{
}

/// Frame: a record that does not match stays byte-identical; a record that matches becomes the
/// tombstone of exactly itself (digest of the original at its own position, op and flags kept).
pub proof fn lemma_frame_and_tombstone(recs: Seq<Rec>, t: Target, k: Know, i: int)
    requires
        0 <= i < recs.len(),
    ensures
        matches(recs[i], t, k) != Tri::Yes ==> redact_all(recs, t, k)[i] == recs[i],
        matches(recs[i], t, k) == Tri::Yes ==> exists|l: Live| recs[i] == Rec::Live(l)
            && redact_all(recs, t, k)[i] == tomb(l, i as nat),
{
    if matches(recs[i], t, k) == Tri::Yes {
        match recs[i] {
            Rec::Live(l) => {
                assert(redact_all(recs, t, k)[i] == tomb(l, i as nat));
            },
            Rec::Tomb { .. } => {},
        }
    }
}

/// A tombstone never matches: so re-scanning is harmless.
pub proof fn lemma_tomb_never_matches(l: Live, pos: nat, t: Target, k: Know)
    ensures
        matches(tomb(l, pos), t, k) == Tri::No,
{
}

/// Batches compose: two consecutive committed batches equal one batch over the union
/// (Decision 3: each batch is its own transaction; the cursor continues where the last stopped).
pub proof fn lemma_batches_compose(recs: Seq<Rec>, t: Target, k: Know, lo: int, mid: int, hi: int)
    requires
        0 <= lo <= mid <= hi <= recs.len(),
    ensures
        redact_range(redact_range(recs, t, k, lo, mid), t, k, mid, hi) == redact_range(recs, t, k, lo, hi),
{
    let a = redact_range(recs, t, k, lo, mid);
    let b = redact_range(a, t, k, mid, hi);
    let c = redact_range(recs, t, k, lo, hi);
    assert forall|i: int| 0 <= i < recs.len() implies b[i] == c[i] by {
        if mid <= i < hi {
            assert(a[i] == recs[i]);
        }
    }
    assert(b =~= c);
}

/// Resumption (LedgerRedact.Redact restarts its scan at the first record): rescanning any prefix
/// of an already-redacted range changes nothing, so a resumed run ends where an uninterrupted
/// one would.
pub proof fn lemma_rescan_is_harmless(recs: Seq<Rec>, t: Target, k: Know, done: int, lo: int, hi: int)
    requires
        0 <= lo <= hi <= done <= recs.len(),
    ensures
        redact_range(redact_range(recs, t, k, 0, done), t, k, lo, hi) == redact_range(recs, t, k, 0, done),
{
    let a = redact_range(recs, t, k, 0, done);
    let b = redact_range(a, t, k, lo, hi);
    assert forall|i: int| 0 <= i < recs.len() implies b[i] == a[i] by {
        if lo <= i < hi {
            match recs[i] {
                Rec::Live(l) => {
                    if matches(recs[i], t, k) == Tri::Yes {
                        lemma_tomb_never_matches(l, i as nat, t, k);
                    }
                },
                Rec::Tomb { .. } => {},
            }
        }
    }
    assert(b =~= a);
}

/// After the scan reaches the end, no record the run can recognise as the target's survives.
pub proof fn lemma_complete_scan_leaves_no_match(recs: Seq<Rec>, t: Target, k: Know, i: int)
    requires
        0 <= i < recs.len(),
    ensures
        matches(redact_all(recs, t, k)[i], t, k) != Tri::Yes,
{
    match recs[i] {
        Rec::Live(l) => {
            if matches(recs[i], t, k) == Tri::Yes {
                lemma_tomb_never_matches(l, i as nat, t, k);
            }
        },
        Rec::Tomb { .. } => {},
    }
}

/// L1 completeness: with P_ends, a complete run leaves no record that belongs to the target.
pub proof fn lemma_complete_run_removes_every_target_record(
    recs: Seq<Rec>,
    t: Target,
    k: Know,
    truth: Map<nat, (Id, Id)>,
    i: int,
)
    requires
        0 <= i < recs.len(),
        knows_enough(recs, t, k, truth),
        forall|j: int| 0 <= j < recs.len() ==> #[trigger] stmt_in_truth(recs[j], truth),
    ensures
        !belongs(redact_all(recs, t, k)[i], t, truth),
{
    assert(qual_needs(recs[i], t, k));
    assert(tuple_parses(recs[i]));
    assert(stmt_in_truth(recs[i], truth));
    lemma_matches_refines_belongs(recs[i], t, k, truth);
    match recs[i] {
        Rec::Live(l) => {
            if matches(recs[i], t, k) == Tri::Yes {
                lemma_tomb_never_matches(l, i as nat, t, k);
                assert(redact_all(recs, t, k)[i] == tomb(l, i as nat));
            } else {
                assert(redact_all(recs, t, k)[i] == recs[i]);
            }
        },
        Rec::Tomb { .. } => {},
    }
}

pub open spec fn stmt_in_truth(r: Rec, truth: Map<nat, (Id, Id)>) -> bool {
    match r {
        Rec::Live(l) => is_qual_op(l.op) ==> truth.contains_key(l.stmt),
        Rec::Tomb { .. } => true,
    }
}


// ============================================================================ live content

/// A live row of the target's content.
///   NodeRow      Graph_KG.nodes / rdf_labels / rdf_props rows of one node id in one graph
///   EdgeRow      Graph_KG.rdf_edges row (including a temporal edge's marked structural row, ADR-0009)
///   TemporalOnly a temporal edge of a temporal-only predicate (ADR-0015): ^KG temporal subtrees, no row
pub enum Item {
    NodeRow { g: Id, id: Id },
    /// a Graph_KG.rdf_props (or rdf_labels) row; the table has no foreign key to Graph_KG.nodes, so it can exist
    /// without a node row (post_commit_properties and raw SQL insert it directly) (review round 3 R3-4)
    PropRow { g: Id, id: Id },
    EdgeRow { g: Id, s: Id, o: Id },
    TemporalOnly { g: Id, s: Id, o: Id },
}

/// L1: the item is content of the target. ADR-0013 / CONTEXT.md "Redaction": refused while any of
/// the target's content is live. spec 256 plan.md: "The node-liveness check for a default-graph
/// target is graph-blind" (node records are graph-blind and verify() compares nodes graph-blind).
pub open spec fn content(it: Item, t: Target) -> bool {
    match it {
        Item::NodeRow { g, id } => (t.g.len() == 0 || g == t.g) && (t.m.len() == 0 || has_prefix(id, t.m)),
        Item::PropRow { g, id } => (t.g.len() == 0 || g == t.g) && (t.m.len() == 0 || has_prefix(id, t.m)),
        Item::EdgeRow { g, s, o } => g == t.g && (t.m.len() == 0 || ends_hit((s, o), t.m)),
        Item::TemporalOnly { g, s, o } => g == t.g && (t.m.len() == 0 || ends_hit((s, o), t.m)),
    }
}

/// L2: what Graph.KG.Eraser removes for a target: EraseGraph(g) (m empty) or EraseNodes(g, prefix)
/// (incident edges in g; TemporalIndex.EraseNodes). Graph-scoped: a default-graph erase never removes
/// named-graph rows (review R1-8: the model's Erase used to remove L1 content, which is graph-blind).
pub open spec fn erased(it: Item, t: Target) -> bool {
    match it {
        Item::NodeRow { g, id } => g == t.g && (t.m.len() == 0 || has_prefix(id, t.m)),
        // EraseGraph deletes every rdf_props row of the graph; EraseNodes deletes props only of ids it found as node rows
        Item::PropRow { g, id } => g == t.g && t.m.len() == 0,
        Item::EdgeRow { g, s, o } => g == t.g && (t.m.len() == 0 || ends_hit((s, o), t.m)),
        Item::TemporalOnly { g, s, o } => g == t.g && t.m.len() == 0,
    }
}

/// EraseNodes collects the ids to erase from Graph_KG.nodes rows (Eraser.cls:331-349) and erases temporal entries
/// only for those ids (TemporalIndex.EraseNodes). A temporal-only predicate writes no node row, so a prefix erase
/// reaches a temporal-only entry only through an endpoint that has a node row of the target (review round 2 core
/// R2-1). EraseGraph (no prefix) removes every temporal entry of the graph.
pub open spec fn erased_in(live: Set<Item>, it: Item, t: Target) -> bool {
    erased(it, t) || match it {
        Item::PropRow { g, id } => g == t.g && t.m.len() > 0 && has_prefix(id, t.m) && live.contains(Item::NodeRow { g, id }),
        Item::TemporalOnly { g, s, o } => g == t.g && t.m.len() > 0 && (
            (has_prefix(s, t.m) && live.contains(Item::NodeRow { g, id: s }))
            || (has_prefix(o, t.m) && live.contains(Item::NodeRow { g, id: o }))),
        _ => false,
    }
}

/// L2: LedgerRedact.LiveRows (nodes, rdf_labels, rdf_props, rdf_edges; graph-blind node rows only
/// for a prefix target in the default graph; the temporal index is not read).
pub open spec fn checked(it: Item, t: Target) -> bool {
    match it {
        Item::NodeRow { g, id } =>
            if t.m.len() == 0 { g == t.g }
            else if t.g.len() == 0 { has_prefix(id, t.m) }
            else { g == t.g && has_prefix(id, t.m) },
        // LiveRows reads rdf_labels and rdf_props by `s` with the same rule as nodes
        Item::PropRow { g, id } =>
            if t.m.len() == 0 { g == t.g }
            else if t.g.len() == 0 { has_prefix(id, t.m) }
            else { g == t.g && has_prefix(id, t.m) },
        Item::EdgeRow { g, s, o } => g == t.g && (t.m.len() == 0 || ends_hit((s, o), t.m)),
        Item::TemporalOnly { .. } => false,
    }
}

/// The as-built check never refuses a target L1 would allow: it is an under-approximation.
pub proof fn lemma_checked_implies_content(it: Item, t: Target)
    ensures checked(it, t) ==> content(it, t),
{
}

pub open spec fn any_checked(live: Set<Item>, t: Target) -> bool {
    exists|it: Item| live.contains(it) && #[trigger] checked(it, t)
}

pub open spec fn any_content(live: Set<Item>, t: Target) -> bool {
    exists|it: Item| live.contains(it) && #[trigger] content(it, t)
}

// ============================================================================ the lifecycle state

/// One Redact() call: its target, its scan cursor (flattened position) and whether it has written a
/// tombstone (LedgerRedact sets the marker on the first one).
pub struct Run {
    pub t: Target,
    pub cursor: nat,
    pub started: bool,
    /// the scan passed the last record (LedgerRedact.Redact: tSeq = "" → tDone); Final follows
    /// without rescanning, so records committed after this point are not scanned by this run
    pub done: bool,
}

pub struct St {
    /// ^IVG.Ledger("rec", seq, ordinal), flattened
    pub recs: Seq<Rec>,
    /// the revision seq of each position
    pub rev: Seq<nat>,
    pub nrev: nat,
    /// Graph_KG.ledger_revisions.idempotency_key (absent = NULL)
    pub key_of: Map<nat, int>,
    /// ghost: the key each revision was committed with
    pub orig_key: Map<nat, int>,
    /// ^IVG.Ledger("redactedRev", seq): revisions whose four metadata fields were cleared
    pub cleared: Set<nat>,
    /// ^IVG.Ledger("idem", key) = seq
    pub idem: Map<int, nat>,
    /// ^IVG.Ledger("idemRedacted", sha256(key))
    pub idem_redacted: Set<int>,
    /// ^IVG.Ledger("redacting")
    pub marker: Option<Target>,
    pub live: Set<Item>,
    /// ^IVG.Ledger("meta","state") = "enabled"
    pub enabled: bool,
    /// redaction calls in flight, by process
    pub runs: Map<nat, Run>,
}

pub enum Action {
    /// Graph.KG.Ledger.Commit: records, idempotency key, rows written
    Commit { recs: Seq<Live>, key: Option<int>, adds: Set<Item> },
    /// Graph.KG.Eraser.EraseGraph / EraseNodes (one transaction; ADR-0004)
    Erase { t: Target },
    /// a write that does not go through the ledger (engine.create_edge, Cypher CREATE, bulk load,
    /// post_commit_properties); LedgerGuard refuses it only in strict mode
    Unrecorded { adds: Set<Item> },
    /// LedgerRedact.Redact's checks before the first batch (outside the head lock)
    Start { p: nat, t: Target },
    /// one record inside a batch transaction (a batch is a sequence of these under the head lock)
    Step { p: nat },
    /// a batch that rolls back (lock timeout, disabled ledger, SQL failure, process death): the
    /// call returns and its cursor is forgotten
    Abandon { p: nat },
    /// LedgerRedact.Final (own transaction under the head lock)
    Final { p: nat },
    Disable,
    Enable,
}

#[allow(non_snake_case)]
pub uninterp spec fn K() -> Know;  // statement knowledge: a model parameter (see coverage.md premises)

pub open spec fn live_of(l: Live) -> Rec { Rec::Live(l) }

pub open spec fn append_commit(s: St, new: Seq<Live>, key: Option<int>, adds: Set<Item>) -> St {
    let n = new.len();
    St {
        recs: s.recs + new.map_values(|l: Live| Rec::Live(l)),
        rev: s.rev + Seq::new(n, |i: int| s.nrev),
        nrev: s.nrev + 1,
        key_of: match key { Some(k) => s.key_of.insert(s.nrev, k), None => s.key_of },
        orig_key: match key { Some(k) => s.orig_key.insert(s.nrev, k), None => s.orig_key },
        idem: match key { Some(k) => s.idem.insert(k, s.nrev), None => s.idem },
        live: s.live.union(adds),
        ..s
    }
}

/// Graph.KG.Ledger.CommitInTxn admission (idempotency → redacted key → apply → BlocksCommit).
/// A replay of a bound key and every refusal leave the state unchanged, so they are stutters.
pub open spec fn commit_admits(s: St, new: Seq<Live>, key: Option<int>, blocks: bool) -> bool {
    &&& s.enabled
    &&& new.len() > 0
    &&& match key { Some(k) => !s.idem.contains_key(k) && !s.idem_redacted.contains(k), None => true }
    &&& (blocks ==> match s.marker {
            Some(t) => forall|j: int| 0 <= j < new.len() ==> matches(Rec::Live(#[trigger] new[j]), t, K()) != Tri::Yes,
            None => true,
        })
}

/// LedgerRedact.Tombstone + ClearRevision for position i (first tombstone of a revision clears its
/// metadata and moves its key from idem to idemRedacted).
pub open spec fn tombstone_at(s: St, i: int) -> St {
    let rv = s.rev[i];
    let l = s.recs[i]->Live_0;
    let first = !s.cleared.contains(rv);
    let has_key = s.key_of.contains_key(rv);
    St {
        recs: s.recs.update(i, tomb(l, i as nat)),
        cleared: s.cleared.insert(rv),
        key_of: if first && has_key { s.key_of.remove(rv) } else { s.key_of },
        idem: if first && has_key { s.idem.remove(s.key_of[rv]) } else { s.idem },
        idem_redacted: if first && has_key { s.idem_redacted.insert(s.key_of[rv]) } else { s.idem_redacted },
        ..s
    }
}

/// Variant switches: `serial` restricts Start to an idle system (the premise under which the
/// as-built mechanism is correct); `repaired` makes Step refuse when the marker names another
/// target (the proposal in design_simplification/bugs register); `blocks` is BlocksCommit;
/// `full_check` replaces LiveRows by the L1 content test.
pub struct Variant {
    pub serial: bool,
    pub repaired: bool,
    pub blocks: bool,
    pub full_check: bool,
}

pub open spec fn live_hit(s: St, t: Target, v: Variant) -> bool {
    if v.full_check { any_content(s.live, t) } else { any_checked(s.live, t) }
}

pub open spec fn step(s: St, a: Action, v: Variant) -> Option<St> {
    match a {
        Action::Commit { recs, key, adds } =>
            if commit_admits(s, recs, key, v.blocks) { Some(append_commit(s, recs, key, adds)) } else { None },
        Action::Erase { t } => Some(St { live: s.live.filter(|it: Item| !erased_in(s.live, it, t)), ..s }),
        Action::Unrecorded { adds } => Some(St { live: s.live.union(adds), ..s }),
        Action::Start { p, t } =>
            if s.runs.contains_key(p) || (v.serial && busy(s)) || !s.enabled {
                None
            } else if s.marker is Some && s.marker != Some(t) {
                None  // redaction_in_progress
            } else if live_hit(s, t, v) {
                None  // target_live
            } else {
                Some(St { runs: s.runs.insert(p, Run { t, cursor: 0, started: s.marker == Some(t), done: s.recs.len() == 0 }), ..s })
            },
        Action::Step { p } =>
            if !s.runs.contains_key(p) || !s.enabled || s.runs[p].done || s.runs[p].cursor >= s.recs.len() {
                None
            } else {
                let r = s.runs[p];
                let i = r.cursor as int;
                if matches(s.recs[i], r.t, K()) == Tri::Yes {
                    if v.repaired && s.marker is Some && s.marker != Some(r.t) {
                        None
                    } else {
                        let s1 = tombstone_at(s, i);
                        Some(St {
                            marker: if s.marker is None { Some(r.t) } else { s.marker },
                            runs: s.runs.insert(p, Run { cursor: r.cursor + 1, started: true, done: r.cursor + 1 == s.recs.len(), ..r }),
                            ..s1
                        })
                    }
                } else {
                    Some(St { runs: s.runs.insert(p, Run { cursor: r.cursor + 1, done: r.cursor + 1 == s.recs.len(), ..r }), ..s })
                }
            },
        Action::Abandon { p } =>
            if s.runs.contains_key(p) { Some(St { runs: s.runs.remove(p), ..s }) } else { None },
        Action::Final { p } =>
            if !s.runs.contains_key(p) || !s.runs[p].done || !s.enabled || live_hit(s, s.runs[p].t, v) {
                None  // disabled / target_live: the call returns, its run ends (see Abandon)
            } else if v.repaired && s.marker is Some && s.marker != Some(s.runs[p].t) {
                None
            } else if s.marker is Some {
                let audit = Live { op: Op::Redact, id: Seq::empty(), stmt: 0, ends: None, graph: Seq::empty(), payload: 0, flags: 0 };
                let s1 = append_commit(s, seq![audit], None, Set::empty());
                Some(St { marker: None, runs: s.runs.remove(p), ..s1 })
            } else {
                Some(St { runs: s.runs.remove(p), ..s })
            },
        Action::Disable => Some(St { enabled: false, ..s }),
        Action::Enable => Some(St { enabled: true, ..s }),
    }
}

// ============================================================================ invariants (serialised redactions)

pub open spec fn behind_cursor_clean(s: St) -> bool {
    forall|p: nat, i: int| #![trigger s.runs.contains_key(p), s.recs[i]]
        s.runs.contains_key(p) && 0 <= i < s.runs[p].cursor ==> matches(s.recs[i], s.runs[p].t, K()) != Tri::Yes
}

pub open spec fn marker_names_started_run(s: St) -> bool {
    forall|p: nat| #[trigger] s.runs.contains_key(p) && s.runs[p].started ==> s.marker == Some(s.runs[p].t)
}

pub open spec fn marker_is_none_or_run_target(s: St) -> bool {
    forall|p: nat| #[trigger] s.runs.contains_key(p) ==> (s.marker is None || s.marker == Some(s.runs[p].t))
}

/// Decision 2 bookkeeping: a revision with a tombstone has its metadata cleared and its key moved.
pub open spec fn tombs_cleared(s: St) -> bool {
    &&& s.rev.len() == s.recs.len()
    &&& forall|i: int| 0 <= i < s.recs.len() ==> s.rev[i] < s.nrev
    &&& forall|i: int| 0 <= i < s.recs.len() && (#[trigger] s.recs[i] is Tomb) ==> s.cleared.contains(s.rev[i])
    &&& forall|rv: nat| #[trigger] s.cleared.contains(rv) ==> !s.key_of.contains_key(rv) && rv < s.nrev
    &&& forall|rv: nat| #[trigger] s.cleared.contains(rv) && s.orig_key.contains_key(rv) ==>
            s.idem_redacted.contains(s.orig_key[rv]) && !s.idem.contains_key(s.orig_key[rv])
    &&& forall|rv: nat| #[trigger] s.key_of.contains_key(rv) ==>
            rv < s.nrev && s.orig_key.contains_key(rv) && s.key_of[rv] == s.orig_key[rv]
            && s.idem.contains_key(s.key_of[rv]) && s.idem[s.key_of[rv]] == rv
    &&& forall|rv: nat| #[trigger] s.orig_key.contains_key(rv) ==> rv < s.nrev
            && (!s.cleared.contains(rv) ==> s.key_of.contains_key(rv))
    &&& forall|k: int| #[trigger] s.idem.contains_key(k) ==> !s.idem_redacted.contains(k)
            && s.key_of.contains_key(s.idem[k]) && s.key_of[s.idem[k]] == k
}

pub open spec fn cursors_in_range(s: St) -> bool {
    forall|p: nat| #[trigger] s.runs.contains_key(p) ==> s.runs[p].cursor <= s.recs.len()
        && (!s.runs[p].done ==> s.runs[p].cursor < s.recs.len() || s.recs.len() == 0 && s.runs[p].cursor == 0)
}

/// After a started run's scan is done, nothing behind its back matches: commits were refused.
pub open spec fn done_clean(s: St) -> bool {
    forall|p: nat, i: int| #![trigger s.runs.contains_key(p), s.recs[i]]
        s.runs.contains_key(p) && s.runs[p].done && s.marker == Some(s.runs[p].t)
        && s.runs[p].cursor <= i < s.recs.len() ==> matches(s.recs[i], s.runs[p].t, K()) != Tri::Yes
}

pub open spec fn inv(s: St) -> bool {
    &&& behind_cursor_clean(s)
    &&& marker_names_started_run(s)
    &&& marker_is_none_or_run_target(s)
    &&& tombs_cleared(s)
    &&& cursors_in_range(s)
    &&& done_clean(s)
    &&& at_most_one_run(s)
}

pub open spec fn at_most_one_run(s: St) -> bool {
    forall|p: nat, q: nat| #[trigger] s.runs.contains_key(p) && #[trigger] s.runs.contains_key(q) ==> p == q
}

pub open spec fn busy(s: St) -> bool {
    exists|q: nat| #[trigger] s.runs.contains_key(q)
}

pub open spec fn as_built() -> Variant {
    Variant { serial: true, repaired: false, blocks: true, full_check: false }
}


// ---------------------------------------------------------------------------- preservation

pub proof fn lemma_commit_preserves(s: St, new: Seq<Live>, key: Option<int>, adds: Set<Item>)
    requires
        inv(s),
        commit_admits(s, new, key, true),
    ensures
        inv(append_commit(s, new, key, adds)),
{
    let s2 = append_commit(s, new, key, adds);
    assert(s2.recs.len() == s.recs.len() + new.len());
    assert forall|i: int| 0 <= i < s.recs.len() implies s2.recs[i] == s.recs[i] && s2.rev[i] == s.rev[i] by {}
    assert forall|i: int| s.recs.len() <= i < s2.recs.len() implies s2.recs[i] == Rec::Live(new[i - s.recs.len()]) && s2.rev[i] == s.nrev by {}
    assert(behind_cursor_clean(s2)) by {
        assert forall|p: nat, i: int| #![trigger s2.runs.contains_key(p), s2.recs[i]]
            s2.runs.contains_key(p) && 0 <= i < s2.runs[p].cursor implies matches(s2.recs[i], s2.runs[p].t, K()) != Tri::Yes by {
            assert(s.runs.contains_key(p));
            assert(s.recs[i] == s2.recs[i]);
        }
    }
    assert(tombs_cleared(s2)) by {
        assert forall|i: int| 0 <= i < s2.recs.len() && (#[trigger] s2.recs[i] is Tomb) implies s2.cleared.contains(s2.rev[i]) by {
            if i < s.recs.len() { assert(s.recs[i] is Tomb); } else { assert(s2.recs[i] == Rec::Live(new[i - s.recs.len()])); }
        }
        assert forall|i: int| 0 <= i < s2.recs.len() implies s2.rev[i] < s2.nrev by {}
        match key {
            Some(k) => {
                assert forall|rv: nat| #[trigger] s2.cleared.contains(rv) implies !s2.key_of.contains_key(rv) by {
                    assert(s.cleared.contains(rv));
                }
                assert forall|rv: nat| #[trigger] s2.cleared.contains(rv) && s2.orig_key.contains_key(rv) implies
                    s2.idem_redacted.contains(s2.orig_key[rv]) && !s2.idem.contains_key(s2.orig_key[rv]) by {
                    assert(rv != s.nrev);
                    assert(s2.orig_key[rv] == s.orig_key[rv]);
                    assert(s.orig_key[rv] != k);
                }
                assert forall|rv: nat| #[trigger] s2.key_of.contains_key(rv) implies
                    rv < s2.nrev && s2.orig_key.contains_key(rv) && s2.key_of[rv] == s2.orig_key[rv]
                    && s2.idem.contains_key(s2.key_of[rv]) && s2.idem[s2.key_of[rv]] == rv by {
                    if rv != s.nrev {
                        assert(s.key_of.contains_key(rv));
                        assert(s.key_of[rv] != k);
                    }
                }
                assert forall|kk: int| #[trigger] s2.idem.contains_key(kk) implies !s2.idem_redacted.contains(kk)
                    && s2.key_of.contains_key(s2.idem[kk]) && s2.key_of[s2.idem[kk]] == kk by {
                    if kk != k {
                        assert(s.idem.contains_key(kk));
                        assert(s.idem[kk] < s.nrev);
                    }
                }
            },
            None => {
                assert forall|rv: nat| #[trigger] s2.cleared.contains(rv) implies !s2.key_of.contains_key(rv) by {}
            },
        }
    }
}




pub open spec fn audit_rec() -> Live {
    Live { op: Op::Redact, id: Seq::empty(), stmt: 0, ends: None, graph: Seq::empty(), payload: 0, flags: 0 }
}

pub proof fn lemma_step_preserves_inv(s: St, a: Action)
    requires
        inv(s),
        step(s, a, as_built()) is Some,
    ensures
        inv(step(s, a, as_built())->Some_0),
{
    let v = as_built();
    let s2 = step(s, a, v)->Some_0;
    match a {
        Action::Commit { recs, key, adds } => {
            lemma_commit_preserves(s, recs, key, adds);
        },
        Action::Erase { t } => {},
        Action::Unrecorded { adds } => {},
        Action::Start { p, t } => {
            assert(!busy(s));
            assert forall|q: nat| #[trigger] s2.runs.contains_key(q) implies q == p by {
                if q != p { assert(s.runs.contains_key(q)); assert(busy(s)); }
            }
            assert(behind_cursor_clean(s2)) by {
                assert forall|q: nat, i: int| #![trigger s2.runs.contains_key(q), s2.recs[i]]
                    s2.runs.contains_key(q) && 0 <= i < s2.runs[q].cursor implies matches(s2.recs[i], s2.runs[q].t, K()) != Tri::Yes by {
                    assert(q == p);
                }
            }
        },
        Action::Step { p } => {
            let r = s.runs[p];
            let i = r.cursor as int;
            assert(at_most_one_run(s2)) by {
                assert forall|q1: nat, q2: nat| #[trigger] s2.runs.contains_key(q1) && #[trigger] s2.runs.contains_key(q2) implies q1 == q2 by {
                    assert(s.runs.contains_key(q1) && s.runs.contains_key(q2));
                }
            }
            if matches(s.recs[i], r.t, K()) == Tri::Yes {
                let l = s.recs[i]->Live_0;
                let s1 = tombstone_at(s, i);
                lemma_tomb_never_matches(l, i as nat, r.t, K());
                assert(s2.recs == s.recs.update(i, tomb(l, i as nat)));
                assert(behind_cursor_clean(s2)) by {
                    assert forall|q: nat, j: int| #![trigger s2.runs.contains_key(q), s2.recs[j]]
                        s2.runs.contains_key(q) && 0 <= j < s2.runs[q].cursor implies matches(s2.recs[j], s2.runs[q].t, K()) != Tri::Yes by {
                        assert(q == p);
                        if j != i { assert(s2.recs[j] == s.recs[j]); assert(s.runs.contains_key(p)); }
                    }
                }
                assert(marker_names_started_run(s2)) by {
                    assert(s.marker is None || s.marker == Some(r.t));
                }
                assert(marker_is_none_or_run_target(s2)) by {
                    assert(s.marker is None || s.marker == Some(r.t));
                }
                let rv = s.rev[i];
                assert(tombs_cleared(s2)) by {
                    assert forall|j: int| 0 <= j < s2.recs.len() && (#[trigger] s2.recs[j] is Tomb) implies s2.cleared.contains(s2.rev[j]) by {
                        if j != i { assert(s.recs[j] is Tomb); }
                    }
                    if !s.cleared.contains(rv) && s.key_of.contains_key(rv) {
                        let k0 = s.key_of[rv];
                        assert forall|rv2: nat| #[trigger] s2.cleared.contains(rv2) && s2.orig_key.contains_key(rv2) implies
                            s2.idem_redacted.contains(s2.orig_key[rv2]) && !s2.idem.contains_key(s2.orig_key[rv2]) by {
                            if rv2 != rv {
                                assert(s.cleared.contains(rv2));
                            }
                        }
                        assert forall|rv2: nat| #[trigger] s2.key_of.contains_key(rv2) implies
                            rv2 < s2.nrev && s2.orig_key.contains_key(rv2) && s2.key_of[rv2] == s2.orig_key[rv2]
                            && s2.idem.contains_key(s2.key_of[rv2]) && s2.idem[s2.key_of[rv2]] == rv2 by {
                            assert(s.key_of.contains_key(rv2));
                            assert(rv2 != rv);
                            assert(s.idem[s.key_of[rv2]] == rv2);
                            assert(s.key_of[rv2] != k0);
                        }
                        assert forall|kk: int| #[trigger] s2.idem.contains_key(kk) implies !s2.idem_redacted.contains(kk)
                            && s2.key_of.contains_key(s2.idem[kk]) && s2.key_of[s2.idem[kk]] == kk by {
                            assert(s.idem.contains_key(kk));
                            assert(kk != k0);
                            assert(s.idem[kk] != rv);
                        }
                        assert forall|rv2: nat| #[trigger] s2.orig_key.contains_key(rv2) implies rv2 < s2.nrev
                            && (!s2.cleared.contains(rv2) ==> s2.key_of.contains_key(rv2)) by {
                            if !s2.cleared.contains(rv2) { assert(rv2 != rv); }
                        }
                    } else {
                        assert forall|rv2: nat| #[trigger] s2.cleared.contains(rv2) && s2.orig_key.contains_key(rv2) implies
                            s2.idem_redacted.contains(s2.orig_key[rv2]) && !s2.idem.contains_key(s2.orig_key[rv2]) by {
                            if rv2 == rv && !s.cleared.contains(rv) {
                                assert(s.key_of.contains_key(rv));  // contradiction with the branch
                            }
                        }
                        assert forall|rv2: nat| #[trigger] s2.cleared.contains(rv2) implies !s2.key_of.contains_key(rv2) && rv2 < s2.nrev by {
                            if rv2 == rv { assert(s.rev[i] < s.nrev); }
                        }
                    }
                }
            } else {
                assert(behind_cursor_clean(s2)) by {
                    assert forall|q: nat, j: int| #![trigger s2.runs.contains_key(q), s2.recs[j]]
                        s2.runs.contains_key(q) && 0 <= j < s2.runs[q].cursor implies matches(s2.recs[j], s2.runs[q].t, K()) != Tri::Yes by {
                        assert(q == p);
                        if j != i { assert(s.runs.contains_key(p)); }
                    }
                }
            }
        },
        Action::Abandon { p } => {},
        Action::Final { p } => {
            if s.marker is Some {
                let t = s.marker->Some_0;
                assert(matches(Rec::Live(audit_rec()), t, K()) == Tri::No);
                assert(commit_admits(s, seq![audit_rec()], None, true)) by {
                    assert forall|j: int| 0 <= j < seq![audit_rec()].len() implies matches(Rec::Live(#[trigger] seq![audit_rec()][j]), t, K()) != Tri::Yes by {
                        assert(seq![audit_rec()][j] == audit_rec());
                    }
                }
                lemma_commit_preserves(s, seq![audit_rec()], None, Set::empty());
                let s1 = append_commit(s, seq![audit_rec()], None, Set::empty());
                assert(s2 == St { marker: None, runs: s.runs.remove(p), ..s1 });
                assert forall|q: nat| !s2.runs.contains_key(q) by {
                    if q != p { if s.runs.contains_key(q) { assert(s.runs.contains_key(p)); } }
                }
            } else {
                assert forall|q: nat| !s2.runs.contains_key(q) by {
                    if q != p { if s.runs.contains_key(q) { assert(s.runs.contains_key(p)); } }
                }
            }
        },
        Action::Disable => {},
        Action::Enable => {},
    }
}


// ---------------------------------------------------------------------------- initial state

/// A namespace whose ledger was just enabled (genesis) with no redaction in flight.
pub open spec fn init(s: St) -> bool {
    &&& s.rev.len() == s.recs.len()
    &&& forall|i: int| 0 <= i < s.recs.len() ==> (#[trigger] s.recs[i]) is Live && s.rev[i] < s.nrev
    &&& s.cleared == Set::<nat>::empty()
    &&& s.key_of == Map::<nat, int>::empty()
    &&& s.orig_key == Map::<nat, int>::empty()
    &&& s.idem == Map::<int, nat>::empty()
    &&& s.idem_redacted == Set::<int>::empty()
    &&& s.marker is None
    &&& s.runs == Map::<nat, Run>::empty()
}

pub proof fn lemma_init_establishes_inv(s: St)
    requires init(s),
    ensures inv(s),
{
    assert(behind_cursor_clean(s));
    assert(marker_names_started_run(s));
    assert(marker_is_none_or_run_target(s));
    assert(cursors_in_range(s));
    assert(at_most_one_run(s));
    assert forall|i: int| 0 <= i < s.recs.len() && (#[trigger] s.recs[i] is Tomb) implies s.cleared.contains(s.rev[i]) by {
        assert(s.recs[i] is Live);
    }
    assert forall|i: int| 0 <= i < s.recs.len() implies s.rev[i] < s.nrev by {
        assert(s.recs[i] is Live);
    }
    assert(tombs_cleared(s));
}

// ---------------------------------------------------------------------------- what a complete run guarantees

/// Completion (spec 256 US1, ADR-0013): when the final step of a run that tombstoned anything
/// commits, (1) the marker named the run's target until then (so readers refused and target commits
/// were refused throughout), (2) no record before the redaction revision is still recognisably the
/// target's, (3) a content-free redaction revision was appended, and (4) the marker is gone.
pub proof fn theorem_completion(s: St, p: nat)
    requires
        inv(s),
        s.runs.contains_key(p),
        s.runs[p].started,
        step(s, Action::Final { p }, as_built()) is Some,
    ensures ({
        let s2 = step(s, Action::Final { p }, as_built())->Some_0;
        let t = s.runs[p].t;
        &&& s.marker == Some(t)
        &&& forall|i: int| 0 <= i < s.recs.len() ==> matches(#[trigger] s2.recs[i], t, K()) != Tri::Yes
        &&& s2.recs.len() == s.recs.len() + 1
        &&& s2.recs[s.recs.len() as int] == Rec::Live(audit_rec())
        &&& matches(Rec::Live(audit_rec()), t, K()) == Tri::No
        &&& s2.marker is None
        &&& !any_checked(s.live, t)
    }),
{
    let s2 = step(s, Action::Final { p }, as_built())->Some_0;
    let t = s.runs[p].t;
    assert(s.runs[p].done);
    assert(s.marker == Some(t));
    assert forall|i: int| 0 <= i < s.recs.len() implies matches(#[trigger] s2.recs[i], t, K()) != Tri::Yes by {
        assert(s2.recs[i] == s.recs[i]);
        assert(s.runs.contains_key(p) && s.recs[i] == s.recs[i]);
    }
}

/// Decision 2 + the retry rule: once any record of a revision is a tombstone, that revision's
/// idempotency key is unbound and a commit carrying it is refused (idempotency_redacted), whatever
/// the changeset; nothing is replayed or written.
pub proof fn theorem_redacted_key_refused(s: St, i: int, new: Seq<Live>, adds: Set<Item>, blocks: bool)
    requires
        inv(s),
        0 <= i < s.recs.len(),
        s.recs[i] is Tomb,
        s.orig_key.contains_key(s.rev[i]),
    ensures
        !commit_admits(s, new, Some(s.orig_key[s.rev[i]]), blocks),
        !s.idem.contains_key(s.orig_key[s.rev[i]]),
        !s.key_of.contains_key(s.rev[i]),
{
    assert(s.cleared.contains(s.rev[i]));
}

/// Frame for mixed-tenant revisions: a redaction step changes at most the one position its cursor
/// is on, and only when that record matches the run's target. Every other record — including other
/// tenants' records in the same revision — keeps its exact value.
pub proof fn theorem_step_frame(s: St, a: Action, j: int)
    requires
        inv(s),
        step(s, a, as_built()) is Some,
        0 <= j < s.recs.len(),
    ensures ({
        let s2 = step(s, a, as_built())->Some_0;
        s2.recs[j] != s.recs[j] ==> (exists|p: nat| a == Action::Step { p } && s.runs.contains_key(p)
            && s.runs[p].cursor == j && matches(s.recs[j], s.runs[p].t, K()) == Tri::Yes)
    }),
{
    let s2 = step(s, a, as_built())->Some_0;
    match a {
        Action::Step { p } => {
            let r = s.runs[p];
            if matches(s.recs[r.cursor as int], r.t, K()) == Tri::Yes && j != r.cursor {
                assert(s2.recs[j] == s.recs[j]);
            }
        },
        Action::Commit { recs, key, adds } => { assert(s2.recs[j] == s.recs[j]); },
        Action::Final { p } => {
            if s.marker is Some { assert(s2.recs[j] == s.recs[j]); }
        },
        _ => {},
    }
}

// ---------------------------------------------------------------------------- witnesses (counterexamples)

pub open spec fn node_rec(id: Id) -> Live {
    Live { op: Op::CreateNode, id, stmt: 0, ends: None, graph: Seq::empty(), payload: 1, flags: 0 }
}

pub open spec fn s_two_tenants() -> St {
    St {
        recs: seq![Rec::Live(node_rec(seq!['a', '|', '1'])), Rec::Live(node_rec(seq!['b', '|', '1']))],
        rev: seq![1nat, 2nat],
        nrev: 3,
        key_of: Map::empty(),
        orig_key: Map::empty(),
        cleared: Set::empty(),
        idem: Map::empty(),
        idem_redacted: Set::empty(),
        marker: None,
        live: Set::empty(),
        enabled: true,
        runs: Map::empty(),
    }
}

pub open spec fn ta() -> Target { Target { g: Seq::empty(), m: seq!['a', '|'] } }
pub open spec fn tb() -> Target { Target { g: Seq::empty(), m: seq!['b', '|'] } }

pub open spec fn concurrent() -> Variant { Variant { serial: false, repaired: false, blocks: true, full_check: false } }
pub open spec fn concurrent_repaired() -> Variant { Variant { serial: false, repaired: true, blocks: true, full_check: false } }

/// W1 — two redactions of different targets started before either wrote a tombstone. The marker
/// check runs only at the start (outside the head lock) and BatchInLock writes tombstones under a
/// marker that names another target. The second run's final step removes the marker while the first
/// is unfinished; a commit into the first run's target is then admitted mid-redaction.
pub proof fn witness_concurrent_targets_break_the_marker() {
    let v = concurrent();
    let s0 = s_two_tenants();
    assert(has_prefix(seq!['a', '|', '1'], seq!['a', '|'])) by { assert(seq!['a', '|', '1'].subrange(0, 2) =~= seq!['a', '|']); }
    assert(!has_prefix(seq!['b', '|', '1'], seq!['a', '|'])) by { assert(seq!['b', '|', '1'].subrange(0, 2)[0] == 'b'); }
    assert(has_prefix(seq!['b', '|', '1'], seq!['b', '|'])) by { assert(seq!['b', '|', '1'].subrange(0, 2) =~= seq!['b', '|']); }
    assert(!has_prefix(seq!['a', '|', '1'], seq!['b', '|'])) by { assert(seq!['a', '|', '1'].subrange(0, 2)[0] == 'a'); }
    assert(!any_checked(s0.live, ta()));
    assert(!any_checked(s0.live, tb()));
    let s1 = step(s0, Action::Start { p: 1, t: ta() }, v)->Some_0;
    assert(step(s0, Action::Start { p: 1, t: ta() }, v) is Some);
    let s2 = step(s1, Action::Start { p: 2, t: tb() }, v)->Some_0;
    assert(step(s1, Action::Start { p: 2, t: tb() }, v) is Some);
    // run 1 tombstones a|1 and sets the marker to A
    assert(s2.recs[0] == Rec::Live(node_rec(seq!['a', '|', '1'])));
    assert(matches(s2.recs[0], ta(), K()) == Tri::Yes);
    let s3 = step(s2, Action::Step { p: 1 }, v)->Some_0;
    assert(s3.marker == Some(ta()));
    // run 2 skips the tombstone and tombstones b|1 under A's marker
    lemma_tomb_never_matches(node_rec(seq!['a', '|', '1']), 0, tb(), K());
    assert(matches(s3.recs[0], tb(), K()) == Tri::No);
    let s4 = step(s3, Action::Step { p: 2 }, v)->Some_0;
    assert(s4.runs[2].cursor == 1);
    assert(s4.recs[1] == Rec::Live(node_rec(seq!['b', '|', '1'])));
    assert(matches(s4.recs[1], tb(), K()) == Tri::Yes);
    let s5 = step(s4, Action::Step { p: 2 }, v)->Some_0;
    assert(step(s4, Action::Step { p: 2 }, v) is Some);
    assert(s5.runs[2].started && s5.marker == Some(ta()) && ta() != tb()) by {
        assert(ta().m[0] != tb().m[0]);
    }
    // the invariant the serialised proof relies on is false here
    assert(!marker_names_started_run(s5)) by {
        assert(s5.runs.contains_key(2) && s5.runs[2].started && s5.marker != Some(s5.runs[2].t)) by {
            assert(ta().m[0] != tb().m[0]);
        }
    }
    // run 2 finishes first: the marker goes while run 1 (cursor 1 of 2) is unfinished
    let s6 = step(s5, Action::Final { p: 2 }, v)->Some_0;
    assert(step(s5, Action::Final { p: 2 }, v) is Some);
    assert(s6.marker is None && s6.runs.contains_key(1) && s6.runs[1].started && s6.runs[1].cursor < s6.recs.len());
    // a commit that writes into run 1's target is admitted mid-redaction
    let late = seq![node_rec(seq!['a', '|', '2'])];
    assert(commit_admits(s6, late, None, true));
}

/// Under the repaired step (BatchInLock refuses while the marker names another target) the same
/// schedule stops at run 2's first tombstone: nothing is written under another target's marker.
pub proof fn witness_repair_refuses_the_interleaving() {
    let v = concurrent_repaired();
    let s0 = s_two_tenants();
    assert(has_prefix(seq!['a', '|', '1'], seq!['a', '|'])) by { assert(seq!['a', '|', '1'].subrange(0, 2) =~= seq!['a', '|']); }
    assert(has_prefix(seq!['b', '|', '1'], seq!['b', '|'])) by { assert(seq!['b', '|', '1'].subrange(0, 2) =~= seq!['b', '|']); }
    assert(!any_checked(s0.live, ta()));
    assert(!any_checked(s0.live, tb()));
    let s1 = step(s0, Action::Start { p: 1, t: ta() }, v)->Some_0;
    let s2 = step(s1, Action::Start { p: 2, t: tb() }, v)->Some_0;
    assert(matches(s2.recs[0], ta(), K()) == Tri::Yes);
    let s3 = step(s2, Action::Step { p: 1 }, v)->Some_0;
    lemma_tomb_never_matches(node_rec(seq!['a', '|', '1']), 0, tb(), K());
    let s4 = step(s3, Action::Step { p: 2 }, v)->Some_0;
    assert(matches(s4.recs[1], tb(), K()) == Tri::Yes);
    assert(s4.marker == Some(ta()) && ta() != tb()) by { assert(ta().m[0] != tb().m[0]); }
    assert(step(s4, Action::Step { p: 2 }, v) is None);
}

/// W2 — a target whose only live content is a temporal edge of a temporal-only predicate passes
/// LiveRows; its create_temporal_edge record is tombstoned while the edge is still in the index.
pub proof fn witness_temporal_only_content_is_not_seen() {
    let g: Id = seq!['g'];
    let t = Target { g, m: Seq::empty() };
    let it = Item::TemporalOnly { g, s: seq!['x'], o: seq!['y'] };
    let live = Set::empty().insert(it);
    assert(content(it, t));
    assert(!any_checked(live, t)) by {
        assert forall|i: Item| live.contains(i) implies !checked(i, t) by { assert(i == it); }
    }
    assert(any_content(live, t));
    let r = Live { op: Op::CreateTemporal, id: Seq::empty(), stmt: 0, ends: Some((seq!['x'], seq!['y'])), graph: g, payload: 2, flags: 0 };
    assert(matches(Rec::Live(r), t, K()) == Tri::Yes);
}

/// W3 — the whole default graph as a target: LiveRows counts only default-graph node rows, but node
/// records are graph-blind, so a node id still live in a named graph has its records tombstoned.
pub proof fn witness_default_graph_target_is_not_graph_blind() {
    let v = as_built();
    let t = Target { g: Seq::empty(), m: Seq::empty() };
    let n: Id = seq!['n'];
    let named = Item::NodeRow { g: seq!['G'], id: n };
    let dflt = Item::NodeRow { g: Seq::empty(), id: n };
    // the ledger created n in the default graph and registered it in G for a named-graph edge
    let s0 = St { recs: seq![Rec::Live(node_rec(n))], rev: seq![1nat], nrev: 2,
                  live: Set::empty().insert(named).insert(dflt), ..s_two_tenants() };
    assert(seq!['G'].len() == 1);
    assert(erased(dflt, t) && !erased(named, t));
    // erase_graph(None) removes the default graph's row only
    let s1 = step(s0, Action::Erase { t }, v)->Some_0;
    assert(s1.live.contains(named) && !s1.live.contains(dflt));
    assert(content(named, t));
    assert(any_content(s1.live, t));
    assert(!any_checked(s1.live, t)) by {
        assert forall|i: Item| s1.live.contains(i) implies !checked(i, t) by {
            assert(s0.live.contains(i));
            assert(i == named || i == dflt);
        }
    }
    // redact(None) starts and tombstones n's record while n is still a row in G
    assert(!busy(s1));
    let s2 = step(s1, Action::Start { p: 1, t }, v)->Some_0;
    assert(step(s1, Action::Start { p: 1, t }, v) is Some);
    assert(matches(s2.recs[0], t, K()) == Tri::Yes);
    let s3 = step(s2, Action::Step { p: 1 }, v)->Some_0;
    assert(s3.recs[0] == tomb(node_rec(n), 0) && s3.live.contains(named));
}

/// W4 — a qualifier record whose statement has no create_rel/delete_rel record (the statement was
/// assigned to an unrecorded edge: LedgerApply flag assigned_stmt) and whose ^IVG.Ledger("stmt")
/// entry the erasure removed. The run cannot attribute it (Matches = -1), counts it in
/// unattributed_records, and leaves it holding the target's qualifier value; L1 says it belongs.
pub proof fn witness_unattributed_qualifier_survives() {
    let t = Target { g: Seq::empty(), m: seq!['a', '|'] };
    let q = Live { op: Op::SetQual, id: seq!['7'], stmt: 7, ends: None, graph: Seq::empty(), payload: 42, flags: 1 };
    let k = Know { redacting: Set::empty(), ends: Map::empty() };
    let truth = Map::empty().insert(7nat, (seq!['a', '|', '1'], seq!['a', '|', '2']));
    assert(has_prefix(seq!['a', '|', '1'], seq!['a', '|'])) by { assert(seq!['a', '|', '1'].subrange(0, 2) =~= seq!['a', '|']); }
    assert(matches(Rec::Live(q), t, k) == Tri::Unknown);
    assert(belongs(Rec::Live(q), t, truth));
    let recs = seq![Rec::Live(q)];
    assert(redact_all(recs, t, k)[0] == Rec::Live(q));
    assert(belongs(redact_all(recs, t, k)[0], t, truth));
}

/// Control for BlocksCommit: without it, a commit with a target record that lands after the scan passed
/// the end survives a completed run — the property theorem_completion proves for the as-built check.
pub proof fn witness_without_blockscommit() {
    let v = Variant { serial: true, repaired: false, blocks: false, full_check: false };
    let s0 = St { recs: seq![Rec::Live(node_rec(seq!['a', '|', '1']))], rev: seq![1nat], nrev: 2, ..s_two_tenants() };
    assert(has_prefix(seq!['a', '|', '1'], seq!['a', '|'])) by { assert(seq!['a', '|', '1'].subrange(0, 2) =~= seq!['a', '|']); }
    assert(has_prefix(seq!['a', '|', '2'], seq!['a', '|'])) by { assert(seq!['a', '|', '2'].subrange(0, 2) =~= seq!['a', '|']); }
    assert(!any_checked(s0.live, ta()));
    assert(!busy(s0));
    let s1 = step(s0, Action::Start { p: 1, t: ta() }, v)->Some_0;
    let s2 = step(s1, Action::Step { p: 1 }, v)->Some_0;
    assert(s2.runs[1].cursor == s2.recs.len() && s2.marker == Some(ta()));
    let late = seq![node_rec(seq!['a', '|', '2'])];
    assert(commit_admits(s2, late, None, false));
    assert(!commit_admits(s2, late, None, true)) by {
        assert(matches(Rec::Live(late[0]), ta(), K()) == Tri::Yes);
    }
    let s3 = step(s2, Action::Commit { recs: late, key: None, adds: Set::empty() }, v)->Some_0;
    assert(s3.runs[1].done && s3.marker == Some(ta()));
    assert(!any_checked(s3.live, ta()));
    // the final step does not rescan: the run completes and the admitted record survives it
    let s4 = step(s3, Action::Final { p: 1 }, v)->Some_0;
    assert(step(s3, Action::Final { p: 1 }, v) is Some);
    assert(s4.marker is None && !s4.runs.contains_key(1));
    assert(s4.recs[1] == Rec::Live(late[0]));
    assert(matches(s4.recs[1], ta(), K()) == Tri::Yes);
}


/// A valid completion and its neighbouring refusal: with the tenant's node live, Start is refused
/// (target_live) and nothing changes; after the erase the same redaction runs to completion, the
/// record becomes its tombstone and a content-free redaction revision is appended.
pub proof fn witness_erase_then_redact_completes() {
    let v = as_built();
    let a1: Id = seq!['a', '|', '1'];
    let row = Item::NodeRow { g: Seq::empty(), id: a1 };
    let s0 = St { recs: seq![Rec::Live(node_rec(a1))], rev: seq![1nat], nrev: 2, live: Set::empty().insert(row), ..s_two_tenants() };
    assert(has_prefix(a1, seq!['a', '|'])) by { assert(a1.subrange(0, 2) =~= seq!['a', '|']); }
    assert(checked(row, ta()));
    assert(any_checked(s0.live, ta()));
    assert(step(s0, Action::Start { p: 1, t: ta() }, v) is None);
    let s1 = step(s0, Action::Erase { t: ta() }, v)->Some_0;
    assert(content(row, ta()));
    assert(!any_checked(s1.live, ta())) by {
        assert forall|it: Item| s1.live.contains(it) implies !checked(it, ta()) by { assert(s0.live.contains(it)); assert(it == row); }
    }
    assert(!busy(s1));
    let s2 = step(s1, Action::Start { p: 1, t: ta() }, v)->Some_0;
    let s3 = step(s2, Action::Step { p: 1 }, v)->Some_0;
    assert(s3.recs[0] == tomb(node_rec(a1), 0) && s3.marker == Some(ta()) && s3.runs[1].done);
    let s4 = step(s3, Action::Final { p: 1 }, v)->Some_0;
    assert(step(s3, Action::Final { p: 1 }, v) is Some);
    assert(s4.recs.len() == 2 && s4.recs[0] == tomb(node_rec(a1), 0) && s4.recs[1] == Rec::Live(audit_rec()));
    assert(s4.marker is None && s4.cleared.contains(1));
}

/// The stricter liveness test (L1 content) refuses W2 and W3 and still lets the valid run start.
pub proof fn witness_full_check_refuses_the_gaps() {
    let v = Variant { serial: true, repaired: false, blocks: true, full_check: true };
    let g: Id = seq!['g'];
    let t2 = Target { g, m: Seq::empty() };
    let it2 = Item::TemporalOnly { g, s: seq!['x'], o: seq!['y'] };
    let s2 = St { live: Set::empty().insert(it2), ..s_two_tenants() };
    assert(content(it2, t2));
    assert(step(s2, Action::Start { p: 1, t: t2 }, v) is None);
    let t3 = Target { g: Seq::empty(), m: Seq::empty() };
    let it3 = Item::NodeRow { g: seq!['G'], id: seq!['n'] };
    let s3 = St { live: Set::empty().insert(it3), ..s_two_tenants() };
    assert(content(it3, t3));
    assert(step(s3, Action::Start { p: 1, t: t3 }, v) is None);
    let s4 = s_two_tenants();
    assert(!any_content(s4.live, ta()));
    assert(step(s4, Action::Start { p: 1, t: ta() }, v) is Some);
}

// ============================================================================ replay (replay.py)

/// The entity a record changes in GraphState: a node (by id) or a statement (by statement id).
/// Temporal records, tombstones and redaction-audit records change nothing (replay.contributes,
/// GraphState.apply ignores entity kinds other than node/rel).
pub enum Ent {
    NodeE(Id),
    StmtE(nat),
}

pub open spec fn entity(r: Rec) -> Option<Ent> {
    match r {
        Rec::Tomb { .. } => None,
        Rec::Live(l) =>
            if l.op == Op::Redact || l.op == Op::CreateTemporal { None }
            else if is_node_op(l.op) { Some(Ent::NodeE(l.id)) }
            else { Some(Ent::StmtE(l.stmt)) },
    }
}

/// GraphState.apply for one record, abstracted: the new value of the record's entity is a function
/// of the record and the entity's previous value (absent = None). Nothing else changes.
pub uninterp spec fn upd(l: Live, old: Option<int>) -> Option<int>;

pub type GState = Map<Ent, Option<int>>;

pub open spec fn get(st: GState, e: Ent) -> Option<int> {
    if st.contains_key(e) { st[e] } else { None }
}

pub open spec fn apply(st: GState, r: Rec) -> GState {
    match entity(r) {
        Some(e) => st.insert(e, upd(r->Live_0, get(st, e))),
        None => st,
    }
}

pub open spec fn replay(recs: Seq<Rec>) -> GState
    decreases recs.len(),
{
    if recs.len() == 0 { Map::empty() } else { apply(replay(recs.drop_last()), recs.last()) }
}

pub open spec fn keep(r: Rec, t: Target, k: Know) -> bool { matches(r, t, k) != Tri::Yes }

/// R1: replaying a redacted history is replaying the history without the target's records.
pub proof fn theorem_replay_skips_target(recs: Seq<Rec>, t: Target, k: Know)
    ensures
        replay(redact_all(recs, t, k)) == replay(recs.filter(|r: Rec| keep(r, t, k))),
    decreases recs.len(),
{
    if recs.len() > 0 {
        let init = recs.drop_last();
        let last = recs.last();
        theorem_replay_skips_target(init, t, k);
        let ra = redact_all(recs, t, k);
        assert(ra.drop_last() =~= redact_all(init, t, k));
        let f = |r: Rec| keep(r, t, k);
        assert(recs.filter(f) == if f(last) { init.filter(f).push(last) } else { init.filter(f) }) by {
            reveal(Seq::filter);
            assert(recs =~= init.push(last));
        }
        if keep(last, t, k) {
            assert(ra.last() == last);
            assert(init.filter(f).push(last).drop_last() =~= init.filter(f));
        } else {
            match last {
                Rec::Live(l) => { assert(ra.last() == tomb(l, (recs.len() - 1) as nat)); },
                Rec::Tomb { .. } => {},
            }
            assert(entity(ra.last()) is None);
        }
    }
}

/// Which entities belong to the target. `sg`/`truth` give each statement's graph and endpoints.
pub open spec fn ent_of_target(e: Ent, t: Target, sg: Map<nat, Id>, truth: Map<nat, (Id, Id)>) -> bool {
    match e {
        Ent::NodeE(id) => t.g.len() == 0 && (t.m.len() == 0 || has_prefix(id, t.m)),
        Ent::StmtE(x) => sg.contains_key(x) && sg[x] == t.g
            && (t.m.len() == 0 || (truth.contains_key(x) && ends_hit(truth[x], t.m))),
    }
}

/// Premise P_rec: records are consistent with the statement map (a relationship record carries its
/// statement's graph and, if it has a tuple, its statement's endpoints), and the redaction can
/// attribute every relationship record of the target graph.
pub open spec fn rec_consistent(r: Rec, t: Target, k: Know, sg: Map<nat, Id>, truth: Map<nat, (Id, Id)>) -> bool {
    match r {
        Rec::Tomb { .. } => true,
        Rec::Live(l) =>
            (is_node_op(l.op) ==> l.graph == Seq::<char>::empty())
            && ((!is_node_op(l.op) && l.op != Op::Redact && l.op != Op::CreateTemporal) ==>
                sg.contains_key(l.stmt) && sg[l.stmt] == l.graph && truth.contains_key(l.stmt)
                && (l.op == Op::CreateRel || l.op == Op::DeleteRel ==> l.ends == Some(truth[l.stmt]))
                && (is_qual_op(l.op) && t.m.len() > 0 && l.graph == t.g ==>
                    (k.redacting.contains(l.stmt) || k.ends.contains_key(l.stmt))))
            && (!is_node_op(l.op) && !is_qual_op(l.op) && l.op != Op::CreateRel && l.op != Op::DeleteRel
                && l.op != Op::CreateTemporal ==> l.op == Op::Redact),
    }
}

pub proof fn lemma_keep_iff_entity_not_target(r: Rec, t: Target, k: Know, sg: Map<nat, Id>, truth: Map<nat, (Id, Id)>)
    requires
        rec_consistent(r, t, k, sg, truth),
        agrees(t, k, truth),
        entity(r) is Some,
    ensures
        keep(r, t, k) == !ent_of_target(entity(r)->Some_0, t, sg, truth),
{
    let l = r->Live_0;
    if is_node_op(l.op) {
        if t.g.len() == 0 { assert(t.g =~= Seq::<char>::empty()); }
        assert(l.graph == Seq::<char>::empty());
    }
}

pub open spec fn restrict(st: GState, t: Target, sg: Map<nat, Id>, truth: Map<nat, (Id, Id)>) -> GState {
    st.restrict(st.dom().filter(|e: Ent| !ent_of_target(e, t, sg, truth)))
}

/// R2: the target's records only change the target's entities and the others only theirs, so
/// replaying without the target's records gives the full replay with the target's entities removed.
pub proof fn theorem_replay_independence(recs: Seq<Rec>, t: Target, k: Know, sg: Map<nat, Id>, truth: Map<nat, (Id, Id)>)
    requires
        agrees(t, k, truth),
        forall|i: int| 0 <= i < recs.len() ==> rec_consistent(#[trigger] recs[i], t, k, sg, truth),
    ensures
        replay(recs.filter(|r: Rec| keep(r, t, k))) == restrict(replay(recs), t, sg, truth),
    decreases recs.len(),
{
    let f = |r: Rec| keep(r, t, k);
    if recs.len() == 0 {
        assert(recs.filter(f) =~= Seq::<Rec>::empty()) by { reveal(Seq::filter); }
        assert(restrict(replay(recs), t, sg, truth) =~= Map::<Ent, Option<int>>::empty());
    } else {
        let init = recs.drop_last();
        let last = recs.last();
        assert forall|i: int| 0 <= i < init.len() implies rec_consistent(#[trigger] init[i], t, k, sg, truth) by {
            assert(init[i] == recs[i]);
        }
        theorem_replay_independence(init, t, k, sg, truth);
        assert(rec_consistent(last, t, k, sg, truth)) by { assert(last == recs[recs.len() - 1]); }
        assert(recs.filter(f) == if f(last) { init.filter(f).push(last) } else { init.filter(f) }) by {
            reveal(Seq::filter);
            assert(recs =~= init.push(last));
        }
        let full0 = replay(init);
        let kept0 = replay(init.filter(f));
        assert(kept0 == restrict(full0, t, sg, truth));
        match entity(last) {
            None => {
                if f(last) {
                    assert(init.filter(f).push(last).drop_last() =~= init.filter(f));
                }
            },
            Some(e) => {
                lemma_keep_iff_entity_not_target(last, t, k, sg, truth);
                let full1 = replay(recs);
                assert(full1 == full0.insert(e, upd(last->Live_0, get(full0, e))));
                if f(last) {
                    assert(init.filter(f).push(last).drop_last() =~= init.filter(f));
                    assert(!ent_of_target(e, t, sg, truth));
                    assert(get(kept0, e) == get(full0, e));
                    assert(replay(recs.filter(f)) =~= restrict(full1, t, sg, truth));
                } else {
                    assert(ent_of_target(e, t, sg, truth));
                    assert(replay(recs.filter(f)) =~= restrict(full1, t, sg, truth));
                }
            },
        }
    }
}

/// verify() after erasure and redaction is "equal" — under named premises:
///   P_unrecorded: before the erasure the canonical tables equal the ledger's replay (no unrecorded
///                 writes; verify() was "equal")
///   P_erase:      the erasure removed exactly the target's entities from what read_canonical sees
///   P_rec/P_ends: every record is consistent with the statement map and attributable
/// R1 + R2 give replay(redacted) == canonical.
pub proof fn theorem_verify_equal_after_redaction(
    recs: Seq<Rec>, t: Target, k: Know, sg: Map<nat, Id>, truth: Map<nat, (Id, Id)>, canonical_after: GState,
)
    requires
        agrees(t, k, truth),
        forall|i: int| 0 <= i < recs.len() ==> rec_consistent(#[trigger] recs[i], t, k, sg, truth),
        canonical_after == restrict(replay(recs), t, sg, truth),
    ensures
        replay(redact_all(recs, t, k)) == canonical_after,
{
    theorem_replay_skips_target(recs, t, k);
    theorem_replay_independence(recs, t, k, sg, truth);
}


// ============================================================================ commit admission (Ledger.CommitInTxn)

/// The outcome of Graph.KG.Ledger.CommitInTxn. Check order (Ledger.cls header, spec 213 FR-019):
/// lock → state → idempotency → (spec 256) redacted key → expected_head → size/empty → apply →
/// (spec 256) BlocksCommit → write.
pub enum Outcome {
    LockTimeout,
    NotEnabled,
    Disabled,
    Replay { seq: nat },
    IdempotencyConflict,
    IdempotencyRedacted,
    UnknownHead,
    StaleHead,
    Empty,
    TooLarge,
    FailedOp,
    RedactionInProgress,
    Committed,
}

pub struct CommitIn {
    pub locked: bool,
    pub state_enabled: bool,
    pub never_enabled: bool,
    pub key: Option<int>,
    pub fingerprint: int,
    /// ^IVG.Ledger("idem", key) = $LB(seq, fingerprint)
    pub bound: Option<(nat, int)>,
    pub key_redacted: bool,
    pub expected_head: Option<nat>,
    pub head_known: bool,
    pub head: nat,
    pub n_ops: nat,
    pub max_ops: nat,
    pub apply_ok: bool,
    pub blocked: bool,
}

pub open spec fn commit_outcome(c: CommitIn) -> Outcome {
    if !c.locked { Outcome::LockTimeout }
    else if c.never_enabled { Outcome::NotEnabled }
    else if !c.state_enabled { Outcome::Disabled }
    else if c.key is Some && c.bound is Some {
        if c.bound->Some_0.1 == c.fingerprint { Outcome::Replay { seq: c.bound->Some_0.0 } } else { Outcome::IdempotencyConflict }
    }
    else if c.key is Some && c.key_redacted { Outcome::IdempotencyRedacted }
    else if c.expected_head is Some && !c.head_known { Outcome::UnknownHead }
    else if c.expected_head is Some && c.expected_head->Some_0 != c.head { Outcome::StaleHead }
    else if c.n_ops == 0 { Outcome::Empty }
    else if c.n_ops > c.max_ops { Outcome::TooLarge }
    else if !c.apply_ok { Outcome::FailedOp }
    else if c.blocked { Outcome::RedactionInProgress }
    else { Outcome::Committed }
}

/// Only Committed writes a revision; every other outcome leaves the ledger and the tables as they were
/// (the refused level is rolled back: Ledger.Commit TROLLBACK 1). Replay returns the bound revision.
pub open spec fn writes(o: Outcome) -> bool { o == Outcome::Committed }

/// FR-019 precedence: a retry with a bound key and the same changeset replays, whatever the head,
/// size or redaction marker say now — and never writes.
pub proof fn theorem_retry_replays_first(c: CommitIn)
    requires c.locked, !c.never_enabled, c.state_enabled, c.key is Some, c.bound is Some, c.bound->Some_0.1 == c.fingerprint,
    ensures commit_outcome(c) == (Outcome::Replay { seq: c.bound->Some_0.0 }), !writes(commit_outcome(c)),
{
}

/// Spec 256: an unbound key whose revision was redacted is refused before the head check and before
/// anything is applied; nothing is written whatever the changeset holds.
pub proof fn theorem_redacted_key_refused_before_apply(c: CommitIn)
    requires c.locked, !c.never_enabled, c.state_enabled, c.key is Some, c.bound is None, c.key_redacted,
    ensures commit_outcome(c) == Outcome::IdempotencyRedacted, !writes(commit_outcome(c)),
{
}

/// A write happens only when every guard passed, including BlocksCommit.
pub proof fn theorem_commit_writes_only_when_admitted(c: CommitIn)
    ensures writes(commit_outcome(c)) ==> c.locked && c.state_enabled && !c.never_enabled
        && (c.key is Some ==> c.bound is None && !c.key_redacted)
        && (c.expected_head is Some ==> c.head_known && c.expected_head->Some_0 == c.head)
        && 0 < c.n_ops <= c.max_ops && c.apply_ok && !c.blocked,
{
}

/// The bridge to the lifecycle model: commit_admits (used by `step`) is exactly "this outcome writes"
/// for a caller that holds the lock, does not use expected_head and stays within max_ops.
pub proof fn lemma_commit_admits_matches_outcome(s: St, new: Seq<Live>, key: Option<int>, fp: int, max_ops: nat)
    requires
        new.len() <= max_ops,
    ensures ({
        let blocked = match s.marker {
            Some(t) => exists|j: int| 0 <= j < new.len() && matches(Rec::Live(#[trigger] new[j]), t, K()) == Tri::Yes,
            None => false,
        };
        let c = CommitIn {
            locked: true, state_enabled: s.enabled, never_enabled: false, key, fingerprint: fp,
            bound: match key { Some(k) => if s.idem.contains_key(k) { Some((s.idem[k], fp + 1)) } else { None }, None => None },
            key_redacted: match key { Some(k) => s.idem_redacted.contains(k), None => false },
            expected_head: None, head_known: true, head: s.nrev, n_ops: new.len(), max_ops, apply_ok: true, blocked,
        };
        writes(commit_outcome(c)) == commit_admits(s, new, key, true)
    }),
{
}


// ============================================================================ per-call knowledge (review R1-1)

/// What LedgerRedact.Matches knows on one Redact() call, as product state rather than the constant K():
///   pre      — PrePass over the create_rel/delete_rel records of the target graph that are still live
///              (a tombstoned create_rel no longer gives its endpoints)
///   live     — the ^IVG.Ledger("stmt") map (the erase removed the target's entries)
///   redacting — ^IVG.Ledger("redacting","stmt"): statements whose create/delete this target's runs
///              tombstoned; it lives under the marker and ANY run's FinalInLock kills it
pub open spec fn call_knowledge(pre: Map<nat, (Id, Id)>, live: Map<nat, (Id, Id)>, redacting: Set<nat>) -> Know {
    Know { redacting, ends: live.union_prefer_right(pre) }
}

/// Classification fact only (review round 2 core R2-2): WITH the statement in the redacting set, Matches attributes a
/// qualifier record of it to the target even though PrePass no longer sees the tombstoned create_rel. That the set
/// survives a pause under serialised redactions is an argument from the code (no other target's final step can run
/// while the marker exists), not a theorem: the lifecycle state machine still uses the constant K(). Resume of a
/// prefix target is therefore OBSERVED natively (redaction_prefix_resume), not proved.
pub proof fn lemma_serial_resume_keeps_attribution(t: Target, stmt: nat, q: Live)
    requires
        t.m.len() > 0,
        q.op == Op::SetQual,
        q.stmt == stmt,
        q.graph == t.g,
    ensures
        matches(Rec::Live(q), t, call_knowledge(Map::empty(), Map::empty(), Set::empty().insert(stmt))) == Tri::Yes,
{
}

/// Classification fact only: WITHOUT the redacting set (killed with the marker by another target's final step, which
/// is possible only through bug-001's race), with the create_rel tombstoned (PrePass skips it) and the statement entry
/// erased, Matches answers Unknown for the qualifier record, which then stays in clear under a complete receipt. This is
/// not a trace of the lifecycle state machine (review round 2 core R2-2).
pub proof fn witness_race_then_resume_loses_attribution(t: Target, stmt: nat, q: Live)
    requires
        t.m.len() > 0,
        q.op == Op::SetQual,
        q.stmt == stmt,
        q.graph == t.g,
    ensures
        matches(Rec::Live(q), t, call_knowledge(Map::empty(), Map::empty(), Set::empty())) == Tri::Unknown,
{
}


// ============================================================================ W5: prefix erase misses temporal-only events

/// W5 (review round 2 core R2-1; native `erasure_prefix_temporal_only`): a tenant event of a temporal-only
/// predicate whose endpoints have no node row survives the documented erase-by-prefix; the redaction that follows
/// starts (LiveRows sees nothing) and its record becomes a tombstone while the event is still in the index.
pub proof fn witness_prefix_erase_leaves_temporal_only_content() {
    let v = as_built();
    let ev = Item::TemporalOnly { g: Seq::empty(), s: seq!['a', '|', 'x'], o: seq!['a', '|', 'y'] };
    let r = Live { op: Op::CreateTemporal, id: Seq::empty(), stmt: 0, ends: Some((seq!['a', '|', 'x'], seq!['a', '|', 'y'])),
                   graph: Seq::empty(), payload: 3, flags: 0 };
    let s0 = St { recs: seq![Rec::Live(r)], rev: seq![1nat], nrev: 2, live: Set::empty().insert(ev), ..s_two_tenants() };
    assert(has_prefix(seq!['a', '|', 'x'], seq!['a', '|'])) by { assert(seq!['a', '|', 'x'].subrange(0, 2) =~= seq!['a', '|']); }
    assert(!erased_in(s0.live, ev, ta())) by {
        assert(!s0.live.contains(Item::NodeRow { g: Seq::empty(), id: seq!['a', '|', 'x'] }));
        assert(!s0.live.contains(Item::NodeRow { g: Seq::empty(), id: seq!['a', '|', 'y'] }));
    }
    let s1 = step(s0, Action::Erase { t: ta() }, v)->Some_0;
    assert(s1.live.contains(ev) && content(ev, ta()));
    assert(!any_checked(s1.live, ta())) by {
        assert forall|i: Item| s1.live.contains(i) implies !checked(i, ta()) by { assert(s0.live.contains(i)); assert(i == ev); }
    }
    assert(!busy(s1));
    let s2 = step(s1, Action::Start { p: 1, t: ta() }, v)->Some_0;
    assert(step(s1, Action::Start { p: 1, t: ta() }, v) is Some);
    assert(matches(s2.recs[0], ta(), K()) == Tri::Yes);
    let s3 = step(s2, Action::Step { p: 1 }, v)->Some_0;
    assert(s3.recs[0] == tomb(r, 0) && s3.live.contains(ev));
}


// ============================================================================ W6: an orphan property row blocks prefix redaction

/// W6 (review round 3 R3-4): a tenant's property row with no node row (post_commit_properties write rdf_props
/// directly; the table has no foreign key) is not selected by the prefix erase, which collects ids from node rows,
/// but LiveRows counts it. Every prefix redaction of the tenant is then refused, and erasing by prefix again changes
/// nothing; only an explicit-id erase or raw SQL clears it.
pub proof fn witness_orphan_prop_row_blocks_prefix_redaction() {
    let v = as_built();
    let prop = Item::PropRow { g: Seq::empty(), id: seq!['a', '|', 'x'] };
    let s0 = St { recs: seq![Rec::Live(node_rec(seq!['a', '|', '1']))], rev: seq![1nat], nrev: 2,
                  live: Set::empty().insert(prop), ..s_two_tenants() };
    assert(has_prefix(seq!['a', '|', 'x'], seq!['a', '|'])) by { assert(seq!['a', '|', 'x'].subrange(0, 2) =~= seq!['a', '|']); }
    assert(!s0.live.contains(Item::NodeRow { g: Seq::empty(), id: seq!['a', '|', 'x'] }));
    assert(!erased_in(s0.live, prop, ta()));
    let s1 = step(s0, Action::Erase { t: ta() }, v)->Some_0;
    assert(s1.live.contains(prop));
    assert(checked(prop, ta()));
    assert(any_checked(s1.live, ta()));
    assert(step(s1, Action::Start { p: 1, t: ta() }, v) is None);
    // erasing by prefix again changes nothing
    let s2 = step(s1, Action::Erase { t: ta() }, v)->Some_0;
    assert(s2.live.contains(prop));
    assert(step(s2, Action::Start { p: 1, t: ta() }, v) is None);
}


/// Erase frame (ADR-0004 / erasure.scope: an erase of graph g never touches another graph's content; review round 3
/// R3-5, whose scratch check showed a graph-blind erase passing every other obligation).
pub open spec fn item_graph(it: Item) -> Id {
    match it {
        Item::NodeRow { g, .. } => g,
        Item::PropRow { g, .. } => g,
        Item::EdgeRow { g, .. } => g,
        Item::TemporalOnly { g, .. } => g,
    }
}

pub proof fn lemma_erase_stays_in_target_graph(live: Set<Item>, it: Item, t: Target)
    ensures erased_in(live, it, t) ==> item_graph(it) == t.g,
{
}

pub proof fn lemma_erase_keeps_other_graphs(s: St, t: Target, it: Item)
    requires s.live.contains(it), item_graph(it) != t.g,
    ensures step(s, Action::Erase { t }, as_built())->Some_0.live.contains(it),
{
    lemma_erase_stays_in_target_graph(s.live, it, t);
}

} // verus!
