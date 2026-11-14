//! Module 18 (snapshot), L1: the business contract of `save_snapshot` / `restore_snapshot` (replacing) against the
//! revision ledger and redaction (HD-1801, HD-1802; F-1801, F-C1801, F-C1802, F-C1804, F-C1304).
//!
//! State: the namespace's committed content `content` (every store: tables, node and edge vector routes, native
//! globals; an item is `(store, tenant, key)`), the ledger `led` (head, revision id per seq, recorded content per
//! seq), the tenants a completed redaction removed `red`, and the archives `archives[id]` (the ZIP files).
//!
//! Business rules (transition rules; `inv1` is their consequence):
//! - **an archive is a committed state of the namespace** (HD-1802 working answer: a consistent snapshot only under
//!   quiet writers or a verified gate; SNP-I1: each store is copied): `Save` records exactly the committed content
//!   and ledger at one moment;
//! - **a restore keeps one history that only extends** (HD-1801 working answer; SNP-I3.6; SYS-I5): a restore is
//!   refused before any write, or the live history (its revision ids) is a prefix of the archive's and the ledger
//!   becomes the archive's;
//! - **no redacted content returns** (ADR-0013; spec 256 US1; F-C1304): a restore re-applies the live redactions to
//!   the archive's content and records, and the redaction receipt names every archive that still holds the tenant;
//! - **a restore's answer says what it did not restore** (SNP-X2.14; snapshot.py:1088-1094): `Done{failed}` restores
//!   exactly the archive's content minus `failed` (and minus redacted tenants).
//!
//! Not modelled (PROOFS.md): merge restore (F-1802, F-1805), idempotency bindings, value types (F-1804), edge-vector
//! keys (F-1803), revision kinds, restore under a forced replacement (HD-1801 alternative (a)), crash mid-restore.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

/// A content item `(store, tenant, key)`. Stores: 0 tables (`SQL_TABLES_EXPORT`), 1 node-vector routes `kg_emb_*`,
/// 2 edge-vector routes `kg_eemb_*`, 3 native globals (`^KG`, `^NKG`, `^BM25Idx`, ...).
pub type Item = (int, int, int);

pub open spec fn not_ten(c: Set<Item>, ten: int) -> Set<Item> { c.filter(|i: Item| i.1 != ten) }
pub open spec fn scrub(c: Set<Item>, red: Set<int>) -> Set<Item> { c.filter(|i: Item| !red.contains(i.1)) }

/// The ledger: `^IVG.Ledger("head")`, `("idBySeq", seq)`, `("rec", seq, ord)` (one set of items per seq).
#[verifier::ext_equal]
pub struct Led { pub head: nat, pub ids: Map<nat, int>, pub recs: Map<nat, Set<Item>> }

#[verifier::ext_equal]
pub struct Arch { pub content: Set<Item>, pub led: Led }

#[verifier::ext_equal]
pub struct SS1 { pub content: Set<Item>, pub led: Led, pub red: Set<int>, pub archives: Map<nat, Arch> }

pub enum ROut { Refused, Done { failed: Set<Item> } }

pub enum SL1 {
    /// A ledger commit: the revision and its content in one step (module 11's contract at this level).
    Commit { items: Set<Item>, id: int },
    /// A committed write without a revision (an unledgered or not-strict engine write).
    Write { items: Set<Item> },
    /// delete_nodes_by_prefix / erase_graph of a tenant: content leaves, history stays (Eraser.cls:812).
    Erase { ten: int },
    /// ledger.redact of a tenant: its content leaves the history; `oor` is the receipt's out-of-reach archives.
    Redact { ten: int, oor: Set<nat> },
    /// save_snapshot writes archive `id`.
    Save { id: nat, arch: Arch },
    /// restore_snapshot(merge=False) of archive `id`.
    Restore { id: nat, out: ROut },
}

pub open spec fn scrub_recs(m: Map<nat, Set<Item>>, red: Set<int>) -> Map<nat, Set<Item>> {
    m.map_values(|r: Set<Item>| scrub(r, red))
}
pub open spec fn redact_recs(m: Map<nat, Set<Item>>, ten: int) -> Map<nat, Set<Item>> {
    m.map_values(|r: Set<Item>| not_ten(r, ten))
}
pub open spec fn scrub_led(l: Led, red: Set<int>) -> Led { Led { recs: scrub_recs(l.recs, red), ..l } }

/// One history: revisions 1..head, each with its id and records.
pub open spec fn wf(l: Led) -> bool {
    &&& forall|q: nat| #[trigger] l.ids.contains_key(q) <==> 1 <= q <= l.head
    &&& forall|q: nat| #[trigger] l.recs.contains_key(q) <==> 1 <= q <= l.head
}

/// The live history is a prefix of the archive's: its revisions carry the same ids there (HD-1801).
pub open spec fn prefix(live: Led, a: Led) -> bool {
    &&& live.head <= a.head
    &&& forall|q: nat| 1 <= q <= live.head ==> #[trigger] a.ids.contains_key(q) && live.ids.contains_key(q) && a.ids[q] == live.ids[q]
}

/// An archive holds some of the tenant's content (in its rows or in its ledger records).
pub open spec fn holds(a: Arch, ten: int) -> bool {
    ||| exists|i: Item| #[trigger] a.content.contains(i) && i.1 == ten
    ||| exists|q: nat, i: Item| a.led.recs.contains_key(q) && #[trigger] a.led.recs[q].contains(i) && i.1 == ten
}

pub open spec fn none_of(red: Set<int>, c: Set<Item>) -> bool { forall|i: Item| #[trigger] c.contains(i) ==> !red.contains(i.1) }

pub struct SnapL1;

impl Contract for SnapL1 {
    type S = SS1;
    type L = SL1;

    open spec fn init(s: SS1) -> bool {
        &&& s.content == Set::<Item>::empty() && s.red == Set::<int>::empty() && s.archives == Map::<nat, Arch>::empty()
        &&& s.led == (Led { head: 0, ids: Map::empty(), recs: Map::empty() })
    }

    open spec fn next(s: SS1, l: SL1, t: SS1) -> bool {
        match l {
            SL1::Commit { items, id } => {
                &&& none_of(s.red, items)
                &&& t == SS1 { content: s.content.union(items),
                               led: Led { head: s.led.head + 1, ids: s.led.ids.insert(s.led.head + 1, id),
                                          recs: s.led.recs.insert(s.led.head + 1, items) }, ..s }
            },
            SL1::Write { items } => none_of(s.red, items) && t == SS1 { content: s.content.union(items), ..s },
            SL1::Erase { ten } => t == SS1 { content: not_ten(s.content, ten), ..s },
            SL1::Redact { ten, oor } => {
                &&& not_ten(s.content, ten) == s.content
                &&& forall|a: nat| #[trigger] s.archives.contains_key(a) && holds(s.archives[a], ten) ==> oor.contains(a)
                &&& t == SS1 { led: Led { recs: redact_recs(s.led.recs, ten), ..s.led }, red: s.red.insert(ten), ..s }
            },
            SL1::Save { id, arch } => {
                &&& !s.archives.contains_key(id)
                &&& arch == (Arch { content: s.content, led: s.led })
                &&& t == SS1 { archives: s.archives.insert(id, arch), ..s }
            },
            SL1::Restore { id, out } => {
                &&& s.archives.contains_key(id)
                &&& match out {
                    ROut::Refused => t == s,
                    ROut::Done { failed } => {
                        let a = s.archives[id];
                        &&& prefix(s.led, a.led)
                        &&& failed.subset_of(a.content)
                        &&& t == SS1 { content: scrub(a.content.difference(failed), s.red), led: scrub_led(a.led, s.red), ..s }
                    },
                }
            },
        }
    }
}

pub open spec fn recs_none_of(red: Set<int>, m: Map<nat, Set<Item>>) -> bool {
    forall|q: nat, i: Item| m.contains_key(q) && #[trigger] m[q].contains(i) ==> !red.contains(i.1)
}

pub open spec fn inv1(s: SS1) -> bool {
    &&& wf(s.led)
    &&& forall|a: nat| #[trigger] s.archives.contains_key(a) ==> wf(s.archives[a].led)
    &&& none_of(s.red, s.content)
    &&& recs_none_of(s.red, s.led.recs)
}

proof fn lemma_scrub_none(c: Set<Item>, red: Set<int>)
    ensures none_of(red, scrub(c, red)),
{
}

proof fn lemma_scrub_recs_none(m: Map<nat, Set<Item>>, red: Set<int>)
    ensures recs_none_of(red, scrub_recs(m, red)), scrub_recs(m, red).dom() == m.dom(),
{
    assert forall|q: nat, i: Item| scrub_recs(m, red).contains_key(q) && #[trigger] scrub_recs(m, red)[q].contains(i)
        implies !red.contains(i.1) by {
        assert(scrub_recs(m, red)[q] == scrub(m[q], red));
    }
}

impl SafeContract for SnapL1 {
    open spec fn inv(s: SS1) -> bool { inv1(s) }

    proof fn init_safe(s: SS1) {}

    proof fn step_safe(s: SS1, l: SL1, t: SS1) {
        match l {
            SL1::Commit { items, id } => {
                assert forall|q: nat, i: Item| t.led.recs.contains_key(q) && #[trigger] t.led.recs[q].contains(i)
                    implies !t.red.contains(i.1) by {
                    if q != s.led.head + 1 { assert(s.led.recs.contains_key(q) && s.led.recs[q].contains(i)); }
                }
            }
            SL1::Write { items } => {}
            SL1::Erase { ten } => {}
            SL1::Redact { ten, oor } => {
                assert forall|i: Item| #[trigger] t.content.contains(i) implies !t.red.contains(i.1) by {
                    assert(not_ten(s.content, ten).contains(i));
                }
                assert forall|q: nat, i: Item| t.led.recs.contains_key(q) && #[trigger] t.led.recs[q].contains(i)
                    implies !t.red.contains(i.1) by {
                    assert(t.led.recs[q] == not_ten(s.led.recs[q], ten));
                    assert(s.led.recs[q].contains(i));
                }
                assert(wf(t.led)) by {
                    assert forall|q: nat| #[trigger] t.led.recs.contains_key(q) <==> 1 <= q <= t.led.head by {
                        assert(t.led.recs.dom() == s.led.recs.dom());
                    }
                }
            }
            SL1::Save { id, arch } => {}
            SL1::Restore { id, out } => {
                match out {
                    ROut::Refused => {}
                    ROut::Done { failed } => {
                        let a = s.archives[id];
                        lemma_scrub_none(a.content.difference(failed), s.red);
                        lemma_scrub_recs_none(a.led.recs, s.red);
                        assert(wf(a.led));
                    }
                }
            }
        }
    }
}

// ------------------------------------------------------------------------------------------------ business theorems

/// SYS-I5 / SNP-I3.6: the ledger's history only extends: no step moves the head back or changes a revision id.
pub proof fn theorem_history_only_extends(s: SS1, l: SL1, t: SS1)
    requires inv1(s), SnapL1::next(s, l, t),
    ensures
        t.led.head >= s.led.head,
        forall|q: nat| 1 <= q <= s.led.head ==> #[trigger] t.led.ids.contains_key(q) && t.led.ids[q] == s.led.ids[q],
{
}

/// F-1801's wedge cannot happen: the next commit's seq is free in every reachable state.
pub proof fn theorem_next_seq_free(s: SS1)
    requires inv1(s),
    ensures !s.led.ids.contains_key(s.led.head + 1), !s.led.recs.contains_key(s.led.head + 1),
{
}

/// A restore that is refused changes nothing (refusal before any write).
pub proof fn theorem_refused_restore_changes_nothing(s: SS1, id: nat, t: SS1)
    requires SnapL1::next(s, SL1::Restore { id, out: ROut::Refused }, t),
    ensures t == s,
{
}

/// F-C1304: the redaction receipt names every archive that still holds the tenant.
pub proof fn theorem_receipt_names_holding_archives(s: SS1, ten: int, oor: Set<nat>, t: SS1, a: nat)
    requires SnapL1::next(s, SL1::Redact { ten, oor }, t), s.archives.contains_key(a), holds(s.archives[a], ten),
    ensures oor.contains(a),
{
}

proof fn lemma_red_monotone(states: Seq<SS1>, labels: Seq<SL1>, i: int, j: int, ten: int)
    requires execution::<SnapL1>(states, labels), 0 <= i <= j < states.len(), states[i].red.contains(ten),
    ensures states[j].red.contains(ten),
    decreases j - i,
{
    if j > i { lemma_red_monotone(states, labels, i, j - 1, ten); assert(SnapL1::next(states[j - 1], labels[j - 1], states[j])); }
}

/// ADR-0013 / F-C1304: once a tenant is redacted, no later state holds its content in the namespace or in the
/// ledger's records, whatever saves, restores, erasures and commits follow.
pub proof fn theorem_redacted_content_never_returns(states: Seq<SS1>, labels: Seq<SL1>, i: int, j: int, ten: int)
    requires execution::<SnapL1>(states, labels), 0 <= i <= j < states.len(), states[i].red.contains(ten),
    ensures
        forall|x: Item| #[trigger] states[j].content.contains(x) ==> x.1 != ten,
        forall|q: nat, x: Item| states[j].led.recs.contains_key(q) && #[trigger] states[j].led.recs[q].contains(x) ==> x.1 != ten,
{
    lemma_red_monotone(states, labels, i, j, ten);
    invariant_at::<SnapL1>(states, labels, j);
}

proof fn lemma_archive_stable(states: Seq<SS1>, labels: Seq<SL1>, i: int, j: int, id: nat, a: Arch)
    requires execution::<SnapL1>(states, labels), 0 <= i < j < states.len(), labels[i] == (SL1::Save { id, arch: a }),
    ensures states[j].archives.contains_key(id) && states[j].archives[id] == a,
    decreases j - i,
{
    assert(SnapL1::next(states[i], labels[i], states[i + 1]));
    if j > i + 1 {
        lemma_archive_stable(states, labels, i, j - 1, id, a);
        assert(SnapL1::next(states[j - 1], labels[j - 1], states[j]));
    }
}

/// SNP-I1 with SNP-X2.14: a restore that reports nothing failed brings back exactly the content the archive was
/// saved from, minus only the tenants redacted since.
pub proof fn theorem_complete_restore_reproduces_saved_state(states: Seq<SS1>, labels: Seq<SL1>, i: int, j: int,
                                                             id: nat, a: Arch)
    requires
        execution::<SnapL1>(states, labels), 0 <= i < j, j + 1 < states.len(),
        labels[i] == (SL1::Save { id, arch: a }),
        labels[j] == (SL1::Restore { id, out: ROut::Done { failed: Set::empty() } }),
    ensures
        states[j + 1].content == scrub(states[i].content, states[j].red),
        states[j + 1].led == scrub_led(states[i].led, states[j].red),
{
    lemma_archive_stable(states, labels, i, j, id, a);
    assert(SnapL1::next(states[i], labels[i], states[i + 1]));
    assert(SnapL1::next(states[j], labels[j], states[j + 1]));
    assert(a.content.difference(Set::<Item>::empty()) =~= a.content);
}

} // verus!
