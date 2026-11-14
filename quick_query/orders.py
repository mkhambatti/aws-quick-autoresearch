"""Small, deterministic synthetic orders demo; independent of the flights workload."""
import csv
from pathlib import Path


def download(destination):
    """Create a small local fixture, preserving any existing file."""
    path = Path(destination).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open('x', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['region', 'category', 'amount_cents', 'returned'])
            for i in range(2400):
                writer.writerow([['US', 'CA', 'GB', 'DE'][i % 4],
                                 ['books', 'home', 'food'][i % 3],
                                 'NA' if i % 17 == 0 else 100 + i % 997,
                                 int(i % 7 == 0)])
    return path


def workload():
    return {
        'name': 'Synthetic orders starter',
        'queries': {'totals': 'SELECT category, COUNT(*) AS orders, COUNT(amount_cents) AS priced_orders, SUM(amount_cents) AS amount_cents, SUM(returned) AS returns FROM data WHERE region = {{region}} GROUP BY category'},
        'train_cases': [{'region': 'US'}, {'region': 'CA'}],
        'test_cases': [{'region': 'GB'}, {'region': 'DE'}, {'region': 'NO_MATCH'}],
    }


def proposals():
    return [
        {'hypothesis': 'Read reusable regional category totals instead of scanning individual orders.',
         'materialize': {'sql': 'SELECT region, category, COUNT(*) AS orders, COUNT(amount_cents) AS priced_orders, SUM(amount_cents) AS amount_cents, SUM(returned) AS returns FROM data GROUP BY region, category', 'compression': 'zstd'},
         'queries': {'totals': 'SELECT category, orders, priced_orders, amount_cents, returns FROM cache WHERE region = {{region}}'}},
        {'hypothesis': 'Negative control: dropping returned orders must change the answers and be rejected.',
         'materialize': None,
         'queries': {k: v.replace('WHERE region', 'WHERE returned = 0 AND region') for k, v in workload()['queries'].items()}},
    ]
