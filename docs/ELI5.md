# How Quick learns to answer the same question faster

Suppose a flight dashboard gets faster after someone removes every cancelled flight. Would you ship it? Ask the dashboard how many flights were cancelled and the problem shows up immediately. That’s why this project gives the experiment two rules. Get the same answers first. Then see how long they take.

**Autoresearch means the result of one experiment helps choose the next.** You supply the questions and the budget. Quick suggests a shortcut. A program tries it, checks the answers, and times it. Quick sees what happened and decides what to try next. MCP is the connection that lets Quick submit an idea and read back a measured result from chat. [Watch the before-and-after replay](https://mkhambatti.github.io/aws-quick-autoresearch/#replay)

## Draw the loop

```text
[You]  choose the questions, the correct SQL, and the time limit
   ↓
[Quick]  “What if we counted flights by route ahead of time?”
   ↓
[Runner]  build the summary → check the answers → time passing ideas
   ↓
[Trial log]  record the decision, the time, and any error
   └──────→ Quick reads the result and chooses the next experiment
```

You can follow the same path in the code. The [flight workload](../examples/quick-led/workload.json) defines the five questions. In [server.py](../quick_query/server.py), `submit_experiment` receives Quick’s SQL and `research_status` returns the decision. In [engine.py](../quick_query/engine.py), `trial()` puts the idea to the test. [local.py](../quick_query/local.py) runs DuckDB on the data, and [sql.py](../quick_query/sql.py) gives each result a fingerprint that accounts for column names, values, missing values, and duplicate rows. Changing the order of the rows is fine. Losing a row changes the fingerprint.

What earns a win? First, every practice answer must match. Then the runner takes turns timing the new idea and the current winner. Under the default rule the new idea must be more than 3% faster than both the winner’s earlier time and its time today. A tiny lucky gain stays in the log. [Rules Quick receives](../goal.md) · [How the runner picks a winner](ARCHITECTURE.md#experiment-lifecycle)

## Count three flights by hand

The 2008 file contains 7,009,728 rows, one per flight, and 29 columns. Here are three actual Southwest flights from Seattle to Denver. All were scheduled to depart at 3:25 p.m. on a Monday. The original columns include `Origin`, `Dest`, `ArrDelay` (minutes early or late), and `Cancelled`. [Source and download](../DATA_SOURCES.md) · [Full schema](../examples/quick-led/source.json)

| Date | Arrival delay | Cancelled? |
|---|---:|---|
| January 14 | −22 minutes | No |
| January 21 | 70 minutes | No |
| January 28 | Missing | Yes |

Cover the table. **How many were scheduled? How many arrived at least 15 minutes late? What was the average delay?** Three were scheduled, one was late, and the two recorded arrivals averaged 24 minutes: (−22 + 70) ÷ 2. The cancellation rate uses all three flights. Saving both counts lets the dashboard get both answers right later.

## See the shortcut Quick found

The original dashboard read the flight file to produce each panel. For example, its routes panel selects one month and origin airport, then counts flights by destination. The other panels group by carrier, departure hour, weekday, or carrier nationwide. Refreshing the dashboard meant doing the counting again. [Original queries](../examples/quick-led/workload.json)

Trial 5 did the counting ahead of time. It wrote one small Parquet file with a label on each row saying which panel it belongs to. Here is one actual route row, covering **all** January flights from Seattle to Denver, including the three above. [Winning SQL](../examples/quick-led/winner.json)

| Panel | Month | Origin → destination | Scheduled | Recorded arrivals | Total delay minutes | Late | Cancelled | Diverted |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Routes | January | SEA → DEN | 531 | 524 | 4,185 | 129 | 7 | 0 |

Now ask, “How many arrived late?” The routes panel can look up **129**. It can also divide 4,185 by 524 to find the average delay. If someone wants the identity of the flight that was 70 minutes late, they’ll need the individual flight records. When those records change, the summary needs rebuilding.

## Read the two pictures

**The before-and-after replay answers “How long did we wait for the same answers?”** It starts two seconds into a recorded comparison. The original is still counting. The prepared summary has already finished. Pick **Replay from start** to watch both clocks together, or **Show both charts** to compare the answers immediately. Each chart shows the same three destinations with the most late arrivals from Chicago O’Hare in February. The bars count flights. The timers cover all **20 queries** in the batch. [Open the replay](https://mkhambatti.github.io/aws-quick-autoresearch/#replay) · [Query timings](../examples/quick-led/final-measurements.json)

**The trial chart answers “Which ideas helped?”** Read left to right, one experiment at a time. Lower means faster. Each equal step on the vertical scale represents the same factor of change. The line follows the fastest accepted version. On the 15-query practice batch, the original took 14.38 seconds. Trial 1 prepared shared totals and took 0.044 seconds. Trial 4 tried storing the file in bigger chunks and lost. Trial 5 prepared each panel’s own answers and took 0.0093 seconds. Later ideas failed to beat it. Quick could learn from all eight attempts. [Trial chart](../examples/quick-led/progress.png) · [Decisions and hypotheses](../examples/quick-led/history.json)

For the **final check**, the runner locked the winner and tried five panels on four held-back sets of filters, including one that should return no flights. All 20 answers matched. With the data already warm in the local machine’s cache, the middle of three batch timings fell from **19.77 seconds to 0.0131 seconds**. Building the summary cost **5.117 seconds** once for this snapshot. The saved time repaid that cost on the first full batch. New questions and new data need their own checks. [Final measurements and limits](../examples/quick-led/final.json)

There’s a second flight report in the repo. That run followed a fixed list of ideas, including a deliberately broken shortcut that dropped cancelled flights. Look for the rejection at trial 8. The replay above uses the separate run where Quick chose its own ideas. [Scripted trial log](../examples/measured/history.json) · [How the chart is drawn](../quick_query/report.py)

## Where the idea comes from

Andrej Karpathy’s autoresearch agent edits a training program, runs it, and uses the model’s score to choose the next edit. Here, Quick edits how a dashboard gets its answers. The score is how long those answers take. A faster idea only qualifies if its answers pass the checks. [Karpathy’s post](https://x.com/karpathy/status/2029701092347630069) · [Original autoresearch project](https://github.com/karpathy/autoresearch)

**Is this like GEPA?** Both use feedback to choose another experiment. In the GEPA paper, an AI reads traces of what happened, edits prompts, and can combine ideas from candidates with different strengths. This runner keeps one speed winner. Quick reads the trial history and proposes the next SQL experiment itself. [GEPA paper](https://arxiv.org/abs/2507.19457) · [Selection rule](ARCHITECTURE.md#experiment-lifecycle)

To try this with your team, pick a question people ask repeatedly and an answer you trust. Supply a CSV or Parquet file and the queries that produce those answers. To see a checker catch a mistake first, the small orders demo includes a shortcut that drops returned orders. [Run the small demo](../README.md#try-it-without-an-aws-account) · [Use your own data](WORKLOADS.md)
