import fcntl
import json
import os
import re
import statistics
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from .local import LocalEngine, inspect_source
from .sql import render, signature, validate
from .util import digest, read, run_path, write


def create(workspace, source_path, workload, *, aws=None, trials=12, repeats=3,
           timeout=90, seconds=3600, objective='seconds', minimum_gain=0.03, nullstr='NA'):
    if not (2 <= trials <= 100 and 2 <= repeats <= 9 and 1 <= timeout <= 600 and 30 <= seconds <= 86400):
        raise ValueError('Bounds: trials 2..100, repeats 2..9, timeout 1..600, seconds 30..86400')
    if objective not in {'seconds', 'bytes_scanned'} or (not aws and objective != 'seconds'):
        raise ValueError('Local objective is seconds; Athena supports seconds or bytes_scanned')
    if not 0 <= minimum_gain < 1:
        raise ValueError('minimum_gain must be 0..1')
    if not isinstance(workload.get('name'), str) or not workload['name'].strip():
        raise ValueError('Workload requires a nonempty name')
    if not workload.get('queries') or not workload.get('train_cases') or not workload.get('test_cases'):
        raise ValueError('Workload requires queries, train_cases and test_cases')
    if len(workload['queries']) > 20 or len(workload['train_cases']) > 20 or len(workload['test_cases']) > 20:
        raise ValueError('At most 20 queries / training cases / test cases')
    dialect = 'trino' if aws else 'duckdb'
    for case in workload['train_cases'] + workload['test_cases']:
        for sql in workload['queries'].values():
            validate(render(sql, case), tables=('data',), dialect=dialect)
    if aws:
        required = ['region', 'workgroup', 'database', 'table', 'snapshot_id', 'max_queries', 'max_bytes_per_query', 'usd_per_tb']
        if any(k not in aws for k in required):
            raise ValueError(f'AWS config requires {required}')
        for k in ('database', 'table'):
            if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', aws[k]):
                raise ValueError(f'Invalid AWS identifier: {k}')
        if not 1 <= aws['max_queries'] <= 10000 or not 10000000 <= aws['max_bytes_per_query'] <= 100000000000:
            raise ValueError('AWS query/scan bounds outside allowed range')
        if not 0 < aws['usd_per_tb'] < 1000:
            raise ValueError('Invalid USD/TB estimate')
        source = dict(aws, engine='athena')
    else:
        source = inspect_source(source_path, nullstr)
        source.update(engine='local', sha256=digest(source_path))
    run_id = 'query-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    path = Path(workspace).resolve() / 'runs' / run_id
    path.mkdir(parents=True)
    state = {'id': run_id, 'source': source, 'workload': workload,
             'limits': {'trials': trials, 'repeats': repeats, 'query_timeout': timeout, 'seconds': seconds},
             'objective': objective, 'minimum_gain': minimum_gain, 'spent_seconds': 0.0,
             'history': [], 'winner': None, 'sealed': False, 'job': {'status': 'idle'}}
    write(path / 'state.json', state)
    return {'run_id': run_id, 'path': str(path), 'source': source}


@contextmanager
def lock(path, existing_fd=None):
    fd = existing_fd if existing_fd is not None else os.open(path / '.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
    except BlockingIOError:
        raise ValueError('An experiment is already running') from None
    finally:
        os.close(fd)


def launch(workspace, run_id, action, candidate=None):
    path = run_path(workspace, run_id)
    with lock(path) as fd:
        state = read(path / 'state.json')
        if state['sealed']:
            raise ValueError('Run is sealed; create a new run to research again')
        if action not in {'baseline', 'trial', 'finalize'}:
            raise ValueError('Unknown action')
        if action == 'trial' and state['winner'] is None:
            raise ValueError('Run baseline first')
        if action == 'baseline' and state['history']:
            raise ValueError('Baseline already exists')
        if action != 'finalize' and len(state['history']) >= state['limits']['trials']:
            raise ValueError('Trial budget exhausted; finalize the run')
        if state['spent_seconds'] >= state['limits']['seconds']:
            raise ValueError('Run time budget exhausted')
        (path / '.stop').unlink(missing_ok=True)
        write(path / 'request.json', {'action': action, 'candidate': candidate})
        state['job'] = {'status': 'running', 'action': action, 'started': time.time()}
        write(path / 'state.json', state)
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path(__file__).resolve().parent.parent) + os.pathsep + env.get('PYTHONPATH', '')
        with (path / 'worker.log').open('a') as log:
            process = subprocess.Popen([sys.executable, '-m', 'quick_query.worker', str(path), str(fd)],
                                       pass_fds=(fd,), start_new_session=True, stdout=log, stderr=log, env=env)
        # The child inherited the locked file description; closing the parent keeps the lock held.
        return {'run_id': run_id, 'status': 'running', 'pid': process.pid}


def status(workspace, run_id):
    path = run_path(workspace, run_id)
    state = read(path / 'state.json')
    try:
        with lock(path):
            state = read(path / 'state.json')
            if state['job']['status'] == 'running':
                state['job'] = {'status': 'error', 'error': 'Worker interrupted. Retry the operation; finalization remains sealed if started.'}
                write(path / 'state.json', state)
    except ValueError:
        # Keep polling until the worker releases the lock, including report rendering.
        state['job'] = dict(state['job'], status='running')
    public = {k: v for k, v in state.items() if k != 'workload'}
    public['workload'] = {k: v for k, v in state['workload'].items() if k != 'test_cases'}
    public['path'] = str(path)
    public['candidate_format'] = {'hypothesis': 'Why this may improve the objective',
                                  'queries': state['workload']['queries'],
                                  'materialize': {'sql': 'SELECT * FROM data', 'compression': 'zstd'}}
    if (path / 'final.json').exists():
        public['final'] = read(path / 'final.json')
    if (path / 'aws-usage.json').exists():
        usage = read(path / 'aws-usage.json')
        public['aws_submitted_queries'] = usage['submitted']
    return public


def stop(workspace, run_id):
    path = run_path(workspace, run_id)
    (path / '.stop').touch()
    return {'status': 'stop requested; current query finishes or reaches its timeout'}


class Runner:
    def __init__(self, path):
        self.path = Path(path)
        self.state = read(self.path / 'state.json')
        self.start = time.monotonic()
        self.deadline = self.start + self.state['limits']['seconds'] - self.state['spent_seconds']
        self.engines = []

    def check(self):
        if (self.path / '.stop').exists():
            raise InterruptedError('Stop requested')
        if time.monotonic() >= self.deadline:
            raise TimeoutError('Run time budget exhausted')

    def engine(self, directory, attach=False):
        directory.mkdir(exist_ok=True)
        source = self.state['source']
        if source['engine'] == 'local':
            cls, cache = LocalEngine, directory / 'cache.parquet'
        else:
            from .athena import AthenaEngine
            cls, cache = AthenaEngine, directory / 'cache.json'
        obj = cls(source, cache, timeout=self.state['limits']['query_timeout'])
        self.engines.append(obj)
        if attach:
            obj.attach_cache()
        return obj

    def query(self, engine, sql):
        self.check()
        engine.timeout = min(self.state['limits']['query_timeout'], max(0.1, self.deadline - time.monotonic()))
        return engine.query(sql)

    def execute_set(self, engine, queries, cases, expected=None):
        totals = {'seconds': 0.0, 'bytes_scanned': 0, 'estimated_scan_usd': 0.0}
        signatures = {}
        details = []
        for ci, params in enumerate(cases):
            for name, sql in queries.items():
                result = self.query(engine, render(sql, params))
                key = f'{ci}:{name}'
                signatures[key] = signature(result)
                if expected is not None and signatures[key] != expected[key]:
                    raise ValueError(f'Answer mismatch in {name}, case {ci}; candidate rejected')
                for k in totals:
                    totals[k] += result.get(k) or 0
                details.append({k: v for k, v in result.items() if k != 'rows'} | {'case': ci, 'query': name})
        if self.state['source']['engine'] == 'local':
            totals['bytes_scanned'], totals['estimated_scan_usd'] = None, None
        return totals, signatures, details

    def baseline(self):
        directory = self.path / 'trial-000'
        engine = self.engine(directory)
        workload = self.state['workload']
        candidate = {'hypothesis': 'Baseline: unchanged source and dashboard SQL', 'queries': workload['queries'], 'materialize': None}
        write(directory / 'candidate.json', candidate)
        _, expected, _ = self.execute_set(engine, candidate['queries'], workload['train_cases'])
        write(self.path / 'reference.json', expected)
        samples, details = [], []
        for _ in range(self.state['limits']['repeats']):
            metrics, _, d = self.execute_set(engine, candidate['queries'], workload['train_cases'], expected)
            samples.append(metrics)
            details.extend(d)
        metric = self.state['objective']
        score = statistics.median(s[metric] for s in samples)
        record = {'trial': 0, 'hypothesis': candidate['hypothesis'], 'status': 'kept', 'score': score,
                  'running_best': score, 'samples': samples, 'setup': {'seconds': 0, 'storage_bytes': 0},
                  'directory': directory.name, 'correct': True}
        write(directory / 'measurements.json', details)
        self.state['history'].append(record)
        self.state['winner'] = 0

    def trial(self, candidate):
        idx = len(self.state['history'])
        if idx >= self.state['limits']['trials']:
            raise ValueError('Trial budget exhausted')
        directory = self.path / f'trial-{idx:03d}'
        directory.mkdir(exist_ok=True)
        write(directory / 'candidate.json', candidate)
        best = self.state['history'][self.state['winner']]
        record = {'trial': idx, 'hypothesis': str(candidate.get('hypothesis', 'Untitled'))[:1000],
                  'status': 'rejected', 'score': None, 'running_best': best['running_best'],
                  'directory': directory.name, 'correct': False}
        try:
            if set(candidate) - {'hypothesis', 'queries', 'materialize'}:
                raise ValueError('Unknown candidate key')
            if set(candidate['queries']) != set(self.state['workload']['queries']):
                raise ValueError('Candidate must supply exactly the baseline query names')
            obj = self.engine(directory)
            self.check()
            obj.timeout = min(self.state['limits']['query_timeout'], max(0.1, self.deadline-time.monotonic()))
            setup = obj.materialize(candidate.get('materialize'))
            record['setup'] = setup
            expected = read(self.path / 'reference.json')
            cases = self.state['workload']['train_cases']
            self.execute_set(obj, candidate['queries'], cases, expected)
            record['correct'] = True
            best_dir = self.path / best['directory']
            incumbent = read(best_dir / 'candidate.json')
            other = self.engine(best_dir, attach=bool(incumbent.get('materialize')))
            samples, comparison, details = [], [], []
            # Alternate execution order. Validation above serves as a warm-up.
            self.execute_set(other, incumbent['queries'], cases, expected)
            for i in range(self.state['limits']['repeats']):
                tasks = [(obj, candidate, samples, 'candidate'), (other, incumbent, comparison, 'incumbent')]
                if (idx + i) % 2:
                    tasks.reverse()
                for eng, config, dest, role in tasks:
                    metrics, _, d = self.execute_set(eng, config['queries'], cases, expected)
                    dest.append(metrics)
                    details.extend([x | {'role': role} for x in d])
            metric = self.state['objective']
            score = statistics.median(s[metric] for s in samples)
            paired = statistics.median(s[metric] for s in comparison)
            record.update(score=score, samples=samples, incumbent_samples=comparison,
                          paired_incumbent_score=paired)
            # Both original best and paired incumbent must improve; no cache-only timing wins.
            threshold = min(best['running_best'], paired) * (1 - self.state['minimum_gain'])
            if score < threshold:
                record.update(status='kept', running_best=score)
                self.state['winner'] = idx
            else:
                record['status'] = 'discarded'
            write(directory / 'measurements.json', details)
        except Exception as e:
            record['error'] = f'{type(e).__name__}: {e}'
        self.state['history'].append(record)

    def finalize(self):
        if self.state['winner'] is None:
            raise ValueError('No baseline yet')
        # Seal before revealing untouched parameter cases. Failure also seals the run.
        self.state['sealed'] = True
        write(self.path / 'state.json', self.state)
        baseline = self.state['history'][0]
        best = self.state['history'][self.state['winner']]
        bdir, wdir = self.path / baseline['directory'], self.path / best['directory']
        bc, wc = read(bdir / 'candidate.json'), read(wdir / 'candidate.json')
        be = self.engine(bdir)
        we = self.engine(wdir, attach=bool(wc.get('materialize')))
        cases = self.state['workload']['test_cases']
        _, expected, _ = self.execute_set(be, bc['queries'], cases)
        self.execute_set(we, wc['queries'], cases, expected)
        bs, ws, details = [], [], []
        for i in range(self.state['limits']['repeats']):
            tasks = [(be, bc, bs, 'baseline'), (we, wc, ws, 'winner')]
            if i % 2:
                tasks.reverse()
            for eng, config, samples, label in tasks:
                metrics, _, d = self.execute_set(eng, config['queries'], cases, expected)
                samples.append(metrics)
                details.extend([x | {'role': label} for x in d])
        b = statistics.median(x['seconds'] for x in bs)
        w = statistics.median(x['seconds'] for x in ws)
        setup = best['setup']['seconds']
        result = {'correct_on_final_cases': True, 'winner_trial': best['trial'],
                  'test_cases': len(cases), 'queries_per_case': len(bc['queries']),
                  'baseline_seconds': b, 'winner_seconds': w,
                  'speedup': b / w if w else None, 'reduction_pct': (b-w)/b*100 if b else None,
                  'setup_seconds': setup, 'break_even_test_workloads': __import__('math').ceil(setup/(b-w)) if b>w else None,
                  'baseline_samples': bs, 'winner_samples': ws,
                  'note': 'Exact answers on finite unseen parameter cases, not a proof of SQL equivalence. Warm-cache benchmark; no statistical significance claim. Setup and research costs excluded from steady-state timing.'}
        if self.state['source']['engine'] == 'athena':
            bbytes = statistics.median(x['bytes_scanned'] for x in bs)
            wbytes = statistics.median(x['bytes_scanned'] for x in ws)
            bcost = statistics.median(x['estimated_scan_usd'] for x in bs)
            wcost = statistics.median(x['estimated_scan_usd'] for x in ws)
            setup_cost = best['setup'].get('estimated_scan_usd', 0)
            ledger = read(self.path / 'aws-usage.json')
            result.update(baseline_scanned_bytes=bbytes, winner_scanned_bytes=wbytes,
                          scan_reduction_pct=(bbytes-wbytes)/bbytes*100 if bbytes else None,
                          baseline_estimated_scan_usd=bcost, winner_estimated_scan_usd=wcost,
                          setup_estimated_scan_usd=setup_cost,
                          estimated_scan_break_even_workloads=__import__('math').ceil(setup_cost/(bcost-wcost)) if bcost>wcost else None,
                          research_queries_submitted=ledger['submitted'],
                          research_observed_scanned_bytes=sum(x.get('statistics',{}).get('DataScannedInBytes',0) for x in ledger['executions']))
        write(self.path / 'final.json', result)
        write(self.path / 'final-measurements.json', details)
        write(self.path / 'winner.json', wc)

    def run(self, request):
        try:
            self.check()
            source = self.state['source']
            if source['engine'] == 'local' and digest(source['path']) != source['sha256']:
                raise ValueError('Source file changed; create a new run')
            action = request['action']
            if action == 'baseline':
                self.baseline()
            elif action == 'trial':
                self.trial(request['candidate'])
            elif action == 'finalize':
                self.finalize()
            self.state['job'] = {'status': 'idle', 'last_action': action}
        except Exception as e:
            self.state['job'] = {'status': 'error', 'error': f'{type(e).__name__}: {e}'}
            if request['action'] == 'finalize':
                write(self.path / 'final.json', {'correct_on_final_cases': False, 'error': str(e), 'note': 'Sealed; do not deploy this candidate.'})
        finally:
            for eng in self.engines:
                eng.close()
            self.state['spent_seconds'] += time.monotonic() - self.start
            write(self.path / 'state.json', self.state)
            if self.state['history']:
                from .report import report
                report(self.path)
        return self.state
