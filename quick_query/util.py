import hashlib
import json
import os
import re
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')
    tmp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def run_path(workspace, run_id):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', run_id):
        raise ValueError('Invalid run ID')
    path = Path(workspace).resolve() / 'runs' / run_id
    if not (path / 'state.json').exists():
        raise ValueError('Unknown run ID')
    return path


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise ValueError('Parameters must be strings, integers, booleans, or null')
