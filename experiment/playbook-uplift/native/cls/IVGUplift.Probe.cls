/// Test-only probes for the playbook uplift's live scenarios. Loaded into the dedicated test namespace only;
/// not part of the product. Each method exercises one IRIS behaviour the product relies on, with ObjectScript
/// semantics (the Native API's own lock calls behave differently).
Class IVGUplift.Probe Extends %RegisteredObject
{

/// P-0003: open a transaction, take a lock and release it with a plain "Lock -", as Graph.KG.Ledger.Commit does
/// before its TCOMMIT. Returns $TLevel; the transaction is left open for the caller to end.
ClassMethod LockThenUnlockInTxn(pTag As %String) As %Integer
{
    TSTART
    Lock +^IVGUplift("L", pTag):5
    If '$Test Quit -1
    Lock -^IVGUplift("L", pTag)
    Quit $TLevel
}

/// 1 when this process can take the lock at once (and releases it again), 0 when another process holds it.
ClassMethod CanLock(pTag As %String) As %Integer
{
    Lock +^IVGUplift("L", pTag):0
    If '$Test Quit 0
    Lock -^IVGUplift("L", pTag)
    Quit 1
}

/// 1 when this process can take the ledger head lock at once (and releases it), 0 when another holds it.
ClassMethod CanLockHead() As %Integer
{
    Lock +^IVG.Ledger("head"):0
    If '$Test Quit 0
    Lock -^IVG.Ledger("head")
    Quit 1
}

}
