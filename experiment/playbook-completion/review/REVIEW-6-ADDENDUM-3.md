# Independent review 6, addendum 3: `a7975f31` (A2-01..A2-08 fixes, lock-hold logging)

Scope: `git show a7975f31` read with grep/diff only; the six named checks run on the working tree (HEAD = `a7975f31`,
plus other sessions' uncommitted STATUS/PROOF-DEBT/QUEUE edits and 23 untracked evidence runs) and, where git is not
needed, on a clean `git archive a7975f31` extract in /tmp. No IRIS, Verus or cargo; nothing committed or stashed.

## Decision

**A2-01..A2-08 are met in substance.** I found each fix in the diff:
- DISCHARGES `module:13`/`:17` are finding/inspected, with no "unreached" text left;
- F-C1750 `intended` rests on `iris_sql_store.py:1333-1338` and INV-stmt, with ADMIN_GUIDE/R206 kept as context only;
- the E-1 qualifier is in place;
- ENV2-4 is in `premise_map.py`'s MAP;
- STATUS cites `ws-check-r6`;
- PRIVILEGE.md has the new AUDITB window section.

One gate claim in the response is not true of the commit as committed (A3-01).

Check results:

| Check | Working tree | Clean extract |
|---|---|---|
| `hygiene_check.py --self-test` | pass | pass |
| `check_premise_map.py` | pass | n/a (needs git) |
| `check_discharges.py` | pass | n/a (needs git) |
| `build_matrix.py --check` | **FAIL (STALE)** | **FAIL (STALE)** |
| `status_numbers.py --check` | pass | pass |
| `check-product-scope.sh` | pass | not run |

`tools/locks.sh` keeps the lock semantics:
- `flock -w $LOCK_WAIT_SECONDS`, default 10800;
- the command's exit code passed through;
- a timeout (`-E 75` with no `acquired` record) exits 1.

## Items

1. **A3-01 (S3): the committed matrix counts runs that are not in the commit.**
   - `matrix/obligations.json:38544` records `"registry_runs": 1566`, but `a7975f31` contains 1551 files in
     `evidence/runs/`.
   - The 15 extra runs are the untracked `lockplans-*` runs (written 01:06 UTC), which were present when the matrix was
     rebuilt before the 02:01 commit. `build_matrix.py:153`/`:614` count `evidence/runs/*.json` from disk.
   - On a clean extract, rebuilding differs from the committed file **only** in `registry_runs` (1551). So
     `build_matrix.py --check` fails on a fresh checkout of `a7975f31`, and on today's working tree (1574 runs).
   - This contradicts the response's "build_matrix --check ... pass" (`review/RESPONSE-6-ADDENDUM-2.md:19-20`).
   - Fix: rebuild from a tree without untracked runs, or commit the lockplans runs. Better: count only tracked runs
     (`git ls-files`) so the check is reproducible.
2. **A3-02 (S4): one unqualified "E-1 proved" remains.**
   - `proofs-env2/PROOFS.md:15` (the summary) still says "(E-1 proved, P-M2 proved in part)". A2-04 asked for the
     qualifier "wherever E-1 is called proved".
   - Fix: add "in the specification" and point to section 3 (`:78-79`).
3. **A3-03 (S4): module 17's reason does not depend on whether the cell closes.**
   - In `writesets/tools/build_discharges.py:721-725`, the module-17 text always ends with "Verification cell closes;
     product obligation fails (...)". `closes` (`:733`) can still be false.
   - If a module-17 cell reopens, DISCHARGES would show `open/open` with a "closes" reason. Module 13 (`:694-704`)
     handles this case correctly.
   - Fix: append the clause only when `closes`.
4. **A3-04 (S4): the response cites the wrong line range.** `review/RESPONSE-6-ADDENDUM-2.md:11` cites
   `schema.py:2822-2830`. The finding and the review use `:2828-2830`. The response text needs the correction; the
   finding is correct.
5. **A3-05 (S4): locks.sh edge cases (semantics otherwise kept).**
   - **Stopping by pid** (`tools/locks.sh:37-45`): the script no longer `exec`s into flock. Killing the locks.sh pid
     leaves flock and the command holding the lock, with no `released` record. The header correctly says to stop the
     holder by the `acquired` pid; H2 only flags this once that pid is gone.
   - **Timeout vs exit 75** (`:40`): the script tells a timeout from a command that exits 75 by grepping for the
     `acquired` record. `locks_rec.py:29-30` swallows write errors, so if that record failed to write, a command exit
     of 75 would be reported as a timeout (exit 1).
   - **New exit code** (`:30-33`): the disk-floor refusal (exit 3) is new caller-visible behaviour.
