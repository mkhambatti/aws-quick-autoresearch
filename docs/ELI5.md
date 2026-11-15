# One flight dashboard, two ways to answer it

Imagine you run operations at Chicago O’Hare. You have a year of U.S. flight records in a spreadsheet-like file. Each row describes one flight. There are **7,009,728 rows**. At the February review, someone asks, “Which destinations had the most late arrivals?” Someone else asks, “Which airlines cancelled the most flights?” You want to put the answers on one screen. [Open the flight operations dashboard](https://mkhambatti.github.io/aws-quick-autoresearch/flight-operations.html)

## Why did the original take 19 seconds?

Take the destinations question. The original query opens the 689 MB file, finds February flights out of Chicago, groups them by destination, and counts arrivals at least 15 minutes late. New York LaGuardia had **369**, Dallas/Fort Worth **276**, and Newark **258**. The airlines panel reads the file again to count cancellations. The departure-hour, weekday, and nationwide airline panels do their own counting too. [The five original queries in workload.json](../examples/quick-led/workload.json)

The final test ran those five questions with four sets of filters. One deliberately selected no flights, to check that an empty answer stayed empty. The **whole set of 20** took **19.77 seconds** on the local machine. You can watch Chicago’s answers appear as their individual queries finish in the dashboard replay. [Recorded query times](../examples/quick-led/final-measurements.json)

## Who came up with the shortcut?

In the published run, **AWS Quick proposed the experiments from chat**. Through its MCP connector, Quick could send the local program a proposed change written in SQL, read what happened, and choose its next idea. The local program ran the queries, checked the answers, and kept time. The operator’s Quick conversation identifies this run. The public files record the eight proposals and their results, but don’t identify the underlying model version. The command-line demos try a fixed list of ideas. You can also submit your own SQL ideas to the runner. Checking and timing either kind of experiment works without a model. [Run provenance](RESULTS.md) · [Eight experiments in history.json](../examples/quick-led/history.json)

**Trial five won.** Its idea was simple. Count what each panel needs once and save those totals in a small file. For the February Chicago routes panel, that file already has a row for LaGuardia with the number 369. The dashboard can look it up. Cancelled flights still count toward cancellations. Quick also tried compression, but the fastest version used an **uncompressed** summary. You can open the exact proposal and see both the SQL that builds the summary and the five short queries that read it. Running those queries later needs no AI call. [Trial five’s proposal](../examples/quick-led/trial-005/candidate.json) · [Saved winning SQL](../examples/quick-led/winner.json)

## What made it a win?

1. **Get the answers right.** For every practice case, the returned columns and values had to match the original, including duplicates and missing values. A mismatch ended the trial before speed scoring.
2. **Beat the current winner.** The runner timed both versions repeatedly, alternating which went first. A new idea had to be more than 3% faster than both the previous best time and the winner’s time that day.
3. **Pass a fresh check.** Once the winner was locked, the runner tried the four reserved filter sets. All 20 answers matched. The same batch took **13 milliseconds**, measured locally with the data already warm in the machine’s cache. Preparing the summary took **5.117 seconds** once for that snapshot. When the data changes, it needs rebuilding. [Checks in engine.py](../quick_query/engine.py) · [Final results](../examples/quick-led/final.json)

That’s **autoresearch** here. Quick makes a guess, gets an answer it can measure, and uses that evidence to make its next guess. Andrej Karpathy used this loop to change model-training code and measure model quality. Here the thing being improved is how a dashboard gets its numbers. [Karpathy’s post](https://x.com/karpathy/status/2029701092347630069) · [His original project](https://github.com/karpathy/autoresearch) · [Benchmark and trial history](https://mkhambatti.github.io/aws-quick-autoresearch/#trials)

## Try it with your own data

Suppose your team tracks returns and asks, “How many orders came back in each product category?” You supply the data and a query whose answer you trust. Quick can then try shortcuts that fit *your* question.

1. **Pick a snapshot.** From a [set-up clone](../README.md#try-it-without-an-aws-account), put one CSV with a header or one Parquet file in `data/local/`. Say yours is `orders.parquet`.
2. **Write down what has to stay true.** Copy [the orders example](../examples/orders/workload.json) to `workloads/local/orders.json`. Edit its `queries` to use your column names. Each query reads a table called `data`. Give it practice filters in `train_cases` (say, two sales regions) and different filters in `test_cases` for the final check. A file alone doesn’t tell Quick which business questions matter.
3. **Register it.** Run the command below from the clone and keep the run ID it prints.

   ```bash
   .venv/bin/quick-query init --source data/local/orders.parquet --workload workloads/local/orders.json
   ```

4. **Give Quick the job.** Import the generated `quick-mcp.json` in Quick desktop and enable the connector. Give Quick your run ID with the [ready-to-paste research prompt](QUICK.md#research-instruction). It measures your starting point, proposes SQL for your data, and returns the results for review. After it finishes, open `workspaces/default/runs/YOUR_RUN_ID/report.html` to see what helped. The winning SQL for your data is in `winner.json` beside that report. [Workload format](WORKLOADS.md) · [Connector setup](QUICK.md#connect-the-desktop-application)
