//! Generic composition: implementations of the participants, run in a protocol's synchronized steps, form a machine
//! (`Sys`) that refines the protocol's outer contract. Proved once for every `Protocol2` with an initial condition,
//! from `actors::protocol::theorem_compose` (both participants move), `theorem_compose_stutter_b` (only the first
//! moves) and `step_binds` (only the second moves, or neither), plus hidden implementation steps that the
//! implementation's own refinement maps to a stutter. Because `Sys<P, IA, IB>` refines `P::Outer`, it can be the
//! implementation of a participant of a next protocol: that is how the three participants compose in two levels
//! (`system::Top`).
use vstd::prelude::*;
use actors::protocol::*;

verus! {

/// A protocol whose owned state has an initial condition, and whose initial participant states represent an
/// initial outer state.
pub trait ProtocolInit: Protocol2 {
    spec fn own_init(o: Self::Own) -> bool;

    proof fn init_binds(a: <Self::A as Contract>::S, b: <Self::B as Contract>::S, o: Self::Own)
        requires <Self::A as Contract>::init(a), <Self::B as Contract>::init(b), Self::own_init(o),
        ensures <Self::Outer as Contract>::init(Self::abs(a, b, o));
}

pub struct SysS<SA, SB, O> { pub a: SA, pub b: SB, pub o: O }

pub enum SysL<L, LA, LB> {
    /// One protocol step on outer label `l`; each implementation takes a step (`Some`) whose label maps to the
    /// protocol's label for its participant, or does not move (`None`, the protocol gives it no label).
    Sync { l: L, la: Option<LA>, lb: Option<LB> },
    /// An internal step of the first implementation (its refinement maps it to a stutter).
    HiddenA { la: LA },
    /// An internal step of the second implementation.
    HiddenB { lb: LB },
}

pub struct Sys<P, IA, IB> { pub _m: std::marker::PhantomData<(P, IA, IB)> }

pub open spec fn sync_side<C: Contract, I: Refines<C>>(s: I::S, y: Option<I::L>, u: I::S, want: Option<C::L>) -> bool {
    match y {
        Some(x) => I::next(s, x, u) && I::lab(x) == want,
        None => u == s && want is None,
    }
}

impl<P: ProtocolInit, IA: Refines<P::A>, IB: Refines<P::B>> Contract for Sys<P, IA, IB> {
    type S = SysS<IA::S, IB::S, P::Own>;
    type L = SysL<<P::Outer as Contract>::L, IA::L, IB::L>;

    open spec fn init(s: Self::S) -> bool {
        IA::init(s.a) && IB::init(s.b) && P::own_init(s.o)
    }

    open spec fn next(s: Self::S, x: Self::L, u: Self::S) -> bool {
        match x {
            SysL::Sync { l, la, lb } => {
                let va = IA::abs(s.a);
                let vb = IB::abs(s.b);
                &&& P::guard(va, vb, s.o, l)
                &&& sync_side::<P::A, IA>(s.a, la, u.a, P::lab_a(va, vb, s.o, l))
                &&& sync_side::<P::B, IB>(s.b, lb, u.b, P::lab_b(va, vb, s.o, l))
                &&& P::own_next(va, vb, s.o, l, u.o)
            }
            SysL::HiddenA { la } => IA::next(s.a, la, u.a) && IA::lab(la) is None && u.b == s.b && u.o == s.o,
            SysL::HiddenB { lb } => IB::next(s.b, lb, u.b) && IB::lab(lb) is None && u.a == s.a && u.o == s.o,
        }
    }
}

impl<P: ProtocolInit, IA: Refines<P::A>, IB: Refines<P::B>> Refines<P::Outer> for Sys<P, IA, IB> {
    open spec fn abs(s: Self::S) -> <P::Outer as Contract>::S {
        P::abs(IA::abs(s.a), IB::abs(s.b), s.o)
    }

    open spec fn lab(x: Self::L) -> Option<<P::Outer as Contract>::L> {
        match x {
            SysL::Sync { l, la, lb } => Some(l),
            _ => None,
        }
    }

    proof fn init_refines(s: Self::S) {
        IA::init_refines(s.a);
        IB::init_refines(s.b);
        P::init_binds(IA::abs(s.a), IB::abs(s.b), s.o);
    }

    proof fn step_refines(s: Self::S, x: Self::L, u: Self::S) {
        match x {
            SysL::Sync { l, la, lb } => {
                let va = IA::abs(s.a);
                let vb = IB::abs(s.b);
                match la {
                    Some(ya) => {
                        match lb {
                            Some(yb) => {
                                theorem_compose::<P, IA, IB>(s.a, s.b, s.o, l, ya, yb, u.a, u.b, u.o);
                            }
                            None => {
                                theorem_compose_stutter_b::<P, IA>(s.a, vb, s.o, l, ya, u.a, u.o);
                            }
                        }
                    }
                    None => {
                        match lb {
                            Some(yb) => {
                                IB::step_refines(s.b, yb, u.b);
                                P::step_binds(va, vb, s.o, l, va, IB::abs(u.b), u.o);
                            }
                            None => {
                                P::step_binds(va, vb, s.o, l, va, vb, u.o);
                            }
                        }
                    }
                }
            }
            SysL::HiddenA { la } => { IA::step_refines(s.a, la, u.a); }
            SysL::HiddenB { lb } => { IB::step_refines(s.b, lb, u.b); }
        }
    }
}

/// A contract as its own implementation.
pub struct Id<C> { pub _m: std::marker::PhantomData<C> }

impl<C: Contract> Contract for Id<C> {
    type S = C::S;
    type L = C::L;
    open spec fn init(s: C::S) -> bool { C::init(s) }
    open spec fn next(s: C::S, l: C::L, t: C::S) -> bool { C::next(s, l, t) }
}

impl<C: Contract> Refines<C> for Id<C> {
    open spec fn abs(s: C::S) -> C::S { s }
    open spec fn lab(l: C::L) -> Option<C::L> { Some(l) }
    proof fn init_refines(s: C::S) {}
    proof fn step_refines(s: C::S, l: C::L, t: C::S) {}
}

} // verus!
