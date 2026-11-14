# Measured results

## What the evidence establishes

The published Quick-led run improved a fixed flight dashboard workload from 19.769377878 seconds to 0.013104917 seconds on its final batch. The 1,508.55× ratio compares medians of three warm-cache repetitions of **four parameter cases × five queries**. It is not a measurement of one dashboard load, network latency, user-perceived response time, or an AWS bill.

Run `query-20261113-173728-e6a1d9` contains nine records: one baseline and eight candidates. Four candidates were kept. The winning trial was 5. Its preparation took 5.117151250 seconds and produced 1,740,685 bytes of Parquet. The runner recorded 227.68 seconds of work. All 20 held-out query/case combinations matched exactly.

The operator supplied a Quick conversation showing the assistant selecting experiments and describing completion of this run. The saved runtime files corroborate the SQL, decisions, timings, and final verification. The ledger does not record an authenticated client identity or model version, so it cannot independently prove the planner's identity. The private conversation is not published.

## What changed

The baseline scans the original CSV for route, carrier, departure-hour, weekday, and national-carrier panels. Quick first proposed a reusable aggregate over all dashboard dimensions. It tested compression and row-group sizes. The largest later improvement came from computing each panel's aggregates in advance, tagging those rows by panel type, and sorting the combined Parquet output by panel, month, and origin.

The winning SQL groups across source dimensions rather than materializing only the known training filter values. The final checks exercise different month/origin cases on the same source. This makes the optimization inspectable, but does not establish correctness for every possible future source snapshot.

| Trial | Change | Decision | Training batch seconds |
|---|---|---|---:|
| 0 | Original CSV and reference queries | Baseline | 14.38 |
| 1 | Reusable dimensional aggregate | Kept | 0.0442 |
| 2 | Uncompressed aggregate | Kept | 0.0394 |
| 3 | 65,536-row groups | Kept | 0.0193 |
| 4 | 262,144-row groups | Discarded | 0.0351 |
| 5 | Separate per-panel aggregates in one tagged table | Kept | 0.0093 |
| 6 | Smaller row groups | Discarded | 0.0140 |
| 7 | One large row group | Discarded | 0.0105 |
| 8 | Snappy compression | Discarded | 0.0113 |

Rounded values summarize [the exact history](../examples/quick-led/history.json). Training and final scores total different parameter cases and should not be substituted for each other.

## Cost and limitations

The reported preparation break-even is one **final 20-query batch** because 5.117 seconds of setup is less than the approximately 19.756 seconds saved per batch. This calculation excludes all research effort and assistant cost. Summary refresh cost returns when the source changes. The project does not maintain incremental refreshes.

The starting point is a 689 MB CSV with repeated parsing and scans. The winner reads a 1.74 MB summary for fixed questions. Most of the gain is explained by reducing work and changing storage representation. These results do not predict gains on optimized Parquet, an indexed database, or a tuned warehouse. No confidence interval, statistical-significance result, formal equivalence proof, production latency SLO, or AWS cost reduction is claimed.

The source has 7,009,728 actual flight records; no duplicated rows were added to claim scale. Held-out parameters are withheld from MCP responses before finalization, but an owner with filesystem access can read them. The evaluator is fixed through this interface, not cryptographically immutable.

## Earlier scripted evidence

The original Linux demonstration (`query-20261112-204646-e020aa`) used predefined proposals. It measured 30.299964315 → 0.108952640 seconds (278.10×), with 3.177320071 seconds of setup. Its nine records include an intentionally wrong proposal that was rejected. [Inspect its report](../examples/measured/report.html) and [environment](../examples/tested-environment.json).

Do not interpret the ratio between the two runs as a controlled comparison of Quick versus a scripted planner. Hardware, execution conditions, and candidate sets differ. The older Mac report mentioned in the operator's conversation is not the Linux example above; its 387× result is not silently combined with either dataset of measurements.

## Inspect the artifacts

[Quick-led report](../examples/quick-led/report.html), [history](../examples/quick-led/history.json), [winner](../examples/quick-led/winner.json), [final samples](../examples/quick-led/final.json), [per-query measurements](../examples/quick-led/final-measurements.json), [source metadata](../examples/quick-led/source.json), and [workload](../examples/quick-led/workload.json) are included. Machine-specific absolute paths, raw data, caches, and private chats are excluded. The environment captured during publication preparation is labeled as such; it was not instrumented at original experiment time.
