## v1.1.2 更新

修复离线翻译进程持续返回英文却没有自动恢复的问题。工作进程退出、超时、输出损坏或未产出中文时，自动重建并重试当前片段一次。Mac 系统翻译会话也会在失效后重建。仍无法翻译的片段保留原文，工具调用继续转发。

保留 v1.1.1 的 cmux 启动和手动恢复会话支持。[cmux 设置与恢复会话说明](https://github.com/fanyb/claude-thinking-translation#在-cmux-中使用-cli)

## 选电脑对应的安装包

四个安装包都自带运行环境。安装时用图形界面操作，完成后自动打开「Claude 思考翻译」面板。面板里可以分别开启 Desktop 和 CLI 的翻译、恢复英文或恢复直连。

| 电脑 | 下载文件 | 怎么装 |
| --- | --- | --- |
| Apple 芯片 Mac，macOS 26+ | `Claude-Thinking-Translation-macOS-Apple-Silicon.dmg` | 双击磁盘映像，再打开里面的「安装 Claude 思考翻译」。首次使用请在系统设置的「翻译语言」下载英语（美国）和简体中文。 |
| Windows 10 / 11，x64 | `Claude-Thinking-Translation-Windows-x64-Setup.exe` | 双击安装，保留完成页打开面板的选项。以后从开始菜单搜索 `Claude Thinking Translation`。 |
| Linux，Intel / AMD 64 位 | `Claude-Thinking-Translation-Linux-x86_64.tar.gz` | 解压后打开「安装 Claude 思考翻译」。如果 GNOME 双击未执行，右键选「作为程序运行」。 |
| Linux，ARM64 | `Claude-Thinking-Translation-Linux-aarch64.tar.gz` | 同上。以后从应用菜单搜索「Claude 思考翻译」。 |

macOS 安装包暂无 Apple 公证，Windows 安装包暂无发布者签名。首次打开可能需要确认。Windows 在缺少 Visual C++ 运行库时会从 Microsoft 下载并校验签名。Linux 需要使用 glibc 2.35 或更新版本的桌面发行版。Windows 和 Linux 的中文面板在浏览器中显示，翻译在本机执行。

安装时保留现有 CC Switch 供应商、Claude 官方更新和开发者模式设置。已有旧版需要先从原面板恢复直连、退出相关会话，再卸载后安装新版。

[完整安装与使用说明](https://github.com/fanyb/claude-thinking-translation#下载图形安装包)
