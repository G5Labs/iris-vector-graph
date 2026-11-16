// product 3eaa79cf: the HTTP Cypher readers (iris_vector_graph/cypher_api.py).
//   _run_cypher :239-265 keeps at most `limit` rows of execute_cypher's answer (default 1000); cypher_query :351-375
//   (`limitRows`, default 1000, and `rowCount` = rows kept), neo4j_tx_commit :379-410 and neo4j_query_v2 :436-460 (the
//   default limit, no count). Provider premise: execute_cypher's rows (bound elsewhere) are the input; JSON encoding of
//   ordinary values is unchanged (observed in W38).
use vstd::prelude::*;
verus! {
pub type R=int;
pub open spec fn kept(rows:Seq<R>,limit:nat)->Seq<R> {if rows.len()<=limit {rows} else {rows.subrange(0,limit as int)}}
pub open spec fn DEFAULT()->nat {1000}
pub struct ApiAnswer {pub rows:Seq<R>,pub row_count:nat}
pub open spec fn api(rows:Seq<R>,limit_rows:nat)->ApiAnswer {let k=kept(rows,limit_rows); ApiAnswer{rows:k,row_count:k.len()}}
/// /db/neo4j/tx/commit and /db/neo4j/query/v2: the rows kept under the default limit, and nothing else about their number.
pub open spec fn neo4j(rows:Seq<R>)->Seq<R> {kept(rows,DEFAULT())}

/// Every route answers at most its limit, and the full answer when it fits.
pub proof fn theorem_answer_is_prefix(rows:Seq<R>,limit:nat)
 ensures kept(rows,limit).len()<=limit || kept(rows,limit)==rows,
  rows.len()<=limit ==> kept(rows,limit)==rows,
  rows.len()>limit ==> kept(rows,limit).len()==limit,
{}
/// W38 H5, as built: two engine answers that differ (1000 rows vs more, same first 1000) give the same Neo4j-route answer,
/// so a client of those routes cannot tell a complete answer from a cut one.
pub proof fn theorem_neo4j_answer_cannot_tell_truncation(a:Seq<R>,b:Seq<R>)
 requires a.len()==DEFAULT(),b.len()>DEFAULT(),b.subrange(0,DEFAULT() as int)=~=a
 ensures neo4j(a)=~=neo4j(b),a!=b,
{assert(a.len()!=b.len());}
/// /api/cypher's rowCount is the number of rows kept, not the number the query produced.
pub proof fn theorem_api_row_count_is_kept(rows:Seq<R>,limit:nat)
 requires rows.len()>limit
 ensures api(rows,limit).row_count==limit,api(rows,limit).row_count<rows.len(),
{}
}
