# Non-receipt development attempts

The first ledger_apply/binding.py execution (before fixing its fixture) raised:

```
TypeError: _CommitWireResult.__init__() missing 5 required positional arguments:
'revision_id', 'replayed', 'stmt_ids', 'error_code', and 'reason'
```

It occurred while constructing the substituted server failure response, before
that error-mapping case ran. The successful property-reader loops had executed,
but no binding verdict was recorded and no credit was taken from that attempt.
The corrected fixture supplies all fields; the committed AGREES receipt is the
substantive result. All unsuccessful proof/control runs have their own retained
receipts and copied raw logs; see each model NOTES for interpretation.

The first git diff whitespace check refused to commit because new TSV rows ended
in empty tab-separated fields; the fields were filled, then corrected to the
actual canonical page paths in the sealing commit. No product file changed.
