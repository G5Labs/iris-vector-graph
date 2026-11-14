//! The three participants in two levels, and what holds of any implementations of them.
//!
//! `Top<IL, IR, IS>`: implementations `IL`, `IR`, `IS` of the Ledger, Redactor and Store contracts; the ledger and
//! redactor implementations run in level 1's synchronized steps (`Sys<RLP, IL, IR>`, which refines `RL`), and that
//! machine and the store implementation run in level 2's (`Sys<SysP, _, IS>`, which refines `Biz`).
//! Proved for every such triple (generic in the implementations):
//! - `theorem_implementations_refine`: every step is a Biz step or a stutter (via `actors::protocol::theorem_compose`
//!   at both levels, `compose::Sys`);
//! - `theorem_implementations_safe`: every state of every execution satisfies Biz's invariants
//!   (`actors::hierarchy::refinement_preserves_safety`);
//! - `theorem_implementation_steps`: every visible step is a Biz step from a state that satisfies them, so each
//!   business step theorem of `biz` (no tombstone of live content, per-target audit counts, marker ownership)
//!   applies to it; `theorem_implementation_states`: statements match live edges and replay equals the store once
//!   settled, in every state;
//! - `theorem_levels`: any machine refining the composed participant contracts refines Biz
//!   (`actors::protocol::theorem_trans`).
use vstd::prelude::*;
use actors::protocol::*;
use actors::hierarchy::*;
use crate::vocab::*;
use crate::ledger::*;
use crate::store::*;
use crate::redactor::*;
use crate::protocol_rl::*;
use crate::biz::*;
use crate::protocol_sys::*;
use crate::compose::*;

verus! {

/// One step of the composed participant contracts, flattened onto the business view: the level-2 guard and store
/// step, and, when the level-2 protocol gives RL a label, the level-1 guard with the ledger and redactor steps. It is
/// the relation the broken-implementation controls change (`counterexamples`).
pub open spec fn sys_step(x: BizS, l: BizL, y: BizS) -> bool {
    &&& p2_guard(x.rl, x.st, l)
    &&& match p2_lab_rl(x.rl, x.st, l) {
            Some(m) => p1_guard(x.rl.l, x.rl.r, m) && side_l(x.rl.l, p1_lab_l(x.rl.l, x.rl.r, m), y.rl.l)
                && side_r(x.rl.r, p1_lab_r(x.rl.l, x.rl.r, m), y.rl.r),
            None => y.rl == x.rl,
        }
    &&& step_or_stutter::<Store>(x.st, p2_lab_st(x.rl, x.st, l), y.st)
    &&& y.pend == pend_after(x.rl, x.pend, l)
}

/// Both protocols' `step_binds` in one statement: every step of the composed participant contracts is a Biz step.
pub proof fn theorem_sys_step_refines(x: BizS, l: BizL, y: BizS)
    requires sys_step(x, l, y),
    ensures biz_next(x, l, y),
{
    match p2_lab_rl(x.rl, x.st, l) {
        Some(m) => {
            lemma_p1_binds(x.rl.l, x.rl.r, m, y.rl.l, y.rl.r);
            assert(RLS { l: x.rl.l, r: x.rl.r } == x.rl);
            assert(RLS { l: y.rl.l, r: y.rl.r } == y.rl);
        }
        None => {}
    }
    lemma_p2_binds(x.rl, x.st, Own2 { pend: x.pend }, l, y.rl, y.st, Own2 { pend: y.pend });
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

pub type Inner<IL, IR> = Sys<RLP, IL, IR>;

pub type Top<IL, IR, IS> = Sys<SysP, Sys<RLP, IL, IR>, IS>;

/// The participant contracts themselves, composed.
pub type Spec = Top<Id<Ledger>, Id<Redactor>, Id<Store>>;

/// **Composition.** Any implementations refining the three participant contracts, run in the two protocols'
/// synchronized steps, refine the outer business contract: every step is a Biz step or a stutter.
pub proof fn theorem_implementations_refine<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>>(
    s: <Top<IL, IR, IS> as Contract>::S, x: <Top<IL, IR, IS> as Contract>::L, u: <Top<IL, IR, IS> as Contract>::S)
    requires <Top<IL, IR, IS> as Contract>::next(s, x, u),
    ensures step_or_stutter::<Biz>(<Top<IL, IR, IS> as Refines<Biz>>::abs(s), <Top<IL, IR, IS> as Refines<Biz>>::lab(x),
        <Top<IL, IR, IS> as Refines<Biz>>::abs(u)),
{
    <Top<IL, IR, IS> as Refines<Biz>>::step_refines(s, x, u);
}

pub proof fn theorem_implementations_init<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>>(
    s: <Top<IL, IR, IS> as Contract>::S)
    requires <Top<IL, IR, IS> as Contract>::init(s),
    ensures Biz::init(<Top<IL, IR, IS> as Refines<Biz>>::abs(s)),
{
    <Top<IL, IR, IS> as Refines<Biz>>::init_refines(s);
}

/// **Safety.** Every state of every execution of the implementations satisfies the business invariants.
pub proof fn theorem_implementations_safe<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>>(
    states: Seq<<Top<IL, IR, IS> as Contract>::S>, labels: Seq<<Top<IL, IR, IS> as Contract>::L>)
    requires execution::<Top<IL, IR, IS>>(states, labels),
    ensures forall|i: int| 0 <= i < states.len() ==> biz_inv(#[trigger] <Top<IL, IR, IS> as Refines<Biz>>::abs(states[i])),
{
    refinement_preserves_safety::<Top<IL, IR, IS>, Biz>(states, labels);
}

/// Every visible step of an execution of the implementations is a Biz step from a state satisfying the invariants;
/// every other step leaves the business state unchanged.
pub proof fn theorem_implementation_steps<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>>(
    states: Seq<<Top<IL, IR, IS> as Contract>::S>, labels: Seq<<Top<IL, IR, IS> as Contract>::L>, i: int)
    requires execution::<Top<IL, IR, IS>>(states, labels), 0 <= i < labels.len(),
    ensures ({
        let x = <Top<IL, IR, IS> as Refines<Biz>>::abs(states[i]);
        let y = <Top<IL, IR, IS> as Refines<Biz>>::abs(states[i + 1]);
        &&& biz_inv(x) && biz_inv(y)
        &&& match <Top<IL, IR, IS> as Refines<Biz>>::lab(labels[i]) {
                Some(l) => biz_next(x, l, y),
                None => y == x,
            }
    }),
{
    theorem_implementations_safe::<IL, IR, IS>(states, labels);
    assert(<Top<IL, IR, IS> as Contract>::next(states[i], labels[i], states[i + 1]));
    theorem_implementations_refine::<IL, IR, IS>(states[i], labels[i], states[i + 1]);
}

/// In every state of every execution of the implementations: statement entries match live edges outside an open
/// erasure, and the replay equals the store once settled.
pub proof fn theorem_implementation_states<IL: Refines<Ledger>, IR: Refines<Redactor>, IS: Refines<Store>>(
    states: Seq<<Top<IL, IR, IS> as Contract>::S>, labels: Seq<<Top<IL, IR, IS> as Contract>::L>, i: int, k: Key)
    requires execution::<Top<IL, IR, IS>>(states, labels), 0 <= i < states.len(),
    ensures ({
        let x = <Top<IL, IR, IS> as Refines<Biz>>::abs(states[i]);
        &&& (k.edge && !in_erasing(x.st.erasing)(k) ==> (x.st.stmts.contains(k) <==> x.st.rows.contains_key(k)))
        &&& (settled(x) ==> replay(x.rl.l.hist) =~= x.st.rows)
    }),
{
    theorem_implementations_safe::<IL, IR, IS>(states, labels);
    let x = <Top<IL, IR, IS> as Refines<Biz>>::abs(states[i]);
    assert(biz_inv(x));
    if k.edge && !in_erasing(x.st.erasing)(k) { theorem_statements_match(x, k); }
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
