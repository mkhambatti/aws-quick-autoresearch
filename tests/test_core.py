import copy
import csv
import json
from decimal import Decimal
from pathlib import Path
import pytest
from quick_query import engine
from quick_query.flights import workload, proposals
from quick_query.local import LocalEngine, inspect_source
from quick_query.sql import validate, render, same, signature
from quick_query.util import read, write


@pytest.fixture
def source(tmp_path):
    p = tmp_path/'flights.csv'
    with p.open('w',newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Month','Origin','Dest','UniqueCarrier','DayOfWeek','CRSDepTime','ArrDelay','Cancelled','Diverted'])
        for month,origin in [(1,'SEA'),(6,'JFK'),(11,'SFO'),(2,'ORD'),(8,'ATL'),(12,'SEA')]:
            for i in range(30):
                writer.writerow([month,origin,['LAX','JFK'][i%2],['AA','WN'][i%2],i%7+1,600+i*25,'NA' if i%8==0 else i-10, int(i%8==0),int(i%17==0)])
    return p


def new_run(tmp_path,source):
    r = engine.create(tmp_path/'ws',source,workload(),repeats=2,timeout=5,seconds=300)
    return Path(r['path'])


def run(path,action,candidate=None):
    return engine.Runner(path).run({'action':action,'candidate':candidate})


def test_full_real_engine_and_final_seal(tmp_path,source):
    p=new_run(tmp_path,source)
    s=run(p,'baseline')
    assert s['job']['status']=='idle',s
    for candidate in [proposals()[1],proposals()[4],proposals()[5]]:
        s=run(p,'trial',candidate)
        assert s['history'][-1]['correct'],s['history'][-1]
    # Ensure final verifies a materialized query, even if tiny fixture timings discard it.
    s['winner']=3;write(p/'state.json',s)
    s=run(p,'finalize')
    assert s['sealed']
    assert read(p/'final.json')['correct_on_final_cases'],read(p/'final.json')
    assert (p/'report.html').exists() and (p/'progress.png').stat().st_size>1000
    with pytest.raises(ValueError,match='sealed'):
        engine.launch(tmp_path/'ws',p.name,'trial',proposals()[1])


def test_wrong_answer_rejected(tmp_path,source):
    p=new_run(tmp_path,source);run(p,'baseline')
    s=run(p,'trial',proposals()[-1])
    r=s['history'][-1]
    assert r['status']=='rejected' and not r['correct']
    assert 'Answer mismatch' in r['error']
    assert s['winner']==0


def test_source_mutation_detected(tmp_path,source):
    p=new_run(tmp_path,source)
    with source.open('a') as f:f.write('1,SEA,JFK,WN,1,600,5,0,0\n')
    s=run(p,'baseline')
    assert s['job']['status']=='error' and 'changed' in s['job']['error']


@pytest.mark.parametrize('sql',[
    "SELECT * FROM read_csv('/etc/passwd')",'SELECT * FROM other',
    'SELECT 1; DROP TABLE data',"COPY data TO '/tmp/a'",'SELECT random() FROM data',
    'INSTALL httpfs',"SELECT * FROM sqlite_scan('/x','y')",'SELECT * INTO test FROM data',
    'WITH RECURSIVE a AS (SELECT * FROM a) SELECT * FROM a', 'SELECT * FROM main.data'])
def test_sql_guard(sql):
    with pytest.raises(ValueError):validate(sql)


def test_parameter_injection_and_equality():
    sql=render('SELECT * FROM data WHERE Origin = {{origin}}',{'origin':"SEA'; DROP TABLE data;--"})
    validate(sql)
    a={'columns':['v'],'rows':[[1],[1],[None],[Decimal('2.00')]]}
    b={'columns':['v'],'rows':[[None],[2],[1],[1]]}
    assert same(a,b) and signature(a)==signature(b)
    assert not same(a,{'columns':['v'],'rows':[[None],[2],[1]]})
    assert signature(a)!=signature({'columns':['v'],'rows':[[None],[2],[1]]})


def test_external_access_denied(tmp_path,source):
    meta=inspect_source(source)
    obj=LocalEngine(meta,tmp_path/'cache.parquet')
    with pytest.raises(Exception):obj.con.execute("select * from read_csv('/etc/passwd')")
    obj.close()


def test_async_lock_and_mcp_status(tmp_path,source):
    from quick_query.cli import wait
    p=new_run(tmp_path,source)
    engine.launch(tmp_path/'ws',p.name,'baseline')
    with pytest.raises(ValueError,match='already running'):
        engine.launch(tmp_path/'ws',p.name,'baseline')
    s=wait(tmp_path/'ws',p.name)
    assert s['history'][0]['correct']
    assert 'test_cases' not in s['workload']


def test_hidden_case_failure_seals_run(tmp_path,source):
    p=new_run(tmp_path,source);run(p,'baseline')
    candidate=copy.deepcopy(proposals()[1])
    candidate['materialize']['sql']+=' WHERE Month <> 2'
    s=run(p,'trial',candidate)
    assert s['history'][-1]['correct']
    s['winner']=1;write(p/'state.json',s)
    s=run(p,'finalize')
    assert s['sealed'] and not read(p/'final.json')['correct_on_final_cases']


def test_query_timeout(tmp_path,source):
    obj=LocalEngine(inspect_source(source),tmp_path/'cache.parquet',timeout=.01)
    with pytest.raises(Exception,match='Interrupted'):
        obj.query('SELECT SUM(a.ArrDelay*b.ArrDelay*c.ArrDelay*d.ArrDelay) AS v FROM data a CROSS JOIN data b CROSS JOIN data c CROSS JOIN data d')
    obj.close()


def test_status_does_not_report_idle_before_report_unlock(tmp_path,source):
    p=new_run(tmp_path,source)
    with engine.lock(p):
        assert engine.status(tmp_path/'ws',p.name)['job']['status']=='running'
    assert engine.status(tmp_path/'ws',p.name)['job']['status']=='idle'


def test_cli_demo_end_to_end(tmp_path,source):
    import subprocess,sys
    result=subprocess.run([sys.executable,'-m','quick_query.cli','--workspace',str(tmp_path/'cli-ws'),
                           'demo','--data',str(source),'--trials','2','--repeats','2','--seconds','120'],
                          capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stderr+result.stdout
    assert 'Report:' in result.stdout
    paths=list((tmp_path/'cli-ws'/'runs').glob('*/final.json'))
    assert len(paths)==1 and read(paths[0])['correct_on_final_cases']


def test_exact_large_integer_fingerprints():
    a={'columns':['n'],'rows':[[10**35+1]]}
    b={'columns':['n'],'rows':[[10**35+2]]}
    assert signature(a)!=signature(b)
