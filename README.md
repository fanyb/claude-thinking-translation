# Claude 思考翻译

用本机离线模型把 Claude Code CLI 和 Claude Desktop Gateway 收到的英文思考片段译成简体中文。安装在当前用户目录，保留 CC Switch 供应商切换、工具回传、官方安装包和更新。模型调用仍由你自己的供应商处理和计费。

## 下载图形安装包

从 [GitHub Releases](https://github.com/fanyb/claude-thinking-translation/releases/latest) 选择对应的文件。安装包自带 Python，安装过程无需终端。完成后自动打开图形面板。

| 系统 | 下载文件 | 安装方式 |
| --- | --- | --- |
| macOS 26 或以上，Apple 芯片 | `macOS-Apple-Silicon.dmg` | 双击打开磁盘映像，再打开「安装 Claude 思考翻译」，点击「安装」。 |
| Windows 10 / 11，x64 | `Windows-x64-Setup.exe` | 双击安装，保留完成页「Open Claude Thinking Translation」的勾选。 |
| Linux，Intel / AMD 64 位 | `Linux-x86_64.tar.gz` | 在文件管理器解压，打开里面的「安装 Claude 思考翻译」。 |
| Linux，ARM64 | `Linux-aarch64.tar.gz` | 在文件管理器解压，打开里面的「安装 Claude 思考翻译」。 |

- **macOS** 初次使用系统离线翻译时，在「系统设置 → 通用 → 语言与地区 → 翻译语言」下载英语（美国）和简体中文。当前安装包没有 Apple 公证。若系统阻止打开，确认文件来自这个仓库的 Releases 后，在「系统设置 → 隐私与安全性」选择「仍要打开」。[Apple 的打开方式](https://support.apple.com/zh-cn/guide/mac-help/mh40616/mac) · [macOS 图解安装说明（PDF）](docs/Claude-Thinking-Translation-v1.1.0-macOS-Install-Guide.pdf)
- **Windows** 当前安装包未做 Authenticode 签名，SmartScreen 可能提示未知发布者。确认下载来源后，可在允许继续的电脑上点「更多信息 → 仍要运行」。如果缺少 Visual C++ 运行库，安装器会联网从 Microsoft 下载并验证签名，Windows 可能要求允许安装。[Microsoft 运行库](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist)
- **Linux** 使用 glibc 2.35 或更新版本的桌面发行版，例如 Ubuntu 22.04+、Debian 12+。如果 GNOME 双击未运行，请右键选择「作为程序运行」，默认浏览器会打开面板。Windows 和 Linux 安装包已包含离线模型。

如果已经安装了旧版，可以继续使用原面板。升级前先将 Desktop 和 CLI 恢复直连，退出相关会话，再卸载旧版。macOS Release 版从面板的应用菜单卸载，Windows 从「设置 → 应用」卸载。

## 让 Codex 或 Claude Code 安装

在要安装的电脑上打开 **本地** Codex 或 Claude Code，把这句话发给它即可。

> 从 https://github.com/fanyb/claude-thinking-translation/releases/latest 下载适合这台电脑的安装包，帮我安装 Claude 思考翻译并打开图形面板。保留我的 CC Switch 供应商、普通 `claude` 和官方更新。

若希望顺便开启，可以在这句话后加「同时开启 CLI 翻译」或「同时开启 Desktop 翻译」。安装过程不需要把供应商密钥发给助手。

## 图形面板

安装结束会自动打开 **Claude 思考翻译**。两张卡片分别控制 Claude Desktop 和 Claude Code CLI，各自可以点「开启翻译」「恢复英文」「恢复直连」。后续打开方式如下。

- **macOS 系统离线版**从 Finder 的 `~/Applications` 打开「Claude 思考翻译.app」。使用 Argos 的 Mac 可打开同目录的「Claude 思考翻译」网页快捷方式。
- **Windows**在开始菜单搜索「Claude Thinking Translation」。
- **Linux 桌面**在应用菜单搜索「Claude 思考翻译」。Windows 和 Linux 的面板用默认浏览器显示，页面和翻译服务都在本机。

从源码安装时，也可在仓库目录运行 `python3 install.py panel`，Windows 用 `py -3 install.py panel`。WSL 或没有桌面会话的机器可继续用下方命令操作。从源码安装如需跳过打开窗口，使用 `install --no-open`。

## 在 cmux 中使用 CLI

1. 在 Mac 上安装 v1.1.1 或更新版本，并在「Claude 思考翻译」面板的 CLI 卡片点「开启翻译」。
2. 在 cmux 的「设置 → 自动化（Automation）→ Claude Binary Path」填入 `~/.local/bin/claude-zh` 的完整路径。可在终端运行 `printf '%s\n' "$HOME/.local/bin/claude-zh"` 查看路径。[cmux 配置说明](https://cmux.com/docs/configuration#automation)
3. 新开一个 cmux 终端，运行 `claude` 开始新会话。要继续旧会话，等当前任务结束后，在原会话输入 `/exit`，然后到新开的 cmux 终端，在同一项目目录运行 `claude --resume` 并选回原会话。

恢复会话后发出的新请求会使用翻译，已有的英文思考记录会保留。思考区折叠时按 **Ctrl+O** 展开。侧栏状态继续由 cmux 更新，思考区的显示时机由 Claude Code 控制。

要恢复英文，在面板的 CLI 卡片点「恢复英文」。要让新会话恢复原连接，点「恢复直连」，等正在执行的工具完成后再退出并重开相关会话。也可清空 cmux 的 Claude Binary Path，恢复它原来的启动方式。

## 支持范围

| 环境 | 默认引擎 | 使用入口 |
| --- | --- | --- |
| macOS 26+，Apple 芯片 | macOS 系统离线翻译 | Claude Code CLI、CC Switch Desktop Gateway、macOS 控制面板 |
| Windows x64 | Argos 离线 | 本地图形面板、Claude Code CLI、CC Switch Desktop Gateway |
| Linux x86-64 / ARM64 | Argos 离线 | 本地图形面板、Claude Code CLI、装有 Claude Desktop 且 CC Switch 已配置 Gateway 时可启用桌面翻译 |
| WSL | Argos 离线 | 在 WSL 内安装并使用 Linux CLI，使用 WSL 自己的 Claude 配置和可达的供应商 |

从源码安装 Argos 时，需要 Python 3.10+（推荐 3.12）、可用的原生依赖和首次联网下载约 67 MB 模型。macOS 也可从源码使用 `install --engine argos`。[CTranslate2 环境要求](https://opennmt.net/CTranslate2/installation.html)

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

Linux Release 版可用自带的 Python 卸载。默认安装路径下的命令是 `~/.local/share/claude-thinking-translation/venv/bin/python ~/.local/share/claude-thinking-translation/install.py uninstall`。如果设置了 `XDG_DATA_HOME`，请使用该目录下的 `claude-thinking-translation`。

可在已启用的会话试一句「请执行 `pwd`，随后用简体中文解释这是什么目录」。观察思考区、工具结果和后续回复。该请求按原供应商规则计费。安装自检使用本机测试文本。

这是独立工具。中文显示取决于模型返回的可见思考和离线译文质量。所有工具权限仍由 Claude Code 管理。

翻译工作进程退出、超时、输出损坏或没有产出中文时，网关会重建工作进程，并重试当前片段一次。Mac 系统翻译会话失效时也会先重建系统会话。持续失败的片段保留原文，模型回复和工具调用继续转发；历史中的英文不会重新翻译。

Argos 版在安装时从 [Argos 模型索引](https://github.com/argosopentech/argospm-index) 下载英译中模型，模型源自 Jörg Tiedemann 与 Santhosh Thottingal 的 [OPUS-MT](https://aclanthology.org/2020.eamt-1.61/)，原模型许可为 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本仓库源码采用 [MIT 许可](LICENSE)。
