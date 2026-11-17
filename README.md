# Claude 思考翻译

用本机离线模型把 Claude Code CLI 和 Claude Desktop Gateway 收到的英文思考片段译成简体中文。安装在当前用户目录，保留 CC Switch 供应商切换、工具回传、官方安装包和更新。模型调用仍由你自己的供应商处理和计费。

## 让 Codex 或 Claude Code 安装

在要安装的电脑上打开 **本地** Codex 或 Claude Code，把这句话发给它即可。

> 从 https://github.com/fanyb/claude-thinking-translation 帮我安装 Claude 思考翻译。按 AGENTS.md 自动识别系统，使用默认离线引擎，装好后打开图形面板。保留我的 CC Switch 供应商、普通 `claude` 和官方更新。

若希望顺便开启，可以在这句话后加「同时开启 CLI 翻译」或「同时开启 Desktop 翻译」。安装过程不需要把供应商密钥发给助手。

## 图形面板

安装结束会自动打开 **Claude 思考翻译**。两张卡片分别控制 Claude Desktop 和 Claude Code CLI，各自可以点「开启翻译」「恢复英文」「恢复直连」。后续打开方式如下。

- **macOS 系统离线版**从 Finder 的 `~/Applications` 打开「Claude 思考翻译.app」。使用 Argos 的 Mac 可打开同目录的「Claude 思考翻译」网页快捷方式。
- **Windows**在开始菜单搜索「Claude Thinking Translation」。也可先[下载 ZIP](https://github.com/fanyb/claude-thinking-translation/archive/refs/heads/main.zip)，解压后双击 `install-windows.cmd`。若尚未安装 Python，安装器会打开 Python 官方下载页，装好后再双击安装器。
- **Linux 桌面**在应用菜单搜索「Claude 思考翻译」。Windows 和 Linux 的面板用默认浏览器显示，页面和翻译服务都在本机。

需要手动重新打开时，可在仓库目录运行 `python3 install.py panel`，Windows 用 `py -3 install.py panel`。WSL 或没有桌面会话的机器可继续用下方命令操作。安装时如需跳过打开窗口，使用 `install --no-open`。

## 支持范围

| 环境 | 默认引擎 | 使用入口 |
| --- | --- | --- |
| macOS 26+，Apple 芯片 | macOS 系统离线翻译 | Claude Code CLI、CC Switch Desktop Gateway、macOS 控制面板 |
| Windows x64 | Argos 离线 | 本地图形面板、Claude Code CLI、CC Switch Desktop Gateway |
| Linux x86-64 / ARM64 | Argos 离线 | 本地图形面板、Claude Code CLI、装有 Claude Desktop 且 CC Switch 已配置 Gateway 时可启用桌面翻译 |
| WSL | Argos 离线 | 在 WSL 内安装并使用 Linux CLI，使用 WSL 自己的 Claude 配置和可达的供应商 |

macOS 也可用 `install --engine argos`。Argos 需要 Python 3.10+（推荐 3.12）、可用的原生依赖和首次联网下载约 67 MB 模型，之后翻译在本机完成。Windows 若提示缺少 CTranslate2 的 DLL，可按上游文档安装 Microsoft Visual C++ 运行库。[CTranslate2 环境要求](https://opennmt.net/CTranslate2/installation.html)

桌面端识别 **DeepSeek V4.1 Flash** 思考流。CLI 还支持 **GLM 5.3 / 5.3 Flash** 和沿用的 **Ark Code Latest** 路由。其他模型照常转发。需要使用已经通过 CC Switch 配好并且能发送请求的第三方供应商。模型未返回可见思考时没有文本可译。

## 手动安装和使用

克隆本仓库，在仓库目录运行下列命令。Windows 用 `py -3` 或已安装的 `python` 替换 `python3`。

```console
python3 install.py install
python3 install.py check
python3 install.py status
```

- **macOS 系统离线引擎**先通过 `xcode-select --install` 安装 Apple 命令行工具，并在「系统设置 → 通用 → 语言与地区 → 翻译语言」下载英语（美国）和简体中文。安装后可打开 `~/Applications` 中的「Claude 思考翻译.app」操作。[Apple 离线翻译说明](https://support.apple.com/zh-cn/guide/mac-help/mchldd8b3c15/mac)
- **CLI**运行 `python3 install.py cli-on`，再用 `python3 install.py claude` 启动会话。可继续传原来的 Claude Code 参数。macOS 系统离线版也可运行 `~/.local/bin/claude-zh`。折叠思考区可按 **Ctrl+O** 展开。切换供应商后重开会话。
- **桌面**先在 CC Switch 的 Claude Desktop 页为供应商启用「需要模型映射」，确认能发消息。再运行 `python3 install.py desktop-on`，完全退出并重新打开 Claude，在 Code 会话打开 **Transcript view → Thinking**。CC Switch 重新应用配置后，可重新运行 `desktop-on`。[CC Switch 桌面配置指南](https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/zh/2-providers/2.6-claude-desktop.md)
- **服务**仅监听 `127.0.0.1:15722`。Argos 版注册当前用户的登录启动。在无桌面会话的 Linux 环境，CLI 启动时会按需拉起服务，也可运行 `python3 install.py start`。

运行 `desktop-off` 或 `cli-off` 可从后续请求恢复原文，仍经过本地服务以便回传之前已翻译的工具上下文。要回到安装前的连接，运行 `desktop-direct` 或 `cli-direct`，重启受影响的会话。完成正在用工具的旧会话，恢复直连并退出它们后，可从仓库目录运行 `python3 install.py uninstall`。卸载会删除保存在本机的工具回传缓存和离线运行环境。

可在已启用的会话试一句「请执行 `pwd`，随后用简体中文解释这是什么目录」。观察思考区、工具结果和后续回复。该请求按原供应商规则计费。安装自检使用本机测试文本。

这是独立工具。中文显示取决于模型返回的可见思考和离线译文质量。所有工具权限仍由 Claude Code 管理。

Argos 版在安装时从 [Argos 模型索引](https://github.com/argosopentech/argospm-index) 下载英译中模型，模型源自 Jörg Tiedemann 与 Santhosh Thottingal 的 [OPUS-MT](https://aclanthology.org/2020.eamt-1.61/)，原模型许可为 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本仓库源码采用 [MIT 许可](LICENSE)。
