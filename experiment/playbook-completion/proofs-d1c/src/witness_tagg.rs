//! Non-vacuity of the reviewed bucket model (compiled without its control): an edge, its update (one edge, weight
//! replaced), a second edge, a skip at an occupied coordinate (nothing), an exact aggregate read, a delete and an exact
//! counter read.
use vstd::prelude::*;
use crate::tagg_l1::*;
use crate::tagg_l2::*;
use crate::tagg_runs::*;

verus! {

pub open spec fn w1() -> TS2 { p_write(t0(), 0, 1, Mode::Insert) }
pub open spec fn w2() -> TS2 { p_write(w1(), 0, 5, Mode::Update) }
pub open spec fn w3() -> TS2 { p_write(w2(), 1, 2, Mode::Insert) }
pub open spec fn w4() -> TS2 { p_write(w3(), 1, 9, Mode::Skip) }
pub open spec fn w5() -> TS2 { p_delete(w4(), 0) }

pub proof fn witness_tagg()
    ensures
        init2(t0()),
        step2(t0(), TL2::Write { ts: 0, w: 1, mode: Mode::Insert }, w1()),
        step2(w1(), TL2::Write { ts: 0, w: 5, mode: Mode::Update }, w2()),
        w2().count == 1 && w2().sum == 5 && w2().bucket == 1,
        step2(w2(), TL2::Write { ts: 1, w: 2, mode: Mode::Insert }, w3()),
        step2(w3(), TL2::Write { ts: 1, w: 9, mode: Mode::Skip }, w4()),
        w4() == w3(),
        step2(w4(), TL2::ReadAgg { count: 2, sum: 7 }, w4()),
        step2(w4(), TL2::Delete { ts: 0 }, w5()),
        step2(w5(), TL2::ReadBucket { n: 1 }, w5()),
        w5().count == 1 && w5().sum == 2,
{
    lemma_t_steps(t0(), 0, 1, Mode::Insert);
    lemma_t_steps(w1(), 0, 5, Mode::Update);
    lemma_t_steps(w2(), 1, 2, Mode::Insert);
    lemma_t_steps(w3(), 1, 9, Mode::Skip);
    lemma_t_steps(w4(), 0, 1, Mode::Insert);
    lemma_t_steps(w5(), 0, 1, Mode::Insert);
    lemma_cnt_empty(bw());
    assert(w4().tout.remove(0) =~= Map::<int, int>::empty().insert(1, 2));
    lemma_cnt_insert(Map::<int, int>::empty(), bw(), 1, 2);
}

} // verus!
