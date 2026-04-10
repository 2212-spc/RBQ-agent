# HDR-Bench v0.1 (Complete-Protocol Mini)

This repository now contains a complete-protocol mini implementation of HDR-Bench:

- Phase0: Spider seed filtering + SQLite/DuckDB dual-engine validation
- Phase1: Topological Explosion (SQLite/CSV/Parquet)
- Phase2: Variant A/B/C + Universe A (gold generation + consistency check)
- Phase3: Universe B (L1/L2/L3 + distractors + Full/Oracle/Trimmed)
- Phase4: inverse_check + perfect_agent_check
- Evaluation: view-level ASR (`Full/Oracle/Trimmed`) over A/B/C variants

## Environment

```powershell
conda create -n hdrbench_mvp python=3.11 -y
conda activate hdrbench_mvp
pip install -r requirements.txt
```

## Data Prerequisite (Spider)

You need Spider JSON + SQLite databases locally.

Expected structure:

```text
<SPIDER_DB_ROOT>/
  concert_singer/concert_singer.sqlite
  world_1/world_1.sqlite
  ...
```

Spider QA json example: `train_spider.json` or `dev.json`.

## 1) Phase0: Build seed registry

```powershell
conda activate hdrbench_mvp
python construction/phase0_seed_filter.py \
  --spider_json D:/path/to/train_spider.json \
  --db_root D:/path/to/spider/database \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_v01/seed_registry.jsonl \
  --max_seeds 12 \
  --per_db_limit 3
```

Outputs:
- `seed_registry.jsonl`
- `seed_registry.summary.json`
- `seed_registry.skipped.json`

## 2) Build complete mini benchmark (Phase1-4)

```powershell
conda activate hdrbench_mvp
python construction/build_hdrbench.py \
  --seed_registry D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_v01/seed_registry.jsonl \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_v01 \
  --max_seeds 12 \
  --distractor_min 3 \
  --distractor_max 5 \
  --trimmed_ratio 0.5 \
  --nonkey_rename_prob 0.7 \
  --l3_apply_prob 0.6
```

Per seed output:

```text
outputs/hdrbench_v01/<seed_id>/
  seed_report.json
  variants/
    A/
      universe_a/ (canonical + rewritten_sql + gold.csv)
      universe_b/ (full/oracle/trimmed + manifest_dirty.json)
      inverse_check_report.json
      perfect_agent.sql
      perfect_agent_report.json
      manifest_public.json
      manifest_private.json
    B/
    C/
```

## 3) Run evaluation

```powershell
conda activate hdrbench_mvp
python evaluation/run_hdrbench_eval.py \
  --bench_root D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_v01 \
  --mode naive_sql \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_v01/eval_naive
```

For pipeline sanity (should be high):

```powershell
python evaluation/run_hdrbench_eval.py \
  --bench_root D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_v01 \
  --mode perfect_sql \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_v01/eval_perfect
```

Main agent comparison:

```powershell
python evaluation/run_hdrbench_eval.py \
  --bench_root D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_full150_v1 \
  --mode llm_code_agent \
  --variants A \
  --split l1 \
  --view full \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_full150_v1/eval_llm_l1_A

python evaluation/run_hdrbench_eval.py \
  --bench_root D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_full150_v1 \
  --mode support_plan_agent \
  --variants A \
  --split l1 \
  --view full \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_full150_v1/eval_support_plan_l1_A

python evaluation/run_hdrbench_eval.py \
  --bench_root D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_full150_v1 \
  --mode support_plan_no_obligation \
  --variants A \
  --split l1 \
  --view full \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_full150_v1/eval_support_plan_no_obligation_l1_A
```

Compare two reports:

```powershell
python evaluation/compare_agent_reports.py \
  --baseline_report D:/code/Python/research_data_agent/hdrbench_mvp/outputs/full150_llm_l1_ABC/report_llm_code_agent.json \
  --candidate_report D:/code/Python/research_data_agent/hdrbench_mvp/outputs/full150_support_v3_l1_ABC/report_support_plan_agent.json \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/analysis/l1_support_vs_llm.json

python evaluation/compare_agent_reports.py \
  --bench_root D:/code/Python/research_data_agent/hdrbench_mvp/outputs/hdrbench_full150_v1 \
  --baseline_report D:/code/Python/research_data_agent/hdrbench_mvp/outputs/full150_llm_l1_ABC/report_llm_code_agent.json \
  --candidate_report D:/code/Python/research_data_agent/hdrbench_mvp/outputs/full150_support_v3_l1_ABC/report_support_plan_agent.json \
  --out D:/code/Python/research_data_agent/hdrbench_mvp/outputs/analysis/l1_support_vs_llm_motif.json
```

## Notes

- This v0.1 focuses on protocol-complete execution with small seed count.
- If a variant fails inverse/perfect checks, it is marked failed in `seed_report.json`.
- `Full/Oracle/Trimmed` are first-class outputs for C1 isolation.

## Current benchmark root

The active benchmark root kept in this repository is:

- [`outputs/hdrbench_full150_v1`](./outputs/hdrbench_full150_v1)

See:

- [`outputs/README.md`](./outputs/README.md)
- [`outputs/hdrbench_full150_v1/README.md`](./outputs/hdrbench_full150_v1/README.md)
- [`docs/support_plan_redesign.md`](./docs/support_plan_redesign.md)
- [`docs/support_plan_worklog.md`](./docs/support_plan_worklog.md)

## Build a larger benchmark root

To build a larger benchmark root using the original Phase0-4 pipeline, use:

```powershell
python construction/build_hdrbench_full.py `
  --spider_json data/spider_data/spider_data/train_spider.json `
  --db_root data/spider_data/spider_data/database `
  --out outputs/hdrbench_full_train_v1 `
  --max_seeds 5000 `
  --per_db_limit 999 `
  --chunk_size 100 `
  --random_seed 13 `
  --distractor_min 3 `
  --distractor_max 5 `
  --trimmed_ratio 0.5 `
  --nonkey_rename_prob 0.7 `
  --l3_apply_prob 0.6 `
  --min_gold_rows 1
```

This wrapper:

- keeps the original Phase0 filtering rules
- keeps the original Phase1-4 construction logic
- adds chunked construction for large registries
- writes build summaries and successful-seed registries under the benchmark root
