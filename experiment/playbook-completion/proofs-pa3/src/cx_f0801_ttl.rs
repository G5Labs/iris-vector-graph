//! Proved counterexample for control `control_f0801_ttl_cache` (F-0801, TTL window), compiled only with it.
//!
//! Engine E1's guard probes while strict mode is off and caches the answer; engine E2 turns strict mode on (its
//! set_strict refreshes only E2's guard, client.py:305-307); within the TTL E1's create_node lands. The step is a
//! governed write landing while the ledger is enabled in strict mode: not an L1 step.
use vstd::prelude::*;
use actors::protocol::*;
use crate::ledger_l1::*;
use crate::ledger_l2::*;
use crate::cx_ledger_common::*;

verus! {

pub open spec fn k1() -> K { K { id: 1, edge: false, gr: 0 } }
pub open spec fn c2() -> LS2 { LS2 { gcache: Some(Meta { state: LState::Enabled, strict: false }), ..c_genesis(false) } }
pub open spec fn c3() -> LS2 { LS2 { meta: Meta { state: LState::Enabled, strict: true }, ..c2() } }
pub open spec fn l4() -> L2Label { L2Label::EngineWrite { w: Wr::Api, k: k1(), v: Some(7), landed: true } }
pub open spec fn c4() -> LS2 { engine_write(c3(), Wr::Api, k1(), Some(7)) }

pub proof fn counterexample_f0801_ttl()
    ensures
        init2(c_init()),
        step2(c_init(), L2Label::Enable { strict: false, id: 1, recs: seq![], busy: false }, c_genesis(false)),
        step2(c_genesis(false), L2Label::GuardProbe, c2()),
        step2(c2(), L2Label::SetStrict { on: true }, c3()),
        step2(c3(), l4(), c4()),
        strict_on(c3().meta) && c4().rows.contains_key(k1()),
        !step_or_stutter::<L1>(abs11(c3()), lab11(l4()), abs11(c4())),
{
    lemma_genesis_step(false);
    assert(step2(c_genesis(false), L2Label::GuardProbe, c2()));
    assert(step2(c2(), L2Label::SetStrict { on: true }, c3()));
    assert(!refuses(c3(), Wr::Api));
    assert(step2(c3(), l4(), c4()));
}

} // verus!
