# Contributing

Fork the repository, clone your fork, and run `bash scripts/setup.sh`. Run `.venv/bin/python -m pytest -q` before opening a pull request. For code changes, reinstall with `.venv/bin/python -m pip install --no-deps .`; setup installs a regular package so the MCP executable also works outside the checkout.

Keep domain-specific schemas and proposals in demo modules and `examples/`. The runner must accept a user-owned workload without importing a domain schema into its correctness rules. Add a small fixture for a new adapter or correctness rule. Do not use full flight downloads in unit tests.

Describe the problem, behavior change, and validation in the pull request. Performance claims need the source snapshot, query workload, repeated measurements, setup cost, and failed attempts. Do not commit runtime workspaces, credentials, generated connector configuration, or private data.
