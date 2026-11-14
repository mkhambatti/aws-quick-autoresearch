# Run against Amazon Athena

The adapter is implemented and tested with boto3's API Stubber, including pagination, null values, result reuse rejection, CTAS generation, timeout cancellation and measured statistics. **It has not been run against a live AWS account in this build.** Account policies, Lake Formation, encryption and data locations can require additional setup.

Local timings are not an Athena benchmark. Athena may optimize SQL differently; it may also already have good Parquet layouts, leaving little improvement available.

## Account setup

Use a dedicated AWS sandbox and an S3 bucket in the same region as Athena. Configure credentials using your normal AWS profile/SSO. Do not paste credentials into Quick or check them into this repo. If Quick desktop does not inherit your terminal's AWS_PROFILE, add that non-secret profile name to the connector environment; credentials still come from the SDK provider chain.

1. Create an S3 prefix for immutable inputs and another for research results.
2. Create an Athena **SQL engine v3** workgroup named `quick-query-research` with an S3 query results location, for example `s3://YOUR_BUCKET/quick-query/results/`, and a **per-query scan cutoff of 1 GB (1,000,000,000 bytes)**. The adapter refuses workgroups with missing or larger cutoffs than the configured maximum. Athena cancels queries exceeding the cutoff; cancelled queries can still incur charges.
3. Ensure the workgroup's result configuration supports CTAS. This adapter does not supply an external_location and lets Athena create CTAS output under its configured query-result location. Do not use an S3 prefix containing unrelated valuable data for research results.
4. Upload the real source and register its schema:

```bash
.venv/bin/quick-query download-flights
aws s3 cp data/2008.csv s3://YOUR_BUCKET/quick-query/input/2008/2008.csv
```

Edit `examples/athena-setup.sql` to replace YOUR_BUCKET and execute its statements individually in the Athena console. This keeps the original CSV layout; do not convert an existing Parquet source to CSV just to manufacture a dramatic baseline.

5. Review `examples/athena-config.json`, particularly the region, source table, workgroup, `max_queries`, `max_bytes_per_query`, `usd_per_tb` and `allow_materialize`. Set the regional on-demand SQL scan rate; the $5/TB example is not a universal price. This estimator uses decimal MB/TB, rounds up to MB and applies a 10 MB minimum. It is an estimate, not a billing reconciliation. It excludes S3, Glue, KMS, network, model calls and provisioned-capacity pricing.
6. Register and measure a small run first:

```bash
.venv/bin/quick-query init-aws \
  --config examples/athena-config.json \
  --workload examples/flights/workload.json \
  --allow-aws --trials 5 --repeats 2 --timeout 120 --seconds 7200
.venv/bin/quick-query baseline latest --wait
```

Then use Quick as described in QUICK.md, or submit a candidate manually:

```bash
.venv/bin/quick-query submit latest examples/flights/03-candidate.json --wait
.venv/bin/quick-query finalize latest --wait
```

The compression-only Parquet example above is compatible with both engines. `row_group_size` is a **local-only** option; remove it from Athena proposals. Athena supports ZSTD and SNAPPY in this adapter, not the local `uncompressed` recipe. Use `data` and `cache` aliases in queries; the adapter substitutes the registered table and generated scratch table. Only tables in the registered database are supported. Federated catalogs, UDFs and cross-database joins are outside this version's scope.

## What is actually measured

- `DataScannedInBytes` and `EngineExecutionTimeInMillis` come from GetQueryExecution, not a value supplied by the AI.
- `TotalExecutionTimeInMillis` and query IDs remain in measurement files; queue/service time is not part of the optimizer's engine-time score.
- Result reuse is explicitly disabled on every submission. A response marked as reused is rejected.
- Validation, repeated benchmarks, paired incumbent measurements and final verification all incur real queries. These count against the same `max_queries` budget.
- The bytes objective totals the training workload's scanned bytes. A lower byte count may not lower the bill if queries already hit Athena's minimum charge. The final report retains both scan-cost estimates and timings.
- All query submissions, including CTAS, are reserved in `aws-usage.json` before sending requests. The ledger records IDs, status and available service statistics. Timeouts request cancellation. A hard process termination or network outage can leave a query running; monitor your workgroup.
- `max_queries=2000` with a 1 GB cutoff puts the scale of scan spending around $10 at the illustrative $5/TB rate. This is **not a hard dollar cap**: cutoffs/cancellations, retries, other workgroup users and non-Athena charges matter. Start smaller, inspect usage, and reserve sufficient query budget for finalization.

## Permissions

The runner identity needs:

- Athena GetWorkGroup, StartQueryExecution, GetQueryExecution, GetQueryResults and StopQueryExecution on the dedicated workgroup.
- Glue GetDatabase/GetTable/GetPartitions and related metadata reads on your registered database/table. With materialization enabled, allow CreateTable and required Glue updates only in the scratch database (the source view can also live there). Use Lake Formation grants if enabled.
- S3 ListBucket and GetObject on the source prefix; GetObject/PutObject and necessary multipart operations on the results prefix. Add required KMS permissions if your buckets are encrypted.

The runner does not need permission to overwrite source objects or delete production tables. Keep source prefixes read-only. If `allow_materialize=false`, restrict the runner to SELECT and query-result writes.

## Immutability and cleanup

Use an immutable snapshot table/prefix for the whole research run. `snapshot_id` is recorded provenance, not an enforcement mechanism; this prototype cannot stop an external pipeline changing your Athena source. Local sources are SHA-256 checked before every operation. A production extension should bind catalog snapshots or versioned object manifests.

Each materialized trial creates a `qqar_<random>` table; the chosen table appears in that trial's `cache.json`. A failed CTAS may leave objects. Keep the winner for serving the dashboard if accepted. After reviewing artifacts, manually drop unwanted `qqar_...` tables and remove their corresponding S3 locations/manifests. **Dropping an external table does not delete S3 data.** Configure lifecycle expiration on the dedicated research results prefix; don't blindly remove a shared bucket.

## Official references

- https://docs.aws.amazon.com/athena/latest/APIReference/API_StartQueryExecution.html
- https://docs.aws.amazon.com/athena/latest/APIReference/API_QueryExecutionStatistics.html
- https://docs.aws.amazon.com/athena/latest/ug/workgroups-setting-control-limits-cloudwatch.html
- https://docs.aws.amazon.com/athena/latest/ug/ctas.html
- https://docs.aws.amazon.com/athena/latest/ug/csv-serde.html
- https://aws.amazon.com/athena/pricing/
