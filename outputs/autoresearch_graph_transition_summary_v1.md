# Graph-First Transition Summary

## Goal

Evaluate whether moving `AggregationJoin` from a family-specific runtime object to a more explicit graph-based abstraction improves method identity and remains viable on the frozen benchmark root:

- `outputs/hdrbench_full150_v1`

## What changed

The current implementation now includes:

- explicit `ObligationGraph`
- `ObligationNode`
- `ObligationEdge`
- graph-backed `AggregationJoin` sketch output
- graph-backed obligation status in traces
- `obligation_edge` probe path for aggregation support

This transition was intended to move the system away from flat slot filling and closer to a constraint-graph resolver.

## Key runs

### Representative AggregationJoin control on frozen bench

- Stable:
  - `outputs/graph_full150_03144_stable_v1/report_contrastive_agent.json`
- Graph/object:
  - `outputs/graph_full150_03144_object_v1/report_contrastive_agent.json`
- Graph/object + no repair:
  - `outputs/graph_full150_03144_object_norepair_v1/report_contrastive_agent.json`

Result on `spider__assets_maintenance__03144 / l1.full / A,B,C`:

- `stable`: `0/3`
- `graph object`: `1/3`
- `graph object + no repair`: `1/3`

Interpretation:

- the graph-based object does activate and change search behavior
- but on the frozen benchmark root the gain is much weaker than on the earlier dev root
- the current graph path is therefore a stronger abstraction, but not yet a stronger family-level method

### Secondary AggregationJoin-like check

- `outputs/graph_full150_00826_object_v1/report_contrastive_agent.json`

Result on `spider__chinook_1__00826 / l1.full / A,B,C`:

- `graph object`: `1/3`

Interpretation:

- the object is triggered on all variants
- `obligation_edge` appears early
- but support-side correctness still does not reliably propagate to output-side anchor selection

## Most important positive result

The strongest success of this transition is not benchmark score, but method identity:

- the runtime trace now contains an explicit `ObligationGraph`
- edge-level status is visible in `obligation_status`
- hard cases can now be described in terms of edge satisfaction rather than family-specific patches

This means the system is closer to a genuine system abstraction.

## Most important negative result

The frozen benchmark root reveals that:

- graph abstraction alone does not yet deliver stable family-level gains
- `03144` no longer behaves as the easy canonical win it did on the earlier dev root
- this is strong evidence that the project must now prioritize:
  - family protocol
  - design/holdout discipline
  - method audit
  - principle-driven improvements rather than new case-by-case tuning

## Current best interpretation

The graph-first transition is:

- a good **abstraction upgrade**
- but not yet a complete **performance upgrade**

It successfully protects the project from collapsing into patch soup, but it also exposes that the next gains must come from better family-level propagation and constraint resolution rather than additional local fixes.

## Recommended next step

Do not resume case-by-case patching.

Instead:

1. Freeze this graph-first transition as the new abstraction baseline.
2. Use the frozen benchmark root plus `AggregationJoin` family protocol to define:
   - design set
   - holdout set
   - acceptance metrics
3. Evaluate further changes only through that protocol.
