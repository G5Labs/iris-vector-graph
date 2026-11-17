// product 3eaa79cf: Cypher built-in functions whose argument is known only at run time (W54, iteration 47).
//   Translator: iris_vector_graph/cypher/translator.py (_expr_subscript 23500-23656, _scalar_string reverse 24495-24513,
//   _expr_fn_list_ops range 29112-29119, rand/randomuuid 26919-26924). Bodies: schema.py Graph_KG.JSON_ARRAYGET (2179),
//   CY_LIST_ELEM (2300), RAND (2321), NEWID (2324), CY_REVERSE (2364); iris_src/src/Graph/KG/CypherFn.cls IVGLISTGET,
//   IVGRANGE, IVGTYPEERROR (with their SqlProcs forwarders). Reader: the execute_cypher result row (SQL path; the native
//   executor declines these shapes on the fixture).
use vstd::prelude::*;
verus! {

// ---------------------------------------------------------------- list element by index
/// What a reader gets for list[i]: the element at a 0-based position, null, or a failed statement.
pub enum Elem { At(int), Null, Fails }

/// openCypher: a negative index counts from the end; past either end is null.
pub open spec fn rule_index(len: nat, i: int) -> Elem {
    if 0 <= i && i < len { Elem::At(i) } else if i < 0 && -i <= len { Elem::At(len + i) } else { Elem::Null }
}
/// Graph_KG.JSON_ARRAYGET(j, i) = %DynamicArray.%Get(i): past the end is "" (null); a negative i raises <RANGE>, which
/// fails the whole statement (-149).
pub open spec fn json_arrayget(len: nat, i: int) -> Elem {
    if i < 0 { Elem::Fails } else if i < len { Elem::At(i) } else { Elem::Null }
}
/// CypherFn.IVGLISTGET (SQL CypherFn_IVGLISTGET): wraps a negative index, then null out of range. Not emitted by the
/// translator for these shapes.
pub open spec fn ivglistget(len: nat, i: int) -> Elem {
    let j = if i < 0 { len + i } else { i };
    if j < 0 || j >= len { Elem::Null } else { Elem::At(j) }
}
/// How the index reaches the translator.
pub enum IdxKind { LiteralInt, RowValue }
/// _expr_subscript for a list held in a property or a WITH column: a literal negative index is wrapped in
/// CASE WHEN JSON_ARRAYLENGTH(l) >= -i THEN JSON_ARRAYGET(l, len + i) END; any other index is passed to
/// JSON_ARRAYGET(l, CAST(i AS INTEGER)) as it is.
pub open spec fn translated_index(k: IdxKind, len: nat, i: int) -> Elem {
    match k {
        IdxKind::LiteralInt => if i < 0 { if len >= -i { json_arrayget(len, len + i) } else { Elem::Null } } else { json_arrayget(len, i) },
        IdxKind::RowValue => json_arrayget(len, i),
    }
}

/// W54 L2 (new finding): over [1,2,3] an index of -1 from an UNWIND row fails the statement; the rule answers 3.
pub proof fn theorem_row_negative_index_fails()
    ensures translated_index(IdxKind::RowValue, 3, -1) == Elem::Fails, rule_index(3, -1) == Elem::At(2),
{}
/// Neighbor: a literal index of any value follows the rule, for every list length.
pub proof fn theorem_literal_index_follows_rule(len: nat, i: int)
    ensures translated_index(IdxKind::LiteralInt, len, i) == rule_index(len, i),
{}
/// Neighbor: a non-negative row index follows the rule.
pub proof fn theorem_row_nonnegative_index_follows_rule(len: nat, i: int)
    requires i >= 0,
    ensures translated_index(IdxKind::RowValue, len, i) == rule_index(len, i),
{}
/// The SQL-callable CypherFn_IVGLISTGET already implements the rule for every index.
pub proof fn theorem_ivglistget_is_rule(len: nat, i: int)
    ensures ivglistget(len, i) == rule_index(len, i),
{}

// ---------------------------------------------------------------- reverse()
/// The syntactic kind of reverse()'s argument as the translator sees it.
pub enum ArgKind { ListLiteral, ListComprehension, ListFunction, Variable, Case, PropertyRead }
/// The run-time value: a list (its JSON text in SQL) or a string.
pub enum Val { List, Str }
pub enum Rev { ReversedList, ReversedText }
/// _scalar_string: CY_REVERSE (reverses a JSON array, else the string) for list literals, comprehensions, list-valued
/// functions, variables and CASE; plain SQL REVERSE() of the text for anything else.
pub open spec fn uses_cy_reverse(k: ArgKind) -> bool {
    match k { ArgKind::PropertyRead => false, _ => true }
}
pub open spec fn reverse_result(k: ArgKind, v: Val) -> Rev {
    if uses_cy_reverse(k) { match v { Val::List => Rev::ReversedList, Val::Str => Rev::ReversedText } } else { Rev::ReversedText }
}
pub open spec fn rule_reverse(v: Val) -> Rev { match v { Val::List => Rev::ReversedList, Val::Str => Rev::ReversedText } }

/// W54 L1 (new finding): reverse(n.l) of a stored list reverses its JSON text (']3 ,2 ,1[').
pub proof fn theorem_stored_list_reversed_as_text()
    ensures reverse_result(ArgKind::PropertyRead, Val::List) == Rev::ReversedText, rule_reverse(Val::List) == Rev::ReversedList,
{}
/// Neighbors: a literal list, and a stored string, follow the rule.
pub proof fn theorem_reverse_neighbors()
    ensures reverse_result(ArgKind::ListLiteral, Val::List) == rule_reverse(Val::List),
            reverse_result(ArgKind::PropertyRead, Val::Str) == rule_reverse(Val::Str),
{}

// ---------------------------------------------------------------- node[key]
/// The key expression of n[k]: a row variable, a parameter, or a string literal. Names and values are numbered.
pub enum KeyArg { RowVar { name: int, value: int }, Param { value: int } }
/// _expr_subscript for a node: a Variable index binds input_params.get(name, name), i.e. the variable's own name when
/// it is not a parameter; the join then reads rdf_props.key = that text.
pub open spec fn node_key_read(k: KeyArg) -> int {
    match k { KeyArg::RowVar { name, value } => name, KeyArg::Param { value } => value }
}
pub open spec fn rule_node_key(k: KeyArg) -> int {
    match k { KeyArg::RowVar { name, value } => value, KeyArg::Param { value } => value }
}
/// W54 L7 (new finding): with k = 'num' from a row, n[k] reads the property named "k".
pub proof fn theorem_row_key_reads_variable_name(name: int, value: int)
    requires name != value,
    ensures node_key_read(KeyArg::RowVar { name, value }) == name, node_key_read(KeyArg::RowVar { name, value }) != rule_node_key(KeyArg::RowVar { name, value }),
{}
/// Neighbor: a parameter key reads the named property.
pub proof fn theorem_param_key_follows_rule(value: int)
    ensures node_key_read(KeyArg::Param { value }) == rule_node_key(KeyArg::Param { value }),
{}

// ---------------------------------------------------------------- range() with a run-time step
pub enum Range { Elems(nat), ArgumentError }
/// IVGRANGE's loops: `For i = start:step:end` for a positive step, `While i >= end ... i += step` for a negative one.
pub open spec fn ivg_count(start: int, end: int, step: int) -> nat {
    if step > 0 { if end >= start { ((end - start) / step + 1) as nat } else { 0 } }
    else if step < 0 { if start >= end { ((start - end) / (-step) + 1) as nat } else { 0 } }
    else { 0 }
}
/// openCypher's count of start, start + step, ... not passing end (written separately from IVGRANGE's, so that a
/// control on IVGRANGE does not also change the rule).
pub open spec fn rule_count(start: int, end: int, step: int) -> nat {
    if (step > 0 && end < start) || (step < 0 && end > start) || step == 0 { 0 }
    else if step > 0 { ((end - start) / step + 1) as nat }
    else { ((start - end) / (-step) + 1) as nat }
}
/// CypherFn.IVGRANGE (reached through CypherFn_IVGRANGE for a step known only at run time): `If stepVal = 0 { Return "[]" }`.
pub open spec fn ivgrange(start: int, end: int, step: int) -> Range {
    if step == 0 { Range::Elems(0) } else { Range::Elems(ivg_count(start, end, step)) }
}
/// openCypher: a step of 0 is ArgumentError NumberOutOfRange (List11); the translator raises it for a literal 0.
pub open spec fn rule_range(start: int, end: int, step: int) -> Range {
    if step == 0 { Range::ArgumentError } else { Range::Elems(rule_count(start, end, step)) }
}
/// W54 L4 (inherited F-C0841): a run-time step of 0 answers [].
pub proof fn theorem_runtime_zero_step_empty()
    ensures ivgrange(1, 3, 0) == Range::Elems(0), rule_range(1, 3, 0) == Range::ArgumentError,
{}
/// Neighbor: every non-zero run-time step follows the rule (a step against the direction gives []).
pub proof fn theorem_nonzero_step_follows_rule(start: int, end: int, step: int)
    requires step != 0,
    ensures ivgrange(start, end, step) == rule_range(start, end, step),
{}

// ---------------------------------------------------------------- randomUUID() and rand() per row
/// The translator emits Graph_KG.NEWID() / Graph_KG.RAND(), calls with no row argument. Provider premise (observed on
/// IRIS 2026.1, not established for other versions): such a call is evaluated once per statement, so every row sees
/// the statement's value.
pub open spec fn evaluated_per_row() -> bool { false }
pub open spec fn value_on_row(stmt_value: int, row_value: int) -> int {
    if evaluated_per_row() { row_value } else { stmt_value }
}
/// W54 L12 (new finding): two rows whose fresh draws differ still answer one value.
pub proof fn theorem_rows_share_one_value(stmt_value: int, row1: int, row2: int)
    requires row1 != row2,
    ensures value_on_row(stmt_value, row1) == value_on_row(stmt_value, row2),
{}

}
