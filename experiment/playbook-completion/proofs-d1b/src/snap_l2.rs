//! Module 18 (snapshot), L2: `save_snapshot` / `restore_snapshot` over the stored layout at pin 3eaa79cf, with the
//! ledger globals, the redaction, concurrent writers and the archive files; refinement of `snap_l1` for every step,
//! the invariant, and six broken-implementation controls.
//!
//! State (production names):
//! - `rows`   committed content of every store (Graph_KG tables, `kg_emb_*` / `kg_eemb_*` routes, `^KG`, `^NKG`, ...)
//! - `cur`    what a reader sees: the committed rows plus an open writer's uncommitted ones (SQL READ UNCOMMITTED and
//!            global reads, SYS-P2; live c18-live-dirty-export)
//! - `g`      `^IVG.Ledger("head" | "idBySeq" | "rec")` and `^Graph.KG.LedgerRevisionD(seq)` (IdKey Seq,
//!            LedgerRevision.cls:44: a second row at a seq is refused, Ledger.cls:538-556)
//! - `scope`  reviewed design only: the tenants a completed redaction removed, kept outside what a snapshot archives
//!            and what a restore writes (the pin keeps `redactedRev`/`idemRedacted` marks, LedgerRedact.cls:24-25,
//!            which no restore reads: snapshot.py has no reference to redaction)
//! - `w`      one open writer transaction (its uncommitted creates)
//! - `x`      a `save_snapshot` in flight: one `SELECT *` / global walk per store in sequence, then the ledger
//!            globals (snapshot.py:864-1034, 395-409), then the ZIP
//! - `r`      a replacing `restore_snapshot` in flight: refusal checks (snapshot.py:1095-1129), `erase_all()` (one
//!            transaction that keeps the ledger's records and head, Eraser.cls:806-812), the archive's rows and
//!            globals, the archive's ledger globals set node by node over the live ones (snapshot.py:1554-1588,
//!            1654-1692), the answer
//! - `files`  the archive files (ZIP: sql/*.ndjson, globals/*.ndjson incl. globals/IVG.Ledger.ndjson)
//!
//! **Design** (reviewed, the working answers and the findings' remedies):
//! - R18-1 (HD-1802): an export gate: the exporter holds it exclusively for the whole save, every writer holds it
//!   shared for its transaction;
//! - R18-2 (HD-1801): a restore is refused before any write unless the live history is a prefix of the archive's;
//!   the pin's overlay of the archive's ledger is kept (under the prefix it is a wholesale replacement,
//!   `lemma_overlay`);
//! - R18-3: a restore holds the same gate exclusively (no writer or save overlaps it);
//! - R18-4 (HD-1801, F-C1304): a redaction keeps its scope; a restore re-applies it to the archive's rows and
//!   records; the receipt names IVG's archives as out of reach;
//! - R18-5 (F-C1802): a global line IRIS refuses is counted in `failed_rows`;
//! - R18-6 (F-C1804): the export plan covers every store, edge-vector routes included.
//! At the pin none of R18-1..R18-6 holds. Each control puts back one pin decision.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::snap_l1::*;

verus! {

/// `^IVG.Ledger` (head, idBySeq, rec) and the revision rows `^Graph.KG.LedgerRevisionD(seq)`.
#[verifier::ext_equal]
pub struct G2 { pub led: Led, pub rev: Set<nat> }

/// An archive file: its content lines and its ledger globals.
#[verifier::ext_equal]
pub struct AF { pub lines: Set<Item>, pub g: G2 }

/// A save in flight: stores read so far (`stage`), the lines collected, the ledger globals once read.
pub struct XP { pub id: nat, pub stage: nat, pub part: Set<Item>, pub g: Option<G2> }

pub enum RPh { Erased, Loaded, LedgerSet }
/// A restore in flight, with the namespace's pre-restore content and ledger (the abstraction's view until it ends).
pub struct RP { pub id: nat, pub ph: RPh, pub failed: Set<Item>, pub pre_rows: Set<Item>, pub pre_g: G2 }

#[verifier::ext_equal]
pub struct SS2 {
    pub rows: Set<Item>,
    pub cur: Set<Item>,
    pub g: G2,
    pub scope: Set<int>,
    pub w: Option<Set<Item>>,
    pub x: Option<XP>,
    pub r: Option<RP>,
    pub files: Map<nat, AF>,
}

pub enum SL2 {
    /// Ledger.Commit, one transaction (module 11's L2 step).
    Commit { items: Set<Item>, id: int },
    /// The revision row's IdKey exists: "revision row save failed", rolled back (Ledger.cls:538-556).
    CommitRefused { items: Set<Item>, id: int },
    /// A writer transaction creates rows (visible before commit).
    WOpen { items: Set<Item> },
    WEnd { commit: bool, items: Set<Item> },
    /// delete_nodes_by_prefix / erase_graph of a tenant, one transaction.
    Erase { ten: int },
    /// ledger.redact of a tenant: its records lose its content; `oor` is the receipt's out-of-reach archives.
    Redact { ten: int, oor: Set<nat> },
    XStart { id: nat },
    /// One store of the export plan.
    XRead,
    /// The ledger globals.
    XLedger,
    /// The ZIP is written.
    XEnd { id: nat, lines: Set<Item>, g: G2 },
    /// A refusal before any write (layout, strict mode, caller transaction; reviewed: also a history that is not a
    /// prefix of the archive's).
    RRefuse { id: nat },
    /// The checks pass; erase_all.
    RBegin { id: nat },
    /// The archive's rows and globals; IRIS refuses the global lines in `bad` (a null subscript, <SUBSCRIPT>).
    RLoad { bad: Set<Item> },
    /// The archive's ledger globals, set over the live ones.
    RLedger,
    /// The answer, with `failed_rows`.
    REnd { id: nat, failed: Set<Item> },
}

pub open spec fn f1801p() -> bool { cfg!(feature = "control_f1801_no_prefix_check") }
pub open spec fn f1801u() -> bool { cfg!(feature = "control_f1801_restore_unredacts") }
pub open spec fn fc1304() -> bool { cfg!(feature = "control_fc1304_receipt_omits_archives") }
pub open spec fn fc1801() -> bool { cfg!(feature = "control_fc1801_dirty_export") }
pub open spec fn fc1802() -> bool { cfg!(feature = "control_fc1802_swallowed_line") }
pub open spec fn fc1804() -> bool { cfg!(feature = "control_fc1804_edge_routes_omitted") }

pub open spec fn store_of(c: Set<Item>, k: int) -> Set<Item> { c.filter(|i: Item| i.0 == k) }
/// The export plan: every store (reviewed); the pin's routed plan keeps node routes only (snapshot.py:299-344).
pub open spec fn planned(k: int) -> bool { !(fc1804() && k == 2) }
pub open spec fn read_upto(c: Set<Item>, n: nat) -> Set<Item> { c.filter(|i: Item| 0 <= i.0 < n && planned(i.0)) }
pub open spec fn stores_ok(c: Set<Item>) -> bool { forall|i: Item| #[trigger] c.contains(i) ==> 0 <= i.0 <= 3 }

/// A writer may run: no restore holds the gate (R18-3) and (reviewed, R18-1) no save does.
pub open spec fn writer_may(s: SS2) -> bool { s.r is None && (fc1801() || s.x is None) }

pub open spec fn new_items(s: SS2, items: Set<Item>) -> bool {
    items.disjoint(s.cur) && none_of(s.scope, items) && stores_ok(items)
}

pub open spec fn commit_g(g: G2, items: Set<Item>, id: int) -> G2 {
    G2 { led: Led { head: g.led.head + 1, ids: g.led.ids.insert(g.led.head + 1, id),
                    recs: g.led.recs.insert(g.led.head + 1, items) },
         rev: g.rev.insert(g.led.head + 1) }
}

/// The archived records the restore writes: reviewed, with the live redactions re-applied (R18-4).
pub open spec fn arch_recs(a: G2, scope: Set<int>) -> Map<nat, Set<Item>> {
    if f1801u() { a.led.recs } else { scrub_recs(a.led.recs, scope) }
}

/// Every archived ledger node set over the live one, nothing killed (snapshot.py:1654-1692).
pub open spec fn overlay(live: G2, a: G2, scope: Set<int>) -> G2 {
    G2 { led: Led { head: a.led.head, ids: live.led.ids.union_prefer_right(a.led.ids),
                    recs: live.led.recs.union_prefer_right(arch_recs(a, scope)) },
         rev: live.rev.union(a.rev) }
}

/// The rows and globals the restore writes: reviewed, without the redacted tenants (R18-4).
pub open spec fn loaded(lines: Set<Item>, bad: Set<Item>, scope: Set<int>) -> Set<Item> {
    if f1801u() { lines.difference(bad) } else { scrub(lines.difference(bad), scope) }
}

/// The receipt's out-of-reach archives: reviewed, every archive file (R18-4); the pin names none
/// (LedgerRedact.cls:504-509: exports, journals, backups).
pub open spec fn receipt(s: SS2) -> Set<nat> { if fc1304() { Set::empty() } else { s.files.dom() } }

pub open spec fn led0() -> Led { Led { head: 0, ids: Map::empty(), recs: Map::empty() } }

pub open spec fn init2(s: SS2) -> bool {
    &&& s.rows == Set::<Item>::empty() && s.cur == Set::<Item>::empty() && s.scope == Set::<int>::empty()
    &&& s.g == (G2 { led: led0(), rev: Set::empty() })
    &&& s.w is None && s.x is None && s.r is None && s.files == Map::<nat, AF>::empty()
}

pub open spec fn step2(s: SS2, l: SL2, t: SS2) -> bool {
    match l {
        SL2::Commit { items, id } => {
            &&& writer_may(s) && new_items(s, items) && !s.g.rev.contains(s.g.led.head + 1)
            &&& t == SS2 { rows: s.rows.union(items), cur: s.cur.union(items), g: commit_g(s.g, items, id), ..s }
        },
        SL2::CommitRefused { items, id } =>
            writer_may(s) && new_items(s, items) && s.g.rev.contains(s.g.led.head + 1) && t == s,
        SL2::WOpen { items } =>
            writer_may(s) && s.w is None && new_items(s, items) && t == SS2 { cur: s.cur.union(items), w: Some(items), ..s },
        SL2::WEnd { commit, items } => {
            &&& s.w == Some(items)
            &&& t == SS2 { rows: if commit { s.rows.union(items) } else { s.rows },
                           cur: if commit { s.cur } else { s.cur.difference(items) }, w: None, ..s }
        },
        SL2::Erase { ten } => {
            &&& writer_may(s)
            // the eraser's deletes wait for an open writer's row locks on the tenant (premise P-S3)
            &&& match s.w { Some(wi) => not_ten(wi, ten) == wi, None => true }
            &&& t == SS2 { rows: not_ten(s.rows, ten), cur: not_ten(s.cur, ten), ..s }
        },
        SL2::Redact { ten, oor } => {
            &&& writer_may(s) && not_ten(s.cur, ten) == s.cur && oor == receipt(s)
            &&& t == SS2 { g: G2 { led: Led { recs: redact_recs(s.g.led.recs, ten), ..s.g.led }, ..s.g },
                           scope: s.scope.insert(ten), ..s }
        },
        SL2::XStart { id } => {
            &&& s.x is None && s.r is None && (fc1801() || s.w is None) && !s.files.contains_key(id)
            &&& t == SS2 { x: Some(XP { id, stage: 0, part: Set::empty(), g: None }), ..s }
        },
        SL2::XRead => match s.x {
            Some(xp) => xp.stage < 4 && t == SS2 { x: Some(XP { stage: xp.stage + 1,
                part: if planned(xp.stage as int) { xp.part.union(store_of(s.cur, xp.stage as int)) } else { xp.part },
                ..xp }), ..s },
            None => false,
        },
        SL2::XLedger => match s.x {
            Some(xp) => xp.stage == 4 && xp.g is None && t == SS2 { x: Some(XP { g: Some(s.g), ..xp }), ..s },
            None => false,
        },
        SL2::XEnd { id, lines, g } => match s.x {
            Some(xp) => xp.id == id && xp.stage == 4 && xp.g == Some(g) && lines == xp.part
                && t == SS2 { files: s.files.insert(id, AF { lines, g }), x: None, ..s },
            None => false,
        },
        SL2::RRefuse { id } => s.files.contains_key(id) && s.r is None && t == s,
        SL2::RBegin { id } => {
            &&& s.files.contains_key(id) && s.r is None && s.x is None && s.w is None
            &&& (f1801p() || prefix(s.g.led, s.files[id].g.led))
            &&& t == SS2 { rows: Set::empty(), cur: Set::empty(),
                           r: Some(RP { id, ph: RPh::Erased, failed: Set::empty(), pre_rows: s.rows, pre_g: s.g }), ..s }
        },
        SL2::RLoad { bad } => match s.r {
            Some(rp) => rp.ph is Erased && s.files.contains_key(rp.id) && bad.subset_of(store_of(s.files[rp.id].lines, 3))
                && t == SS2 { rows: loaded(s.files[rp.id].lines, bad, s.scope), cur: loaded(s.files[rp.id].lines, bad, s.scope),
                              r: Some(RP { ph: RPh::Loaded, failed: if fc1802() { Set::empty() } else { bad }, ..rp }), ..s },
            None => false,
        },
        SL2::RLedger => match s.r {
            Some(rp) => rp.ph is Loaded && s.files.contains_key(rp.id)
                && t == SS2 { g: overlay(s.g, s.files[rp.id].g, s.scope), r: Some(RP { ph: RPh::LedgerSet, ..rp }), ..s },
            None => false,
        },
        SL2::REnd { id, failed } => match s.r {
            Some(rp) => rp.ph is LedgerSet && rp.id == id && failed == rp.failed && t == SS2 { r: None, ..s },
            None => false,
        },
    }
}

// ------------------------------------------------------------------------------------------------ invariant

/// The ledger layout holds one history, and the revision rows are exactly its seqs.
pub open spec fn wf2(g: G2) -> bool { wf(g.led) && forall|q: nat| #[trigger] g.rev.contains(q) <==> 1 <= q <= g.led.head }

pub open spec fn inv_cur(s: SS2) -> bool {
    match s.w { Some(wi) => s.cur == s.rows.union(wi) && wi.disjoint(s.rows), None => s.cur == s.rows }
}
pub open spec fn inv_red(s: SS2) -> bool {
    none_of(s.scope, s.cur) && recs_none_of(s.scope, s.g.led.recs) && stores_ok(s.cur)
}
pub open spec fn inv_files(s: SS2) -> bool {
    forall|a: nat| #[trigger] s.files.contains_key(a) ==> wf2(s.files[a].g) && stores_ok(s.files[a].lines)
}
/// A save in flight holds the gate: no writer, no restore; it has collected the committed rows of the stores read.
pub open spec fn inv_x(s: SS2) -> bool {
    match s.x {
        Some(xp) => {
            &&& s.w is None && s.r is None && !s.files.contains_key(xp.id) && xp.stage <= 4
            &&& xp.part == read_upto(s.rows, xp.stage)
            &&& match xp.g { Some(g) => xp.stage == 4 && g == s.g, None => true }
        },
        None => true,
    }
}
/// A restore in flight holds the gate; the live history is a prefix of the archive's; what it has written so far.
pub open spec fn inv_r(s: SS2) -> bool {
    match s.r {
        Some(rp) => {
            let a = s.files[rp.id];
            &&& s.w is None && s.x is None && s.files.contains_key(rp.id)
            &&& prefix(rp.pre_g.led, a.g.led) && wf2(rp.pre_g)
            &&& none_of(s.scope, rp.pre_rows) && recs_none_of(s.scope, rp.pre_g.led.recs) && stores_ok(rp.pre_rows)
            &&& s.cur == s.rows
            &&& match rp.ph {
                RPh::Erased => s.rows == Set::<Item>::empty() && rp.failed == Set::<Item>::empty() && s.g == rp.pre_g,
                RPh::Loaded => s.rows == scrub(a.lines.difference(rp.failed), s.scope) && rp.failed.subset_of(a.lines)
                    && s.g == rp.pre_g,
                RPh::LedgerSet => s.rows == scrub(a.lines.difference(rp.failed), s.scope) && rp.failed.subset_of(a.lines)
                    && s.g == overlay(rp.pre_g, a.g, s.scope),
            }
        },
        None => true,
    }
}

pub open spec fn inv18(s: SS2) -> bool {
    inv_cur(s) && wf2(s.g) && inv_red(s) && inv_files(s) && inv_x(s) && inv_r(s)
}

pub struct SnapL2;

impl Contract for SnapL2 {
    type S = SS2;
    type L = SL2;
    open spec fn init(s: SS2) -> bool { init2(s) }
    open spec fn next(s: SS2, l: SL2, t: SS2) -> bool { inv18(s) && step2(s, l, t) }
}

pub struct SnapRaw;

impl Contract for SnapRaw {
    type S = SS2;
    type L = SL2;
    open spec fn init(s: SS2) -> bool { init2(s) }
    open spec fn next(s: SS2, l: SL2, t: SS2) -> bool { step2(s, l, t) }
}

// ------------------------------------------------------------------------------------------------ the abstraction

pub open spec fn absf(f: AF) -> Arch { Arch { content: f.lines, led: f.g.led } }
pub open spec fn arch_of(files: Map<nat, AF>) -> Map<nat, Arch> { files.map_values(|f: AF| absf(f)) }

/// While a restore is in flight L1 sees the namespace as it was; L1's restore happens when it answers.
pub open spec fn abs18(s: SS2) -> SS1 {
    match s.r {
        Some(rp) => SS1 { content: rp.pre_rows, led: rp.pre_g.led, red: s.scope, archives: arch_of(s.files) },
        None => SS1 { content: s.rows, led: s.g.led, red: s.scope, archives: arch_of(s.files) },
    }
}

pub open spec fn lab18(l: SL2) -> Option<SL1> {
    match l {
        SL2::Commit { items, id } => Some(SL1::Commit { items, id }),
        SL2::CommitRefused { items, id } => None,
        SL2::WOpen { items } => None,
        SL2::WEnd { commit, items } => if commit { Some(SL1::Write { items }) } else { None },
        SL2::Erase { ten } => Some(SL1::Erase { ten }),
        SL2::Redact { ten, oor } => Some(SL1::Redact { ten, oor }),
        SL2::XStart { id } => None,
        SL2::XRead => None,
        SL2::XLedger => None,
        SL2::XEnd { id, lines, g } => Some(SL1::Save { id, arch: Arch { content: lines, led: g.led } }),
        SL2::RRefuse { id } => Some(SL1::Restore { id, out: ROut::Refused }),
        SL2::RBegin { id } => None,
        SL2::RLoad { bad } => None,
        SL2::RLedger => None,
        SL2::REnd { id, failed } => Some(SL1::Restore { id, out: ROut::Done { failed } }),
    }
}

// ------------------------------------------------------------------------------------------------ lemmas

proof fn lemma_arch_of_insert(files: Map<nat, AF>, id: nat, f: AF)
    ensures arch_of(files.insert(id, f)) == arch_of(files).insert(id, absf(f)),
{
    assert(arch_of(files.insert(id, f)) =~= arch_of(files).insert(id, absf(f)));
}

proof fn lemma_wf2_commit(g: G2, items: Set<Item>, id: int)
    requires wf2(g),
    ensures wf2(commit_g(g, items, id)),
{
}

/// Under the prefix, the pin's overlay of the archive's ledger is the archive's ledger (with the redactions the
/// reviewed restore re-applies): a wholesale replacement.
pub proof fn lemma_overlay(live: G2, a: G2, scope: Set<int>)
    requires wf2(live), wf2(a), prefix(live.led, a.led),
    ensures
        overlay(live, a, scope).led == (Led { recs: arch_recs(a, scope), ..a.led }),
        overlay(live, a, scope).rev == a.rev,
        wf2(overlay(live, a, scope)),
{
    let o = overlay(live, a, scope);
    assert(arch_recs(a, scope).dom() =~= a.led.recs.dom());
    assert(o.led.ids =~= a.led.ids) by {
        assert forall|q: nat| #[trigger] live.led.ids.contains_key(q) implies a.led.ids.contains_key(q) by {}
    }
    assert(o.led.recs =~= arch_recs(a, scope)) by {
        assert forall|q: nat| #[trigger] live.led.recs.contains_key(q) implies a.led.recs.contains_key(q) by {}
    }
    assert(o.rev =~= a.rev) by {
        assert forall|q: nat| #[trigger] live.rev.contains(q) implies a.rev.contains(q) by {}
    }
}

proof fn lemma_read_all(s: SS2)
    requires inv18(s), s.x is Some, stores_ok(s.rows),
    ensures read_upto(s.rows, 4) =~= s.rows,
{
    assert forall|i: Item| #[trigger] s.rows.contains(i) implies read_upto(s.rows, 4).contains(i) by {
        // every store is in the export plan (control F-C1804 fails here: the plan leaves out edge-vector routes)
        assert(planned(i.0));
    }
}

// ------------------------------------------------------------------------------------------------ writer steps

proof fn lemma_commit(s: SS2, items: Set<Item>, id: int, t: SS2)
    requires inv18(s), step2(s, SL2::Commit { items, id }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::Commit { items, id }), abs18(t)),
{
    // the commit waits for a save to finish (the export gate; control F-C1801 fails here)
    assert(s.x is None);
    lemma_wf2_commit(s.g, items, id);
    if let Some(wi) = s.w {
        assert(t.cur =~= t.rows.union(wi));
        assert(wi.disjoint(t.rows));
    } else {
        assert(t.cur =~= t.rows);
    }
    assert forall|q: nat, i: Item| t.g.led.recs.contains_key(q) && #[trigger] t.g.led.recs[q].contains(i)
        implies !t.scope.contains(i.1) by {
        if q != s.g.led.head + 1 { assert(s.g.led.recs.contains_key(q) && s.g.led.recs[q].contains(i)); }
    }
    assert(abs18(t) == SS1 { content: abs18(s).content.union(items),
        led: Led { head: abs18(s).led.head + 1, ids: abs18(s).led.ids.insert(abs18(s).led.head + 1, id),
                   recs: abs18(s).led.recs.insert(abs18(s).led.head + 1, items) }, ..abs18(s) });
}

proof fn lemma_commit_refused(s: SS2, items: Set<Item>, id: int, t: SS2)
    requires inv18(s), step2(s, SL2::CommitRefused { items, id }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::CommitRefused { items, id }), abs18(t)),
{
}

proof fn lemma_wopen(s: SS2, items: Set<Item>, t: SS2)
    requires inv18(s), step2(s, SL2::WOpen { items }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::WOpen { items }), abs18(t)),
{
    // a writer waits for a save to finish (the export gate; control F-C1801 fails here)
    assert(s.x is None);
    assert(t.cur =~= t.rows.union(items));
}

proof fn lemma_wend(s: SS2, commit: bool, items: Set<Item>, t: SS2)
    requires inv18(s), step2(s, SL2::WEnd { commit, items }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::WEnd { commit, items }), abs18(t)),
{
    assert(s.r is None && s.x is None);
    if commit {
        assert(t.cur =~= t.rows);
        assert(none_of(s.scope, items)) by {
            assert forall|i: Item| #[trigger] items.contains(i) implies !s.scope.contains(i.1) by { assert(s.cur.contains(i)); }
        }
    } else {
        assert(t.cur =~= t.rows);
    }
}

proof fn lemma_erase(s: SS2, ten: int, t: SS2)
    requires inv18(s), step2(s, SL2::Erase { ten }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::Erase { ten }), abs18(t)),
{
    // the erase waits for a save to finish (the export gate; control F-C1801 fails here)
    assert(s.x is None);
    if let Some(wi) = s.w {
        assert(t.cur =~= t.rows.union(wi)) by {
            assert forall|i: Item| #[trigger] wi.contains(i) implies i.1 != ten by { assert(not_ten(wi, ten).contains(i)); }
        }
    } else {
        assert(t.cur =~= t.rows);
    }
}

proof fn lemma_redact(s: SS2, ten: int, oor: Set<nat>, t: SS2)
    requires inv18(s), step2(s, SL2::Redact { ten, oor }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::Redact { ten, oor }), abs18(t)),
{
    // the redaction waits for a save to finish (the export gate; control F-C1801 fails here)
    assert(s.x is None);
    let a1 = abs18(s);
    assert forall|i: Item| #[trigger] s.cur.contains(i) implies i.1 != ten by { assert(not_ten(s.cur, ten).contains(i)); }
    assert(not_ten(s.rows, ten) =~= s.rows) by {
        assert forall|i: Item| #[trigger] s.rows.contains(i) implies i.1 != ten by { assert(s.cur.contains(i)); }
    }
    // the receipt names every archive that still holds the tenant (control F-C1304 fails here)
    assert forall|a: nat| #[trigger] a1.archives.contains_key(a) && holds(a1.archives[a], ten) implies oor.contains(a) by {
        assert(s.files.contains_key(a));
    }
    assert(t.g.led.recs.dom() == s.g.led.recs.dom());
    assert forall|q: nat, i: Item| t.g.led.recs.contains_key(q) && #[trigger] t.g.led.recs[q].contains(i)
        implies !t.scope.contains(i.1) by {
        assert(t.g.led.recs[q] == not_ten(s.g.led.recs[q], ten));
        assert(s.g.led.recs[q].contains(i));
    }
    assert(abs18(t) == SS1 { led: Led { recs: redact_recs(a1.led.recs, ten), ..a1.led }, red: a1.red.insert(ten), ..a1 });
}

// ------------------------------------------------------------------------------------------------ save steps

proof fn lemma_xstart(s: SS2, id: nat, t: SS2)
    requires inv18(s), step2(s, SL2::XStart { id }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::XStart { id }), abs18(t)),
{
    // the save waits for open writers (the export gate; control F-C1801 fails here)
    assert(s.w is None);
    assert(read_upto(s.rows, 0) =~= Set::<Item>::empty());
}

proof fn lemma_xread(s: SS2, t: SS2)
    requires inv18(s), step2(s, SL2::XRead, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::XRead), abs18(t)),
{
    let xp = s.x->0;
    assert(s.cur == s.rows);
    let n = xp.stage;
    assert(t.x->0.part =~= read_upto(s.rows, (n + 1) as nat)) by {
        assert forall|i: Item| #[trigger] read_upto(s.rows, (n + 1) as nat).contains(i) implies t.x->0.part.contains(i) by {
            if i.0 < n { assert(read_upto(s.rows, n).contains(i)); } else { assert(store_of(s.cur, n as int).contains(i)); }
        }
    }
}

proof fn lemma_xledger(s: SS2, t: SS2)
    requires inv18(s), step2(s, SL2::XLedger, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::XLedger), abs18(t)),
{
}

proof fn lemma_xend(s: SS2, id: nat, lines: Set<Item>, g: G2, t: SS2)
    requires inv18(s), step2(s, SL2::XEnd { id, lines, g }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::XEnd { id, lines, g }), abs18(t)),
{
    assert(s.cur == s.rows && s.r is None);
    lemma_read_all(s);
    // the archive is the committed state: every store, read with no writer in between
    assert(lines == s.rows);
    assert(g == s.g);
    lemma_arch_of_insert(s.files, id, AF { lines, g });
    assert(!arch_of(s.files).contains_key(id));
}

// ------------------------------------------------------------------------------------------------ restore steps

proof fn lemma_rrefuse(s: SS2, id: nat, t: SS2)
    requires inv18(s), step2(s, SL2::RRefuse { id }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::RRefuse { id }), abs18(t)),
{
    assert(arch_of(s.files).contains_key(id));
}

proof fn lemma_rbegin(s: SS2, id: nat, t: SS2)
    requires inv18(s), step2(s, SL2::RBegin { id }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::RBegin { id }), abs18(t)),
{
    // refused before any write unless the live history is a prefix of the archive's (control F-1801 fails here)
    assert(prefix(s.g.led, s.files[id].g.led));
    assert(s.cur == s.rows);
}

proof fn lemma_rload(s: SS2, bad: Set<Item>, t: SS2)
    requires inv18(s), step2(s, SL2::RLoad { bad }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::RLoad { bad }), abs18(t)),
{
    let rp = s.r->0;
    let a = s.files[rp.id];
    let f2 = t.r->0.failed;
    // a refused global line is counted in failed_rows (control F-C1802 fails here)
    assert(f2 == bad);
    // the live redactions are re-applied to the archive's rows (control F-1801 redaction half fails here)
    assert(t.rows == scrub(a.lines.difference(bad), s.scope));
    assert(bad.subset_of(a.lines));
    assert(stores_ok(t.cur)) by {
        assert forall|i: Item| #[trigger] t.cur.contains(i) implies 0 <= i.0 <= 3 by { assert(a.lines.contains(i)); }
    }
}

proof fn lemma_rledger(s: SS2, t: SS2)
    requires inv18(s), step2(s, SL2::RLedger, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::RLedger), abs18(t)),
{
    let rp = s.r->0;
    let a = s.files[rp.id];
    lemma_overlay(s.g, a.g, s.scope);
    // the live redactions are re-applied to the archive's records (control F-1801 redaction half fails here)
    assert(arch_recs(a.g, s.scope) == scrub_recs(a.g.led.recs, s.scope));
    lemma_scrub_recs_none(a.g.led.recs, s.scope);
}

proof fn lemma_rend(s: SS2, id: nat, failed: Set<Item>, t: SS2)
    requires inv18(s), step2(s, SL2::REnd { id, failed }, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(SL2::REnd { id, failed }), abs18(t)),
{
    let rp = s.r->0;
    let a = s.files[rp.id];
    lemma_overlay(rp.pre_g, a.g, s.scope);
    let a1 = abs18(s);
    assert(a1.archives.contains_key(id) && a1.archives[id] == absf(a));
    // the answer's ledger is the archive's with the live redactions re-applied (control F-1801 redaction half
    // fails here)
    assert(t.g.led == scrub_led(a.g.led, s.scope));
    assert(abs18(t) == SS1 { content: scrub(absf(a).content.difference(failed), a1.red),
                             led: scrub_led(absf(a).led, a1.red), ..a1 });
}

proof fn lemma_scrub_recs_none(m: Map<nat, Set<Item>>, red: Set<int>)
    ensures recs_none_of(red, scrub_recs(m, red)),
{
    assert forall|q: nat, i: Item| scrub_recs(m, red).contains_key(q) && #[trigger] scrub_recs(m, red)[q].contains(i)
        implies !red.contains(i.1) by {
        assert(scrub_recs(m, red)[q] == scrub(m[q], red));
    }
}

proof fn lemma_step(s: SS2, l: SL2, t: SS2)
    requires inv18(s), step2(s, l, t),
    ensures inv18(t), step_or_stutter::<SnapL1>(abs18(s), lab18(l), abs18(t)),
{
    match l {
        SL2::Commit { items, id } => lemma_commit(s, items, id, t),
        SL2::CommitRefused { items, id } => lemma_commit_refused(s, items, id, t),
        SL2::WOpen { items } => lemma_wopen(s, items, t),
        SL2::WEnd { commit, items } => lemma_wend(s, commit, items, t),
        SL2::Erase { ten } => lemma_erase(s, ten, t),
        SL2::Redact { ten, oor } => lemma_redact(s, ten, oor, t),
        SL2::XStart { id } => lemma_xstart(s, id, t),
        SL2::XRead => lemma_xread(s, t),
        SL2::XLedger => lemma_xledger(s, t),
        SL2::XEnd { id, lines, g } => lemma_xend(s, id, lines, g, t),
        SL2::RRefuse { id } => lemma_rrefuse(s, id, t),
        SL2::RBegin { id } => lemma_rbegin(s, id, t),
        SL2::RLoad { bad } => lemma_rload(s, bad, t),
        SL2::RLedger => lemma_rledger(s, t),
        SL2::REnd { id, failed } => lemma_rend(s, id, failed, t),
    }
}

impl Refines<SnapL1> for SnapL2 {
    open spec fn abs(s: SS2) -> SS1 { abs18(s) }
    open spec fn lab(l: SL2) -> Option<SL1> { lab18(l) }
    proof fn init_refines(s: SS2) {
        assert(arch_of(s.files) =~= Map::<nat, Arch>::empty());
    }
    proof fn step_refines(s: SS2, l: SL2, t: SS2) { lemma_step(s, l, t); }
}

impl SafeContract for SnapL2 {
    open spec fn inv(s: SS2) -> bool { inv18(s) }
    proof fn init_safe(s: SS2) {}
    proof fn step_safe(s: SS2, l: SL2, t: SS2) { lemma_step(s, l, t); }
}

// ------------------------------------------------------------------------------------------------ theorems

proof fn lemma_raw_inv_at(states: Seq<SS2>, labels: Seq<SL2>, k: int)
    requires execution::<SnapRaw>(states, labels), 0 <= k < states.len(),
    ensures inv18(states[k]),
    decreases k,
{
    if k == 0 { SnapL2::init_safe(states[0]); } else {
        lemma_raw_inv_at(states, labels, k - 1);
        lemma_step(states[k - 1], labels[k - 1], states[k]);
    }
}

/// Every execution of the L2 step relation from its initial state keeps the L2 invariant, and its abstraction is an
/// L1 execution every state of which satisfies L1's business invariant.
pub proof fn theorem_raw_executions_refine(states: Seq<SS2>, labels: Seq<SL2>)
    requires execution::<SnapRaw>(states, labels),
    ensures
        execution::<SnapL2>(states, labels),
        abstract_execution::<SnapL1>(Seq::new(states.len(), |i: int| abs18(states[i])),
                                     Seq::new(labels.len(), |i: int| lab18(labels[i]))),
        forall|i: int| 0 <= i < states.len() ==> inv18(#[trigger] states[i]) && inv1(abs18(states[i])),
{
    assert forall|i: int| 0 <= i < states.len() implies inv18(#[trigger] states[i]) by { lemma_raw_inv_at(states, labels, i); }
    assert(execution::<SnapL2>(states, labels));
    trace_refines::<SnapL2, SnapL1>(states, labels);
    refinement_preserves_safety::<SnapL2, SnapL1>(states, labels);
    assert(Seq::new(states.len(), |i: int| abs18(states[i])) =~= Seq::new(states.len(), |i: int| <SnapL2 as Refines<SnapL1>>::abs(states[i])));
    assert(Seq::new(labels.len(), |i: int| lab18(labels[i])) =~= Seq::new(labels.len(), |i: int| <SnapL2 as Refines<SnapL1>>::lab(labels[i])));
}

/// F-1801 on the layout: in every reachable state the revision rows are exactly the seqs 1..head, so the next
/// commit's revision row can be saved (a `CommitRefused` step is never enabled).
pub proof fn theorem_commit_never_wedged(s: SS2, items: Set<Item>, id: int, t: SS2)
    requires inv18(s),
    ensures !s.g.rev.contains(s.g.led.head + 1), !step2(s, SL2::CommitRefused { items, id }, t),
{
}

} // verus!
