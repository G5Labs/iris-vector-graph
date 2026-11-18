# algorithms.op.paths.weighted (review-1 fork B)
Independent enumeration: 25 (lead 2; b1 2; b2 2; b3 5; b4 3; b5 2; b6 2; b7 4; b8 1; b9 2) vs recorded 19; exclusions 2 (open q-iter-007, WA) agree.
Merges: o01 (min-cost vs no-row), o02, o03, o04 (cost cap vs hop cap), o06 (public refuse vs native unbounded: different entry points/outcomes), o08 (public refuse vs native no path; graded partial because one half modelled).
Grades: full rows o01,o02,o04,o05,o07,o09,o14,o17 agree (narrowed). o18 full -> partial (minor): 'omitted' case is decided in Python carrier (engine.py:1265-1270 None -> '[]'), model only has native Set (weighted_paths.rs:20-23); weighted_fraction NOTES:99 says no formal raw-to-Config carrier theorem.
Systematic: 'procedure rows' observation on o01/o04/o05/o07/o09 reached via observed-only Python carrier (weighted_fraction NOTES:99); accepted since Python forwards verbatim and '{}' -> no row, but strictly this is checklist c.
o01 cites only JSON route; YIELD totalCost route (DijkstraCost, weighted_cost, needs mirrored premise) not cited (minor, b).
Fidelity: TraversalPaths.cls:300-341 matches step/relax/effective (weighted_paths.rs:18-58); tBound=(+maxHops>0) so native negative=unbounded (o06 native half) not representable with bound:nat.
