# result decoders

One stored node value through the result decoders and four readers: typed reads (property, WITH of a property, RETURN coalesce) round-trip every kind under both IRIS drivers; a WITH coalesce column answers a stored number as text (bug-cyp-155); a CASE column answers booleans, lists and maps as text and, with IRIS driver 5.4.1, numbers as text (bug-cyp-156); a comparison column answers booleans or null; an unbound OPTIONAL node answers labels '[]' at Python and HTTP (bug-plt-135)

Evidence status: active. Variant: as-built bounded transcription.

Verified and errors count obligations reported by the verifier. A control is judged against its named expected failure. Native observations have their recorded scope.

[Formal source](result_decoders.rs)

[Formal claims, product bindings and limitations](NOTES.md)

[Premises](NOTES.md)

[Product and declaration crosswalk](../../crosswalk/decision-links.tsv)
