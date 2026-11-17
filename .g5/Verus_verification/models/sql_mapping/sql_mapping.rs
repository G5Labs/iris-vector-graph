// product 3eaa79cf: SQL table mappings (iris_vector_graph/_engine/fhir.py map_sql_table, map_sql_relationship,
//   remove_table_mapping, reload_table_mappings) as the Cypher translator reads them (iris_vector_graph/cypher/translator.py).
//   Each engine reads mappings from its own cache, loaded on first use and cleared only by its own mapping calls or by
//   reload_table_mappings. A mapped label's nodes are the table's rows; a mapped relationship joins two mapped tables on
//   `target_fk`, a column of the TARGET table holding the source row's id; any other relationship from a mapped node is
//   translated against IVG's node columns, which a mapped table does not have (IRIS refuses with SQLCODE -29).
//   map_sql_table checks the table in INFORMATION_SCHEMA under its schema, or under `USER` when the name has no schema.
use vstd::prelude::*;
verus! {

pub enum Source { Table, IvgNodes }

/// Which source a reader uses for a label: its cache's mapping if any, else IVG's own nodes.
pub open spec fn label_source(cache_has_mapping: bool) -> Source { if cache_has_mapping { Source::Table } else { Source::IvgNodes } }

/// An engine's cache after a sequence of mapping writes by `writer` engines: it reflects the store only if this engine
/// made the last write itself, reloaded after it, or loaded it for the first time after it.
pub open spec fn cache_current(made_last_write: bool, reloaded_after: bool, first_load_after: bool) -> bool {
    made_last_write || reloaded_after || first_load_after
}

/// T1/T2/T3: the writing engine reads the table while mapped and IVG's nodes after removal.
pub proof fn theorem_writer_reads_current(mapped: bool)
    ensures label_source(mapped) == (if mapped { Source::Table } else { Source::IvgNodes }),
{}

/// T9 (question fhir.sql_mapping.cache): an engine that loaded its cache before another engine mapped the label keeps reading
/// IVG's own nodes until it reloads; the two engines answer the same query differently.
pub proof fn theorem_stale_engine_reads_own_nodes()
    ensures !cache_current(false, false, false),
        label_source(true) != label_source(false),
{}

/// As built: a pair (s, t) is a relationship when the target row's fk column holds the source row's id.
pub open spec fn joined_built(s_id: int, s_fk: int, t_id: int, t_fk: int) -> bool { t_fk == s_id }
/// As documented ("a foreign key on the source table"): the source row's fk column holds the target row's id.
pub open spec fn joined_doc(s_id: int, s_fk: int, t_id: int, t_fk: int) -> bool { s_fk == t_id }

/// T4 (bug-cyp-108): with the key on the source table as documented, the built join finds nothing the documented
/// reading finds, and the reverse.
pub proof fn theorem_fk_side_differs(s_id: int, t_id: int, null_fk: int)
    requires s_id != t_id, null_fk != s_id, null_fk != t_id,
    ensures joined_doc(s_id, t_id, t_id, null_fk), !joined_built(s_id, t_id, t_id, null_fk),
        joined_built(s_id, null_fk, t_id, s_id), !joined_doc(s_id, null_fk, t_id, s_id),
{}

pub enum Rel { Mapped, Unmapped }
pub enum Outcome { Rows, SqlError }

/// T5/W46b (bug-cyp-109): a relationship from a node of a mapped label is translated only if it is a mapped
/// relationship; otherwise the statement names IVG node columns on the mapped table and IRIS refuses it.
pub open spec fn pattern_outcome(source: Source, rel: Rel) -> Outcome {
    match (source, rel) { (Source::Table, Rel::Unmapped) => Outcome::SqlError, (_, _) => Outcome::Rows }
}

pub proof fn theorem_mapped_with_ivg_relationship_errors()
    ensures pattern_outcome(Source::Table, Rel::Unmapped) == Outcome::SqlError,
        pattern_outcome(Source::Table, Rel::Mapped) == Outcome::Rows,
        pattern_outcome(Source::IvgNodes, Rel::Unmapped) == Outcome::Rows,
{}

/// T0 (bug-cyp-110): the schema map_sql_table checks an unqualified name in; IRIS keeps such tables in SQLUser.
pub open spec fn USER() -> int { 1 }
pub open spec fn SQLUSER() -> int { 2 }
pub open spec fn checked_schema(qualified: bool, schema: int) -> int { if qualified { schema } else { USER() } }
pub open spec fn accepted(qualified: bool, schema: int, actual_schema: int) -> bool { checked_schema(qualified, schema) == actual_schema }

pub proof fn theorem_unqualified_name_refused()
    ensures !accepted(false, 0, SQLUSER()), accepted(true, SQLUSER(), SQLUSER()),
{}

}
