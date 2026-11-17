// product 3eaa79cf: export_rdf_from_cypher (iris_vector_graph/_engine/rdf_export.py, _project_row_as_rdf). The query's
//   rows are projected to triples: with columns named s, p, o a row is written unless a value is null; with any other
//   three columns a row is written only if every raw value is truthy (0, "", false drop it); every value becomes an IRI.
//   The answer counts distinct triples. A query that fails sets result.error with no rows, which the export does not
//   check: it writes an empty file and answers 0.
use vstd::prelude::*;
verus! {

pub enum Val { Null, Falsy, Other }   // Falsy: 0, "", false (Python-falsy, not null)
pub enum Cols { Named, Positional }

pub open spec fn written(cols: Cols, s: Val, p: Val, o: Val) -> bool {
    match cols {
        Cols::Named => s != Val::Null && p != Val::Null && o != Val::Null,
        Cols::Positional => s == Val::Other && p == Val::Other && o == Val::Other,
    }
}

pub enum Answer { Count(nat), Raised }
/// The export's answer for a query: its distinct triples, or for a failed query 0 (the error is not read).
pub open spec fn export_answer(query_failed: bool, distinct_triples: nat) -> Answer {
    if query_failed { Answer::Count(0) } else { Answer::Count(distinct_triples) }
}

/// C1/C2/C6: an ordinary row is written either way; a null drops it either way.
pub proof fn theorem_ordinary_and_null_rows()
    ensures written(Cols::Named, Val::Other, Val::Other, Val::Other), written(Cols::Positional, Val::Other, Val::Other, Val::Other),
        !written(Cols::Named, Val::Other, Val::Other, Val::Null), !written(Cols::Positional, Val::Other, Val::Other, Val::Null),
{}

/// C11 (bug-plt-112): a value 0 keeps the row under named columns and drops it under positional ones.
pub proof fn theorem_falsy_value_depends_on_names()
    ensures written(Cols::Named, Val::Other, Val::Other, Val::Falsy), !written(Cols::Positional, Val::Other, Val::Other, Val::Falsy),
{}

/// C10 (bug-plt-111): a failed query is reported as an export of 0 triples, the same answer as a query that matched
/// nothing.
pub proof fn theorem_failed_query_looks_empty()
    ensures export_answer(true, 0) == export_answer(false, 0), export_answer(true, 5) != Answer::Raised,
{}

}
