//! Concrete states shared by the module 11 counterexamples (compiled only with a module 11 control).
use vstd::prelude::*;
use crate::ledger_l1::*;
use crate::ledger_l2::*;

verus! {

pub open spec fn c_init() -> LS2 {
    LS2 {
        meta: Meta { state: LState::Never, strict: false }, g: glob0(), stats: Stats { ok: 0, rej: 0 },
        rows: Map::empty(), txn: None, gcache: None, probe_fails: false, copies: Map::empty(), drift: Set::empty(),
    }
}

/// The genesis of an empty graph (revision 1, id 1, no records), strict as given.
pub open spec fn c_genesis(strict: bool) -> LS2 {
    LS2 {
        meta: Meta { state: LState::Enabled, strict },
        g: commit_glob(glob0(), genesis_args(seq![], 1)),
        stats: Stats { ok: 1, rej: 0 },
        drift: Set::empty(),
        ..c_init()
    }
}

pub proof fn lemma_genesis_step(strict: bool)
    ensures
        init2(c_init()),
        step2(c_init(), L2Label::Enable { strict, id: 1, recs: seq![], busy: false }, c_genesis(strict)),
        c_genesis(strict).g.head == 1,
{
    assert(apply_recs(Map::<K, V>::empty(), Seq::<Op>::empty()) == Map::<K, V>::empty());
}

} // verus!
