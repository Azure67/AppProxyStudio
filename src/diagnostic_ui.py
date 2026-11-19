"""Startup diagnostics UI, shared by manual checks and engine startup."""
import copy
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout,QTableWidgetItem,QMessageBox,QHeaderView,QPlainTextEdit
from diagnostics import collect_diagnostics

class DiagnosticFeatures:
    def build_diagnostics(self):
        from app import button,label,table
        v=self.page('启动诊断');self.diagnostic_page=self.tabs.widget(self.tabs.count()-1)
        bar=QHBoxLayout();bar.addWidget(button('重新检查',self.check_diagnostics));bar.addStretch();v.addLayout(bar)
        self.diagnostic_status=label('检查端口、权限、路径和可能冲突的代理设置。','muted');self.diagnostic_status.setWordWrap(True);v.addWidget(self.diagnostic_status)
        self.diagnostic_table=table(['结果','检查项','发现','处理建议']);self.diagnostic_table.setWordWrap(True)
        self.diagnostic_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.diagnostic_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(self.diagnostic_table,1)
        self.diagnostic_details=QPlainTextEdit();self.diagnostic_details.setReadOnly(True);self.diagnostic_details.setMaximumHeight(110);self.diagnostic_details.setPlaceholderText('选中一项，查看完整发现和处理建议。');v.addWidget(self.diagnostic_details)
        self.diagnostic_table.itemSelectionChanged.connect(self.show_diagnostic_detail)
    def show_diagnostic_detail(self):
        row=self.diagnostic_table.currentRow()
        if row<0:self.diagnostic_details.clear();return
        items=[self.diagnostic_table.item(row,col) for col in (1,2,3)]
        if all(items):self.diagnostic_details.setPlainText(items[0].text()+'\n\n'+items[1].text()+'\n\n处理建议：'+(items[2].text() or '无需处理。'))
    def check_diagnostics(self,start_after=False):
        from engine import ROOT
        state=copy.deepcopy(self.state);owned=set()
        if self.manager.running:
            owned.add((int(self.manager.state['api_port']),'TCP'))
            owned.update((int(a['port']),p) for a in self.manager.state['apps'] for p in ('TCP','UDP'))
        self.tabs.setCurrentWidget(self.diagnostic_page)
        self.run(lambda:collect_diagnostics(state,ROOT,owned),lambda rows:self.show_diagnostics(rows,state,start_after))
    def show_diagnostics(self,rows,state,start_after):
        labels={'error':'需修复','warning':'注意','ok':'通过','info':'说明'};colors={'error':'#a32929','warning':'#72551c','ok':'#21623f','info':'#555555'}
        self.diagnostic_table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,key in enumerate(('level','check','detail','action')):
                text=labels[row[key]] if key=='level' else row[key];item=QTableWidgetItem(text);item.setToolTip(text);self.diagnostic_table.setItem(i,j,item)
            self.diagnostic_table.item(i,0).setForeground(QColor(colors[row['level']]))
        self.diagnostic_table.resizeRowsToContents()
        if rows:self.diagnostic_table.selectRow(next((i for i,r in enumerate(rows) if r['level']=='error'),0))
        errors=sum(r['level']=='error' for r in rows);warnings=sum(r['level']=='warning' for r in rows)
        self.diagnostic_status.setText(f'检查完成：{errors} 项需修复，{warnings} 项需留意。检查结果不代表节点可用或连接已走代理。')
        if not start_after:return
        if errors:self.log('启动诊断发现阻塞项，尚未启动引擎。');return
        if warnings:
            msg=QMessageBox(self);msg.setWindowTitle('启动前发现需留意的项目');msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText('发现以下情况，可能影响应用分流：\n\n'+'\n'.join(r['check']+'：'+r['detail'] for r in rows if r['level']=='warning'))
            proceed=msg.addButton('仍然启动',QMessageBox.ButtonRole.AcceptRole);back=msg.addButton('返回检查',QMessageBox.ButtonRole.RejectRole);msg.setDefaultButton(back);msg.exec()
            if msg.clickedButton()!=proceed:return
        self.run(lambda:self.manager.start(state),lambda _:self.log('引擎已就绪；连接是否经过所选节点，请在联网进程中核对。'))
