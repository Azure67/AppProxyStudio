"""AppProxy Studio: portable configuration, node import and Mihomo lifecycle."""
from __future__ import annotations
import base64, copy, ctypes, json, os, re, secrets, socket, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote, quote
from urllib.request import Request, build_opener, ProxyHandler
import yaml
import psutil
from processes import related_paths, validate_associations

ROOT = Path(sys.executable).resolve().parents[2] if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CORE = ROOT / 'core' / 'mihomo.exe'
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
SUPPORTED = {'ss','ssr','vmess','vless','trojan','hysteria','hysteria2','tuic','http','socks5','wireguard','snell','ssh','mieru','anytls'}

def atomic_write(path, text):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(text, encoding='utf-8')
    os.replace(temp, path)

def defaults():
    return {'version':1, 'tun':True, 'api_port':19791, 'apps':[],
            'direct_domains':['10jqka.com.cn','hexin.cn'], 'nodes':[]}

def load_state():
    path = DATA / 'settings.json'
    if not path.exists(): return defaults()
    obj = json.loads(path.read_text(encoding='utf-8'))
    if obj.get('version') != 1: raise ValueError('不支持的配置版本')
    return {**defaults(), **obj}

def save_state(state):
    atomic_write(DATA / 'settings.json', json.dumps(state, ensure_ascii=False, indent=2))

def b64(s):
    s = s.strip().replace('-', '+').replace('_', '/')
    return base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8')

def parse_uri(line):
    u = urlsplit(line); scheme = u.scheme.lower(); q = parse_qs(u.query)
    get = lambda k, default='': q.get(k, [default])[0]
    if scheme == 'vmess':
        v = json.loads(b64(line.split('://',1)[1]))
        if str(v.get('net','tcp')) not in ('tcp','ws','grpc'): raise ValueError('VMess 传输方式请使用 YAML 导入')
        n = {'name':v.get('ps') or v['add'], 'type':'vmess','server':v['add'],'port':int(v['port']),
             'uuid':v['id'],'alterId':int(v.get('aid',0)), 'cipher':v.get('scy','auto'), 'udp':True}
        if v.get('tls') == 'tls': n.update(tls=True, servername=v.get('sni') or v.get('host') or v['add'])
        net = v.get('net','tcp')
        if net != 'tcp': n['network']=net
        if net == 'ws': n['ws-opts']={'path':v.get('path','/'),'headers':{'Host':v.get('host',v['add'])}}
        if net == 'grpc': n['grpc-opts']={'grpc-service-name':v.get('path','')}
        return n
    if scheme == 'ss':
        body = line.split('://',1)[1].split('#',1)[0]
        if '?' in body: body = body.split('?',1)[0]
        if '@' not in body: body = b64(body)
        auth, host = body.rsplit('@',1)
        auth = unquote(auth)
        if ':' not in auth: auth = b64(auth)
        cipher, password = auth.split(':',1)
        addr = urlsplit('ss://' + host)
        n={'name':unquote(u.fragment) or addr.hostname,'type':'ss','server':addr.hostname,
           'port':addr.port,'cipher':cipher,'password':password,'udp':True}
        if get('plugin'): raise ValueError('带插件的 SS 节点请通过 YAML 导入，避免丢失插件参数')
        return n
    aliases={'hy2':'hysteria2','socks':'socks5','https':'http'}
    kind=aliases.get(scheme,scheme)
    if kind not in {'vless','trojan','hysteria2','tuic','socks5','http'}:
        raise ValueError('此分享链接暂不支持，请使用 Clash/Mihomo YAML 导入')
    if not u.hostname or not u.port: raise ValueError('分享链接缺少服务器或端口')
    n={'name':unquote(u.fragment) or u.hostname,'type':kind,'server':u.hostname,'port':u.port}
    username=unquote(u.username or ''); password=unquote(u.password or '')
    if kind=='vless': n.update(uuid=username, udp=True)
    elif kind=='tuic': n.update(uuid=username,password=password,udp=True)
    elif kind in ('trojan','hysteria2'): n.update(password=username + ((':'+password) if password else ''),udp=True)
    else:
        if username: n['username']=username
        if password: n['password']=password
    if kind=='trojan': n['sni']=get('sni') or u.hostname
    if scheme=='https': n['tls']=True
    if get('security') in ('tls','reality') or get('tls')=='1': n['tls']=True
    if get('sni'): n['servername' if kind=='vless' else 'sni']=get('sni')
    if get('insecure') in ('1','true') or get('allowInsecure')=='1': n['skip-cert-verify']=True
    if get('alpn'): n['alpn']=get('alpn').split(',')
    if get('fp'): n['client-fingerprint']=get('fp')
    if get('flow'): n['flow']=get('flow')
    if get('security')=='reality':
        if not get('pbk'): raise ValueError('Reality 链接缺少公钥')
        n['reality-opts']={'public-key':get('pbk'),'short-id':get('sid')}
    net=get('type','tcp')
    if net not in ('tcp','ws','grpc'): raise ValueError('此传输方式请用 YAML 导入')
    if net!='tcp': n['network']=net
    if net=='ws': n['ws-opts']={'path':get('path','/'),'headers':{'Host':get('host',u.hostname)}}
    if net=='grpc': n['grpc-opts']={'grpc-service-name':get('serviceName')}
    if get('obfs'):
        n['obfs']=get('obfs'); n['obfs-password']=get('obfs-password')
    if get('congestion_control'): n['congestion-controller']=get('congestion_control')
    # Do not silently accept URI features we cannot faithfully translate.
    allowed={'sni','security','tls','insecure','allowInsecure','alpn','fp','flow','pbk','sid','type','path','host','serviceName','obfs','obfs-password','congestion_control','encryption'}
    unknown=set(q)-allowed
    if unknown: raise ValueError('链接含未支持参数 '+', '.join(sorted(unknown))+'；请改用 YAML')
    return n

def import_nodes(text):
    text=text.strip().lstrip('\ufeff')
    if len(text)>8*1024*1024: raise ValueError('导入内容超过 8 MB')
    if '://' not in text and not any(x in text for x in ('proxies:', 'server:', '{','[')):
        try: text=b64(text)
        except Exception: pass
    if text.splitlines() and re.match(r'^[a-z0-9]+://',text.splitlines()[0]):
        nodes=[]
        for i,line in enumerate(text.splitlines(),1):
            if line.strip():
                try: nodes.append(parse_uri(line.strip()))
                except Exception as e: raise ValueError(f'第 {i} 行：{e}') from e
    else:
        doc=yaml.safe_load(text)
        nodes=doc.get('proxies', [doc] if 'type' in doc else []) if isinstance(doc,dict) else doc
    if not isinstance(nodes,list) or not nodes: raise ValueError('未找到节点。需要 proxies 列表、节点 YAML 或分享链接。')
    if len(nodes)>2000: raise ValueError('单次最多导入 2000 个节点')
    for n in nodes:
        if not isinstance(n,dict) or not all(n.get(k) for k in ('name','type','server','port')): raise ValueError('节点缺少 name/type/server/port')
        if n['type'] not in SUPPORTED: raise ValueError('当前版本不支持节点类型：'+str(n['type']))
        if not 1<=int(n['port'])<=65535: raise ValueError('节点端口不合法')
        if any(c in str(n['name']) for c in '\r\n,'): raise ValueError('节点名称不能含逗号或换行')
        if n['name'] in ('DIRECT','REJECT') or str(n['name']).startswith('APP-'): raise ValueError('节点使用了保留名称')
        if n.get('dialer-proxy'): raise ValueError('带链式 dialer-proxy 的节点请先改成独立节点')
    return nodes

def merge_nodes(existing,incoming):
    result=copy.deepcopy(existing)
    for node in incoming:
        same=next((n for n in result if n['name']==node['name']),None)
        if same: result[result.index(same)]=copy.deepcopy(node)
        else: result.append(copy.deepcopy(node))
    return result

def fetch_subscription(url):
    if urlsplit(url).scheme not in ('https','http'): raise ValueError('订阅地址必须是 HTTP 或 HTTPS')
    req=Request(url,headers={'User-Agent':'clash.meta/AppProxyStudio'})
    with build_opener(ProxyHandler({})).open(req,timeout=25) as r:
        content=r.read(8*1024*1024+1)
    if len(content)>8*1024*1024: raise ValueError('订阅超过 8 MB')
    return import_nodes(content.decode('utf-8-sig'))

def codex_backend_pattern(app):
    """Associate only the installed OpenAI desktop package with its owned backend."""
    path=app['path'].replace('/', '\\').lower()
    if '\\windowsapps\\openai.codex_' not in path or not path.endswith('\\app\\chatgpt.exe'):
        return None
    local=os.environ.get('LOCALAPPDATA')
    if not local: return None
    base=str(Path(local)/'OpenAI'/'Codex'/'bin')
    return r'(?i)^'+re.escape(base)+r'\\[^\\]+\\(?:codex|codex-code-mode-host)\.exe$'

def generate_config(state,secret):
    validate_associations(state['apps'])
    nodes=state['nodes']; names={n['name'] for n in nodes}; ports=set(); paths=set(); groups=[]; listeners=[]; rules=[]
    api=int(state.get('api_port',19791))
    if not 1024<=api<=65535: raise ValueError('控制端口必须为 1024–65535')
    for d in state.get('direct_domains',[]):
        d=d.strip().lower().lstrip('.')
        if not re.fullmatch(r'[a-z0-9.-]+',d): raise ValueError('直连域名格式错误：'+d)
        rules.append('DOMAIN-SUFFIX,'+d+',DIRECT')
    for app in state['apps']:
        port=int(app['port']); path=app['path']; key=os.path.normcase(path)
        if not 1024<=port<=65535 or port==api or port in ports: raise ValueError('软件端口重复、超出范围或与控制端口冲突')
        if not path.lower().endswith('.exe') or ',' in path or '\n' in path: raise ValueError('请选择有效的 EXE 路径（不能包含逗号）')
        if key in paths: raise ValueError('同一个程序只能绑定一个通道')
        if not re.fullmatch(r'[a-f0-9]{12}',app['id']): raise ValueError('通道 ID 无效')
        paths.add(key); ports.add(port)
        group='APP-'+app['id']; node=app.get('node','')
        if app['enabled'] and node not in names: raise ValueError(app['name']+' 尚未选择有效节点')
        selected=node if app['enabled'] else 'DIRECT'
        groups.append({'name':group,'type':'select','proxies':[selected]})
        listeners.append({'name':group,'type':'mixed','port':port,'listen':'127.0.0.1','udp':True})
        rules.append('IN-NAME,'+group+','+group)
    for app in state['apps']:
        for path in [app['path']]+related_paths(app):
            rules.append('PROCESS-PATH,'+path+',APP-'+app['id'])
    # Explicit software entries have precedence over automatic package associations.
    for app in state['apps']:
        pattern=codex_backend_pattern(app)
        if pattern:
            rules.append('PROCESS-PATH-REGEX,'+pattern+',APP-'+app['id'])
    rules.append('MATCH,DIRECT')
    return {'mode':'rule','log-level':'warning','ipv6':True,'allow-lan':False,'find-process-mode':'always',
            'external-controller':f'127.0.0.1:{api}','secret':secret,'proxies':copy.deepcopy(nodes),
            'proxy-groups':groups,'listeners':listeners,'rules':rules,
            'tun':{'enable':bool(state['tun']),'device':'AppProxyStudio','stack':'mixed','auto-route':True,
                   'auto-detect-interface':True,'strict-route':False,'dns-hijack':['any:53','tcp://any:53']},
            'dns':{'enable':True,'listen':'127.0.0.1:0','ipv6':True,'enhanced-mode':'redir-host',
                   'nameserver':['223.5.5.5','119.29.29.29'],'proxy-server-nameserver':['223.5.5.5','119.29.29.29']}}

class CoreManager:
    def __init__(self,root=ROOT):
        self.root=Path(root); self.data=self.root/'data'; self.data.mkdir(parents=True,exist_ok=True)
        self.core=self.root/'core'/'mihomo.exe'; self.proc=None; self.logfile=None; self.secret=secrets.token_hex(24)
        self.state=None; self.job=None
    @property
    def running(self): return self.proc is not None and self.proc.poll() is None
    def api(self,method,path,payload=None):
        req=Request('http://127.0.0.1:'+str(self.state['api_port'])+path,
                    data=json.dumps(payload).encode() if payload is not None else None,method=method,
                    headers={'Authorization':'Bearer '+self.secret,'Content-Type':'application/json'})
        with build_opener(ProxyHandler({})).open(req,timeout=12) as r:
            data=r.read(); return json.loads(data) if data else None
    def validate(self,state):
        if not self.core.exists(): raise ValueError('缺少 core/mihomo.exe')
        config=generate_config(state,self.secret)
        candidate=self.data/'candidate.yaml'
        atomic_write(candidate,yaml.safe_dump(config,allow_unicode=True,sort_keys=False))
        result=subprocess.run([str(self.core),'-t','-d',str(self.data),'-f',str(candidate)],capture_output=True,creationflags=FLAGS,timeout=25)
        if result.returncode:
            # Do not expose server secrets accidentally echoed by a core parser.
            raise ValueError('Mihomo 配置校验失败。请检查节点字段及当前核心的协议支持；现有运行配置未改变。')
        return candidate
    def _attach_job(self):
        # A kill-on-close Windows Job prevents orphaned TUN processes after GUI crashes.
        if os.name!='nt': return
        from ctypes import wintypes as w
        class BASIC(ctypes.Structure):
            _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
        class IO(ctypes.Structure): _fields_=[(x,ctypes.c_ulonglong) for x in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
        class EXT(ctypes.Structure): _fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateJobObjectW.restype=w.HANDLE; k.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR]
        k.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]; k.CloseHandle.argtypes=[w.HANDLE]
        job=k.CreateJobObjectW(None,None); info=EXT(); info.BasicLimitInformation.LimitFlags=0x2000
        if not job or not k.SetInformationJobObject(job,9,ctypes.byref(info),ctypes.sizeof(info)) or not k.AssignProcessToJobObject(job,w.HANDLE(int(self.proc._handle))):
            if job:k.CloseHandle(job)
            raise RuntimeError('无法建立进程保护，已取消启动以避免遗留 TUN 进程')
        self.job=job
    def start(self,state):
        if self.running: raise ValueError('核心已经运行')
        if state['tun'] and os.name=='nt' and not ctypes.windll.shell32.IsUserAnAdmin(): raise ValueError('TUN 分流需要管理员权限，请使用“以管理员身份重启”')
        if not state['apps']: raise ValueError('请先添加一个软件通道')
        candidate=self.validate(state)
        for port in [state['api_port']]+[a['port'] for a in state['apps']]:
            with socket.socket() as sock:
                try: sock.bind(('127.0.0.1',int(port)))
                except OSError: raise ValueError(f'端口 {port} 已被其他程序占用')
        runtime=self.data/'runtime.yaml'; atomic_write(runtime,candidate.read_text(encoding='utf-8'))
        self.state=copy.deepcopy(state)
        self.logfile=open(self.data/'core.log','w',encoding='utf-8')
        self.proc=subprocess.Popen([str(self.core),'-d',str(self.data),'-f',str(runtime)],stdout=self.logfile,stderr=subprocess.STDOUT,creationflags=FLAGS,cwd=self.root)
        try:
            self._attach_job()
            for _ in range(60):
                if not self.running: raise RuntimeError('核心启动失败。请检查端口、管理员权限和其他 VPN/TUN 冲突。')
                try:
                    self.api('GET','/version')
                    if state['tun']:
                        nic=psutil.net_if_stats().get('AppProxyStudio')
                        if not nic or not nic.isup:
                            time.sleep(.1); continue
                    return
                except Exception: time.sleep(.1)
            raise RuntimeError('核心启动超时')
        except Exception: self.stop(); raise
    def apply(self,state):
        if not self.running: self.validate(state); return
        if state['tun']!=self.state['tun'] or state['api_port']!=self.state['api_port']:
            raise ValueError('更换 TUN 模式或控制端口前，请先停止引擎')
        old=copy.deepcopy(self.state)
        old_ports={int(a['port']) for a in old['apps']}
        for a in state['apps']:
            if int(a['port']) not in old_ports:
                with socket.socket() as sock:
                    try: sock.bind(('127.0.0.1',int(a['port'])))
                    except OSError: raise ValueError(f"端口 {a['port']} 已被其他程序占用")
        candidate=self.validate(state)
        try:
            self.api('PUT','/configs?force=true',{'path':str(candidate)})
        except Exception:
            try: self.api('PUT','/configs?force=true',{'path':str(self.data/'runtime.yaml')})
            except Exception: self.stop()
            raise ValueError('配置应用失败，已尝试恢复原配置；请检查引擎状态。')
        self.state=copy.deepcopy(state)
        atomic_write(self.data/'runtime.yaml',candidate.read_text(encoding='utf-8'))
        # Reset only flows owned by managed channels; otherwise old sockets keep the previous node.
        before={a['id']:a for a in old['apps']}; after={a['id']:a for a in state['apps']}
        old_nodes={n['name']:n for n in old['nodes']}; new_nodes={n['name']:n for n in state['nodes']}
        changed=set()
        for key in set(before)|set(after):
            a=before.get(key); b=after.get(key)
            if a!=b or old['direct_domains']!=state['direct_domains'] or (b and old_nodes.get(b['node'])!=new_nodes.get(b['node'])):
                changed.add(key)
        paths={os.path.normcase(path) for a in old['apps']+state['apps'] if a['id'] in changed for path in [a['path']]+related_paths(a)}
        groups={'APP-'+key for key in changed}
        try:
            for c in (self.api('GET','/connections') or {}).get('connections',[]):
                meta=c.get('metadata',{})
                if os.path.normcase(meta.get('processPath','')) in paths or groups.intersection(c.get('chains',[])) or any(codex_backend_pattern(a) and re.match(codex_backend_pattern(a),meta.get('processPath','')) for a in old['apps']+state['apps'] if a['id'] in changed):
                    self.api('DELETE','/connections/'+quote(c['id'],safe=''))
        except Exception: pass
    def stop(self):
        if self.proc:
            if self.running:
                self.proc.terminate()
                try:self.proc.wait(timeout=8)
                except subprocess.TimeoutExpired:self.proc.kill(); self.proc.wait(timeout=5)
            self.proc=None
        if self.job:
            from ctypes import wintypes
            close=ctypes.windll.kernel32.CloseHandle; close.argtypes=[wintypes.HANDLE]; close(wintypes.HANDLE(self.job)); self.job=None
        if self.logfile:self.logfile.close(); self.logfile=None
    def delay(self,node):
        return self.api('GET','/proxies/'+quote(node,safe='')+'/delay?timeout=5000&url='+quote('https://www.gstatic.com/generate_204',safe='')).get('delay')
