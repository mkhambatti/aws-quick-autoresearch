"""Build a static GitHub Pages site from curated public evidence only."""
import html
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
(OUT / 'index.html').write_text(template)
(OUT / '.nojekyll').touch()
print(f'Built {OUT}/index.html from curated examples; no runtime data included.')
