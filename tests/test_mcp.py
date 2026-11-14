import asyncio
import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_mcp_stdio_handshake_tools_and_call(tmp_path):
    async def go():
        params=StdioServerParameters(command=sys.executable,args=['-m','quick_query.cli','--workspace',str(tmp_path),'serve'])
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as session:
                await session.initialize()
                listing=await session.list_tools()
                names={t.name for t in listing.tools}
                assert names=={'list_research_runs','research_status','start_baseline','submit_experiment','stop_research','finalize_research','get_progress_chart','get_candidate'}
                result=await session.call_tool('list_research_runs',{})
                assert not result.isError and json.loads(result.content[0].text)=={'runs':[]}
                result=await session.call_tool('research_status',{'run_id':'../../etc'})
                assert result.isError
    asyncio.run(go())


def test_mcp_full_experiment_and_chart(tmp_path):
    from quick_query.engine import create
    source=tmp_path/'source.csv';source.write_text('region,amount\nUS,100\nUS,200\nGB,50\n')
    workload={'name':'MCP integration','queries':{'totals':'SELECT region, SUM(amount) AS amount FROM data WHERE region={{region}} GROUP BY region'},'train_cases':[{'region':'US'}],'test_cases':[{'region':'GB'}]}
    workspace=tmp_path/'ws'
    run_id=create(workspace,source,workload,repeats=2,timeout=5,seconds=120)['run_id']
    async def go():
        params=StdioServerParameters(command=sys.executable,args=['-m','quick_query.cli','--workspace',str(workspace),'serve'])
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as session:
                await session.initialize()
                async def call(name,**args):
                    result=await session.call_tool(name,args)
                    assert not result.isError,result
                    return json.loads(result.content[0].text)
                async def wait():
                    for _ in range(200):
                        result=await call('research_status',run_id=run_id)
                        if result['job']['status']!='running':
                            assert result['job']['status']=='idle',result
                            return result
                        await asyncio.sleep(.05)
                    raise AssertionError('MCP worker did not finish')
                await call('start_baseline',run_id=run_id);await wait()
                candidate={'hypothesis':'Use columnar source','materialize':{'sql':'SELECT * FROM data','compression':'zstd'},'queries':{k:v.replace('FROM data','FROM cache') for k,v in workload['queries'].items()}}
                await call('submit_experiment',run_id=run_id,candidate_json=json.dumps(candidate))
                status=await wait();assert status['history'][-1]['correct']
                await call('finalize_research',run_id=run_id);status=await wait()
                assert status['final']['correct_on_final_cases']
                result=await session.call_tool('get_progress_chart',{'run_id':run_id})
                assert not result.isError and result.content[0].type=='image'
    asyncio.run(go())
