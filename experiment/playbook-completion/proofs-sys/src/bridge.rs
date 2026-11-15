//! The bridge to the per-mechanism proofs (crate proofs-mech): for each composed choice that has an exact mechanism
//! instance in proofs-mech, the design's mechanism component is that instance (a type generic in the design), the
//! design's system obligation is proved EQUAL to the component's mechanism obligation(s) (using proofs-mech's own
//! discharge, keep, refute and rule lemmas), and proofs-mech's generic theorems are instantiated at the component.
//!
//! What this reuses and what it does not: the module-00 axioms are proved on the composed machine (src/axioms.rs,
//! src/progress.rs); the semantics lane's composed machine (sys00) abstracts each mechanism differently from its own
//! machine (one global reply, applies as single steps, a parked redaction that resumes), so no refinement from sys00
//! to the mechanism machines is claimed. The bridge shows, for M-02, M-03, M-04, M-05 and M-10, that the composition
//! keeps an axiom exactly when the mechanism instance it plugs in keeps the corresponding mechanism law, and that the
//! mechanism law then holds for that instance by proofs-mech's generic theorem (proved once over its trait).
use vstd::prelude::*;
use ivg_proofs_mech::exec::*;
use ivg_proofs_mech::m02_retry as m02;
use ivg_proofs_mech::i02_retry as i02;
use ivg_proofs_mech::m03_excl as m03;
use ivg_proofs_mech::i03_excl as i03;
use ivg_proofs_mech::m04_derived as m04;
use ivg_proofs_mech::i04_derived as i04;
use ivg_proofs_mech::m05_removal as m05;
use ivg_proofs_mech::i05_removal as i05;
use ivg_proofs_mech::m10_unit as m10;
use ivg_proofs_mech::i10_unit as i10;
use crate::sys::*;

verus! {

// ------------------------------------------------------------------------------------------------ M-02 retry binding

/// W's retry key: the ledger's binding (atomic with the commit, application retries) with the design's post-commit
/// policy and redaction policy. (InCommit, move) is proofs-mech's LedgerKeyReviewed; (SeparateAlways, move) its
/// LedgerKeyAsBuilt (F-1101, F-1306); (InCommit, no move) its ZeroRecordRevisionAsBuilt (F-CS01).
pub struct RetryOf<O> { pub o: O }
impl<O: SysDesign> m02::RetryPolicy for RetryOf<O> {
    open spec fn cfg() -> m02::RetryCfg {
        m02::RetryCfg {
            post: if O::cfg().m02_post is InCommit { m02::Post::SkipOnReplay } else { m02::Post::Always },
            redact: if O::cfg().m05_move_binding { m02::Redact::Moves } else { m02::Redact::Keeps },
            ..i02::ledger_rv()
        }
    }
}

/// AX-06's obligation is exactly M02-L1 and M02-L2's for W's retry key; the redaction's move is exactly M02-L4's.
pub proof fn bridge_m02<O: SysDesign>()
    ensures
        obl_ax06::<O>() == (m02::obl_l1::<RetryOf<O>>() && m02::obl_l2::<RetryOf<O>>()),
        O::cfg().m05_move_binding == m02::obl_l4::<RetryOf<O>>(),
{
}

/// proofs-mech's generic M-02 theorems for the composition's retry key, under the composition's obligations.
pub proof fn component_m02<O: SysDesign>(s0: m02::RS, ls: Seq<m02::RA>, t: m02::RS)
    requires reached::<m02::RetryM<RetryOf<O>>>(s0, ls, t),
    ensures
        obl_ax06::<O>() ==> m02::law_l1(t),
        O::cfg().m05_move_binding ==> m02::law_l4(t),
{
    bridge_m02::<O>();
    if obl_ax06::<O>() { m02::theorem_l1::<RetryOf<O>>(s0, ls, t); }
    if O::cfg().m05_move_binding { m02::theorem_l4::<RetryOf<O>>(s0, ls, t); }
}

// ------------------------------------------------------------------------------------------------ M-03 lock and marker

pub open spec fn redact_never_cleared(t: nat) -> Seq<m03::Step> {
    seq![m03::Step::LockX, m03::Step::CheckNoMarkerAny, m03::Step::CheckNotLive(t), m03::Step::SetMarker(t), m03::Step::Tomb(t),
         m03::Step::Unlock, m03::Step::LockX, m03::Step::CheckNotLive(t), m03::Step::Unlock]
}
pub open spec fn progs_never_cleared() -> Seq<Seq<m03::Step>> {
    seq![redact_never_cleared(0), redact_never_cleared(1),
         seq![m03::Step::LockX, m03::Step::CheckNoMarker(0), m03::Step::MakeLive(0), m03::Step::Unlock]]
}

/// The redaction's exclusive section as an M-03 instance: proofs-mech's reviewed redaction-marker programs, its
/// as-built ones (F-1302, F-1303), its check-before-lock mutant, or the reviewed programs without the final clear.
pub struct ExclOf<O> { pub o: O }
impl<O: SysDesign> m03::ExclPolicy for ExclOf<O> {
    open spec fn progs() -> Seq<Seq<m03::Step>> {
        match O::cfg().m03_redact {
            M03Redact::Reviewed => i03::progs_redaction_marker_reviewed(),
            M03Redact::AsBuilt => i03::progs_redaction_marker(),
            M03Redact::CheckBeforeLock => i03::progs_ctl_check_before_lock(),
            M03Redact::NeverCleared => progs_never_cleared(),
        }
    }
    open spec fn init_live() -> Seq<bool> { seq![false, false] }
}

/// The erasure as an M-03 instance: proofs-mech's eraser-no-head-lock reviewed or as-built programs (F-1201).
pub struct EraserOf<O> { pub o: O }
impl<O: SysDesign> m03::ExclPolicy for EraserOf<O> {
    open spec fn progs() -> Seq<Seq<m03::Step>> {
        if O::cfg().m03_erase_locked { i03::progs_eraser_no_head_lock_reviewed() } else { i03::progs_eraser_no_head_lock() }
    }
    open spec fn init_live() -> Seq<bool> { seq![true, false] }
}

/// AX-11's obligation (both parts) is exactly M03-L3 and M03-L5's for the redaction's section; the eraser's head lock
/// is exactly M03-L2's for the erasure (no module-00 axiom check of sys00 covers M03-L2: see PROOFS.md).
pub proof fn bridge_m03<O: SysDesign>()
    ensures
        obl_ax11::<O>() == (m03::obl_l3::<ExclOf<O>>() && m03::obl_l5::<ExclOf<O>>()),
        O::cfg().m03_erase_locked == m03::obl_l2::<EraserOf<O>>(),
{
    i03::rules_redaction_marker_reviewed();
    i03::rules_redaction_marker();
    i03::rules_ctl_check_before_lock();
    i03::rules_eraser_no_head_lock_reviewed();
    i03::rules_eraser_no_head_lock();
    assert(m03::holds_all(m03::Rule::MarkerSet, progs_never_cleared())) by (compute);
    assert(m03::holds_all(m03::Rule::MakeLiveChecked, progs_never_cleared())) by (compute);
    assert(m03::holds_all(m03::Rule::Discipline, progs_never_cleared())) by (compute);
    assert(m03::holds_all(m03::Rule::TombChecked, progs_never_cleared())) by (compute);
    assert(m03::holds_all(m03::Rule::MakeLiveInX, progs_never_cleared())) by (compute);
}

pub proof fn component_m03<O: SysDesign>(s0: m03::XS, ls: Seq<nat>, t: m03::XS, e0: m03::XS, els: Seq<nat>, e: m03::XS)
    requires reached::<m03::ExclM<ExclOf<O>>>(s0, ls, t), reached::<m03::ExclM<EraserOf<O>>>(e0, els, e),
    ensures
        obl_ax11::<O>() ==> m03::law_l3(t),
        forall|q: nat| obl_ax11::<O>() && #[trigger] m03::x_step::<ExclOf<O>>(t, q) is Some ==> m03::law_l5::<ExclOf<O>>(t, q),
        forall|q: nat| O::cfg().m03_erase_locked && #[trigger] m03::x_step::<EraserOf<O>>(e, q) is Some ==> m03::law_l2::<EraserOf<O>>(e, q),
{
    bridge_m03::<O>();
    if obl_ax11::<O>() {
        m03::theorem_l3::<ExclOf<O>>(s0, ls, t);
        assert forall|q: nat| #[trigger] m03::x_step::<ExclOf<O>>(t, q) is Some implies m03::law_l5::<ExclOf<O>>(t, q) by {
            m03::theorem_l5::<ExclOf<O>>(s0, ls, t, q);
        }
    }
    if O::cfg().m03_erase_locked {
        assert forall|q: nat| #[trigger] m03::x_step::<EraserOf<O>>(e, q) is Some implies m03::law_l2::<EraserOf<O>>(e, q) by {
            m03::theorem_l2::<EraserOf<O>>(e0, els, e, q);
        }
    }
}

// ------------------------------------------------------------------------------------------------ M-04 derived store

/// The derived store as an M-04 instance: a functional entry every write path maintains (proofs-mech's
/// AdjacencyFunctional) or, when erasure skips it, the ivf-erase variant (F-0606 family).
pub struct DerivedOf<O> { pub o: O }
impl<O: SysDesign> m04::DerivedPolicy for DerivedOf<O> {
    open spec fn cfg() -> m04::DCfg {
        if erase_maintains(O::cfg()) { <i04::AdjacencyFunctional as m04::DerivedPolicy>::cfg() }
        else { <i04::IvfEraseF0606 as m04::DerivedPolicy>::cfg() }
    }
}

/// Erasure maintains the derived store exactly when the derived store's instance keeps M04-L1 and M04-L2.
pub proof fn bridge_m04<O: SysDesign>()
    ensures erase_maintains(O::cfg()) == (m04::obl_l1::<DerivedOf<O>>() && m04::obl_l2::<DerivedOf<O>>()),
{
    <i04::AdjacencyFunctional as m04::DerivedObject>::discharge_l1();
    <i04::AdjacencyFunctional as m04::DerivedObject>::discharge_l2();
    i04::refute_ivf_erase_f0606_l1();
}

pub proof fn component_m04<O: SysDesign>(s0: m04::DS, ls: Seq<m04::DA>, t: m04::DS)
    requires reached::<m04::DerivedM<DerivedOf<O>>>(s0, ls, t),
    ensures erase_maintains(O::cfg()) ==> m04::law_l1(t),
{
    bridge_m04::<O>();
    if erase_maintains(O::cfg()) { m04::theorem_l1::<DerivedOf<O>>(s0, ls, t); }
}

// ------------------------------------------------------------------------------------------------ M-05 removal

/// The redaction's reach as an M-05 instance: the graph-content inventory (proofs-mech's RowsAdjacencyTemporal) or,
/// when it tombstones every tenant, its cross-target mutant.
pub struct RemovalOf<O> { pub o: O }
impl<O: SysDesign> m05::RemovalPolicy for RemovalOf<O> {
    open spec fn cfg() -> m05::RmCfg {
        if O::cfg().m05_tomb is Any { <i05::CtlCrossTarget as m05::RemovalPolicy>::cfg() }
        else { <i05::RowsAdjacencyTemporal as m05::RemovalPolicy>::cfg() }
    }
}

/// AX-02's obligation is exactly M05-L2's for the redaction's reach.
pub proof fn bridge_m05<O: SysDesign>()
    ensures obl_ax02::<O>() == m05::obl_l2::<RemovalOf<O>>(),
{
    <i05::RowsAdjacencyTemporal as m05::RemovalObject>::discharge_l2();
    i05::refute_ctl_cross_target_l2();
    let c = <RemovalOf<O> as m05::RemovalPolicy>::cfg();
    if O::cfg().m05_tomb is Any {
        // the cross-target store (temporal, store 2) is reached by the second write path
        assert(c.paths[1].contains(2nat) && c.cross.contains(2nat));
    } else {
        assert forall|p: int, x: nat| 0 <= p < c.paths.len() && #[trigger] c.paths[p].contains(x) implies !c.cross.contains(x) by {}
    }
}

pub proof fn component_m05<O: SysDesign>(s0: m05::RmS, ls: Seq<m05::RmA>, t: m05::RmS, a: m05::RmA)
    requires reached::<m05::RemovalM<RemovalOf<O>>>(s0, ls, t), m05::removal_step::<RemovalOf<O>>(t, a) is Some,
    ensures obl_ax02::<O>() ==> m05::law_l2(t, a, m05::removal_step::<RemovalOf<O>>(t, a)->0),
{
    bridge_m05::<O>();
    if obl_ax02::<O>() { m05::theorem_l2::<RemovalOf<O>>(s0, ls, t, a); }
}

// ------------------------------------------------------------------------------------------------ M-10 unit of work

/// The erasure as an M-10 unit: one transaction (proofs-mech's canonical unit) or per-statement commits (its
/// per-statement-commit variant) when it is split into two stoppable steps.
pub struct UnitOf<O> { pub o: O }
impl<O: SysDesign> m10::UnitPolicy for UnitOf<O> {
    open spec fn cfg() -> m10::UnitCfg {
        if O::cfg().m10_erase_split { <i10::PerStatementCommitAsBuilt as m10::UnitPolicy>::cfg() }
        else { <i10::Canonical as m10::UnitPolicy>::cfg() }
    }
}

/// AX-04's obligation is exactly M10-L1's for the erasure as a unit.
pub proof fn bridge_m10<O: SysDesign>()
    ensures obl_ax04::<O>() == m10::obl_l1::<UnitOf<O>>(),
{
    <i10::Canonical as m10::UnitObject>::discharge_l1();
    i10::refute_per_statement_commit_l1();
}

pub proof fn component_m10<O: SysDesign>(s0: m10::US, ls: Seq<m10::UA>, t: m10::US)
    requires reached::<m10::UnitM<UnitOf<O>>>(s0, ls, t),
    ensures obl_ax04::<O>() ==> m10::law_l1(t),
{
    bridge_m10::<O>();
    if obl_ax04::<O>() { m10::theorem_l1::<UnitOf<O>>(s0, ls, t); }
}

} // verus!
