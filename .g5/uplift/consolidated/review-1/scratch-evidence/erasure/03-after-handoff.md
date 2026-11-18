# Step 5 (after reading HANDOFF, MASTER-INTEGRATION, bugs, open questions, crosswalk)
- HANDOFF s9 discloses: one-call atomicity is a premise; _delete_in_scope reifier cleanup not modelled; TAgg not compared for
  list erases. Disclosure does not change rule-2 grading (full requires the formal rule to distinguish; premise/definition => partial).
- Cross-graph reach of delete_node's reifier cleanup (_graphs_holding -> every graph) NOT in any finding; bug-str-014 is the
  analogous delete_reification issue. Crosswalk binds _delete_in_scope to eraser_of ("delegates") and delete_node "is EraseNodeIds".
- F-1502 is High, yet census keeps the reifier residue outside-statement for erasure.scope#o02.
- bug-str-118: reachable (InvalidateDerived). bug-str-119: reachable on a joined connection; authors observed DDL rolled back.
  bug-str-120: conditional on a post-commit DROP failure (not established). bug-srch-117: reachable (EraseAll names no index global).
- GraphQL api/gql/resolvers/mutation.py raw delete is dead code (live route -> examples resolver -> engine.delete_node): dismissed.
Final: 6 census disagreements of 58; sign-off not clean (material: R1-ER-01, -02, -05).
