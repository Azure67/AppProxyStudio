import copy,json,os,re,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'vendor'),str(ROOT/'src')]
from engine import codex_backend_pattern,generate_config,defaults,CoreManager
class CodexRules(unittest.TestCase):
 def setUp(self):
  self.state=defaults();self.state['tun']=False
  self.state['nodes']=[{'name':'Test','type':'http','server':'127.0.0.1','port':9981}]
  self.app={'id':'111111111111','name':'ChatGPT','path':r'C:\Program Files\WindowsApps\OpenAI.Codex_test_x64__example\app\ChatGPT.exe','port':18801,'node':'Test','enabled':True}
  self.state['apps']=[self.app]
 def test_real_backend_and_update_versions(self):
  pattern=codex_backend_pattern(self.app)
  for version in ('sample-version','future-version'):
   for exe in ('codex.exe','codex-code-mode-host.exe'):
    self.assertRegex(os.environ['LOCALAPPDATA']+'\\OpenAI\\Codex\\bin\\'+version+'\\'+exe,pattern)
 def test_no_unrelated_program_match(self):
  p=codex_backend_pattern(self.app)
  self.assertIsNone(re.match(p,r'C:\Other\codex.exe'));self.assertIsNone(codex_backend_pattern({'path':r'C:\Other\ChatGPT.exe'}))
 def test_same_group_and_off_switch(self):
  group='APP-'+self.app['id'];c=generate_config(self.state,'test')
  self.assertTrue(any(r.startswith('PROCESS-PATH-REGEX,') and r.endswith(','+group) for r in c['rules']))
  self.app['enabled']=False;c=generate_config(self.state,'test');self.assertEqual(next(g for g in c['proxy-groups'] if g['name']==group)['proxies'],['DIRECT'])
 def test_explicit_rules_win(self):
  c=generate_config(self.state,'test');first=next(i for i,r in enumerate(c['rules']) if r.startswith('PROCESS-PATH-REGEX,'));last=max(i for i,r in enumerate(c['rules']) if r.startswith('PROCESS-PATH,'));self.assertGreater(first,last)
 def test_real_core_accepts_regex(self):
  m=CoreManager();m.data=ROOT/'build'/'codex-validation';m.data.mkdir(parents=True,exist_ok=True);m.validate(self.state)
if __name__=='__main__':unittest.main(verbosity=2)
