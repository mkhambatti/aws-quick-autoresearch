import sys
from pathlib import Path
from .engine import Runner, lock
from .util import read

if __name__ == '__main__':
    path = Path(sys.argv[1])
    with lock(path, int(sys.argv[2])):
        Runner(path).run(read(path / 'request.json'))
