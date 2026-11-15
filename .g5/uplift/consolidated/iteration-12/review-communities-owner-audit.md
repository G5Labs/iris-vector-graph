# Iteration admission authority review

The old generic algorithms.op bullet overgeneralizes the recovered authority:

> A damping factor outside (0, 1), an iteration count below 1 or an unknown direction raises `ValueError` before anything is read.

The exact original bullet/block and before-edit source hash are preserved in
review-communities-owner-audit.json. USER_GUIDE598–600 places damping and minimum
iterations inside its PPR discussion and explicitly names ppr/CALLivg.ppr,
kg_PAGERANK and gds.pageRank.stream. CHANGELOG41–43 explicitly attributes these
refusals to PageRank and personalized PageRank. The method-specific WCC and CDLP
API entries do not promise that validation. COMMUNITIES164–169 describes WCC's
safety limit including a confirming unchanged round; its CDLP section describes
synchronous rounds/stopping/parity, without a below1 pre-read ValueError promise.

Recommend scoping the damping/iteration clause to PageRank and personalized
PageRank, keeping the existing unknown-direction clause separate and unchanged.
This corrects the ontology reconstruction's attribution from explicit authority;
it does not weaken a valid WCC/CDLP commitment to fit code, resolve a policy, or
establish a new product defect. The specific PageRank/PPR validation intent stays.

Raw source Owner behavior remains separately represented: nonpositive WCC budget
can refuse only after membership enumeration (empty core returns first), while
nonpositive CDLP limit executes zero rounds. Those facts do not by themselves
settle public backend/error behavior. No new zero-call native panel, product/shared
edit, private evaluator access or issue creation was performed by this reviewer.
