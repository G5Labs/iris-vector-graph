//! Proved counterexample for control `control_f1511_upsert_before_load` (F-1511), compiled only with it.
//!
//! F-1511 (reproduced in the explorer model, cmc-register-as-built-refusal; live blocked-access: no FHIR repository on
//! Community): Register run again with new settings commits its upsert (FHIRGraph.cls:235-245), then LoadColumns
//! throws and the call answers {"status": "error"} (:274-276) with the new settings kept: not an L1 step (a refused
//! register changes nothing, INT-F3.9, SYS-I3).
use vstd::prelude::*;
use actors::protocol::*;
use crate::fhir_l1::*;
use crate::fhir_l2::*;
use crate::fhir_runs::*;

verus! {

broadcast use vstd::set_lib::range_set_properties;

pub open spec fn r0() -> F2 { f0(1, false) }
pub open spec fn r1() -> F2 { F2 { settings: 3, ..r0() } }

pub proof fn counterexample_f1511()
    ensures
        init2(r0()),
        step2(r0(), FL2::Register { ok: false, v: 3 }, r1()),
        !step_or_stutter::<FhirL1>(absf(r0()), labf(FL2::Register { ok: false, v: 3 }), absf(r1())),
        r1().settings != r0().settings && r1().wm == r0().wm,
{
    lemma_f_steps(r0(), 0, 3);
}

} // verus!
