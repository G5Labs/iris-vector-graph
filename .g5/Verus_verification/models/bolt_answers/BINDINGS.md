# bolt answers

One answer through the query pipeline to the Neo4j driver: Bolt agrees 4.4 and 5.0-5.4 and refuses other offers; integers use the smallest PackStream width and a value past int64 breaks the session (bug-plt-125); every RUN failure except the read-only and key gates is a SyntaxError (bug-plt-124); node ids are 31 bits of a salted hash, so two nodes can reach the driver as one (bug-plt-122); relationship endpoints follow column order (bug-plt-123); whole-node properties over 200 characters are cut (bug-plt-121); only the long-list error is retried, and never a write; list parameters depend on the IRIS driver (bug-cyp-125) and a parameter slice answers [] on 5.4.1 (bug-cyp-144); a string literal or parameter equals a stored number it spells (bug-cyp-145)

Evidence status: active. Variant: as-built bounded transcription.

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

[Formal source](bolt_answers.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)
