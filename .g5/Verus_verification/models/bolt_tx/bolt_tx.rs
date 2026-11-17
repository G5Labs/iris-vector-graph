// product 3eaa79cf: Bolt explicit transactions (iteration 56, review 53-55 item F1; inherited F-1601).
//   Bolt server (iris_vector_graph/bolt_server.py), the session's message dispatch BoltSession._dispatch 459-519
//   (TcpBoltSession inherits it):
//     BEGIN (0x11)    500-501: answers SUCCESS {"db": "neo4j"}; no transaction state is opened.
//     RUN (0x10)      _handle_run 567-622: engine.execute_cypher(query) on the session's engine. The engine's
//                     connection has no open caller transaction, so each write commits when the call returns
//                     (premise P-AUTOCOMMIT: the engine's per-call nesting, USER_GUIDE "Transactions": with no caller
//                     transaction a write commits when the call returns). An exception or result.error answers
//                     FAILURE and sets the session FAILED; a failed statement leaves no writes (premise P-STMT-ATOMIC).
//     PULL (0x3F)     _handle_pull 624-660: answers the pending rows; no store effect.
//     COMMIT (0x12)   502-504: answers SUCCESS, state READY; no store effect.
//     ROLLBACK (0x13) 505-510: clears the pending rows, answers SUCCESS, state READY; no store effect.
//     RESET (0x0F)    _handle_reset 662-667: clears pending rows, READY, SUCCESS; no store effect.
//     GOODBYE / a closed connection: no store effect.
//     FAILED state 465-472: RESET is handled, GOODBYE ends the session, every other message answers IGNORED.
//   Rule (access.bolt.transactions; Bolt protocol: a transaction's writes are kept only by COMMIT, and ROLLBACK, a
//   failure, RESET or a closed connection discard them): the client ledger `neo` below. The as-built `step` departs
//   from it exactly when a transaction that does not end in COMMIT ran a write (theorem_rollback_departs_iff_writes).
//   Two repairs are checked against the rule: refusing BEGIN (design Refuse, proved here) and buffering the
//   transaction's writes (control `atomic-tx`, which must break every departure theorem).
use vstd::prelude::*;
verus! {

pub enum Msg { Begin, Run(nat, bool), Pull, Commit, Rollback, Reset, Close }
pub enum Ans { Success, Failure, Ignored }
pub enum Design { AsBuilt, Refuse }

/// Server state: the committed node count the final reader sees, whether the session is FAILED, and the writes held
/// for an open transaction (never set as built: the server keeps no transaction).
pub struct S { pub store: nat, pub failed: bool, pub tx: Option<nat> }

/// One message's effect and answer. `Run(w, fails)`: a statement that would create w nodes, and whether it fails.
pub open spec fn step(d: Design, s: S, m: Msg) -> (S, Ans) {
    if s.failed {
        match m {
            Msg::Reset => (S { store: s.store, failed: false, tx: None }, Ans::Success),
            _ => (s, Ans::Ignored),
        }
    } else {
        match d {
            Design::Refuse => match m {
                Msg::Begin => (S { store: s.store, failed: true, tx: None }, Ans::Failure),
                Msg::Run(w, fails) => if fails { (S { store: s.store, failed: true, tx: s.tx }, Ans::Failure) }
                    else { (S { store: s.store + w, failed: false, tx: s.tx }, Ans::Success) },
                _ => (s, Ans::Success),
            },
            Design::AsBuilt => match m {
                Msg::Begin => (s, Ans::Success),
                Msg::Run(w, fails) => if fails { (S { store: s.store, failed: true, tx: s.tx }, Ans::Failure) }
                    else { (S { store: s.store + w, failed: false, tx: s.tx }, Ans::Success) },
                Msg::Pull => (s, Ans::Success),
                Msg::Commit => (s, Ans::Success),
                Msg::Rollback => (s, Ans::Success),
                Msg::Reset => (s, Ans::Success),
                Msg::Close => (s, Ans::Success),
            },
        }
    }
}

pub open spec fn exec(d: Design, s: S, ms: Seq<Msg>) -> (S, Seq<Ans>)
    decreases ms.len()
{
    if ms.len() == 0 { (s, Seq::empty()) }
    else {
        let r = step(d, s, ms[0]);
        let t = exec(d, r.0, ms.drop_first());
        (t.0, seq![r.1] + t.1)
    }
}

// ------------------------------------------------------------------ the rule: the client's ledger (Bolt semantics)
pub struct C { pub store: nat, pub tx: Option<nat>, pub failed: bool }

pub open spec fn neo_step(c: C, m: Msg) -> C {
    if c.failed {
        match m {
            Msg::Reset => C { store: c.store, tx: None, failed: false },
            Msg::Close => C { store: c.store, tx: None, failed: false },
            _ => c,
        }
    } else {
        match m {
            Msg::Begin => C { store: c.store, tx: Some(0), failed: false },
            Msg::Run(w, fails) => if fails { C { store: c.store, tx: c.tx, failed: true } }
                else { match c.tx { Some(p) => C { store: c.store, tx: Some(p + w), failed: false },
                                    None => C { store: c.store + w, tx: None, failed: false } } },
            Msg::Pull => c,
            Msg::Commit => match c.tx { Some(p) => C { store: c.store + p, tx: None, failed: false }, None => c },
            Msg::Rollback => C { store: c.store, tx: None, failed: false },
            Msg::Reset => C { store: c.store, tx: None, failed: false },
            Msg::Close => C { store: c.store, tx: None, failed: false },
        }
    }
}

pub open spec fn neo(c: C, ms: Seq<Msg>) -> C
    decreases ms.len()
{
    if ms.len() == 0 { c } else { neo(neo_step(c, ms[0]), ms.drop_first()) }
}

pub open spec fn c0(s: S) -> C { C { store: s.store, tx: None, failed: false } }

// ------------------------------------------------------------------ shapes
/// Statements that succeed (and PULLs): what a client runs inside a transaction before ending it.
pub open spec fn plain(ms: Seq<Msg>) -> bool
    decreases ms.len()
{
    if ms.len() == 0 { true }
    else { (match ms[0] { Msg::Run(_, f) => !f, Msg::Pull => true, _ => false }) && plain(ms.drop_first()) }
}

pub open spec fn total(ms: Seq<Msg>) -> nat
    decreases ms.len()
{
    if ms.len() == 0 { 0 } else { (match ms[0] { Msg::Run(w, _) => w, _ => 0nat }) + total(ms.drop_first()) }
}

pub open spec fn all_are(xs: Seq<Ans>, a: Ans) -> bool { forall|i: int| 0 <= i < xs.len() ==> xs[i] == a }

// ------------------------------------------------------------------ lemmas
pub proof fn lemma_exec_append(d: Design, s: S, a: Seq<Msg>, b: Seq<Msg>)
    ensures
        exec(d, s, a + b).0 == exec(d, exec(d, s, a).0, b).0,
        exec(d, s, a + b).1 == exec(d, s, a).1 + exec(d, exec(d, s, a).0, b).1,
    decreases a.len()
{
    if a.len() == 0 {
        assert(a + b =~= b);
        assert(Seq::<Ans>::empty() + exec(d, s, b).1 =~= exec(d, s, b).1);
    } else {
        assert((a + b).drop_first() =~= a.drop_first() + b);
        assert((a + b)[0] == a[0]);
        let r = step(d, s, a[0]);
        lemma_exec_append(d, r.0, a.drop_first(), b);
        let x = exec(d, r.0, a.drop_first()).1;
        let y = exec(d, exec(d, r.0, a.drop_first()).0, b).1;
        assert(seq![r.1] + (x + y) =~= (seq![r.1] + x) + y);
    }
}

pub proof fn lemma_neo_append(c: C, a: Seq<Msg>, b: Seq<Msg>)
    ensures neo(c, a + b) == neo(neo(c, a), b),
    decreases a.len()
{
    if a.len() == 0 { assert(a + b =~= b); }
    else {
        assert((a + b).drop_first() =~= a.drop_first() + b);
        assert((a + b)[0] == a[0]);
        lemma_neo_append(neo_step(c, a[0]), a.drop_first(), b);
    }
}

pub proof fn lemma_one(d: Design, s: S, m: Msg)
    ensures exec(d, s, seq![m]).0 == step(d, s, m).0, exec(d, s, seq![m]).1 == seq![step(d, s, m).1],
{
    reveal_with_fuel(exec, 2);
    assert(seq![m][0] == m);
    assert(seq![m].drop_first() =~= Seq::<Msg>::empty());
    assert(seq![step(d, s, m).1] + Seq::<Ans>::empty() =~= seq![step(d, s, m).1]);
}

pub proof fn lemma_neo_one(c: C, m: Msg)
    ensures neo(c, seq![m]) == neo_step(c, m),
{
    reveal_with_fuel(neo, 2);
    assert(seq![m][0] == m);
    assert(seq![m].drop_first() =~= Seq::<Msg>::empty());
}

/// As built, successful statements commit one by one, whatever came before: the store grows by their writes.
pub proof fn lemma_plain_as_built(s: S, ms: Seq<Msg>)
    requires !s.failed, plain(ms),
    ensures
        exec(Design::AsBuilt, s, ms).0 == (S { store: s.store + total(ms), failed: false, tx: s.tx }),
        exec(Design::AsBuilt, s, ms).1.len() == ms.len(),
        all_are(exec(Design::AsBuilt, s, ms).1, Ans::Success),
    decreases ms.len()
{
    if ms.len() > 0 {
        let r = step(Design::AsBuilt, s, ms[0]);
        assert(!r.0.failed && r.1 == Ans::Success);
        lemma_plain_as_built(r.0, ms.drop_first());
        let rest = exec(Design::AsBuilt, r.0, ms.drop_first()).1;
        assert forall|i: int| 0 <= i < (seq![r.1] + rest).len() implies (seq![r.1] + rest)[i] == Ans::Success by {
            if i > 0 { assert((seq![r.1] + rest)[i] == rest[i - 1]); }
        }
    }
}

/// A FAILED session ignores successful statements and PULLs (either design).
pub proof fn lemma_plain_failed(d: Design, s: S, ms: Seq<Msg>)
    requires s.failed, plain(ms),
    ensures exec(d, s, ms).0 == s, exec(d, s, ms).1.len() == ms.len(), all_are(exec(d, s, ms).1, Ans::Ignored),
    decreases ms.len()
{
    if ms.len() > 0 {
        lemma_plain_failed(d, s, ms.drop_first());
        let rest = exec(d, s, ms.drop_first()).1;
        assert forall|i: int| 0 <= i < (seq![Ans::Ignored] + rest).len() implies (seq![Ans::Ignored] + rest)[i] == Ans::Ignored by {
            if i > 0 { assert((seq![Ans::Ignored] + rest)[i] == rest[i - 1]); }
        }
    }
}

pub proof fn lemma_plain_neo(c: C, ms: Seq<Msg>)
    requires !c.failed, plain(ms),
    ensures
        neo(c, ms) == (match c.tx { Some(p) => C { store: c.store, tx: Some(p + total(ms)), failed: false },
                                    None => C { store: c.store + total(ms), tx: None, failed: false } }),
    decreases ms.len()
{
    if ms.len() > 0 { lemma_plain_neo(neo_step(c, ms[0]), ms.drop_first()); }
}

/// Splits `[m] + inner + tail` into its three parts for both machines.
pub proof fn lemma_shape(d: Design, s: S, m: Msg, inner: Seq<Msg>, tail: Seq<Msg>)
    ensures
        exec(d, s, seq![m] + inner + tail).0
            == exec(d, exec(d, exec(d, s, seq![m]).0, inner).0, tail).0,
        exec(d, s, seq![m] + inner + tail).1
            == exec(d, s, seq![m]).1 + exec(d, exec(d, s, seq![m]).0, inner).1
               + exec(d, exec(d, exec(d, s, seq![m]).0, inner).0, tail).1,
        neo(c0(s), seq![m] + inner + tail) == neo(neo(neo(c0(s), seq![m]), inner), tail),
{
    lemma_exec_append(d, s, seq![m] + inner, tail);
    lemma_exec_append(d, s, seq![m], inner);
    lemma_neo_append(c0(s), seq![m] + inner, tail);
    lemma_neo_append(c0(s), seq![m], inner);
}

// ------------------------------------------------------------------ theorems (as built)
pub open spec fn rb_shape(inner: Seq<Msg>) -> Seq<Msg> { seq![Msg::Begin] + inner + seq![Msg::Rollback] }
pub open spec fn commit_shape(inner: Seq<Msg>) -> Seq<Msg> { seq![Msg::Begin] + inner + seq![Msg::Commit] }

/// BEGIN, the statements and ROLLBACK are all answered SUCCESS, yet every write of the transaction stays.
pub proof fn theorem_rollback_keeps_writes(s: S, inner: Seq<Msg>)
    requires !s.failed, s.tx is None, plain(inner),
    ensures
        exec(Design::AsBuilt, s, rb_shape(inner)).0.store == s.store + total(inner),
        all_are(exec(Design::AsBuilt, s, rb_shape(inner)).1, Ans::Success),
        neo(c0(s), rb_shape(inner)).store == s.store,
{
    lemma_shape(Design::AsBuilt, s, Msg::Begin, inner, seq![Msg::Rollback]);
    lemma_one(Design::AsBuilt, s, Msg::Begin);
    lemma_plain_as_built(s, inner);
    let s2 = exec(Design::AsBuilt, s, inner).0;
    lemma_one(Design::AsBuilt, s2, Msg::Rollback);
    let a = exec(Design::AsBuilt, s, rb_shape(inner)).1;
    let mid = exec(Design::AsBuilt, s, inner).1;
    assert(a == seq![Ans::Success] + mid + seq![Ans::Success]);
    assert forall|i: int| 0 <= i < a.len() implies a[i] == Ans::Success by {
        if i == 0 {} else if i <= mid.len() { assert(a[i] == mid[i - 1]); } else {}
    }
    lemma_neo_one(c0(s), Msg::Begin);
    lemma_plain_neo(neo_step(c0(s), Msg::Begin), inner);
    lemma_neo_one(neo(neo_step(c0(s), Msg::Begin), inner), Msg::Rollback);
}

/// The departure is exactly the transaction's writes: a rollback of a write-free transaction agrees with the rule.
pub proof fn theorem_rollback_departs_iff_writes(s: S, inner: Seq<Msg>)
    requires !s.failed, s.tx is None, plain(inner),
    ensures
        (exec(Design::AsBuilt, s, rb_shape(inner)).0.store != neo(c0(s), rb_shape(inner)).store) <==> total(inner) > 0,
{
    theorem_rollback_keeps_writes(s, inner);
}

/// Neighbor: a committed transaction keeps its writes on both.
pub proof fn theorem_commit_agrees(s: S, inner: Seq<Msg>)
    requires !s.failed, s.tx is None, plain(inner),
    ensures
        exec(Design::AsBuilt, s, commit_shape(inner)).0.store == s.store + total(inner),
        neo(c0(s), commit_shape(inner)).store == s.store + total(inner),
        exec(Design::AsBuilt, s, commit_shape(inner)).1.last() == Ans::Success,
{
    lemma_shape(Design::AsBuilt, s, Msg::Begin, inner, seq![Msg::Commit]);
    lemma_one(Design::AsBuilt, s, Msg::Begin);
    lemma_plain_as_built(s, inner);
    lemma_one(Design::AsBuilt, exec(Design::AsBuilt, s, inner).0, Msg::Commit);
    lemma_neo_one(c0(s), Msg::Begin);
    lemma_plain_neo(neo_step(c0(s), Msg::Begin), inner);
    lemma_neo_one(neo(neo_step(c0(s), Msg::Begin), inner), Msg::Commit);
}

/// Neighbor: statements outside a transaction (auto-commit) keep their writes on both.
pub proof fn theorem_autocommit_agrees(s: S, inner: Seq<Msg>)
    requires !s.failed, s.tx is None, plain(inner),
    ensures
        exec(Design::AsBuilt, s, inner).0.store == s.store + total(inner),
        neo(c0(s), inner).store == s.store + total(inner),
{
    lemma_plain_as_built(s, inner);
    lemma_plain_neo(c0(s), inner);
}

pub open spec fn fail_shape(inner: Seq<Msg>, v: nat) -> Seq<Msg> {
    seq![Msg::Begin] + inner + seq![Msg::Run(v, true), Msg::Pull, Msg::Rollback, Msg::Reset]
}

/// A statement fails inside the transaction: the failure is answered, PULL and ROLLBACK are IGNORED, RESET succeeds,
/// and the earlier statements' writes stay; the rule discards them.
pub proof fn theorem_failed_tx_keeps_earlier_writes(s: S, inner: Seq<Msg>, v: nat)
    requires !s.failed, s.tx is None, plain(inner),
    ensures
        exec(Design::AsBuilt, s, fail_shape(inner, v)).0.store == s.store + total(inner),
        !exec(Design::AsBuilt, s, fail_shape(inner, v)).0.failed,
        exec(Design::AsBuilt, s, fail_shape(inner, v)).1
            == seq![Ans::Success] + exec(Design::AsBuilt, s, inner).1
               + seq![Ans::Failure, Ans::Ignored, Ans::Ignored, Ans::Success],
        neo(c0(s), fail_shape(inner, v)).store == s.store,
{
    let tail = seq![Msg::Run(v, true), Msg::Pull, Msg::Rollback, Msg::Reset];
    lemma_shape(Design::AsBuilt, s, Msg::Begin, inner, tail);
    lemma_one(Design::AsBuilt, s, Msg::Begin);
    lemma_plain_as_built(s, inner);
    let s2 = exec(Design::AsBuilt, s, inner).0;
    reveal_with_fuel(exec, 5);
    assert(tail.drop_first() =~= seq![Msg::Pull, Msg::Rollback, Msg::Reset]);
    assert(tail.drop_first().drop_first() =~= seq![Msg::Rollback, Msg::Reset]);
    assert(tail.drop_first().drop_first().drop_first() =~= seq![Msg::Reset]);
    assert(tail.drop_first().drop_first().drop_first().drop_first() =~= Seq::<Msg>::empty());
    assert(exec(Design::AsBuilt, s2, tail).1 =~= seq![Ans::Failure, Ans::Ignored, Ans::Ignored, Ans::Success]);
    lemma_neo_one(c0(s), Msg::Begin);
    lemma_plain_neo(neo_step(c0(s), Msg::Begin), inner);
    reveal_with_fuel(neo, 5);
}

/// RESET or a closed connection in the middle of a transaction keeps its writes too; the rule discards them.
pub proof fn theorem_reset_or_close_keeps_writes(s: S, inner: Seq<Msg>, end: Msg)
    requires !s.failed, s.tx is None, plain(inner), end == Msg::Reset || end == Msg::Close,
    ensures
        exec(Design::AsBuilt, s, seq![Msg::Begin] + inner + seq![end]).0.store == s.store + total(inner),
        neo(c0(s), seq![Msg::Begin] + inner + seq![end]).store == s.store,
{
    lemma_shape(Design::AsBuilt, s, Msg::Begin, inner, seq![end]);
    lemma_one(Design::AsBuilt, s, Msg::Begin);
    lemma_plain_as_built(s, inner);
    lemma_one(Design::AsBuilt, exec(Design::AsBuilt, s, inner).0, end);
    lemma_neo_one(c0(s), Msg::Begin);
    lemma_plain_neo(neo_step(c0(s), Msg::Begin), inner);
    lemma_neo_one(neo(neo_step(c0(s), Msg::Begin), inner), end);
}

// ------------------------------------------------------------------ the checked alternative repair: refuse BEGIN
/// Refusing BEGIN tells the client there is no transaction: the following statements are IGNORED until RESET, so no
/// write the client meant to roll back is kept, and the store agrees with the rule.
pub proof fn theorem_refusal_matches_rule(s: S, inner: Seq<Msg>)
    requires !s.failed, s.tx is None, plain(inner),
    ensures
        exec(Design::Refuse, s, seq![Msg::Begin] + inner + seq![Msg::Rollback, Msg::Reset]).1[0] == Ans::Failure,
        exec(Design::Refuse, s, seq![Msg::Begin] + inner + seq![Msg::Rollback, Msg::Reset]).0.store == s.store,
        neo(c0(s), seq![Msg::Begin] + inner + seq![Msg::Rollback, Msg::Reset]).store == s.store,
{
    let tail = seq![Msg::Rollback, Msg::Reset];
    lemma_shape(Design::Refuse, s, Msg::Begin, inner, tail);
    lemma_one(Design::Refuse, s, Msg::Begin);
    let s1 = step(Design::Refuse, s, Msg::Begin).0;
    lemma_plain_failed(Design::Refuse, s1, inner);
    reveal_with_fuel(exec, 3);
    assert(tail.drop_first() =~= seq![Msg::Reset]);
    assert(tail.drop_first().drop_first() =~= Seq::<Msg>::empty());
    lemma_neo_one(c0(s), Msg::Begin);
    lemma_plain_neo(neo_step(c0(s), Msg::Begin), inner);
    reveal_with_fuel(neo, 3);
}

// ------------------------------------------------------------------ concrete witnesses (the binding's shapes)
pub proof fn theorem_witness_one_create_rolled_back()
    ensures
        exec(Design::AsBuilt, S { store: 0, failed: false, tx: None }, rb_shape(seq![Msg::Run(1, false), Msg::Pull])).0.store == 1,
        neo(C { store: 0, tx: None, failed: false }, rb_shape(seq![Msg::Run(1, false), Msg::Pull])).store == 0,
{
    let inner = seq![Msg::Run(1, false), Msg::Pull];
    reveal_with_fuel(plain, 3);
    reveal_with_fuel(total, 3);
    assert(inner.drop_first() =~= seq![Msg::Pull]);
    assert(inner.drop_first().drop_first() =~= Seq::<Msg>::empty());
    theorem_rollback_keeps_writes(S { store: 0, failed: false, tx: None }, inner);
}

} // verus!
