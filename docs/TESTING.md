# 验证范围

Windows x64 / Python 3.10。运行 setup.ps1 后：

```powershell
python tests/test_engine.py
python tests/test_codex.py
python tests/test_processes.py
python tests/test_diagnostics.py
```

共 38 项：导入/规则校验、双本地 HTTP 节点并发、切换节点、关闭单个通道、直连例外、失败回滚、端口占用保护、Codex 规则、辅助进程归属与连接状态。测试只使用虚构配置和本地模拟节点，不读取 data/settings.json。

TUN 手动实测：先关闭其他工具的 TUN，在管理员 PowerShell 执行 `tests/run-tun-admin.ps1`。该测试会创建测试虚拟网卡并改变测试期间路由，结束后回收核心；不会在 CI 自动运行。通过两个 Windows curl.exe 路径检查不同出口、热切换与关闭单条规则。

历史本机 TUN 测试通过不代表任意软件/协议都通过。外部商业节点、多种真实协议握手、DNS 隐私、IPv6、QUIC、短命 UDP、反作弊/系统服务进程需要额外实测。UI 已手动检查应用通道、辅助进程和联网进程页面。

1.4 新增 8 项诊断回归测试，包括真实 TCP/UDP 端口占用、权限模式差异、运行中自有端口排除、TUN 名称识别、配置/核心错误、路径提示、代理凭据不显示与检查失败不冒充通过。
