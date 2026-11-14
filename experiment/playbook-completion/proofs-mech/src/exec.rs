//! Executions of a mechanism's machine, proved once for every machine.
//!
//! Every mechanism `M-NN` defines one machine per instance type `O` (`<Mech>M<O>`, a `Machine` whose step is the
//! mechanism's generic step function evaluated with `O`'s parameters). `run` folds a finite list of actions from a
//! state; a state is *reached* when some run from an initial state ends in it. `lemma_reached_inv` lifts an
//! inductive predicate to every reached state (the shape of `actors::hierarchy::invariant_at`, stated on runs so
//! counterexamples can be written as one list of actions). Nothing here is mechanism-specific or trusted.
use vstd::prelude::*;

verus! {

pub trait Machine: Sized {
    type S;
    type A;
    spec fn init(s: Self::S) -> bool;
    spec fn step(s: Self::S, a: Self::A) -> Option<Self::S>;
}

/// The state after running `ls` from `s`, or `None` if some action is not enabled.
pub open spec fn run<M: Machine>(s: M::S, ls: Seq<M::A>) -> Option<M::S>
    decreases ls.len(),
{
    if ls.len() == 0 {
        Some(s)
    } else {
        match M::step(s, ls[0]) {
            Some(t) => run::<M>(t, ls.drop_first()),
            None => None,
        }
    }
}

/// `t` is reached from the initial state `s0` by the run `ls`.
pub open spec fn reached<M: Machine>(s0: M::S, ls: Seq<M::A>, t: M::S) -> bool {
    M::init(s0) && run::<M>(s0, ls) == Some(t)
}

/// `inv` holds initially and every enabled step keeps it.
pub open spec fn inductive<M: Machine>(inv: spec_fn(M::S) -> bool) -> bool {
    &&& forall|s: M::S| M::init(s) ==> #[trigger] inv(s)
    &&& forall|s: M::S, a: M::A| inv(s) && (#[trigger] M::step(s, a)) is Some ==> inv(M::step(s, a)->0)
}

pub proof fn lemma_run_inv<M: Machine>(inv: spec_fn(M::S) -> bool, s: M::S, ls: Seq<M::A>)
    requires
        inv(s),
        forall|x: M::S, a: M::A| inv(x) && (#[trigger] M::step(x, a)) is Some ==> inv(M::step(x, a)->0),
    ensures
        run::<M>(s, ls) is Some ==> inv(run::<M>(s, ls)->0),
    decreases ls.len(),
{
    if ls.len() > 0 {
        match M::step(s, ls[0]) {
            Some(t) => {
                lemma_run_inv::<M>(inv, t, ls.drop_first());
            },
            None => {},
        }
    }
}

/// Every reached state satisfies an inductive predicate.
pub proof fn lemma_reached_inv<M: Machine>(inv: spec_fn(M::S) -> bool, s0: M::S, ls: Seq<M::A>, t: M::S)
    requires
        inductive::<M>(inv),
        reached::<M>(s0, ls, t),
    ensures
        inv(t),
{
    lemma_run_inv::<M>(inv, s0, ls);
}

/// Running `a ++ b` is running `a`, then `b` (used to splice a counterexample's prefix and its violating step).
pub proof fn lemma_run_append<M: Machine>(s: M::S, a: Seq<M::A>, b: Seq<M::A>)
    ensures
        run::<M>(s, a + b) == match run::<M>(s, a) {
            Some(t) => run::<M>(t, b),
            None => None,
        },
    decreases a.len(),
{
    if a.len() > 0 {
        assert((a + b).drop_first() =~= a.drop_first() + b);
        assert((a + b)[0] == a[0]);
        match M::step(s, a[0]) {
            Some(t) => {
                lemma_run_append::<M>(t, a.drop_first(), b);
            },
            None => {},
        }
    } else {
        assert(a + b =~= b);
    }
}

} // verus!
