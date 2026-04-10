# Support Plan Redesign

## Background

`support_plan_agent` was introduced to test a relation-aware alternative to direct LLM-to-SQL generation on HDR-Bench. The core idea is sound:

- retrieve before query
- separate surface query understanding from latent support reasoning
- represent support/evidence relations explicitly rather than hoping the model writes the right SQL in one shot

The current implementation already has the right ingredients:

- `ObservableSketch` for surface query structure
- `ObligationSketch` for latent answerability requirements
- `WorkspaceCatalog` for profiling sources and join edges
- a planner/compiler pipeline instead of direct generation

However, the system is still underperforming because it does not yet turn these ingredients into a single answerability-oriented solver.

## Current System

### Observable Layer

- Extracts output slots, explicit filters, time hints, aggregation/order hints.
- Good abstraction for surface semantics.

### Obligation Layer

- Infers `support_relation`, `aggregation_support`, `filter_transfer`, `multihop`, `value_alignment`.
- Good abstraction for latent requirements.
- Currently behaves more like a mode switch than a real constraint layer.

### Workspace Catalog Layer

- Profiles columns and sources.
- Builds source graph using overlap-driven join edges.
- Useful for retrieval, but still mostly a surface graph.

### Planning Layer

- Generates local candidates for output/filter/support/measure.
- Compiles the best candidate to SQL.
- Uses rerank heuristics, but not yet a full unified solver.

## Confirmed Problem Classes

### 1. FilterJoin is not first-class

Current behavior is still too close to:

1. choose output
2. attach filter
3. try to patch in a path later

This means the system often fails to generate the right `output + filter + path` family in the first place.

### 2. AggregationJoin is not first-class

Especially for:

- `COUNT(*)`
- `most / least`
- `top-k aggregation`

the system still guesses support, measure, and anchor independently instead of generating a coherent aggregation plan family.

### 3. The rerank is not yet a real solver

The current rerank can suppress some obviously bad plans, but it still does not reliably elevate the correct plan.

Observed symptom:

- some nonempty wrong answers turn into empty failures
- but correct answers do not appear often enough

### 4. L2 adds a new output alignment problem

Recall analysis shows:

- `L1` still has high output recall
- `L2` suffers a major drop in output recall

So `L2` is not only “harder planning”; it also introduces output latent alignment failure.

## Methodology Reframe

The redesign should not be understood as “more heuristics for FilterJoin/AggregationJoin”. The more accurate frame is:

> A query should be solved by selecting an answerable subgraph over the workspace graph under explicit constraints.

### Multi-layer Graph View

The intended conceptual graph is:

- instance nodes
- attribute nodes
- column nodes
- source/table nodes
- operation nodes
- relation/constraint nodes

The current system already approximates:

- operation nodes via `ObservableSketch`
- relation hints via `ObligationSketch`
- source/column graph via `WorkspaceCatalog`

What it lacks:

- a sufficiently explicit attribute layer
- query-family candidate generation
- a unified answerability solver over those candidates

## Good Existing Design Choices

- `observable` / `obligation` separation
- retrieval-before-query
- support/evidence perspective
- explicit planning pipeline rather than one-shot SQL generation
- diagnostic tooling:
  - recall audit
  - controls
  - top-candidate analysis
  - mini regression

## Bad Existing Design Choices

- jumping too quickly from column labels to local binding decisions
- obligation acting mostly as a switch
- component-wise candidate choice followed by late stitching
- compiler taking too much burden for semantic recovery
- no explicit query family for `FilterJoin`
- no explicit query family for `AggregationJoin`

## Execution Order

### Phase 0: Freeze and Document

- initialize git
- create `.gitignore`
- freeze current baseline
- tag `baseline-pre-family-refactor`
- create worklog and redesign docs

### Phase 1: FilterJoin Family

- make `FilterJoin` a first-class family
- represent:
  - output bindings
  - filter bindings
  - filter path
- status:
  - partially implemented
  - `SupportPlan` now carries explicit family identity and filter paths
  - planner generates explicit `filter_join` candidates
  - representative diagnostics show the correct `FilterJoin` family can now enter the top candidate set
  - remaining gap: the correct `FilterJoin` plan is not yet consistently ranked first

### Phase 2: AggregationJoin Family

- make `AggregationJoin` a first-class family
- explicitly represent:
  - evidence/support source
  - anchor path
  - measure binding
  - aggregation unit
- handle `COUNT(*)` separately
- current status:
  - family identity is now explicit in top-candidate diagnostics
  - `count_star_support` has been introduced as a first-class candidate family
  - `aggregation_join` and `direct_aggregation` are now distinct plan kinds
  - top aggregation candidates still do not convert to pass improvements reliably
  - this indicates the remaining bottleneck is now more solver strength than family visibility

### Phase 3: Strong Joint Solver

- family-internal unified scoring
- family-to-family best-plan comparison
- stronger shape sanity
- current status:
  - a first unified scoring layer exists
  - family-best competition skeleton now exists
  - top-1 family selection now looks structurally more correct on representative cases
  - but it still behaves more like a bad-plan suppressor than a strong correct-plan selector
  - next step is to make the solver family-aware in a stricter sense, especially for:
    - hard invalidation
    - family-internal semantic completeness
    - aggregation ranking

## Current Stage Read

The redesign has already produced a meaningful internal improvement:

- correct `FilterJoin` / `AggregationJoin` families now appear and can rank first

But the system is not yet showing strong end-to-end gains because:

- the selected top-1 family plan is still often semantically incomplete
- hard invalidation is not yet strong enough
- family-internal consistency is not yet strong enough

So the current state should be understood as:

> The model is now better at choosing the right type of plan, but not yet reliably better at choosing the right concrete plan inside that type.

## When Visible Gains Should Appear

Visible gains should be expected in three layers:

### 1. Immediate internal gains

- top-candidate family correctness
- explicit `count_star_support` / `aggregation_join` / `filter_join`
- better diagnostic decomposition of errors

This layer is already visible.

### 2. Early local gains

Expected after the next solver-strengthening pass:

- `new_only_pass` appears on smoke/minireg
- `avg_score_delta` becomes positive
- `empty_fail_ratio` no longer rises as `nonempty_fail_ratio` falls

### 3. Benchmark-visible gains

Only after local gains stabilize should we expect:

- positive deltas on `run_l012_support_compare.py`
- then positive movement on full `L1/L2`
- then only after that, meaningful work on `L2` output alignment

So benchmark-visible gains are not expected from family introduction alone; they should appear only after family-aware solver strengthening starts to turn the correct family into the correct top-1 plan.

## Current Solver Focus

The next strengthening pass is no longer about introducing new families. It is about
making the solver prefer structurally complete plans over hollow plans inside the
already-correct family.

The current implementation is moving toward three generic solver behaviors:

- classify join paths by semantics rather than by existence alone
  - `key_path`
  - `fact_to_dimension_path`
  - `attribute_echo_path`
  - `fallback_name_match_path`
- track `semantic_gap_count` on each plan
- sort plans by:
  - hard invalidation
  - semantic completeness
  - number of semantic gaps
  - total score

This is intended to improve generalization because the rules are defined only over:

- `ObservableSketch`
- `ObligationSketch`
- `WorkspaceCatalog`
- `SupportPlan` family metadata

and not over any seed-level identifiers.

The first concrete effect of this pass is already visible on a representative
`FilterJoin` case:

- `spider__apartment_rentals__01238` `l1`
- after tightening path representation and penalizing multi-hop paths that route
  through projected output columns, the top-1 candidate becomes a true pass

At the same time, a light `l1/l2` stratified smoke run remains mixed, which is
consistent with the current diagnosis:

- family-heavy cases are starting to benefit from better solver structure
- simple duplicated-schema output selection still needs a later output-side calibration pass

## Current Stabilization Result

The bounded direct-order stabilization pass has now produced a small but credible
benchmark-visible gain without introducing any new families:

- `spider__book_2__00224` (`l1/l2`) now grounds ordering through an explicit
  cross-source `order_binding + order_join_path`
- both `stride=20` and `stride=10` `l1/l2` stratified runs are net positive:
  - `l1`: `+1`
  - `l2`: `0`

This means the current redesign has crossed an important threshold:

- family-aware structure is no longer only improving interpretability
- it is now capable of producing modest but real regression-set gains

At the same time, the remaining hard cases are still dominated by:

- aggregation support grounding
- key-like pseudo-measure selection
- deeper representation issues on `L2`

So the current architecture still appears useful for bounded gains, but the
long-term structural concerns remain unchanged.

### Phase 4: L2 Output Alignment

- strengthen output binding scoring only after family + solver stabilize

### Phase 5: Obligation Constraint Upgrade

- move obligation from switch-like behavior to family trigger + plan constraint

## Validation Strategy

### Fixed Regression Assets

- `smoke_set`
- `l012_stratified_set`
- `full_eval`

### Fixed Diagnostics

- `evaluation/analyze_support_plan_recall.py`
- `evaluation/analyze_support_plan_controls.py`
- `evaluation/analyze_support_plan_top_candidates.py`
- `evaluation/analyze_support_plan_minireg.py`

### Primary Metrics

- pass rate
- empty fail ratio
- nonempty fail ratio
- motif-level pass rate
- top-candidate family correctness

### Success Criterion For This Refactor

Not “large score jump immediately”, but:

- correct family starts appearing in candidates
- wrong plans are suppressed and replaced by plausible alternatives
- `FilterJoin` and `AggregationJoin` stop depending on accidental local stitching

## Analysis Artifact Index

- `outputs/analysis/support_plan_recall_v1/support_plan_recall_summary.json`
- `outputs/support_plan_l012_reval/compare_l012_summary.json`
- `outputs/analysis/top_candidates_apartment_l1.json`
- `outputs/analysis/top_candidates_apartment_l2.json`
- `outputs/analysis/top_candidates_assets_agg_l2.json`
- `outputs/analysis/top_candidates_egov_agg_l1.json`
- `outputs/analysis/minireg_support_compare_l1.json`
- `outputs/analysis/minireg_support_compare_l2.json`
- `outputs/latent_edge_protocol_v1/latent_edge_summary.md`
- `outputs/autoresearch_graph_transition_summary_v1.md`

## Open Questions

- How much of `L1` is still candidate-family incompleteness vs solver weakness?
- How much of `L2` can be recovered by better output alignment once family generation is fixed?
- When does obligation need to become a hard constraint instead of a soft score?
- When is critique reliable enough to justify a repair loop?
