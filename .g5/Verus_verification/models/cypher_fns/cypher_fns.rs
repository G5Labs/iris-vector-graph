// product 3eaa79cf: Cypher built-in functions whose argument is known only at run time (W54, iteration 47).
//   Translator: iris_vector_graph/cypher/translator.py (_expr_subscript 23500-23656, _scalar_string reverse 24495-24513,
//   _expr_fn_list_ops range 29114-29122, rand/randomuuid 26919-26924; _is_row_list_elem 7681-7732, _container_kind
//   21911-21963). Bodies: schema.py Graph_KG.JSON_ARRAYGET (2179), JSON_VALUE (2184), CY_LIST_ELEM (2300), RAND (2321),
//   NEWID (2324), CY_REVERSE (2364); iris_src/src/Graph/KG/CypherFn.cls IVGLISTGET,
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
/// openCypher (TCK List1): a null index gives null (`None` is a null index).
pub open spec fn rule_index_opt(len: nat, i: Option<int>) -> Elem {
    match i { Some(i) => rule_index(len, i), None => Elem::Null }
}
/// Graph_KG.JSON_ARRAYGET(j, i) = %DynamicArray.%Get(i): past the end is "" (null); a negative i raises <RANGE>, which
/// fails the whole statement (-149).
pub open spec fn json_arrayget(len: nat, i: int) -> Elem {
    if i < 0 { Elem::Fails } else if i < len { Elem::At(i) } else { Elem::Null }
}
/// JSON_ARRAYGET(j, CAST(i AS INTEGER)) with a null i: IRIS hands an ObjectScript SQL function a NULL argument as "",
/// and %Get("") reads position 0 (observed: `n.l[null]` and `n.l[n.nope]` answer the first element).
pub open spec fn json_arrayget_opt(len: nat, i: Option<int>) -> Elem {
    match i { Some(i) => json_arrayget(len, i), None => if len > 0 { Elem::At(0) } else { Elem::Null } }
}
/// Graph_KG.JSON_VALUE(l, '$.' || CAST(i AS VARCHAR)) over a list: the key is the text after "$.", read by %Get, so a
/// negative position raises, past the end is "", and a null index makes the path '$.' whose key "" reads position 0.
pub open spec fn json_value_index(len: nat, i: Option<int>) -> Elem {
    match i {
        Some(i) => if i < 0 { Elem::Fails } else if i < len { Elem::At(i) } else { Elem::Null },
        None => if len > 0 { Elem::At(0) } else { Elem::Null },
    }
}
/// Graph_KG.CY_LIST_ELEM(j, i) (schema.py 2300, 4.6.0 R227/R308): wraps a negative i, null past either end, and
/// answers the element with its type.
pub open spec fn cy_list_elem(len: nat, i: int) -> Elem {
    let pos: int = if i < 0 { len + i } else { i };
    if pos < 0 || pos >= len { Elem::Null } else { Elem::At(pos) }
}
/// CypherFn.IVGLISTGET (SQL CypherFn_IVGLISTGET): wraps a negative index, then null out of range. Not emitted by the
/// translator for these shapes.
pub open spec fn ivglistget(len: nat, i: int) -> Elem {
    let j = if i < 0 { len + i } else { i };
    if j < 0 || j >= len { Elem::Null } else { Elem::At(j) }
}
/// Where the list comes from, as _expr_subscript sees its base: a property read (`n.l`, not a Variable), a WITH column
/// holding a literal list (`WITH [1, 2, 3] AS l`, _cmp_literal_list), or another WITH column (`WITH n.l AS l`).
pub enum Src { PropertyRead, WithLiteralList, WithOtherList }
/// How the index reaches the translator: a literal (an integer or null), a row value (UNWIND, WITH, a property), or
/// a parameter.
pub enum IdxKind { LiteralInt, RowValue, Param }
/// _expr_subscript's choice. A literal integer: the R267 CASE for a negative one, else JSON_ARRAYGET (as a RETURN
/// column the typed CY_LIST_ELEM, same position); a literal null: JSON_ARRAYGET / JSON_VALUE of NULL. A row value:
/// JSON_ARRAYGET(l, CAST(i AS INTEGER)) for a property read; CY_LIST_ELEM for a WITH-held literal list when the
/// index's kind may be an integer (R308), JSON_VALUE when it is known to be null; JSON_VALUE(l, '$.' || i) for another
/// WITH column. A parameter: its integer inlined into JSON_ARRAYGET for a WITH column; a null parameter, and any
/// parameter on a property read, leaves a marker IRIS refuses ("Incorrect number of parameters").
pub open spec fn translated_index(src: Src, k: IdxKind, len: nat, i: Option<int>) -> Elem {
    match k {
        IdxKind::LiteralInt => match i {
            Some(i) => if i < 0 { if len >= -i { json_arrayget(len, len + i) } else { Elem::Null } } else { json_arrayget(len, i) },
            None => json_arrayget_opt(len, None),
        },
        IdxKind::RowValue => match src {
            Src::PropertyRead => json_arrayget_opt(len, i),
            Src::WithLiteralList => match i { Some(i) => cy_list_elem(len, i), None => json_value_index(len, None) },
            Src::WithOtherList => json_value_index(len, i),
        },
        IdxKind::Param => match src {
            Src::PropertyRead => Elem::Fails,
            _ => match i { Some(i) => json_arrayget(len, i), None => Elem::Fails },
        },
    }
}
/// Whether the reader gets the element with its type or as IRIS's text of it ('1' for 1): CY_LIST_ELEM is typed (a
/// literal index as a RETURN column, a row index into a WITH-held literal list); JSON_ARRAYGET and JSON_VALUE are text.
pub enum Ty { Typed, Text }
pub open spec fn translated_type(src: Src, k: IdxKind) -> Ty {
    match k {
        IdxKind::LiteralInt => Ty::Typed,
        IdxKind::RowValue => match src { Src::WithLiteralList => Ty::Typed, _ => Ty::Text },
        IdxKind::Param => Ty::Text,
    }
}

/// W54 L2 (bug-cyp-111, narrowed in iteration 50): for every list and every negative run-time index, a list from a
/// property, read directly or through a WITH column, fails the statement; the rule counts from the end.
pub proof fn theorem_row_negative_index_fails(len: nat, i: int)
    requires i < 0,
    ensures
        translated_index(Src::PropertyRead, IdxKind::RowValue, len, Some(i)) == Elem::Fails,
        translated_index(Src::WithOtherList, IdxKind::RowValue, len, Some(i)) == Elem::Fails,
        rule_index(len, i) != Elem::Fails,
{}
/// Iteration 50 (bug-cyp-111): a negative parameter index fails for every list source.
pub proof fn theorem_param_negative_index_fails(src: Src, len: nat, i: int)
    requires i < 0,
    ensures translated_index(src, IdxKind::Param, len, Some(i)) == Elem::Fails, rule_index(len, i) != Elem::Fails,
{}
/// Iteration 50 neighbor (review 47-49 item 2): a run-time index into a WITH-held literal list follows the rule for
/// every index, with the element's type (`WITH [1, 2, 3] AS l UNWIND [-1] AS i RETURN l[i]` answers the integer 3).
pub proof fn theorem_with_literal_row_index_follows_rule(len: nat, i: int)
    ensures
        translated_index(Src::WithLiteralList, IdxKind::RowValue, len, Some(i)) == rule_index(len, i),
        translated_type(Src::WithLiteralList, IdxKind::RowValue) == Ty::Typed,
{}
/// Neighbor: a literal integer index of any value follows the rule, for every list source and length.
pub proof fn theorem_literal_index_follows_rule(src: Src, len: nat, i: int)
    ensures translated_index(src, IdxKind::LiteralInt, len, Some(i)) == rule_index(len, i),
{}
/// Neighbor: a non-negative row index reaches the right position for every list source; from a property it is text.
pub proof fn theorem_row_nonnegative_index_follows_rule(src: Src, len: nat, i: int)
    requires i >= 0,
    ensures
        translated_index(src, IdxKind::RowValue, len, Some(i)) == rule_index(len, i),
        translated_type(Src::PropertyRead, IdxKind::RowValue) == Ty::Text,
        translated_type(Src::WithOtherList, IdxKind::RowValue) == Ty::Text,
{}
/// Iteration 50 (new, bug-cyp-126): a null index known only at run time, and a literal null on a list a row holds,
/// answers the first element of every non-empty list, from every source; the rule answers null.
pub proof fn theorem_null_index_reads_first_element(src: Src, len: nat)
    requires len > 0,
    ensures
        translated_index(src, IdxKind::RowValue, len, None) == Elem::At(0),
        translated_index(src, IdxKind::LiteralInt, len, None) == Elem::At(0),
        rule_index_opt(len, None) == Elem::Null,
{}
/// The SQL-callable CypherFn_IVGLISTGET already implements the rule for every index.
pub proof fn theorem_ivglistget_is_rule(len: nat, i: int)
    ensures ivglistget(len, i) == rule_index(len, i),
{}

// ---------------------------------------------------------------- reverse()
/// The syntactic kind of reverse()'s argument as the translator sees it. A list-valued call is one whose container
/// kind is a list (`tail()`, `split()`, `keys()`, `+` with a list); another call (`coalesce()`, `head()`) is not.
pub enum ArgKind { ListLiteral, ListComprehension, ListValuedCall, Variable, Case, PropertyRead, Slice, Subscript, OtherCall }
/// The run-time value: a list (its JSON text in SQL) or a string that does not spell a JSON list.
pub enum Val { List, Str }
/// What the reader gets: the reversed list, the reversed list's JSON text as a string, or the characters reversed.
pub enum Rev { ReversedList, ListAsJsonText, ReversedText }
/// _scalar_string: CY_REVERSE (reverses a JSON array, else the string) for list literals, comprehensions, list-valued
/// calls, variables and CASE; plain SQL REVERSE() of the text for anything else (a property read, a slice, a
/// subscript, another call).
pub open spec fn uses_cy_reverse(k: ArgKind) -> bool {
    match k {
        ArgKind::ListLiteral | ArgKind::ListComprehension | ArgKind::ListValuedCall | ArgKind::Variable | ArgKind::Case => true,
        _ => false,
    }
}
/// The reader: CY_REVERSE answers JSON text, which the engine decodes into a list only for a column the translator
/// knows to be a list (`known_list`: a literal, a list-valued call, a WITH column holding a literal list); otherwise the
/// JSON text is returned as a string. SQL REVERSE() turns the text around whatever the column is.
pub open spec fn reverse_result(k: ArgKind, v: Val, known_list: bool) -> Rev {
    match v {
        Val::Str => Rev::ReversedText,
        Val::List => if uses_cy_reverse(k) { if known_list { Rev::ReversedList } else { Rev::ListAsJsonText } } else { Rev::ReversedText },
    }
}
pub open spec fn rule_reverse(v: Val) -> Rev { match v { Val::List => Rev::ReversedList, Val::Str => Rev::ReversedText } }

/// W54 L1 (bug-cyp-112, widened in iteration 50): for a property read, a slice, a subscript or a call that is not
/// list-valued (`coalesce(n.l, [])`), reverse() of a list reverses its JSON text (']3 ,2 ,1['), whatever the column.
/// (Stated per kind: quantifying over `!uses_cy_reverse(k)` let the control `property-to-cy-reverse` survive vacuously.)
pub proof fn theorem_stored_list_reversed_as_text(known_list: bool)
    ensures
        reverse_result(ArgKind::PropertyRead, Val::List, known_list) == Rev::ReversedText,
        reverse_result(ArgKind::Slice, Val::List, known_list) == Rev::ReversedText,
        reverse_result(ArgKind::Subscript, Val::List, known_list) == Rev::ReversedText,
        reverse_result(ArgKind::OtherCall, Val::List, known_list) == Rev::ReversedText,
        rule_reverse(Val::List) == Rev::ReversedList,
{}
/// Iteration 50 (review 47-49 item 3): a variable whose list the translator does not know (`WITH n.l AS l RETURN
/// reverse(l)`) is reversed as a list but answered as its JSON text, the string '[3,2,1]'.
pub proof fn theorem_unknown_list_variable_answered_as_text()
    ensures reverse_result(ArgKind::Variable, Val::List, false) == Rev::ListAsJsonText,
            reverse_result(ArgKind::Variable, Val::List, false) != rule_reverse(Val::List),
{}
/// Neighbors: a literal list, a known list variable and a list-valued call follow the rule; every string argument does.
pub proof fn theorem_reverse_neighbors(k: ArgKind, known_list: bool)
    ensures
        reverse_result(ArgKind::ListLiteral, Val::List, true) == rule_reverse(Val::List),
        reverse_result(ArgKind::Variable, Val::List, true) == rule_reverse(Val::List),
        reverse_result(ArgKind::ListValuedCall, Val::List, true) == rule_reverse(Val::List),
        reverse_result(k, Val::Str, known_list) == rule_reverse(Val::Str),
{}

// ---------------------------------------------------------------- node[key]
/// The key expression of n[k]: an UNWIND row variable, a parameter, or a WITH column carried with the node (`WITH n,
/// 'num' AS k`). Names and values are numbered.
pub enum KeyArg { RowVar { name: int, value: int }, Param { value: int }, WithColumn { name: int, value: int } }
pub enum KeyOut { Reads(int), Fails }
/// _expr_subscript for a node: a Variable index binds input_params.get(name, name), i.e. the variable's own name when
/// it is not a parameter, and the join reads rdf_props.key = that text. A node carried through WITH is a stage column,
/// so it takes the scalar branch, where a key known to be no integer raises "Non-integer index type for list subscript".
pub open spec fn node_key_read(k: KeyArg) -> KeyOut {
    match k {
        KeyArg::RowVar { name, value } => KeyOut::Reads(name),
        KeyArg::Param { value } => KeyOut::Reads(value),
        KeyArg::WithColumn { name, value } => KeyOut::Fails,
    }
}
pub open spec fn rule_node_key(k: KeyArg) -> KeyOut {
    match k {
        KeyArg::RowVar { name, value } => KeyOut::Reads(value),
        KeyArg::Param { value } => KeyOut::Reads(value),
        KeyArg::WithColumn { name, value } => KeyOut::Reads(value),
    }
}
/// W54 L7 (bug-cyp-113): with k = 'num' from a row, n[k] reads the property named "k".
pub proof fn theorem_row_key_reads_variable_name(name: int, value: int)
    requires name != value,
    ensures node_key_read(KeyArg::RowVar { name, value }) == KeyOut::Reads(name),
            node_key_read(KeyArg::RowVar { name, value }) != rule_node_key(KeyArg::RowVar { name, value }),
{}
/// Iteration 50 (bug-cyp-113, review m5): a key from a WITH column fails the statement.
pub proof fn theorem_with_column_key_fails(name: int, value: int)
    ensures node_key_read(KeyArg::WithColumn { name, value }) == KeyOut::Fails,
            rule_node_key(KeyArg::WithColumn { name, value }) == KeyOut::Reads(value),
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
/// the statement's value. Iteration 50 (review 47-49 item 4): this is an observed premise, not a model of the
/// emitter; the translator member is a locator only (crosswalk relation `cites`).
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
