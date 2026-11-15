# Iteration9 paired builder ledger

Builder judgments only, purposive source-informed overlapping panel; not independent evaluator grades or population rates. Frozen agent panels precede candidates; root public/provider/PPR neighbors are explicitly source-derived. Published/private grader inputs unchanged/uninspected.

Same19 scheduled decisions on both snapshots. Full source/code/native limits and actual role fragments are in builder-scores.json; intended policy and human approval are separate.

| ID | Decision | Ontology before -> after | Model before -> after |
|---|---|---|---|
| W1 | Cheaper longer route vs expensive direct route, primary JSON integer graph | complete/supported -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| W2 | Hop2 vs unbounded arrival and raw stale queue/minimum-hop dominance | complete/supported -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| W3 | Exact cost cap vs one below, including target-at-cap | complete/supported -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| W4 | Returned parent path/cost/length vs empty-queue no feasible walk | complete/supported -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| W5 | Finite terminal result vs continuing raw stale pops | complete/supported -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| W6 | Public negative hops/empty endpoint refusal vs native admitted boundary | complete/wrong -> complete/supported | partial/unanswered/unanswered -> partial/unanswered/partial |
| W7 | Mode-off callback overwrite vs completed mode-on lowest-key projection | partial/unanswered/partial -> complete/supported | partial/unanswered/unanswered -> partial/unanswered/partial |
| W8 | JSON vs Cost with missing/unequal reverse mirror | partial/unanswered/unanswered -> complete/supported | partial/unanswered/unanswered -> partial/unanswered/partial |
| W9 | Lowest-key weighted graph vs minimum over all keyed edge weights, as built | partial/unanswered/partial -> complete/supported | partial/unanswered/unanswered -> partial/unanswered/partial |
| W10 | Which weighted parallel-edge policy should govern | partial/unanswered/unanswered -> partial/unanswered/unanswered | partial/unanswered/unanswered -> partial/unanswered/unanswered |
| B1 | Default vs small chunks: actual raw boundary and wrong re-encoded cut | partial/unanswered/unanswered -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| B2 | Separate vs coalesced valid fragmented messages and later delivery | partial/unanswered/unanswered -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| B3 | Empty NOOP vs ordinary nonempty body in initialized WebSocket | partial/unanswered/unanswered -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| B4 | WebSocket vs TCP NOOP whole receive-loop contrast | partial/unanswered/unanswered -> complete/supported | partial/unanswered/unanswered -> partial/unanswered/partial |
| B5 | Positive partial PULL vs all remaining and empty second PULL | partial/unanswered/unanswered -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| B6 | COMMIT keeps pending rows vs RESET/ROLLBACK clearing them | partial/unanswered/unanswered -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| B7 | Raw nonempty RUN error/FAILED gate vs empty success/reset recovery | partial/unanswered/unanswered -> complete/supported | partial/unanswered/unanswered -> complete/supported |
| P1 | Default PPR numerical restart/dangling/multiplicity recurrence | complete/supported -> complete/supported | partial/unanswered/unanswered -> partial/unanswered/unanswered |
| P2 | PPR sparse scores to every-node zero-fill reader on a small uncapped stable graph | complete/supported -> complete/supported | partial/unanswered/partial -> partial/unanswered/partial |

The old public nonpositive-hop wording was a complete but wrong answer (W6), not lost coverage. The mode-off lowest-key oracle and all-coalesced framing expectation were actual harness misses, withdrawn and retained rather than counted as product errors. W10 stays unanswered. P1/P2 retain an underserved workflow and inherited row/cache hit; those rows do not get new formal credit from native probes.

{
  "before": {
    "ontology": {
      "complete": 8,
      "scheduled": 19,
      "answered": 10,
      "supported": 7,
      "partial": 2,
      "wrong": 1,
      "unconfirmed": 0,
      "unanswered": 9,
      "supported_over_answered": [
        7,
        10
      ],
      "supported_over_scheduled": [
        7,
        19
      ]
    },
    "model": {
      "complete": 0,
      "scheduled": 19,
      "answered": 1,
      "supported": 0,
      "partial": 1,
      "wrong": 0,
      "unconfirmed": 0,
      "unanswered": 18,
      "supported_over_answered": [
        0,
        1
      ],
      "supported_over_scheduled": [
        0,
        19
      ]
    }
  },
  "after": {
    "ontology": {
      "complete": 18,
      "scheduled": 19,
      "answered": 18,
      "supported": 18,
      "partial": 0,
      "wrong": 0,
      "unconfirmed": 0,
      "unanswered": 1,
      "supported_over_answered": [
        18,
        18
      ],
      "supported_over_scheduled": [
        18,
        19
      ]
    },
    "model": {
      "complete": 11,
      "scheduled": 19,
      "answered": 17,
      "supported": 11,
      "partial": 6,
      "wrong": 0,
      "unconfirmed": 0,
      "unanswered": 2,
      "supported_over_answered": [
        11,
        17
      ],
      "supported_over_scheduled": [
        11,
        19
      ]
    }
  }
}
