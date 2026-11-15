# aws-quick-autoresearch

Which destinations had the most late flights out of Chicago? The original dashboard counted through seven million flight records to answer questions like this. AWS Quick tried ways to do the counting ahead of time. A local program checked every answer and timed each idea. The same 20 queries went from 19.77 seconds to 13 milliseconds.

`v0.1.0` · Python 3.11–3.13 · Local DuckDB · MIT

[ELI5 walkthrough](docs/ELI5.md) · [Open the flight operations dashboard](https://mkhambatti.github.io/aws-quick-autoresearch/flight-operations.html) · [Benchmark and trial history](https://mkhambatti.github.io/aws-quick-autoresearch/) · [Technical design](docs/ARCHITECTURE.md) · [Connect Quick](docs/QUICK.md)

## Try it without an AWS account

With Git and Python 3.11–3.13 on macOS or Linux, run these commands. On Windows, use WSL.

```bash
git clone https://github.com/mkhambatti/aws-quick-autoresearch.git
cd aws-quick-autoresearch
bash scripts/setup.sh
.venv/bin/quick-query demo-small
```

Open the HTML report at the path printed by the last command. The demo generates 2,400 synthetic orders, tests a reusable summary, and submits a candidate that drops returned orders. Look for the answer mismatch in the trial history. The small fixture exercises the checker even when the summary takes longer to query.

Setup installs dependencies and writes the local connector configuration to `quick-mcp.json`. The demo uses scripted proposals and requires no AWS credentials, model API key, or dataset download. To run the larger scripted flight demo, use `.venv/bin/quick-query demo`. It downloads a 114 MB archive and needs about 3 GB of free space. [Data source and checksums](DATA_SOURCES.md)

## Measured flight workload

The baseline read 7,009,728 flight records from a 689 MB CSV for five dashboard panels. In eight experiments, Quick found four improvements. The winner computed each panel’s totals across the source dimensions and stored them in one Parquet file.

| Measurement | Recorded result |
|---|---|
| Held-out batch latency | `19.7694s → 0.01310s` (1,508.5× speedup) |
| Timing conditions | Local DuckDB, warm cache, median of three repetitions per implementation with alternating execution order |
| Checked answers | All 20 matched across four held-out parameter cases and five queries |
| Winning summary | 5.117 seconds to build, 1,740,685 bytes on disk |

The ratio covers the 20-query batch and excludes preparation, research, and assistant time. One such batch recovered the winning summary’s build cost on this machine. Rebuild the summary when its source changes. Exact matches on a finite suite leave equivalence on other inputs unproven. [Final samples](examples/quick-led/final.json) · [Winning SQL](examples/quick-led/winner.json) · [Benchmark limits and provenance](docs/RESULTS.md)

## How Quick runs an experiment

You define the source, questions, and budget. MCP gives Quick access to the runner’s tools from chat. Quick can ask, for example, whether preparing monthly totals once would save time across several dashboard panels. It submits the SQL for that change. The runner computes the summary, checks every training answer, and times candidates that pass. Quick reads the decision before proposing another change.

This adapts Andrej Karpathy’s autoresearch loop to analytics. In his project, an agent changes training code, trains a model, and checks its validation score. Here Quick changes SQL or the layout of a Parquet summary. A fixed evaluator checks the rows and measures query time. [Karpathy’s post](https://x.com/karpathy/status/2029701092347630069) · [Original autoresearch project](https://github.com/karpathy/autoresearch) · [Experiment lifecycle and selection rule](docs/ARCHITECTURE.md#experiment-lifecycle)

For a Quick-led run, register a fresh workload with `.venv/bin/quick-query init-small` or `.venv/bin/quick-query init-flights`. Import the generated connector configuration in Quick desktop and give Quick the printed run ID. The run produces SQL and measurements for the owner to review. [Connection steps and research prompt](docs/QUICK.md)

## Bring your own data

Each local run accepts one CSV or Parquet snapshot and a workload definition. Put the file in `data/local/` or register its existing path. Copy `examples/orders/workload.json` to `workloads/local/orders.json` and edit its reference queries, training parameters, and held-out cases for your schema.

```bash
.venv/bin/quick-query init \
  --source data/local/orders.parquet \
  --workload workloads/local/orders.json \
  --trials 12 --seconds 3600
```

Git ignores the local data and workload folders’ contents, runtime workspaces, and connector configuration. The optional Athena adapter uses a registered table or view and incurs AWS charges. Its validation uses stubbed service responses. [Workload format](docs/WORKLOADS.md) · [Athena setup](docs/ATHENA.md)

## Development

Run `.venv/bin/python -m pytest -q` for the test suite. After editing the package, rerun setup before launching the installed connector. [Contributing](CONTRIBUTING.md) · [Validation record](docs/VALIDATION.md) · [Publish a results page](docs/PUBLISHING.md) · [License](LICENSE)
