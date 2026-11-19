import base64, copy, concurrent.futures, json, os, socket, sys, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'vendor'),str(ROOT/'src')]
from engine import defaults,generate_config,import_nodes,merge_nodes,CoreManager

def freeport():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def application(i,port,node,enabled=True):
    return {'id':str(i)*12,'name':'App '+str(i),'path':f'C:\\Apps\\app{i}.exe','port':port,'node':node,'enabled':enabled}

class ConfigTests(unittest.TestCase):
    def state(self):
        s=defaults();s['tun']=False;s['nodes']=[{'name':'node1','type':'http','server':'127.0.0.1','port':9981},{'name':'node2','type':'socks5','server':'127.0.0.1','port':9982}];s['apps']=[application(1,18801,'node1'),application(2,18802,'node2')];return s
    def test_split_and_direct_default(self):
        s=self.state();c=generate_config(s,'secret');self.assertEqual(c['rules'][-1],'MATCH,DIRECT');self.assertEqual(c['proxy-groups'][1]['proxies'],['node2']);self.assertEqual(c['listeners'][0]['listen'],'127.0.0.1');self.assertIn('PROCESS-PATH,C:\\Apps\\app1.exe,APP-111111111111',c['rules'])
    def test_disabled_direct(self):
        s=self.state();s['apps'][0]['enabled']=False;self.assertEqual(generate_config(s,'x')['proxy-groups'][0]['proxies'],['DIRECT'])
    def test_duplicate_port_rejected(self):
        s=self.state();s['apps'][1]['port']=18801
        with self.assertRaises(ValueError):generate_config(s,'x')
    def test_duplicate_program_rejected(self):
        s=self.state();s['apps'][1]['path']=s['apps'][0]['path'].upper()
        with self.assertRaises(ValueError):generate_config(s,'x')
    def test_missing_node_rejected(self):
        s=self.state();s['apps'][0]['node']='missing'
        with self.assertRaises(ValueError):generate_config(s,'x')
    def test_yaml_preserves_reality(self):
        n=import_nodes('name: X\ntype: vless\nserver: example.com\nport: 443\nuuid: test\nreality-opts: {public-key: xyz, short-id: abc}\n')[0]
        self.assertEqual(n['reality-opts']['short-id'],'abc')
    def test_ss_uri(self):
        auth=base64.urlsafe_b64encode(b'aes-128-gcm:hello:world').decode().rstrip('=');n=import_nodes('ss://'+auth+'@127.0.0.1:8388#Test')[0];self.assertEqual(n['password'],'hello:world')
    def test_vless_reality(self):
        n=import_nodes('vless://abc@example.com:443?security=reality&pbk=key&sid=01&flow=xtls-rprx-vision#Reality')[0];self.assertEqual(n['reality-opts']['public-key'],'key');self.assertTrue(n['tls'])
    def test_hy2(self):
        self.assertEqual(import_nodes('hy2://pass@example.com:443?sni=test.com#HY')[0]['type'],'hysteria2')
    def test_unsupported_uri_option_rejected(self):
        with self.assertRaises(ValueError):import_nodes('vless://abc@example.com:443?unknown=value')
    def test_base64_subscription(self):
        v=base64.b64encode(b'trojan://secret@example.com:443#T').decode();self.assertEqual(import_nodes(v)[0]['name'],'T')
    def test_merge_preserves_other_nodes(self):
        old=[{'name':'one','value':1},{'name':'two','value':2}];self.assertEqual(merge_nodes(old,[{'name':'one','value':3}]),[{'name':'one','value':3},{'name':'two','value':2}]);self.assertEqual(old[0]['value'],1)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.servers=[]
        def server(tag):
            class Handler(BaseHTTPRequestHandler):
                def do_CONNECT(self):
                    self.send_response(200);self.end_headers();self.wfile.flush()
                    self.rfile.readline()
                    while self.rfile.readline().strip():pass
                    body=tag.encode();self.wfile.write(b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body);self.wfile.flush();self.close_connection=True
                def do_GET(self):
                    body=tag.encode();self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                def log_message(self,*args):pass
            s=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=s.serve_forever,daemon=True).start();self.servers.append(s);return s.server_port
        p1=server('NODE-A');p2=server('NODE-B');self.origin=server('DIRECT')
        self.state=defaults();self.state.update(tun=False,api_port=freeport(),direct_domains=[])
        self.state['nodes']=[{'name':'Alpha','type':'http','server':'127.0.0.1','port':p1},{'name':'Beta','type':'http','server':'127.0.0.1','port':p2}]
        self.state['apps']=[application(1,freeport(),'Alpha'),application(2,freeport(),'Beta')]
        self.manager=CoreManager();self.manager.data=ROOT/'build'/'integration';self.manager.data.mkdir(parents=True,exist_ok=True)
    def tearDown(self):
        self.manager.stop()
        for s in self.servers:s.shutdown();s.server_close()
    def request(self,i,host='127.0.0.1'):
        # Explicit ProxyHandler bypasses loopback on Windows, so issue a raw absolute-form HTTP request.
        with socket.create_connection(('127.0.0.1',self.state['apps'][i]['port']),timeout=4) as s:
            s.sendall(f'GET http://{host}:{self.origin}/probe HTTP/1.1\r\nHost: {host}:{self.origin}\r\nConnection: close\r\n\r\n'.encode())
            data=b''
            while True:
                part=s.recv(8192)
                if not part:break
                data+=part
        return data.split(b'\r\n\r\n',1)[1].decode()
    def test_simultaneous_channels_live_switch_and_disable(self):
        self.manager.start(self.state)
        with concurrent.futures.ThreadPoolExecutor() as pool:
            self.assertEqual(list(pool.map(self.request,[0,1])),['NODE-A','NODE-B'])
        s=copy.deepcopy(self.state);s['apps'][0]['node']='Beta';self.manager.apply(s);self.state=s
        self.assertEqual(self.request(0),'NODE-B')
        s=copy.deepcopy(self.state);s['apps'][0]['enabled']=False;self.manager.apply(s);self.state=s
        self.assertEqual(self.request(0),'DIRECT');self.assertEqual(self.request(1),'NODE-B')
        s=copy.deepcopy(self.state);s['direct_domains']=['localhost'];self.manager.apply(s);self.state=s
        self.assertEqual(self.request(1,'localhost'),'DIRECT')
        ports=[a['port'] for a in self.state['apps']];self.manager.stop()
        for port in ports:
            with socket.socket() as sock:self.assertNotEqual(sock.connect_ex(('127.0.0.1',port)),0)
    def test_invalid_reload_keeps_active_channel(self):
        self.manager.start(self.state);s=copy.deepcopy(self.state);s['apps'][0]['node']='missing'
        with self.assertRaises(ValueError):self.manager.apply(s)
        self.assertTrue(self.manager.running);self.assertEqual(self.request(0),'NODE-A')
    def test_occupied_new_port_keeps_active_channel(self):
        self.manager.start(self.state)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));sock.listen();s=copy.deepcopy(self.state);s['apps'][0]['port']=sock.getsockname()[1]
            with self.assertRaises(ValueError):self.manager.apply(s)
        self.assertEqual(self.request(0),'NODE-A')

if __name__=='__main__':unittest.main(verbosity=2)
