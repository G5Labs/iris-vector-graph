// As-built projection of import_graph_ndjson's NODE flow, 3eaa79cf.
// JSON parsing is a boundary port: Blank, Invalid and NonObject are parser outcomes;
// Object carries raw kind/type fields. Edge/temporal effects are deliberately not claimed.
use vstd::prelude::*;
verus! {
pub enum Kind { Missing, Node, Rel, Edge, Temporal, Other }
pub enum Line {
    Blank, Invalid, NonObject,
    Object { kind: Kind, etype: Kind, id: Option<int>, chars: nat, value: int },
}
pub enum Admission { Ignore, Skip, Node { id: int, chars: nat, value: int }, OutsideScope }
pub open spec fn selected(k: Kind, t: Kind) -> Kind {
    if k is Missing && t is Node { Kind::Node }
    else if k is Missing && t is Rel { Kind::Edge }
    else { k }
}
pub open spec fn admit(line: Line) -> Admission {
    match line {
        Line::Blank => Admission::Ignore,
        Line::Invalid | Line::NonObject => Admission::Skip,
        Line::Object { kind, etype, id, chars, value } => {
            let k = selected(kind, etype);
            if k is Node {
                match id { Some(id) => Admission::Node { id, chars, value }, None => Admission::Skip }
            } else if k is Edge || k is Temporal { Admission::OutsideScope }
            else { Admission::Skip }
        }
    }
}
pub struct State { pub props: Map<int,int>, pub nodes: nat, pub skipped: nat, pub stopped: bool }
pub open spec fn start(props: Map<int,int>) -> State { State { props, nodes: 0, skipped: 0, stopped: false } }
pub open spec fn step(s: State, line: Line) -> State {
    if s.stopped { s } else {
        match admit(line) {
            Admission::Ignore | Admission::OutsideScope => s,
            Admission::Skip => State { skipped: s.skipped+1, ..s },
            Admission::Node { id, chars, value } => {
                if chars > 256 { State { stopped: true, ..s } }
                else { State { props: if s.props.contains_key(id) { s.props } else { s.props.insert(id,value) }, nodes: s.nodes+1, ..s } }
            }
        }
    }
}
pub open spec fn run(s: State, lines: Seq<Line>) -> State
    decreases lines.len(),
{
    if lines.len()==0 { s } else { run(step(s,lines[0]),lines.drop_first()) }
}
pub open spec fn node(id: int, value: int) -> Line {
    Line::Object { kind: Kind::Node, etype: Kind::Missing, id: Some(id), chars: 1, value }
}
pub proof fn theorem_raw_kind_precedence()
    ensures selected(Kind::Missing,Kind::Node) is Node,
        selected(Kind::Missing,Kind::Rel) is Edge,
        selected(Kind::Other,Kind::Node) is Other,
{}
pub proof fn theorem_unknown_malformed_and_blank(s: State)
    requires !s.stopped,
    ensures step(s,Line::Invalid).skipped == s.skipped+1,
        step(s,Line::Object { kind: Kind::Other, etype: Kind::Node, id: Some(1), chars: 1, value: 4 }).skipped == s.skipped+1,
        step(s,Line::Blank) == s,
        step(s,Line::Invalid).props == s.props,
{}
pub proof fn theorem_missing_id_skipped(s: State)
    requires !s.stopped,
    ensures step(s,Line::Object { kind: Kind::Node, etype: Kind::Missing, id: None, chars: 0, value: 3 }).skipped==s.skipped+1,
{}
pub proof fn theorem_new_vs_duplicate(s: State,id: int,v: int)
    requires !s.stopped,
    ensures step(s,node(id,v)).nodes==s.nodes+1,
        step(s,node(id,v)).props.contains_key(id),
        step(s,node(id,v)).props[id] == if s.props.contains_key(id) { s.props[id] } else { v },
{}
pub proof fn theorem_duplicate_count_not_upsert(id: int,a: int,b: int)
    ensures run(start(Map::empty()),seq![node(id,a),node(id,b)]).nodes==2,
        run(start(Map::empty()),seq![node(id,a),node(id,b)]).props[id]==a,
{ reveal_with_fuel(run,3); }
pub proof fn theorem_wide_writer_refusal_preserves_prefix(id: int,a: int)
    ensures run(start(Map::empty()),seq![node(id,a),Line::Object { kind: Kind::Node,etype:Kind::Missing,id:Some(id+1),chars:257,value:9 }]).stopped,
        run(start(Map::empty()),seq![node(id,a),Line::Object { kind: Kind::Node,etype:Kind::Missing,id:Some(id+1),chars:257,value:9 }]).props[id]==a,
        run(start(Map::empty()),seq![node(id,a),Line::Object { kind: Kind::Node,etype:Kind::Missing,id:Some(id+1),chars:257,value:9 }]).nodes==1,
{ reveal_with_fuel(run,3); }
pub proof fn theorem_no_resume_after_error(s: State,lines: Seq<Line>)
    requires s.stopped, ensures run(s,lines)==s,
    decreases lines.len(),
{ if lines.len()>0 { theorem_no_resume_after_error(s,lines.drop_first()); } }
pub proof fn theorem_skip_then_node_reaches_reader(id: int,v: int)
    ensures run(start(Map::empty()),seq![Line::Invalid,node(id,v)]).props[id]==v,
        run(start(Map::empty()),seq![Line::Invalid,node(id,v)]).nodes==1,
        run(start(Map::empty()),seq![Line::Invalid,node(id,v)]).skipped==1,
{ reveal_with_fuel(run,3); }
}
