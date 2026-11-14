import argparse
import json
import sys
import time
from pathlib import Path
from . import engine, flights, orders
from .util import read, run_path, write


def wait(workspace, run_id):
    while True:
        result = engine.status(workspace, run_id)
        if result['job']['status'] != 'running':
            if result['job']['status'] == 'error':
                raise RuntimeError(result['job']['error'])
            return result
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description='Same answers, measured query optimization.')
    parser.add_argument('--workspace', default='workspaces/default')
    commands = parser.add_subparsers(dest='command', required=True)
    d = commands.add_parser('download-flights')
    d.add_argument('--destination', default='data')
    for name in ['init', 'init-flights', 'init-small', 'init-aws', 'demo', 'demo-small']:
        p = commands.add_parser(name)
        if name in {'init', 'init-aws'}:
            p.add_argument('--workload', required=True)
        if name == 'init':
            p.add_argument('--source', required=True)
            p.add_argument('--nullstr', default='NA')
        if name in {'demo', 'init-flights'}:
            p.add_argument('--data', default='data/2008.csv')
        if name in {'init-small', 'demo-small'}:
            p.add_argument('--data', default='data/demo-orders.csv')
        if name == 'init-aws':
            p.add_argument('--config', required=True)
            p.add_argument('--allow-aws', action='store_true', help='Authorize metered Athena calls under configured limits')
            p.add_argument('--objective', choices=['seconds', 'bytes_scanned'], default='bytes_scanned')
        p.add_argument('--trials', type=int, default=12)
        p.add_argument('--repeats', type=int, default=3)
        p.add_argument('--timeout', type=int, default=90)
        p.add_argument('--seconds', type=int, default=3600)
    for name in ['baseline', 'submit', 'finalize', 'status', 'stop', 'report']:
        p = commands.add_parser(name)
        p.add_argument('run', help='Run ID or latest')
        if name == 'submit':
            p.add_argument('candidate')
        if name in {'baseline','submit','finalize'}:
            p.add_argument('--wait', action='store_true')
    commands.add_parser('serve')
    q = commands.add_parser('quick-config')
    q.add_argument('--output', default='quick-mcp.json')
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    if args.command == 'serve':
        from .server import build_server
        build_server(workspace).run(transport='stdio')
        return
    if args.command == 'quick-config':
        config = {'mcpServers': {'quick-query-autoresearch': {'command': sys.executable,
                   'args': ['-m', 'quick_query.cli', '--workspace', str(workspace), 'serve']}}}
        write(args.output, config)
        print(json.dumps(config, indent=2))
        return
    if args.command == 'download-flights':
        print(flights.download(args.destination))
        return
    if args.command in {'init','init-flights','init-small','init-aws','demo','demo-small'}:
        aws = None
        if args.command == 'init-aws':
            if not args.allow_aws:
                parser.error('init-aws requires --allow-aws; Athena queries and CTAS incur charges')
            aws = read(args.config)
        if args.command in {'init-flights','demo'}:
            source = Path(args.data).resolve()
            if not source.exists():
                if source.name != '2008.csv':
                    parser.error('Supply an existing 2008-schema flight CSV, or use default data/2008.csv')
                print('Downloading real 2008 flight data (~114 MB compressed; ~689 MB CSV)…', flush=True)
                flights.download(source.parent)
            workload = flights.workload()
        elif args.command in {'init-small', 'demo-small'}:
            source = orders.download(args.data)
            workload = orders.workload()
        else:
            source = getattr(args, 'source', None)
            workload = read(args.workload)
        result = engine.create(workspace, source, workload, aws=aws, trials=args.trials,
                               repeats=args.repeats, timeout=args.timeout, seconds=args.seconds,
                               objective=getattr(args,'objective','seconds'), nullstr=getattr(args,'nullstr','NA'))
        write(workspace/'latest.json', {'run_id':result['run_id']})
        print(json.dumps(result, indent=2), flush=True)
        if args.command not in {'demo', 'demo-small'}:
            return
        run_id = result['run_id']
        print('Planner: deterministic example proposals. No LLM calls. Quick can propose its own experiments via MCP.', flush=True)
        engine.launch(workspace, run_id, 'baseline')
        wait(workspace, run_id)
        proposals = orders.proposals() if args.command == 'demo-small' else flights.proposals()
        for candidate in proposals[:args.trials-1]:
            engine.launch(workspace, run_id, 'trial', candidate)
            status = wait(workspace, run_id)
            trial = status['history'][-1]
            print(json.dumps({k:trial[k] for k in ['trial','status','score','hypothesis']}), flush=True)
        engine.launch(workspace, run_id, 'finalize')
        status = wait(workspace, run_id)
        print(json.dumps(status.get('final'), indent=2))
        print(f"Report: {result['path']}/report.html")
        if not status.get('final', {}).get('correct_on_final_cases'):
            raise RuntimeError('Final verification failed; inspect the report')
        return
    run_id = read(workspace/'latest.json')['run_id'] if args.run == 'latest' else args.run
    if args.command == 'status':
        result = engine.status(workspace, run_id)
    elif args.command == 'stop':
        result = engine.stop(workspace, run_id)
    elif args.command == 'report':
        from .report import report
        path = run_path(workspace,run_id)
        report(path)
        result = {'report': str(path/'report.html')}
    else:
        action = {'baseline':'baseline','submit':'trial','finalize':'finalize'}[args.command]
        candidate = read(args.candidate) if action=='trial' else None
        result = engine.launch(workspace,run_id,action,candidate)
        if args.wait:
            result = wait(workspace,run_id)
    print(json.dumps(result, indent=2, default=str))

if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
