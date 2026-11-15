const traces = JSON.parse(document.querySelector('#trace').textContent);
const reports = [...document.querySelectorAll('article[data-case]')];
const airport = document.querySelector('#airport');
const progress = document.querySelector('progress');
const label = document.querySelector('#progress');
const status = document.querySelector('[role=status]');
const skip = document.querySelector('#skip');
let role = 'winner';
let completed = traces.winner.length;
let timer;

for (const value of document.querySelectorAll('.totals dd')) {
  value.dataset.result = value.textContent;
}

function draw() {
  const trace = traces[role];
  const report = reports.find(item => item.dataset.case === airport.value);
  for (const item of reports) item.hidden = item !== report;
  const ready = new Set(trace.slice(0, completed)
    .filter(([index]) => index === Number(airport.value)).map(([, query]) => query));
  for (const panel of report.querySelectorAll('.panel')) {
    const available = ready.has(panel.dataset.query);
    panel.querySelector('.answer').hidden = !available;
    panel.querySelector('.pending').hidden = available;
  }
  for (const value of report.querySelectorAll('.totals dd')) {
    value.textContent = ready.has('routes') ? value.dataset.result : '…';
  }
  const mode = role === 'baseline' ? 'Before' : 'After';
  label.textContent = mode + ' · ' + completed + ' of ' + trace.length + ' queries finished';
  progress.value = completed;
  skip.disabled = completed === trace.length;
}

function play(nextRole) {
  clearTimeout(timer);
  role = nextRole;
  completed = 0;
  const trace = traces[role];
  const start = performance.now();
  status.textContent = role === 'baseline' ? 'Replaying original queries.' : 'Replaying prepared totals.';
  function advance() {
    const elapsed = performance.now() - start;
    while (completed < trace.length && trace[completed][2] * 1000 <= elapsed) completed++;
    draw();
    if (completed < trace.length) {
      timer = setTimeout(advance, Math.ceil(trace[completed][2] * 1000 - elapsed));
    } else {
      status.textContent = 'All reports are ready.';
    }
  }
  advance();
}

airport.addEventListener('change', draw);
document.querySelector('#before').addEventListener('click', () => play('baseline'));
document.querySelector('#after').addEventListener('click', () => play('winner'));
skip.addEventListener('click', () => {
  clearTimeout(timer);
  completed = traces[role].length;
  draw();
  status.textContent = 'Showing all completed answers.';
});
for (const control of document.querySelectorAll('.controls')) control.hidden = false;
draw();
