//! M-02 instances: one type per object variant of mechanisms.json (family `retry`, models/semantics/src/retry.rs).
use vstd::prelude::*;
use crate::exec::*;
use crate::m02_retry::*;

verus! {

/// The reviewed ledger policy (LEDGER_RV of the explorer): binding atomic with the commit, application retries,
/// post-commit properties skipped on a replayed answer, redaction moves the binding.
pub open spec fn ledger_rv() -> RetryCfg {
    RetryCfg { dedup: Dedup::Atomic, client: ClientRetry::AppRetry, post: Post::SkipOnReplay, redact: Redact::Moves, rerun: false }
}

// ---------------------------------------------------------------- canonical and reviewed instances (baseline)

/// idempotent-setup: 01/setup-routine, 06/registry-row, 06/queue-entry (canonical: business-identity idempotence).
pub struct IdempotentSetup;
impl RetryPolicy for IdempotentSetup {
    open spec fn cfg() -> RetryCfg {
        RetryCfg { dedup: Dedup::Atomic, client: ClientRetry::AppRetry, post: Post::NoPost, redact: Redact::Moves, rerun: false }
    }
}
impl RetryObject for IdempotentSetup {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// ledger-key, reviewed: 11/retry-key.
pub struct LedgerKeyReviewed;
impl RetryPolicy for LedgerKeyReviewed { open spec fn cfg() -> RetryCfg { ledger_rv() } }
impl RetryObject for LedgerKeyReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// zero-record-revision, reviewed: 13/redaction-target (every revision's binding moves at redaction).
pub struct ZeroRecordRevisionReviewed;
impl RetryPolicy for ZeroRecordRevisionReviewed { open spec fn cfg() -> RetryCfg { ledger_rv() } }
impl RetryObject for ZeroRecordRevisionReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// client-resend, reviewed: 17/client-request (a POST with no dedup identity is not resent).
pub struct ClientResendReviewed;
impl RetryPolicy for ClientResendReviewed {
    open spec fn cfg() -> RetryCfg {
        RetryCfg { dedup: Dedup::NoDedup, client: ClientRetry::Never, post: Post::NoPost, redact: Redact::Moves, rerun: false }
    }
}
impl RetryObject for ClientResendReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

/// server-rerun, reviewed: 16/cypher-http-call (the server does not re-run a write).
pub struct ServerRerunReviewed;
impl RetryPolicy for ServerRerunReviewed {
    open spec fn cfg() -> RetryCfg {
        RetryCfg { dedup: Dedup::NoDedup, client: ClientRetry::Never, post: Post::NoPost, redact: Redact::Moves, rerun: false }
    }
}
impl RetryObject for ServerRerunReviewed {
    proof fn discharge_l1() {}
    proof fn discharge_l2() {}
    proof fn discharge_l3() {}
    proof fn discharge_l4() {}
}

pub proof fn laws_idempotent_setup(s0: RS, ls: Seq<RA>, t: RS, a: RA) requires reached::<RetryM<IdempotentSetup>>(s0, ls, t)
    ensures law_l1(t), law_l4(t) { theorem_retry::<IdempotentSetup>(s0, ls, t, a); }
pub proof fn laws_ledger_key_reviewed(s0: RS, ls: Seq<RA>, t: RS, a: RA) requires reached::<RetryM<LedgerKeyReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4(t) { theorem_retry::<LedgerKeyReviewed>(s0, ls, t, a); }
pub proof fn laws_zero_record_revision_reviewed(s0: RS, ls: Seq<RA>, t: RS, a: RA) requires reached::<RetryM<ZeroRecordRevisionReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4(t) { theorem_retry::<ZeroRecordRevisionReviewed>(s0, ls, t, a); }
pub proof fn laws_client_resend_reviewed(s0: RS, ls: Seq<RA>, t: RS, a: RA) requires reached::<RetryM<ClientResendReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4(t) { theorem_retry::<ClientResendReviewed>(s0, ls, t, a); }
pub proof fn laws_server_rerun_reviewed(s0: RS, ls: Seq<RA>, t: RS, a: RA) requires reached::<RetryM<ServerRerunReviewed>>(s0, ls, t)
    ensures law_l1(t), law_l4(t) { theorem_retry::<ServerRerunReviewed>(s0, ls, t, a); }

// ---------------------------------------------------------------- as-built variants that depart (parameters only)

/// ledger-key as built: 11/retry-key (F-1101, F-1306; Ledger.cls:454-473, client.py:418-487): the client re-applies
/// post-commit properties on a replayed answer.
pub struct LedgerKeyAsBuilt;
impl RetryPolicy for LedgerKeyAsBuilt { open spec fn cfg() -> RetryCfg { RetryCfg { post: Post::Always, ..ledger_rv() } } }
pub proof fn refute_ledger_key_l1() ensures !obl_l1::<LedgerKeyAsBuilt>() {}
pub proof fn refute_ledger_key_l2() ensures !obl_l2::<LedgerKeyAsBuilt>() {}
pub proof fn keep_ledger_key_l3() ensures obl_l3::<LedgerKeyAsBuilt>() {}
pub proof fn keep_ledger_key_l4() ensures obl_l4::<LedgerKeyAsBuilt>() {}

/// zero-record-revision as built: 13/redaction-target (F-CS01; LedgerApply.cls:229-233, 252-284): a revision whose
/// changeset recorded nothing is never touched by redaction, so its key stays bound.
pub struct ZeroRecordRevisionAsBuilt;
impl RetryPolicy for ZeroRecordRevisionAsBuilt { open spec fn cfg() -> RetryCfg { RetryCfg { redact: Redact::Keeps, ..ledger_rv() } } }
pub proof fn keep_zero_record_revision_l1() ensures obl_l1::<ZeroRecordRevisionAsBuilt>() {}
pub proof fn keep_zero_record_revision_l2() ensures obl_l2::<ZeroRecordRevisionAsBuilt>() {}
pub proof fn keep_zero_record_revision_l3() ensures obl_l3::<ZeroRecordRevisionAsBuilt>() {}
pub proof fn refute_zero_record_revision_l4() ensures !obl_l4::<ZeroRecordRevisionAsBuilt>() {}

/// client-resend as built: 17/client-request (F-C1703; sdk.py:209-228): the HTTP client resends a POST after a
/// timeout or a 5xx with no identity the server dedups on.
pub struct ClientResendAsBuilt;
impl RetryPolicy for ClientResendAsBuilt {
    open spec fn cfg() -> RetryCfg {
        RetryCfg { dedup: Dedup::NoDedup, client: ClientRetry::ResendOnLost, post: Post::NoPost, redact: Redact::Moves, rerun: false }
    }
}
pub proof fn refute_client_resend_l1() ensures !obl_l1::<ClientResendAsBuilt>() {}
pub proof fn keep_client_resend_l2() ensures obl_l2::<ClientResendAsBuilt>() {}
pub proof fn keep_client_resend_l3() ensures obl_l3::<ClientResendAsBuilt>() {}
pub proof fn keep_client_resend_l4() ensures obl_l4::<ClientResendAsBuilt>() {}

/// server-rerun as built: 16/cypher-http-call (F-C1604; cypher_api.py:239-268): the server runs the query again
/// after any exception, writes included.
pub struct ServerRerunAsBuilt;
impl RetryPolicy for ServerRerunAsBuilt {
    open spec fn cfg() -> RetryCfg {
        RetryCfg { dedup: Dedup::NoDedup, client: ClientRetry::Never, post: Post::NoPost, redact: Redact::Moves, rerun: true }
    }
}
pub proof fn refute_server_rerun_l1() ensures !obl_l1::<ServerRerunAsBuilt>() {}
pub proof fn keep_server_rerun_l2() ensures obl_l2::<ServerRerunAsBuilt>() {}
pub proof fn keep_server_rerun_l3() ensures obl_l3::<ServerRerunAsBuilt>() {}
pub proof fn keep_server_rerun_l4() ensures obl_l4::<ServerRerunAsBuilt>() {}

// ---------------------------------------------------------------- generic mutants of the reviewed ledger policy

/// retry-control-C1-bind-after-effect: the binding is written in a second step after the effect.
pub struct CtlBindAfterEffect;
impl RetryPolicy for CtlBindAfterEffect { open spec fn cfg() -> RetryCfg { RetryCfg { dedup: Dedup::TwoStep, ..ledger_rv() } } }
pub proof fn refute_ctl_bind_after_effect_l1() ensures !obl_l1::<CtlBindAfterEffect>() {}
pub proof fn keep_ctl_bind_after_effect_l2() ensures obl_l2::<CtlBindAfterEffect>() {}
pub proof fn keep_ctl_bind_after_effect_l3() ensures obl_l3::<CtlBindAfterEffect>() {}
pub proof fn keep_ctl_bind_after_effect_l4() ensures obl_l4::<CtlBindAfterEffect>() {}

/// retry-control-C2-post-on-replay: post-commit steps run on a replayed answer.
pub struct CtlPostOnReplay;
impl RetryPolicy for CtlPostOnReplay { open spec fn cfg() -> RetryCfg { RetryCfg { post: Post::Always, ..ledger_rv() } } }
pub proof fn refute_ctl_post_on_replay_l1() ensures !obl_l1::<CtlPostOnReplay>() {}
pub proof fn refute_ctl_post_on_replay_l2() ensures !obl_l2::<CtlPostOnReplay>() {}
pub proof fn keep_ctl_post_on_replay_l3() ensures obl_l3::<CtlPostOnReplay>() {}
pub proof fn keep_ctl_post_on_replay_l4() ensures obl_l4::<CtlPostOnReplay>() {}

/// retry-control-C3-apply-conflict: another payload under a bound key is applied and rebinds it.
pub struct CtlApplyConflict;
impl RetryPolicy for CtlApplyConflict { open spec fn cfg() -> RetryCfg { RetryCfg { dedup: Dedup::ApplyConflict, ..ledger_rv() } } }
pub proof fn refute_ctl_apply_conflict_l1() ensures !obl_l1::<CtlApplyConflict>() {}
pub proof fn keep_ctl_apply_conflict_l2() ensures obl_l2::<CtlApplyConflict>() {}
pub proof fn refute_ctl_apply_conflict_l3() ensures !obl_l3::<CtlApplyConflict>() {}
pub proof fn keep_ctl_apply_conflict_l4() ensures obl_l4::<CtlApplyConflict>() {}

/// retry-control-C4-redaction-keeps-binding: redaction keeps the binding.
pub struct CtlRedactionKeepsBinding;
impl RetryPolicy for CtlRedactionKeepsBinding { open spec fn cfg() -> RetryCfg { RetryCfg { redact: Redact::Keeps, ..ledger_rv() } } }
pub proof fn keep_ctl_redaction_keeps_binding_l1() ensures obl_l1::<CtlRedactionKeepsBinding>() {}
pub proof fn keep_ctl_redaction_keeps_binding_l2() ensures obl_l2::<CtlRedactionKeepsBinding>() {}
pub proof fn keep_ctl_redaction_keeps_binding_l3() ensures obl_l3::<CtlRedactionKeepsBinding>() {}
pub proof fn refute_ctl_redaction_keeps_binding_l4() ensures !obl_l4::<CtlRedactionKeepsBinding>() {}

// ---------------------------------------------------------------- non-vacuity (explorer sharpness witnesses)

/// retry-sharp-replay: a replayed answer is delivered (reviewed ledger key).
pub proof fn sharp_replay()
    ensures ({
        let t = run::<RetryM<LedgerKeyReviewed>>(retry_s0(), seq![RA::Send(1), RA::Lose, RA::Send(1), RA::Deliver]);
        t is Some && t->0.client == Client::Answered(Reply::Replay)
    })
{
    reveal_with_fuel(run, 5);
}

/// retry-sharp-conflict: a conflict refusal is delivered.
pub proof fn sharp_conflict()
    ensures ({
        let t = run::<RetryM<LedgerKeyReviewed>>(retry_s0(), seq![RA::Send(1), RA::Deliver, RA::PostStep, RA::Send(2), RA::Deliver]);
        t is Some && t->0.client == Client::Answered(Reply::Conflict)
    })
{
    reveal_with_fuel(run, 6);
}

/// retry-sharp-redacted-refusal: a retry is refused after redaction.
pub proof fn sharp_redacted_refusal()
    ensures ({
        let t = run::<RetryM<LedgerKeyReviewed>>(retry_s0(),
            seq![RA::Send(1), RA::Deliver, RA::PostStep, RA::RedactRev, RA::Send(1), RA::Deliver]);
        t is Some && t->0.client == Client::Answered(Reply::Refused)
    })
{
    reveal_with_fuel(run, 7);
}

} // verus!
