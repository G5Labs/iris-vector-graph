// product 3eaa79cf: one answer through the query pipeline to the Neo4j driver (W60, iteration 55).
//   Bolt server (iris_vector_graph/bolt_server.py):
//     A version negotiation: negotiate_version 331-347 (major = raw & 0xFF, minor = raw >> 8, range = raw >> 16; a 5.x
//       offer answers min(minor, 4) when the loop range(min(minor,4), max(-1, minor-range-1), -1) is not empty; a 4.x
//       offer with minor >= 4 answers 4.4; the four proposals in order; otherwise 0). Reader: the four bytes the client
//       reads after its handshake (_do_handshake 427-437, TcpBoltSession._do_handshake 962-972).
//     B PackStream integers: PackStream._pack_int 95-105 (tiny -16..127, INT_8, INT_16, INT_32, else struct '>q', which
//       raises for a value outside int64); _handle_pull 624-660 sends each row with _send_message, outside the RUN
//       handler's try, so a raise there ends the session (run loop) instead of a FAILURE.
//     C FAILURE codes: _handle_run 567-622 (read-only write: AccessMode; every exception, including the engine's
//       result.error re-raised as RuntimeError: Neo.ClientError.Statement.SyntaxError); _refuse_unauthorized 523-528.
//     D graph values: _node_int_id 351-352 (hash(node_id) & 0x7FFFFFFF); _recompose_graph_row 713-801 (a relationship
//       column takes the node triplet before it as start and the one after it as end, else 0); _parse_props_field
//       876-905 (a property whose str() is longer than 200 characters becomes its first 200 characters plus "...").
//       Reader: the neo4j Python driver 6.4.1's hydrated Node/Relationship (provider P-DRIVER-ID: one Node object per
//       id within a result, the last hydration's labels and properties).
//   Query pipeline (iris_vector_graph/_engine/query.py):
//     E the long-list retry: _is_long_list_temp_error 1671-1678; _execute_parsed_sql 2286-2311 (a transactional
//       statement goes to execute_transaction and is never retried; a read whose error is the long-list error goes to
//       _unwind_by_index_retry 2251-2284, which retries once only when the rewrite used an UNWIND by index and the
//       retry is neither transactional nor var-length).
//   Translator (iris_vector_graph/cypher/translator.py) and the IRIS driver:
//     F parameter lists: UNWIND $xs and $l[$s..$e] read the list through JSON_TABLE(?, ...) (translated SQL recorded in
//       iteration-55/pipeline-PAIRS.md); _expr_slice 23778-23789 appends its null-guard markers after the slice's own
//       markers but writes the guards first. Provider P-DRV-JT: intersystems-irispython 5.3.2 refuses a marker inside
//       JSON_TABLE's source ("Invalid/Incorrect number of parameters"), 5.4.1 binds it (observed).
//     G node filter equality: _stored_number_comparison 16331-16358 gives an operand whose value is a number known
//       before the query runs (_static_number: a literal or a parameter's value) the typed guard (_number_eq_sql ->
//       _node_number_eq_sql 16264); any other operand, a string literal or a string parameter, falls through to the raw
//       comparison `p.val = '1'` / `p.val = ?`. Provider P-IRIS-EQ: IRIS compares the raw column with a string as text,
//       so a stored number's text equals the string (observed; the same IRIS fact as bug-cyp-102's boolean arm).
use vstd::prelude::*;
verus! {

// ======================================================================== A. version negotiation
pub open spec fn major(raw: nat) -> nat { raw % 256 }
pub open spec fn minor(raw: nat) -> nat { (raw / 256) % 256 }
pub open spec fn rng(raw: nat) -> nat { (raw / 65536) % 256 }
pub open spec fn min4(m: nat) -> nat { if m < 4 { m } else { 4 } }
/// One proposal's answer: Some(agreed version) or None (try the next proposal).
pub open spec fn one(raw: nat) -> Option<nat> {
    if raw == 0 { None }
    else if major(raw) == 5 && (min4(minor(raw)) as int) > (minor(raw) as int) - (rng(raw) as int) - 1 {
        Some(min4(minor(raw)) * 256 + 5)
    } else if major(raw) == 4 && minor(raw) >= 4 { Some(4 * 256 + 4) }
    else { None }
}
pub open spec fn negotiate(a: nat, b: nat, c: nat, d: nat) -> nat {
    match one(a) { Some(v) => v, None => match one(b) { Some(v) => v, None => match one(c) {
        Some(v) => v, None => match one(d) { Some(v) => v, None => 0 } } } }
}
/// The versions the server can answer: 4.4 and 5.0 to 5.4.
pub open spec fn supported(v: nat) -> bool { v == 4 * 256 + 4 || (v % 256 == 5 && v / 256 <= 4) }

pub proof fn lemma_one_supported(raw: nat)
    ensures one(raw) is Some ==> supported(one(raw)->Some_0),
{
    if one(raw) is Some {
        let v = one(raw)->Some_0;
        if major(raw) == 5 && (min4(minor(raw)) as int) > (minor(raw) as int) - (rng(raw) as int) - 1 {
            let m = min4(minor(raw));
            assert(v == m * 256 + 5);
            assert((m * 256 + 5) % 256 == 5) by (nonlinear_arith) requires m <= 4;
            assert((m * 256 + 5) / 256 == m) by (nonlinear_arith) requires m <= 4;
        }
    }
}
/// General: whatever the four proposals, the answer is 0 or a version the server supports.
pub proof fn theorem_answer_is_zero_or_supported(a: nat, b: nat, c: nat, d: nat)
    ensures negotiate(a, b, c, d) == 0 || supported(negotiate(a, b, c, d)),
{
    lemma_one_supported(a); lemma_one_supported(b); lemma_one_supported(c); lemma_one_supported(d);
}
/// General rule for one 5.x proposal: it is accepted exactly when its range reaches 5.4 or below, at min(minor, 4).
pub proof fn theorem_v5_rule(raw: nat)
    requires major(raw) == 5,
    ensures (one(raw) is Some) == ((minor(raw) as int) - (rng(raw) as int) <= 4),
            one(raw) is Some ==> one(raw)->Some_0 == min4(minor(raw)) * 256 + 5,
{
    assert(raw != 0);
}
pub proof fn theorem_probe_offers()
    ensures negotiate(0x0404, 0, 0, 0) == 0x0404,
            negotiate(0x0003, 0, 0, 0) == 0,
            negotiate(0x0909, 0, 0, 0) == 0,
            negotiate(0x0005, 0, 0, 0) == 0x0005,
            negotiate(0x0405, 0, 0, 0) == 0x0405,
            negotiate(0x0805, 0, 0, 0) == 0,
            negotiate(0x020805, 0, 0, 0) == 0,
            negotiate(0x040805, 0, 0, 0) == 0x0405,
            negotiate(0x01FF, 0x0404, 0, 0) == 0x0404,
{
    assert(major(0x0404) == 4 && minor(0x0404) == 4) by (compute_only);
    assert(major(0x0003) == 3) by (compute_only);
    assert(major(0x0909) == 9) by (compute_only);
    assert(major(0x0005) == 5 && minor(0x0005) == 0 && rng(0x0005) == 0) by (compute_only);
    assert(major(0x0405) == 5 && minor(0x0405) == 4 && rng(0x0405) == 0) by (compute_only);
    assert(major(0x0805) == 5 && minor(0x0805) == 8 && rng(0x0805) == 0) by (compute_only);
    assert(major(0x020805) == 5 && minor(0x020805) == 8 && rng(0x020805) == 2) by (compute_only);
    assert(major(0x040805) == 5 && minor(0x040805) == 8 && rng(0x040805) == 4) by (compute_only);
    assert(major(0x01FF) == 255) by (compute_only);
}

// ======================================================================== B. PackStream integers and the PULL reader
pub enum IntMarker { Tiny, I8, I16, I32, I64, NoFit }
pub open spec fn int_marker(v: int) -> IntMarker {
    if -16 <= v && v <= 127 { IntMarker::Tiny }
    else if -128 <= v && v <= 127 { IntMarker::I8 }
    else if -32768 <= v && v <= 32767 { IntMarker::I16 }
    else if -2147483648 <= v && v <= 2147483647 { IntMarker::I32 }
    else if -9223372036854775808 <= v && v <= 9223372036854775807 { IntMarker::I64 }
    else { IntMarker::NoFit }
}
/// The bytes each marker takes on the wire (PackStream spec), and the values it can carry.
pub open spec fn width(m: IntMarker) -> nat {
    match m { IntMarker::Tiny => 1, IntMarker::I8 => 2, IntMarker::I16 => 3, IntMarker::I32 => 5, IntMarker::I64 => 9, IntMarker::NoFit => 0 }
}
pub open spec fn carries(m: IntMarker, v: int) -> bool {
    match m {
        IntMarker::Tiny => -16 <= v && v <= 127,
        IntMarker::I8 => -128 <= v && v <= 127,
        IntMarker::I16 => -32768 <= v && v <= 32767,
        IntMarker::I32 => -2147483648 <= v && v <= 2147483647,
        IntMarker::I64 => -9223372036854775808 <= v && v <= 9223372036854775807,
        IntMarker::NoFit => false,
    }
}
/// General: every 64-bit integer gets a marker that carries it, and no marker that carries it is narrower.
pub proof fn theorem_marker_is_smallest(v: int, m: IntMarker)
    requires -9223372036854775808 <= v && v <= 9223372036854775807,
    ensures carries(int_marker(v), v),
            carries(m, v) ==> width(int_marker(v)) <= width(m),
{
}
pub proof fn theorem_probe_widths()
    ensures int_marker(127) == IntMarker::Tiny, int_marker(128) == IntMarker::I16, int_marker(-16) == IntMarker::Tiny,
            int_marker(-17) == IntMarker::I8, int_marker(32767) == IntMarker::I16, int_marker(32768) == IntMarker::I32,
            int_marker(2147483648) == IntMarker::I64, int_marker(-9223372036854775808) == IntMarker::I64,
{
}
pub enum PullOutcome { Records, Failure, Broken }
/// What the client gets for one row value: a value with no marker raises inside PULL, outside RUN's try, and the
/// session ends (the driver reports a defunct connection).
pub open spec fn pull_value(v: int) -> PullOutcome {
    match int_marker(v) { IntMarker::NoFit => PullOutcome::Broken, _ => PullOutcome::Records }
}
/// The engine answers `RETURN 9223372036854775807 + 1` as IRIS computes it (observed 9223372036854775810): a Python
/// int past int64 reaches PULL, and the connection breaks; openCypher expects an overflow error (a FAILURE).
pub proof fn theorem_overflow_breaks_connection(v: int)
    requires v > 9223372036854775807,
    ensures pull_value(v) == PullOutcome::Broken, pull_value(v) != PullOutcome::Failure,
{
}
pub proof fn theorem_int64_values_arrive(v: int)
    requires -9223372036854775808 <= v && v <= 9223372036854775807,
    ensures pull_value(v) == PullOutcome::Records,
{
}

// ======================================================================== C. FAILURE codes
pub enum Cause { ReadOnlyWrite, BadKey, Parse, IrisSql, DriverParam, Undefined }
pub enum Code { AccessMode, Unauthorized, SyntaxError, DatabaseError, ParameterMissing }
/// As built: the two gates name their codes; every other failure in RUN is reported as a syntax error.
pub open spec fn bolt_code(c: Cause) -> Code {
    match c { Cause::ReadOnlyWrite => Code::AccessMode, Cause::BadKey => Code::Unauthorized, _ => Code::SyntaxError }
}
/// Neo4j's classification (status codes): a query that parses but fails in the database is a database error; a
/// parameter that is not supplied is ParameterMissing.
pub open spec fn neo4j_code(c: Cause) -> Code {
    match c {
        Cause::ReadOnlyWrite => Code::AccessMode, Cause::BadKey => Code::Unauthorized, Cause::Parse => Code::SyntaxError,
        Cause::IrisSql => Code::DatabaseError, Cause::DriverParam => Code::DatabaseError, Cause::Undefined => Code::ParameterMissing,
    }
}
pub proof fn theorem_runtime_failure_reported_as_syntax()
    ensures bolt_code(Cause::IrisSql) == Code::SyntaxError, neo4j_code(Cause::IrisSql) != Code::SyntaxError,
            bolt_code(Cause::DriverParam) == Code::SyntaxError, bolt_code(Cause::Parse) == bolt_code(Cause::IrisSql),
{
}
pub proof fn theorem_gate_codes_follow_rule(c: Cause)
    requires c == Cause::ReadOnlyWrite || c == Cause::BadKey || c == Cause::Parse,
    ensures bolt_code(c) == neo4j_code(c),
{
}

// ======================================================================== D. graph values over Bolt
/// D1. A node as the server sends it: its id is the low 31 bits of Python's hash of the node id (h); `key` is the node
/// id itself and `props` stands for its labels and properties.
pub struct SNode { pub key: int, pub h: int, pub props: int }
pub open spec fn bolt_id(n: SNode) -> int { n.h % 0x80000000 }
/// Provider P-DRIVER-ID (neo4j 6.4.1, observed): within one result the driver keeps one Node per id, holding the last
/// hydration's labels and properties. The client's view of a two-row result.
pub open spec fn client_view2(a: SNode, b: SNode) -> (int, int) {
    if bolt_id(a) == bolt_id(b) { (b.props, b.props) } else { (a.props, b.props) }
}
/// Two different nodes whose hashes agree in the low 31 bits reach the client as one node: the first row shows the
/// second node's properties.
pub proof fn theorem_hash_collision_loses_first_node(a: SNode, b: SNode)
    requires a.key != b.key, a.props != b.props, a.h % 0x80000000 == b.h % 0x80000000,
    ensures client_view2(a, b).0 != a.props, client_view2(a, b) == (b.props, b.props),
{
}
pub proof fn theorem_distinct_ids_keep_both(a: SNode, b: SNode)
    requires bolt_id(a) != bolt_id(b),
    ensures client_view2(a, b) == (a.props, b.props),
{
}
/// D2. Result columns as _recompose_graph_row sees them: a node triplet (its Bolt id), a relationship column, a scalar.
pub enum Col { Node(int), Rel, Scalar }
/// The node of the latest node triplet before column i (0 when none): prev_node_id.
pub open spec fn prev_node(cols: Seq<Col>, i: int) -> int
    decreases i,
{
    if i <= 0 || i > cols.len() { 0 }
    else { match cols[i - 1] { Col::Node(x) => x, _ => prev_node(cols, i - 1) } }
}
/// The node triplet right after column i, else 0.
pub open spec fn next_node(cols: Seq<Col>, i: int) -> int {
    if 0 <= i + 1 && i + 1 < cols.len() { match cols[i + 1] { Col::Node(x) => x, _ => 0 } } else { 0 }
}
/// The (start, end) the server reports for the relationship column i.
pub open spec fn reported(cols: Seq<Col>, i: int) -> (int, int) { (prev_node(cols, i), next_node(cols, i)) }
/// Stored a->b; `RETURN b, r, a` reports start b and end a.
pub proof fn theorem_endpoints_follow_columns(a: int, b: int)
    requires a != b, a != 0, b != 0,
    ensures reported(seq![Col::Node(b), Col::Rel, Col::Node(a)], 1) == (b, a),
            reported(seq![Col::Node(b), Col::Rel, Col::Node(a)], 1) != (a, b),
{
    let s = seq![Col::Node(b), Col::Rel, Col::Node(a)];
    assert(s[0] == Col::Node(b)); assert(s[2] == Col::Node(a));
    reveal_with_fuel(prev_node, 2);
}
/// General over one-hop rows: the report equals the stored direction (src, dst) exactly when src's column comes first.
pub proof fn theorem_one_hop_right_iff_source_first(x: int, y: int, src: int, dst: int)
    requires x != y, src != dst, (x == src && y == dst) || (x == dst && y == src),
    ensures (reported(seq![Col::Node(x), Col::Rel, Col::Node(y)], 1) == (src, dst)) == (x == src),
{
    let s = seq![Col::Node(x), Col::Rel, Col::Node(y)];
    assert(s[0] == Col::Node(x)); assert(s[2] == Col::Node(y));
    reveal_with_fuel(prev_node, 2);
}
pub proof fn theorem_rel_alone_or_last(a: int, b: int)
    ensures reported(seq![Col::Rel], 0) == (0int, 0int),
            reported(seq![Col::Node(a), Col::Node(b), Col::Rel], 2) == (b, 0int),
{
    let s = seq![Col::Node(a), Col::Node(b), Col::Rel];
    assert(s[1] == Col::Node(b));
    reveal_with_fuel(prev_node, 2);
}
/// D3. A whole node's property as Bolt carries it: kind and the length of Python's str() of the value.
pub enum PKind { Str, List, Map, Num, Bool }
pub struct PVal { pub kind: PKind, pub rendered: nat, pub whole: bool }
pub open spec fn bolt_node_prop(v: PVal) -> PVal {
    if v.rendered > 200 { PVal { kind: PKind::Str, rendered: 203, whole: false } } else { v }
}
/// `RETURN n.p` (any reader) and the engine's three columns carry the stored value.
pub open spec fn scalar_read(v: PVal) -> PVal { v }
/// General: a whole-node property longer than 200 characters loses its tail on Bolt, and a long list or map becomes
/// a string; the scalar read keeps it.
pub proof fn theorem_long_property_truncated(v: PVal)
    requires v.whole, v.rendered > 200,
    ensures !bolt_node_prop(v).whole, bolt_node_prop(v).kind == PKind::Str, scalar_read(v).whole,
            (v.kind == PKind::List || v.kind == PKind::Map) ==> bolt_node_prop(v).kind != v.kind,
{
}
pub proof fn theorem_short_property_kept(v: PVal)
    requires v.rendered <= 200,
    ensures bolt_node_prop(v) == v,
{
}

// ======================================================================== E. the long-list retry
/// Features of an IRIS error text that _is_long_list_temp_error reads.
pub struct ErrText { pub c400: bool, pub subscript: bool, pub temp: bool, pub sqlcq: bool, pub encoded: bool, pub over: bool }
pub open spec fn is_long(e: ErrText) -> bool { e.c400 && e.subscript && (e.temp || (e.sqlcq && e.encoded && e.over)) }
pub struct Stmt { pub used_unwind: bool, pub transactional: bool, pub var_length: bool }
/// How many times the statement runs: a transactional statement (any write) once on execute_transaction; a read
/// once, and once more when its first error is the long-list error and the by-index rewrite applies.
pub open spec fn runs(first_error: Option<ErrText>, s: Stmt) -> nat {
    if s.transactional { 1 } else { match first_error { Some(e) => if is_long(e) && s.used_unwind && !s.transactional && !s.var_length { 2 } else { 1 }, None => 1 } }
}
/// General: a write is never run twice by this retry, whatever its error.
pub proof fn theorem_write_runs_once(e: Option<ErrText>, s: Stmt)
    requires s.transactional,
    ensures runs(e, s) == 1,
{
}
/// General: a second run happens only for the long-list error, and never a third.
pub proof fn theorem_retry_only_for_long_list(e: Option<ErrText>, s: Stmt)
    ensures runs(e, s) <= 2, runs(e, s) == 2 ==> (e is Some && is_long(e->Some_0)),
{
}
pub proof fn theorem_other_400_not_retried(s: Stmt)
    ensures runs(Some(ErrText { c400: true, subscript: false, temp: true, sqlcq: true, encoded: true, over: true }), s) == 1,
            runs(Some(ErrText { c400: true, subscript: true, temp: false, sqlcq: true, encoded: true, over: false }), s) == 1,
{
}

// ======================================================================== F. parameter lists through the IRIS driver
pub enum Drv { V532, V541 }
/// Provider P-DRV-JT (observed iteration 55): does the driver bind a `?` inside JSON_TABLE's source?
pub open spec fn binds_json_table_marker(d: Drv) -> bool { match d { Drv::V532 => false, Drv::V541 => true } }
pub enum Ans { Fail, Rows(Seq<int>) }
/// UNWIND $xs reads the list through JSON_TABLE(?, ...); WITH $xs AS l UNWIND l does not.
pub open spec fn unwind_param(d: Drv, xs: Seq<int>) -> Ans { if binds_json_table_marker(d) { Ans::Rows(xs) } else { Ans::Fail } }
pub open spec fn unwind_with(d: Drv, xs: Seq<int>) -> Ans { Ans::Rows(xs) }
pub proof fn theorem_unwind_param_depends_on_driver(xs: Seq<int>)
    ensures unwind_param(Drv::V532, xs) == Ans::Fail, unwind_param(Drv::V541, xs) == Ans::Rows(xs),
            unwind_with(Drv::V532, xs) == Ans::Rows(xs),
{
}
/// $l[$s..$e]: the SQL's markers in order are guard1, guard2, the list (JSON_TABLE's source), lo, hi; the parameter
/// values are appended as [list, s, e] then the guards' [s, e].
pub enum Slot { L, S, E }
pub open spec fn params_order() -> Seq<Slot> { seq![Slot::L, Slot::S, Slot::E, Slot::S, Slot::E] }
/// The value JSON_TABLE reads is the third bound marker. Over a list it yields the elements; over a scalar's text it
/// yields no row (provider P-JT-SCALAR, observed), and JSON_ARRAYAGG of no row answers [] (observed).
pub open spec fn slice_answer(d: Drv, l: Seq<int>, s: int, e: int) -> Ans {
    if !binds_json_table_marker(d) { Ans::Fail }
    else if params_order()[2] == Slot::L { Ans::Rows(l.subrange(s, e)) }
    else { Ans::Rows(Seq::<int>::empty()) }
}
pub proof fn theorem_param_slice_answers_empty(l: Seq<int>, s: int, e: int)
    requires 0 <= s < e <= l.len(),
    ensures slice_answer(Drv::V541, l, s, e) == Ans::Rows(Seq::<int>::empty()),
            slice_answer(Drv::V541, l, s, e) != Ans::Rows(l.subrange(s, e)),
            slice_answer(Drv::V532, l, s, e) == Ans::Fail,
{
    assert(l.subrange(s, e).len() > 0);
}

// ======================================================================== G. node filter equality: literal vs parameter
/// A stored node value: a number (its value and its canonical text) or a string (its text). Texts are abstract.
pub enum Stored { Num(int, int), Str(int) }
pub enum Operand { IntLit(int), StrLit(int), IntParam(int), StrParam(int) }
pub open spec fn text_of(s: Stored) -> int { match s { Stored::Num(_, t) => t, Stored::Str(t) => t } }
/// As built: a number operand (literal or parameter, resolved before the query runs) is guarded to stored numbers; a
/// string operand is compared raw, and IRIS compares the raw column with a string as text (P-IRIS-EQ).
pub open spec fn matches(st: Stored, op: Operand) -> bool {
    match op {
        Operand::IntLit(v) => match st { Stored::Num(n, _) => n == v, _ => false },
        Operand::IntParam(v) => match st { Stored::Num(n, _) => n == v, _ => false },
        Operand::StrLit(t) => text_of(st) == t,
        Operand::StrParam(t) => text_of(st) == t,
    }
}
/// openCypher: values of different types are never equal.
pub open spec fn rule(st: Stored, op: Operand) -> bool {
    match op {
        Operand::IntLit(v) | Operand::IntParam(v) => match st { Stored::Num(n, _) => n == v, _ => false },
        Operand::StrLit(t) | Operand::StrParam(t) => match st { Stored::Str(u) => u == t, _ => false },
    }
}
/// A string literal or a string parameter equals a stored number whose text it is.
pub proof fn theorem_string_operand_matches_number(n: int, t: int)
    ensures matches(Stored::Num(n, t), Operand::StrLit(t)), !rule(Stored::Num(n, t), Operand::StrLit(t)),
            matches(Stored::Num(n, t), Operand::StrParam(t)), !rule(Stored::Num(n, t), Operand::StrParam(t)),
{
}
/// General: integer operands, and any operand over a stored string, follow the rule.
pub proof fn theorem_int_operands_and_string_values_follow_rule(st: Stored, op: Operand)
    requires (op is IntLit || op is IntParam) || st is Str,
    ensures matches(st, op) == rule(st, op),
{
}

} // verus!
fn main() {}
