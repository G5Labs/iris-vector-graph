//! The four participants in three levels, and what holds of any implementations of them.
//!
//! `Top<IL, IR, IS, IW>`: implementations of the Ledger, Redactor, Store and Writer contracts; level 1 composes the
//! ledger and redactor implementations (`Sys<RLP, IL, IR>` refines `RL`), level 2 composes that and the store
//! (`Sys<SysP, _, IS>` refines `Mid`), level 3 composes that and the writers (`Sys<TopP, _, IW>` refines `Biz`).
//! Proved generically (for every such quadruple): every step refines Biz, every state satisfies Biz's invariants,
//! every visible step is a Biz step between invariant states, and any machine refining the composed participant
//! contracts refines Biz.
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::writer::*;
use crate::protocol_rl::*;
use crate::mid::*;
use crate::protocol_sys::*;
use crate::biz::*;
use crate::safety::*;
use crate::theorems::*;
use crate::protocol_top::*;
use crate::compose::*;

verus! {

/// One step of the composed participant contracts, flattened onto the business view: the level-3 guard and writer
/// step, and when level 3 gives Mid a label, the level-2 guard, store step and pend, and when level 2 gives RL a
/// label, the level-1 guard with the ledger and redactor steps. The controls change this relation (`cx_*`).
pub open spec fn sys_step(x: BizS, l: BizL, y: BizS) -> bool {
    &&& p3_guard(mid_of(x), x.wr, l)
    &&& step_or_stutter::<Writer>(x.wr, p3_lab_w(mid_of(x), x.wr, l), y.wr)
    &&& match p3_lab_m(mid_of(x), x.wr, l) {
            Some(m) => {
                &&& p2_guard(x.rl, x.st, m)
                &&& match p2_lab_rl(x.rl, x.st, m) {
                        Some(a) => p1_guard(x.rl.l, x.rl.r, a) && side_l(x.rl.l, p1_lab_l(x.rl.l, x.rl.r, a), y.rl.l)
                            && side_r(x.rl.r, p1_lab_r(x.rl.l, x.rl.r, a), y.rl.r),
                        None => y.rl == x.rl,
                    }
                &&& step_or_stutter::<Store>(x.st, p2_lab_st(x.rl, x.st, m), y.st)
                &&& y.pend == pend_after(x.rl, x.st, x.pend, m)
            }
            None => mid_of(y) == mid_of(x),
        }
}

/// All three protocols' `step_binds` at once: every step of the composed participant contracts is a Biz step.
pub proof fn theorem_sys_step_refines(x: BizS, l: BizL, y: BizS)
    requires sys_step(x, l, y),
    ensures biz_next(x, l, y),
{
    match p3_lab_m(mid_of(x), x.wr, l) {
        Some(m) => {
            match p2_lab_rl(x.rl, x.st, m) {
                Some(a) => {
                    lemma_p1_binds(x.rl.l, x.rl.r, a, y.rl.l, y.rl.r);
                    assert(RLS { l: x.rl.l, r: x.rl.r } == x.rl);
                    assert(RLS { l: y.rl.l, r: y.rl.r } == y.rl);
                }
                None => {}
            }
            lemma_p2_binds(x.rl, x.st, Own2 { pend: x.pend }, m, y.rl, y.st, Own2 { pend: y.pend });
        }
        None => {}
    }
    lemma_p3_binds(mid_of(x), x.wr, l, mid_of(y), y.wr);
    assert(top_abs(mid_of(x), x.wr) == x);
    assert(top_abs(mid_of(y), y.wr) == y);
}

pub open spec fn sys_run(xs: Seq<BizS>, ls: Seq<BizL>) -> bool {
    &&& xs.len() == ls.len() + 1
    &&& Biz::init(xs[0])
    &&& forall|i: int| 0 <= i < ls.len() ==> #[trigger] sys_step(xs[i], ls[i], xs[i + 1])
}

/// Every state reached by the composed participant contracts satisfies the business invariants.
pub proof fn theorem_sys_safe(xs: Seq<BizS>, ls: Seq<BizL>, k: int)
    requires sys_run(xs, ls), 0 <= k < xs.len(),
    ensures biz_inv(xs[k]),
    decreases k,
{
    if k == 0 {
        <Biz as SafeContract>::init_safe(xs[0]);
    } else {
        let j = k - 1;
        theorem_sys_safe(xs, ls, j);
        assert(sys_step(xs[j], ls[j], xs[j + 1]));
        theorem_sys_step_refines(xs[j], ls[j], xs[j + 1]);
        lemma_biz_safe(xs[j], ls[j], xs[j + 1]);
    }
}

pub type Top<IL, IR, IS, IW> = Sys<TopP, Sys<SysP, Sys<RLP, IL, IR>, IS>, IW>;

/// The participant contracts themselves, composed.
pub type Spec = Top<Id<Ledger>, Id<Redactor>, Id<Store>, Id<Writer>>;

/// **Composition.** Any implementations refining the four participant contracts, run in the three protocols'
/// synchronized steps, refine the outer business contract.
pub proof fn theorem_implementations_refine<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>, IW: Refines<Writer>>(
    s: <Top<IL, IR, IS, IW> as Contract>::S, x: <Top<IL, IR, IS, IW> as Contract>::L, u: <Top<IL, IR, IS, IW> as Contract>::S)
    requires <Top<IL, IR, IS, IW> as Contract>::next(s, x, u),
    ensures step_or_stutter::<Biz>(<Top<IL, IR, IS, IW> as Refines<Biz>>::abs(s), <Top<IL, IR, IS, IW> as Refines<Biz>>::lab(x),
        <Top<IL, IR, IS, IW> as Refines<Biz>>::abs(u)),
{
    <Top<IL, IR, IS, IW> as Refines<Biz>>::step_refines(s, x, u);
}

pub proof fn theorem_implementations_init<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>, IW: Refines<Writer>>(
    s: <Top<IL, IR, IS, IW> as Contract>::S)
    requires <Top<IL, IR, IS, IW> as Contract>::init(s),
    ensures Biz::init(<Top<IL, IR, IS, IW> as Refines<Biz>>::abs(s)),
{
    <Top<IL, IR, IS, IW> as Refines<Biz>>::init_refines(s);
}

/// **Safety.** Every state of every execution of the implementations satisfies the business invariants.
pub proof fn theorem_implementations_safe<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>, IW: Refines<Writer>>(
    states: Seq<<Top<IL, IR, IS, IW> as Contract>::S>, labels: Seq<<Top<IL, IR, IS, IW> as Contract>::L>)
    requires execution::<Top<IL, IR, IS, IW>>(states, labels),
    ensures forall|i: int| 0 <= i < states.len() ==> biz_inv(#[trigger] <Top<IL, IR, IS, IW> as Refines<Biz>>::abs(states[i])),
{
    refinement_preserves_safety::<Top<IL, IR, IS, IW>, Biz>(states, labels);
}

/// Every visible step of an execution of the implementations is a Biz step between invariant states (so each step
/// theorem of `theorems` applies to it); every other step leaves the business state unchanged.
pub proof fn theorem_implementation_steps<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>, IW: Refines<Writer>>(
    states: Seq<<Top<IL, IR, IS, IW> as Contract>::S>, labels: Seq<<Top<IL, IR, IS, IW> as Contract>::L>, i: int)
    requires execution::<Top<IL, IR, IS, IW>>(states, labels), 0 <= i < labels.len(),
    ensures ({
        let x = <Top<IL, IR, IS, IW> as Refines<Biz>>::abs(states[i]);
        let y = <Top<IL, IR, IS, IW> as Refines<Biz>>::abs(states[i + 1]);
        &&& biz_inv(x) && biz_inv(y)
        &&& match <Top<IL, IR, IS, IW> as Refines<Biz>>::lab(labels[i]) {
                Some(l) => biz_next(x, l, y),
                None => y == x,
            }
    }),
{
    theorem_implementations_safe::<IL, IR, IS, IW>(states, labels);
    assert(<Top<IL, IR, IS, IW> as Contract>::next(states[i], labels[i], states[i + 1]));
    theorem_implementations_refine::<IL, IR, IS, IW>(states[i], labels[i], states[i + 1]);
}

/// In every state of every execution of the implementations: statement entries match live edges (outside the open
/// erasure, at keys last written through the ledger), and replay equals the store once settled (at such keys).
pub proof fn theorem_implementation_states<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>, IW: Refines<Writer>>(
    states: Seq<<Top<IL, IR, IS, IW> as Contract>::S>, labels: Seq<<Top<IL, IR, IS, IW> as Contract>::L>, i: int, k: Key)
    requires execution::<Top<IL, IR, IS, IW>>(states, labels), 0 <= i < states.len(),
    ensures ({
        let x = <Top<IL, IR, IS, IW> as Refines<Biz>>::abs(states[i]);
        &&& (k.edge && !in_erasing(x.st.erasing)(k) && !x.st.unrec.contains(k) ==> (x.st.stmts.contains(k) <==> x.st.rows.contains_key(k)))
        &&& (settled(x) && !x.st.unrec.contains(k) ==> oget(replay(x.rl.l.hist), k) == oget(x.st.rows, k))
    }),
{
    theorem_implementations_safe::<IL, IR, IS, IW>(states, labels);
    let x = <Top<IL, IR, IS, IW> as Refines<Biz>>::abs(states[i]);
    assert(biz_inv(x));
    if k.edge && !in_erasing(x.st.erasing)(k) && !x.st.unrec.contains(k) { theorem_statements_match(x, k); }
    if settled(x) { theorem_replay_settled(x); }
}

/// **Levels.** Any machine that refines the composed participant contracts refines Biz (`theorem_trans`).
pub proof fn theorem_levels<M: Refines<Spec>>(s: M::S, l: M::L, t: M::S)
    requires M::next(s, l, t),
    ensures step_or_stutter::<Biz>(<Spec as Refines<Biz>>::abs(M::abs(s)), lab2::<M, Spec, Biz>(l),
        <Spec as Refines<Biz>>::abs(M::abs(t))),
{
    theorem_trans::<M, Spec, Biz>(s, l, t);
}

pub proof fn theorem_levels_init<M: Refines<Spec>>(s: M::S)
    requires M::init(s),
    ensures Biz::init(<Spec as Refines<Biz>>::abs(M::abs(s))),
{
    theorem_trans_init::<M, Spec, Biz>(s);
}

} // verus!
