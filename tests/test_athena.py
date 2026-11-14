import boto3
from botocore.stub import Stubber, ANY
import pytest
from quick_query.athena import AthenaEngine
from quick_query.util import read


def config():
    return {'region':'us-east-1','database':'demo','table':'flights','workgroup':'research',
            'max_bytes_per_query':1000000000,'max_queries':20,'usd_per_tb':5,'allow_materialize':True}


def make(tmp_path):
    client=boto3.client('athena',region_name='us-east-1',aws_access_key_id='test',aws_secret_access_key='test')
    stub=Stubber(client)
    stub.add_response('get_work_group',{'WorkGroup':{'Name':'research','Configuration':{'BytesScannedCutoffPerQuery':1000000000}}},{'WorkGroup':'research'})
    stub.activate()
    p=tmp_path/'run'/'trial-000'/'cache.json';p.parent.mkdir(parents=True)
    return AthenaEngine(config(),p,client=client),stub


def args(sql):
    return {'QueryString':sql,'QueryExecutionContext':{'Database':'demo','Catalog':'AwsDataCatalog'},
            'WorkGroup':'research','ResultReuseConfiguration':{'ResultReuseByAgeConfiguration':{'Enabled':False}}}


def response(stub,sql,cached=False,status='SUCCEEDED'):
    stub.add_response('start_query_execution',{'QueryExecutionId':'q1'},args(sql))
    stub.add_response('get_query_execution',{'QueryExecution':{'QueryExecutionId':'q1','Status':{'State':status},
                      'Statistics':{'EngineExecutionTimeInMillis':123,'DataScannedInBytes':100,
                                    'TotalExecutionTimeInMillis':150,'ResultReuseInformation':{'ReusedPreviousResult':cached}}}}, {'QueryExecutionId':'q1'})


def test_real_boto_schema_no_reuse_pagination_nulls(tmp_path):
    eng,stub=make(tmp_path)
    response(stub,'SELECT COUNT(*) AS n FROM "flights"')
    meta={'ColumnInfo':[{'Name':'n','Type':'bigint'}]}
    stub.add_response('get_query_results',{'ResultSet':{'ResultSetMetadata':meta,'Rows':[{'Data':[{'VarCharValue':'n'}]},{'Data':[{'VarCharValue':'12'}]}]},'NextToken':'page2'}, {'QueryExecutionId':'q1','MaxResults':1000})
    stub.add_response('get_query_results',{'ResultSet':{'ResultSetMetadata':meta,'Rows':[{'Data':[{}]}]}}, {'QueryExecutionId':'q1','MaxResults':1000,'NextToken':'page2'})
    r=eng.query('SELECT COUNT(*) AS n FROM data')
    assert r['rows']==[[12],[None]] and r['seconds']==.123
    assert r['estimated_scan_usd']==.00005
    assert read(eng.run_path/'aws-usage.json')['submitted']==1
    stub.assert_no_pending_responses()


def test_cached_results_rejected(tmp_path):
    eng,stub=make(tmp_path);response(stub,'SELECT COUNT(*) AS n FROM "flights"',cached=True)
    with pytest.raises(RuntimeError,match='Cached'):eng.query('SELECT COUNT(*) AS n FROM data')
    stub.assert_no_pending_responses()


def test_timeout_cancels(tmp_path):
    eng,stub=make(tmp_path);eng.timeout=-1
    response(stub,'SELECT COUNT(*) AS n FROM "flights"',status='RUNNING')
    stub.add_response('stop_query_execution',{}, {'QueryExecutionId':'q1'})
    with pytest.raises(TimeoutError):eng.query('SELECT COUNT(*) AS n FROM data')
    assert read(eng.run_path/'aws-usage.json')['executions'][0]['status']=='CANCEL_REQUESTED'
    stub.assert_no_pending_responses()


def test_ctas_is_generated_and_cte_rewrites(tmp_path):
    eng,stub=make(tmp_path)
    assert '"flights"' in eng._rewrite('WITH s AS (SELECT * FROM data) SELECT COUNT(*) FROM s')
    with pytest.raises(ValueError):eng._rewrite('WITH data AS (SELECT 1) SELECT * FROM data')
    stub.add_response('start_query_execution',{'QueryExecutionId':'q1'},args(ANY))
    stub.add_response('get_query_execution',{'QueryExecution':{'Status':{'State':'SUCCEEDED'},'Statistics':{'EngineExecutionTimeInMillis':100,'DataScannedInBytes':100}}},{'QueryExecutionId':'q1'})
    stub.add_response('get_query_results',{'ResultSet':{'ResultSetMetadata':{'ColumnInfo':[]},'Rows':[]}},{'QueryExecutionId':'q1','MaxResults':1000})
    r=eng.materialize({'sql':'SELECT * FROM data','compression':'zstd'})
    assert r['table'].startswith('qqar_') and read(eng.cache_path)['table']==r['table']
    stub.assert_no_pending_responses()
