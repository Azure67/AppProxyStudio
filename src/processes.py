"""Process associations and observable connection records; never guess proxy usage."""
import ntpath, os, re
from pathlib import Path
import psutil

def pathkey(path):return ntpath.normcase(ntpath.normpath(path)) if path else ''

def related_paths(app):
    result=[]; seen={pathkey(app['path'])}
    for path in app.get('related_paths',[]):
        key=pathkey(path)
        if key and key not in seen:result.append(path);seen.add(key)
    return result

def validate_associations(apps):
    owners={}
    for a in apps:
        for path in [a['path']]+related_paths(a):
            if not ntpath.isabs(path) or not path.lower().endswith('.exe') or any(x in path for x in (',','\r','\n')):
                raise ValueError('程序和辅助进程必须使用完整 EXE 路径，不能含逗号或换行')
            key=pathkey(path)
            if key in owners and owners[key]!=a['id']:raise ValueError('进程已属于另一通道：'+ntpath.basename(path)+'；请先解除原通道关联')
            owners[key]=a['id']

def discover_descendants(app, records):
    """Discover candidates only. The caller requires explicit checked selections."""
    bypid={p['pid']:p for p in records}; roots={p['pid'] for p in records if pathkey(p.get('exe'))==pathkey(app['path'])}
    found={}
    for p in records:
        path=p.get('exe') or ''
        if not path.lower().endswith('.exe') or pathkey(path)==pathkey(app['path']):continue
        cursor=p;visited=set()
        while cursor.get('ppid') in bypid and cursor['pid'] not in visited:
            visited.add(cursor['pid']);parent=bypid[cursor['ppid']]
            if (parent.get('create_time') or 0)>(cursor.get('create_time') or float('inf')):break
            if parent['pid'] in roots:
                found[pathkey(path)]={'path':path,'reason':'正在运行的子进程（需手动勾选）'};break
            cursor=parent
    return list(found.values())

def process_records():
    records=[]
    for p in psutil.process_iter(['pid','ppid','exe','create_time']):
        try:records.append(p.info)
        except (psutil.AccessDenied,psutil.NoSuchProcess):pass
    return records

def discover_related(app):
    found={pathkey(x['path']):x for x in discover_descendants(app,process_records())}
    # Known, narrowly scoped OpenAI backend association survives relaunches.
    from engine import codex_backend_pattern
    if codex_backend_pattern(app):
        base=Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI'/'Codex'/'bin'
        for name in ('codex.exe','codex-code-mode-host.exe'):
            for p in base.glob('*/'+name):found[pathkey(str(p))]={'path':str(p),'reason':'Codex 后台（内置规则已自动关联）','automatic':True}
    for path in related_paths(app):found.setdefault(pathkey(path),{'path':path,'reason':'已保存的关联进程'})
    return sorted(found.values(),key=lambda x:x['path'].lower())

def configured_owner(path,apps):
    from engine import codex_backend_pattern
    key=pathkey(path)
    for a in apps:
        if key and key in {pathkey(a['path'])}|{pathkey(p) for p in related_paths(a)}:return a
    for a in apps:
        pattern=codex_backend_pattern(a)
        if pattern and re.match(pattern,path or ''):return a
    return None

def core_connections(payload,apps):
    groups={'APP-'+a['id']:a for a in apps};rows=[]
    for c in payload.get('connections',[]):
        m=c.get('metadata',{});path=m.get('processPath','');chain=c.get('chains',[])
        owner=next((groups[g] for g in chain if g in groups),None) or configured_owner(path,apps)
        reject=any(x in ('REJECT','REJECT-DROP') for x in chain)
        if reject:route='已阻断'
        elif 'DIRECT' in chain:route='直连'
        elif chain:route='代理 · '+next((g for g in chain if g not in groups),chain[0])
        else:route='未知（等待核心信息）'
        rows.append({'id':c['id'],'path':path,'process':m.get('process') or ntpath.basename(path) or '未知进程',
            'pid':m.get('pid') or '', 'target':str(m.get('host') or m.get('destinationIP',''))+':'+str(m.get('destinationPort','')),
            'channel':owner['name'] if owner else '未分配','route':route,'rule':c.get('rule','')+' '+str(c.get('rulePayload','')),
            'network':m.get('network',''),'observed':True})
    return rows

def system_connections(apps):
    rows=[];cache={}
    for c in psutil.net_connections(kind='inet'):
        if not c.raddr:continue
        pid=c.pid
        if pid not in cache:
            try:p=psutil.Process(pid) if pid else None;cache[pid]=(p.exe(),p.name()) if p else ('','未知进程')
            except (psutil.AccessDenied,psutil.NoSuchProcess):cache[pid]=('','受限进程')
        path,name=cache[pid];owner=configured_owner(path,apps)
        rows.append({'id':str((pid,c.laddr,c.raddr)),'path':path,'process':name,'pid':pid or '',
                     'target':str(c.raddr.ip)+':'+str(c.raddr.port),'channel':owner['name'] if owner else '未分配',
                     'route':'未核实（系统连接）','rule':c.status,'observed':False})
    return rows
