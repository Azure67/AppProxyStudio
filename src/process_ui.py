"""Connection inspection and explicit helper-process management UI."""
import copy,ntpath,os
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,
 QCheckBox,QDialogButtonBox,QTableWidgetItem,QFileDialog,QInputDialog,QMessageBox,QApplication)
from processes import related_paths,pathkey,discover_related,core_connections,system_connections,configured_owner

class ProcessFeatures:
    def init_process_features(self):
        self.net_worker=None;self.connection_rows=[];self.visible_connections=[]
        self.net_timer=QTimer(self);self.net_timer.timeout.connect(self.auto_connections);self.net_timer.start(3000)
    def build_connections(self):
        from app import button,label,table
        v=self.page('联网进程');self.connection_page=self.tabs.widget(self.tabs.count()-1)
        bar=QHBoxLayout();self.conn_filter=QLineEdit();self.conn_filter.setPlaceholderText('搜索进程、目标、路径或通道');self.conn_filter.textChanged.connect(self.render_connections);bar.addWidget(self.conn_filter,1)
        self.only_direct=QCheckBox('只看未分配 / 直连');self.only_direct.toggled.connect(self.render_connections);bar.addWidget(self.only_direct)
        self.auto_conn=QCheckBox('自动刷新');self.auto_conn.setChecked(True);bar.addWidget(self.auto_conn)
        bar.addWidget(button('刷新',self.refresh_connections));bar.addWidget(button('关联到通道',self.associate_connection,'accent'));v.addLayout(bar)
        self.connection_table=table(['进程','PID','目标地址','所属通道','实际走向','匹配规则']);v.addWidget(self.connection_table,1)
        self.connection_table.itemSelectionChanged.connect(self.show_connection_path)
        self.connection_path=label('选中连接可查看完整程序路径。','muted');self.connection_path.setWordWrap(True);v.addWidget(self.connection_path)
        self.connection_status=label('引擎运行时显示核心确认的当前连接；未运行时只观察系统连接，不推测是否经过其他代理。','muted');self.connection_status.setWordWrap(True);v.addWidget(self.connection_status)
        self.tabs.currentChanged.connect(lambda _:self.refresh_connections() if self.tabs.currentWidget()==self.connection_page else None)
    def auto_connections(self):
        if self.auto_conn.isChecked() and self.tabs.currentWidget()==self.connection_page and not QApplication.activeModalWidget():self.refresh_connections()
    def refresh_connections(self):
        if self.busy or self.net_worker is not None:return
        from app import Worker
        state=copy.deepcopy(self.state);running=self.manager.running;self.connection_status.setText('正在读取当前连接…')
        def fetch():
            if running:return core_connections(self.manager.api('GET','/connections') or {},state['apps'])
            return system_connections(state['apps'])
        worker=Worker(fetch);self.net_worker=worker;outcome=[];worker.result.connect(lambda value,error:outcome.append((value,error)))
        def finish():
            self.net_worker=None
            value,error=outcome[0] if outcome else (None,RuntimeError('连接查询未返回'))
            if error:self.connection_status.setText('连接读取失败：'+str(error))
            else:
                self.connection_rows=value;self.render_connections();self.connection_status.setText(('核心实际连接' if running else '系统连接观察 · 未核实代理走向')+f' · {len(value)} 条；仅显示当前连接，短暂连接可能已结束。')
            worker.deleteLater()
        worker.finished.connect(finish);worker.start()
    def render_connections(self,*args):
        query=self.conn_filter.text().strip().casefold();current=self.connection_table.currentRow();selected=self.visible_connections[current]['id'] if 0<=current<len(self.visible_connections) else None
        rows=[]
        for row in self.connection_rows:
            if query and query not in ' '.join(str(v) for v in row.values()).casefold():continue
            if self.only_direct.isChecked() and row['channel']!='未分配' and row['route']!='直连':continue
            rows.append(row)
        self.visible_connections=rows;self.connection_table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,key in enumerate(('process','pid','target','channel','route','rule')):
                item=QTableWidgetItem(str(row.get(key,'')));item.setToolTip(row.get('path','') if j==0 else str(row.get(key,'')));self.connection_table.setItem(i,j,item)
            self.connection_table.item(i,4).setForeground(QColor('#21623f' if row['route'].startswith('代理') else '#72551c'))
            if row['id']==selected:self.connection_table.selectRow(i)
        self.show_connection_path()
    def show_connection_path(self):
        i=self.connection_table.currentRow();self.connection_path.setText(self.visible_connections[i]['path'] or '系统未提供进程路径；管理员权限可能改善识别。' if 0<=i<len(self.visible_connections) else '选中连接可查看完整程序路径。')
    def associate_connection(self):
        i=self.connection_table.currentRow()
        if not 0<=i<len(self.visible_connections):return
        row=dict(self.visible_connections[i]);path=row['path']
        if not path or not path.lower().endswith('.exe'):self.error('此连接没有可用 EXE 路径，无法关联。请以管理员身份运行后刷新。');return
        if not self.state['apps']:self.error('请先添加一个应用通道');return
        choices=[a['name']+' · '+str(a['port']) for a in self.state['apps']]
        selected,ok=QInputDialog.getItem(self,'关联联网进程','选择 '+ntpath.basename(path)+' 要使用的通道：',choices,0,False)
        if not ok:return
        target=self.state['apps'][choices.index(selected)];owner=configured_owner(path,self.state['apps'])
        if owner and owner['id']!=target['id']:self.error('此进程已属于 '+owner['name']+'，请先解除原通道关联或移除独立条目。');return
        if owner and owner['id']==target['id']:QMessageBox.information(self,'已关联','此进程已属于所选通道。若实际走向是直连，请查看匹配规则、域名例外或通道开关。');return
        new=copy.deepcopy(self.state);a=next(a for a in new['apps'] if a['id']==target['id']);a['related_paths']=related_paths(a)+[path]
        self.commit(new,'已将 '+ntpath.basename(path)+' 关联到 '+target['name']+'。')
    def manage_helpers(self):
        a=self.current()
        if not a:return
        app=copy.deepcopy(a);self.run(lambda:discover_related(app),lambda candidates:self.helper_dialog(app,candidates))
    def helper_dialog(self,app,candidates):
        from app import table,button,label
        d=QDialog(self);d.setWindowTitle('关联辅助进程 · '+app['name']);d.resize(1040,600);v=QVBoxLayout(d)
        hint=label('勾选后，辅助进程与此应用共享节点和代理开关。候选不会自动选中；取消勾选会解除手动关联。','muted');hint.setWordWrap(True);v.addWidget(hint)
        t=table(['关联','程序','完整路径','识别依据']);t.setColumnWidth(0,65);v.addWidget(t,1)
        saved={pathkey(p) for p in related_paths(app)};items=list(candidates)
        def populate():
            t.setRowCount(len(items))
            for i,item in enumerate(items):
                path=item['path'];check=QTableWidgetItem();check.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable);check.setCheckState(Qt.CheckState.Checked if pathkey(path) in saved else Qt.CheckState.Unchecked)
                if item.get('automatic'):check.setCheckState(Qt.CheckState.Checked);check.setFlags(Qt.ItemFlag.NoItemFlags)
                t.setItem(i,0,check)
                for j,val in enumerate((ntpath.basename(path),path,item['reason']),1):cell=QTableWidgetItem(val);cell.setToolTip(val);t.setItem(i,j,cell)
        def add():
            for i,item in enumerate(items):
                if t.item(i,0).checkState()==Qt.CheckState.Checked:saved.add(pathkey(item['path']))
                else:saved.discard(pathkey(item['path']))
            paths,_=QFileDialog.getOpenFileNames(d,'选择辅助程序','','Windows 程序 (*.exe)')
            for path in paths:
                path=str(Path(path).resolve());key=pathkey(path)
                if key!=pathkey(app['path']) and not any(pathkey(x['path'])==key for x in items):items.append({'path':path,'reason':'手动选择'})
                saved.add(key)
            populate()
        row=QHBoxLayout();row.addWidget(button('手动选择 EXE',add));row.addStretch();v.addLayout(row)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);box.button(QDialogButtonBox.StandardButton.Save).setText('保存关联');box.button(QDialogButtonBox.StandardButton.Cancel).setText('取消');v.addWidget(box)
        def save():
            paths=[item['path'] for i,item in enumerate(items) if not item.get('automatic') and t.item(i,0).checkState()==Qt.CheckState.Checked]
            new=copy.deepcopy(self.state);a=next(a for a in new['apps'] if a['id']==app['id']);a['related_paths']=paths
            from processes import validate_associations
            try:validate_associations(new['apps'])
            except Exception as e:QMessageBox.warning(d,'关联冲突',str(e));return
            d.accept();self.commit(new,f'已保存 {len(paths)} 个手动辅助进程关联。')
        box.accepted.connect(save);box.rejected.connect(d.reject);populate();d.exec()
    def repair_path(self):
        app=self.current()
        if not app:return
        path,_=QFileDialog.getOpenFileName(self,'更换主程序路径',str(Path(app['path']).parent),'Windows 程序 (*.exe)')
        if path:self.path.setText(str(Path(path).resolve()));self.save_app()
