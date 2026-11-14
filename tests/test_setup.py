import os
import shutil
import subprocess
from pathlib import Path


def test_setup_chooses_supported_python_and_preserves_bad_venv(tmp_path):
    root=tmp_path/'project';(root/'scripts').mkdir(parents=True)
    shutil.copy(Path(__file__).parents[1]/'scripts'/'setup.sh',root/'scripts'/'setup.sh')
    binaries=tmp_path/'bin';binaries.mkdir()
    fake=binaries/'python3.12'
    fake.write_text('''#!/usr/bin/env bash
if [[ "$1" == "-c" ]]; then exit 0; fi
if [[ "$1" == "-m" && "$2" == "venv" ]]; then
  mkdir -p "$3/bin"
  cp "$0" "$3/bin/python"
  printf '#!/usr/bin/env bash\\nprintf "{}" > quick-mcp.json\\n' > "$3/bin/quick-query"
  chmod +x "$3/bin/quick-query"
  exit 0
fi
if [[ "$1" == "-m" && "$2" == "pip" ]]; then printf '%s\\n' "$*" > pip-args.txt; exit 0; fi
exit 1
''');fake.chmod(0o755)
    bad=binaries/'python3';bad.write_text('#!/bin/sh\nexit 1\n');bad.chmod(0o755)
    (root/'.venv'/'bin').mkdir(parents=True)
    shutil.copy(bad,root/'.venv'/'bin'/'python')
    result=subprocess.run(['bash',str(root/'scripts'/'setup.sh')],env={**os.environ,'PATH':str(binaries)+':/usr/bin:/bin','QUICK_QUERY_PYTHON':''},capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert len(list(root.glob('.venv-backup-*')))==1
    assert '--only-binary=:all:' in (root/'pip-args.txt').read_text()
    assert (root/'quick-mcp.json').exists()


def test_explicit_unsupported_python_rejected(tmp_path):
    bad=tmp_path/'python3.15';bad.write_text('#!/bin/sh\nexit 1\n');bad.chmod(0o755)
    result=subprocess.run(['bash',str(Path(__file__).parents[1]/'scripts'/'setup.sh')],env={**os.environ,'QUICK_QUERY_PYTHON':str(bad)},capture_output=True,text=True)
    assert result.returncode==1 and '3.12' in result.stderr
