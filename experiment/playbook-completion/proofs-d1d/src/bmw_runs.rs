//! The bmw L2 machine's steps as functions (valid under every feature).
use vstd::prelude::*;
use crate::bmw_l1::*;
use crate::bmw_l2::*;

verus! {

pub open spec fn w0() -> BW2 {
    BW2 { cur: Img { docs: Map::empty(), counted: Set::empty(), hdr: false, rows: Set::empty() }, caller: None, b: None }
}
pub open spec fn p_cbegin(s: BW2) -> BW2 { BW2 { caller: Some(s.cur), ..s } }
pub open spec fn p_cwrite(s: BW2, r: int) -> BW2 { BW2 { cur: Img { rows: s.cur.rows.insert(r), ..s.cur }, ..s } }
pub open spec fn p_crollback(s: BW2) -> BW2 { BW2 { cur: s.caller->Some_0, caller: None, ..s } }
pub open spec fn p_ins(s: BW2, d: int, toks: Set<int>, fail: bool) -> BW2 {
    if fail { failed(s) } else { BW2 { cur: ins_body(s.cur, d, toks), ..s } }
}
pub open spec fn p_bstart(s: BW2, corpus: Map<int, Set<int>>) -> BW2 {
    BW2 { cur: if f0701() { killed(s.cur) } else { s.cur },
          b: Some(Bld { corpus, todo: corpus.dom(), loc: Set::empty(), shadow: Map::empty() }), ..s }
}
pub open spec fn p_bdoc(s: BW2, d: int) -> BW2 {
    BW2 { cur: if f0701() && ne(s.b->Some_0.corpus[d]) { Img { docs: s.cur.docs.insert(d, s.b->Some_0.corpus[d]), ..s.cur } } else { s.cur },
          b: Some(bdoc(s.b->Some_0, d)), ..s }
}
pub open spec fn p_bheader(s: BW2, refused: bool) -> BW2 {
    BW2 { cur: if f0701() { Img { counted: s.b->Some_0.loc, hdr: true, ..s.cur } }
               else if refused && !f0704() { s.cur } else { published(s, s.b->Some_0) },
          b: None, ..s }
}
pub open spec fn view2(s: BW2) -> Option<(Map<int, Set<int>>, Set<int>)> {
    if s.cur.hdr { Some((s.cur.docs, s.cur.counted)) } else { None }
}

pub proof fn lemma_w_steps(s: BW2, r: int, d: int, toks: Set<int>, fail: bool, corpus: Map<int, Set<int>>, refused: bool)
    ensures
        init2(w0()),
        s.caller is None && s.b is None ==> step2(s, BWL2::CBegin, p_cbegin(s)),
        s.caller is Some ==> step2(s, BWL2::CWrite { r }, p_cwrite(s, r)),
        s.caller is Some ==> step2(s, BWL2::CRollback, p_crollback(s)),
        free(s) ==> step2(s, BWL2::Ins { d, toks, fail }, p_ins(s, d, toks, fail)),
        s.b is None && s.caller is None ==> step2(s, BWL2::BStart { corpus }, p_bstart(s, corpus)),
        s.b is Some && s.b->Some_0.todo.contains(d) ==> step2(s, BWL2::BDoc { d }, p_bdoc(s, d)),
        s.b is Some && s.b->Some_0.todo == Set::<int>::empty() && (refused ==> s.b->Some_0.loc == Set::<int>::empty())
            ==> step2(s, BWL2::BHeader { corpus: s.b->Some_0.corpus, refused }, p_bheader(s, refused)),
        step2(s, BWL2::Search { ans: view2(s) }, s),
{
}

} // verus!
