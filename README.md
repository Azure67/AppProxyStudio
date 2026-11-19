# AppProxy Studio

Windows 桌面应用代理管理器。给不同软件指定独立节点和本地 HTTP/SOCKS5 端口，单独开启或关闭代理，并查看实际联网进程。

Python / PySide6 · Mihomo · GPL-3.0-or-later

## 功能

- 按 EXE 完整路径分流，多个软件可同时使用不同节点。
- TUN 模式透明分流；独立端口模式供支持显式代理的软件使用。
- 主程序与手动勾选的辅助进程共用节点和开关；已知 Codex 后台按限定安装路径关联。
- 当前连接、目标、所属通道、实际走向和匹配规则；搜索及从连接关联辅助进程。
- 启动前自动诊断权限、TCP/UDP 端口占用、核心/路径、疑似 TUN 冲突及系统/环境代理；也可点击“启动诊断”单独检查。
- 导入节点 YAML、常见分享链接与订阅；手动选节点、延迟测试。
- 配置先校验后应用，支持运行中修改节点/开关，失败时保留原通道。
- 紧凑浅色桌面界面，应用设置与连接诊断分开显示。

## 从源码运行（Windows x64）

需要 Python 3.10 x64 与 PowerShell。打开项目目录后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\run-source.ps1
```

setup.ps1 将 Python 依赖放入 vendor/，从 MetaCubeX 官方 Release 下载固定的 Mihomo v1.19.1 compatible 核心并验证 SHA-256。所有下载、缓存与配置位于项目内，不安装系统服务。可通过 `-Python C:\Path\python.exe` 指定安装依赖使用的 Python；启动与打包时应使用同一 Python 环境。

本仓库提供源码，不包含个人节点、订阅、运行日志、预编译 EXE 或第三方二进制。当前固定的是已测核心基线，不宣称为最新版；升级前应运行兼容性测试。

## 使用

1. 打开“节点库”导入节点。
2. 在“应用通道”添加 EXE，或从运行进程选择。
3. 选择节点，设置端口和代理开关，点击“保存并应用”。
4. TUN 分流需要管理员权限；可在“分流设置”选择“以管理员身份重启”，然后启动引擎。先关闭其他 VPN/代理工具的 TUN。
5. 若软件通过辅助程序联网，选中主程序→“关联辅助进程”，勾选实际联网 EXE。
6. 在“联网进程”核对实际路由。引擎未运行时只显示系统连接，标记“未核实”，不会推断其他代理工具的走向。

关闭应用通道代理后，该应用的新连接走直连；修改节点/开关会关闭受影响通道的旧连接以重新建立连接。未分配的软件默认直连。

独立端口模式不自动注入软件代理，需要在目标软件中手动设置对应的 127.0.0.1 端口。本工具不修改 Windows 系统代理。若目标软件原先配置了其他显式代理，请先自行清理旧设置。

## 节点格式

支持 Clash/Mihomo proxies 列表、单节点 YAML/JSON、Base64 分享链接列表，以及 SS、VMess、VLESS、Trojan、Hysteria2、TUIC、HTTP/HTTPS、SOCKS5 常见链接。

YAML 协议能力以随附核心为准。复杂传输/插件请使用 YAML；不导入订阅中的全局规则。暂不支持仅引用 proxy-providers、节点链式 dialer-proxy、sing-box 原生 JSON。导入数量不代表连通性检查通过。

默认直连域名例外为 10jqka.com.cn 和 hexin.cn，可在设置中修改。

## 已知边界

- 同一 EXE 的实例共享通道，不按窗口/PID/浏览器标签页隔离。
- 路径变化或进程无法识别可能导致规则不匹配。升级后可使用“更换路径”。
- 不是防泄漏、访问控制或断网保护工具。DNS、UDP/QUIC、IPv6 需要单独验证，不能保证全部跟随每个应用的节点。
- 退出窗口会停止核心，没有后台服务、托盘常驻或开机自启功能。
- 软件内置显式代理、其他 TUN/VPN、网络共享可能影响路由。
- 当前面向 Windows x64；程序未做代码签名。
- 配置凭据以明文保存在 data/，不要公开该目录或原始日志。见 [SECURITY.md](SECURITY.md)。

## 测试与打包

```powershell
python tests/test_engine.py
python tests/test_codex.py
python tests/test_processes.py
python tests/test_diagnostics.py
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

构建后运行根目录“启动应用.cmd”。需要保留 app/、core/ 和 assets/ 的目录结构，不能只移动 EXE。构建依赖安装见 setup.ps1；正常测试不需要管理员权限，手动 TUN 测试例外。

测试范围和限制：[docs/TESTING.md](docs/TESTING.md)。项目对比与后续优先级：[docs/RELATED_PROJECTS.md](docs/RELATED_PROJECTS.md)。

## 项目结构

- src/app.py：桌面主界面
- src/engine.py：节点导入、规则与核心生命周期
- src/processes.py、src/process_ui.py：进程关联与连接诊断
- assets/：原创 SVG / PNG / ICO 图标
- tests/：模拟节点集成与规则回归测试
- setup.ps1、build.ps1：依赖安装与打包

公开仓库不包含 data/、build/、vendor/、app/ 与本机快捷方式。请从干净检出构建分发包，不要压缩正在使用的安装目录。

## 参考与许可证

界面布局参考 [qBittorrent](https://www.qbittorrent.org/screenshots)；按应用分流与工程取舍参考 [ProxiFyre](https://github.com/wiresock/proxifyre)、[Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)、[v2rayN](https://github.com/2dust/v2rayN)。未复制这些项目的代码与图标。

本项目源码使用 [GPL-3.0-or-later](LICENSE)。第三方组件许可证和来源见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 1.4 改进

启动诊断直接接入启动流程，缺少权限/核心、配置错误、端口冲突会阻止启动并显示处理建议；疑似 TUN 或显式代理冲突允许检查后继续。检查只读，不自动更改其他软件或网卡。列表使用“已设代理/已设直连”，表示配置，不宣称连通性。诊断不会发起节点请求；其他进程的环境、启动参数和内置代理设置仍需自行检查。
