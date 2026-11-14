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
    e = html.escape
    final = read(path/'final.json') if (path/'final.json').exists() else None
    image = base64.b64encode((path/'progress.png').read_bytes()).decode()
    source = state['source']
    local = source['engine']=='local'
    engine_label = 'Local DuckDB · no AWS charges measured' if local else 'Amazon Athena · service-reported metrics'
    stats = ''
    if final and final.get('correct_on_final_cases'):
        stats = f'''<div class="metrics"><div><b>{final['speedup']:.1f}×</b><span>Final workload speedup</span></div><div><b>{final['baseline_seconds']:.3f}s → {final['winner_seconds']:.3f}s</b><span>Unseen cases · median of {state['limits']['repeats']} repeats</span></div><div><b>{final['setup_seconds']:.2f}s</b><span>Winner's one-time preparation</span></div><div><b>Passed</b><span>Exact answers on {final['test_cases']} final cases × {final['queries_per_case']} queries</span></div></div>'''
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
    provenance = 'Airline data: BTS / Data Expo 2009, UC Davis mirror. Historical benchmark; not live travel recommendations.' if state['workload']['name'] == 'Airline Delay Detective' else 'Source: user-registered workload and snapshot.'
    payload = e(json.dumps(final, indent=2)) if final else 'Not finalized'
    doc = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quick Query Autoresearch</title>
<style>body{{margin:0;background:#f5f7fa;color:#172338;font:16px/1.55 system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:44px 24px}}h1{{font-size:44px;letter-spacing:-1.8px;line-height:1.1;margin:12px 0}}h2{{margin-top:36px;font-size:24px}}.tag{{color:#198761;text-transform:uppercase;letter-spacing:2px;font-size:12px;font-weight:700}}.sub,small{{color:#59677b}}small{{display:block}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}}.metrics div{{background:white;border:1px solid #e0e5eb;border-radius:12px;padding:20px}}.metrics b{{font-size:25px;display:block;color:#146247}}.metrics span{{font-size:12px;display:block;margin-top:7px}}img{{width:100%;border-radius:14px}}table{{width:100%;border-collapse:collapse;background:white;font-size:14px}}td,th{{padding:14px;border-bottom:1px solid #e3e8ee;text-align:left;vertical-align:top}}.kept{{color:#137a52}}.rejected,.error{{color:#b63c2d}}.discarded{{color:#687489}}details{{background:white;border:1px solid #e0e5eb;padding:14px;margin:8px 0;border-radius:8px}}summary{{cursor:pointer;font-weight:600}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}footer{{margin-top:30px;font-size:12px;color:#59677b}}@media(max-width:800px){{.metrics{{grid-template-columns:1fr 1fr}}h1{{font-size:34px}}table{{font-size:12px}}td,th{{padding:8px}}}}</style>
<main><div class="tag">Quick Query Autoresearch / measured experiments</div><h1>Same answers.<br>Less waiting.</h1><p class="sub">{e(state['workload']['name'])} · {desc}<br>{engine_label}</p>{stats}<img alt="Measured experiment staircase" src="data:image/png;base64,{image}"><h2>Every attempt, including failures</h2><p>Objective: {metric}. Scores total all training cases and queries. Timings use warm caches; preprocessing, validation and LLM costs are separate. No fabricated delays or scores.</p><table><thead><tr><th>Trial</th><th>Decision</th><th>Score</th><th>Setup</th><th>Hypothesis</th></tr></thead><tbody>{rows}</tbody></table><h2>Winning implementation</h2>{details}<h2>Final verification</h2><details><summary>Measured results and break-even</summary><pre>{payload}</pre></details><footer>Run {e(state['id'])} · {state['spent_seconds']:.1f}s runner work. A finite test suite cannot prove correctness on every possible input. A declining best-so-far line is a selection rule, not a guarantee of future improvements. {provenance}</footer></main></html>'''
    (path/'report.html').write_text(doc)
