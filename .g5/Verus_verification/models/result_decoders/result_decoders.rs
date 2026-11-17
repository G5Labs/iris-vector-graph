// product 3eaa79cf: the result decoders (W62, iteration 58). One stored property value, through the translator's
// column-kind decision, the SQL column form, the IRIS driver, the engine's decoders and the final reader.
//   Translator (iris_vector_graph/cypher/translator.py):
//     K1 typed column: _reads_node_value 7644-7678 (a node property reference, a WITH variable bound to one
//        (_is_node_value_var 7592-7598, prop_text_vars), coalesce() of node properties and scalars in a RETURN item
//        (_is_typed_coalesce 7620-7641), abs/arithmetic over one); no arm for CASE. A typed item is emitted as
//        CY_TYPED(sql) and its alias appended to typed_value_aliases (30673-30677; SQLQuery.typed_value_columns 7370);
//        any other item is `sql AS alias` (30690-30691).
//     K2 coalesce in a WITH stage: _scalar_coalesce 24454-24470 CASTs the first argument to VARCHAR(3641144).
//     K3 boolean expression: _is_bool_valued -> bool_expr_aliases (30713-30714); a comparison is 1 / 0 / NULL in SQL.
//     K4 OPTIONAL node triplet: _labels_sql 1289 `COALESCE((SELECT JSON_ARRAYAGG(label) ...), CAST('[]' ...))`.
//   Driver (provider P-DRV-NUM, iris_vector_graph/prop_values.py:204-212 docstring, observed): rdf_props.val holds a
//     Cypher/API number as an IRIS number; intersystems-irispython 5.3.2 hands a raw read of it to Python as a number,
//     5.4.1 as its text. CY_TYPED marks a number as "\x01N"/"\x01D" + text under any driver. A CAST to VARCHAR is text.
//   Engine decoders (iris_vector_graph/_engine/query.py), in _finish_sql_result order 332-349:
//     D1 _decode_typed_value_columns 1137-1154 -> read_prop_value (prop_values.py:266-270: decode_typed_text 204-231,
//        decode_json_list_map 234-247);
//     D2 _decode_bool_text_columns 1157-1197 -> parse_prop_text (prop_values.py:129-138) on prop_text_expr_columns,
//        _bool_expr_value 1105-1117 on bool_expr_columns;
//     D3 _decode_numeric_expr_columns 1307, _decode_map_text_columns 1602, _decode_mixed_expr_columns 1397: not
//        applied to any column kind modeled here (their column lists are empty for these shapes, observed meta);
//     D4 _decode_empty_json_strings 475, _decode_json_value_columns 497: identity on the modeled kinds.
//   Readers: execute_cypher (Python), Bolt (neo4j driver 6.4.1 via the product's TCP listener, _recompose_graph_row
//     rebuilds a node from its id/labels/props triplet: a null id is a null node), /api/cypher and
//     /db/neo4j/tx/commit (JSON of the Python values, the node as its three columns).
use vstd::prelude::*;

verus! {

// ------------------------------------------------------------------------------------------------ domains
/// A number as stored: an integer, or a float held as tenths (2.5 = F(25)).
pub enum Num { I(int), F(int) }
/// What the API writer was given (create_node properties).
pub enum W { Absent, Int(int), Float(int), Str(nat), Empty, Bool(bool), List0, Map0 }
/// VARCHAR text: a plain string (not spelling a boolean, number, list or map), '', the writer's 'true'/'false', '[]',
/// '{}', a number's text, and CY_TYPED's marked number.
pub enum Text { Plain(nat), Empty, BoolT(bool), ListT, MapT, NumT(Num), Mark(Num) }
/// rdf_props.val for one key: no row, an IRIS number, or text.
pub enum Stored { Missing, Native(Num), Txt(Text) }
/// A Python value in the engine's row: null, number, text, boolean, the empty list or map, a SQL 1/0.
pub enum DV { Null, N(Num), T(Text), B(bool), L0, M0, Bit(int) }
/// The answered value (Python/Bolt/JSON alike for these kinds).
pub enum V { Null, Int(int), Float(int), Str(Text), Bool(bool), List0, Map0 }
pub enum Driver { D532, D541 }
/// RETURN item shapes over one property value (the row's chosen branch, for CASE and coalesce).
pub enum Shape { Prop, WithProp, RetCoalesce, WithCoalesce, RetCase, WithCase }
/// The SQL form of the column.
pub enum Sql { CyTyped, Raw, CastVarchar }
pub enum Reader { Py, Bolt, Api, Tx }

// ------------------------------------------------------------------------------------------------ writer (as built)
/// The API writer's stored form (nodes_edges create_node; observed rdf_props rows).
pub open spec fn store(w: W) -> Stored {
    match w {
        W::Absent => Stored::Missing,
        W::Int(i) => Stored::Native(Num::I(i)),
        W::Float(t) => Stored::Native(Num::F(t)),
        W::Str(s) => Stored::Txt(Text::Plain(s)),
        W::Empty => Stored::Txt(Text::Empty),
        W::Bool(b) => Stored::Txt(Text::BoolT(b)),
        W::List0 => Stored::Txt(Text::ListT),
        W::Map0 => Stored::Txt(Text::MapT),
    }
}

// ------------------------------------------------------------------------------------------------ K: column kind
/// K1 _reads_node_value (translator.py:7644-7678): CASE has no arm; a WITH of coalesce is not a prop_text_var.
pub open spec fn reads_node_value(s: Shape) -> bool {
    match s {
        Shape::Prop => true,
        Shape::WithProp => true,
        Shape::RetCoalesce => true,
        Shape::WithCoalesce => false,
        Shape::RetCase => false,
        Shape::WithCase => false,
    }
}
/// The column's SQL form, derived from the shape: CY_TYPED for a typed item (30673-30677), the WITH stage's CAST for a
/// coalesce there (_scalar_coalesce 24454-24470), else the raw expression (30690-30691).
pub open spec fn sql_form(s: Shape) -> Sql {
    if reads_node_value(s) { Sql::CyTyped }
    else if s == Shape::WithCoalesce { Sql::CastVarchar }
    else { Sql::Raw }
}
/// prop_text_expr_columns membership: the typed property reads (observed meta: Prop, WithProp, RetCoalesce).
pub open spec fn prop_text_col(s: Shape) -> bool { reads_node_value(s) }

// ------------------------------------------------------------------------------------------------ SQL + driver
/// The value the driver hands Python for the column (provider P-DRV-NUM).
pub open spec fn sql_value(f: Sql, st: Stored, d: Driver) -> DV {
    match st {
        Stored::Missing => DV::Null,
        Stored::Txt(t) => DV::T(t),
        Stored::Native(n) => match f {
            Sql::CyTyped => DV::T(Text::Mark(n)),
            Sql::CastVarchar => DV::T(Text::NumT(n)),
            Sql::Raw => match d { Driver::D532 => DV::N(n), Driver::D541 => DV::T(Text::NumT(n)) },
        },
    }
}

// ------------------------------------------------------------------------------------------------ decoders
/// read_prop_value (prop_values.py:266-270): a marked number decoded; '[]' / '{}' parsed; else unchanged.
pub open spec fn dec_typed(v: DV) -> DV {
    match v {
        DV::T(Text::Mark(n)) => DV::N(n),
        DV::T(Text::ListT) => DV::L0,
        DV::T(Text::MapT) => DV::M0,
        _ => v,
    }
}
/// parse_prop_text (prop_values.py:129-138): exactly 'true' / 'false' to a boolean.
pub open spec fn dec_prop_text(v: DV) -> DV {
    match v { DV::T(Text::BoolT(b)) => DV::B(b), _ => v }
}
/// _bool_expr_value (query.py:1105-1117): 1 / 0 and 'true' / 'false' to booleans; null and anything else unchanged.
pub open spec fn dec_bool_expr(v: DV) -> DV {
    match v {
        DV::Bit(k) => if k == 1 { DV::B(true) } else if k == 0 { DV::B(false) } else { v },
        DV::T(Text::BoolT(b)) => DV::B(b),
        _ => v,
    }
}
/// _finish_sql_result (query.py:332-349) for a value column: typed decoder, then the bool-text decoder.
pub open spec fn decode(s: Shape, v: DV) -> DV {
    let a = if reads_node_value(s) { dec_typed(v) } else { v };
    if prop_text_col(s) { dec_prop_text(a) } else { a }
}
/// The client's value (Python object; neo4j driver hydration; JSON) for these kinds.
pub open spec fn to_v(v: DV) -> V {
    match v {
        DV::Null => V::Null,
        DV::N(Num::I(i)) => V::Int(i),
        DV::N(Num::F(t)) => V::Float(t),
        DV::T(t) => V::Str(t),
        DV::B(b) => V::Bool(b),
        DV::L0 => V::List0,
        DV::M0 => V::Map0,
        DV::Bit(k) => V::Int(k),
    }
}
pub open spec fn answer(s: Shape, w: W, d: Driver) -> V { to_v(decode(s, sql_value(sql_form(s), store(w), d))) }

/// openCypher: the value written, of its own type.
pub open spec fn expect(w: W) -> V {
    match w {
        W::Absent => V::Null,
        W::Int(i) => V::Int(i),
        W::Float(t) => V::Float(t),
        W::Str(s) => V::Str(Text::Plain(s)),
        W::Empty => V::Str(Text::Empty),
        W::Bool(b) => V::Bool(b),
        W::List0 => V::List0,
        W::Map0 => V::Map0,
    }
}
pub open spec fn is_num(w: W) -> bool { w is Int || w is Float }
pub open spec fn num_of(w: W) -> Num { match w { W::Int(i) => Num::I(i), W::Float(t) => Num::F(t), _ => Num::I(0) } }
pub open spec fn is_case(s: Shape) -> bool { s == Shape::RetCase || s == Shape::WithCase }

// ------------------------------------------------------------------------------------------------ theorems: value columns
/// General: every typed shape round-trips every written value of every kind, under both drivers (D3, D8 held).
pub proof fn theorem_typed_roundtrip(s: Shape, w: W, d: Driver)
    requires reads_node_value(s),
    ensures answer(s, w, d) == expect(w),
{
}
/// General, per shape: a property read, a WITH of a property and a RETURN coalesce each round-trip every written value
/// under both drivers (the K1 decision for these three shapes, not assumed).
pub proof fn theorem_property_reads_roundtrip(w: W, d: Driver)
    ensures answer(Shape::Prop, w, d) == expect(w),
            answer(Shape::WithProp, w, d) == expect(w),
            answer(Shape::RetCoalesce, w, d) == expect(w),
{
}
/// General: a missing value (the null row) decodes to null whatever the shape, driver and decoder.
pub proof fn theorem_null_row_every_decoder(s: Shape, d: Driver, f: Sql)
    ensures answer(s, W::Absent, d) == V::Null,
            sql_value(f, Stored::Missing, d) == DV::Null,
            dec_typed(DV::Null) == DV::Null, dec_prop_text(DV::Null) == DV::Null, dec_bool_expr(DV::Null) == DV::Null,
{
}
/// bug-cyp-155: a WITH column of coalesce() answers a stored number as its text under both drivers.
pub proof fn theorem_with_coalesce_number_is_text(w: W, d: Driver)
    requires is_num(w),
    ensures answer(Shape::WithCoalesce, w, d) == V::Str(Text::NumT(num_of(w))),
            answer(Shape::WithCoalesce, w, d) != expect(w),
{
}
/// bug-cyp-156 (a): a CASE column answers a stored boolean as the string 'true'/'false' under both drivers.
pub proof fn theorem_case_bool_is_text(s: Shape, b: bool, d: Driver)
    requires is_case(s),
    ensures answer(s, W::Bool(b), d) == V::Str(Text::BoolT(b)), answer(s, W::Bool(b), d) != expect(W::Bool(b)),
{
}
/// bug-cyp-156 (b): a CASE column answers a stored list or map as its JSON text under both drivers.
pub proof fn theorem_case_container_is_text(s: Shape, d: Driver)
    requires is_case(s),
    ensures answer(s, W::List0, d) == V::Str(Text::ListT), answer(s, W::Map0, d) == V::Str(Text::MapT),
            answer(s, W::List0, d) != expect(W::List0),
{
}
/// bug-cyp-156 (c): a CASE column's stored number keeps its type only under driver 5.3.2; under 5.4.1 it is text.
pub proof fn theorem_case_number_by_driver(s: Shape, w: W)
    requires is_case(s), is_num(w),
    ensures answer(s, w, Driver::D532) == expect(w),
            answer(s, w, Driver::D541) == V::Str(Text::NumT(num_of(w))),
            answer(s, w, Driver::D541) != expect(w),
{
}
/// Valid neighbor: strings (plain and empty) keep their value in every shape, under both drivers.
pub proof fn theorem_strings_held_everywhere(s: Shape, x: nat, d: Driver)
    ensures answer(s, W::Str(x), d) == expect(W::Str(x)), answer(s, W::Empty, d) == expect(W::Empty),
{
}

// ------------------------------------------------------------------------------------------------ boolean expression
/// `n.v > c` (c in tenths): SQL 1 / 0 for a stored number, NULL for no value or text (observed D6).
pub open spec fn tenths(n: Num) -> int { match n { Num::I(i) => 10 * i, Num::F(t) => t } }
pub open spec fn gt_sql(st: Stored, c: int) -> DV {
    match st { Stored::Native(n) => DV::Bit(if tenths(n) > c { 1 } else { 0 }), _ => DV::Null }
}
/// The comparison's column is in bool_expr_columns (K3), so _bool_expr_value applies.
pub open spec fn bool_expr_col() -> bool { true }
pub open spec fn answer_gt(w: W, c: int) -> V {
    let v = gt_sql(store(w), c);
    to_v(if bool_expr_col() { dec_bool_expr(v) } else { v })
}
pub proof fn theorem_compare_is_boolean_or_null(w: W, c: int)
    ensures is_num(w) ==> answer_gt(w, c) == V::Bool(tenths(num_of(w)) > c),
            w == W::Absent ==> answer_gt(w, c) == V::Null,
{
}

// ------------------------------------------------------------------------------------------------ OPTIONAL null-row node
/// The node triplet's labels column (K4): JSON_ARRAYAGG of the labels, else '[]' (translator.py:1289).
pub open spec fn labels_col(bound: bool, l: Text) -> DV { if bound { DV::T(l) } else { DV::T(Text::ListT) } }
pub open spec fn id_col(bound: bool, id: nat) -> DV { if bound { DV::T(Text::Plain(id)) } else { DV::Null } }
/// What the reader shows for the `b` of a row: Python/HTTP the three columns, Bolt the rebuilt node (null id: null).
pub open spec fn node_labels_answer(r: Reader, bound: bool, id: nat, l: Text) -> Option<V> {
    match r {
        Reader::Bolt => if id_col(bound, id) == DV::Null { Some(V::Null) } else { None },
        _ => Some(to_v(labels_col(bound, l))),
    }
}
/// bug-plt-135: an unbound OPTIONAL node answers labels '[]' (not null) at Python, /api/cypher and tx/commit; Bolt null.
pub proof fn theorem_optional_node_labels(id: nat, l: Text)
    ensures node_labels_answer(Reader::Py, false, id, l) == Some(V::Str(Text::ListT)),
            node_labels_answer(Reader::Api, false, id, l) == Some(V::Str(Text::ListT)),
            node_labels_answer(Reader::Tx, false, id, l) == Some(V::Str(Text::ListT)),
            node_labels_answer(Reader::Bolt, false, id, l) == Some(V::Null),
            node_labels_answer(Reader::Py, false, id, l) != Some(V::Null),
{
}

// ------------------------------------------------------------------------------------------------ probe rows
/// The probe's nodes: i {v: 3, s: 'si'}, f {v: 2.5, s: 'sf'}, s {s: 'txt'}, b {s: true} (observed both drivers).
pub proof fn theorem_probe_rows()
    ensures answer(Shape::RetCase, W::Int(3), Driver::D532) == V::Int(3),
            answer(Shape::RetCase, W::Float(25), Driver::D532) == V::Float(25),
            answer(Shape::RetCase, W::Int(3), Driver::D541) == V::Str(Text::NumT(Num::I(3))),
            answer(Shape::WithCase, W::Bool(true), Driver::D532) == V::Str(Text::BoolT(true)),
            answer(Shape::WithCoalesce, W::Float(25), Driver::D532) == V::Str(Text::NumT(Num::F(25))),
            answer(Shape::RetCoalesce, W::Bool(true), Driver::D541) == V::Bool(true),
            answer(Shape::Prop, W::Empty, Driver::D532) == V::Str(Text::Empty),
            answer(Shape::Prop, W::List0, Driver::D541) == V::List0,
            answer_gt(W::Float(25), 27) == V::Bool(false),
            answer_gt(W::Int(3), 27) == V::Bool(true),
            answer_gt(W::Str(0), 27) == V::Null,
{
}

fn main() {}

} // verus!
