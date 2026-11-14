"""Real 2008 reporting-carrier data; deterministic demo proposals, not an LLM."""
import bz2
import hashlib
import shutil
import urllib.request
from pathlib import Path
from .util import digest, write

URL = 'https://www.stat.ucdavis.edu/~duncan/Data/rdatasciencecases/Airline/2008.csv.bz2'
CITATION = 'Data Expo 2009: Airline on time data. Harvard Dataverse. https://doi.org/10.7910/DVN/HG7NV7'
# Populated from the retrieved public file; verifies subsequent downloads.
ARCHIVE_SHA256 = 'cc1fab9ada5ae6a879c00fa102340d0359d1ff25c9630895c054fe69c2aa9f92'


def download(destination):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / '2008.csv.bz2'
    output = destination / '2008.csv'
    if not archive.exists() or digest(archive) != ARCHIVE_SHA256:
        part = archive.with_suffix('.download')
        request = urllib.request.Request(URL, headers={'User-Agent': 'quick-query-autoresearch/0.1'})
        with urllib.request.urlopen(request, timeout=90) as source, part.open('wb') as target:
            shutil.copyfileobj(source, target)
        if digest(part) != ARCHIVE_SHA256:
            part.unlink(missing_ok=True)
            raise ValueError('Public archive checksum changed; inspect source before using it')
        part.replace(archive)
    if not output.exists() or digest(output) != '6e9306a0180790f734b2c3ce56d3feb238d4f2b64a14396833046fd01c4dfa9b':
        part = output.with_suffix('.tmp')
        with bz2.open(archive, 'rb') as source, part.open('wb') as target:
            shutil.copyfileobj(source, target)
        part.replace(output)
    write(destination / 'provenance.json', {'url': URL, 'citation': CITATION,
          'archive_sha256': ARCHIVE_SHA256, 'csv_sha256': digest(output),
          'description': '7,009,728 real flight records from 2008; historical benchmark, not live travel advice'})
    return output


def workload():
    dimensions = {'routes': 'Dest', 'carriers': 'UniqueCarrier',
                  'departure_hours': 'FLOOR(CRSDepTime / 100.0)', 'weekdays': 'DayOfWeek'}
    metrics = '''COUNT(*) AS flights, COUNT(ArrDelay) AS observed_arrivals,
    SUM(ArrDelay) AS arrival_delay_minutes,
    SUM(CASE WHEN ArrDelay >= 15 THEN 1 ELSE 0 END) AS delayed_flights,
    SUM(CASE WHEN Cancelled = 1 THEN 1 ELSE 0 END) AS cancellations,
    SUM(CASE WHEN Diverted = 1 THEN 1 ELSE 0 END) AS diversions'''
    queries = {name: f'''SELECT {dim} AS dimension, {metrics}
FROM data WHERE Month = {{{{month}}}} AND Origin = {{{{origin}}}}
GROUP BY {dim}''' for name, dim in dimensions.items()}
    queries['national_carriers'] = f'''SELECT UniqueCarrier AS dimension, {metrics}
FROM data WHERE Month = {{{{month}}}} GROUP BY UniqueCarrier'''
    return {'name': 'Airline Delay Detective',
            'description': 'Five dashboard panels: route delays, carrier reliability, departure hours, weekdays, national carriers. Rates derive from exact counts/sums. No LIMIT hides incorrect rows.',
            'queries': queries,
            'train_cases': [{'month': 1, 'origin': 'SEA'}, {'month': 6, 'origin': 'JFK'}, {'month': 11, 'origin': 'SFO'}],
            'test_cases': [{'month': 2, 'origin': 'ORD'}, {'month': 8, 'origin': 'ATL'},
                           {'month': 12, 'origin': 'SEA'}, {'month': 13, 'origin': 'ZZZ'}]}


def proposals():
    import copy
    w = workload()
    raw = w['queries']
    projected = 'SELECT Month, DayOfWeek, CRSDepTime, UniqueCarrier, ArrDelay, Origin, Dest, Cancelled, Diverted FROM data'
    cached = {k: v.replace('FROM data', 'FROM cache') for k, v in raw.items()}
    candidates = []
    candidates.append({'hypothesis': 'Rewrite month equality as a range; test whether the optimizer already handles it.',
                       'queries': {k: v.replace('Month = {{month}}', 'Month >= {{month}} AND Month <= {{month}}') for k, v in raw.items()}, 'materialize': None})
    for codec in ['uncompressed', 'zstd']:
        candidates.append({'hypothesis': f'Project nine required columns into {codec} Parquet; avoid repeatedly parsing the original CSV.',
                           'queries': cached, 'materialize': {'sql': projected, 'compression': codec}})
    candidates.append({'hypothesis': 'Sort Parquet by month and origin so selective dashboard filters can skip row groups.',
                       'queries': cached, 'materialize': {'sql': projected + ' ORDER BY Month, Origin', 'compression': 'zstd', 'row_group_size': 16384}})
    rollup = '''SELECT Month, Origin, Dest, UniqueCarrier, DayOfWeek, FLOOR(CRSDepTime/100.0) AS departure_hour,
COUNT(*) AS n, COUNT(ArrDelay) AS observed, SUM(ArrDelay) AS delay_sum,
SUM(CASE WHEN ArrDelay >= 15 THEN 1 ELSE 0 END) AS late,
SUM(CASE WHEN Cancelled = 1 THEN 1 ELSE 0 END) AS cancelled_n,
SUM(CASE WHEN Diverted = 1 THEN 1 ELSE 0 END) AS diverted_n
FROM data GROUP BY Month, Origin, Dest, UniqueCarrier, DayOfWeek, FLOOR(CRSDepTime/100.0)'''
    rollqueries = {k: v.replace('FROM data', 'FROM cache').replace('FLOOR(CRSDepTime / 100.0)', 'departure_hour')
                  .replace('COUNT(*)', 'SUM(n)').replace('COUNT(ArrDelay)', 'SUM(observed)').replace('SUM(ArrDelay)', 'SUM(delay_sum)')
                  .replace('SUM(CASE WHEN ArrDelay >= 15 THEN 1 ELSE 0 END)', 'SUM(late)')
                  .replace('SUM(CASE WHEN Cancelled = 1 THEN 1 ELSE 0 END)', 'SUM(cancelled_n)')
                  .replace('SUM(CASE WHEN Diverted = 1 THEN 1 ELSE 0 END)', 'SUM(diverted_n)') for k, v in raw.items()}
    candidates.append({'hypothesis': 'Pre-aggregate reusable counts and sums; preserve dimensions needed by every dashboard query.',
                       'queries': rollqueries, 'materialize': {'sql': rollup, 'compression': 'zstd'}})
    candidates.append({'hypothesis': 'Sort the aggregate by month and origin with smaller row groups.',
                       'queries': rollqueries, 'materialize': {'sql': rollup + ' ORDER BY Month, Origin', 'compression': 'zstd', 'row_group_size': 16384}})
    candidates.append({'hypothesis': 'Try snappy on the sorted aggregate: lower decompression CPU may outweigh extra bytes.',
                       'queries': rollqueries, 'materialize': {'sql': rollup + ' ORDER BY Month, Origin', 'compression': 'snappy', 'row_group_size': 16384}})
    wrong = copy.deepcopy(candidates[-1])
    wrong['hypothesis'] = 'Negative control: drop cancelled flights to save work. Must be rejected because answers change.'
    wrong['materialize']['sql'] = wrong['materialize']['sql'].replace('FROM data GROUP BY', 'FROM data WHERE Cancelled = 0 GROUP BY')
    candidates.append(wrong)
    return candidates
