# 03144 Aggregation Controls

| Mode | l1.full | Explicit AggregationJoin | Early agg probe | Early wrong-support fail | Repair used | Failed variants |
|---|---:|---|---|---|---|---|
| stable | 0.667 | no | - | - | - | A |
| skeleton_proxy | 0.667 | no | - | - | - | A |
| aggregation_object | 1.000 | yes | B, C | B | - | - |
| aggregation_object_no_repair | 1.000 | yes | B, C | B | - | - |

## Per Variant

### stable

- `A`: pass=`False`, attribution=`DISCOVERY_FAIL`, first_probe=`slot_coverage`, repair_used=`False`
- `B`: pass=`True`, attribution=`PASS`, first_probe=`slot_coverage`, repair_used=`False`
- `C`: pass=`True`, attribution=`PASS`, first_probe=`slot_coverage`, repair_used=`False`

### skeleton_proxy

- `A`: pass=`False`, attribution=`DISCOVERY_FAIL`, first_probe=`slot_coverage`, repair_used=`False`
- `B`: pass=`True`, attribution=`PASS`, first_probe=`slot_coverage`, repair_used=`False`
- `C`: pass=`True`, attribution=`PASS`, first_probe=`slot_coverage`, repair_used=`False`

### aggregation_object

- `A`: pass=`True`, attribution=`PASS`, first_probe=`slot_coverage`, repair_used=`False`
- `B`: pass=`True`, attribution=`PASS`, first_probe=`aggregation_support`, repair_used=`False`
- `C`: pass=`True`, attribution=`PASS`, first_probe=`aggregation_support`, repair_used=`False`

### aggregation_object_no_repair

- `A`: pass=`True`, attribution=`PASS`, first_probe=`slot_coverage`, repair_used=`False`
- `B`: pass=`True`, attribution=`PASS`, first_probe=`aggregation_support`, repair_used=`False`
- `C`: pass=`True`, attribution=`PASS`, first_probe=`aggregation_support`, repair_used=`False`
