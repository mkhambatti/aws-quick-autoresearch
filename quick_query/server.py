import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP, Image
from mcp.types import ToolAnnotations
from . import engine
from .util import read, run_path


def build_server(workspace):
    workspace = Path(workspace).resolve()
    server = FastMCP('Quick Query Autoresearch', instructions='Use only these tools for research. Baseline and trials are asynchronous; poll research_status. Propose SQL and optional materialization. The checker and timing code are immutable. Never claim demo recipes are LLM discoveries. Finalization seals the run.')
    ro = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    rw = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)

    @server.tool(annotations=ro)
    def list_research_runs() -> dict:
        """List runs already registered by the user through the CLI. Does not expose raw data."""
        return {'runs': [{'id': x.parent.name, 'name': read(x)['workload']['name'], 'sealed': read(x)['sealed']} for x in sorted((workspace/'runs').glob('*/state.json'))]}

    @server.tool(annotations=ro)
    def research_status(run_id: str) -> dict:
        """Read schema, training workload, candidate format, measured history and current job; final cases stay hidden."""
        return engine.status(workspace, run_id)

    @server.tool(annotations=rw)
    def start_baseline(run_id: str) -> dict:
        """Measure baseline asynchronously. In Athena runs this spends the preauthorized AWS query budget."""
        return engine.launch(workspace, run_id, 'baseline')

    @server.tool(annotations=rw)
    def submit_experiment(run_id: str, candidate_json: str) -> dict:
        """Submit JSON with hypothesis, queries (same names as baseline), and materialize (null or {sql, compression, row_group_size}). Use data for immutable source and cache for your optional materialization. No arbitrary Python or shell. Poll before submitting again."""
        return engine.launch(workspace, run_id, 'trial', json.loads(candidate_json))

    @server.tool(annotations=rw)
    def stop_research(run_id: str) -> dict:
        """Stop after current bounded query; no source data is changed."""
        return engine.stop(workspace, run_id)

    @server.tool(annotations=rw)
    def finalize_research(run_id: str) -> dict:
        """Seal the run, check untouched parameter cases and remeasure baseline and winner. Further tuning is prohibited; costs use the run's budget."""
        return engine.launch(workspace, run_id, 'finalize')

    @server.tool(annotations=ro, structured_output=False)
    def get_progress_chart(run_id: str) -> Image:
        """Display measured PNG staircase in Quick. No image is available until baseline finishes."""
        path = run_path(workspace, run_id) / 'progress.png'
        if not path.exists():
            raise ValueError('Wait for baseline to finish')
        return Image(data=path.read_bytes(), format='png')

    @server.tool(annotations=ro)
    def get_candidate(run_id: str, trial: int) -> dict:
        """Inspect an existing candidate's SQL to plan the next experiment."""
        path = run_path(workspace, run_id)
        state = read(path/'state.json')
        if not 0 <= trial < len(state['history']):
            raise ValueError('Unknown trial')
        return read(path/state['history'][trial]['directory']/'candidate.json')

    return server
