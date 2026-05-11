# Performance Benchmarks

本文记录本地真实图片 benchmark 规则和已知基线。并发、GPU 和 Console 规则见 [PERFORMANCE_AND_CONCURRENCY.md](/E:/aitools/shapeyourphoto/docs/technical/PERFORMANCE_AND_CONCURRENCY.md)。

## `test/` 本地样张目录

`test/` 用于本地真实图片性能和回归检查。

- 图片文件被 `.gitignore` 忽略，不得提交。
- [test/README.md](/E:/aitools/shapeyourphoto/test/README.md) 保留目录约定。
- 推荐覆盖人像、连拍/相似图、建筑、窗景/背光、高饱和、噪点高 ISO、大尺寸照片。
- `tools/benchmark/benchmark_test_images.py` 在目录缺失或无图片时必须安全跳过。

当前 `.gitignore` 约定：

```gitignore
/test/*
!/test/README.md
!/test/.gitkeep
```

## 计时术语

- `wall_time`：用户真实等待时间。
- `worker_cumulative_time`：所有 worker 单图耗时累计，并发时可以大于 `wall_time`。
- `average_wall_time_per_image`：`wall_time / image_count`。
- `average_worker_time_per_image`：`worker_cumulative_time / successful_image_count`。
- `queue_wait_cumulative`：任务提交到 worker 开始之间的等待累计。
- `parallel_efficiency`：`worker_cumulative_time / wall_time`，用于观察并发利用情况。

Console 和 benchmark 摘要必须优先展示 `wall_time`，避免把 worker cumulative 误读成用户等待时间。

## 运行方式

```powershell
python tools/benchmark/benchmark_test_images.py
```

默认会在被忽略的 `benchmark_reports/` 目录生成一份 JSON 报告和一份 Markdown 报告。可用参数调整目录：

```powershell
python tools/benchmark/benchmark_test_images.py --report-dir benchmark_reports --modes single,medium
```

输出应包含：

- 模式和 requested/actual workers。
- wall time、平均 wall time、worker cumulative、parallel efficiency。
- queue/wait、相似检测耗时、相似组数量。
- 问题图数量、cleanup candidate 数量。
- slow images 和 slow stages。
- 如果存在上一份报告，输出 wall time、issues、cleanup candidates、similar groups 的简单变化。

## 本地 manifest 对比

可复制 [test/manifest.example.json](/E:/aitools/shapeyourphoto/test/manifest.example.json) 为 `test/manifest.json`。真实 manifest 默认被 `.gitignore` 忽略，因为其中可能包含用户图片文件名。

manifest 可标注：

- 文件名。
- 场景类型。
- 预期 issues。
- 是否应产生 cleanup candidate。
- 是否应进入 similar group。
- 不应误判的问题。
- 备注。

benchmark 如果发现 `test/manifest.json`，会按文件名输出简单通过/失败对比；不存在时正常跳过。

## 2026-05-07 基线

本地 `test/` 当时包含 16 张真实 JPG。working-image 优化前：

| mode | workers | wall time | avg wall/img | worker cumulative | efficiency | similar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 1 | 164.03s | 10.25s | 158.49s | 0.97x | 5.55s |
| low | 2 | 103.25s | 6.45s | 195.79s | 1.90x | 3.03s |
| medium | 6 | 53.51s | 3.34s | 283.96s | 5.31x | 1.39s |
| high | 16 | 53.29s | 3.33s | 609.98s | 11.45x | 0.94s |

working-image、噪点尺度校正和 JPEG draft 特征提取后：

| mode | workers | wall time | avg wall/img | worker cumulative | efficiency | similar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 1 | 76.67s | 4.79s | 75.29s | 0.98x | 1.38s |
| low | 2 | 46.78s | 2.92s | 89.07s | 1.90x | 0.76s |
| medium | 6 | 26.21s | 1.64s | 140.11s | 5.35x | 0.34s |
| high | 16 | 23.92s | 1.49s | 274.30s | 11.47x | 0.33s |

质量抽查保持稳定：6 张问题图、3 个 cleanup candidates、4 个相似组。
