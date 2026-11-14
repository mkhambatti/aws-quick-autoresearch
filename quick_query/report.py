import base64
import html
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .util import read


def report(path):
    path = Path(path)
    state = read(path / 'state.json')
    history = state['history']
    if not history:
        return
    metric = state['objective']
    fig, ax = plt.subplots(figsize=(13, 6.4))
    fig.patch.set_facecolor('#f9fafb')
    ax.set_facecolor('#ffffff')
    x = [r['trial'] for r in history]
    best = [r['running_best'] for r in history]
    ax.step(x, best, where='post', color='#198761', lw=2.3, label='Running best')
    for status, color, label in [('discarded', '#a6adb7', 'Discarded'), ('kept', '#28a477', 'Kept')]:
        rows = [r for r in history if r['status'] == status and r.get('score') is not None]
        ax.scatter([r['trial'] for r in rows], [r['score'] for r in rows], color=color, edgecolor='white', s=65, zorder=4, label=label)
    for r in history:
        if r['status'] == 'kept':
            label = 'Baseline' if r['trial'] == 0 else f"Trial {r['trial']}: " + r['hypothesis'][:34] + '…'
            ax.annotate(label, (r['trial'], r['score']), xytext=(7, 13), textcoords='offset points', fontsize=9, color='#126549')
    rejected = [r['trial'] for r in history if r['status'] == 'rejected']
    if rejected:
        ax.scatter(rejected, [best[-1]]*len(rejected), marker='x', color='#dc563d', s=65, label='Rejected (no valid score)')
    positive = [r['score'] for r in history if r.get('score') and r['score'] > 0]
    log = bool(positive and max(positive)/min(positive) > 15)
    if log:
        ax.set_yscale('log')
    ax.set_ylabel(('Dashboard workload seconds' if metric == 'seconds' else 'Bytes scanned per workload') + (' · logarithmic scale' if log else '') + '\nLower is better')
    ax.set_xlabel('Experiment number')
    ax.set_xticks(x)
    ax.set_xlim(-0.35, max(x)+0.7)
    ax.grid(True, alpha=.17)
    ax.legend(loc='upper right', fontsize=9)
    improvements = sum(r['status']=='kept' for r in history)-1
    ax.set_title(f'Query Autoresearch: {len(history)} experiments · {improvements} kept improvements', fontsize=17, loc='left', pad=25)
    fig.text(.09, .015, 'Measured on fixed data. Every timed answer checked. Setup cost excluded and reported separately.', fontsize=9, color='#627085')
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(path/'progress.png', dpi=170)
    fig.savefig(path/'progress.svg')
    plt.close(fig)
    render_html(path, state)


def render_html(path, state):
    history = state['history']
    metric = state['objective']
    e = html.escape
    final = read(path/'final.json') if (path/'final.json').exists() else None
    image = base64.b64encode((path/'progress.png').read_bytes()).decode()
    source = state['source']
    local = source['engine']=='local'
    engine_label = 'Local DuckDB · no AWS charges measured' if local else 'Amazon Athena · service-reported metrics'
    stats = ''
    if final and final.get('correct_on_final_cases'):
        stats = f'''<table class="metrics"><caption>Held-out batch</caption><tbody>
<tr><th scope="row">Query time</th><td>{final['baseline_seconds']:.4f}s → {final['winner_seconds']:.5f}s</td></tr>
<tr><th scope="row">Speedup</th><td>{final['speedup']:,.1f}×</td></tr>
<tr><th scope="row">Repetitions</th><td>Median of {state['limits']['repeats']} batch timings per implementation</td></tr>
<tr><th scope="row">Verified answers</th><td>{final['test_cases']} held-out cases × {final['queries_per_case']} queries, all matched</td></tr>
<tr><th scope="row">Preparation</th><td>{final['setup_seconds']:.3f}s</td></tr>
</tbody></table>'''
    elif final:
        stats = '<p class="error">Final verification failed. Do not deploy this candidate.</p>'
    else:
        stats = '<p>Research in progress. Final unseen cases have not been opened.</p>'
    rows = ''
    for r in history:
        score = '—' if r.get('score') is None else f"{r['score']:.6g}"
        setup = r.get('setup',{}).get('seconds')
        prep = '—' if setup is None else f'{setup:.2f}s'
        rows += f"<tr><td>{r['trial']}</td><td><span class='{r['status']}'>{e(r['status'])}</span></td><td>{score}</td><td>{prep}</td><td>{e(r['hypothesis'])}<small>{e(r.get('error',''))}</small></td></tr>"
    winner = read(path / history[state['winner']]['directory'] / 'candidate.json')
    details = ''.join(f'<details><summary>{e(name)}</summary><pre>{e(sql)}</pre></details>' for name,sql in winner['queries'].items())
    if winner.get('materialize'):
        details = '<details open><summary>One-time preparation SQL</summary><pre>'+e(winner['materialize']['sql'])+'</pre></details>'+details
    desc = f"{source.get('rows', 'Enterprise')} rows · {source.get('size_bytes', 0)/1e6:.1f} MB original input" if local else 'Snapshot: '+e(source['snapshot_id'])
    provenance = 'Flight data from BTS / Data Expo 2009, UC Davis mirror.' if state['workload']['name'] == 'Airline Delay Detective' else 'Source: user-registered workload and snapshot.'
    payload = e(json.dumps(final, indent=2)) if final else 'Not finalized'
    title = e(state['workload']['name'])
    conditions = ('Local DuckDB with warm caches.' if local
                  else 'Athena timings and scan counts come from the service.')
    doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Experiment report</title>
<style>
* {{box-sizing:border-box}}
body {{background:white;color:#191d21;font:16px/1.5 system-ui,sans-serif;margin:0}}
main {{width:min(100% - 32px,1020px);margin:auto;padding:20px 0 32px}}
header {{border-bottom:1px solid #191d21;padding-bottom:10px}}
h1 {{font-size:clamp(28px,4vw,42px);line-height:1.15;letter-spacing:-.04em;margin:0 0 4px}}
h2 {{font-size:22px;letter-spacing:-.025em;margin:20px 0 8px}}
p {{margin:8px 0;max-width:85ch}} code,pre,.metrics td {{font-family:ui-monospace,monospace}}
table {{border-collapse:collapse;width:100%;font-size:14px}}
caption {{font-weight:650;font-size:18px;text-align:left;padding:12px 0 5px}}
th,td {{text-align:left;vertical-align:top;border-bottom:1px solid #c6cbd1;padding:6px 10px}}
.metrics {{border:1px solid #b9c0c6}} .metrics th {{width:24%}} .metrics td {{font-variant-numeric:tabular-nums}}
.metrics tr:first-child td {{font-size:18px;font-weight:650}}
.scroll {{overflow-x:auto}} .note,.error {{border-left:2px solid #747d86;padding-left:12px;color:#49515b}}
small {{display:block}} details {{border-top:1px solid #c6cbd1;padding:7px 0}}
summary {{cursor:pointer;color:#124c96}} :focus-visible {{outline:2px solid #124c96}}
img {{width:100%;height:auto}} pre {{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}
footer {{border-top:1px solid #191d21;margin-top:20px;padding-top:10px;font-size:13px}}
</style></head><body><main>
<header><h1>{title}</h1><code>{e(state['id'])}</code><p>{engine_label} · {desc}</p></header>
{stats}
<p class="note">{conditions} The query-time ratio excludes preparation and research time. Answer checks cover the registered cases. Rebuild summaries after a source change.</p>
<h2>Training trials</h2><p>Score in {e(metric)} across all training cases and queries. Rejected trials have no benchmark score.</p>
<div class="scroll"><table><thead><tr><th>Trial</th><th>Decision</th><th>Score</th><th>Setup</th><th>Hypothesis</th></tr></thead><tbody>{rows}</tbody></table></div>
<details><summary>Training chart</summary><img alt="Training scores and the running best by trial" src="data:image/png;base64,{image}"></details>
<h2>Selected SQL</h2>{details}<h2>Final verification</h2>
<details><summary>Batch samples and break-even calculation</summary><pre>{payload}</pre></details>
<footer>{state['spent_seconds']:.1f}s recorded runner time. {provenance}</footer></main></body></html>'''
    (path / 'report.html').write_text(doc)
