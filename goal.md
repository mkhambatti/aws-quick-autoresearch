# Research contract

Goal: reduce the registered workload's measured objective while preserving every reference answer.

Read `research_status` through MCP. Change only candidate SELECT SQL and optional materialization settings. Use `data` for the fixed source and `cache` for the candidate's derived table. Submit a hypothesis, poll completion, inspect feedback, then choose the next experiment. Consider projection, predicate placement, row layout, compression, reusable aggregates and work already performed by the query optimizer. Reject changes that merely hide rows or hardcode known answers.

The workload, source snapshot, checker, timers and scoring rules are owned by the user. Do not edit them, read hidden cases, disable correctness tests or inflate measured improvement. Do not run shell commands or arbitrary Python to escape the tool contract.

Prefer a few informative experiments over maximizing trial count. Stop at the budget or after three consecutive non-improvements. Leave enough time and cloud-query budget for final evaluation. Finalize once, show the actual chart and distinguish measured local performance from measured Athena cost. Report one-time setup, final-case verification and failures. Never promise a particular percentage improvement, formal SQL equivalence, a viral outcome or unattended operation beyond the host's limits.
