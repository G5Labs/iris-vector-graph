//! The planc L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::planc_l1::*;
use crate::planc_l2::*;

verus! {

pub open spec fn hm() -> Map<int, int> { Map::empty().insert(0int, 7int).insert(1int, 7int) }
pub open spec fn q0() -> PC2 {
    PC2 { db: 0, hash: hm(), ent: Map::empty(), src: Map::empty(), cls: Map::empty(), locks: Set::empty(),
          jobs: Map::empty(), rd: Map::empty(), next_cls: 0 }
}

pub proof fn lemma_p_steps(s: PC2, r: int, shape: int, j: int, restart: bool)
    ensures
        init2(q0()),
        !s.rd.contains_key(r) && !s.jobs.contains_key(j) ==> step2(s, PCL2::For { r, shape, j, restart }, for2(s, r, shape, j, restart)),
        s.rd.contains_key(r) && s.rd[r].left > 0 ==> step2(s, PCL2::Walk { r, shape: s.rd[r].s, a: answer(s, s.rd[r]) }, walk2(s, r)),
        started(s, j) && !can_build(s, j) ==> step2(s, PCL2::BLeave { j }, PC2 { jobs: s.jobs.remove(j), ..s }),
        can_build(s, j) && s.src[s.jobs[j].h] == s.jobs[j].dig ==> step2(s, PCL2::BCompile { j }, compile2(s, j)),
        s.jobs.contains_key(j) && s.jobs[j].ph is Compiled ==> step2(s, PCL2::BMark { j }, mark2(s, j)),
{
}

} // verus!
