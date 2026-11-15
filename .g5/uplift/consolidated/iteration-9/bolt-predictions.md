# Bolt stream predictions before new model

Product3eaa79cf; input foundation9e1209165d5076039d2ee315cc5cf67e4aa00856.
Read iteration8 remaining PAIRS/survey and raw local probes before following the
current session/codec bodies or existing formal contracts. These are inherited
source-informed builder predictions, not a hidden/blind evaluation. Product and
shared foundation stay unchanged; root owns protocol adjudication/native probes.

| Neighbor | Expected as-built result to derive, and intended distinction |
|---|---|
| Default chunking / max_chunk1 for RESET body then RUN | stateless decode recovers both bodies; session default preserves RUN, one-byte first framing retains a terminator and the next WS read can yield empty bytes. Derive actual and default re-encoded lengths from raw headers/payload rather than supply consumed length/messages |
| complete / incomplete header or payload or missing terminator | only complete chunk-terminated bodies reach decoded output; incomplete original suffix must remain a raw-buffer concern. Exact current buffer update awaits source trace |
| two complete bodies in one transport frame / split transport frames | queue preserves decoded order; raw buffer length and subsequent extraction remain coupled to actual framing, not assumed canonical encoding |
| RUN rows1,2,3 then PULL1 followed by PULL1 / PULL-1 | first emits1 then drops pending suffix and omits has_more / emits all. Known F-1602, not new. Compatible intended PULL retains suffix and reports has_more |
| RUN then DISCARD/RESET/ROLLBACK / COMMIT then PULL | clear pending rows / COMMIT leaves rows; include result/column/type writers and final encoded records |
| engine result.error / successful empty result | FAILURE and FAILED with cleared pending / SUCCESS with empty result; dispatch FAILED ignores ordinary PULL and transaction commands until RESET/GOODBYE |
| second RUN / RESET followed by RUN | replaces prior pending output / recovers for next result; do not treat per-session engine caching as message-state reset |
| typed scalar/list/map/JSON-looking text | admitted PackStream values survive record emission with their types; arbitrary graph/custom type and codec equivalence are provider fragments |
| BEGIN/RUN/COMMIT or ROLLBACK | existing F-1601 transaction model is a substantive inherited hit; new work targets final record state, not another no-op transaction theorem |

B4 small-chunk framing is a candidate for root adjudication. Do not open/count a
new issue here. NOOP direction/version remains unassessed until primary Bolt4.4
protocol and actual source are checked; n0 is retained as as-built only until
valid command domain is settled. No socket/listener/database/security probe.
