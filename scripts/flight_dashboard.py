"""Render public flight panel answers and the timings from the recorded median runs."""
from html import escape
from itertools import accumulate
import json
import shutil

AIRPORTS = {
    'LGA': 'New York LaGuardia', 'DFW': 'Dallas/Fort Worth', 'EWR': 'Newark',
    'ANC': 'Anchorage', 'DEN': 'Denver', 'LAX': 'Los Angeles',
}
AIRLINES = {
    'AA': 'American', 'MQ': 'American Eagle', 'OO': 'SkyWest', 'EV': 'Atlantic Southeast',
    'DL': 'Delta', 'FL': 'AirTran', 'AS': 'Alaska', 'WN': 'Southwest', 'YV': 'Mesa',
    'XE': 'ExpressJet',
}
REPORTS = {'ORD': 'Chicago O’Hare', 'ATL': 'Atlanta', 'SEA': 'Seattle–Tacoma'}
MONTHS = {2: 'February', 8: 'August', 12: 'December'}
DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def median_trace(measurements, role, final):
    size = final['test_cases'] * final['queries_per_case']
    records = [m for m in measurements if m['role'] == role]
    for start in range(0, len(records), size):
        batch = records[start:start + size]
        ends = list(accumulate(m['seconds'] for m in batch))
        if len(ends) == size and abs(ends[-1] - final[f'{role}_seconds']) < 1e-9:
            return [[m['case'], m['query'], end] for m, end in zip(batch, ends)]
    raise ValueError(f'Missing recorded median batch for {role}')


def ranking(values, names):
    maximum = max(values.values())
    return '<ol class="ranks">' + ''.join(
        f'<li><span>{escape(names.get(code, code))}</span><b>{n:,}</b>'
        f'<i aria-hidden="true" style="width:{100 * n / maximum:.2f}%"></i></li>'
        for code, n in values.items()
    ) + '</ol>'


def hour_chart(values):
    peak = max(values, key=values.get)
    maximum = values[peak]
    bars = []
    for hour in range(24):
        n = values.get(str(hour), 0)
        label = f'{hour:02d}:00 · {n:,} late arrivals'
        bars.append(f'<li title="{label}" aria-label="{label}"><i style="height:{100*n/maximum:.2f}%"></i></li>')
    rows = ''.join(f'<tr><th>{h:02d}:00</th><td>{values.get(str(h), 0):,}</td></tr>' for h in range(24))
    return (f'<p class="peak"><b>{int(peak):02d}:00</b> departures had the most late arrivals '
            f'({maximum:,} flights).</p><ol class="hours">{"".join(bars)}</ol>'
            '<div class="axis" aria-hidden="true"><span>00:00</span><span>06:00</span>'
            '<span>12:00</span><span>18:00</span></div>'
            f'<details><summary>Hourly counts</summary><table><tr><th>Departure hour</th><th>Late arrivals</th></tr>{rows}</table></details>')


def panel(key, title, unit, content):
    return (f'<section class="panel {key}" data-query="{key}"><h3>{title}</h3><p class="unit">{unit}</p>'
            f'<div class="answer">{content}</div><p class="pending" hidden>Waiting for this answer…</p></section>')


def report(case, index):
    t = case['totals']
    summary = ''.join(f'<div><dt>{label}</dt><dd>{t[key]:,}</dd></div>'
                      for key, label in [('flights', 'Scheduled flights'), ('delayed_flights', 'Arrived late'),
                                         ('cancellations', 'Cancelled')])
    weekdays = ''.join(f'<li><span>{DAYS[int(k)-1]}</span><b>{v:,}</b></li>' for k, v in case['weekdays'].items())
    panels = [
        panel('departure_hours', 'When did late flights depart?', 'Late arrivals by scheduled departure hour · local time', hour_chart(case['departure_hours'])),
        panel('routes', 'Which destinations had the most late arrivals?', 'Top three destinations · flights', ranking(case['routes'], AIRPORTS)),
        panel('weekdays', 'Which days saw the most delays?', 'Late arrivals by departure weekday · monthly totals', f'<ul class="days">{weekdays}</ul>'),
        panel('carriers', 'Which airlines cancelled the most flights?', 'Departures from this airport · top three by count', ranking(case['carriers'], AIRLINES)),
        panel('national_carriers', 'Who had the most cancellations nationwide?', 'All U.S. origins this month · top three by count', ranking(case['national_carriers'], AIRLINES)),
    ]
    name = REPORTS[case['origin']]
    month = MONTHS[case['month']]
    hidden = ' hidden' if index else ''
    return (f'<article data-case="{index}"{hidden}><div class="report-title"><h2>{name}</h2>'
            f'<p>{month} 2008 departures · {case["origin"]}</p></div>'
            f'<dl class="totals" data-query="routes">{summary}</dl>'
            f'<div class="questions">{"".join(panels)}</div></article>')


def build_dashboard(source, out, evidence, final, repo):
    cases = json.loads((evidence / 'dashboard-preview.json').read_text())
    workload = json.loads((evidence / 'workload.json').read_text())
    measurements = json.loads((evidence / 'final-measurements.json').read_text())
    options, articles = [], []
    for c in cases:
        index = workload['test_cases'].index({'month': c['month'], 'origin': c['origin']})
        options.append(f'<option value="{index}">{REPORTS[c["origin"]]} · {MONTHS[c["month"]]} 2008</option>')
        articles.append(report(c, index))
    trace = {role: median_trace(measurements, role, final) for role in ('baseline', 'winner')}
    page = (source / 'flight-operations.html').read_text()
    for token, value in {'REPORTS': ''.join(articles), 'OPTIONS': ''.join(options), 'TRACE': json.dumps(trace),
                         'BASELINE': f"{final['baseline_seconds']:.2f} s",
                         'WINNER': f"{final['winner_seconds']*1000:.0f} ms", 'REPO': escape(repo)}.items():
        page = page.replace(f'@@{token}@@', value)
    (out / 'flight-operations.html').write_text(page)
    for asset in ('flight-operations.css', 'replay.js'):
        shutil.copyfile(source / asset, out / asset)
