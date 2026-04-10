# Support Plan Worklog

## 2026-03-30

### Context

- We evaluated `support_plan_agent` across `L0/L1/L2` and compared it with `llm_code_agent`.
- We also added analysis tools for:
  - motif breakdown
  - recall audit
  - controls
  - top-candidate analysis
  - mini regression

### Key Findings So Far

- `L1`:
  - candidates often enter the pool
  - but the system still fails to jointly choose a consistent answer plan
- `L2`:
  - output alignment degrades sharply
  - and the pre-existing planning weaknesses remain
- `FilterJoin`:
  - still behaves like “output plan + attached filter” too often
- `AggregationJoin`:
  - still lacks an explicit family, especially for `COUNT(*) / most / least / top-k`

### Representative Evidence

- `outputs/analysis/support_plan_recall_v1/support_plan_recall_summary.json`
- `outputs/support_plan_l012_reval/compare_l012_summary.json`
- `outputs/analysis/top_candidates_apartment_l1.json`
- `outputs/analysis/top_candidates_apartment_l2.json`
- `outputs/analysis/top_candidates_assets_agg_l2.json`
- `outputs/analysis/top_candidates_egov_agg_l1.json`
- `outputs/analysis/minireg_support_compare_l1.json`
- `outputs/analysis/minireg_support_compare_l2.json`

### Current Diagnosis

The system is no longer best described as “failing to find relevant tables”. A better description is:

- it often retrieves enough relevant pieces
- but it still does not reliably choose a coherent answerability-consistent plan
- in `L2`, output latent alignment additionally collapses

### Immediate Development Direction

1. Freeze the baseline and start versioned development.
2. Promote `FilterJoin` to a first-class family.
3. Promote `AggregationJoin` to a first-class family.
4. Strengthen the joint solver so it becomes a real plan selector, not just a bad-plan suppressor.
5. Only after that, revisit `L2` output alignment.

### Next Update Checklist

- record git bootstrap status
- record branch + tag names
- record first `FilterJoin family` implementation delta
- record stratified-set results after family refactor

### Repository State

- Initialized local git repository at `hdrbench_mvp/`
- Created baseline commit:
  - `Bootstrap support plan redesign baseline`
- Created tag:
  - `baseline-pre-family-refactor`
- Created development branch:
  - `feature/support-plan-family-solver-v1`

### Phase 1 Progress: FilterJoin Family Skeleton

- Promoted `SupportPlan` toward explicit family representation:
  - added `plan_kind`
  - added `filter_join_paths`
- Updated planner so filter bindings are no longer only a late attachment:
  - added filter-binding assignment generation
  - added explicit `FilterJoin` candidate construction
  - family-aware notes and diagnostics now record the chosen family
- Updated IR / compiler to consume explicit filter join paths
- Added tests for:
  - `filter_join` family presence
  - aggregation family presence
  - family-aware search behavior

### Phase 1 Evidence

- Representative `FilterJoin` top-candidate analysis:
  - `outputs/analysis/top_candidates_apartment_l1_phase1.json`
  - `outputs/analysis/top_candidates_apartment_l2_phase1.json`
- Key finding:
  - for `spider__apartment_rentals__01238` the candidate count increased from a tiny pool to a broader `FilterJoin` family pool
  - a fully correct `FilterJoin` candidate now appears in top candidates for `l1`, but not yet at rank 1
- Interpretation:
  - Phase 1 is starting to fix candidate-family incompleteness
  - the main remaining issue is solver strength, not pure candidate absence

### Phase 2 Signal Already Visible

- Representative `AggregationJoin` top-candidate analysis:
  - `outputs/analysis/top_candidates_assets_agg_l2_phase1.json`
- Key finding:
  - candidates are now explicitly labelled `aggregation_join`
  - but top plans still frequently have weak or missing measure semantics
- Interpretation:
  - aggregation family exists as a scaffold
  - but `COUNT(*) / top-k / measure-anchor` logic still needs a dedicated Phase 2 pass

### Phase 2 Progress: AggregationJoin / Count-Star Family Skeleton

- Extended `SupportPlan` with explicit aggregation-family metadata:
  - `evidence_source_ids`
  - `aggregation_unit_kind`
  - `aggregation_anchor_source_id`
  - `aggregation_mode`
  - `ranking_target_kind`
- Upgraded the planner so aggregation candidates are explicitly named:
  - `direct_aggregation`
  - `aggregation_join`
  - `count_star_support`
- Added family-best competition skeleton so each family can compete via its best plan, rather than letting one family flood the full candidate list.
- Strengthened aggregation-specific scoring:
  - `count_star_support` gets explicit consistency checks
  - same-source fake support is penalized more strongly
  - anchor presence now matters directly for aggregation

### Phase 2 Evidence

- `outputs/analysis/top_candidates_assets_agg_l2_phase2.json`
- `outputs/analysis/top_candidates_egov_agg_l1_phase2.json`
- `outputs/analysis/minireg_support_compare_phase2_l1.json`
- `outputs/analysis/minireg_support_compare_phase2_l2.json`

### Phase 2 Finding

- The correct aggregation family now appears explicitly in top candidates:
  - `assets_maintenance__03144` now surfaces `count_star_support`
  - `e_government__06324` now surfaces `aggregation_join`
- But end-to-end pass rate on the small regression slices did not yet improve.
- Interpretation:
  - representation is improving
  - solver selection is still too weak to reliably pick the right plan
  - next effort should continue into a stronger family-aware solver rather than retreat to local scorer patches

### Phase 3 Progress: Family-Aware Solver Strengthening

- Introduced an explicit plan-score structure on `SupportPlan`:
  - `family_name`
  - `base_retrieval_score`
  - `output_consistency`
  - `filter_consistency`
  - `aggregation_consistency`
  - `obligation_consistency`
  - `shape_sanity`
  - `hard_invalid`
  - `hard_invalid_reasons`
  - `total`
- Upgraded top-candidate diagnostics so they now expose:
  - `global_rank`
  - `family_rank`
  - `plan_score`
  - `hard_invalid`
  - `hard_invalid_reasons`
- Added family-best competition:
  - each family now competes through its own best candidate instead of flooding the global list
- Added initial hard-gate skeleton for:
  - invalid direct aggregation
  - invalid aggregation without measure
  - invalid same-source count-star support
  - invalid missing filter path

### Phase 3 Evidence

- `outputs/analysis/top_candidates_apartment_l1_phase3.json`
- `outputs/analysis/top_candidates_assets_agg_l2_phase3.json`
- `outputs/analysis/top_candidates_egov_agg_l1_phase3.json`
- `outputs/analysis/minireg_support_compare_phase3_l1.json`
- `outputs/analysis/minireg_support_compare_phase3_l2.json`

### Phase 3 Finding

- The system now consistently places the intended family at global rank 1 for representative hard cases:
  - `filter_join` for `apartment_rentals__01238`
  - `count_star_support` for `assets_maintenance__03144`
  - `aggregation_join` for `e_government__06324`
- This is a real structural gain:
  - the system is no longer mostly choosing the wrong family
- But the chosen top-1 family plan is still often semantically hollow or incomplete.
- So the bottleneck has shifted again:
  - from `family existence`
  - to `family-internal plan quality`

### Current Interpretation

- We have moved from:
  - "correct family often absent"
- to:
  - "correct family present and top-ranked, but not yet executable-correct"
- This means the redesign is working, but visible benchmark gains are not expected yet.
- The next clear target is:
  - strengthen hard invalidation and family-internal semantic consistency so that top-1 is not only the right family, but also the right plan.

### When To Expect Visible Gains

- **Already visible now**
  - top-candidate family correctness
  - clearer separation of `FilterJoin` / `AggregationJoin` behavior
  - better diagnostic observability
- **Next milestone for noticeable local gains**
  - smoke / minireg should start showing:
    - `new_only_pass > 0`
    - or `avg_score_delta > 0` without `empty_fail_ratio` getting worse
- **When to expect benchmark-visible gains**
  - only after the solver begins selecting a semantically complete top-1 plan inside the correct family
  - concretely:
    - `nonempty_fail_ratio` must start dropping on `FilterJoin / AggregationJoin`
    - `run_l012_support_compare.py` should show at least small positive deltas before full-bench reruns are worth doing

### Phase 3b Progress: Semantic Completeness Tightening

- `PlanScore` now tracks `semantic_gap_count`
- plan sorting now prefers:
  - valid plans
  - then semantically complete plans
  - then plans with fewer semantic gaps
  - then higher total score
- path handling is now more semantic:
  - `key_path`
  - `fact_to_dimension_path`
  - `attribute_echo_path`
  - `fallback_name_match_path`
- weak path semantics now affect:
  - `shape_sanity`
  - `hard_invalid`
  - `semantic_complete_reasons`
- `filter_join` completeness now explicitly checks:
  - filter type conflict
  - weak / echo / fallback filter paths
  - weak evidence grain on the filter side
- `aggregation_join` and `count_star_support` completeness now explicitly checks:
  - weak anchor semantics
  - weak evidence grain
  - measure off support source
- diagnostics now expose:
  - `semantic_gap_count`
  - `anchor_semantics`
  - `filter_join_path_semantics`
  - `output_join_semantics`
- mini-reg comparison now exposes `net_pass_delta`

### Phase 3b Intent

- move the solver from "correct family, hollow plan"
- toward "correct family, structurally fuller plan"
- without introducing any seed-level or database-level exceptions

### Phase 3c Evidence

- `outputs/analysis/top_candidates_apartment_l1_phase3c.json`
- `outputs/analysis/top_candidates_assets_agg_l2_phase3c.json`
- `outputs/analysis/top_candidates_egov_agg_l1_phase3c.json`
- `outputs/analysis/phase3c_l12_smoke/compare_l012_summary.json`

### Phase 3c Finding

- fixing path representation and detecting multi-hop paths that leave the output source through a projected output column produced the first concrete plan-selection win:
  - `spider__apartment_rentals__01238` `l1`
  - top-1 is now a passing `filter_join` plan
- aggregation representatives still remain incomplete but diagnostics are now sharper:
  - `assets_maintenance__03144` still shows `support_not_fact_like`
  - `e_government__06324` still shows `measure_is_key_like`
- a light `l1/l2` stratified smoke run (`stride=20`) now shows:
  - `l1`: `+1 / -1` flip balance, net neutral
  - `l2`: `-1` net pass on this tiny slice
- interpretation:
  - semantic-completeness tightening is beginning to turn some representative cases into true passes
  - but direct/simple output-source calibration is still unstable, especially on duplicate-schema `SimpleJoin` cases

### Phase 4 Progress: Order-Aware Direct Solver Stabilization

- kept the family set fixed; no new `family` labels were introduced
- promoted ordering into an explicit plan component:
  - `order_binding`
  - `order_join_path`
- extended fallback observable parsing so explicit ordering phrases can recover:
  - `direction`
  - `target`
  - without incorrectly forcing `LIMIT 1` for plain `descending/ascending order of ...`
- added order-target grounding to search:
  - direct/simple plans can now bind an ordering column on another source
  - cross-source ordering requires an explicit path
  - weak or projection-bridge order paths degrade completeness
- added `ordering_consistency` to `PlanScore`
- upgraded diagnostics to expose:
  - `order_source_id`
  - `order_column`
  - `order_join_path_source_ids`
  - `order_join_path_semantics`
  - `ordering_consistency`

### Phase 4 Evidence

- `outputs/analysis/top_candidates_book2_l1_phase4b.json`
- `outputs/analysis/top_candidates_book2_l2_phase4b.json`
- `outputs/analysis/phase4_l12_smoke/compare_l012_summary.json`
- `outputs/analysis/phase4_l12_stride10/compare_l012_summary.json`

### Phase 4 Finding

- the main `SimpleJoin` ordering regression is fixed:
  - `spider__book_2__00224`
  - `l1` and `l2` top-1 are now true passes
- existing representative wins remain stable:
  - `spider__apartment_rentals__01238 l1` remains a top-1 pass
  - `spider__party_host__02679 l1` remains a pass
- aggregation hard cases remain incomplete, but were not destabilized by this pass
- stratified smoke now shows the first credible net-positive signal:
  - `stride=20`
    - `l1`: `+1`
    - `l2`: `0`
  - `stride=10`
    - `l1`: `+1`
    - `l2`: `0`
- interpretation:
  - bounded direct/order stabilization can convert structural solver gains into benchmark-visible improvement
  - the current `v1.5` line still has some headroom, but gains are now coming from narrower calibration rather than major architectural unlocks

### Phase 5 Progress: LLM Join Overlay Injection

- kept the family set and solver logic unchanged
- did not add search-level fallback branches
- instead repaired the data-flow gap between:
  - `llm_grounding.suggested_joins`
  - graph path search
- implementation:
  - validated LLM join suggestions into run-local overlay `JoinEdge`s
  - injected them directly into `catalog.join_edges`
  - reused the same overlay helper in both:
    - `agent.py`
    - `analyze_support_plan_top_candidates.py`
- safeguards:
  - source / column existence checks
  - self-loop rejection
  - conservative overlap mapping
  - overlay provenance via `edge_id` prefix `llm_overlay__...`

### Phase 5 Evidence

- `outputs/analysis/top_candidates_aircraft_l1_overlayfix.json`
- `outputs/analysis/overlayfix_discovery_l1/report_support_plan_agent.json`
- `outputs/analysis/overlayfix_l12_stride10/compare_l012_summary.json`

### Phase 5 Finding

- the `right-but-rejected grounding` failure mode is real and this fix addresses it:
  - `spider__aircraft__04821 l1` now becomes a true pass
  - top candidate uses a mixed native+overlay 2-hop path through the bridge source
- on the 5-case discovery-like mini set:
  - `aircraft` fixed
  - `inn_1` fixed
  - 3 others unchanged
- on `l1 stride=10`:
  - baseline `4/17`
  - overlayfix `7/17`
  - net `+3`
- on `l2 stride=10`:
  - baseline `2/17`
  - overlayfix `1/17`
  - this matches the prior llmaug run exactly, so overlay did not improve the current L2 bottleneck
- interpretation:
  - overlay injection successfully repairs a real structural gap
  - it helps `L1` where correct grounding exists but graph recall is insufficient
  - it does not solve `L2` cases dominated by wrong-but-confident grounding
