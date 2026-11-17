# 给协助安装的 Codex 或 Claude Code

- 在用户要使用 Claude 的本机操作，先读 README，检查系统和架构，优先从 GitHub Releases 选择匹配的图形安装包。安装包自带 Python，使用当前用户安装。保留已有工作目录和安装，遇到系统确认窗口请让用户本人确认。
- 没有匹配的安装包时再用源码方式。在新目录检出仓库，检查 `python3 --version`（Windows 用 `py -3 --version`），运行 `python3 install.py install`，Windows 替换 Python 启动命令。默认在 Apple 芯片 macOS 26+ 用系统离线引擎，在 Windows/Linux/其他支持的 macOS 用 Argos。苹果系统语言包或命令行工具缺失时说明确切的系统操作。用户选择换引擎时可改用 `--engine argos`。
- 图形安装器会执行离线自检。源码安装后依次运行 `python3 install.py check` 和 `python3 install.py status`。尚未配置 Desktop Gateway 的电脑可用于 CLI。不要输出或复制现有 API 密钥、配置文件全文或会话内容。自检不调用供应商。
- 只在用户要求开启时执行 `cli-on` 或 `desktop-on`。`desktop-on` 前应已有 CC Switch 本地模型映射。保留普通 `claude` 和现有供应商，不改应用程序安装包或开发者模式。已安装时先检查状态，避免覆盖或卸载现有版本。
- 向用户说明实际引擎和通过的自检，优先引导使用面板的按钮。Windows 从开始菜单搜索 Claude Thinking Translation，Linux 从应用菜单、macOS 从 `~/Applications` 打开，也可运行 `python3 install.py panel`。CLI 的启动命令在面板中，Desktop 在完全退出并重新打开 Claude 后选 Thinking 视图。在用户同意发测试消息时再验证真实供应商和工具调用。
