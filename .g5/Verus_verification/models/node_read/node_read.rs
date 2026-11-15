// As-built, product 3eaa79cf. prop_value -> CY_TYPED -> read_node_value -> get_nodes.
// Numeric payloads are abstract identities, not a floating point arithmetic proof.
// CY_TYPED numeric spelling/parse identity is a provider premise; its tag selection is represented.
use vstd::prelude::*;
verus! {
pub enum Input { Integer(int), Double(int), Text(Seq<char>), Bool(bool) }
pub enum Stored { Number { payload: int, double: bool }, Text(Seq<char>), BigText(int) }
pub enum Wire { N(int), D(int), Plain(Seq<char>), S(Seq<char>), BigText(int) }
pub enum Value { Integer(int), Double(int), Text(Seq<char>), Bool(bool), BigText(int) }

pub open spec fn in64(n: int) -> bool { -(0x8000000000000000int) <= n <= 0x7fffffffffffffffint }
pub open spec fn bool_text(b: bool) -> Seq<char> {
    if b { seq!['t','r','u','e'] } else { seq!['f','a','l','s','e'] }
}
pub open spec fn write(v: Input) -> Stored {
    match v {
        Input::Integer(n) => if in64(n) { Stored::Number { payload: n, double: false } } else { Stored::BigText(n) },
        Input::Double(n) => Stored::Number { payload: n, double: true },
        Input::Text(t) => Stored::Text(t),
        Input::Bool(b) => Stored::Text(bool_text(b)),
    }
}
pub open spec fn cy_typed(s: Stored) -> Wire {
    match s {
        Stored::Number { payload, double } => if double { Wire::D(payload) } else { Wire::N(payload) },
        Stored::Text(t) => if t.len() > 0 && t[0] == '\u{1}' { Wire::S(t) } else { Wire::Plain(t) },
        Stored::BigText(n) => Wire::BigText(n),
    }
}
// The plain-text branch here covers booleans and non-container strings. JSON containers, J marks,
// malformed numeric tags and N decimal/exponent parsing remain separate, unchecked obligations.
pub open spec fn read(w: Wire) -> Value {
    match w {
        Wire::N(n) => Value::Integer(n),
        Wire::D(n) => Value::Double(n),
        Wire::S(t) => Value::Text(t),
        Wire::Plain(t) => if t == bool_text(true) { Value::Bool(true) }
            else if t == bool_text(false) { Value::Bool(false) } else { Value::Text(t) },
        Wire::BigText(n) => Value::BigText(n),
    }
}
pub open spec fn journey(v: Input) -> Value { read(cy_typed(write(v))) }
pub proof fn theorem_numeric_writer_and_reader(n: int)
    requires in64(n),
    ensures journey(Input::Integer(n)) == Value::Integer(n),
        journey(Input::Double(n)) == Value::Double(n),
{}
pub proof fn theorem_outside_int64_stays_text(n: int)
    requires !in64(n), ensures journey(Input::Integer(n)) == Value::BigText(n),
{}
pub proof fn theorem_numeric_looking_text_distinct()
    ensures journey(Input::Integer(29)) == Value::Integer(29),
        journey(Input::Text(seq!['2','9'])) == Value::Text(seq!['2','9']),
        journey(Input::Double(5)) == Value::Double(5),
        journey(Input::Text(seq!['5'])) == Value::Text(seq!['5']),
{}
pub proof fn theorem_escape_strips_once(t: Seq<char>)
    requires t.len() > 0, t[0] == '\u{1}',
    ensures journey(Input::Text(t)) == Value::Text(t),
{}
pub proof fn theorem_boolean_precedes_integer(b: bool)
    ensures journey(Input::Bool(b)) == Value::Bool(b),
{ assert(bool_text(true) != bool_text(false)); }

pub struct Row { pub id: int, pub label_rows: nat, pub property_rows: nat, pub node_row: bool }
pub open spec fn included(r: Row) -> bool {
    r.label_rows > 0 || r.property_rows > 0 || r.node_row
}
pub open spec fn result(ids: Seq<int>, rows: Map<int, Row>) -> Seq<int>
    recommends forall|i: int| 0 <= i < ids.len() ==> rows.contains_key(ids[i]),
    decreases ids.len(),
{
    if ids.len() == 0 { seq![] } else {
        let tail = result(ids.drop_first(), rows);
        if included(rows[ids[0]]) { seq![ids[0]] + tail } else { tail }
    }
}
pub proof fn theorem_bare_node_vs_absent(id: int)
    ensures included(Row { id, label_rows: 0, property_rows: 0, node_row: true }),
        !included(Row { id, label_rows: 0, property_rows: 0, node_row: false }),
{}
pub proof fn theorem_child_rows_do_not_check_node(id: int, l: nat, p: nat)
    requires l > 0 || p > 0,
    ensures included(Row { id, label_rows: l, property_rows: p, node_row: false }),
{}
pub proof fn theorem_requested_duplicates_remain(id: int, rows: Map<int, Row>)
    requires rows.contains_key(id), included(rows[id]),
    ensures result(seq![id,id], rows) == seq![id,id],
{ reveal_with_fuel(result, 3); }

// Key abstraction: 0=id, 1=labels, 2=p_id, 3=p_labels, all other keys >=4.
pub open spec fn alias(k: int) -> int { if k == 0 { 2 } else if k == 1 { 3 } else { k } }
pub open spec fn assign(m: Map<int, int>, k: int, v: int) -> Map<int, int> { m.insert(alias(k), v) }
pub proof fn theorem_structural_keys_kept(m: Map<int,int>, k: int, v: int)
    requires k >= 0, m.contains_key(0), m.contains_key(1),
    ensures assign(m,k,v)[0] == m[0], assign(m,k,v)[1] == m[1],
{}
pub proof fn witness_alias_collision(a: int, b: int)
    requires a != b,
    ensures assign(assign(Map::empty(),0,a),2,b)[2] == b,
        assign(assign(Map::empty(),2,b),0,a)[2] == a,
{}
}
