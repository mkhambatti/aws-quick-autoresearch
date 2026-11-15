// Replay cumulative query times from the two measured median batches.
const replay = document.querySelector('#replay');
const panels = Array.from(replay.querySelectorAll('figure'), figure => ({
  times: JSON.parse(figure.dataset.times),
  clock: figure.querySelector('.clock'),
  finalTime: figure.querySelector('.clock').textContent,
  bars: figure.querySelector('.bars'),
  waiting: figure.querySelector('.waiting'),
  count: figure.querySelector('.query-count'),
}));
const controls = replay.querySelector('.replay-controls');
const play = controls.querySelector('#play');
const finish = controls.querySelector('#finish');
const status = controls.querySelector('[role=status]');
const duration = Math.max(...panels.map(panel => panel.times.at(-1)));
let frame;

function show(seconds) {
  for (const panel of panels) {
    const completed = panel.times.filter(end => end <= seconds).length;
    const ready = completed === panel.times.length;
    panel.clock.textContent = ready ? panel.finalTime : seconds.toFixed(1) + ' s';
    panel.count.textContent = completed + ' of ' + panel.times.length + ' queries finished';
    panel.bars.hidden = !ready;
    panel.waiting.hidden = ready;
  }
}

function showBoth() {
  cancelAnimationFrame(frame);
  show(duration);
  status.textContent = 'Both batches finished. The flight counts match.';
}

finish.addEventListener('click', showBoth);
play.addEventListener('click', () => {
  cancelAnimationFrame(frame);
  const start = performance.now();
  status.textContent = 'Replaying both batches at recorded speed.';
  function tick(now) {
    const elapsed = (now - start) / 1000;
    if (elapsed >= duration) {
      showBoth();
      return;
    }
    show(elapsed);
    frame = requestAnimationFrame(tick);
  }
  tick(start);
});

show(2);
status.textContent = 'Paused at 2 seconds. The prepared batch has finished.';
controls.hidden = false;
