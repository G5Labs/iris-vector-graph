# Reviewer challenge: batch qualifier empty keys

Freeze before this native panel. The independent reviewer found a draft-model
miss, not a product issue: actual batch relationship qualifier maps are copied
to native local keys and enumerated with $Order from empty. Empty keys are
therefore skipped. Direct SetQual still refuses an empty key. This is a
source-informed post-review challenge, not a blind evaluator case.

1. New relationship with {'':'ignored','q':'x'} succeeds; physical qualifier JSON,
   emitted records and public reconstruction contain q:x and no empty key.
2. Existing upsert with {'':'ignored-again','q':'y'} succeeds; it emits only the
   changed q record with prior x and keeps no empty key.
3. Direct set_qualifier with key'' refuses before commit and leaves the head.
4. Node property batches differ: their dynamic iterator calls SetProp for empty
   key, so a new node with {'':'x','k':'y'} refuses and its earlier create is rolled
   back. No node or revision remains. Do not reuse qualifier enumeration for it.

Fresh prefix, actual owned runtime only, no erase/reset/security/source changes.
