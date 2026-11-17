// product 3eaa79cf: import_rdf (iris_vector_graph/_engine/snapshot.py) per parsed statement. A quad's named context
//   decides its graph, else the `graph` argument; a literal becomes a property of the subject under the predicate's local
//   name with the literal's lexical text (no datatype); a property row is INSERTed and a failure (the key already set)
//   is logged and skipped; `infer` runs materialize_inference on the `graph` argument.
//   Reader premise (observed): get_node and Cypher read a property stored as text "2011" as the string "2011", while an
//   integer written by the API reads back as 2011.
use vstd::prelude::*;
verus! {

pub type G = int;                     // graph; 0 = default
pub enum Dt { Plain, Integer, Boolean }
pub struct Lit { pub lexical: int, pub dt: Dt }

/// Where a statement goes.
pub open spec fn effective_graph(ctx: Option<G>, arg: G) -> G { match ctx { Some(g) => g, None => arg } }

/// What is stored for a literal: its lexical text only.
pub open spec fn stored(l: Lit) -> int { l.lexical }
/// What a reader can tell about the type: only what the stored row carries (no datatype).
pub open spec fn stored_has_datatype(l: Lit) -> bool { false }

/// Property rows after importing value `v` for a key whose current value is `cur` (None if unset).
pub open spec fn after_import(cur: Option<int>, v: int) -> Option<int> { match cur { Some(c) => Some(c), None => Some(v) } }
pub open spec fn counted(cur: Option<int>) -> bool { cur is None }

/// The property key: the predicate's local name (after the last '/' or '#'): two predicates with one local name share it.
pub open spec fn key_of(namespace: int, local: int) -> int { local }

/// The graph inference runs on, given the argument and the named context the file's quads used (if one).
pub open spec fn infer_graph(arg: G, quads_ctx: Option<G>) -> G { arg }

/// R1/R2/R6: a named context wins; without one the argument decides.
pub proof fn theorem_context_wins(g: G, arg: G)
    ensures effective_graph(Some(g), arg) == g, effective_graph(None, arg) == arg,
{}

/// R5 (bug-str-109): an xsd:integer literal and the plain literal with the same text are stored identically, and the
/// stored row carries no datatype, so no reader can return the integer the source data declared.
pub proof fn theorem_datatype_dropped(n: int)
    ensures stored(Lit { lexical: n, dt: Dt::Integer }) == stored(Lit { lexical: n, dt: Dt::Plain }),
        !stored_has_datatype(Lit { lexical: n, dt: Dt::Integer }),
{}

/// R9 (bug-str-110): importing a changed literal for a key already set keeps the old value and is not counted.
pub proof fn theorem_reimport_keeps_old_value(old: int, new: int)
    requires old != new,
    ensures after_import(Some(old), new) == Some(old), !counted(Some(old)),
        after_import(None, new) == Some(new), counted(None),
{}

/// R4: two predicates with one local name write one key, so the second literal is not stored.
pub proof fn theorem_local_name_collision(ns1: int, ns2: int, local: int, v1: int, v2: int)
    requires ns1 != ns2, v1 != v2,
    ensures key_of(ns1, local) == key_of(ns2, local),
        after_import(after_import(None, v1), v2) == Some(v1),
{}

/// R10 (bug-str-111): with every quad in a named context G and no graph argument, inference runs on the default graph,
/// not on G.
pub proof fn theorem_infer_ignores_contexts(g: G)
    requires g != 0,
    ensures effective_graph(Some(g), 0) == g, infer_graph(0, Some(g)) != g,
{}

}
