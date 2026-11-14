"""Athena adapter: real service statistics, bounded submissions, no result reuse."""
import math
import time
import uuid
from decimal import Decimal
from pathlib import Path
import boto3
from botocore.config import Config
from sqlglot import exp
from .sql import validate
from .util import read, write


class AthenaEngine:
    def __init__(self, source, cache_path, threads=2, timeout=90, client=None):
        self.source, self.timeout = source, timeout
        self.cache_path = Path(cache_path)
        self.run_path = self.cache_path.parent.parent
        self.client = client or boto3.client('athena', region_name=source['region'], config=Config(connect_timeout=5, read_timeout=15, retries={'max_attempts': 2}))
        wg = self.client.get_work_group(WorkGroup=source['workgroup'])['WorkGroup']
        config = wg['Configuration']
        cutoff = config.get('BytesScannedCutoffPerQuery', 0)
        if not 10000000 <= cutoff <= source['max_bytes_per_query']:
            raise ValueError('Set a workgroup per-query byte cutoff no larger than max_bytes_per_query')
        self.cutoff = cutoff
        self.cache_table = None
        if self.cache_path.exists():
            self.cache_table = read(self.cache_path)['table']

    def _rewrite(self, sql, tables=('data', 'cache')):
        tree = validate(sql, tables=tables, dialect='trino')
        ctes = {c.alias.lower() for c in tree.find_all(exp.CTE)}
        if ctes & {'data', 'cache'}:
            raise ValueError('CTE names must not shadow data/cache')
        for t in tree.find_all(exp.Table):
            if t.name.lower() in ctes:
                continue
            name = t.name.lower()
            if name == 'data':
                physical = self.source['table']
            elif name == 'cache' and self.cache_table:
                physical = self.cache_table
            else:
                raise ValueError('No cache exists for this trial')
            t.set('this', exp.to_identifier(physical, quoted=True))
        return tree.sql(dialect='trino')

    def _execute(self, sql):
        ledger_path = self.run_path / 'aws-usage.json'
        ledger = read(ledger_path) if ledger_path.exists() else {'submitted': 0, 'executions': []}
        if ledger['submitted'] >= self.source['max_queries']:
            raise ValueError('AWS query submission budget exhausted')
        ledger['submitted'] += 1  # Reserve before a network call, including failures.
        write(ledger_path, ledger)
        args = {'QueryString': sql,
                'QueryExecutionContext': {'Database': self.source['database'], 'Catalog': 'AwsDataCatalog'},
                'WorkGroup': self.source['workgroup'],
                'ResultReuseConfiguration': {'ResultReuseByAgeConfiguration': {'Enabled': False}}}
        if self.source.get('output_location'):
            args['ResultConfiguration'] = {'OutputLocation': self.source['output_location']}
        qid = self.client.start_query_execution(**args)['QueryExecutionId']
        entry = {'query_id': qid, 'status': 'SUBMITTED'}
        ledger['executions'].append(entry)
        write(ledger_path, ledger)
        start = time.monotonic()
        try:
            while True:
                q = self.client.get_query_execution(QueryExecutionId=qid)['QueryExecution']
                state = q['Status']['State']
                if state in {'SUCCEEDED', 'FAILED', 'CANCELLED'}:
                    break
                if time.monotonic() - start > self.timeout:
                    raise TimeoutError(f'Athena query timeout: {qid}')
                time.sleep(0.5)
            stats = q.get('Statistics', {})
            entry.update(status=state, statistics=stats)
            write(ledger_path, ledger)
            if state != 'SUCCEEDED':
                raise RuntimeError(q['Status'].get('StateChangeReason', state))
            if stats.get('ResultReuseInformation', {}).get('ReusedPreviousResult'):
                raise RuntimeError('Cached Athena result rejected')
            rows, columns, types = [], [], []
            token = None
            first = True
            while True:
                kwargs = {'QueryExecutionId': qid, 'MaxResults': 1000}
                if token:
                    kwargs['NextToken'] = token
                page = self.client.get_query_results(**kwargs)
                rs = page['ResultSet']
                if not columns:
                    info = rs['ResultSetMetadata']['ColumnInfo']
                    columns = [c['Name'] for c in info]
                    types = [c['Type'] for c in info]
                batch = rs.get('Rows', [])
                if first:
                    batch = batch[1:]  # Athena SELECT header only on first page.
                    first = False
                for r in batch:
                    row = []
                    for i, c in enumerate(r['Data']):
                        value = c.get('VarCharValue')
                        if value is not None and types[i] in {'bigint', 'integer', 'smallint', 'tinyint'}:
                            value = int(value)
                        elif value is not None and (types[i] in {'double', 'float', 'real'} or types[i].startswith('decimal')):
                            value = Decimal(value)
                        row.append(value)
                    rows.append(row)
                if len(rows) > 10000:
                    raise ValueError('Result exceeds 10,000 rows')
                token = page.get('NextToken')
                if not token:
                    break
            scanned = stats.get('DataScannedInBytes', 0)
            # Standard on-demand scan estimate; not an AWS bill and not capacity pricing.
            billed = max(10_000_000, math.ceil(scanned / 1_000_000) * 1_000_000)
            return {'columns': columns, 'rows': rows, 'seconds': stats['EngineExecutionTimeInMillis'] / 1000,
                    'total_seconds': stats.get('TotalExecutionTimeInMillis', 0) / 1000,
                    'bytes_scanned': scanned, 'estimated_scan_usd': billed / 1e12 * self.source['usd_per_tb'],
                    'query_id': qid}
        except BaseException:
            if entry['status'] == 'SUBMITTED':
                self.client.stop_query_execution(QueryExecutionId=qid)
                entry['status'] = 'CANCEL_REQUESTED'
                write(ledger_path, ledger)
            raise

    def query(self, sql):
        return self._execute(self._rewrite(sql))

    def materialize(self, spec):
        if spec is None:
            return {'seconds': 0.0, 'storage_bytes': None, 'estimated_scan_usd': 0}
        if not self.source.get('allow_materialize'):
            raise ValueError('CTAS disabled; explicitly enable allow_materialize in trusted AWS config')
        if set(spec) - {'sql', 'compression', 'row_group_size'}:
            raise ValueError('Unknown materialization option')
        if 'row_group_size' in spec:
            raise ValueError('row_group_size is local-only')
        codec = spec.get('compression', 'zstd').upper()
        if codec not in {'SNAPPY', 'ZSTD'}:
            raise ValueError('Athena CTAS supports SNAPPY or ZSTD in this adapter')
        sql = self._rewrite(spec['sql'], tables=('data',))
        self.cache_table = 'qqar_' + uuid.uuid4().hex
        write(self.cache_path, {'table': self.cache_table, 'database': self.source['database']})
        # Generated table name + validated SELECT; never accept arbitrary DDL from a planner.
        result = self._execute(f"CREATE TABLE {self.cache_table} WITH (format='PARQUET', write_compression='{codec}') AS {sql}")
        return {'seconds': result['seconds'], 'storage_bytes': None,
                'estimated_scan_usd': result['estimated_scan_usd'], 'table': self.cache_table,
                'query_id': result['query_id'], 'bytes_scanned': result['bytes_scanned']}

    def attach_cache(self):
        self.cache_table = read(self.cache_path)['table']

    def close(self):
        pass
