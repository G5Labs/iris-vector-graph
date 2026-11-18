# query.native.route (review-1 fork A)
Independent enumeration ~17: lead route-to-faster; recheck 1000; drift-sooner (=bullet 4); shadow bypass; native warm+2 timings; small_ms stop; SQL warm + alternate to 5; margin near-tie; 4x slowest ends on native; only held advances; threshold resets -> native next; SQL failure permanent; drift 50/20/2x; recheck-disable; drift-disable; eviction new trial; new engine new trial; WA current behaviour.
Split: o13 merges recheck-disable (proved, route_recheck.rs:39-42) with drift-disable (unmodeled) -> partial masks a full half; o14 merges new-engine (definition native_admission.rs:149) with eviction (absent). Minor under-splits.
Exclusions x01 (owner o12 carries drift), x02 cross-ref, x03 undecided "yes": agree.
Grades: 15/15 agree. o03 full narrowed: native_admission.rs:477-482 requires native answers; o09 full/full route_recheck.rs:43-46; o10 full narrowed :29-34; o11 full/full :47-50 (product native_route.py:110 failed guard precedes recheck and drift: premise true).
Fidelity: native_route.py:57-123 vs route_recheck.rs:7-28 match (next_path, _held_run guard, recheck falsy 0, _decide via sql_failed). query.py:2063-2082 shadow skips route consult and record, matches exec_parsed.
o15 absent: platform.rs:858 ApiSample is an enum doc label for the write path only; agree absent.
