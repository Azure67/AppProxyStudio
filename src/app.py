"""Qt desktop UI for AppProxy Studio. All persistent files remain in the project."""
from __future__ import annotations
import copy, ctypes, os, secrets, socket, subprocess, sys, time
from pathlib import Path
import psutil, yaml
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QIcon
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
 QTabWidget,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QSplitter,QFormLayout,QLineEdit,
 QComboBox,QCheckBox,QSpinBox,QPlainTextEdit,QMessageBox,QFileDialog,QInputDialog,QDialog,QDialogButtonBox,QFrame)
from engine import ROOT,DATA,CoreManager,load_state,save_state,import_nodes,merge_nodes,fetch_subscription

sys.modules.setdefault('app',sys.modules[__name__])
from process_ui import ProcessFeatures
from diagnostic_ui import DiagnosticFeatures
from processes import related_paths

STYLE='''
QWidget { background:#f3f3f3; color:#242424; font-family:"Microsoft YaHei UI"; font-size:13px; }
QLabel { background:transparent; }
QLabel#muted { color:#666666; }
QLabel#status { color:#555555; }
QLabel#section { font-weight:600; padding-bottom:6px; }
QFrame#toolbar { border-bottom:1px solid #d5d5d5; }
QPushButton { background:#fafafa; border:1px solid #bcbcbc; border-radius:3px; padding:5px 12px; min-height:20px; }
QPushButton:hover { background:#eaf2fa; border-color:#6f9dc6; }
QPushButton:pressed { background:#d8e8f6; }
QPushButton:disabled { color:#999999; background:#eeeeee; border-color:#d8d8d8; }
QPushButton#accent { background:#f8fbff; border-color:#7a9bbb; color:#174f7d; }
QPushButton#accent:hover { background:#e2edf7; }
QPushButton#danger { color:#a32929; }
QTabWidget::pane { border:1px solid #cccccc; background:#f3f3f3; }
QTabBar::tab { background:#e8e8e8; color:#555555; border:1px solid #cccccc; border-bottom:0; padding:7px 20px; margin-right:2px; }
QTabBar::tab:selected { background:#f3f3f3; color:#174f7d; border-top:2px solid #3876a8; padding-top:6px; }
QTabBar::tab:hover { background:#ededed; }
QTableWidget { background:#ffffff; alternate-background-color:#f7f7f7; border:1px solid #cccccc; gridline-color:#e8e8e8; selection-background-color:#dcebf8; selection-color:#172f44; }
QTableWidget::item { padding:3px 8px; }
QHeaderView::section { background:#eeeeee; color:#444444; border:0; border-right:1px solid #d8d8d8; border-bottom:1px solid #cccccc; padding:6px 8px; }
QLineEdit,QComboBox,QSpinBox,QPlainTextEdit { background:#ffffff; border:1px solid #bcbcbc; border-radius:2px; padding:5px; selection-background-color:#cce4f7; selection-color:#172f44; }
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QPlainTextEdit:focus { border-color:#3876a8; }
QLineEdit:disabled,QComboBox:disabled,QSpinBox:disabled { background:#eeeeee; color:#999999; }
QSpinBox QLineEdit { padding:0; border:0; background:transparent; }
QComboBox QAbstractItemView { background:white; color:#242424; selection-background-color:#dcebf8; selection-color:#172f44; }
QCheckBox { spacing:6px; padding:3px 0; }
QSplitter::handle { background:#d5d5d5; width:1px; }
QStatusBar { background:#eeeeee; border-top:1px solid #cccccc; }
QStatusBar::item { border:0; }
QToolTip { background:#ffffe6; color:#242424; padding:5px; border:1px solid #aaa; }
'''

class Worker(QThread):
    result=Signal(object,object)
    def __init__(self,fn):super().__init__();self.fn=fn
    def run(self):
        try:self.result.emit(self.fn(),None)
        except Exception as e:self.result.emit(None,e)

def label(text,kind=None):
    w=QLabel(text)
    if kind:w.setObjectName(kind)
    return w

def button(text,fn,kind=None):
    b=QPushButton(text);b.clicked.connect(fn)
    if kind:b.setObjectName(kind)
    return b

def table(headings):
    t=QTableWidget(0,len(headings));t.setHorizontalHeaderLabels(headings);t.verticalHeader().hide()
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);t.setAlternatingRowColors(True);t.setShowGrid(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);t.verticalHeader().setDefaultSectionSize(32)
    return t

class Studio(QMainWindow, ProcessFeatures, DiagnosticFeatures):
    def __init__(self):
        super().__init__();self.setWindowTitle('AppProxy Studio');self.resize(1180,760);self.setMinimumSize(1060,700)
        self.setWindowIcon(QIcon(str(ROOT/'assets'/'app.ico')));self.manager=CoreManager();self.state=load_state();self.worker=None;self.last_running=False;self.selected_id=None
        central=QWidget();self.setCentralWidget(central);layout=QVBoxLayout(central);layout.setContentsMargins(10,8,10,10);layout.setSpacing(8)
        toolbar=QFrame();toolbar.setObjectName('toolbar');header=QHBoxLayout(toolbar);header.setContentsMargins(0,0,0,8)
        self.start=button('启动引擎',self.toggle_engine);header.addWidget(self.start);header.addWidget(button('启动诊断',self.check_diagnostics))
        self.mode_label=label('','muted');header.addWidget(self.mode_label);header.addStretch()
        header.addWidget(label('AppProxy Studio 1.4','muted'));layout.addWidget(toolbar)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        self.init_process_features();self.build_apps();self.build_nodes();self.build_connections();self.build_diagnostics();self.build_settings();self.build_logs()
        self.status=label('引擎未启动','status');self.statusBar().addWidget(self.status)
        self.summary=label('','muted');self.statusBar().addPermanentWidget(self.summary)
        self.refresh();self.log('先导入节点，再添加软件并选择节点；配置好后启动引擎。')
        self.timer=QTimer(self);self.timer.timeout.connect(self.update_status);self.timer.start(1000)
    @property
    def busy(self):return self.worker is not None
    def page(self,name):
        w=QWidget();v=QVBoxLayout(w);v.setContentsMargins(10,10,10,10);v.setSpacing(8);self.tabs.addTab(w,name);return v
    def build_apps(self):
        v=self.page('应用通道');tools=QHBoxLayout()
        for text,fn,kind in [('添加软件…',self.add_file,None),('从运行进程选择',self.add_process,None),('切换代理开关',self.toggle_app,None),('关联辅助进程',self.manage_helpers,None)]:tools.addWidget(button(text,fn,kind))
        tools.addStretch();tools.addWidget(button('移除通道',self.remove_app));v.addLayout(tools)
        split=QSplitter();v.addWidget(split,1);self.apps=table(['应用','代理配置','出口节点','本地端口']);split.addWidget(self.apps)
        right=QWidget();right.setMinimumWidth(330);r=QVBoxLayout(right);r.setContentsMargins(14,2,0,0);r.addWidget(label('应用设置','section'))
        form=QFormLayout();form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows);form.setVerticalSpacing(8)
        self.name=QLineEdit();self.path=QLineEdit();self.port=QSpinBox();self.port.setRange(1024,65535);self.node=QComboBox()
        for title,w in [('应用名称',self.name),('程序完整路径（EXE）',self.path),('独立 HTTP / SOCKS5 端口',self.port),('出口节点',self.node)]:w.setMinimumHeight(30);form.addRow(title,w)
        r.addLayout(form);self.enabled=QCheckBox('为此软件开启代理');r.addWidget(self.enabled)
        r.addWidget(button('保存并应用',self.save_app,'accent'));row=QHBoxLayout();row.addWidget(button('启动软件',self.launch_app));row.addWidget(button('更换路径',self.repair_path));r.addLayout(row);r.addStretch()
        hint=label('TUN 模式按程序路径自动分流。\n端口模式需在软件中设置本地端口。\n开关或节点变更会重连受影响的通道。','muted');hint.setWordWrap(True);r.addWidget(hint);split.addWidget(right);split.setSizes([740,360])
        self.apps.itemSelectionChanged.connect(self.select_app)
        self.empty=label('尚未添加应用。点击“添加软件”选择需要分流的 EXE。','muted');v.addWidget(self.empty)
    def build_nodes(self):
        v=self.page('节点库');row=QHBoxLayout()
        for text,fn in [('粘贴 YAML / 链接',self.import_text),('导入文件',self.import_file),('订阅地址',self.import_url),('编辑节点',self.edit_node),('测试延迟',self.test_node),('删除节点',self.remove_node)]:row.addWidget(button(text,fn))
        row.addStretch();v.addLayout(row);self.nodes=table(['节点名称','协议','服务器','端口']);v.addWidget(self.nodes,1)
        hint=label('YAML 支持核心所支持的主流协议。常见分享链接可直接粘贴；复杂传输与插件请使用 Clash / Mihomo YAML。','muted');hint.setWordWrap(True);v.addWidget(hint)
    def build_settings(self):
        v=self.page('分流设置');self.tun=QCheckBox('启用 TUN 通用进程分流（需要管理员权限）');self.tun.setChecked(self.state['tun']);v.addWidget(self.tun)
        v.addWidget(label('开启：软件按 EXE 路径自动分流。关闭：仅提供独立端口，不自动接管软件连接。','muted'))
        v.addWidget(label('直连域名例外 · 每行一个，包含其子域名'))
        self.domains=QPlainTextEdit('\n'.join(self.state['direct_domains']));self.domains.setMaximumHeight(140);v.addWidget(self.domains)
        v.addWidget(label('例外域名优先直连，适用于内置浏览器访问同花顺等场景。','muted'))
        row=QHBoxLayout();row.addWidget(button('保存分流设置',self.save_settings,'accent'));row.addWidget(button('以管理员身份重启',self.elevate));row.addStretch();v.addLayout(row)
        text=label('• 未分配的软件默认直连，不修改 Windows 系统代理。\n• ChatGPT/Codex 自动关联 OpenAI 后台进程；其他软件可通过“关联辅助进程”纳入同一通道。\n• TUN 模式不宜与其他 VPN / TUN 同时开启。\n• 软件已有显式代理时，先清除它的旧设置，再使用 TUN 分流。\n• 退出工具会停止本工具的核心；现有 GPT 专用代理不受管理。','muted');text.setWordWrap(True);v.addWidget(text)
        v.addStretch();v.addWidget(label('本地数据：'+str(DATA),'muted'))
    def build_logs(self):
        v=self.page('运行记录');self.logs=QPlainTextEdit();self.logs.setReadOnly(True);v.addWidget(self.logs)
    def log(self,text):self.logs.appendPlainText(time.strftime('%H:%M:%S')+'  '+str(text))
    def error(self,e):self.log(str(e));QMessageBox.warning(self,'操作未完成',str(e))
    def run(self,fn,done=None):
        if self.busy:return
        self.start.setEnabled(False);self.tabs.setEnabled(False);self.status.setText('正在处理…')
        worker=Worker(fn);self.worker=worker
        outcome=[]
        worker.result.connect(lambda value,error:outcome.append((value,error)))
        def finished():
            self.worker=None;self.start.setEnabled(True);self.tabs.setEnabled(True)
            value,error=outcome[0] if outcome else (None,RuntimeError('后台任务未返回结果'))
            if error:self.error(error)
            elif done:done(value)
            worker.deleteLater();self.update_status()
        worker.finished.connect(finished);worker.start()
    def update_status(self):
        if self.busy:return
        running=self.manager.running
        if self.last_running and not running:self.log('核心已退出，当前不再提供代理。请检查配置或重新启动。')
        self.last_running=running;self.start.setText('停止引擎' if running else '启动引擎')
        self.status.setText(('引擎运行中 · '+('TUN 分流' if self.manager.state['tun'] else '独立端口') if running else '引擎未启动'))
    def refresh(self):
        selected=self.selected_id;self.apps.blockSignals(True);self.apps.setRowCount(len(self.state['apps']))
        for i,a in enumerate(self.state['apps']):
            for j,value in enumerate((a['name']+(' · +'+str(len(related_paths(a))) if related_paths(a) else ''),'路径失效' if not Path(a['path']).is_file() else ('已设代理' if a['enabled'] else '已设直连'),a.get('node') or '未选择',a['port'])):
                item=QTableWidgetItem(str(value));item.setToolTip(a['path'] if j==0 else str(value));self.apps.setItem(i,j,item)
            self.apps.item(i,1).setForeground(QColor('#21623f' if a['enabled'] else '#666666'))
        self.apps.blockSignals(False);self.node.clear();self.node.addItem('请选择节点','');
        for n in self.state['nodes']:self.node.addItem(n['name'],n['name'])
        self.nodes.setRowCount(len(self.state['nodes']))
        for i,n in enumerate(self.state['nodes']):
            for j,key in enumerate(('name','type','server','port')):self.nodes.setItem(i,j,QTableWidgetItem(str(n[key])))
        self.summary.setText(f"{len(self.state['apps'])} 个应用   |   {sum(a['enabled'] for a in self.state['apps'])} 个已设代理   |   {len(self.state['nodes'])} 个节点");self.mode_label.setText('TUN 进程分流' if self.state['tun'] else '独立端口模式')
        self.empty.setVisible(not self.state['apps'])
        idx=next((i for i,a in enumerate(self.state['apps']) if a['id']==selected),0)
        if self.state['apps']:self.apps.selectRow(idx);self.select_app()
        else:self.selected_id=None;self.name.clear();self.path.clear();self.enabled.setChecked(False)
    def current(self):
        i=self.apps.currentRow();return self.state['apps'][i] if 0<=i<len(self.state['apps']) else None
    def select_app(self):
        a=self.current()
        if not a:return
        self.selected_id=a['id'];self.name.setText(a['name']);self.path.setText(a['path']);self.port.setValue(a['port']);self.node.setCurrentIndex(max(0,self.node.findData(a.get('node',''))));self.enabled.setChecked(a['enabled']);self.enabled.setToolTip('ChatGPT/Codex 桌面端会自动关联 OpenAI Codex bin 目录下的后台进程，共享本通道开关和节点。')
    def commit(self,new,description):
        def work():self.manager.apply(new);save_state(new)
        def done(_):self.state=new;self.refresh();self.log(description)
        self.run(work,done)
    def add_path(self,path):
        if any(os.path.normcase(a['path'])==os.path.normcase(path) for a in self.state['apps']):self.error('该程序已添加');return
        used={a['port'] for a in self.state['apps']};port=18801
        while port in used:port+=1
        a={'id':secrets.token_hex(6),'name':Path(path).stem,'path':str(Path(path).resolve()),'port':port,'enabled':False,'node':self.state['nodes'][0]['name'] if self.state['nodes'] else ''}
        new=copy.deepcopy(self.state);new['apps'].append(a);self.selected_id=a['id'];self.commit(new,'已添加软件，默认直连。选择节点后可开启代理。')
    def add_file(self):
        path,_=QFileDialog.getOpenFileName(self,'选择软件','','Windows 程序 (*.exe)')
        if path:self.add_path(path)
    def add_process(self):
        d=QDialog(self);d.setWindowTitle('选择正在运行的软件');d.resize(900,540);v=QVBoxLayout(d);t=table(['进程','完整路径']);v.addWidget(t)
        paths=set()
        for p in psutil.process_iter(['exe']):
            try:
                if p.info['exe'] and p.info['exe'].lower().endswith('.exe'):paths.add(p.info['exe'])
            except (psutil.AccessDenied,psutil.NoSuchProcess):pass
        paths=sorted(paths,key=lambda p:Path(p).name.lower());t.setRowCount(len(paths))
        for i,p in enumerate(paths):t.setItem(i,0,QTableWidgetItem(Path(p).name));t.setItem(i,1,QTableWidgetItem(p))
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);b.button(QDialogButtonBox.StandardButton.Ok).setText('添加');b.button(QDialogButtonBox.StandardButton.Cancel).setText('取消');b.accepted.connect(d.accept);b.rejected.connect(d.reject);v.addWidget(b)
        if d.exec() and t.currentRow()>=0:self.add_path(paths[t.currentRow()])
    def save_app(self):
        a=self.current()
        if not a:return
        if not Path(self.path.text().strip()).is_file():self.error('程序路径不存在');return
        if not self.name.text().strip():self.error('请输入应用名称');return
        new=copy.deepcopy(self.state);x=next(x for x in new['apps'] if x['id']==a['id']);x.update(name=self.name.text().strip(),path=self.path.text().strip(),port=self.port.value(),node=self.node.currentData(),enabled=self.enabled.isChecked())
        self.commit(new,'通道配置已保存并应用。')
    def toggle_app(self):
        a=self.current()
        if a:
            new=copy.deepcopy(self.state);x=next(x for x in new['apps'] if x['id']==a['id']);x['enabled']=not x['enabled'];self.commit(new,'已切换 '+a['name']+' 的代理开关。')
    def remove_app(self):
        a=self.current()
        if a:
            new=copy.deepcopy(self.state);new['apps']=[x for x in new['apps'] if x['id']!=a['id']];self.commit(new,'应用通道已移除，后续连接默认直连。')
    def launch_app(self):
        a=self.current()
        if not a:return
        if a['enabled'] and not self.manager.running:self.error('请先启动引擎');return
        if a['enabled'] and not self.state['tun']:QMessageBox.information(self,'独立端口模式','请在该软件内设置代理 127.0.0.1:'+str(a['port'])+'。仅启动软件不会强制它使用代理。')
        try:subprocess.Popen([a['path']],cwd=str(Path(a['path']).parent))
        except Exception as e:self.error(e)
    def toggle_engine(self):
        if self.manager.running:self.run(self.manager.stop,lambda _:self.log('引擎已停止；本工具端口与 TUN 已释放。'))
        else:self.check_diagnostics(start_after=True)
    def editor(self,title,initial,callback):
        d=QDialog(self);d.setWindowTitle(title);d.resize(800,580);v=QVBoxLayout(d)
        v.addWidget(label('节点仅保存于项目 data 文件夹；编辑内容可能包含密码。','muted'));edit=QPlainTextEdit(initial);v.addWidget(edit)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.button(QDialogButtonBox.StandardButton.Save).setText('保存');b.button(QDialogButtonBox.StandardButton.Cancel).setText('取消');v.addWidget(b)
        def accept():
            try:callback(edit.toPlainText());d.accept()
            except Exception as e:QMessageBox.warning(d,'输入无效',str(e))
        b.accepted.connect(accept);b.rejected.connect(d.reject);d.exec()
    def accept_nodes(self,nodes):
        new=copy.deepcopy(self.state);new['nodes']=merge_nodes(new['nodes'],nodes);self.commit(new,f'导入 / 更新了 {len(nodes)} 个节点。')
    def import_text(self):self.editor('粘贴 YAML 或分享链接','',lambda text:self.accept_nodes(import_nodes(text)))
    def import_file(self):
        p,_=QFileDialog.getOpenFileName(self,'导入节点','','节点文件 (*.yaml *.yml *.json *.txt);;所有文件 (*)')
        if p:
            try:self.accept_nodes(import_nodes(Path(p).read_text(encoding='utf-8-sig')))
            except Exception as e:self.error(e)
    def import_url(self):
        url,ok=QInputDialog.getText(self,'导入订阅','HTTP / HTTPS 地址（不保存订阅地址）')
        if not ok or not url.strip():return
        def work():
            try:return fetch_subscription(url.strip())
            except Exception:raise ValueError('订阅下载或解析失败。确认地址有效，或下载 YAML 后导入文件。')
        self.run(work,self.accept_nodes)
    def chosen_node(self):
        i=self.nodes.currentRow();return self.state['nodes'][i] if 0<=i<len(self.state['nodes']) else None
    def edit_node(self):
        node=self.chosen_node()
        if not node:return
        def accept(text):
            nodes=import_nodes(text)
            if len(nodes)!=1:raise ValueError('编辑时只能保留一个节点')
            new=copy.deepcopy(self.state)
            if nodes[0]['name']!=node['name'] and any(n['name']==nodes[0]['name'] for n in new['nodes']):raise ValueError('该节点名称已存在')
            new['nodes']=[nodes[0] if n['name']==node['name'] else n for n in new['nodes']]
            for a in new['apps']:
                if a['node']==node['name']:a['node']=nodes[0]['name']
            self.commit(new,'节点已更新。')
        self.editor('编辑节点',yaml.safe_dump(node,allow_unicode=True,sort_keys=False),accept)
    def remove_node(self):
        n=self.chosen_node()
        if not n:return
        if any(a['node']==n['name'] for a in self.state['apps']):self.error('该节点被应用引用，请先选择其他节点');return
        new=copy.deepcopy(self.state);new['nodes']=[x for x in new['nodes'] if x['name']!=n['name']];self.commit(new,'节点已删除。')
    def test_node(self):
        n=self.chosen_node()
        if not n:return
        if not self.manager.running:self.error('请先启动引擎，再测试节点延迟');return
        self.run(lambda:self.manager.delay(n['name']),lambda ms:self.log(n['name']+' 连通延迟：'+str(ms)+' ms'))
    def save_settings(self):
        new=copy.deepcopy(self.state);new['tun']=self.tun.isChecked();new['direct_domains']=[d.strip() for d in self.domains.toPlainText().splitlines() if d.strip()];self.commit(new,'分流设置已保存。')
    def elevate(self):
        if ctypes.windll.shell32.IsUserAnAdmin():QMessageBox.information(self,'权限','当前已经具有管理员权限');return
        if self.manager.running:self.error('请先停止引擎，再切换权限');return
        args=['--wait-instance'] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve()),'--wait-instance']
        code=ctypes.windll.shell32.ShellExecuteW(None,'runas',sys.executable,subprocess.list2cmdline(args),str(ROOT),1)
        if code>32:self.close()
        else:self.error('管理员重启已取消或失败')
    def closeEvent(self,event):
        if self.net_worker is not None:event.ignore();return
        if self.busy:event.ignore();return
        if self.manager.running:
            if QMessageBox.question(self,'退出工具','退出会停止代理引擎。是否继续？')!=QMessageBox.StandardButton.Yes:event.ignore();return
        self.manager.stop();event.accept()

def main():
    DATA.mkdir(parents=True,exist_ok=True);ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('AppProxyStudio.Desktop');app=QApplication(sys.argv);app.setWindowIcon(QIcon(str(ROOT/'assets'/'app.ico')));app.setStyle('Fusion');app.setStyleSheet(STYLE)
    lock=socket.socket();lock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    for attempt in range(30 if '--wait-instance' in sys.argv else 1):
        try:lock.bind(('127.0.0.1',19790));break
        except OSError:
            if '--wait-instance' in sys.argv and attempt<29:time.sleep(.2);continue
            QMessageBox.information(None,'AppProxy Studio','工具已经在运行，或管理端口 19790 被占用。');return
    window=None
    try:window=Studio();window.show();app.exec()
    except Exception as e:QMessageBox.critical(None,'启动失败',str(e))
    finally:
        if window:window.manager.stop()
        lock.close()
if __name__=='__main__':main()
