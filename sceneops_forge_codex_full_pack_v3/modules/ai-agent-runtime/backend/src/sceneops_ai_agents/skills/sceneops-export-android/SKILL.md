---
name: sceneops-export-android
description: 将当前 Web/Three.js 项目通过 Capacitor 导出 Android APK 或用户指定的 AAB，定位 Gradle、SDK、资源和真机运行问题；不要求先经过 Unity 或 Xcode。
---

# 安卓导出

识别实际 Web 构建方式和 Capacitor 配置；已有原生安卓目录时增量修复，不重新生成覆盖。没有安卓目录时在导出任务工作目录准备包装工程。版本以项目锁文件和对应官方迁移说明为准；不要复制参考资料的 SDK/AGP 数字当作通用配置。

先读取包管理器、Capacitor core/cli/android 版本是否匹配，随后读取 Gradle wrapper、AGP、compileSdk、buildTools、minSdk 与 targetSdk。缺失或找不到 JDK/SDK 时调用环境技能补齐，补完立即重试。使用工程 Gradle wrapper，不依赖主机随意安装的 Gradle。

完成 Web 构建并核对入口、相对/根路径、public 资源、字体、图片和模型。webDir 指向本次真实产物；本地试玩不遗留 server.url 或对开发服务器的依赖。新增平台执行 add，资源或插件变化执行 sync；旧工程已经存在时不重复 add。然后按目标运行 assembleDebug 或已授权 release/bundle 任务，保存完整失败日志。

调试 APK 用于当前首期真机安装；AAB 是商店提交产物，不称为可直接安装的 APK。正式签名需求不要用调试密钥替代；不因 APK 安装冲突自动卸载设备上的现有应用或删除其数据。

失败诊断：
- Gradle 启动失败：核对实际 Java、wrapper 和 AGP 兼容性，先改具体缺项而非清空 ~/.gradle。
- 白屏/旧内容：核对 webDir、sync 时间、包内资源、WebView 控制台和网络请求；不关闭 HTTPS/CSP 来掩盖资源路径错误。
- 插件缺失：核对安装清单、sync 和原生注册，再运行 doctor；避免任意增加权限。
- 安装失败：核对设备 ABI、Android 版本、包标识、版本号和签名，再确定解决方式。

验证先 `adb devices` 确认实际设备和授权状态，再在用户选择的设备安装、启动并读取 logcat/WebView 错误。检查触控移动、主要交互、方向和安全区，不能用桌面鼠标或模拟器启动证明真机触控通过。触控源码缺失按当前开发授权衔接，保留导出任务与来源版本。

参考与来源见 [Capacitor 资料](references/sources.md)。
