import json
import subprocess
import sys
from pathlib import Path

from quick_query import engine, orders
from quick_query.util import read, write


def test_orders_materialization_preserves_nulls_and_unseen_regions(tmp_path):
    source = orders.download(tmp_path / 'orders.csv')
    path = Path(engine.create(tmp_path / 'ws', source, orders.workload(), repeats=2)['path'])
    state = engine.Runner(path).run({'action': 'baseline'})
    assert state['job']['status'] == 'idle'
    state = engine.Runner(path).run({'action': 'trial', 'candidate': orders.proposals()[0]})
    assert state['history'][1]['correct']
    # Verify the candidate on held-out cases even when tiny-fixture timing loses.
    state['winner'] = 1
    write(path / 'state.json', state)
    state = engine.Runner(path).run({'action': 'finalize'})
    assert state['sealed'] and read(path / 'final.json')['correct_on_final_cases']


def test_small_demo_installed_cli_and_negative_control(tmp_path):
    workspace = tmp_path / 'workspace'
    source = tmp_path / 'orders.csv'
    result = subprocess.run([sys.executable, '-I', '-m', 'quick_query.cli',
                             '--workspace', str(workspace), 'demo-small', '--data', str(source),
                             '--repeats', '2', '--seconds', '120'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    run = read(workspace / 'latest.json')['run_id']
    state = read(workspace / 'runs' / run / 'state.json')
    assert state['source']['rows'] == 2400
    assert state['history'][2]['status'] == 'rejected'
    assert 'Answer mismatch' in state['history'][2]['error']
    assert read(workspace / 'runs' / run / 'final.json')['correct_on_final_cases']


def test_small_demo_does_not_overwrite_existing_source(tmp_path):
    source = tmp_path / 'orders.csv'
    source.write_text('existing content\n')
    assert orders.download(source) == source.resolve()
    assert source.read_text() == 'existing content\n'
