# 模块快速索引

本文是模块快速索引，帮助接手者先定位文件。正式维护规则、流程细节和版本说明以 [docs/README.md](/E:/aitools/shapeyourphoto/docs/README.md) 为准；如果旧版本说明与当前行为冲突，以 1.2.6 文档和代码为准。

## 启动链路

- [start.bat](/E:/aitools/shapeyourphoto/start.bat)：普通 Windows 用户双击入口，负责查找 Python 并进入启动 helper。
- [tools/launcher/start_helper.py](/E:/aitools/shapeyourphoto/tools/launcher/start_helper.py)：显示中英文阶段提示，检查运行依赖，缺少依赖时按需安装，然后启动 GUI。
- [tools/launcher/python_missing.ps1](/E:/aitools/shapeyourphoto/tools/launcher/python_missing.ps1)：Python 缺失时的可读提示窗口。
- [app.py](/E:/aitools/shapeyourphoto/app.py)：源码包 GUI 薄启动器，加入 `src/` 模块路径并创建 Tk 根窗口。
- [app.pyw](/E:/aitools/shapeyourphoto/app.pyw)：无控制台 GUI 入口。
- [tools/legacy/](/E:/aitools/shapeyourphoto/tools/legacy)：旧 `setup_deps.bat`、`start_app.bat` 和 `start_app.vbs` 兼容入口，普通用户不需要使用。

## 应用代码

- [src/ui_app.py](/E:/aitools/shapeyourphoto/src/ui_app.py)：主应用控制中心。管理列表、导入、扫描、分析/修复调度、run_id/cancel_event、Console 合并刷新、cleanup/similar 弹窗入口、统计和右侧信息区。
- [src/ui_*](/E:/aitools/shapeyourphoto/src/ui_analysis_actions.py)：主窗口 mixin，承载扫描、分析、修复、列表、Console 和复核流程。
- [src/ui/](/E:/aitools/shapeyourphoto/src/ui)：窗口标题、display mapping、主题、HiDPI、Splash、EXIF 编辑、云端更新/公告 UI。
- [src/analysis/](/E:/aitools/shapeyourphoto/src/analysis)：分析流水线、人像识别、cleanup candidate 和共享分析工具。
- [src/analyzer.py](/E:/aitools/shapeyourphoto/src/analyzer.py)：兼容入口，只导出 `analysis` 包中的 `analyze_image()` 和 `is_supported_image()`。
- [src/repair_planner.py](/E:/aitools/shapeyourphoto/src/repair_planner.py)、[src/repair_engine.py](/E:/aitools/shapeyourphoto/src/repair_engine.py)、[src/repair_ops.py](/E:/aitools/shapeyourphoto/src/repair_ops.py)：修复规划、执行和图像算子。
- [src/similar_detector.py](/E:/aitools/shapeyourphoto/src/similar_detector.py)：批次级相似图片检测。
- [src/app_metadata.py](/E:/aitools/shapeyourphoto/src/app_metadata.py)：应用名、版本号、应用身份和内置版本历史。
- [src/updater.py](/E:/aitools/shapeyourphoto/src/updater.py)：独立 GUI updater。

## 工具、构建与文档

- [tools/benchmark/benchmark_test_images.py](/E:/aitools/shapeyourphoto/tools/benchmark/benchmark_test_images.py)：本地性能基准工具；`test/` 为空时安全跳过，不属于日常启动流程。
- [build/](/E:/aitools/shapeyourphoto/build)：PyInstaller、Inno Setup 和 dmg 构建脚本。
- [assets/](/E:/aitools/shapeyourphoto/assets)：图标和更新验签公钥等资源。
- [docs/](/E:/aitools/shapeyourphoto/docs/README.md)：正式维护文档体系。
- [private_docs/](/E:/aitools/shapeyourphoto/private_docs)：私有文档目录，继续由 `.gitignore` 排除。

## 已废弃但需记住的旧入口

- 独立 `single_image_window.py` 和“单图模式”不是当前主路径；单张图片通过主列表导入。
- 孤立“去噪当前”按钮不是当前主路径；降噪由分析、修复规划和修复执行链统一处理。
- 批量修复长详情不应回退到普通 `messagebox`；应继续使用 `repair_completion_dialog.py`。
