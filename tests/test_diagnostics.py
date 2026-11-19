import copy,os,socket,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'vendor'),str(ROOT/'src'),str(ROOT/'tests')]
from engine import defaults
from test_engine import application
from diagnostics import diagnose,probe_port,environment_snapshot

class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.state=defaults();self.state['nodes']=[{'name':'A','type':'http','server':'127.0.0.1','port':9001}];self.state['apps']=[application(1,18801,'A')]
        self.snap=dict(admin=True,env_proxy=[],system_proxy=False,pac=False,interfaces=[],interfaces_known=True,registry_known=True)
    def check(self,**kw):
        options=dict(snapshot=self.snap,exists=lambda p:True,probe=lambda port,udp:True);options.update(kw)
        return diagnose(self.state,ROOT,**options)
    def test_missing_admin_blocks_tun_only(self):
        self.snap['admin']=False;self.assertTrue(any(r['level']=='error' for r in self.check()))
        self.state['tun']=False;self.assertFalse(any(r['level']=='error' for r in self.check()))
    def test_active_tun_warns_but_own_running_tun_does_not(self):
        self.snap['interfaces']=['Ethernet','FlClash TUN','AppProxyStudio']
        rows=self.check(owned_ports={(19791,'TCP')});warning=next(r for r in rows if r['check']=='其他虚拟网卡')
        self.assertIn('FlClash',warning['detail']);self.assertNotIn('AppProxyStudio',warning['detail'])
        self.snap['interfaces']=['Ethernet','Teredo Tunneling Pseudo-Interface','AppProxyStudio'];self.assertFalse(any(r['check']=='其他虚拟网卡' for r in self.check(owned_ports={(19791,'TCP')})))
        self.assertTrue(any(r['check']=='其他虚拟网卡' for r in self.check()))
    def test_tcp_udp_owner_and_no_owned_port_false_positive(self):
        rows=self.check(probe=lambda p,u:False,owned_ports={(19791,'TCP'),(18801,'TCP')},owners={(18801,'UDP'):'test.exe (PID 123)'})
        conflicts=[r for r in rows if r['check'].startswith('端口 ')]
        self.assertEqual(len(conflicts),1);self.assertIn('UDP',conflicts[0]['check']);self.assertIn('PID 123',conflicts[0]['detail'])
    def test_real_tcp_and_udp_binding_conflicts(self):
        for udp in (False,True):
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM if udp else socket.SOCK_STREAM) as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                self.assertFalse(probe_port(port,udp))
            self.assertTrue(probe_port(port,udp))
    def test_missing_core_and_bad_configuration_block(self):
        self.assertTrue(any(r['level']=='error' for r in self.check(exists=lambda p:False)))
        self.state['apps'][0]['node']='missing';self.assertTrue(any(r['check']=='配置规则' and r['level']=='error' for r in self.check()))
    def test_paths_warn_and_no_state_mutation(self):
        before=copy.deepcopy(self.state);rows=self.check(exists=lambda p:str(p).endswith('mihomo.exe'))
        self.assertTrue(any(r['check']=='程序路径' for r in rows));self.assertEqual(self.state,before)
    def test_proxy_environment_values_never_reported(self):
        with patch.dict(os.environ,{'HTTPS_PROXY':'http://username:secret-value@proxy.example:1234'}):
            snap=environment_snapshot();self.assertIn('HTTPS_PROXY',snap['env_proxy']);self.assertNotIn('secret-value',str(snap))
        self.snap.update(env_proxy=['HTTPS_PROXY'],system_proxy=True,pac=True)
        rows=self.check();self.assertTrue(any(r['check']=='Windows 显式代理' for r in rows));self.assertTrue(any(r['check']=='进程环境代理' for r in rows))
    def test_unavailable_checks_are_not_reported_as_pass(self):
        self.snap.update(interfaces_known=False,registry_known=False)
        rows=self.check();self.assertTrue(any(r['check']=='网卡检查' and r['level']=='warning' for r in rows));self.assertTrue(any(r['check']=='Windows 显式代理' and r['level']=='warning' for r in rows))

if __name__=='__main__':unittest.main(verbosity=2)
