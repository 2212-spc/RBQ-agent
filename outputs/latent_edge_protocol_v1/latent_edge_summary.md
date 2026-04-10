# Latent Edge Holdout Extraction

- Bench root: `outputs\hdrbench_full150_v1`
- Auto candidate count: `8`
- Design ids (manual): `spider__assets_maintenance__03144, spider__chinook_1__00826, spider__inn_1__02601`
- Design ids present in bench: `spider__assets_maintenance__03144, spider__chinook_1__00826, spider__inn_1__02601`
- Design ids overlapping auto candidates: `spider__inn_1__02601`
- Holdout count: `7`

## Holdout IDs

- `spider__customers_and_addresses__06086`
- `spider__driving_school__06657`
- `spider__e_government__06324`
- `spider__game_injury__01287`
- `spider__inn_1__02600`
- `spider__network_2__04398`
- `spider__network_2__04399`

## Notes

- Automatic inclusion uses a strict lexical table-mention heuristic.
- Therefore, some canonical mechanism witnesses may not appear in the auto candidate set and can still be manually pinned in the design set.