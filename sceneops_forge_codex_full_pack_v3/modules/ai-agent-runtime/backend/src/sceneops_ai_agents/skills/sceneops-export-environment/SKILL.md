---
name: sceneops-export-environment
description: 为导出任务检查并补齐本机 Node、JDK、Android SDK、桌面打包工具与配置；用于原生 Agent 在已有电脑操作授权下处理构建环境缺项。
---

# 本机构建环境

从运行时上下文确定主机系统/架构、目标平台、源码目录、输出目录、已允许的操作，再检查相关工具。只需要 APK 时不安装 Xcode；在 Mac 上打 Windows 包不等于已在 Windows 上验证。

读取 package.json、锁文件、Capacitor 版本、Gradle wrapper/AGP/SDK 配置、Electron 与 builder 配置，沿用工程已选版本。识别已安装工具及路径问题，优先使用已有兼容版本。不要凭一份旧示例把整个项目升级到最新版。

缺项处理顺序：发现实际缺失 → 从官方发行或已配置可信包管理器补齐兼容版本 → 当前任务配置路径 → 执行健康检查 → 重试原失败步骤。一次已授权导出包含的常规补齐持续完成，不把每个命令都交给用户。是否允许系统安装由当前执行授权决定，不能从本文件推导。

- macOS：检查 `uname -m`、`node --version`、包管理器与 `java -version`；`/usr/libexec/java_home -V` 可列出已安装 JDK。Android Studio 自带的 JDK 也需检查实际版本。优先任务进程 JAVA_HOME/ANDROID_HOME，不默认写全局 shell 配置。
- Windows：检查实际进程架构、Node/JDK/SDK 位置与 PATH；用已安装的受信包管理器或官方安装程序。路径含空格时传参正确引用，不靠迁移用户工程避开问题。
- Android：先发现现有 Android CLI / sdkmanager。Android Developers 的 sdkmanager 页面现推荐 Android CLI 的 `android sdk` 子命令；先检查是否已有该 CLI，已有兼容工程仍可用 sdkmanager，不因说明变化重装工具链。先列出组件，再根据工程 compileSdk/buildTools 安装所缺包，查看当前官方帮助，不凭旧示例切换工具链。SDK 许可或管理员界面需要用户操作时保留待续点，不自动回答所有许可提示。
- 桌面：先尝试所选目标的实际构建，再依据日志判断缺少 toolset、Wine 或目标原生模块编译器；不先安装虚拟机、Docker 或大套件。

依赖安装先审查清单和生命周期脚本。已知可信工具所需初始化仅在授权范围内执行，不解除宿主的脚本限制、不执行下载页给出的未审查管道命令。安装器需改变系统安全或账号访问时遵守实际权限边界。

环境诊断与日志只保留工具版本、错误和任务相关路径，不复制整个环境变量、npmrc、密钥链或用户配置到提示词或产物。失效网络请求先检查来源与连接，不换不可信镜像、不关闭 TLS。

读取 [平台来源与版本依据](references/sources.md) 查当前官方要求；包管理器与 SDK 具体版本以工程和当前官方资料为准。
