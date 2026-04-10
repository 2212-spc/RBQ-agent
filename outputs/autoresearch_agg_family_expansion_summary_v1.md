# Aggregation Family Expansion Summary

## Goal

Move from single-case `AggregationJoin` evidence on `spider__assets_maintenance__03144` toward a small family-level check with additional Spider-derived seeds.

## New Candidate Registry

- Registry: `outputs/agg_family_seed_registry_v2.jsonl`
- Initially screened from Spider train set using the same validity logic as phase0:
  - explicit join
  - valid key types
  - SQLite/DuckDB execution
  - non-empty result

## Build Outcome

- Built benchmark root: `outputs/hdrbench_agg_family_v2`
- Requested candidates: `5`
- Successfully built:
  - `spider__chinook_1__00826`
  - `spider__inn_1__02601`
- Failed candidates exposed benchmark/build compatibility issues rather than method issues:
  - `spider__driving_school__06688`
  - `spider__insurance_fnol__00909`
  - `spider__journal_committee__00663`

## Main Control Already Frozen

- Main single-case control table:
  - `outputs/autoresearch_controls_03144_l1_ABC_summary_v1.md`

Key result:

- On `03144 / l1.full / A,B,C`
  - `stable`: `2/3`
  - `skeleton proxy`: `2/3`
  - `aggregation object`: `3/3`
  - `aggregation object + no repair`: `3/3`

Interpretation:

- The explicit `AggregationJoin` object is now a real system object.
- Its gain is no longer primarily explained by compile-time repair.
- Early support-aware probing now enters the decision path on hard variants.

## Family Expansion Check

Runs:

- Stable:
  - `outputs/autoresearch_aggfamily_v2_stable_l1_ABC_v2/report_contrastive_agent.json`
- Aggregation object:
  - `outputs/autoresearch_aggfamily_v2_object_l1_ABC_v2/report_contrastive_agent.json`

### Stable

- `l1.full` pass rate on the two new seeds: `0/6`

### Aggregation Object

- `l1.full` pass rate on the two new seeds: `1/6`

Breakdown:

- `spider__chinook_1__00826`
  - object is triggered on all variants
  - one variant passes
  - remaining failures expose a generalized `output-side key propagation` problem
  - the system chooses the correct support relation (`ALBUM.ArtistId`) but still anchors output on a schema-similar distractor `name` source

- `spider__inn_1__02601`
  - object is triggered on all variants
  - current `support_hint` inference is weak because the query names the output attribute (`decor`) rather than the support relation (`Reservations`)
  - failures expose a generalized `support relation inference` gap

## What This Means

This expansion does **not yet** establish family-level controlled success for `AggregationJoin`.

What it does establish is:

1. The `AggregationJoin` object is not limited to one hand-curated case.
2. It can be triggered and traced on additional Spider-derived seeds.
3. The next bottlenecks are now clearer and more general:
   - output-side key propagation
   - support relation inference when the query lexical cue refers to the output attribute rather than the support relation

## Current Best Interpretation

- `03144` provides strong single-case mechanism evidence.
- The small family expansion shows partial transfer, but not yet repeatable family-level gains.
- The method has progressed from:
  - "object exists"
  - to "object changes early search on the representative case"
  - and now to "object reveals two generalized next bottlenecks on new seeds"

## Recommended Next Step

Do not expand to many more seeds yet.

The next highest-value method step is:

- make `AggregationJoin` propagate support evidence into output-side key selection more reliably
- or explicitly model an `output-side join key` obligation

Only after that should the aggregation family be re-evaluated on this small expansion set.
