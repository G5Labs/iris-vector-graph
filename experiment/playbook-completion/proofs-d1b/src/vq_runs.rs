//! Module 06 queue: concrete steps of node 5's entry used by the witness and the counterexamples (valid under every
//! feature).
use vstd::prelude::*;
use crate::vq_l1::*;
use crate::vq_l2::*;

verus! {

pub open spec fn n5() -> int { 5 }
pub open spec fn q0() -> QS2 { QS2 { text: Map::empty(), st: Map::empty(), rows: Map::empty(), wk: Map::empty(), lock: None } }
pub open spec fn enq(s: QS2) -> QS2 { QS2 { text: s.text.insert(n5(), next_ver(s.text, n5())), st: s.st.insert(n5(), St::Pending), ..s } }
pub open spec fn claim(s: QS2, w: nat) -> QS2 {
    QS2 { wk: s.wk.insert(w, WK { node: n5(), ver: s.text[n5()], ok: false, ph: WPh::Claimed }),
          lock: if hd0604() { s.lock } else { Some(w) }, ..s }
}
pub open spec fn embed(s: QS2, w: nat, ok: bool) -> QS2 { QS2 { wk: s.wk.insert(w, WK { ok, ph: WPh::Embedded, ..s.wk[w] }), ..s } }
pub open spec fn write(s: QS2, w: nat) -> QS2 {
    QS2 { rows: if s.wk[w].ok { s.rows.insert(n5(), s.wk[w].ver) } else { s.rows },
          wk: s.wk.insert(w, WK { ph: WPh::Written, ..s.wk[w] }), ..s }
}
pub open spec fn mark(s: QS2, w: nat) -> QS2 {
    QS2 { st: match mark_out(s, w) { Some(d) => s.st.insert(n5(), if d { St::Done } else { St::Error }), None => s.st },
          wk: s.wk.remove(w), lock: if s.lock == Some(w) { None } else { s.lock }, ..s }
}
pub open spec fn wrote(s: QS2, w: nat) -> Option<nat> { if s.wk[w].ok { Some(s.wk[w].ver) } else { None } }

pub proof fn lemma_q_steps(s: QS2, w: nat, ok: bool)
    ensures
        step2(s, QL2::Enqueue { node: n5() }, enq(s)),
        !s.wk.contains_key(w) && s.st.contains_key(n5()) && s.st[n5()] is Pending && s.text.contains_key(n5())
            && (hd0604() || s.lock is None) ==> step2(s, QL2::Claim { w, node: n5() }, claim(s, w)),
        s.wk.contains_key(w) && s.wk[w].ph is Claimed ==> step2(s, QL2::Embed { w, ok }, embed(s, w, ok)),
        s.wk.contains_key(w) && s.wk[w].ph is Embedded && s.wk[w].node == n5()
            ==> step2(s, QL2::Write { w, node: n5(), wrote: wrote(s, w) }, write(s, w)),
        s.wk.contains_key(w) && s.wk[w].ph is Written && s.wk[w].node == n5()
            ==> step2(s, QL2::Mark { w, node: n5(), out: mark_out(s, w) }, mark(s, w)),
{
}

} // verus!
