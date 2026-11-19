"""Read-only startup checks. Findings do not imply successful proxy routing."""
import ctypes, os, re, socket
from pathlib import Path
import psutil
from processes import related_paths

def finding(level,check,detail,action=''):
    return dict(level=level,check=check,detail=detail,action=action)

def probe_port(port,udp=False):
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM if udp else socket.SOCK_STREAM) as sock:
        if os.name=='nt':sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        try:sock.bind(('127.0.0.1',int(port)));return True
        except OSError:return False

def environment_snapshot():
    snap={'admin':bool(ctypes.windll.shell32.IsUserAnAdmin()) if os.name=='nt' else False,
          'env_proxy':[k for k,v in os.environ.items() if v and k.lower() in ('http_proxy','https_proxy','all_proxy')],
          'system_proxy':False,'pac':False,'registry_known':True,'interfaces':[],'interfaces_known':True}
    if os.name=='nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                def value(name):
                    try:return winreg.QueryValueEx(key,name)[0]
                    except FileNotFoundError:return None
                snap['system_proxy']=bool(value('ProxyEnable'));snap['pac']=bool(value('AutoConfigURL'))
        except OSError:snap['registry_known']=False
    try:snap['interfaces']=[name for name,stat in psutil.net_if_stats().items() if stat.isup]
    except (OSError,psutil.Error):snap['interfaces_known']=False
    return snap

def port_owners():
    result={}
    try:
        for c in psutil.net_connections(kind='inet'):
            if not c.laddr or (c.type==socket.SOCK_STREAM and c.status!=psutil.CONN_LISTEN):continue
            if c.laddr.ip not in ('0.0.0.0','127.0.0.1','::','::1'):continue
            protocol='UDP' if c.type==socket.SOCK_DGRAM else 'TCP'
            name='未知进程'
            if c.pid:
                try:name=psutil.Process(c.pid).name()
                except (psutil.Error,OSError):pass
            result[(c.laddr.port,protocol)]=name+(' (PID '+str(c.pid)+')' if c.pid else '')
    except (psutil.Error,OSError):pass
    return result

def diagnose(state,root,owned_ports=(),snapshot=None,probe=probe_port,exists=None,owners=None):
    from engine import generate_config
    root=Path(root);exists=exists or (lambda p:Path(p).is_file());out=[]
    snap=environment_snapshot() if snapshot is None else snapshot
    if not exists(root/'core'/'mihomo.exe'):
        out.append(finding('error','核心文件','缺少 core/mihomo.exe','运行 setup.ps1 安装核心。'))
    else:out.append(finding('ok','核心文件','已找到 Mihomo 核心'))
    if not state['apps']:out.append(finding('error','应用通道','没有已配置的应用','先添加软件并选择节点。'))
    try:generate_config(state,'diagnostic-placeholder')
    except (ValueError,KeyError,TypeError):
        out.append(finding('error','配置规则','配置结构、端口、节点选择或进程归属无效','检查应用配置；保存时会显示具体校验错误。'));return out
    if state['tun']:
        out.append(finding('ok' if snap['admin'] else 'error','管理员权限',
            '已具有管理员权限' if snap['admin'] else 'TUN 模式需要管理员权限',
            '' if snap['admin'] else '在分流设置中以管理员身份重启，或关闭 TUN 使用独立端口。'))
        suspects=[n for n in snap['interfaces'] if re.search(r'(^|[\s_-])tun[0-9]*($|[\s_-])|wintun|clash|mihomo|wireguard|warp|tailscale|appproxystudio',n,re.I) and not (owned_ports and n=='AppProxyStudio')]
        if suspects:out.append(finding('warning','其他虚拟网卡','检测到可能影响路由的活动接口：'+', '.join(suspects),'检查对应 VPN/代理工具的 TUN；确认路由安排后再启动。不会自动停用网卡。'))
        elif not snap.get('interfaces_known',True):out.append(finding('warning','网卡检查','无法读取接口状态','提升权限后重试，或手动检查其他 VPN/TUN。'))
        else:out.append(finding('info','网卡检查','未发现名称匹配的其他活动 TUN','仅按接口名称识别，不能排除自定义名称或路由冲突。'))
        for a in state['apps']:
            for p in [a['path']]+related_paths(a):
                if not exists(p):out.append(finding('warning','程序路径',a['name']+'：'+str(p),'主程序用“更换路径”修复；辅助程序在“关联辅助进程”中更新。'))
    else:out.append(finding('info','独立端口模式','不自动接管应用连接','在目标软件内设置对应的本地 HTTP/SOCKS5 端口。'))
    ports=[(int(state['api_port']),'TCP')]+[(int(a['port']),protocol) for a in state['apps'] for protocol in ('TCP','UDP')]
    for port,protocol in ports:
        if (port,protocol) in owned_ports:continue
        if not probe(port,protocol=='UDP'):
            owner=(owners or {}).get((port,protocol),'占用者未知或端口受系统保留')
            out.append(finding('error','端口 '+str(port)+' / '+protocol,owner,'更换此端口，或自行关闭占用它的程序后重试。'))
    if not any(x['check'].startswith('端口 ') for x in out):out.append(finding('ok','本地端口','未检测到绑定冲突（运行中本引擎端口除外）','启动时仍会再次检查，以防端口被抢占。'))
    if snap['system_proxy'] or snap['pac']:
        out.append(finding('warning' if state['tun'] else 'info','Windows 显式代理','当前用户启用了系统代理或 PAC','采用系统代理的软件可能先连接其他本地代理；核对该软件的代理设置。'))
    if not snap.get('registry_known',True):out.append(finding('warning','Windows 显式代理','无法读取当前用户代理设置','手动检查 Windows 代理设置。'))
    if snap['env_proxy']:out.append(finding('warning' if state['tun'] else 'info','进程环境代理','当前工具环境含 '+', '.join(snap['env_proxy']),'从本工具启动的程序会继承环境；核对 HTTP_PROXY / HTTPS_PROXY / ALL_PROXY。'))
    out.append(finding('info','检查范围','未测试节点连通性；不能读取其他进程的完整环境、启动参数及所有内置代理设置。','启动后在“联网进程”查看实际走向；节点库可单独测试延迟。'))
    return out

def collect_diagnostics(state,root,owned_ports=()):
    return diagnose(state,root,owned_ports,owners=port_owners())
