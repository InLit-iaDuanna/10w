---
name: sceneops-export-desktop
description: 使用 Electron 与 electron-builder 导出 macOS 或 Windows 本地可玩包，并修复打包、架构、包内资源和启动问题；保留项目现有桌面架构。
---

# 桌面导出

先检查已有 Electron / builder 工程和目标：macOS arm64、macOS x64、Windows x64。当前默认 ZIP 中包含应用及依赖，用户要求后再做安装器、签名和自动更新。已有其他桌面技术时保留，不为套用本技能重写项目。

复用当前 Web 构建输出，Electron 主进程与网页渲染进程分离。保持 sandbox、contextIsolation、webSecurity，关闭渲染器 Node 集成；不要用关闭安全设置修复白屏。保留项目现有安全机制，仅按所需能力暴露最小接口。

使用项目选定的 electron-builder 和 Electron 版本；锁文件与目标架构保持一致。原生 Node 依赖必须有目标平台预构建或在相应环境编译，交叉打包成功不代表原生模块可运行。缺少依赖/toolset 时读取具体失败日志，使用环境技能补齐，保留其他成功平台。

构建时明确 platform/arch/target，默认 `--publish never`，以免打包命令意外上传。保留必要 license/notice 与资源。ZIP 中的 .app 或 .exe 及依赖是一个整体，不能只给 Windows 主 exe。

排查资源：独立启动包内应用，核对实际协议和资源根目录；ASAR 路径、中文、空格、字体、模型及根路径都需检查。Node 主进程加载本地页面时避免任意文件读取；协议处理对路径进行规范化和目录限制。查 Electron/WebView 控制台，别通过用户开发机的 localhost 服务掩盖缺失资源。

macOS 应用与签名在 Mac 上处理；Windows 目标可按官方支持交叉构建，但缺原生依赖或目标环境时补齐真实运行环境，不伪报 Windows 验证。实际无法取得目标编译或运行环境时报告缺口与可继续条件，保留成功平台产物。Apple Silicon/Intel 分别标明，不把 arm64 包叫通用包。若代码签名、公证或系统安全提示阻止发行，按用户的发行目标处理，不移除 quarantine 或关闭 Gatekeeper。

用生成后的应用验证窗口启动、键鼠、失焦/重新聚焦、主要玩法、退出及资源读取；停止开发服务器后再次启动。找不到目标机器时报告包生成状态和待验证的平台，不做截图替身。

具体平台差异见 [Electron 官方项目资料](references/sources.md)。
