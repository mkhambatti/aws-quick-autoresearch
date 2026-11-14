# Quick Query Autoresearch

**Let an assistant try faster ways to answer your data questions. Keep a change only when measured results improve and the checked answers stay the same.**

[View the results](https://mkhambatti.github.io/aws-quick-autoresearch/) · [Connect AWS Quick](docs/QUICK.md) · [Bring your data](docs/WORKLOADS.md) · [Technical design](docs/ARCHITECTURE.md)

## The idea, in plain language

Imagine counting every item in a warehouse each time someone asks how many items are on a shelf. A better approach might be to prepare a shelf-by-shelf tally. But that shortcut is useful only if the tally gives the right answer and saves more time than it takes to build.

This project lets an assistant test those shortcuts. You supply a fixed dataset and the questions that matter. The assistant proposes a change. A separate runner checks the answers, measures the time, and keeps or rejects the proposal. The assistant reads that evidence before choosing its next experiment.

**MCP is the connection between the assistant and the runner.** AWS Quick can use it to conduct experiments from chat and show the measured chart. Quick supplies the reasoning; this project supplies the experiment tools and evidence. It does not require a separate model API key for the Quick path.

## Why this is useful with Quick

A query suggestion alone does not establish that a dashboard became faster or that its answers stayed correct. This connector gives Quick a complete feedback loop: inspect a registered workload, propose SQL or reusable summaries, run a bounded experiment, inspect its result, and try again. The same eight tools work across registered datasets. A human sets the questions and budget before research begins.

The output is a reviewable candidate with SQL, preparation cost, repeated measurements, failed attempts, and final checks. Adopting that candidate in a production dashboard remains a separate owner decision. The connector does not update Quick apps or production tables automatically.

## Try it without an AWS account

Requirements: macOS or Linux, Python **3.11–3.13**, and Git. Python 3.12 is recommended. Windows requires WSL because the worker uses Unix file locks.

```bash
git clone https://github.com/mkhambatti/aws-quick-autoresearch.git
cd aws-quick-autoresearch
# If needed on macOS: brew install python@3.12
bash scripts/setup.sh
.venv/bin/quick-query demo-small
```

The small demo generates **2,400 explicitly synthetic order rows**, tests a reusable summary, and tests an intentionally wrong proposal that should be rejected. It prints the location of an HTML report. It requires no data download or AWS credentials. Small-data timings are a functional check, not a performance claim; the summary may not win.

The installer creates `.venv`, installs the package and test dependencies, and generates a machine-specific `quick-mcp.json`. It preserves an incompatible existing environment. After changing code, rerun setup or `.venv/bin/python -m pip install --no-deps .`.

To reproduce the larger public-data demonstration:

```bash
.venv/bin/quick-query demo
```

This downloads the checksum-verified 2008 flight archive (114 MB compressed; 689 MB CSV), then runs predefined proposals. Reserve about 3 GB of disk and several minutes. **Both CLI demos are scripted recipes.** For assistant-selected experiments, use a fresh run with [Quick](docs/QUICK.md).

## A measured Quick-led experiment

The published flight experiment used **7,009,728 records** and five dashboard queries. On four held-out parameter cases, the baseline took **19.7694 seconds** and the winning implementation took **0.01310 seconds**, a **1,508.5×** reduction in elapsed query time. These are median times for a **20-query batch**, not a single dashboard load.

The winner precomputed the totals each panel needed, across the source dimensions. Building it took **5.117 seconds** and produced about **1.7 MB** of Parquet. All 20 final query/case combinations matched the reference answers. The run evaluated eight candidate experiments; four improved the incumbent.

[Read the experiment and its limits](docs/RESULTS.md) · [Inspect the final measurements](examples/quick-led/final.json) · [Inspect the winning SQL](examples/quick-led/winner.json)

The large gain reflects repeated CSV scans versus precomputed summaries for fixed questions. It is not evidence of a similar gain on an optimized warehouse, a measured AWS cost saving, or a proof of equivalence on every possible input. Times use warm caches. Research, preparation, and assistant latency are excluded from the query-time ratio. Summaries must be rebuilt when source data changes. The operator's Quick conversation identifies the planner; the run ledger independently records measurements but does not authenticate which client submitted them.

## Bring a different dataset

Flights are an optional demo, not an engine requirement. Each run accepts one local CSV/Parquet snapshot or one registered Athena table/view, plus a workload definition.

1. Put your file in `data/local/`, or keep it at another local path.
2. Copy `examples/orders/workload.json` into `workloads/local/` and edit the reference SQL, training cases, and held-out cases for your schema.
3. Register the run:

```bash
.venv/bin/quick-query init \
  --source data/local/orders.parquet \
  --workload workloads/local/orders.json \
  --trials 12 --seconds 3600
```

Keep the printed run ID and give that exact ID to Quick. Private data, private workload definitions, connector settings, and runtime results are ignored by Git. See [the full guide](docs/WORKLOADS.md) for parameters, nulls, correctness rules, and the candidate format. [Athena](docs/ATHENA.md) is an optional metered adapter; its live AWS path has not been verified in the published experiment.

## What “autoresearch” means here

Autoresearch is a repeated experiment loop: propose a change, run it, measure it against a fixed evaluator, keep an improvement, and use the result to choose the next attempt. Andrej Karpathy's [autoresearch project](https://github.com/karpathy/autoresearch) applies this pattern to model training. His repository links to the [original context post](https://x.com/karpathy/status/2029701092347630069) and a [follow-up post](https://x.com/karpathy/status/2031135152349524125).

This project adapts the pattern to analytics: SQL and data layouts are the editable candidates; answer checks and timing rules are the evaluator. It is an independent implementation, not a fork of Karpathy's code. The aim is evidence-driven iteration, not an assurance that every experiment will help.

## Read further

| Document | What it explains |
|---|---|
| [Quick guide](docs/QUICK.md) | Connect the local MCP server and direct a bounded research run |
| [Technical design](docs/ARCHITECTURE.md) | State transitions, tool contracts, selection rules, and trust boundaries |
| [Workload guide](docs/WORKLOADS.md) | Register another source and define correct answers |
| [Measured results](docs/RESULTS.md) | Quick-led and scripted evidence, with comparison limits |
| [Validation](docs/VALIDATION.md) | What was tested and what remains unverified |
| [Publishing results](docs/PUBLISHING.md) | GitHub Pages and explicit report exports |
| [Contributing](CONTRIBUTING.md) | Fork, install, test, and propose changes |
| [Data attribution](DATA_SOURCES.md) | Flight source, hashes, and third-party data terms |

```bash
.venv/bin/python -m pytest -q
```

MIT-licensed code. Flight data is downloaded separately and retains its publisher's terms. Independent prototype; no affiliation with or endorsement by AWS or Andrej Karpathy is implied.
