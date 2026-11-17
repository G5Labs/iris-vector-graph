// Ledger client, admission, error mapping, counters, caller transactions, readers, lifecycle, immutability and
// chunked transport. As-built transcription at product 3eaa79cf (iteration 60).
//
// Deciding sources (bound in crosswalk/decision-links.tsv): changeset.py (Changeset.validate, fingerprint,
// canonical_json, canonical_dumps), client.py (GraphLedger.commit/_commit/_send_changeset/_call/_emit/head/_seq_of/
// get_revision/diff/reconstruct/export_reconstruction/enable/disable/set_strict), errors.py (from_commit_error and the
// classes), Ledger.cls (Commit, CommitInTxn, WriteRevision, Err, ErrLimit, RevisionResponse, Head, SeqOf, State, Meta,
// Enable, Disable, SetStrict, StageChunk, LargeOut, ReadLargeOutChunk), LedgerStats.cls (Bump, PropertyFor),
// LedgerRevision.cls (RejectUpdate, RejectDelete, %OnBeforeSave, %OnDelete).
//
// Premises (not proved here): the apply outcome of an admitted changeset is supplied by `Apply` (its producer is the
// separate ledger_apply model); SHA-256 is collision-free where a theorem says so (`collision_free`); `NewId` GUIDs are
// fresh; a caller transaction's rollback undoes every journaled global and row it wrote (IRIS transactions). Redaction
// marker blocking (BlocksCommit, whether the applied records touch the target) is an input here (`Apply.blocked`,
// decided in ledger_redaction); the strict-mode guard is modelled in platform.
//
// Repair after review 60 (FE-3, FE-4, FE-5, FE-6): the counter row. A counted outcome saves the single ledger_stats row
// (WriteRevision's CommitsOk, or Bump after the commit's own level); inside a caller's transaction that row stays
// locked until the transaction ends, and another process's Bump waits about 10 s for it and is lost (observed: a
// lock-timeout refusal and a Ledger.Count call while the caller's transaction is open move no counter). Uncounted:
// not_enabled, empty, a redaction-blocked commit, and `inconsistent` (a revision row that does not fit its columns,
// LedgerRevision MAXLEN, or a counter row another transaction holds). Readers that take a revision ID refuse an
// unfinished redaction before looking the ID up.
use vstd::prelude::*;

verus! {

// =============================================================== changeset (client side)

/// A Changeset as the builder holds it. `ops` are canonical operation contents (canonical_dumps of each op dict);
/// `bad_ref` is the first operation whose op_ref does not name an earlier relationship operation (validate()).
pub struct Cs {
    pub actor: int,
    pub actor_type: int,
    pub message: int,
    pub correlation: int,
    pub key: Option<int>,
    pub expected: Option<int>,
    pub ops: Seq<int>,
    pub bad_ref: Option<nat>,
    /// lengths of the revision-row text fields this changeset fills (message, source JSON, actor, actor type,
    /// correlation ID, idempotency key)
    pub lens: Lens,
}

pub struct Lens { pub message: nat, pub source: nat, pub actor: nat, pub actor_type: nat, pub correlation: nat, pub key: nat }

/// LedgerRevision column limits (MAXLEN): message and source 4000; actor, correlation_id and idempotency_key 256;
/// actor_type 32. A longer value fails the revision row's %Save in WriteRevision.
pub open spec fn fits(c: Cs) -> bool {
    c.lens.message <= 4000 && c.lens.source <= 4000 && c.lens.actor <= 256 && c.lens.actor_type <= 32
        && c.lens.correlation <= 256 && c.lens.key <= 256
}

/// changeset.py fingerprint(): the hashed scope is {actor, actor_type, ops} only.
pub struct Scope {
    pub actor: int,
    pub actor_type: int,
    pub ops: Seq<int>,
}

pub open spec fn scope(c: Cs) -> Scope {
    Scope { actor: c.actor, actor_type: c.actor_type, ops: c.ops }
}

/// hashlib.sha256(canonical_dumps(scope)): the hash provider.
pub uninterp spec fn sha256(s: Scope) -> int;

pub open spec fn fingerprint(c: Cs) -> int {
    sha256(scope(c))
}

pub open spec fn collision_free() -> bool {
    forall|a: Scope, b: Scope| #![trigger sha256(a), sha256(b)] sha256(a) == sha256(b) ==> a == b
}

// =============================================================== server state

pub enum LState { Never, Enabled, Disabled }

/// Graph_KG.ledger_stats counters (LedgerStats properties).
pub struct Cnt {
    pub ok: nat,
    pub replays: nat,
    pub stale: nat,
    pub unknown: nat,
    pub conflict: nat,
    pub failed: nat,
    pub size: nat,
    pub disabled: nat,
    pub lock: nat,
    pub strict_block: nat,
}

pub struct Srv {
    /// ^IVG.Ledger("meta","state")
    pub state: LState,
    pub strict: bool,
    pub max_ops: nat,
    pub recon_bound: nat,
    /// ^IVG.Ledger("head")
    pub head: nat,
    /// ^IVG.Ledger("idBySeq", seq) and ("revById", id)
    pub id_of: Map<nat, int>,
    pub seq_of: Map<int, nat>,
    /// LedgerRevision.ParentId by seq
    pub parent: Map<nat, int>,
    /// ^IVG.Ledger("idem", key) = $LB(seq, fingerprint)
    pub idem: Map<int, (nat, int)>,
    /// ^IVG.Ledger("idemRedacted", sha256(key))
    pub redacted_keys: Set<int>,
    /// ghost: the operations each written revision applied, in seq order
    pub content: Seq<Seq<int>>,
    /// the process whose open transaction holds ^IVG.Ledger("head")
    pub holder: Option<nat>,
    /// the process whose open transaction has saved the ledger_stats row (holds its lock until it ends), and the
    /// counters as they were when it took the row
    pub stats_holder: Option<nat>,
    pub stats_base: Cnt,
    /// ^IVG.Ledger("redacting"): a redaction is unfinished
    pub redacting: bool,
    pub cnt: Cnt,
}

pub open spec fn head_id(s: Srv) -> int {
    s.id_of[s.head]
}

/// Everything except the counters and the lock holder.
pub open spec fn same_ledger(a: Srv, b: Srv) -> bool {
    &&& a.state == b.state && a.strict == b.strict && a.max_ops == b.max_ops && a.recon_bound == b.recon_bound
    &&& a.head == b.head && a.id_of == b.id_of && a.seq_of == b.seq_of && a.parent == b.parent
    &&& a.idem == b.idem && a.redacted_keys == b.redacted_keys && a.content == b.content
}

/// The apply outcome of an admitted changeset (LedgerApply.ApplyAll; ledger_apply model): first failing operation's
/// zero-based index, and the node it named when the reason is node_not_found.
pub struct Apply {
    pub ok: bool,
    pub index: nat,
    pub missing: Option<int>,
    /// LedgerRedact.BlocksCommit: the applied records touch the unfinished redaction's target (ledger_redaction)
    pub blocked: bool,
}

pub enum Code { NotEnabled, Disabled, Empty, TooLarge, StaleHead, UnknownHead, Conflict, IdemRedacted, FailedOp, LockTimeout, Inconsistent, RedactionInProgress, Other(int) }

/// Ledger.Err / ErrLimit / RevisionResponse JSON.
pub enum Wire {
    Ok { seq: nat, replayed: bool, stmts: bool },
    Err { code: Code, head: Option<int>, op_index: Option<nat>, missing: Option<int>, limit: Option<nat> },
}

pub open spec fn err(code: Code, head: Option<int>) -> Wire {
    Wire::Err { code, head, op_index: None, missing: None, limit: None }
}

/// Ledger.Commit sets pBump in CommitInTxn and calls LedgerStats.Bump after its level ends; PropertyFor maps the
/// column name; a refusal with no pBump (not_enabled, empty, inconsistent, redaction_in_progress) moves no counter.
pub open spec fn bump(c: Cnt, code: Code) -> Cnt {
    match code {
        Code::Disabled => Cnt { disabled: c.disabled + 1, ..c },
        Code::Conflict => Cnt { conflict: c.conflict + 1, ..c },
        Code::IdemRedacted => Cnt { conflict: c.conflict + 1, ..c },
        Code::UnknownHead => Cnt { unknown: c.unknown + 1, ..c },
        Code::StaleHead => Cnt { stale: c.stale + 1, ..c },
        Code::TooLarge => Cnt { size: c.size + 1, ..c },
        Code::FailedOp => Cnt { failed: c.failed + 1, ..c },
        Code::LockTimeout => Cnt { lock: c.lock + 1, ..c },
        _ => c,
    }
}

/// The counter row is free for process p unless another process's open transaction has saved it.
pub open spec fn stats_free(s: Srv, p: nat) -> bool {
    s.stats_holder is None || s.stats_holder == Some(p)
}

/// Bump(pBump) after the commit's level: counted only when the counter row is free; otherwise its %Save waits for the
/// row lock, fails, and the increment is lost (the refusal itself is still returned).
pub open spec fn refuse(s: Srv, w: Wire, p: nat) -> (Srv, Wire) {
    match w {
        Wire::Err { code, .. } => (if stats_free(s, p) { Srv { cnt: bump(s.cnt, code), ..s } } else { s }, w),
        _ => (s, w),
    }
}

/// Ledger.CommitInTxn (inside Commit's TSTART). Order: head lock, state, idempotency, redacted key, expected head,
/// empty/size, apply, redaction block, revision row (field limits), counter row, write. `p` is the calling process;
/// `fresh` is NewId(). The last three refusals have no pBump: they are uncounted.
pub open spec fn server(s: Srv, c: Cs, p: nat, a: Apply, fresh: int) -> (Srv, Wire) {
    if s.holder is Some && s.holder->Some_0 != p {
        refuse(s, err(Code::LockTimeout, None), p)
    } else if s.state == LState::Never {
        (s, err(Code::NotEnabled, None))
    } else if s.state == LState::Disabled {
        refuse(s, err(Code::Disabled, None), p)
    } else if c.key is Some && s.idem.contains_key(c.key->Some_0) {
        if s.idem[c.key->Some_0].1 == fingerprint(c) {
            (if stats_free(s, p) { Srv { cnt: Cnt { replays: s.cnt.replays + 1, ..s.cnt }, ..s } } else { s },
             Wire::Ok { seq: s.idem[c.key->Some_0].0, replayed: true, stmts: false })
        } else {
            refuse(s, err(Code::Conflict, Some(head_id(s))), p)
        }
    } else if c.key is Some && s.redacted_keys.contains(c.key->Some_0) {
        refuse(s, err(Code::IdemRedacted, Some(head_id(s))), p)
    } else if c.expected is Some && !s.seq_of.contains_key(c.expected->Some_0) {
        refuse(s, err(Code::UnknownHead, Some(head_id(s))), p)
    } else if c.expected is Some && c.expected->Some_0 != head_id(s) {
        refuse(s, err(Code::StaleHead, Some(head_id(s))), p)
    } else if c.ops.len() == 0 {
        (s, err(Code::Empty, Some(head_id(s))))
    } else if c.ops.len() > s.max_ops {
        refuse(s, Wire::Err { code: Code::TooLarge, head: None, op_index: None, missing: None, limit: Some(s.max_ops) }, p)
    } else if !a.ok {
        refuse(s, Wire::Err { code: Code::FailedOp, head: None, op_index: Some(a.index), missing: a.missing, limit: None }, p)
    } else if s.redacting && a.blocked {
        (s, err(Code::RedactionInProgress, None))
    } else if !fits(c) {
        (s, err(Code::Inconsistent, Some(head_id(s))))
    } else if !stats_free(s, p) {
        (s, err(Code::Inconsistent, Some(head_id(s))))
    } else {
        write(s, c, fresh)
    }
}

/// Ledger.WriteRevision + the idem binding, all inside the commit transaction.
pub open spec fn write(s: Srv, c: Cs, fresh: int) -> (Srv, Wire) {
    let n = s.head + 1;
    (Srv {
        head: n,
        id_of: s.id_of.insert(n, fresh),
        seq_of: s.seq_of.insert(fresh, n),
        parent: s.parent.insert(n, head_id(s)),
        idem: if c.key is Some { s.idem.insert(c.key->Some_0, (n, fingerprint(c))) } else { s.idem },
        content: s.content.push(c.ops),
        cnt: Cnt { ok: s.cnt.ok + 1, ..s.cnt },
        ..s
    }, Wire::Ok { seq: n, replayed: false, stmts: true })
}

// =============================================================== Python reader

pub enum Exc {
    Base, NotEnabled, Disabled, Empty, TooLarge { limit: Option<nat> }, Stale { current: Option<int> }, UnknownRev,
    Conflict, IdemRedacted, OpError { index: int }, NodeNotFound { index: int, node: int }, LockTimeout, Inconsistent, TxnOpen,
    RedactionInProgress,
}

/// errors.py from_commit_error.
pub open spec fn from_commit_error(w: Wire) -> Exc {
    match w {
        Wire::Err { code, head, op_index, missing, limit } => match code {
            Code::NotEnabled => Exc::NotEnabled,
            Code::Disabled => Exc::Disabled,
            Code::Empty => Exc::Empty,
            Code::TooLarge => Exc::TooLarge { limit },
            Code::StaleHead => Exc::Stale { current: head },
            Code::UnknownHead => Exc::UnknownRev,
            Code::Conflict => Exc::Conflict,
            Code::IdemRedacted => Exc::IdemRedacted,
            Code::FailedOp => {
                let i: int = if op_index is Some { op_index->Some_0 as int } else { -1 };
                if missing is Some { Exc::NodeNotFound { index: i, node: missing->Some_0 } } else { Exc::OpError { index: i } }
            },
            Code::LockTimeout => Exc::LockTimeout,
            Code::Inconsistent => Exc::Inconsistent,
            Code::RedactionInProgress => Exc::RedactionInProgress,
            Code::Other(_) => Exc::Base,
        },
        _ => Exc::Base,
    }
}

/// Class membership the caller can catch: NodeNotFoundError is a ChangesetOperationError, IdempotencyRedactedError an
/// IdempotencyConflictError; every class is a LedgerError.
pub open spec fn is_op_error(e: Exc) -> bool { e is OpError || e is NodeNotFound }
pub open spec fn is_conflict(e: Exc) -> bool { e is Conflict || e is IdemRedacted }

pub enum Py { Res { seq: nat, replayed: bool, stmts: bool }, Raise(Exc) }

/// A metrics-hook event (client._emit): one per server round trip.
pub enum Ev { Success(nat), Replayed(nat), Refused(Code) }

pub struct Out { pub srv: Srv, pub py: Py, pub events: Seq<Ev> }

pub open spec fn calls_server(c: Cs) -> bool { c.ops.len() > 0 && c.bad_ref is None }

/// GraphLedger.commit without a caller transaction: validate() first (no server call, no event), then _commit.
pub open spec fn client_commit(s: Srv, c: Cs, p: nat, a: Apply, fresh: int) -> Out {
    if c.ops.len() == 0 {
        Out { srv: s, py: Py::Raise(Exc::Empty), events: seq![] }
    } else if c.bad_ref is Some {
        Out { srv: s, py: Py::Raise(Exc::OpError { index: c.bad_ref->Some_0 as int }), events: seq![] }
    } else {
        let (s2, w) = server(s, c, p, a, fresh);
        match w {
            Wire::Ok { seq, replayed, stmts } => Out {
                srv: s2,
                py: Py::Res { seq, replayed, stmts },
                events: seq![if replayed { Ev::Replayed(seq) } else { Ev::Success(seq) }],
            },
            Wire::Err { code, .. } => Out { srv: s2, py: Py::Raise(from_commit_error(w)), events: seq![Ev::Refused(code)] },
        }
    }
}

// =============================================================== caller transactions

/// GraphLedger.commit inside the caller's transaction (write_txn; Ledger.Commit nested): the head lock the commit took
/// is released only when the caller's transaction ends (an unlock inside a transaction waits for its end), whatever
/// the outcome. A counted outcome also saved the counter row inside the caller's transaction, which then holds that
/// row until it ends; an uncounted refusal (not_enabled, inconsistent, redaction_in_progress) leaves the row free.
pub open spec fn txn_commit(s: Srv, c: Cs, p: nat, a: Apply, fresh: int) -> Out {
    let o = client_commit(s, c, p, a, fresh);
    let took_head = calls_server(c) && !(s.holder is Some && s.holder->Some_0 != p);
    let took_row = o.srv.cnt != s.cnt;
    Out {
        srv: Srv {
            holder: if took_head { Some(p) } else { o.srv.holder },
            stats_holder: if took_row { Some(p) } else { o.srv.stats_holder },
            stats_base: if took_row && o.srv.stats_holder != Some(p) { s.cnt } else { o.srv.stats_base },
            ..o.srv
        },
        ..o
    }
}

/// The caller's ROLLBACK: every journaled global and row of its transaction goes back. Its counter changes go back to
/// where they were when it took the counter row (no other process could move them after that); when it never took
/// the row, other processes' counts made meanwhile stay.
pub open spec fn txn_rollback(before: Srv, cur: Srv, p: nat) -> Srv {
    Srv { holder: None, stats_holder: None, cnt: if cur.stats_holder == Some(p) { cur.stats_base } else { cur.cnt }, ..before }
}

/// The caller's COMMIT keeps everything and frees the head and the counter row.
pub open spec fn txn_end(cur: Srv) -> Srv {
    Srv { holder: None, stats_holder: None, ..cur }
}

/// Ledger.Count(kind) from another process (the strict guard's LedgerGuard.count_rejection): LedgerStats.Bump in its
/// own transaction, lost while another process's transaction holds the counter row.
pub open spec fn count_strict(s: Srv, q: nat) -> Srv {
    if stats_free(s, q) { Srv { cnt: Cnt { strict_block: s.cnt.strict_block + 1, ..s.cnt }, ..s } } else { s }
}

// =============================================================== readers

pub enum Read { At(nat), Raise(Exc) }

/// get_revision, diff, reconstruct and export_reconstruction first refuse an unfinished redaction
/// (_refuse_while_redacting), then resolve the revision with GraphLedger._seq_of (Ledger.SeqOf) before reading anything.
pub open spec fn seq_read(s: Srv, id: int) -> Read {
    if s.redacting { Read::Raise(Exc::RedactionInProgress) }
    else if s.seq_of.contains_key(id) { Read::At(s.seq_of[id]) } else { Read::Raise(Exc::UnknownRev) }
}

/// GraphLedger.diff resolves both endpoints first.
pub open spec fn diff_read(s: Srv, a: int, b: int) -> Read {
    match seq_read(s, a) {
        Read::Raise(e) => Read::Raise(e),
        _ => seq_read(s, b),
    }
}

/// GraphLedger.head (Ledger.Head): refused only before the first enable.
pub open spec fn head_read(s: Srv) -> Read {
    if s.state == LState::Never { Read::Raise(Exc::NotEnabled) } else { Read::At(s.head) }
}

// =============================================================== lifecycle

pub enum EnableOut { Head(nat), Adoption, Genesis, Refused(Exc) }

/// GraphLedger.enable (client refusal of a caller transaction first) and Ledger.Enable.
pub open spec fn enable(s: Srv, strict: bool, max_ops: nat, recon: nat, in_txn: bool, fresh: int) -> (Srv, EnableOut) {
    if in_txn {
        (s, EnableOut::Refused(Exc::TxnOpen))
    } else if s.state == LState::Enabled {
        (s, EnableOut::Head(s.head))
    } else if s.state == LState::Disabled {
        (Srv { state: LState::Enabled, strict, ..s }, EnableOut::Adoption)
    } else {
        (Srv {
            state: LState::Enabled, strict, max_ops, recon_bound: recon, head: 1,
            id_of: s.id_of.insert(1, fresh), seq_of: s.seq_of.insert(fresh, 1),
            content: s.content.push(seq![]), cnt: Cnt { ok: s.cnt.ok + 1, ..s.cnt }, ..s
        }, EnableOut::Genesis)
    }
}

/// Ledger.Disable: only an enabled ledger changes.
pub open spec fn disable(s: Srv) -> Srv {
    if s.state == LState::Enabled { Srv { state: LState::Disabled, ..s } } else { s }
}

/// Ledger.SetStrict: refused only before the first enable; accepted while disabled.
pub open spec fn set_strict(s: Srv, flag: bool) -> (Srv, Option<Exc>) {
    if s.state == LState::Never { (s, Some(Exc::NotEnabled)) } else { (Srv { strict: flag, ..s }, None) }
}

// =============================================================== revision rows (LedgerRevision triggers)

pub struct RowUpdate {
    /// %IVGLedgerRedaction names this seq
    pub ctx_names_row: bool,
    /// ^IVG.Ledger("redactedRev", seq) exists
    pub redacted_rev: bool,
    /// any column other than message, source, correlation_id, idempotency_key changes
    pub other_changed: bool,
    /// all four new free-text values are empty
    pub free_text_emptied: bool,
}

/// RejectUpdate: the one redaction exception.
pub open spec fn update_allowed(u: RowUpdate) -> bool {
    u.ctx_names_row && u.redacted_rev && !u.other_changed && u.free_text_emptied
}

/// RejectDelete / %OnDelete: never. %OnBeforeSave: only an insert.
pub open spec fn delete_allowed() -> bool { false }
pub open spec fn object_save_allowed(insert: bool) -> bool { insert }

// =============================================================== chunked transport (CHUNK_CHARS / CHUNKCHARS)

/// client._send_changeset staging (payload[start:start+n] for start in range(0, len, n)) and Ledger.LargeOut
/// ($Extract(pJson, pos, pos+n-1) for pos = 1:n:len); both read back in index order.
pub open spec fn chunks(p: Seq<int>, n: nat) -> Seq<Seq<int>>
    decreases p.len(),
{
    if n == 0 || p.len() == 0 {
        seq![]
    } else if p.len() <= n {
        seq![p]
    } else {
        seq![p.subrange(0, n as int)] + chunks(p.subrange(n as int, p.len() as int), n)
    }
}

/// CommitInTxn's staged read ($Order over ^||IVG.LedgerStage) and client._call's "".join(ReadLargeOutChunk(tag, i)).
pub open spec fn join(cs: Seq<Seq<int>>) -> Seq<int>
    decreases cs.len(),
{
    if cs.len() == 0 { seq![] } else { cs[0] + join(cs.drop_first()) }
}

// =============================================================== theorems: fingerprint and replay

/// Metadata is outside the fingerprint: message, correlation ID, expected head and key do not change it.
pub proof fn theorem_metadata_outside_fingerprint(c: Cs, m: int, corr: int, k: Option<int>, e: Option<int>)
    ensures fingerprint(Cs { message: m, correlation: corr, key: k, expected: e, ..c }) == fingerprint(c),
{
    assert(scope(Cs { message: m, correlation: corr, key: k, expected: e, ..c }) == scope(c));
}

/// Under a collision-free hash, a different actor, actor type or operation list (order included) is a different
/// fingerprint.
pub proof fn theorem_scope_decides_fingerprint(c: Cs, d: Cs)
    requires collision_free(), scope(c) != scope(d),
    ensures fingerprint(c) != fingerprint(d),
{
}

/// Admission premises for a fresh keyed or unkeyed commit that writes.
pub open spec fn admits(s: Srv, c: Cs, p: nat, a: Apply) -> bool {
    &&& s.state == LState::Enabled
    &&& (s.holder is None || s.holder == Some(p))
    &&& (c.key is Some ==> !s.idem.contains_key(c.key->Some_0) && !s.redacted_keys.contains(c.key->Some_0))
    &&& c.expected is None
    &&& c.bad_ref is None
    &&& 0 < c.ops.len() <= s.max_ops
    &&& a.ok
    &&& !a.blocked
    &&& fits(c)
    &&& s.stats_holder is None
}

/// A retry with the same key, actor, actor type and operations but a new message, correlation ID and any expected
/// head (stale or unknown) replays the first revision, writes nothing, counts a replay and returns no statement IDs.
/// The retry's metadata lengths do not matter: the field limits are met only when a revision row is written.
pub proof fn theorem_retry_with_new_metadata_replays(s: Srv, c: Cs, m: int, corr: int, e: Option<int>, ml: Lens, p: nat, q: nat, a: Apply, b: Apply, f1: int, f2: int)
    requires admits(s, c, p, a), c.key is Some, s.holder is None,
    ensures ({
        let o1 = client_commit(s, c, p, a, f1);
        let d = Cs { message: m, correlation: corr, expected: e, lens: ml, ..c };
        let o2 = client_commit(o1.srv, d, q, b, f2);
        &&& o1.py == Py::Res { seq: s.head + 1, replayed: false, stmts: true }
        &&& o2.py == Py::Res { seq: s.head + 1, replayed: true, stmts: false }
        &&& same_ledger(o2.srv, o1.srv)
        &&& o2.srv.cnt == Cnt { replays: o1.srv.cnt.replays + 1, ..o1.srv.cnt }
        &&& o2.events == seq![Ev::Replayed(s.head + 1)]
    }),
{
    assert(scope(Cs { message: m, correlation: corr, expected: e, lens: ml, ..c }) == scope(c));
}

/// The same key with the operations in another order is a conflict: nothing written, one conflict counted.
pub proof fn theorem_reordered_operations_conflict(s: Srv, c: Cs, x: int, y: int, p: nat, q: nat, a: Apply, b: Apply, f1: int, f2: int)
    requires admits(s, c, p, a), c.key is Some, s.holder is None, collision_free(), x != y, c.ops == seq![x, y],
    ensures ({
        let o1 = client_commit(s, c, p, a, f1);
        let d = Cs { ops: seq![y, x], ..c };
        let o2 = client_commit(o1.srv, d, q, b, f2);
        &&& o2.py == Py::Raise(Exc::Conflict)
        &&& is_conflict(Exc::Conflict)
        &&& same_ledger(o2.srv, o1.srv)
        &&& o2.srv.cnt == Cnt { conflict: o1.srv.cnt.conflict + 1, ..o1.srv.cnt }
        &&& o2.events == seq![Ev::Refused(Code::Conflict)]
    }),
{
    let d = Cs { ops: seq![y, x], ..c };
    assert(scope(d).ops[0] != scope(c).ops[0]);
    theorem_scope_decides_fingerprint(c, d);
}

/// As built, a replay returns no statement IDs although the first commit returned them (bug-led-003's observation).
pub proof fn witness_replay_returns_no_statement_ids(s: Srv, c: Cs, p: nat, a: Apply, f1: int, f2: int)
    requires admits(s, c, p, a), c.key is Some, s.holder is None,
    ensures
        client_commit(s, c, p, a, f1).py is Res && client_commit(s, c, p, a, f1).py->stmts,
        client_commit(client_commit(s, c, p, a, f1).srv, c, p, a, f2).py == (Py::Res { seq: s.head + 1, replayed: true, stmts: false }),
{
}

// =============================================================== theorems: refusals and bindings

/// Every refusal leaves the ledger (head, revisions, parents, bindings, content) as it was.
pub proof fn theorem_refusal_writes_nothing(s: Srv, c: Cs, p: nat, a: Apply, f: int)
    ensures server(s, c, p, a, f).1 is Err ==> same_ledger(server(s, c, p, a, f).0, s) && server(s, c, p, a, f).0.holder == s.holder,
{
}

/// A key carried only by a refused (stale-head) commit stays free: the same key with other operations then commits.
pub proof fn theorem_refused_key_stays_free(s: Srv, c: Cs, d: Cs, k: int, e: int, p: nat, a: Apply, b: Apply, f1: int, f2: int)
    requires
        s.state == LState::Enabled, s.holder is None, s.stats_holder is None, c.key == Some(k), !s.idem.contains_key(k), !s.redacted_keys.contains(k),
        c.expected == Some(e), s.seq_of.contains_key(e), e != head_id(s), c.ops.len() > 0, c.bad_ref is None,
        d.key == Some(k), d.expected is None, d.bad_ref is None, 0 < d.ops.len() <= s.max_ops, b.ok, !b.blocked, fits(d),
    ensures ({
        let o1 = client_commit(s, c, p, a, f1);
        let o2 = client_commit(o1.srv, d, p, b, f2);
        &&& o1.py == Py::Raise(Exc::Stale { current: Some(head_id(s)) })
        &&& o2.py == Py::Res { seq: s.head + 1, replayed: false, stmts: true }
        &&& o2.srv.idem[k] == (s.head + 1, fingerprint(d))
    }),
{
}

/// Expected head: a revision of this ledger that is not the head → StaleHeadError naming the current head; an ID that
/// is no revision → UnknownRevisionError. Neither writes; each counts its own rejection (counter row free).
pub proof fn theorem_expected_head_outcomes(s: Srv, c: Cs, e: int, p: nat, a: Apply, f: int)
    requires s.state == LState::Enabled, s.holder is None, s.stats_holder is None, c.key is None, c.bad_ref is None, c.ops.len() > 0, c.expected == Some(e),
    ensures ({
        let o = client_commit(s, c, p, a, f);
        &&& !s.seq_of.contains_key(e) ==> o.py == Py::Raise(Exc::UnknownRev) && o.srv.cnt == (Cnt { unknown: s.cnt.unknown + 1, ..s.cnt })
        &&& s.seq_of.contains_key(e) && e != head_id(s) ==> o.py == Py::Raise(Exc::Stale { current: Some(head_id(s)) })
                && o.srv.cnt == (Cnt { stale: s.cnt.stale + 1, ..s.cnt })
        &&& (e != head_id(s) ==> same_ledger(o.srv, s))
    }),
{
}

/// Never enabled vs disabled: different classes; only the disabled refusal is counted. Both emit one event.
pub proof fn theorem_disabled_and_never_enabled(s: Srv, c: Cs, p: nat, a: Apply, f: int)
    requires s.holder is None, s.stats_holder is None, calls_server(c),
    ensures ({
        let o = client_commit(s, c, p, a, f);
        &&& s.state == LState::Never ==> o.py == Py::Raise(Exc::NotEnabled) && o.srv == s && o.events == seq![Ev::Refused(Code::NotEnabled)]
        &&& s.state == LState::Disabled ==> o.py == Py::Raise(Exc::Disabled) && same_ledger(o.srv, s)
                && o.srv.cnt == (Cnt { disabled: s.cnt.disabled + 1, ..s.cnt }) && o.events == seq![Ev::Refused(Code::Disabled)]
    }),
{
}

/// An empty changeset is refused by validate() before anything is sent, whatever the ledger's state, lock or head:
/// nothing changes, no counter moves, no hook event, the head lock is not taken.
pub proof fn theorem_empty_refused_before_the_server(s: Srv, c: Cs, p: nat, a: Apply, f: int)
    requires c.ops.len() == 0,
    ensures
        client_commit(s, c, p, a, f) == (Out { srv: s, py: Py::Raise(Exc::Empty), events: seq![] }),
        txn_commit(s, c, p, a, f).srv == s,
{
}

/// The size limit is inclusive: exactly max_ops operations commit; one more is refused with the limit attached.
pub proof fn theorem_size_limit_boundary(s: Srv, c: Cs, p: nat, a: Apply, f: int)
    requires s.state == LState::Enabled, s.holder is None, s.stats_holder is None, c.key is None, c.expected is None, c.bad_ref is None,
        s.max_ops > 0, a.ok, !a.blocked, fits(c),
    ensures
        c.ops.len() == s.max_ops ==> client_commit(s, c, p, a, f).py == (Py::Res { seq: s.head + 1, replayed: false, stmts: true }),
        c.ops.len() == s.max_ops + 1 ==> client_commit(s, c, p, a, f).py == Py::Raise(Exc::TooLarge { limit: Some(s.max_ops) })
            && same_ledger(client_commit(s, c, p, a, f).srv, s)
            && client_commit(s, c, p, a, f).srv.cnt == (Cnt { size: s.cnt.size + 1, ..s.cnt }),
{
}

/// A failing operation is reported by its zero-based position; node_not_found narrows to NodeNotFoundError, which is
/// still a ChangesetOperationError. Nothing is written and one failed_op rejection is counted.
pub proof fn theorem_failed_operation_reported(s: Srv, c: Cs, p: nat, a: Apply, f: int)
    requires admits(s, Cs { ..c }, p, Apply { ok: true, ..a }), !a.ok, c.key is None,
    ensures ({
        let o = client_commit(s, c, p, a, f);
        &&& a.missing is Some ==> o.py == Py::Raise(Exc::NodeNotFound { index: a.index as int, node: a.missing->Some_0 })
        &&& a.missing is None ==> o.py == Py::Raise(Exc::OpError { index: a.index as int })
        &&& is_op_error(o.py->Raise_0)
        &&& same_ledger(o.srv, s)
        &&& o.srv.cnt == Cnt { failed: s.cnt.failed + 1, ..s.cnt }
    }),
{
}

/// The mapper's narrowing and fallbacks: a missing op_index reads -1; an unrecognised code is a plain LedgerError.
pub proof fn theorem_error_mapping_fallbacks(i: nat, n: int, h: Option<int>, x: int)
    ensures
        from_commit_error(Wire::Err { code: Code::FailedOp, head: h, op_index: Some(i), missing: Some(n), limit: None })
            == (Exc::NodeNotFound { index: i as int, node: n }),
        from_commit_error(Wire::Err { code: Code::FailedOp, head: h, op_index: None, missing: None, limit: None }) == (Exc::OpError { index: -1 }),
        from_commit_error(err(Code::Other(x), h)) == Exc::Base,
        from_commit_error(err(Code::NotEnabled, h)) != from_commit_error(err(Code::Disabled, h)),
        from_commit_error(err(Code::StaleHead, h)) != from_commit_error(err(Code::UnknownHead, h)),
        is_conflict(from_commit_error(err(Code::IdemRedacted, h))),
        from_commit_error(err(Code::Inconsistent, h)) == Exc::Inconsistent,
        from_commit_error(err(Code::RedactionInProgress, h)) == Exc::RedactionInProgress,
{
}

// =============================================================== theorems: caller transactions

/// A commit inside a caller's transaction holds the head lock and the counter row until the transaction ends: another
/// process's commit is refused with LedgerLockTimeoutError, changes nothing and is NOT counted (its Bump waits for the
/// row and is lost; repaired after review 60 FE-3: the iteration-60 claim was `lock + 1`); after the caller's rollback
/// the same commit gets the next seq with the last kept revision as parent (no gap) and the counters are the caller's
/// starting ones plus that commit; had the caller committed, it builds on the caller's revision.
pub proof fn theorem_caller_transaction_holds_the_head(s: Srv, c: Cs, d: Cs, p: nat, q: nat, a: Apply, b: Apply, f1: int, f2: int)
    requires
        p != q, admits(s, c, p, a), s.holder is None, c.key is None,
        d.key is None, d.expected is None, d.bad_ref is None, 0 < d.ops.len() <= s.max_ops, b.ok, !b.blocked, fits(d),
    ensures ({
        let o1 = txn_commit(s, c, p, a, f1);
        let o2 = client_commit(o1.srv, d, q, b, f2);
        let o3 = client_commit(txn_rollback(s, o2.srv, p), d, q, b, f2);
        let o4 = client_commit(txn_end(o1.srv), d, q, b, f2);
        &&& o1.py == Py::Res { seq: s.head + 1, replayed: false, stmts: true }
        &&& o1.srv.holder == Some(p) && o1.srv.stats_holder == Some(p)
        &&& o2.py == Py::Raise(Exc::LockTimeout)
        &&& o2.events == seq![Ev::Refused(Code::LockTimeout)]
        &&& same_ledger(o2.srv, o1.srv) && o2.srv.cnt == o1.srv.cnt
        &&& o3.py == Py::Res { seq: s.head + 1, replayed: false, stmts: true }
        &&& o3.srv.parent[s.head + 1] == head_id(s)
        &&& o3.srv.cnt == (Cnt { ok: s.cnt.ok + 1, ..s.cnt })
        &&& o4.py == Py::Res { seq: s.head + 2, replayed: false, stmts: true }
        &&& o4.srv.parent[s.head + 2] == f1
    }),
{
}

/// A nested commit refused without a count (here: a revision row that does not fit its columns) still holds the head
/// until the caller's transaction ends, but not the counter row: another process's commit times out and its
/// lock-timeout refusal IS counted, and that count survives the caller's rollback (observed: 30 s and +1, against 40 s
/// and +0 when the nested commit was counted).
pub proof fn theorem_uncounted_nested_refusal_leaves_the_counter_row(s: Srv, c: Cs, d: Cs, p: nat, q: nat, a: Apply, b: Apply, f1: int, f2: int)
    requires
        p != q, s.state == LState::Enabled, s.holder is None, s.stats_holder is None, c.key is None, c.expected is None,
        c.bad_ref is None, 0 < c.ops.len() <= s.max_ops, a.ok, !a.blocked, !fits(c),
        d.key is None, d.expected is None, d.bad_ref is None, 0 < d.ops.len() <= s.max_ops,
    ensures ({
        let o1 = txn_commit(s, c, p, a, f1);
        let o2 = client_commit(o1.srv, d, q, b, f2);
        &&& o1.py == Py::Raise(Exc::Inconsistent) && o1.events == seq![Ev::Refused(Code::Inconsistent)]
        &&& same_ledger(o1.srv, s) && o1.srv.cnt == s.cnt
        &&& o1.srv.holder == Some(p) && o1.srv.stats_holder is None
        &&& o2.py == Py::Raise(Exc::LockTimeout)
        &&& o2.srv.cnt == (Cnt { lock: s.cnt.lock + 1, ..s.cnt })
        &&& txn_rollback(s, o2.srv, p).cnt.lock == s.cnt.lock + 1
    }),
{
}

/// Which server outcomes are counted. With the counter row free: a written revision counts commits_ok, a replay
/// replays_idem, and each refusal its own rejection kind (`bump`), except not_enabled, a redaction-blocked commit and
/// `inconsistent` (a revision row that does not fit its columns), which move no counter. Each of these still sends one
/// hook event and writes nothing. While another process's transaction holds the counter row, no outcome of this
/// process is counted, and the strict guard's count call is lost too.
pub proof fn theorem_uncounted_outcomes(s: Srv, c: Cs, p: nat, a: Apply, f: int, r: nat)
    requires calls_server(c),
    ensures ({
        let o = client_commit(s, c, p, a, f);
        &&& (s.holder is None || s.holder == Some(p)) && s.state == LState::Enabled
            && (c.key is None) && c.expected is None && c.ops.len() <= s.max_ops && a.ok && s.redacting && a.blocked
            ==> o.py == Py::Raise(Exc::RedactionInProgress) && o.srv == s && o.events == seq![Ev::Refused(Code::RedactionInProgress)]
        &&& (s.holder is None || s.holder == Some(p)) && s.state == LState::Enabled
            && (c.key is None) && c.expected is None && c.ops.len() <= s.max_ops && a.ok && !(s.redacting && a.blocked) && !fits(c)
            ==> o.py == Py::Raise(Exc::Inconsistent) && o.srv == s && o.events == seq![Ev::Refused(Code::Inconsistent)]
        &&& s.state == LState::Never && (s.holder is None || s.holder == Some(p))
            ==> o.srv == s && o.py == Py::Raise(Exc::NotEnabled)
        &&& !stats_free(s, p) ==> o.srv.cnt == s.cnt
        &&& r != p && s.stats_holder == Some(r) ==> count_strict(s, p) == s
        &&& stats_free(s, p) ==> count_strict(s, p).cnt == (Cnt { strict_block: s.cnt.strict_block + 1, ..s.cnt })
    }),
{
}

/// A keyed retry is decided by its key before the revision row: the same key and operations with a message too long
/// for its column replay the first revision instead of failing (observed).
pub proof fn theorem_field_limits_checked_after_the_key(s: Srv, c: Cs, ml: Lens, p: nat, a: Apply, b: Apply, f1: int, f2: int)
    requires admits(s, c, p, a), c.key is Some, s.holder is None, ml.message > 4000,
    ensures ({
        let o1 = client_commit(s, c, p, a, f1);
        let d = Cs { lens: ml, ..c };
        &&& !fits(d)
        &&& client_commit(o1.srv, d, p, b, f2).py == Py::Res { seq: s.head + 1, replayed: true, stmts: false }
        &&& client_commit(s, d, p, a, f1).py == Py::Raise(Exc::Inconsistent)
    }),
{
    assert(scope(Cs { lens: ml, ..c }) == scope(c));
}

/// A caller's rollback takes back the revision, its seq and its idempotency binding: the key is free again and the
/// next commit reuses the seq.
pub proof fn theorem_rollback_frees_key_and_seq(s: Srv, c: Cs, d: Cs, p: nat, q: nat, a: Apply, b: Apply, f1: int, f2: int)
    requires
        admits(s, c, p, a), s.holder is None, c.key is Some,
        d.key == c.key, d.expected is None, d.bad_ref is None, 0 < d.ops.len() <= s.max_ops, b.ok, !b.blocked, fits(d),
    ensures ({
        let o1 = txn_commit(s, c, p, a, f1);
        let s1 = txn_rollback(s, o1.srv, p);
        let o2 = client_commit(s1, d, q, b, f2);
        &&& o1.py == Py::Res { seq: s.head + 1, replayed: false, stmts: true }
        &&& same_ledger(s1, s) && s1.holder is None && s1.cnt == s.cnt
        &&& o2.py == Py::Res { seq: s.head + 1, replayed: false, stmts: true }
        &&& o2.srv.id_of[s.head + 1] == f2
    }),
{
}

// =============================================================== theorems: readers and lifecycle

/// Every revision reader first refuses an unfinished redaction (RedactionInProgressError, for a known or unknown ID
/// alike), then resolves its ID: an ID that is no revision raises UnknownRevisionError before any read or file write;
/// a committed revision's ID resolves to its seq.
pub proof fn theorem_revision_readers_resolve_ids(s: Srv, id: int, other: int, c: Cs, p: nat, a: Apply, f: int)
    ensures
        s.redacting ==> seq_read(s, id) == Read::Raise(Exc::RedactionInProgress)
            && diff_read(s, id, other) == Read::Raise(Exc::RedactionInProgress),
        !s.redacting && !s.seq_of.contains_key(id) ==> seq_read(s, id) == Read::Raise(Exc::UnknownRev)
            && diff_read(s, id, other) == Read::Raise(Exc::UnknownRev) && diff_read(s, other, id) is Raise,
        !s.redacting && s.seq_of.contains_key(id) ==> seq_read(s, id) == Read::At(s.seq_of[id]),
        !s.redacting && admits(s, c, p, a) && s.holder is None ==> seq_read(client_commit(s, c, p, a, f).srv, f) == Read::At(s.head + 1),
{
}

/// head() before the first enable raises LedgerNotEnabledError; while disabled it still reads the head.
pub proof fn theorem_head_reader_states(s: Srv)
    ensures
        s.state == LState::Never ==> head_read(s) == Read::Raise(Exc::NotEnabled),
        s.state == LState::Disabled ==> head_read(s) == Read::At(s.head),
        s.state == LState::Enabled ==> head_read(s) == Read::At(s.head),
{
}

/// Enable: on an enabled ledger nothing changes, strict included (enable(strict=True) does not switch it on); after a
/// disable it re-enables with strict taken from this call while max_ops and the reconstruction bound stay; the first
/// enable fixes the bounds; inside a caller transaction it is refused.
pub proof fn theorem_enable_lifecycle(s: Srv, strict: bool, mo: nat, rb: nat, f: int)
    ensures
        s.state == LState::Enabled ==> enable(s, strict, mo, rb, false, f) == (s, EnableOut::Head(s.head)),
        s.state == LState::Disabled ==> enable(s, strict, mo, rb, false, f).0 == (Srv { state: LState::Enabled, strict, ..s })
            && enable(s, strict, mo, rb, false, f).1 == EnableOut::Adoption,
        s.state == LState::Never ==> enable(s, strict, mo, rb, false, f).0.max_ops == mo
            && enable(s, strict, mo, rb, false, f).0.recon_bound == rb && enable(s, strict, mo, rb, false, f).0.head == 1
            && enable(s, strict, mo, rb, false, f).0.strict == strict,
        enable(s, strict, mo, rb, true, f) == (s, EnableOut::Refused(Exc::TxnOpen)),
{
}

/// Disable is idempotent and changes only an enabled ledger; set_strict is refused only before the first enable.
pub proof fn theorem_disable_and_set_strict(s: Srv, flag: bool)
    ensures
        disable(disable(s)) == disable(s),
        s.state != LState::Enabled ==> disable(s) == s,
        s.state == LState::Never ==> set_strict(s, flag) == (s, Some(Exc::NotEnabled)),
        s.state != LState::Never ==> set_strict(s, flag).0.strict == flag && set_strict(s, flag).1 is None,
{
}

/// As built: strict set while disabled is overwritten by the next enable's argument (default False).
pub proof fn witness_strict_set_while_disabled_is_reset_by_enable(s: Srv, f: int)
    requires s.state == LState::Disabled,
    ensures !enable(set_strict(s, true).0, false, 50000, 250000, false, f).0.strict,
{
}

/// One metrics-hook event per call that reaches the server, whatever its outcome; none for a client-side refusal
/// (empty changeset, bad op_ref), against the hook document's "once per call, whatever the outcome".
pub proof fn theorem_one_event_per_server_call(s: Srv, c: Cs, p: nat, a: Apply, f: int)
    ensures client_commit(s, c, p, a, f).events.len() == (if calls_server(c) { 1nat } else { 0nat }),
{
}

// =============================================================== revision source (CommitInTxn, RevisionObj, fetch_history)

/// A changeset's `source`: absent, a text value, or an object whose canonical JSON text is `j`.
pub enum Src { Absent, Text(int), Object(int) }

/// CommitInTxn stores `source` only when it is a JSON object (`%GetTypeOf = "object"`); anything else is stored empty.
pub open spec fn stored_source(x: Src) -> Option<int> {
    match x { Src::Object(j) => Some(j), _ => None }
}

/// history(source=f) pushes `source = ?` to SQL: it matches only the stored text.
pub open spec fn source_filter_matches(stored: Option<int>, f: int) -> bool {
    stored == Some(f)
}

/// As built: a text source is dropped without an error, so the revision has no source and no history filter finds it;
/// an object source is found only by its exact stored JSON text.
pub proof fn witness_text_source_is_dropped(t: int, j: int, k: int)
    requires k != j,
    ensures
        stored_source(Src::Text(t)) is None,
        !source_filter_matches(stored_source(Src::Text(t)), t),
        source_filter_matches(stored_source(Src::Object(j)), j),
        !source_filter_matches(stored_source(Src::Object(j)), k),
{
}

// =============================================================== theorems: immutability and transport

/// Revision rows: no delete and no object re-save; an update passes only as the redaction exception (the row's seq
/// named by the redaction, its redactedRev entry, nothing but the four free-text fields changed, all four emptied).
pub proof fn theorem_revision_rows_immutable(u: RowUpdate)
    ensures
        !delete_allowed(),
        !object_save_allowed(false) && object_save_allowed(true),
        !u.ctx_names_row ==> !update_allowed(u),
        u.other_changed ==> !update_allowed(u),
        !u.free_text_emptied ==> !update_allowed(u),
        update_allowed(RowUpdate { ctx_names_row: true, redacted_rev: true, other_changed: false, free_text_emptied: true }),
{
}

pub proof fn lemma_join_chunks(p: Seq<int>, n: nat)
    requires n > 0,
    ensures join(chunks(p, n)) == p,
        forall|i: int| 0 <= i < chunks(p, n).len() ==> (#[trigger] chunks(p, n)[i]).len() <= n,
    decreases p.len(),
{
    if p.len() == 0 {
        assert(join(chunks(p, n)) =~= p);
    } else if p.len() <= n {
        let cs = chunks(p, n);
        assert(cs == seq![p]);
        assert(cs.drop_first() =~= Seq::<Seq<int>>::empty());
        assert(join(cs.drop_first()) =~= Seq::<int>::empty());
        assert(join(cs) =~= p);
    } else {
        let head = p.subrange(0, n as int);
        let rest = p.subrange(n as int, p.len() as int);
        lemma_join_chunks(rest, n);
        let cs = chunks(p, n);
        assert(cs == seq![head] + chunks(rest, n));
        assert(cs.drop_first() =~= chunks(rest, n));
        assert(cs[0] == head);
        assert(join(cs) == head + join(chunks(rest, n)));
        assert(head + rest =~= p);
        assert forall|i: int| 0 <= i < cs.len() implies (#[trigger] cs[i]).len() <= n by {
            if i > 0 { assert(cs[i] == chunks(rest, n)[i - 1]); }
        }
    }
}

/// A payload above one chunk is staged in chunks of at most CHUNK_CHARS that the server joins back exactly; a large
/// answer is staged and joined the same way; at or below the limit there is one piece (sent inline).
pub proof fn theorem_chunked_transport_roundtrip(p: Seq<int>)
    ensures
        join(chunks(p, 1000000)) == p,
        forall|i: int| 0 <= i < chunks(p, 1000000).len() ==> (#[trigger] chunks(p, 1000000)[i]).len() <= 1000000,
        0 < p.len() <= 1000000 ==> chunks(p, 1000000) == seq![p],
{
    lemma_join_chunks(p, 1000000);
}

} // verus!
