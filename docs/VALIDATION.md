# Validation record

## Published experiments

The Quick-led flight result was executed on the operator's Mac and exported from its sealed run ledger. The operator's supplied Quick conversation provides planner context. See [results and provenance](RESULTS.md). The prior scripted Linux result is retained separately with its original [environment record](../examples/tested-environment.json).

The publication-time Mac environment is recorded in [publication-environment.json](../examples/quick-led/publication-environment.json); it is not asserted to be a capture taken at the start of the earlier run.

## Automated checks

The suite covers exact results, nulls and duplicate preservation, large integer fingerprints, wrong-answer rejection, held-out failure and sealing, source mutation, SQL restrictions, external file restrictions, timeouts, worker locking, CLI execution, setup behavior, and the optional Athena adapter's stubbed API contract. MCP tests exercise a real stdio handshake, tool discovery, an asynchronous experiment, finalization, and chart retrieval.

The new orders path is tested using the installed package from outside the checkout, including rejection of a deliberately wrong candidate. Its materialized candidate is also checked on held-out regions and empty results, independent of whether tiny-fixture timings happen to select it.

Run `.venv/bin/python -m pytest -q`. CI repeats the suite on macOS and Linux with Python 3.11, 3.12, and 3.13. The GitHub status is the source of truth for those hosted runs; configuring the matrix does not imply every combination has already passed.

## Limits of validation

Live Athena execution, AWS bill reduction, remote MCP hosting, multi-user isolation, Windows-native execution, production dashboard deployment, and future Quick releases have not been established by these results. Athena tests use stubbed service responses. SQL correctness is checked on finite cases, not formally proven. The SQL policy and local engine controls have tests but are not a security certification.
