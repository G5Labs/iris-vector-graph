//! Proved counterexample for control `control_f0103_marker_admits` (F-0103), compiled only with it.
//!
//! The live probe breadth-a-live-01-install (p0103_no_record_marker_accepted: check_first_access accepted with the
//! record removed and the marker class present): setup of schema 1 creates its tables and its SQL functions (the
//! marker class `<package>.funcCYCMP`) and stops before its record; an engine of schema 1 is then admitted with no
//! record, which is not an L1 step (L1 refuses: the namespace is bound to nothing).
use vstd::prelude::*;
use actors::protocol::*;
use crate::inst_l1::*;
use crate::inst_l2::*;
use crate::inst_runs::*;

verus! {

pub open spec fn c0() -> IS2 { i0(false, Set::empty(), Set::empty(), Set::empty()) }
pub open spec fn c1() -> IS2 { p_begin(c0(), 1) }
pub open spec fn c2() -> IS2 { p_ddl(c1(), true) }
pub open spec fn c3() -> IS2 { p_funcs(c2()) }
pub open spec fn c4() -> IS2 { p_end(c3()) }

pub proof fn counterexample_f0103()
    ensures
        init2(c0()),
        step2(c0(), IL2::Begin { schema: 1 }, c1()),
        step2(c1(), IL2::Ddl { ok: true }, c2()),
        step2(c2(), IL2::Funcs, c3()),
        step2(c3(), IL2::Stop, c4()),
        c4().rec is None,
        step2(c4(), IL2::Access { schema: 1, adm: Adm::Accepted }, c4()),
        !step_or_stutter::<InstL1>(absi(c4()), labi(IL2::Access { schema: 1, adm: Adm::Accepted }), absi(c4())),
{
    lemma_i_steps(c0(), 1, true, true, 0);
    lemma_i_steps(c1(), 1, true, true, 0);
    lemma_i_steps(c2(), 1, true, true, 0);
    lemma_i_steps(c3(), 1, true, true, 0);
    lemma_i_steps(c4(), 1, true, true, 0);
    assert(c4().funcs.contains(1));
}

} // verus!
