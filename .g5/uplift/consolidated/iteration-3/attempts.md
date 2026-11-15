# Retained unsuccessful or limited work

- The first direct history_diff compile used a Rust matches! pattern on indexed
  Seq<Op> values and failed to type-check. It gave no proof verdict. It was
  replaced with a specification helper; subsequent runner receipts/logs are kept.
- The snapshot extension first used executable Option.map in a spec function;
  its ERROR receipt/raw log remains under results/history_diff/20261115T065018Z-prove.
  Pattern matching fixed the mode error; no assertion was weakened.
- The first vector proof passed nat indices to Seq.take; ERROR receipt/raw log
  remains under results/vector_threshold/20261115T065413Z-prove. Explicit int
  casts fixed the type error.
- The PageRank recursive producer added a termination obligation, making the
  initially expected8 count actual9 with zero logical errors. The UNEXPECTED
  receipt remains under results/pagerank_admission/20261115T065510Z-prove; its
  manifest now expects9 and the final proof/count agrees.
- Initial consolidated checking found new ontology metadata out of body order
  and missing finding backlinks. Reordering metadata and adding the backlinks
  fixed those structural errors; the final gate reports zero writing warnings.
- The inherited simple bug-led-101 inference was withdrawn after actual producer
  inspection, not repaired by weakening a test. Its original fixture/receipt
  remain immutable; the new stronger history carries the real snapshot shape.
- No IRIS/container setup was attempted. ObjectScript/transaction correspondence
  is inspected or inherited, never a new live observation. No security finding
  was reproduced, no delegation or publication occurred.
- Access timing/filename-discovery disclosure is in inputs.json. Independent
  evaluator material contents were not read and no hidden case was self-graded.
