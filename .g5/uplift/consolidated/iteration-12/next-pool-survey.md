# Generated GraphQL pool draw: set aside as an end-to-end proof target

The frozen hypotheses came from the unlinked production census and interfaces
entrypoint description. Eight bounded actual-source checks pass as built, with
the distinct-link hypothesis explicitly refuted. The unmodified pinned module
used opaque connection objects and no sockets, native calls or DB operations.

`AsyncConnectionPool._create_connection` returns `engine.conn` every time. With
max_size2, two admitted borrowers therefore hold the same object and the queue
later contains two references to that one object. The counter tracks logical
creation slots, not distinct IRIS links. Capacity1 blocks a second borrower;
waiting cancellation, acquired-body cancellation and a raised body return the
logical capacity in the checked schedules. The process singleton keeps the first
engine when a later app supplies another one.

The real generated app calls get_pool(engine) while building request context, but
its resolvers never acquire from it. `connection_context` is imported and never
called in resolvers.py. Stats/nodes/outgoing/incoming use engine.conn directly;
node/search/Cypher resolve through the engine itself. Startup schema introspection
and the health reader also use the engine. These synchronous calls contain no
pool acquisition; a helper proof would not establish their request isolation or
physical connection limit. No actual concurrent driver/server behavior was
tested, and no thread-safety guarantee is inferred from an asyncio schedule.

Set aside a new pool-only model: its alias result is small, but formalizing it
would not close the advertised end-to-end request boundary. A real continuation
would first recover a scoped owner for generated-app connection ownership and
concurrency, then model the actual consumers and cleanup. Sample API concurrency
and Bolt lifetime findings remain separate existing findings; no new issue or
owner decision is claimed from these hypotheses. The source is examined, not
excluded as trivial. Cypher MERGE raw branch/value flow is a stronger material
next candidate, and current communities/ledger work remains active.
