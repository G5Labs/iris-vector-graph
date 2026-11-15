//! M-02 counterexamples: for each departing variant and each law it breaks, a run of the generic machine with that
//! variant's parameters from the initial state to a violation (the explorer's counterexample, restated).
use vstd::prelude::*;
use crate::exec::*;
use crate::m02_retry::*;
use crate::i02_retry::*;

verus! {

/// F-1101/F-1306: the replayed answer re-runs the post-commit step: two post-commit effects.
pub proof fn cx_ledger_key_l1()
    ensures ({
        let t = run::<RetryM<LedgerKeyAsBuilt>>(retry_s0(), seq![RA::Send(1), RA::Deliver, RA::PostStep, RA::Send(1), RA::Deliver, RA::PostStep]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// F-1306: a post-commit step on a replayed answer changes the post-commit effects.
pub proof fn cx_ledger_key_l2()
    ensures ({
        let s = run::<RetryM<LedgerKeyAsBuilt>>(retry_s0(), seq![RA::Send(1), RA::Deliver, RA::PostStep, RA::Send(1), RA::Deliver]);
        let a = RA::PostStep;
        s is Some && retry_step::<LedgerKeyAsBuilt>(s->0, a) is Some && !law_l2(s->0, a, retry_step::<LedgerKeyAsBuilt>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 6);
}

/// F-CS01: the revision is redacted and its key is still bound.
pub proof fn cx_zero_record_revision_l4()
    ensures ({
        let t = run::<RetryM<ZeroRecordRevisionAsBuilt>>(retry_s0(), seq![RA::Send(1), RA::RedactRev]);
        t is Some && !law_l4(t->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// F-C1703: the answer is lost and the client resends: two effects.
pub proof fn cx_client_resend_l1()
    ensures ({
        let t = run::<RetryM<ClientResendAsBuilt>>(retry_s0(), seq![RA::Send(1), RA::Lose, RA::Send(1)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// F-C1604: the server re-runs the request after an error raised after its commit: two effects.
pub proof fn cx_server_rerun_l1()
    ensures ({
        let t = run::<RetryM<ServerRerunAsBuilt>>(retry_s0(), seq![RA::Send(1), RA::Rerun]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 3);
}

/// C1: a stop between the effect and the binding; the retry applies again.
pub proof fn cx_ctl_bind_after_effect_l1()
    ensures ({
        let t = run::<RetryM<CtlBindAfterEffect>>(retry_s0(), seq![RA::Send(1), RA::Stop, RA::Send(1)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// C2: two post-commit effects.
pub proof fn cx_ctl_post_on_replay_l1()
    ensures ({
        let t = run::<RetryM<CtlPostOnReplay>>(retry_s0(), seq![RA::Send(1), RA::Deliver, RA::PostStep, RA::Send(1), RA::Deliver, RA::PostStep]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 7);
}

/// C2: a post-commit step on a replayed answer.
pub proof fn cx_ctl_post_on_replay_l2()
    ensures ({
        let s = run::<RetryM<CtlPostOnReplay>>(retry_s0(), seq![RA::Send(1), RA::Deliver, RA::PostStep, RA::Send(1), RA::Deliver]);
        let a = RA::PostStep;
        s is Some && retry_step::<CtlPostOnReplay>(s->0, a) is Some && !law_l2(s->0, a, retry_step::<CtlPostOnReplay>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 6);
}

/// C3: another payload under the bound key is applied: two effects.
pub proof fn cx_ctl_apply_conflict_l1()
    ensures ({
        let t = run::<RetryM<CtlApplyConflict>>(retry_s0(), seq![RA::Send(1), RA::Deliver, RA::PostStep, RA::Send(2)]);
        t is Some && !law_l1(t->0)
    })
{
    reveal_with_fuel(run, 5);
}

/// C3: another payload under the bound key changes the effects.
pub proof fn cx_ctl_apply_conflict_l3()
    ensures ({
        let s = run::<RetryM<CtlApplyConflict>>(retry_s0(), seq![RA::Send(1), RA::Deliver, RA::PostStep]);
        let a = RA::Send(2);
        s is Some && retry_step::<CtlApplyConflict>(s->0, a) is Some && !law_l3(s->0, a, retry_step::<CtlApplyConflict>(s->0, a)->0)
    })
{
    reveal_with_fuel(run, 4);
}

/// C4: redaction keeps the binding.
pub proof fn cx_ctl_redaction_keeps_binding_l4()
    ensures ({
        let t = run::<RetryM<CtlRedactionKeepsBinding>>(retry_s0(), seq![RA::Send(1), RA::RedactRev]);
        t is Some && !law_l4(t->0)
    })
{
    reveal_with_fuel(run, 3);
}

} // verus!
