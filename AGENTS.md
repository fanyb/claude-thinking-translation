# 给协助安装的 Codex 或 Claude Code

- 在用户要使用 Claude 的本机执行。检查操作系统、架构和 `python3 --version`（Windows 用 `py -3 --version` 或 `python --version`）。在新目录检出本仓库，先读 README。已有工作目录和安装保持原样。安装不需要管理员权限。
- 运行 `python3 install.py install`（Windows 替换 Python 启动命令）。默认在 Apple 芯片 macOS 26+ 用系统离线引擎，在 Windows/Linux/其他支持的 macOS 用 Argos。苹果系统语言包或命令行工具缺失时，请向用户说明确切的系统操作；只有用户选择换引擎才改用 `--engine argos`。
- 安装后依次运行 `python3 install.py check` 和 `python3 install.py status`。尚未配置 Desktop Gateway 的电脑可用于 CLI。不要输出或复制现有 API 密钥、配置文件全文或会话内容。自检不调用供应商。
- 只在用户要求开启时执行 `cli-on` 或 `desktop-on`。`desktop-on` 前应已有 CC Switch 本地模型映射。保留普通 `claude` 和现有供应商，不改应用程序安装包或开发者模式。已安装时先检查状态，避免覆盖或卸载现有版本。
- 向用户说明实际引擎、通过的自检和开启的入口。CLI 用 `python3 install.py claude`，Desktop 在完全退出并重新打开 Claude 后选 Thinking 视图。说明如何用 `cli-off`/`desktop-off` 恢复原文，以及 `cli-direct`/`desktop-direct` 恢复直连。在用户同意发测试消息时再验证真实供应商和工具调用。
