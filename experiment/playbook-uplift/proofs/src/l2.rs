//! L2: the algorithmic machine over the stored layout, and its refinement of L1.
//!
//! State (production names, pin 3eaa79cf):
//! - `rec[i][j]`   ^IVG.Ledger("rec", i+1, j+1)                                  Ledger.cls:7
//! - `meta[i]`     the free text and idempotency_key of ledger_revisions seq i+1  LedgerRevision.cls:30-36
//! - `idem`        ^IVG.Ledger("idem", key) -> seq                               Ledger.cls:10, 525
//! - `idem_red`    ^IVG.Ledger("idemRedacted", sha256(key)) (P-1303: the digest is injective on keys)
//! - `red_rev`     ^IVG.Ledger("redactedRev", seq)                              LedgerRedact.cls:366
//! - `marker`      ^IVG.Ledger("redacting") = $LB(digest, graph, match, ...)     LedgerRedact.cls:323
//! - `counted`     ^IVG.Ledger("redacting", "n", "records") > 0                  LedgerRedact.cls:344
//! - `live`        the content tables (nodes, rdf_labels, rdf_props, rdf_edges)
//! - `runs[p]`     process p's redaction cursor (tSeq, tOrd in LedgerRedact.Redact), process-local
//!
//! Steps are transactions: each holds the head lock and commits or rolls back as a whole (Batch, Final, Commit),
//! so a stopped process loses only its cursor (P-0001, P-0004; observed live in native/scenarios.py
//! killed_mid_batch and killed_at_random). A batch of n records is n `Scan` steps with no step of another process
//! between them, which is one of this machine's executions.
//!
//! **Design.** This machine is the *reviewed* design: `Start` checks the target and sets the marker in one
//! transaction under the head lock. The code at the pin checks without the lock and sets the marker only with the
//! first tombstone (LedgerRedact.cls:202-211, 322-324). Features `control_unmarked_start` and `control_other_target`
//! together correspond to that code (F-1302, F-1303); the refinement proof rejects each, the explorer finds their
//! counterexamples, and native/scenarios.py reproduces both on IRIS. The other controls are single broken guards. Not
//! modelled here: audit counts, statement entries, unattributed records, a Final without a marker (MODELS.md).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::model::*;
use crate::l1;
use crate::l1::{KeyState, L1, Rev};

verus! {

pub struct Meta { pub text: bool, pub key: Option<Key> }

pub struct Run { pub t: Tgt, pub i: nat, pub j: nat }

pub struct S2 {
    pub rec: Seq<Seq<Rec>>,
    pub meta: Seq<Meta>,
    pub idem: Map<Key, nat>,
    pub idem_red: Set<Key>,
    pub red_rev: Set<nat>,
    pub marker: Option<Tgt>,
    pub counted: bool,
    pub live: Map<Id, int>,
    pub enabled: bool,
    pub runs: Map<nat, Run>,
    /// ghost
    pub orig: Seq<Seq<Rec>>,
    /// ghost
    pub begun: Set<Tgt>,
}

pub enum L2Label {
    Commit { cs: Seq<Content>, key: Option<Key> },
    Write { id: Id, v: Option<int> },
    Erase { t: Tgt },
    SetEnabled { on: bool },
    /// Process p calls Redact(t): its opening checks. `fresh` when no marker existed.
    Start { p: nat, t: Tgt, fresh: bool },
    /// One record of a batch.
    Scan { p: nat },
    /// The final transaction; `ok` when it finishes (the target is not live).
    Final { p: nat, t: Tgt, ok: bool },
    /// The process stops or returns early (max_batches): its cursor is gone.
    Stop { p: nat },
}

// ------------------------------------------------------------------------------------------------ guards and effects

pub open spec fn commit_ok(s: S2, cs: Seq<Content>, key: Option<Key>) -> bool {
    &&& s.enabled
    &&& cs.len() > 0
    &&& (key is None || (!s.idem.contains_key(key->0) && !s.idem_red.contains(key->0)))
    &&& if cfg!(feature = "control_no_commit_block") { true }
        else { !(s.marker is Some && touches(cs, s.marker->0)) }
}

pub open spec fn commit(s: S2, cs: Seq<Content>, key: Option<Key>) -> S2 {
    S2 {
        rec: s.rec.push(lives(cs)),
        meta: s.meta.push(Meta { text: true, key }),
        idem: match key { Some(k) => s.idem.insert(k, s.rec.len()), None => s.idem },
        live: replay_recs(s.live, lives(cs)),
        orig: s.orig.push(lives(cs)),
        ..s
    }
}

pub open spec fn start_ok(s: S2, p: nat, t: Tgt, fresh: bool) -> bool {
    &&& s.enabled
    &&& !s.runs.contains_key(p)
    &&& !live_in(s.live, t)
    &&& (s.marker is None || s.marker == Some(t))
    &&& fresh == (s.marker is None)
}

pub open spec fn start(s: S2, p: nat, t: Tgt) -> S2 {
    if cfg!(feature = "control_unmarked_start") {
        S2 { runs: s.runs.insert(p, Run { t, i: 0, j: 0 }), ..s }
    } else {
        S2 { runs: s.runs.insert(p, Run { t, i: 0, j: 0 }), marker: Some(t), begun: s.begun.insert(t), ..s }
    }
}

pub open spec fn scan_ok(s: S2, p: nat) -> bool {
    &&& s.enabled
    &&& s.runs.contains_key(p)
    &&& s.runs[p].i < s.rec.len()
    &&& if cfg!(feature = "control_other_target") { true }
        else if cfg!(feature = "control_unmarked_start") { s.marker is None || s.marker == Some(s.runs[p].t) }
        else { s.marker == Some(s.runs[p].t) }
}

pub open spec fn clears(rs: Seq<Rec>, first: bool) -> bool {
    if cfg!(feature = "control_meta_every") {
        forall|j: int| 0 <= j < rs.len() ==> !(#[trigger] rs[j] is Live)
    } else {
        first
    }
}

pub open spec fn tombstone(s: S2, p: nat) -> S2 {
    let r = s.runs[p];
    let c = s.rec[r.i as int][r.j as int]->Live_0;
    let row = s.rec[r.i as int].update(r.j as int, Rec::Tomb(c));
    let first = !s.red_rev.contains(r.i);
    let clear = clears(row, first);
    let k = s.meta[r.i as int].key;
    let move_key = clear && k is Some && !cfg!(feature = "control_keep_retry_key");
    S2 {
        rec: s.rec.update(r.i as int, row),
        meta: if clear { s.meta.update(r.i as int, Meta { text: false, key: if cfg!(feature = "control_keep_retry_key") { k } else { None } }) } else { s.meta },
        idem: if move_key { s.idem.remove(k->0) } else { s.idem },
        idem_red: if move_key { s.idem_red.insert(k->0) } else { s.idem_red },
        red_rev: s.red_rev.insert(r.i),
        counted: true,
        marker: if s.marker is None { Some(r.t) } else { s.marker },
        begun: s.begun.insert(r.t),
        runs: s.runs.insert(p, Run { j: r.j + 1, ..r }),
        ..s
    }
}

pub open spec fn scan(s: S2, p: nat) -> S2 {
    let r = s.runs[p];
    if r.j >= s.rec[r.i as int].len() {
        S2 { runs: s.runs.insert(p, Run { i: r.i + 1, j: 0, ..r }), ..s }
    } else if live_member(s.rec[r.i as int][r.j as int], r.t) {
        tombstone(s, p)
    } else {
        S2 { runs: s.runs.insert(p, Run { j: r.j + 1, ..r }), ..s }
    }
}

pub open spec fn final_ok(s: S2, p: nat, t: Tgt, ok: bool) -> bool {
    &&& s.enabled
    &&& s.runs.contains_key(p)
    &&& s.runs[p].t == t
    &&& s.runs[p].i == s.rec.len()
    &&& s.marker == Some(t)
    &&& if cfg!(feature = "control_no_final_check") { ok } else { ok == !live_in(s.live, t) }
}

pub open spec fn final_step(s: S2, p: nat, ok: bool) -> S2 {
    if ok {
        S2 {
            rec: if s.counted { s.rec.push(seq![Rec::Audit]) } else { s.rec },
            meta: if s.counted { s.meta.push(Meta { text: false, key: None }) } else { s.meta },
            orig: if s.counted { s.orig.push(seq![Rec::Audit]) } else { s.orig },
            marker: None,
            counted: false,
            runs: s.runs.remove(p),
            ..s
        }
    } else {
        S2 { runs: s.runs.remove(p), ..s }
    }
}

// ------------------------------------------------------------------------------------------------ the invariant

pub open spec fn cursor_ok(s: S2, r: Run) -> bool {
    &&& r.i <= s.rec.len()
    &&& r.i < s.rec.len() ==> r.j <= s.rec[r.i as int].len()
    &&& r.i == s.rec.len() ==> r.j == 0
    &&& forall|i: int, j: int| 0 <= i < s.rec.len() && 0 <= j < s.rec[i].len() && (i < r.i || (i == r.i && j < r.j))
            ==> !live_member(#[trigger] s.rec[i][j], r.t)
}

pub open spec fn inv2(s: S2) -> bool {
    &&& s.meta.len() == s.rec.len()
    &&& s.orig.len() == s.rec.len()
    &&& forall|i: int| 0 <= i < s.rec.len() ==> (#[trigger] s.rec[i]).len() == s.orig[i].len()
    &&& forall|i: int, j: int| 0 <= i < s.rec.len() && 0 <= j < s.rec[i].len() ==> l1::rec_ok(s.orig[i][j], #[trigger] s.rec[i][j])
    &&& forall|i: int, j: int| 0 <= i < s.rec.len() && 0 <= j < s.rec[i].len() && #[trigger] is_tomb(s.rec[i][j])
            ==> l1::begun_member(s.begun, s.rec[i][j]->Tomb_0.id)
    &&& forall|i: int| 0 <= i < s.rec.len() ==> (s.red_rev.contains(i as nat) == has_tomb(#[trigger] s.rec[i]))
    &&& forall|n: nat| #[trigger] s.red_rev.contains(n) ==> n < s.rec.len()
    &&& forall|i: int| 0 <= i < s.rec.len() && has_tomb(#[trigger] s.rec[i]) ==> !s.meta[i].text && s.meta[i].key is None
    &&& forall|k: Key| #[trigger] s.idem.contains_key(k) ==>
            s.idem[k] < s.rec.len() && s.meta[s.idem[k] as int].key == Some(k) && !has_tomb(s.rec[s.idem[k] as int])
    &&& forall|i: int| 0 <= i < s.rec.len() && (#[trigger] s.meta[i]).key is Some ==>
            s.idem.contains_key(s.meta[i].key->0) && s.idem[s.meta[i].key->0] == i as nat
    &&& forall|k: Key| #[trigger] s.idem_red.contains(k) ==> !s.idem.contains_key(k)
    &&& s.marker is None ==> !s.counted
    &&& s.marker is Some ==> s.begun.contains(s.marker->0)
    &&& forall|p: nat| #[trigger] s.runs.contains_key(p) ==> cursor_ok(s, s.runs[p])
}

// ------------------------------------------------------------------------------------------------ the contract

pub struct L2;

impl Contract for L2 {
    type S = S2;
    type L = L2Label;

    open spec fn init(s: S2) -> bool {
        &&& s.rec.len() == 0 && s.meta.len() == 0 && s.orig.len() == 0
        &&& s.idem == Map::<Key, nat>::empty() && s.idem_red == Set::<Key>::empty() && s.red_rev == Set::<nat>::empty()
        &&& s.marker is None && !s.counted
        &&& s.live == Map::<Id, int>::empty()
        &&& s.runs == Map::<nat, Run>::empty()
        &&& s.begun == Set::<Tgt>::empty()
    }

    /// Steps from states satisfying the invariant. `theorem_inv2_inductive` proves the invariant holds initially and
    /// after every `step2`, so every execution of `step2` is an execution of this contract.
    open spec fn next(s: S2, l: L2Label, u: S2) -> bool {
        inv2(s) && step2(s, l, u)
    }
}

/// One L2 step, without the invariant.
pub open spec fn step2(s: S2, l: L2Label, u: S2) -> bool {
        match l {
            L2Label::Commit { cs, key } => commit_ok(s, cs, key) && u == commit(s, cs, key),
            L2Label::Write { id, v } => u == S2 { live: match v { Some(x) => s.live.insert(id, x), None => s.live.remove(id) }, ..s },
            L2Label::Erase { t } => u == S2 { live: outside(s.live, t), ..s },
            L2Label::SetEnabled { on } => u == S2 { enabled: on, ..s },
            L2Label::Start { p, t, fresh } => start_ok(s, p, t, fresh) && u == start(s, p, t),
            L2Label::Scan { p } => scan_ok(s, p) && u == scan(s, p),
            L2Label::Final { p, t, ok } => final_ok(s, p, t, ok) && u == final_step(s, p, ok),
            L2Label::Stop { p } => s.runs.contains_key(p) && u == S2 { runs: s.runs.remove(p), ..s },
        }
}

// ------------------------------------------------------------------------------------------------ the abstraction

pub open spec fn imp(x: Rec, m: Option<Tgt>) -> Rec {
    match m { Some(t) => tomb(x, t), None => x }
}

pub open spec fn has_implied(rs: Seq<Rec>, m: Option<Tgt>) -> bool {
    m is Some && exists|j: int| 0 <= j < rs.len() && #[trigger] live_member(rs[j], m->0)
}

pub open spec fn abs_recs(rs: Seq<Rec>, m: Option<Tgt>) -> Seq<Rec> {
    rs.map_values(|x: Rec| imp(x, m))
}

pub open spec fn abs_rev(rs: Seq<Rec>, md: Meta, m: Option<Tgt>) -> Rev {
    Rev {
        recs: abs_recs(rs, m),
        text: md.text && !has_implied(rs, m),
        key: if has_implied(rs, m) { None } else { md.key },
    }
}

pub open spec fn abs_hist(s: S2) -> Seq<Rev> {
    Seq::new(s.rec.len(), |i: int| abs_rev(s.rec[i], s.meta[i], s.marker))
}

pub open spec fn abs_key(s: S2, k: Key) -> KeyState {
    if s.idem_red.contains(k) { KeyState::Redacted }
    else if s.idem[k] < s.rec.len() && has_implied(s.rec[s.idem[k] as int], s.marker) { KeyState::Redacted }
    else { KeyState::Bound(s.idem[k]) }
}

pub open spec fn abs_keys(s: S2) -> Map<Key, KeyState> {
    Map::new(s.idem.dom().union(s.idem_red), |k: Key| abs_key(s, k))
}

pub open spec fn some_member(s: S2, t: Tgt) -> bool {
    exists|i: int, j: int| 0 <= i < s.rec.len() && 0 <= j < s.rec[i].len() && #[trigger] live_member(s.rec[i][j], t)
}

pub open spec fn abs(s: S2) -> l1::S {
    l1::S {
        hist: abs_hist(s),
        live: s.live,
        keys: abs_keys(s),
        redacting: s.marker,
        audit_due: s.counted || (s.marker is Some && some_member(s, s.marker->0)),
        enabled: s.enabled,
        orig: s.orig,
        begun: s.begun,
    }
}

pub open spec fn lab(l: L2Label) -> Option<l1::Label> {
    match l {
        L2Label::Commit { cs, key } => Some(l1::Label::Commit { cs, key }),
        L2Label::Write { id, v } => Some(l1::Label::Write { id, v }),
        L2Label::Erase { t } => Some(l1::Label::Erase { t }),
        L2Label::SetEnabled { on } => Some(l1::Label::SetEnabled { on }),
        L2Label::Start { p, t, fresh } => if fresh { Some(l1::Label::Begin { t }) } else { None },
        L2Label::Scan { p } => None,
        L2Label::Final { p, t, ok } => if ok { Some(l1::Label::Finish { t }) } else { None },
        L2Label::Stop { p } => None,
    }
}

// ------------------------------------------------------------------------------------------------ helper lemmas

proof fn lemma_abs_hist_index(s: S2, i: int)
    requires 0 <= i < s.rec.len(),
    ensures abs_hist(s)[i] == abs_rev(s.rec[i], s.meta[i], s.marker), abs_hist(s).len() == s.rec.len(),
{
}

/// The records of a run's target are gone from everything before its cursor; at the end, from everything.
proof fn lemma_cursor_end(s: S2, r: Run)
    requires cursor_ok(s, r), r.i == s.rec.len(),
    ensures !some_member(s, r.t),
{
    if some_member(s, r.t) {
        let (i, j) = choose|i: int, j: int| 0 <= i < s.rec.len() && 0 <= j < s.rec[i].len() && #[trigger] live_member(s.rec[i][j], r.t);
        assert(i < r.i);
    }
}

proof fn lemma_no_member_abs(s: S2, t: Tgt)
    requires !some_member(s, t), s.marker == Some(t),
    ensures forall|i: int| 0 <= i < s.rec.len() ==> abs_recs(#[trigger] s.rec[i], s.marker) =~= s.rec[i] && !has_implied(s.rec[i], s.marker),
{
    assert forall|i: int| 0 <= i < s.rec.len() implies abs_recs(#[trigger] s.rec[i], s.marker) =~= s.rec[i] && !has_implied(s.rec[i], s.marker) by {
        assert forall|j: int| 0 <= j < s.rec[i].len() implies abs_recs(s.rec[i], s.marker)[j] == s.rec[i][j] by {
            if live_member(s.rec[i][j], t) { assert(some_member(s, t)); }
        }
        if has_implied(s.rec[i], s.marker) {
            let j = choose|j: int| 0 <= j < s.rec[i].len() && #[trigger] live_member(s.rec[i][j], t);
            assert(some_member(s, t));
        }
    }
}

// ------------------------------------------------------------------------------------------------ refinement

proof fn lemma_commit_refines(s: S2, cs: Seq<Content>, key: Option<Key>)
    requires inv2(s), commit_ok(s, cs, key),
    ensures l1::commit_ok(abs(s), cs, key), abs(commit(s, cs, key)) == l1::commit(abs(s), cs, key),
{
    let u = commit(s, cs, key);
    let a = abs(s);
    let e = l1::commit(a, cs, key);
    if s.marker is Some {
        assert(!touches(cs, s.marker->0));
        lemma_lives_no_member(cs, s.marker->0);
    }
    let n = s.rec.len();
    assert forall|i: int| 0 <= i < u.rec.len() implies abs_hist(u)[i] == e.hist[i] by {
        if i < n {
            assert(u.rec[i] == s.rec[i] && u.meta[i] == s.meta[i]);
        } else {
            assert(u.rec[i] == lives(cs));
            if s.marker is Some {
                lemma_tomb_all_noop(lives(cs), s.marker->0);
                assert(abs_recs(lives(cs), s.marker) =~= lives(cs));
                assert(!has_implied(lives(cs), s.marker));
            } else {
                assert(abs_recs(lives(cs), s.marker) =~= lives(cs));
            }
        }
    }
    assert(abs_hist(u) =~= e.hist);
    assert forall|k: Key| #[trigger] abs_keys(u).contains_key(k) <==> e.keys.contains_key(k) by {}
    assert forall|k: Key| #[trigger] abs_keys(u).contains_key(k) implies abs_keys(u)[k] == e.keys[k] by {
        if key == Some(k) {
            assert(!has_implied(u.rec[n as int], u.marker)) by {
                if s.marker is Some { lemma_tomb_all_noop(lives(cs), s.marker->0); }
            }
        } else if s.idem_red.contains(k) {
        } else {
            assert(s.idem.contains_key(k));
            assert(u.idem[k] == s.idem[k]);
            assert(u.rec[s.idem[k] as int] == s.rec[s.idem[k] as int]);
        }
    }
    assert(abs_keys(u) =~= e.keys);
    if u.marker is Some {
        let t = u.marker->0;
        if some_member(u, t) {
            let (i, j) = choose|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && #[trigger] live_member(u.rec[i][j], t);
            if i < n { assert(u.rec[i] == s.rec[i]); assert(some_member(s, t)); }
        }
        if some_member(s, t) {
            let (i, j) = choose|i: int, j: int| 0 <= i < s.rec.len() && 0 <= j < s.rec[i].len() && #[trigger] live_member(s.rec[i][j], t);
            assert(u.rec[i] == s.rec[i]);
            assert(some_member(u, t));
        }
    }
    assert(a.keys.dom() =~= s.idem.dom().union(s.idem_red));
}

proof fn lemma_start_refines(s: S2, p: nat, t: Tgt)
    requires inv2(s), start_ok(s, p, t, true),
    ensures l1::begin_ok(abs(s), t), abs(start(s, p, t)) == l1::begin(abs(s), t),
{
    let u = start(s, p, t);
    let a = abs(s);
    let e = l1::begin(a, t);
    assert(s.marker is None);
    assert forall|i: int| 0 <= i < s.rec.len() implies abs_recs(#[trigger] s.rec[i], s.marker) =~= s.rec[i] by {}
    assert forall|i: int| 0 <= i < s.rec.len() implies abs_hist(u)[i] == e.hist[i] by {
        let rs = s.rec[i];
        assert(a.hist[i] == abs_rev(rs, s.meta[i], None));
        assert(abs_recs(rs, None) =~= rs);
        assert(abs_recs(rs, Some(t)) =~= tomb_all(rs, t));
        assert(has_tomb(tomb_all(rs, t)) == (has_tomb(rs) || has_implied(rs, Some(t)))) by {
            if has_tomb(tomb_all(rs, t)) {
                let j = choose|j: int| 0 <= j < tomb_all(rs, t).len() && #[trigger] is_tomb(tomb_all(rs, t)[j]);
                if !is_tomb(rs[j]) { assert(live_member(rs[j], t)); }
            }
            if has_tomb(rs) {
                let j = choose|j: int| 0 <= j < rs.len() && #[trigger] is_tomb(rs[j]);
                assert(is_tomb(tomb_all(rs, t)[j]));
            }
            if has_implied(rs, Some(t)) {
                let j = choose|j: int| 0 <= j < rs.len() && #[trigger] live_member(rs[j], t);
                assert(is_tomb(tomb_all(rs, t)[j]));
            }
        }
    }
    assert(abs_hist(u) =~= e.hist);
    assert forall|k: Key| #[trigger] abs_keys(u).contains_key(k) implies abs_keys(u)[k] == e.keys[k] by {
        assert(a.keys.contains_key(k));
        assert(e.keys[k] == l1::key_after(a.keys[k], e.hist));
        if s.idem.contains_key(k) && !s.idem_red.contains(k) {
            let i = s.idem[k] as int;
            assert(e.hist[i] == abs_rev(u.rec[i], u.meta[i], u.marker));
        }
    }
    assert(abs_keys(u) =~= e.keys);
    assert(some_member(s, t) == l1::any_member(a.hist, t)) by {
        if some_member(s, t) {
            let (i, j) = choose|i: int, j: int| 0 <= i < s.rec.len() && 0 <= j < s.rec[i].len() && #[trigger] live_member(s.rec[i][j], t);
            assert(a.hist[i].recs[j] == s.rec[i][j]);
        }
        if l1::any_member(a.hist, t) {
            let (i, j) = choose|i: int, j: int| 0 <= i < a.hist.len() && 0 <= j < a.hist[i].recs.len() && #[trigger] live_member(a.hist[i].recs[j], t);
            assert(a.hist[i].recs[j] == s.rec[i][j]);
        }
    }
}

proof fn lemma_scan_stutters(s: S2, p: nat)
    requires inv2(s), scan_ok(s, p),
    ensures abs(scan(s, p)) == abs(s),
{
    let u = scan(s, p);
    let r = s.runs[p];
    if r.j < s.rec[r.i as int].len() && live_member(s.rec[r.i as int][r.j as int], r.t) {
        let t = r.t;
        let i0 = r.i as int;
        let j0 = r.j as int;
        let c = s.rec[i0][j0]->Live_0;
        assert(s.marker == Some(t));
        assert(has_implied(s.rec[i0], s.marker));
        assert(s.begun.contains(t));
        assert(u.begun =~= s.begun);
        assert(u.marker == s.marker);
        assert(s.red_rev.contains(r.i) == has_tomb(s.rec[i0]));
        assert(!u.meta[i0].text && u.meta[i0].key is None);
        assert(u.meta.len() == s.meta.len());
        assert forall|i: int| 0 <= i < s.rec.len() && i != i0 implies #[trigger] u.meta[i] == s.meta[i] by {}
        assert forall|i: int| 0 <= i < s.rec.len() implies abs_hist(u)[i] == abs_hist(s)[i] by {
            if i == i0 {
                assert(abs_recs(u.rec[i], s.marker) =~= abs_recs(s.rec[i], s.marker));
                assert(is_tomb(u.rec[i][j0]));
            } else {
                assert(u.rec[i] == s.rec[i]);
            }
        }
        assert(abs_hist(u) =~= abs_hist(s));
        assert forall|k: Key| #[trigger] abs_keys(u).contains_key(k) <==> abs_keys(s).contains_key(k) by {}
        assert forall|k: Key| #[trigger] abs_keys(u).contains_key(k) implies abs_keys(u)[k] == abs_keys(s)[k] by {
            if s.idem.contains_key(k) && s.idem[k] as int != i0 {
                assert(u.rec[s.idem[k] as int] == s.rec[s.idem[k] as int]);
                if !s.idem_red.contains(k) {
                    assert(u.idem.contains_key(k) && u.idem[k] == s.idem[k]);
                }
            } else if s.idem.contains_key(k) {
                assert(s.meta[i0].key == Some(k));
            }
        }
        assert(abs_keys(u) =~= abs_keys(s));
        assert(some_member(s, t));
    } else {
        assert(abs_hist(u) =~= abs_hist(s));
        assert(abs_keys(u) =~= abs_keys(s));
    }
}

proof fn lemma_final_refines(s: S2, p: nat, t: Tgt)
    requires inv2(s), final_ok(s, p, t, true),
    ensures l1::finish_ok(abs(s), t), abs(final_step(s, p, true)) == l1::finish(abs(s)),
{
    let u = final_step(s, p, true);
    let a = abs(s);
    let e = l1::finish(a);
    assert(cursor_ok(s, s.runs[p]));
    lemma_cursor_end(s, s.runs[p]);
    lemma_no_member_abs(s, t);
    assert forall|i: int| 0 <= i < u.rec.len() implies abs_hist(u)[i] == e.hist[i] by {
        if i < s.rec.len() {
            assert(u.rec[i] == s.rec[i] && u.meta[i] == s.meta[i]);
            assert(abs_recs(s.rec[i], None) =~= s.rec[i]);
        } else {
            assert(abs_recs(seq![Rec::Audit], None) =~= seq![Rec::Audit]);
        }
    }
    assert(abs_hist(u) =~= e.hist);
    assert forall|k: Key| #[trigger] abs_keys(u).contains_key(k) implies abs_keys(u)[k] == e.keys[k] by {
        if s.idem.contains_key(k) && !s.idem_red.contains(k) {
            assert(!has_implied(s.rec[s.idem[k] as int], s.marker));
        }
    }
    assert(abs_keys(u) =~= e.keys);
}

pub open spec fn step_matches(s: S2, l: L2Label, u: S2) -> bool {
    step_or_stutter::<L1>(abs(s), lab(l), abs(u))
}

impl Refines<L1> for L2 {
    open spec fn abs(s: S2) -> l1::S { abs(s) }
    open spec fn lab(l: L2Label) -> Option<l1::Label> { lab(l) }

    proof fn init_refines(s: S2) {
        assert(abs_hist(s) =~= Seq::<Rev>::empty());
        assert(abs_keys(s) =~= Map::<Key, KeyState>::empty());
    }

    proof fn step_refines(s: S2, l: L2Label, u: S2) {
        match l {
            L2Label::Commit { cs, key } => { lemma_commit_refines(s, cs, key); }
            L2Label::Write { id, v } => {
                assert(abs_hist(u) =~= abs_hist(s));
                assert(abs_keys(u) =~= abs_keys(s));
            }
            L2Label::Erase { t } => {
                assert(abs_hist(u) =~= abs_hist(s));
                assert(abs_keys(u) =~= abs_keys(s));
            }
            L2Label::SetEnabled { on } => {
                assert(abs_hist(u) =~= abs_hist(s));
                assert(abs_keys(u) =~= abs_keys(s));
            }
            L2Label::Start { p, t, fresh } => {
                if fresh {
                    lemma_start_refines(s, p, t);
                } else {
                    assert(u.begun =~= s.begun);
                    assert(abs_hist(u) =~= abs_hist(s));
                    assert(abs_keys(u) =~= abs_keys(s));
                }
            }
            L2Label::Scan { p } => { lemma_scan_stutters(s, p); }
            L2Label::Final { p, t, ok } => {
                if ok {
                    lemma_final_refines(s, p, t);
                } else {
                    assert(abs_hist(u) =~= abs_hist(s));
                    assert(abs_keys(u) =~= abs_keys(s));
                }
            }
            L2Label::Stop { p } => {
                assert(abs_hist(u) =~= abs_hist(s));
                assert(abs_keys(u) =~= abs_keys(s));
            }
        }
    }
}


// ------------------------------------------------------------------------------------------------ the invariant is inductive

proof fn lemma_append_keeps(s: S2, u: S2, row: Seq<Rec>, md: Meta)
    requires inv2(s),
        u.rec == s.rec.push(row), u.meta == s.meta.push(md), u.orig == s.orig.push(row),
        u.red_rev == s.red_rev, u.begun == s.begun, u.idem_red == s.idem_red,
        forall|j: int| 0 <= j < row.len() ==> !is_tomb(#[trigger] row[j]),
        forall|p: nat| #[trigger] u.runs.contains_key(p) ==> s.runs.contains_key(p) && u.runs[p] == s.runs[p],
    ensures
        forall|i: int| 0 <= i < u.rec.len() ==> (#[trigger] u.rec[i]).len() == u.orig[i].len(),
        forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() ==> l1::rec_ok(u.orig[i][j], #[trigger] u.rec[i][j]),
        forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && #[trigger] is_tomb(u.rec[i][j])
            ==> l1::begun_member(u.begun, u.rec[i][j]->Tomb_0.id),
        forall|i: int| 0 <= i < u.rec.len() ==> (u.red_rev.contains(i as nat) == has_tomb(#[trigger] u.rec[i])),
        forall|n: nat| #[trigger] u.red_rev.contains(n) ==> n < u.rec.len(),
        forall|i: int| 0 <= i < u.rec.len() && has_tomb(#[trigger] u.rec[i]) ==> !u.meta[i].text && u.meta[i].key is None,
        forall|p: nat| #[trigger] u.runs.contains_key(p) ==> cursor_ok(u, u.runs[p]),
{
    let n = s.rec.len();
    assert forall|i: int| 0 <= i < u.rec.len() implies (#[trigger] u.rec[i]).len() == u.orig[i].len() by {
        if i < n { assert(u.rec[i] == s.rec[i]); }
    }
    assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() implies l1::rec_ok(u.orig[i][j], #[trigger] u.rec[i][j]) by {
        if i < n { assert(u.rec[i] == s.rec[i]); }
    }
    assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && #[trigger] is_tomb(u.rec[i][j])
        implies l1::begun_member(u.begun, u.rec[i][j]->Tomb_0.id) by {
        if i < n { assert(u.rec[i] == s.rec[i]); }
    }
    assert forall|i: int| 0 <= i < u.rec.len() implies (u.red_rev.contains(i as nat) == has_tomb(#[trigger] u.rec[i])) by {
        if i < n { assert(u.rec[i] == s.rec[i]); } else {
            assert(!has_tomb(row));
            assert(!s.red_rev.contains(i as nat));
        }
    }
    assert forall|i: int| 0 <= i < u.rec.len() && has_tomb(#[trigger] u.rec[i]) implies !u.meta[i].text && u.meta[i].key is None by {
        if i < n { assert(u.rec[i] == s.rec[i]); assert(u.meta[i] == s.meta[i]); }
    }
    assert forall|p: nat| #[trigger] u.runs.contains_key(p) implies cursor_ok(u, u.runs[p]) by {
        let r = s.runs[p];
        assert(cursor_ok(s, r));
        assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && (i < r.i || (i == r.i && j < r.j))
            implies !live_member(#[trigger] u.rec[i][j], r.t) by {
            assert(i < n);
            assert(u.rec[i] == s.rec[i]);
        }
        if r.i < u.rec.len() && r.i < n { assert(u.rec[r.i as int] == s.rec[r.i as int]); }
    }
}

proof fn lemma_commit_inv(s: S2, cs: Seq<Content>, key: Option<Key>)
    requires inv2(s), commit_ok(s, cs, key),
    ensures inv2(commit(s, cs, key)),
{
    let u = commit(s, cs, key);
    let n = s.rec.len();
    assert forall|j: int| 0 <= j < lives(cs).len() implies !is_tomb(#[trigger] lives(cs)[j]) by {}
    lemma_append_keeps(s, u, lives(cs), Meta { text: true, key });
    assert(!has_tomb(lives(cs))) by {
        if has_tomb(lives(cs)) { let j = choose|j: int| 0 <= j < lives(cs).len() && #[trigger] is_tomb(lives(cs)[j]); }
    }
    assert forall|k: Key| #[trigger] u.idem.contains_key(k) implies
        u.idem[k] < u.rec.len() && u.meta[u.idem[k] as int].key == Some(k) && !has_tomb(u.rec[u.idem[k] as int]) by {
        if key == Some(k) {
            assert(u.rec[n as int] == lives(cs));
        } else {
            assert(s.idem.contains_key(k));
            assert(u.rec[s.idem[k] as int] == s.rec[s.idem[k] as int]);
            assert(u.meta[s.idem[k] as int] == s.meta[s.idem[k] as int]);
        }
    }
    assert forall|i: int| 0 <= i < u.rec.len() && (#[trigger] u.meta[i]).key is Some implies
        u.idem.contains_key(u.meta[i].key->0) && u.idem[u.meta[i].key->0] == i as nat by {
        if i < n {
            assert(u.meta[i] == s.meta[i]);
            if key == Some(s.meta[i].key->0) { assert(s.idem.contains_key(key->0)); }
        }
    }
}

proof fn lemma_start_inv(s: S2, p: nat, t: Tgt, fresh: bool)
    requires inv2(s), start_ok(s, p, t, fresh),
    ensures inv2(start(s, p, t)),
{
    let u = start(s, p, t);
    assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && #[trigger] is_tomb(u.rec[i][j])
        implies l1::begun_member(u.begun, u.rec[i][j]->Tomb_0.id) by {
        let g = choose|g: Tgt| #[trigger] s.begun.contains(g) && member(g, s.rec[i][j]->Tomb_0.id);
        assert(u.begun.contains(g));
    }
    assert forall|q: nat| #[trigger] u.runs.contains_key(q) implies cursor_ok(u, u.runs[q]) by {
        if q != p { assert(u.runs[q] == s.runs[q]); }
    }
}

proof fn lemma_scan_inv(s: S2, p: nat)
    requires inv2(s), scan_ok(s, p),
    ensures inv2(scan(s, p)),
{
    let u = scan(s, p);
    let r = s.runs[p];
    let i0 = r.i as int;
    let j0 = r.j as int;
    assert(cursor_ok(s, r));
    if r.j >= s.rec[i0].len() {
        assert forall|q: nat| #[trigger] u.runs.contains_key(q) implies cursor_ok(u, u.runs[q]) by {
            if q == p {
                let r2 = u.runs[q];
                assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && (i < r2.i || (i == r2.i && j < r2.j))
                    implies !live_member(#[trigger] u.rec[i][j], r2.t) by {
                    assert(i < i0 || (i == i0 && j < r.j));
                }
            } else { assert(u.runs[q] == s.runs[q]); }
        }
    } else if live_member(s.rec[i0][j0], r.t) {
        let c = s.rec[i0][j0]->Live_0;
        let t = r.t;
        assert(s.marker == Some(t));
        assert(s.begun.contains(t));
        assert(u.begun =~= s.begun);
        assert(rec_ok_live(s.orig[i0][j0], s.rec[i0][j0])) by { assert(l1::rec_ok(s.orig[i0][j0], s.rec[i0][j0])); }
        assert(u.rec.len() == s.rec.len());
        assert forall|i: int| 0 <= i < u.rec.len() && i != i0 implies #[trigger] u.rec[i] == s.rec[i] by {}
        assert(has_tomb(u.rec[i0])) by { assert(is_tomb(u.rec[i0][j0])); }
        assert forall|i: int| 0 <= i < u.rec.len() implies (#[trigger] u.rec[i]).len() == u.orig[i].len() by {
            if i != i0 { assert(u.rec[i] == s.rec[i]); }
        }
        assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() implies l1::rec_ok(u.orig[i][j], #[trigger] u.rec[i][j]) by {
            if i != i0 || j != j0 { if i != i0 { assert(u.rec[i] == s.rec[i]); } }
        }
        assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && #[trigger] is_tomb(u.rec[i][j])
            implies l1::begun_member(u.begun, u.rec[i][j]->Tomb_0.id) by {
            if i == i0 && j == j0 {
                assert(u.rec[i][j]->Tomb_0 == c);
                assert(u.begun.contains(t) && member(t, c.id));
            } else if i != i0 {
                assert(u.rec[i] == s.rec[i]);
            }
        }
        assert forall|i: int| 0 <= i < u.rec.len() implies (u.red_rev.contains(i as nat) == has_tomb(#[trigger] u.rec[i])) by {
            if i != i0 { assert(u.rec[i] == s.rec[i]); }
        }
        assert forall|i: int| 0 <= i < u.rec.len() && has_tomb(#[trigger] u.rec[i]) implies !u.meta[i].text && u.meta[i].key is None by {
            if i != i0 { assert(u.rec[i] == s.rec[i]); assert(u.meta[i] == s.meta[i]); }
            else if s.red_rev.contains(r.i) { assert(has_tomb(s.rec[i0])); }
        }
        assert forall|k: Key| #[trigger] u.idem.contains_key(k) implies
            u.idem[k] < u.rec.len() && u.meta[u.idem[k] as int].key == Some(k) && !has_tomb(u.rec[u.idem[k] as int]) by {
            assert(s.idem.contains_key(k));
            let i = s.idem[k] as int;
            if i == i0 {
                assert(s.meta[i0].key == Some(k));
                assert(!has_tomb(s.rec[i0]));
                assert(!s.red_rev.contains(r.i));
            } else {
                assert(u.rec[i] == s.rec[i]);
            }
        }
        assert forall|i: int| 0 <= i < u.rec.len() && (#[trigger] u.meta[i]).key is Some implies
            u.idem.contains_key(u.meta[i].key->0) && u.idem[u.meta[i].key->0] == i as nat by {
            if i != i0 {
                assert(u.meta[i] == s.meta[i]);
                let k = s.meta[i].key->0;
                if s.meta[i0].key == Some(k) { assert(s.idem[k] == i0 as nat); }
            } else if !s.red_rev.contains(r.i) {
            } else {
                assert(has_tomb(s.rec[i0]));
            }
        }
        assert forall|k: Key| #[trigger] u.idem_red.contains(k) implies !u.idem.contains_key(k) by {}
        assert forall|q: nat| #[trigger] u.runs.contains_key(q) implies cursor_ok(u, u.runs[q]) by {
            let rq = if q == p { r } else { s.runs[q] };
            assert(cursor_ok(s, rq));
            let r2 = u.runs[q];
            assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && (i < r2.i || (i == r2.i && j < r2.j))
                implies !live_member(#[trigger] u.rec[i][j], r2.t) by {
                if i == i0 && j == j0 {
                } else if i != i0 {
                    assert(u.rec[i] == s.rec[i]);
                } else {
                    assert(u.rec[i][j] == s.rec[i][j]);
                }
            }
        }
    } else {
        assert forall|q: nat| #[trigger] u.runs.contains_key(q) implies cursor_ok(u, u.runs[q]) by {
            if q == p {
                let r2 = u.runs[q];
                assert forall|i: int, j: int| 0 <= i < u.rec.len() && 0 <= j < u.rec[i].len() && (i < r2.i || (i == r2.i && j < r2.j))
                    implies !live_member(#[trigger] u.rec[i][j], r2.t) by {
                    if !(i < i0 || (i == i0 && j < r.j)) { assert(i == i0 && j == j0); }
                }
            } else { assert(u.runs[q] == s.runs[q]); }
        }
    }
}

pub open spec fn rec_ok_live(o: Rec, r: Rec) -> bool {
    r is Live ==> o == r
}

proof fn lemma_final_inv(s: S2, p: nat, t: Tgt, ok: bool)
    requires inv2(s), final_ok(s, p, t, ok),
    ensures inv2(final_step(s, p, ok)),
{
    let u = final_step(s, p, ok);
    if ok && s.counted {
        let row = seq![Rec::Audit];
        assert forall|j: int| 0 <= j < row.len() implies !is_tomb(#[trigger] row[j]) by {}
        lemma_append_keeps(s, u, row, Meta { text: false, key: None });
        assert forall|k: Key| #[trigger] u.idem.contains_key(k) implies
            u.idem[k] < u.rec.len() && u.meta[u.idem[k] as int].key == Some(k) && !has_tomb(u.rec[u.idem[k] as int]) by {
            assert(u.rec[s.idem[k] as int] == s.rec[s.idem[k] as int]);
            assert(u.meta[s.idem[k] as int] == s.meta[s.idem[k] as int]);
        }
        assert forall|i: int| 0 <= i < u.rec.len() && (#[trigger] u.meta[i]).key is Some implies
            u.idem.contains_key(u.meta[i].key->0) && u.idem[u.meta[i].key->0] == i as nat by {
            if i < s.rec.len() { assert(u.meta[i] == s.meta[i]); }
        }
    } else {
        assert forall|q: nat| #[trigger] u.runs.contains_key(q) implies cursor_ok(u, u.runs[q]) by {
            assert(u.runs[q] == s.runs[q]);
        }
    }
}

/// The invariant holds initially and is kept by every step: every execution of `step2` is an L2 execution.
pub proof fn theorem_inv2_inductive(s: S2, l: L2Label, u: S2)
    requires inv2(s), step2(s, l, u),
    ensures inv2(u),
{
    match l {
        L2Label::Commit { cs, key } => lemma_commit_inv(s, cs, key),
        L2Label::Start { p, t, fresh } => lemma_start_inv(s, p, t, fresh),
        L2Label::Scan { p } => lemma_scan_inv(s, p),
        L2Label::Final { p, t, ok } => lemma_final_inv(s, p, t, ok),
        L2Label::Stop { p } => {
            assert forall|q: nat| #[trigger] u.runs.contains_key(q) implies cursor_ok(u, u.runs[q]) by {
                assert(u.runs[q] == s.runs[q]);
            }
        }
        _ => {}
    }
}

pub proof fn theorem_inv2_init(s: S2)
    requires L2::init(s),
    ensures inv2(s),
{
}

/// **Composition with the business machine.** Every execution of the L2 machine is, under the abstraction, an
/// execution of L1 (with its internal steps as stutters), and every abstract state satisfies L1's invariants:
/// shape, isolation, Decision 2, the retry rule and the marker rule (actors::hierarchy::refinement_preserves_safety).
pub proof fn theorem_l2_satisfies_l1(states: Seq<S2>, labels: Seq<L2Label>)
    requires execution::<L2>(states, labels),
    ensures forall|i: int| 0 <= i < states.len() ==> l1::inv(#[trigger] abs(states[i])),
{
    refinement_preserves_safety::<L2, L1>(states, labels);
}

} // verus!
