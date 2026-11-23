## v1.2.0 更新

Desktop 和 CLI 统一按 Anthropic Messages 协议中的可见 `thinking` 文本翻译，移除模型名称白名单，修复 GLM-5.4 被原样转发的问题。GLM、DeepSeek、豆包、Kimi、OpenAI 等，只要供应商或 CC Switch 返回相同格式的思考文本，就使用同一套翻译逻辑，不需要为每个新模型补正则。

新增 Orca 兼容：翻译启动器能合并 Orca 自动附加的 `fastMode` 与 `user,project,local` 设置来源，保留模型、恢复会话、权限和其他原生参数。显式自定义连接设置仍沿用用户配置。[Orca 设置与恢复会话说明](https://github.com/fanyb/claude-thinking-translation#在-orca-中使用)

签名、加密上下文、工具参数和最终答案保持原样；回传时恢复思考原文。兼容供应商重复使用签名的情况，也保留旧版翻译历史的回传支持。OpenAI 通常只公开思考摘要，需要上游启用摘要；没有返回可见文本时没有内容可译，无法翻译未公开或加密的内部推理。

README 补充了 Desktop 缓存旧网关地址的排查方法：在官方配置页应用翻译地址后，按提示重新启动 Claude。先完成正在运行的任务，历史英文不会重新翻译。保留 cmux 启动与恢复会话支持，以及 v1.1.2 的离线翻译工作进程自动恢复机制。[cmux 设置与恢复会话说明](https://github.com/fanyb/claude-thinking-translation#在-cmux-中使用-cli)

本次已在 Mac 上通过 Orca 的 GLM-5.4、Desktop Gateway 的 Ark GLM-5.3 中文思考、工具调用和后续回复验证。OpenAI 的验证覆盖转换后的协议和加密上下文回传，未做真实 OpenAI 供应商调用；独立 CLI 供应商测试遇到过 `529 overloaded`，未计为通过。cmux 本次只验证共享逻辑，未开启其外部控制权限。各平台构建执行兼容测试与协议自检，Windows、Linux 另执行隔离安装、开关、工具回传及卸载测试。

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
