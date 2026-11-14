"""Conservative SQL subset. Engine permissions are the second enforcement layer."""
import re
from collections import Counter
from decimal import Decimal
import sqlglot
from sqlglot import exp
from .util import literal

FUNCTIONS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'NULLIF',
             'ABS', 'ROUND', 'FLOOR', 'CEIL', 'CAST', 'TRY_CAST', 'EXTRACT',
             'LOWER', 'UPPER', 'LENGTH', 'SUBSTRING', 'CONCAT', 'CASE', 'IF', 'AND', 'OR'}


def render(template, params):
    def sub(m):
        if m[1] not in params:
            raise ValueError(f'Missing parameter: {m[1]}')
        return literal(params[m[1]])
    return re.sub(r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}', sub, template)


def validate(sql, tables=('data', 'cache'), dialect='duckdb'):
    if not isinstance(sql, str) or len(sql) > 50000:
        raise ValueError('SQL must be a string under 50,000 characters')
    statements = sqlglot.parse(sql, read=dialect)
    if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise ValueError('Exactly one read-only SELECT is required')
    tree = statements[0]
    if any(tree.find_all(exp.Into, exp.Command, exp.Insert, exp.Delete, exp.Update, exp.Create, exp.Drop)):
        raise ValueError('Writes and commands are forbidden')
    if any(c.args.get('recursive') for c in tree.find_all(exp.With)):
        raise ValueError('Recursive CTEs are not supported')
    ctes = {c.alias.lower() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier) or table.db or table.catalog:
            raise ValueError('Only registered, unqualified table names are allowed')
        if table.name.lower() not in set(tables) | ctes:
            raise ValueError(f'Unregistered table: {table.name}')
    for func in tree.find_all(exp.Func):
        if isinstance(func, exp.Anonymous) or func.sql_name() not in FUNCTIONS:
            raise ValueError(f'Unsupported function: {func.sql_name()}')
    return tree


def normalized(rows):
    """Exact multiset equality, including duplicate rows and nulls; no rounding."""
    def cell(x):
        if x is None:
            return ('null',)
        if isinstance(x, (int, float, Decimal)) and not isinstance(x, bool):
            d = Decimal(str(x))
            if not d.is_finite():
                raise ValueError('Non-finite result not supported')
            return ('number', d)
        return (type(x).__name__, str(x))
    return Counter(tuple(cell(v) for v in row) for row in rows)


def same(expected, actual):
    if expected['columns'] != actual['columns']:
        return False
    return normalized(expected['rows']) == normalized(actual['rows'])


def signature(result):
    import hashlib
    import json
    counter = normalized(result['rows'])
    def number_text(d):
        from decimal import localcontext
        with localcontext() as context:
            context.prec = max(28, len(d.as_tuple().digits))
            return str(d.normalize()) if d != 0 else '0'
    pairs = []
    for row, count in counter.items():
        cells = [(c[0], number_text(c[1]) if c[0] == 'number' else (c[1] if len(c) > 1 else None)) for c in row]
        pairs.append([cells, count])
    pairs.sort(key=lambda x: json.dumps(x, sort_keys=True))
    return hashlib.sha256(json.dumps([result['columns'], pairs], sort_keys=True).encode()).hexdigest()
