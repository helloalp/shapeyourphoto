# Portrait-Aware Analysis

本文记录当前人像感知分析的维护口径。1.1.3/1.1.4 的历史演进详见 `docs/updates/`；当前以 1.1.6 说明和代码为准。

## 目标

- 降低闪光灯人像、毕业照、合影和背光人物被误判为普通欠曝/过曝的概率。
- 区分真实正面/近正面人脸、背身或侧背身人物、画作/海报脸和纹理误检。
- 只做质量分析和修复策略保护，不做人脸身份识别，不做复杂美颜。

## 模块分工

- [src/analysis/portrait.py](/E:/aitools/shapeyourphoto/src/analysis/portrait.py)：候选检测、验证、分类和区域构建。
- [src/analysis/core.py](/E:/aitools/shapeyourphoto/src/analysis/core.py)：消费人像结果，生成 issues、场景字段、诊断说明和 cleanup candidate meta。
- [src/repair_planner.py](/E:/aitools/shapeyourphoto/src/repair_planner.py)：根据 portrait policy 限制修复方法和强度。
- [src/repair_ops.py](/E:/aitools/shapeyourphoto/src/repair_ops.py)：执行局部增强、背景保护和场景化降噪。
- [src/repair_engine.py](/E:/aitools/shapeyourphoto/src/repair_engine.py)：候选评分、回退和保存决策。

## 候选分层

- `raw_face_candidates`：宽松候选，用于排查来源。
- `face_candidates`：包含 classification、accepted、is_real_face、is_frontal、rejection_reasons 的明细。
- `validated_face_boxes`：通过验证的真实正面/近正面人脸，才可进入真人 portrait policy、真人虚焦判断和真人相关 cleanup candidate。

维护时不要把 raw candidate 直接当作真实人脸使用。

## 当前分类

- `real_frontal_face` / `real_near_frontal_face`：可进入真人 portrait policy。
- `artwork_face`：画作、海报、印刷品中的脸，不触发真人虚焦删除。
- `non_frontal_face_candidate`：非正面候选，不进入 frontal portrait blur。
- `back_view_proxy`：背身或侧背身人物上下文，不触发真人脸部虚焦。
- `texture_false_positive`：肤色相近纹理或边缘误检。

## 场景与修复联动

- `portrait_type` 表示人像类型，如 `real_frontal_portrait`、`real_multi_portrait`、`artwork_face_context`、`back_view_person_context`。
- `portrait_scene_type` 表示人像曝光场景，如暗背景、高调背景、背光等。
- 主体曝光正常时，不应仅因背景偏暗强行全局提亮。
- 高调背景或白墙/天空场景，不应默认强压高光导致背景发灰。
- 降噪在人像场景中必须保护脸部和皮肤纹理。

## cleanup candidate 边界

真人虚焦 cleanup candidate 只能来自 validated real face / subject 判断。背身人物、画作脸和低置信 raw candidate 不得触发“真实正面人像脸部严重虚焦，建议删除”。

当前已知高风险回归：

- 背身/侧背身人物被误判为真实正面脸。
- 画作或海报脸触发真人虚焦删除。
- 暗背景人像被当作普通欠曝强提亮。
- 高调背景人像被过度压暗。

## 性能与计时

人像检测和区域构建可能是慢阶段。新增耗时应写入 `perf_timings`，如 `face_detect`、`portrait_region_build`、`mask_build`、`mask_feather`。用户可读提示写入 `perf_notes`。
