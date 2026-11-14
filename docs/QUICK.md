# Run experiments from AWS Quick

Quick chooses the next experiment. This local MCP service executes it, checks answers, and measures results. The packaged CLI demos use fixed proposals and do not need Quick.

## Install and register

From your clone's final folder location:

```bash
bash scripts/setup.sh
.venv/bin/quick-query init-small --trials 12 --seconds 3600
# Or register the full public flight workload:
.venv/bin/quick-query init-flights --trials 12 --seconds 3600
```

Run **one** initialization command for the workload you want. `init-small` generates a synthetic orders fixture. `init-flights` downloads the public data if needed. For your own file use `init --source ... --workload ...` as described in the [workload guide](WORKLOADS.md). Keep the printed run ID. `demo` and `demo-small` finalize their own runs, so they cannot be continued by Quick.

## Connect the desktop application

Open **Customize → Connectors → Create → MCP server** in Quick desktop. Choose **Import**, supply the absolute path to your generated `quick-mcp.json`, and load it. Alternatively, select **Local** and copy its executable and arguments. Enable the connector and its tools. These desktop options are documented in [AWS's connector guide](https://docs.aws.amazon.com/quick/latest/userguide/connections-desktop.html).

Ask Quick to call `list_research_runs`, then `research_status` for your exact run ID. Confirm the source points to the intended file. The local connection uses stdio and requires your computer to remain available. The cloud MCP connection is a separate remote-server path; this repository does not deploy that service. See [AWS's cloud MCP guide](https://docs.aws.amazon.com/quick/latest/userguide/mcp-integration.html).

## Research instruction

Replace `YOUR_RUN_ID` before pasting:

> Use the Quick Query Autoresearch connector for run YOUR_RUN_ID only. First inspect research_status and confirm its source and workload. Measure the baseline if needed. Propose and execute up to eight candidate experiments that reduce the registered objective while preserving checked answers. Use only this connector's research tools. Do not modify the source, workload, evaluator, or run files. Preserve all query names and output column names. Use data for the source and cache for an optional reusable materialization. State a hypothesis for each proposal. After each job, poll research_status until it is no longer running; handle errors before proceeding. Use the actual result to choose the next idea. Do not hardcode answers or materialize only known training parameters. Stop after three consecutive non-improvements, eight candidates, or the budget limit, whichever comes first. Reserve time for final verification. Call finalize_research once, wait for completion, then get_progress_chart. Explain final correctness, repeated timings, preparation cost, storage, failed attempts, and limitations. Distinguish the training score from the final held-out batch. Do not call local time savings AWS cost savings.

`--trials 12` includes the baseline and allows headroom for eight candidates. Finalization uses remaining time, but does not consume a trial record. Tool consent and unattended execution depend on Quick's settings. A pause in the conversation does not itself stop a worker already launched.

## Troubleshooting

**Missing package or executable.** Rerun `bash scripts/setup.sh`, then `.venv/bin/python -I -c "import quick_query; print(quick_query.__file__)"`. Reimport the generated connector config. Setup uses a regular package install so imports work when Quick launches outside the repository.

**Folder moved or source missing.** Existing runs retain absolute paths to their original source. Register a new run from the current folder and give Quick that exact ID. Do not pick “newest” across unrelated or stale runs. Regenerate the connector configuration with `.venv/bin/quick-query quick-config` after moving the checkout.

**Sealed run.** Create a fresh run. A successful scripted demo is already sealed. A failed finalization is also sealed to prevent repeated tuning against held-out cases.

**Worker interrupted or budget exhausted.** Inspect the run's `worker.log` and status. Retrying a nonfinal operation may be possible; a finalization failure needs a new run. Reduce the workload or increase owner-set limits for a new run. The MCP client cannot raise them.

**Only a URL field is available.** Use the desktop local MCP connection for this package. A hosted authenticated MCP service is a separate deployment project.

The supplied Quick conversation records one completed assistant-directed run, and its measurements are included in [the results](RESULTS.md). This is evidence of that integration, not a compatibility guarantee for every account or future Quick release.
