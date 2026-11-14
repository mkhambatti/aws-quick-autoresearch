import json
import threading
import time
from pathlib import Path
import duckdb
from .sql import validate
from .util import literal


class LocalEngine:
    """Only fixed source/cache paths can be read; extensions/network are disabled."""
    def __init__(self, source, cache_path, threads=2, timeout=90):
        self.source, self.cache_path = source, Path(cache_path)
        self.timeout = timeout
        self.con = duckdb.connect(config={'threads': threads, 'memory_limit': '1GB',
                                          'autoload_known_extensions': False,
                                          'autoinstall_known_extensions': False})
        self.con.execute(f"SET allowed_paths=[{literal(source['path'])}, {literal(str(self.cache_path))}]")
        self.con.execute('SET enable_external_access=false')
        if source['format'] == 'csv':
            cols = '{' + ','.join(f'{literal(n)}:{literal(t)}' for n, t in source['schema']) + '}'
            relation = f"read_csv({literal(source['path'])}, header=true, auto_detect=false, columns={cols}, nullstr={literal(source.get('nullstr', 'NA'))})"
        else:
            relation = f"read_parquet({literal(source['path'])})"
        self.con.execute(f'CREATE VIEW data AS SELECT * FROM {relation}')

    def _execute(self, sql):
        timer = threading.Timer(self.timeout, self.con.interrupt)
        timer.daemon = True
        timer.start()
        try:
            start = time.perf_counter()
            cursor = self.con.execute(sql)
            columns = [x[0] for x in cursor.description]
            rows = cursor.fetchmany(10001)
            if len(rows) > 10000:
                raise ValueError('Result exceeds 10,000 rows; use an aggregate workload')
            return {'columns': columns, 'rows': rows,
                    'seconds': time.perf_counter() - start, 'bytes_scanned': None}
        finally:
            timer.cancel()

    def query(self, sql):
        validate(sql)
        return self._execute(sql)

    def materialize(self, spec):
        start = time.perf_counter()
        if spec is None:
            return {'seconds': 0.0, 'storage_bytes': 0}
        if set(spec) - {'sql', 'compression', 'row_group_size'}:
            raise ValueError('Unknown materialization option')
        validate(spec['sql'], tables=('data',))
        codec = spec.get('compression', 'zstd').lower()
        if codec not in {'zstd', 'snappy', 'uncompressed'}:
            raise ValueError('Unsupported Parquet compression')
        rg = int(spec.get('row_group_size', 122880))
        if not 2048 <= rg <= 1048576:
            raise ValueError('row_group_size must be 2048..1048576')
        self._execute(f"COPY ({spec['sql']}) TO {literal(str(self.cache_path))} (FORMAT PARQUET, COMPRESSION {codec}, ROW_GROUP_SIZE {rg})")
        self.attach_cache()
        return {'seconds': time.perf_counter() - start, 'storage_bytes': self.cache_path.stat().st_size}

    def attach_cache(self):
        self.con.execute(f'CREATE OR REPLACE VIEW cache AS SELECT * FROM read_parquet({literal(str(self.cache_path))})')

    def close(self):
        self.con.close()


def inspect_source(path, nullstr='NA'):
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in {'.csv', '.parquet'}:
        raise ValueError('Source must be a local .csv or .parquet file')
    con = duckdb.connect(config={'threads': 2})
    try:
        if path.suffix.lower() == '.csv':
            expr = f"read_csv({literal(str(path))}, header=true, nullstr={literal(nullstr)}, sample_size=20480)"
        else:
            expr = f"read_parquet({literal(str(path))})"
        schema = [[r[0], r[1]] for r in con.execute(f'DESCRIBE SELECT * FROM {expr}').fetchall()]
        rows = con.execute(f'SELECT count(*) FROM {expr}').fetchone()[0]
        return {'path': str(path), 'format': path.suffix[1:].lower(), 'schema': schema,
                'rows': rows, 'size_bytes': path.stat().st_size, 'nullstr': nullstr}
    finally:
        con.close()
