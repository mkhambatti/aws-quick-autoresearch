# Bring another workload

Version 0.1 handles one registered CSV/Parquet source or one Athena table/view per run. It can contain millions of rows; practical limits depend on machine memory, time and query shape. Multiple enterprise tables can first be exposed through an owner-managed view. The planner cannot register arbitrary new tables or join outside its allowed source.

A CSV header is required. Schema inference samples the first 20,480 rows; values that contradict inferred types fail rather than silently changing results. Prefer a typed Parquet file for heterogeneous enterprise data. `init --nullstr ...` changes the explicit CSV null token (default `NA`).

## Start from the included orders example

`examples/orders/workload.json` is a complete example with different source columns from the flight demo. Copy it to `workloads/local/orders.json`, then adapt it for your data in `data/local/`. Both local folders are ignored by Git. Use an immutable snapshot; after moving a source or changing its contents, register a fresh run instead of editing an existing run's state.

```bash
.venv/bin/quick-query init --source data/local/orders.parquet --workload workloads/local/orders.json
```

The small generated demo is available with `demo-small`; `init-small` registers it for assistant-led experiments without running them. It has 2,400 synthetic rows and is a functional example, not performance evidence.

## Workload JSON

```json
{
  "name": "Returns operations dashboard",
  "queries": {
    "return_counts": "SELECT reason AS dimension, COUNT(*) AS returns, SUM(refund_cents) AS refund_cents FROM data WHERE region = {{region}} GROUP BY reason"
  },
  "train_cases": [{"region": "US"}, {"region": "CA"}],
  "test_cases": [{"region": "GB"}, {"region": "NO_MATCH"}]
}
```

Use placeholder syntax `{{parameter}}` without surrounding SQL quotes. The harness safely substitutes strings, integers, booleans or null. Every case must define every required parameter.

The user-owned reference query defines correctness. Include relevant cancellation/null/tie/empty-result cases in your workload, and separate final cases with genuinely different distributions. Test cases are not returned to Quick until finalization (and only summary pass/fail then); anyone with owner access to local files can of course read them. For sensitive or adversarial evaluations, put the verifier in a separate service with a separate identity.

## Candidate JSON

```json
{
  "hypothesis": "Precompute reusable return totals by region and reason.",
  "materialize": {
    "sql": "SELECT region, reason, COUNT(*) AS n, SUM(refund_cents) AS refund_cents FROM data GROUP BY region, reason",
    "compression": "zstd"
  },
  "queries": {
    "return_counts": "SELECT reason AS dimension, SUM(n) AS returns, SUM(refund_cents) AS refund_cents FROM cache WHERE region = {{region}} GROUP BY reason"
  }
}
```

`materialize: null` tests SQL-only changes against the original source. Each materialization is built from `data`, independently of previous candidates. It must preserve enough information for every query and parameter case. Queries may read `data` and/or `cache`. A materialization is not a hardcoded cached answer for known parameters; Quick's research instruction prohibits that shortcut, and unseen cases provide an additional check.

The CLI checks reference SQL at registration, and the engine checks every candidate. Unsupported functions are rejected rather than executed. Output columns must match by name and position; rows are compared as multisets. This supports unordered dashboards, not contracts where row ordering itself is meaningful. Use fixed-point integers for money and reproducible aggregates. Reordered floating-point sums can differ slightly; this conservative verifier rejects them.

## Experiment records

`state.json` is the owner's run ledger. Each `trial-NNN` stores candidate SQL, setup metrics and query measurements. Failed SQL or wrong answers remain in history; a losing materialization cannot overwrite the winner. `winner.json` is exported only after successful final checks. The runner does not reset or commit your Git working tree.

`score` is the median total training-workload duration (or scanned bytes for Athena). It is not average latency per query. Each sample includes all training cases × all query templates. Final timings include all final cases × templates. Training and final workloads may differ in size; compare baseline to winner within each workload, not training seconds to final seconds.

`break_even_test_workloads` counts repeats of the complete final-case workload needed to repay the winning materialization's build time. It excludes time spent researching losing candidates, validation, download, schema discovery and model usage. `spent_seconds` reports runner work across baseline/trials/finalization, excluding download/registration and report rendering. A production decision should include those costs, data refresh frequency, storage and freshness requirements.
