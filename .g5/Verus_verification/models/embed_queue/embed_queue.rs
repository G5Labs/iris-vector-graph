// product 3eaa79cf: the embedding queue's two workers and the owner's rule (search.embedding.queue).
//   IRIS worker: iris_src/src/Graph/KG/EmbedQueue.cls ProcessBatch (called by EmbedQueueTask.OnTask, which
//   start_background_embedding starts). Python worker: iris_vector_graph/_engine/embeddings.py process_embed_queue.
//   One entry at a time; the batch continues past each entry in both workers.
//   Provider premises (observed on IRIS 2026.1, iteration 36): SELECT EMBEDDING(?, ?) reports an unknown config
//   (SQLCODE -280) and a provider failure (-400) through SQLCODE, not by throwing; a provider may answer nothing;
//   an empty ObjectScript host variable binds as SQL NULL, so the worker's INSERT of the default graph's name ""
//   into kg_NodeEmbeddings.graph_id (a required column) is refused (-108).
use vstd::prelude::*;
verus! {

/// What the embedding provider answers for the entry's text: IRIS's EMBEDDING() or the Python engine's embedder.
pub enum Provider { Vector, Empty, Fail }
pub enum Status { Pending, Done, Error }

pub struct Entry {
    pub named_graph: bool,   // ^EmbedQueue(reqId,"graph") is a graph name, not "" (the default graph)
    pub node_in_graph: bool, // the node is in the entry's graph (NodeInGraph; a failed check is refused the same way)
    pub has_route: bool,     // a named graph has a node route for the entry's config (RouteTable)
    pub dtype_ok: bool,      // that route's element type is one the worker writes (RouteDtype)
    pub config_known: bool,  // the entry's config names a %Embedding.Config IRIS knows
    pub provider: Provider,
    pub width_ok: bool,      // the vector fits the target's declared width
    pub own_model: bool,     // the entry asks for the model this worker produces (always so for the IRIS worker,
                             // which embeds with the entry's own config)
}

pub struct Outcome { pub status: Status, pub reason: bool, pub stored: bool }

pub open spec fn done(stored: bool) -> Outcome { Outcome { status: Status::Done, reason: false, stored } }
pub open spec fn error() -> Outcome { Outcome { status: Status::Error, reason: true, stored: false } }

/// L1, the owner's rule: a worked entry leaves PENDING; it is DONE exactly when its vector is stored; otherwise it is
/// an ERROR with a reason. An entry asking for another model than the worker produces is an ERROR.
pub open spec fn rule_ok(e: Entry, o: Outcome) -> bool {
    o.status != Status::Pending
    && ((o.status == Status::Done) == o.stored)
    && (o.status == Status::Error ==> o.reason)
    && (!e.own_model ==> o.status == Status::Error)
}

/// Provider premise: the IRIS worker's INSERT succeeds only for a named graph (the default graph's "" binds as NULL
/// into a required column) and a vector of the declared width.
pub open spec fn iris_insert_ok(e: Entry) -> bool { e.named_graph && e.width_ok }

/// As-built ProcessBatch, one PENDING entry.
pub open spec fn iris_worker(e: Entry) -> Outcome {
    if !e.node_in_graph { error() }
    else if e.named_graph && !e.has_route { error() }
    else if e.named_graph && !e.dtype_ok { error() }
    else {
        let answered = e.config_known && e.provider == Provider::Vector;
        if !answered { done(false) }               // SQLCODE < 0 or no vector: the write is skipped, status DONE
        else if iris_insert_ok(e) { done(true) }
        else { error() }                           // a refused INSERT is thrown and caught as the entry's ERROR
    }
}

/// Reviewed repair (not the product): no answer is the entry's ERROR, and the default graph's name is bound as the
/// empty string rather than NULL.
pub open spec fn iris_insert_ok_reviewed(e: Entry) -> bool { e.width_ok }
pub open spec fn iris_worker_reviewed(e: Entry) -> Outcome {
    if !e.node_in_graph { error() }
    else if e.named_graph && !e.has_route { error() }
    else if e.named_graph && !e.dtype_ok { error() }
    else {
        let answered = e.config_known && e.provider == Provider::Vector;
        if !answered { error() }
        else if iris_insert_ok_reviewed(e) { done(true) }
        else { error() }
    }
}

/// Python worker: store_embedding (through _upsert_node_embedding) succeeds for a vector of the route's width.
pub open spec fn py_store_ok(e: Entry) -> bool { e.provider == Provider::Vector && e.width_ok }

/// As-built process_embed_queue, one claimed entry, run to completion: identity first, then encode (a whole-batch
/// failure falls back per entry), SetResult DONE, then the store; a failure at any step is the entry's ERROR.
pub open spec fn py_worker(e: Entry) -> Outcome {
    if !e.own_model { error() }
    else if e.provider == Provider::Fail { error() }
    else if py_store_ok(e) { done(true) }
    else { error() }
}

/// The Python worker's state between SetResult DONE and the store (an interruption there leaves it).
pub open spec fn py_after_mark(e: Entry) -> Outcome { done(false) }

/// Q3-Q5 (Python worker): every entry ends by the owner's rule, for nodes present in their graph.
pub proof fn theorem_python_worker_meets_rule(e: Entry)
    requires e.node_in_graph,
    ensures rule_ok(e, py_worker(e)),
{}

/// The IRIS worker stores a named graph's vector and reports DONE when the provider answers.
pub proof fn theorem_iris_named_success_stored(e: Entry)
    requires e.named_graph, e.node_in_graph, e.has_route, e.dtype_ok, e.config_known,
        e.provider == Provider::Vector, e.width_ok, e.own_model,
    ensures iris_worker(e) == done(true), rule_ok(e, iris_worker(e)),
{}

/// bug-srch-103: when the provider fails, answers nothing or the config is unknown, the IRIS worker marks the entry
/// DONE with no vector and no reason, which the owner's rule rejects.
pub proof fn theorem_iris_unanswered_marked_done(e: Entry)
    requires e.node_in_graph, e.named_graph ==> (e.has_route && e.dtype_ok),
        !(e.config_known && e.provider == Provider::Vector),
    ensures iris_worker(e).status == Status::Done, !iris_worker(e).stored, !iris_worker(e).reason,
        !rule_ok(e, iris_worker(e)),
{}

/// bug-srch-104: the IRIS worker never stores a default-graph vector.
pub proof fn theorem_iris_default_graph_never_stores(e: Entry)
    requires !e.named_graph,
    ensures !iris_worker(e).stored,
{}

/// The reviewed repair meets the owner's rule on every entry (the IRIS worker produces the entry's own model).
pub proof fn theorem_reviewed_iris_meets_rule(e: Entry)
    requires e.own_model,
    ensures rule_ok(e, iris_worker_reviewed(e)),
{}

/// Open question search.embedding.queue.processing: the Python worker's mark-before-store leaves a DONE entry with no
/// vector if it is interrupted between the two writes; the rule rejects that state.
pub proof fn theorem_interrupted_mark_breaks_rule(e: Entry)
    ensures !rule_ok(e, py_after_mark(e)),
{}

}
