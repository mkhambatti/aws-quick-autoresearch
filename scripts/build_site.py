"""Build a static GitHub Pages site from curated public evidence only."""
import html
from itertools import accumulate
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'site'
OUT.mkdir(exist_ok=True)
repo = os.environ.get('GITHUB_REPOSITORY', 'mkhambatti/aws-quick-autoresearch')
# Never copy workspaces/, data/, connector configuration, or local workload files.
for name in ['quick-led', 'measured']:
    shutil.copytree(ROOT / 'examples' / name, OUT / 'results' / name, dirs_exist_ok=True)
final = json.loads((ROOT / 'examples/quick-led/final.json').read_text())
history = json.loads((ROOT / 'examples/quick-led/history.json').read_text())
evidence = ROOT / 'examples/quick-led'
measurements = json.loads((evidence / 'final-measurements.json').read_text())
batch_size = final['test_cases'] * final['queries_per_case']


def replay_times(role):
    """Find the recorded repetition behind the published median batch time."""
    times = [m['seconds'] for m in measurements if m['role'] == role]
    for start in range(0, len(times), batch_size):
        ends = list(accumulate(times[start:start + batch_size]))
        if len(ends) == batch_size and abs(ends[-1] - final[f'{role}_seconds']) < 1e-9:
            return json.dumps(ends)
    raise ValueError(f'Missing recorded median batch for {role}')


routes = json.loads((evidence / 'route-preview.json').read_text())['routes']
largest = max(row['delayed_flights'] for row in routes)
bars = ''.join(
    f'<li><span>{html.escape(row["destination"])}</span>'
    f'<span class="track"><i style="width:{row["delayed_flights"] / largest:.2%}"></i></span>'
    f'<span>{row["delayed_flights"]}</span></li>' for row in routes
)
rows = ''.join(
    f"<tr><td>{r['trial']}</td><td>{html.escape(r['hypothesis'])}</td><td>{r['status']}</td><td>{r['score']:.5f}</td></tr>"
    for r in history
)
template = (ROOT / 'docs/site/index.html').read_text()
values = {'REPO': html.escape(repo), 'SPEEDUP': f"{final['speedup']:,.1f}",
          'BASELINE': f"{final['baseline_seconds']:.4f}", 'WINNER': f"{final['winner_seconds']:.5f}",
          'SETUP': f"{final['setup_seconds']:.3f}", 'DIRECTORY': html.escape(repo.split('/')[-1]), 'ROWS': rows}
for key, value in values.items():
    template = template.replace('@@' + key + '@@', value)
template = template.replace('@@BARS@@', bars)
for role in ('baseline', 'winner'):
    template = template.replace(f'@@{role.upper()}_TIMES@@', replay_times(role))
shutil.copyfile(ROOT / 'docs/site/replay.js', OUT / 'replay.js')
(OUT / 'index.html').write_text(template)
(OUT / '.nojekyll').touch()
print(f'Built {OUT}/index.html from curated examples; no runtime data included.')
