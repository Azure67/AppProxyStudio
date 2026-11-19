import copy,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'vendor'),str(ROOT/'src'),str(ROOT/'tests')]
from engine import defaults,generate_config
from processes import discover_descendants,configured_owner,core_connections,validate_associations,related_paths
from test_engine import application
class ProcessTests(unittest.TestCase):
 def state(self):
  s=defaults();s['tun']=False;s['nodes']=[{'name':'A','type':'http','server':'127.0.0.1','port':9001}];s['apps']=[application(1,18801,'A'),application(2,18802,'A')];return s
 def test_helper_shares_group(self):
  s=self.state();s['apps'][0]['related_paths']=[r'C:\Apps\helper.exe'];c=generate_config(s,'test');self.assertIn(r'PROCESS-PATH,C:\Apps\helper.exe,APP-111111111111',c['rules'])
 def test_disabled_helpers_direct(self):
  s=self.state();s['apps'][0].update(enabled=False,related_paths=[r'C:\Apps\helper.exe']);c=generate_config(s,'test');self.assertEqual(c['proxy-groups'][0]['proxies'],['DIRECT'])
 def test_conflict_between_helpers(self):
  s=self.state()
  for a in s['apps']:a['related_paths']=[r'C:\Apps\helper.exe']
  with self.assertRaises(ValueError):generate_config(s,'x')
 def test_helper_cannot_capture_explicit_app(self):
  s=self.state();s['apps'][0]['related_paths']=[s['apps'][1]['path']]
  with self.assertRaises(ValueError):validate_associations(s['apps'])
 def test_duplicate_helpers_normalized(self):
  a=self.state()['apps'][0];a['related_paths']=[r'C:\Apps\helper.exe',r'C:\APPS\HELPER.EXE'];self.assertEqual(len(related_paths(a)),1)
 def test_relative_path_rejected(self):
  s=self.state();s['apps'][0]['related_paths']=['helper.exe']
  with self.assertRaises(ValueError):generate_config(s,'x')
 def test_descendants_not_unrelated(self):
  app=self.state()['apps'][0];records=[{'pid':1,'ppid':0,'exe':app['path'],'create_time':10},{'pid':2,'ppid':1,'exe':r'C:\Apps\helper.exe','create_time':11},{'pid':3,'ppid':2,'exe':r'C:\Apps\nested.exe','create_time':12},{'pid':4,'ppid':0,'exe':r'C:\Apps\other.exe','create_time':13}]
  rows=discover_descendants(app,records);self.assertEqual(len(rows),2);self.assertFalse(any(x.get('selected') for x in rows))
 def test_pid_reuse_does_not_associate(self):
  app=self.state()['apps'][0];rows=discover_descendants(app,[{'pid':1,'ppid':0,'exe':app['path'],'create_time':20},{'pid':2,'ppid':1,'exe':r'C:\Apps\old.exe','create_time':10}]);self.assertEqual(rows,[])
 def test_actual_direct_exception_not_inferred_proxy(self):
  s=self.state();c={'id':'one','metadata':{'processPath':s['apps'][0]['path'],'host':'local.test','destinationPort':443},'chains':['DIRECT'],'rule':'DomainSuffix','rulePayload':'local.test'};row=core_connections({'connections':[c]},s['apps'])[0];self.assertEqual(row['route'],'直连');self.assertEqual(row['channel'],s['apps'][0]['name'])
 def test_actual_proxy_and_unknown(self):
  s=self.state();payload={'connections':[{'id':'a','metadata':{},'chains':['A','APP-111111111111']},{'id':'b','metadata':{},'chains':[]}]};rows=core_connections(payload,s['apps']);self.assertEqual(rows[0]['route'],'代理 · A');self.assertIn('未知',rows[1]['route']);self.assertEqual(rows[0]['pid'],'')
if __name__=='__main__':unittest.main(verbosity=2)
