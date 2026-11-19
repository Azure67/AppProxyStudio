import sys, os, copy, subprocess, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'vendor'),str(ROOT/'src'),str(ROOT/'tests')]
from test_engine import IntegrationTests
from engine import defaults
case=IntegrationTests();case.setUp()
try:
    case.state['tun']=True
    case.state['apps'][0]['path']=r'C:\Windows\System32\curl.exe'
    case.state['apps'][1]['path']=r'C:\Windows\SysWOW64\curl.exe'
    case.manager.start(case.state)
    env={k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy','no_proxy')}
    def request(exe):
        result=subprocess.run([exe,'--noproxy','*','--max-time','8','--silent','--show-error','http://198.51.100.123/probe'],capture_output=True,timeout=12,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode,result.stdout.decode(errors='replace')
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        results=list(pool.map(request,[a['path'] for a in case.state['apps']]))
    print('TUN process routes:',results)
    assert results==[(0,'NODE-A'),(0,'NODE-B')],results
    updated=copy.deepcopy(case.state);updated['apps'][0]['node']='Beta';case.manager.apply(updated)
    assert request(updated['apps'][0]['path'])==(0,'NODE-B')
    updated['apps'][0]['enabled']=False;case.manager.apply(updated)
    code,body=request(updated['apps'][0]['path']);assert body not in ('NODE-A','NODE-B'),(code,body)
    assert request(updated['apps'][1]['path'])==(0,'NODE-B')
    print('TUN live node switch / individual disable: PASS')
finally:case.tearDown()
