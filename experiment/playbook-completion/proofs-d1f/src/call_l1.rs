//! Modules 16 and 17, L1: one call of a Cypher query over HTTP (IVGClient -> POST /api/cypher -> the Cypher HTTP
//! server -> IRIS), as its caller sees it.
//!
//! State: the query's kind (`op`), how many times its write has been applied in IRIS (`applied`), and the answer the
//! caller got (`answer`: success, a definite failure, or an unknown outcome). Labels: the write takes effect
//! (`Apply`) and the caller gets an answer (`Answer`).
//!
//! Business rules (decisions.md HD-1603 and HD-1702, working answers, one combined protocol; SYS-I6 states the same
//! "never saves twice" for the ledger's retry key, which /api/cypher does not carry):
//! - **at most once**: a write is applied at most once per call, whatever is retried;
//! - **a definite failure applied nothing**: a caller told "failed" (not "unknown") can retry safely;
//! - **success means applied**: a write answered with success was applied.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;

verus! {

pub enum Op { Read, Write }
pub enum Outcome { Success, Failed, Unknown }

pub struct C1 { pub op: Op, pub applied: nat, pub answer: Option<Outcome> }

pub enum CL1 { Apply, Answer { o: Outcome } }

pub struct CallL1;

impl Contract for CallL1 {
    type S = C1;
    type L = CL1;

    open spec fn init(s: C1) -> bool { s.applied == 0 && s.answer is None }

    open spec fn next(s: C1, l: CL1, t: C1) -> bool {
        match l {
            CL1::Apply =>
                s.op is Write && s.applied == 0 && s.answer != Some(Outcome::Failed) && t == C1 { applied: 1, ..s },
            CL1::Answer { o } =>
                s.answer is None && t == C1 { answer: Some(o), ..s }
                    && (o is Success ==> (s.op is Read || s.applied == 1))
                    && (o is Failed ==> s.applied == 0),
        }
    }
}

pub open spec fn inv1(s: C1) -> bool {
    &&& s.applied <= 1
    &&& s.op is Read ==> s.applied == 0
    &&& s.answer == Some(Outcome::Failed) ==> s.applied == 0
    &&& (s.answer == Some(Outcome::Success) && s.op is Write) ==> s.applied == 1
}

impl SafeContract for CallL1 {
    open spec fn inv(s: C1) -> bool { inv1(s) }
    proof fn init_safe(s: C1) {}
    proof fn step_safe(s: C1, l: CL1, t: C1) {}
}

/// HD-1603 / HD-1702: a call applies its write at most once.
pub proof fn theorem_at_most_once(s: C1)
    requires inv1(s),
    ensures s.applied <= 1,
{
}

/// A caller told "failed" saw no effect, now or later (no step applies a write after a definite failure).
pub proof fn theorem_definite_failure_applied_nothing(s: C1, l: CL1, t: C1)
    requires inv1(s), s.answer == Some(Outcome::Failed), CallL1::next(s, l, t),
    ensures t.applied == 0,
{
}

/// A write answered with success was applied, exactly once.
pub proof fn theorem_success_means_applied_once(s: C1)
    requires inv1(s), s.answer == Some(Outcome::Success), s.op is Write,
    ensures s.applied == 1,
{
}

} // verus!
