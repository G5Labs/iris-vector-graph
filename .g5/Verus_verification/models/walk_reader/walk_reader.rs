// product 3eaa79cf: the readers of a breadth-first walk (algorithms.op.khop, algorithms.op.walks).
//   BFSFast (iris_src/src/Graph/KG/TraversalBFS.cls) records every edge it walks, hop by hop, as (s, p, o, step).
//   khop reads that list whole (BFSFastJson through host.call_large, which falls back to BFSFastStream on <MAXSTRING>).
//   kg_GRAPH_WALK stages it with BFSFastJsonSorted in ^ArnoKG("bfs_r", tag, step, o) = (s, p), then reads the stage
//   with ReadBFSResults through host.call_large, which has no fallback for that method.
//   Provider premise (observed on IRIS 2026.1): a reply longer than 3,641,144 characters raises <MAXSTRING>, and
//   ReadBFSResults raises before it kills the stage.
use vstd::prelude::*;
verus! {

pub struct Row { pub s: int, pub p: int, pub o: int, pub step: int }

/// The stage BFSFastJsonSorted writes: one entry per (step, target); a later edge to the same key overwrites.
pub open spec fn stage(rs: Seq<Row>) -> Map<(int, int), (int, int)>
    decreases rs.len(),
{
    if rs.len() == 0 { Map::empty() }
    else {
        let r = rs.last();
        stage(rs.drop_last()).insert((r.step, r.o), (r.s, r.p))
    }
}

/// The owner's reading (algorithms.op.walks): every walked edge is a row of the walk.
pub open spec fn walk_lists_edge(rs: Seq<Row>, r: Row) -> bool {
    stage(rs).contains_key((r.step, r.o)) && stage(rs)[(r.step, r.o)] == (r.s, r.p)
}

/// The last edge recorded for a key is the one the walk returns.
pub proof fn lemma_last_wins(rs: Seq<Row>, i: int)
    requires 0 <= i < rs.len(),
        forall|j: int| i < j < rs.len() ==> (#[trigger] rs[j]).step != rs[i].step || rs[j].o != rs[i].o,
    ensures walk_lists_edge(rs, rs[i]),
    decreases rs.len(),
{
    if i == rs.len() - 1 {
    } else {
        let rest = rs.drop_last();
        assert forall|j: int| i < j < rest.len() implies (#[trigger] rest[j]).step != rest[i].step || rest[j].o != rest[i].o by {
            assert(rest[j] == rs[j]);
        }
        lemma_last_wins(rest, i);
        assert(rs.last() == rs[rs.len() - 1]);
    }
}

/// W1-W3: when no two walked edges share a (hop, target), the walk lists every edge.
pub proof fn theorem_distinct_keys_list_every_edge(rs: Seq<Row>, i: int)
    requires 0 <= i < rs.len(),
        forall|a: int, b: int| 0 <= a < b < rs.len() ==> (#[trigger] rs[a]).step != (#[trigger] rs[b]).step || rs[a].o != rs[b].o,
    ensures walk_lists_edge(rs, rs[i]),
{
    lemma_last_wins(rs, i);
}

/// W5/W6 (new bug-alg-101): two edges walked to the same node at the same hop leave one row; the earlier is lost.
pub proof fn theorem_same_hop_target_collapses(a: Row, b: Row)
    requires a.step == b.step, a.o == b.o, (a.s, a.p) != (b.s, b.p),
    ensures !walk_lists_edge(seq![a, b], a), walk_lists_edge(seq![a, b], b),
        stage(seq![a, b]).dom() =~= set![(a.step, a.o)],
{
    reveal_with_fuel(stage, 3);
    let rs = seq![a, b];
    assert(seq![a].last() == a);
    assert(rs.last() == b);
    assert(rs.drop_last() =~= seq![a]);
    assert(seq![a].drop_last() =~= Seq::<Row>::empty());
    assert(stage(seq![a]) =~= Map::<(int, int), (int, int)>::empty().insert((a.step, a.o), (a.s, a.p)));
    assert(stage(rs) =~= stage(seq![a]).insert((b.step, b.o), (b.s, b.p)));
}

// ---- reading a reply too long for one string ----
pub enum Method { BFSFastJson, ReadBFSResults }

/// host.STREAM_FALLBACKS at the pin.
pub open spec fn has_stream(m: Method) -> bool { m == Method::BFSFastJson }

pub struct ReadOut { pub answered: bool, pub stage_left: bool }

/// host.call_large: the reply itself, or on <MAXSTRING> the method's stream variant if it has one; otherwise it raises.
pub open spec fn call_large(m: Method, overflow: bool) -> bool { !overflow || has_stream(m) }

pub open spec fn khop_read(overflow: bool) -> ReadOut { ReadOut { answered: call_large(Method::BFSFastJson, overflow), stage_left: false } }

/// kg_GRAPH_WALK's read of its stage; ReadBFSResults kills the stage only when it returns.
pub open spec fn walk_read(overflow: bool) -> ReadOut {
    let ok = call_large(Method::ReadBFSResults, overflow);
    ReadOut { answered: ok, stage_left: !ok }
}

/// L1, khop: any answer size is returned.
pub proof fn theorem_khop_answers_any_size(overflow: bool)
    ensures khop_read(overflow).answered,
{}

/// L1, walk (new bug-alg-102): an answer longer than a string raises, and the staged rows stay in ^ArnoKG.
pub proof fn theorem_walk_overflow_raises_and_leaves_stage()
    ensures !walk_read(true).answered, walk_read(true).stage_left,
        walk_read(false).answered, !walk_read(false).stage_left,
{}

}
